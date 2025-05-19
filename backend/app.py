import sys
import os

# Add project root to Python path to fix import issues
# This assumes 'backend' is a sub-directory of the project root.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root) # Insert at the beginning

from fastapi import FastAPI, WebSocket, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import json
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from datetime import datetime
import logging
from fastapi.responses import FileResponse

from backend.utils.websocket_manager import websocket_manager
from backend.utils.data_utils import (
    get_latest_jsonl_file,
    read_jsonl_file,
    calculate_days_since_crawl
)
from backend.crawler import HolmesPlaceCrawler
from backend.utils.logger import logger
from backend.utils.config import Config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Holmes Place Crawler API")
    Config.ensure_output_dir()
    yield
    # Shutdown
    logger.info("Shutting down Holmes Place Crawler API")

app = FastAPI(title="Holmes Place Crawler API", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend/dist")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    logger.warning(f"Static directory not found: {static_dir}")

# Add a root endpoint to serve the frontend
@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("New WebSocket connection request received")
    await websocket_manager.connect(websocket)
    
    # Use a variable to track connection state
    is_connected = True
    
    try:
        while is_connected:
            # Keep connection alive and handle messages
            try:
                # Use a timeout to prevent blocking indefinitely
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                logger.info(f"Received WebSocket message: {data}")
                
                # Attempt to parse JSON message
                try:
                    json_data = json.loads(data)
                    if isinstance(json_data, dict) and "action" in json_data:
                        action = json_data["action"]
                        logger.info(f"Processing WebSocket action: {action}")
                        
                        if action == "get_status":
                            status_data = {
                                "type": "status",
                                "message": "Current crawler status",
                                "data": websocket_manager.get_status(),
                                "timestamp": datetime.now().isoformat()
                            }
                            await websocket.send_json(status_data)
                            logger.info("Sent status response to client")
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON message: {data}")
                    # Not an error, just continue
                    
            except asyncio.TimeoutError:
                # Just a timeout, not an error - send a ping to keep connection alive
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception:
                    # If we can't send ping, assume connection is closed
                    logger.info("WebSocket ping failed, assuming client disconnected")
                    is_connected = False
                    
            except Exception as msg_error:
                # Any other error means we should stop the loop
                logger.error(f"Error processing WebSocket message: {str(msg_error)}")
                is_connected = False
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        logger.info("WebSocket client disconnecting")
        websocket_manager.disconnect(websocket)

@app.get("/api/status")
async def get_status():
    """Get current crawl status."""
    return websocket_manager.get_status()

@app.post("/api/start-crawl")
async def start_crawl():
    """Start the crawling process."""
    if websocket_manager.status["is_running"]:
        raise HTTPException(status_code=400, detail="Crawl already in progress")
    
    try:
        # Get the latest clubs data to determine which clubs to crawl
        logger.info("Looking for latest JSONL file...")
        holmes_file = get_latest_jsonl_file()
        if not holmes_file:
            logger.error("No JSONL file found in data directory")
            raise HTTPException(status_code=404, detail="No clubs data available")
        
        logger.info(f"Found holmes.jsonl file: {holmes_file}")
        logger.info("Reading clubs data...")
        data = read_jsonl_file(holmes_file)
        if not data:
            logger.error("No valid data found in JSONL file")
            raise HTTPException(status_code=404, detail="No valid data found in file")
        
        logger.info(f"Read {len(data)} entries from JSONL file")
        clubs_to_process = []
        
        # Extract clubs from the data
        for entry in data:
            logger.debug(f"Processing entry: {entry}")
            # If entry has a "clubs" key, process each club
            if "clubs" in entry:
                clubs_data = entry["clubs"]
                for club_name, club_info in clubs_data.items():
                    # Get URL if it exists
                    url = club_info.get("url", "")
                    
                    # Create club object with basic info
                    clubs_to_process.append({
                        "name": club_name,
                        "url": url,  # May be empty, crawler will handle fetching
                        "status": club_info.get("status", "unknown")
                    })
            # If entry is a direct club entry
            elif "club_name" in entry:
                club_name = entry["club_name"]
                url = entry.get("url", "")
                
                clubs_to_process.append({
                    "name": club_name,
                    "url": url,  # May be empty, crawler will handle fetching
                    "status": entry.get("status", "unknown")
                })
        
        if not clubs_to_process:
            error_msg = "No clubs found in data"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
        
        logger.info(f"Found {len(clubs_to_process)} clubs to process")
        logger.debug(f"Clubs to process: {clubs_to_process}")
        
        # Update status to running
        await websocket_manager.update_status(
            is_running=True,
            progress=0,
            current_club=None,
            error=None
        )
        
        # Start crawler in background with clubs to process
        asyncio.create_task(run_crawler(clubs_to_process))
        
        return {"message": "Crawl started successfully"}
    except HTTPException as he:
        # Log the error
        logger.error(f"Error starting crawl: {he.detail}")
        # Update status to error
        await websocket_manager.update_status(
            is_running=False,
            error=he.detail
        )
        # Re-raise the HTTP exception
        raise
    except Exception as e:
        # Log the error
        error_msg = str(e) or "Unknown error occurred"
        logger.error(f"Error starting crawl: {error_msg}")
        # Update status to error
        await websocket_manager.update_status(
            is_running=False,
            error=error_msg
        )
        # Return error response
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/api/data")
async def get_data():
    """Get the latest crawl data."""
    try:
        holmes_file = get_latest_jsonl_file()
        if not holmes_file:
            raise HTTPException(status_code=404, detail="No data available")
        
        data = read_jsonl_file(holmes_file)
        days_since_crawl = calculate_days_since_crawl(holmes_file)
        
        return {
            "data": data,
            "days_since_crawl": days_since_crawl
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/instructors")
async def get_instructors():
    """Get list of all instructors from the latest data."""
    try:
        holmes_file = get_latest_jsonl_file()
        if not holmes_file:
            return {"instructors": []}
        
        data = read_jsonl_file(holmes_file)
        instructors = set()
        
        for entry in data:
            if "classes" in entry:
                for class_data in entry["classes"]:
                    if "instructor" in class_data and class_data["instructor"]:
                        instructors.add(class_data["instructor"])
        
        return {"instructors": sorted(list(instructors))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/clubs")
async def get_clubs():
    """Get list of all clubs from the latest data."""
    try:
        # Try various possible locations for club data in order of preference
        candidates = [
            Path(__file__).resolve().parent.parent / "data" / "holmes.jsonl"
        ]
        
        clubs_file = None
        for candidate in candidates:
            if candidate.exists():
                clubs_file = candidate
                break

        if clubs_file is None:
            # Hardcoded fallback - create an in-memory clubs structure
            clubs_data = {
                "clubs": {
                    "הולמס פלייס תל אביב": {
                        "url": "https://www.holmesplace.co.il/club-page-tel-aviv/",
                        "status": "active",
                        "area": "מרכז",
                        "opening_hours": {
                            "ראשון": "06:00-23:00",
                            "שני": "06:00-23:00",
                            "שלישי": "06:00-23:00",
                            "רביעי": "06:00-23:00",
                            "חמישי": "06:00-23:00",
                            "שישי": "06:00-22:00",
                            "שבת": "08:00-22:00"
                        }
                    },
                    "הולמס פלייס הרצליה": {
                        "url": "https://www.holmesplace.co.il/club-page-herzliya/",
                        "status": "active",
                        "area": "שרון",
                        "opening_hours": {
                            "ראשון": "06:00-23:00",
                            "שני": "06:00-23:00",
                            "שלישי": "06:00-23:00",
                            "רביעי": "06:00-23:00",
                            "חמישי": "06:00-23:00",
                            "שישי": "06:00-22:00",
                            "שבת": "08:00-22:00"
                        }
                    }
                }
            }
            data = [clubs_data]
            logger.info("Using hardcoded fallback clubs data")
        else:
            logger.info(f"Loading clubs from: {clubs_file}")
            data = read_jsonl_file(str(clubs_file))
        
        logger.info(f"Read {len(data)} entries from clubs data source")
        logger.info(f"First entry keys: {list(data[0].keys()) if data else []}")
        if data and 'clubs' in data[0]:
            logger.info(f"Club count in first entry: {len(data[0]['clubs'])}")
            logger.info(f"First club name: {list(data[0]['clubs'].keys())[0] if data[0]['clubs'] else 'None'}")

        clubs_by_region = {}  # Dictionary to group clubs by region
        seen_clubs = set()  # Track unique clubs
        
        for entry in data:
            if "clubs" in entry:
                for club_name, club_data in entry["clubs"].items():
                    # Skip if we've already seen this club
                    if club_name in seen_clubs:
                        continue
                    seen_clubs.add(club_name)
                    
                    # Get the region/area for this club
                    area = club_data.get("area", "")
                    if not area:
                        # Try to determine area from club name
                        if "ירושלים" in club_name or "מבשרת" in club_name or "מודיעין" in club_name:
                            area = "ירושלים והסביבה"
                        elif "תל אביב" in club_name or "רמת גן" in club_name or "בני ברק" in club_name or "גבעתיים" in club_name or "דיזנגוף" in club_name or "עזריאלי" in club_name or "פתח תקווה" in club_name or "ראש העין" in club_name or "גבעת שמואל" in club_name or "קריית אונו" in club_name or ("ראשון לציון" in club_name and ("גו אקטיב" in club_name or "פרימיום" in club_name)):
                            area = "מרכז"
                        elif "חיפה" in club_name or "קריות" in club_name or "קריון" in club_name or "גרנד קניון" in club_name or "חדרה" in club_name or "קיסריה" in club_name:
                            area = "צפון"
                        elif "באר שבע" in club_name or "אשדוד" in club_name:
                            area = "דרום"
                        elif "נתניה" in club_name or "הרצליה" in club_name or "רעננה" in club_name or "כפר סבא" in club_name or "שבעת הכוכבים" in club_name:
                            area = "שרון"
                        elif "רחובות" in club_name or ("ראשון לציון" in club_name and not ("גו אקטיב" in club_name or "פרימיום" in club_name)) or "נס ציונה" in club_name or "לוד" in club_name:
                            area = "שפלה"
                        else:
                            area = "מרכז"  # Default to מרכז
                    
                    # Get opening hours
                    opening_hours = club_data.get("opening_hours", {})
                    
                    # Get URL if it exists, but don't try to generate one
                    url = club_data.get("url", "")
                    
                    # Create club object
                    club_obj = {
                        "name": club_name,
                        "short_name": club_name.replace("הולמס פלייס ", ""),
                        "status": club_data.get("status", "unknown"),
                        "url": url,
                        "opening_hours": opening_hours
                    }
                    
                    # Add to region group
                    if area not in clubs_by_region:
                        clubs_by_region[area] = []
                    clubs_by_region[area].append(club_obj)
        
        # Convert to list of regions with clubs
        result = []
        for region, clubs in clubs_by_region.items():
            result.append({
                "region": region,
                "clubs": sorted(clubs, key=lambda x: x["name"])
            })
        
        # Sort regions in a specific order
        region_order = ["מרכז", "שרון", "שפלה", "ירושלים והסביבה", "דרום", "צפון", "אחר"]
        result.sort(key=lambda x: region_order.index(x["region"]) if x["region"] in region_order else len(region_order))
        
        return {"clubs_by_region": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/crawl-status")
async def get_crawl_status():
    """Get current crawl status."""
    try:
        holmes_file = get_latest_jsonl_file()
        status = websocket_manager.get_status()
        
        if holmes_file:
            # Get the file's last modification time
            last_update = os.path.getmtime(holmes_file)
            last_update_str = datetime.fromtimestamp(last_update).isoformat()
            status["latest_crawl_date"] = last_update_str
        
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/class-names")
async def get_class_names():
    """Get list of all class names from the latest data."""
    try:
        holmes_file = get_latest_jsonl_file()
        if not holmes_file:
            return {"class_names": []}
        
        data = read_jsonl_file(holmes_file)
        class_names = set()
        
        for entry in data:
            if "classes" in entry:
                for class_data in entry["classes"]:
                    if "name" in class_data and class_data["name"]:
                        class_names.add(class_data["name"])
        
        return {"class_names": sorted(list(class_names))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/classes")
async def get_classes(class_name: str = None, day_name_hebrew: List[str] = Query(None), instructor: str = None, club: str = None):
    """Get filtered list of classes from the latest data."""
    try:
        holmes_file = get_latest_jsonl_file()
        if not holmes_file:
            return {"classes": [], "regions_found": [], "opening_hours": {}}
        
        data = read_jsonl_file(holmes_file)
        classes = []
        regions_found = set()
        opening_hours = {}
        club_to_region = {}  # Map club names to their regions
        
        # First pass: collect club regions and opening hours
        for entry in data:
            if "club_name" in entry and "area" in entry:
                # Only add known regions to the mapping
                if entry["area"] and entry["area"] != "לא ידוע":
                    club_to_region[entry["club_name"]] = entry["area"]
                if "opening_hours" in entry:
                    opening_hours[entry["club_name"]] = entry["opening_hours"]
        
        # Second pass: process classes
        seen_classes = set()  # Track unique classes
        for entry in data:
            if "classes" in entry:
                for class_data in entry["classes"]:
                    # Apply filters
                    if class_name and class_data.get("name") != class_name:
                        continue
                    if day_name_hebrew and class_data.get("day_name_hebrew") not in day_name_hebrew:
                        continue
                    if instructor and class_data.get("instructor") != instructor:
                        continue
                    if club and class_data.get("club") != club:
                        continue
                    
                    # Create a unique key for the class
                    class_key = (
                        class_data.get("club"),
                        class_data.get("day"),
                        class_data.get("time"),
                        class_data.get("name"),
                        class_data.get("instructor"),
                        class_data.get("location")
                    )
                    
                    # Skip if we've already seen this class
                    if class_key in seen_classes:
                        continue
                    seen_classes.add(class_key)
                    
                    # Add region information to class data
                    club_name = class_data.get("club")
                    if club_name in club_to_region:
                        class_data["area"] = club_to_region[club_name]
                        regions_found.add(club_to_region[club_name])
                    
                    # Add to classes list
                    classes.append(class_data)
        
        # Define region order
        region_order = ["מרכז", "שרון", "שפלה", "דרום", "צפון"]
        
        # Sort classes by region (according to region_order) and then by day and time
        classes.sort(key=lambda x: (
            region_order.index(x.get("area", "")) if x.get("area") in region_order else len(region_order),
            x.get("day", ""),
            x.get("time", "")
        ))
        
        # Sort regions according to region_order
        sorted_regions = sorted(list(regions_found), 
                              key=lambda x: region_order.index(x) if x in region_order else len(region_order))
        
        return {
            "classes": classes,
            "regions_found": sorted_regions,
            "opening_hours": opening_hours
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_crawler(clubs_to_process):
    """Run the crawler and update status."""
    crawler = None
    try:
        logger.info("run_crawler started.")
        
        # Make sure the Playwright installation is available
        try:
            from playwright.async_api import async_playwright
            logger.info("Playwright module imported successfully")
            
            # Check if browsers are installed
            import subprocess
            import sys
            
            logger.info("Checking Playwright browser installation...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
                capture_output=True,
                text=True
            )
            logger.info(f"Playwright install result: {result.returncode}")
            if result.stdout:
                logger.info(f"Playwright install output: {result.stdout}")
            if result.stderr:
                logger.warning(f"Playwright install warnings: {result.stderr}")
                
            # Give the system a moment to complete any background tasks
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Failed to check Playwright installation: {e}")
        
        # Create crawler instance with detailed parameters
        logger.info("Creating HolmesPlaceCrawler instance...")
        crawler = HolmesPlaceCrawler(
            websocket_manager=websocket_manager,
            headless=False,  # Set to False for debugging visibility
            clubs_to_process=clubs_to_process,
            output_dir=os.path.join(os.path.dirname(__file__), "data")
        )
        
        # Add a small delay before starting the crawler
        await asyncio.sleep(1)
        
        # Start the crawler with more detailed logging
        logger.info("Calling crawler.start()...")
        try:
            await crawler.start()
        except Exception as start_error:
            logger.error(f"Error during crawler.start(): {str(start_error)}", exc_info=True)
            raise start_error
        
        # Add a delay before updating status
        await asyncio.sleep(1)
        
        logger.info("run_crawler completed successfully.")
        # Update status to completed
        await websocket_manager.update_status(
            is_running=False,
            progress=100,
            current_club=None,
            error=None
        )
    except Exception as e:
        # Update status with error
        error_msg = str(e)
        logger.error(f"Crawler error in run_crawler: {error_msg}", exc_info=True)
        await websocket_manager.update_status(
            is_running=False,
            error=error_msg
        )
    finally:
        # Make sure browser is closed properly even if there was an error
        if crawler and hasattr(crawler, 'browser_manager') and hasattr(crawler.browser_manager, '_cleanup'):
            try:
                logger.info("Ensuring browser resources are cleaned up...")
                await crawler.browser_manager._cleanup()
                # Give some time for cleanup to complete
                await asyncio.sleep(1)
            except Exception as cleanup_error:
                logger.error(f"Error during final browser cleanup: {str(cleanup_error)}")

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 to allow connections from other machines
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", 8000))
    log_level = os.environ.get("LOG_LEVEL", "info")
    
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level=log_level) 