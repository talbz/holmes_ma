from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
import glob
import json
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
# Import the crawler
from crawler import HolmesPlaceCrawler
import subprocess
import logging
from pydantic import BaseModel
import traceback # Import traceback for detailed error logging
from pathlib import Path
from fastapi.responses import FileResponse

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

# Configure CORS with more specific settings
origins = [
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "*"  # For development only - remove in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global event to signal crawler termination
crawler_stop_event = asyncio.Event()

# Class to manage WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"WebSocket connection accepted from {websocket.client.host}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(f"WebSocket connection removed from active connections")

    async def broadcast(self, message: str):
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logging.error(f"Error broadcasting message: {str(e)}")
                self.active_connections.remove(connection)

# Create a connection manager instance
manager = ConnectionManager()

# Helper function to get the data directory path
def get_data_dir():
    return os.path.join(os.path.dirname(__file__), 'data')

# Define a request model for start_crawl
class CrawlRequest(BaseModel):
    headless: bool = False # Default to non-headless mode

# Define a simple region mapping (can be expanded)
REGION_MAP = {
    "צפון": ["קריון", "גרנד קניון", "חיפה", "קיסריה", "חדרה"],
    "שרון": ["רעננה", "כפר סבא", "נתניה", "הוד השרון", "הרצליה", "שבעת הכוכבים"],
    "מרכז": ["תל אביב", "פתח תקווה", "רמת גן", "גבעתיים", "ראש העין", "עזריאלי", "דיזנגוף", "גבעת שמואל", "ראשון לציון", "קריית אונו", "קרית אונו"],
    "שפלה": ["נס ציונה", "רחובות", "לוד", "אביבים"],
    "ירושלים והסביבה": ["ירושלים", "מבשרת ציון", "מודיעין", "פמלי מבשרת"],
    "דרום": ["אשדוד", "באר שבע", "אשקלון"], 
}

def get_club_region(club_name: Optional[str]) -> str:
    """Determines the region based on the club name."""
    if not club_name:
        return "לא ידוע"
    for region, keywords in REGION_MAP.items():
        if any(keyword in club_name for keyword in keywords):
            return region
    logging.warning(f"Club '{club_name}' did not match any defined region. Assigning 'לא ידוע'.")
    return "לא ידוע"

@app.get("/")
def read_root():
    return {"status": "Holmes Place Schedule API is running"}

@app.options("/ws")
async def websocket_options(request: Request, response: Response):
    """Handle preflight requests for WebSocket connections"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return {}

@app.get("/latest-data")
def get_latest_data():
    """Get the latest crawled data"""
    data_dir = get_data_dir()
    
    # Get the latest successful crawl
    latest_file = get_latest_successful_crawl_file()
    if not latest_file:
        return {"filename": None, "count": 0, "data": []}
    
    # Read and return the data
    data = []
    with open(latest_file, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    
    return {"filename": os.path.basename(latest_file), "count": len(data), "data": data}

def get_latest_successful_crawl_file():
    """Get the latest successful (complete) crawl file"""
    data_dir = get_data_dir()

    # Patterns for JSONL files (old timestamped and new plain)
    class_pattern = os.path.join(data_dir, "holmes_place_schedule*.jsonl")
    club_pattern = os.path.join(data_dir, "holmes_clubs*.jsonl")
    class_files = glob.glob(class_pattern)
    club_files = glob.glob(club_pattern)
    all_files = class_files + club_files

    if not all_files:
        logging.info("No JSONL files found in data directory")
        return None

    # Sort all JSONL files by creation time descending
    sorted_all = sorted(all_files, key=os.path.getctime, reverse=True)
    logging.info(f"Available JSONL files (newest first): {[os.path.basename(f) for f in sorted_all]}")

    # Prefer club-format files if present
    sorted_club = sorted(club_files, key=os.path.getctime, reverse=True)
    if sorted_club:
        latest = sorted_club[0]
        logging.info(f"Using newest club format file: {os.path.basename(latest)}")
        return latest

    # Otherwise, candidate is the most recent file
    latest = sorted_all[0]

    # Check status file to determine usability
    status_file = os.path.join(data_dir, "last_crawl_status.json")
    should_use_latest = True
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as sf:
                status_data = json.load(sf)
            # New format status file
            if isinstance(status_data, dict) and "crawl_results" in status_data:
                was_stopped = status_data.get("was_stopped_early", False)
                critical_error = status_data.get("critical_error_occurred", False)
                results = status_data.get("crawl_results", {})
                logging.info(f"Status file details: was_stopped_early={was_stopped}, critical_error_occurred={critical_error}, clubs_count={len(results)}")
                if (was_stopped or critical_error) and not any(d.get('status') == 'success' for d in results.values()):
                    should_use_latest = False
                    logging.info("Latest crawl is NOT usable - problematic run with no successful clubs")
            else:
                # Old format: direct club statuses
                if not any(isinstance(v, dict) and v.get('status') == 'success' for v in status_data.values()):
                    should_use_latest = False
                    logging.info("Latest crawl is NOT usable - old status format with no successful clubs")
        except Exception as e:
            logging.error(f"Error reading last crawl status: {e}")
    else:
        logging.info("No status file found, defaulting to latest file")

    if should_use_latest:
        logging.info(f"Using most recent file: {os.path.basename(latest)}")
        return latest

    # If not usable and multiple files exist, pick previous
    if len(sorted_all) > 1:
        prev = sorted_all[1]
        logging.info(f"Using previous file due to problematic latest: {os.path.basename(prev)}")
        return prev

    # Fallback: use latest anyway
    logging.info(f"Only one file exists; using it despite potential issues: {os.path.basename(latest)}")
    return latest

def _read_latest_jsonl():
    """Helper function to read all data from the latest successful JSONL file."""
    latest_file = get_latest_successful_crawl_file()
    if not latest_file:
        return []
        
    data = []
    try:
        is_club_format = "holmes_clubs_" in os.path.basename(latest_file)
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    line_data = json.loads(line)
                    
                    # If this is a club format file, extract the classes
                    if is_club_format:
                        # Each line is a club with 'classes' field containing class data
                        if 'classes' in line_data and isinstance(line_data['classes'], list):
                            # Extract all classes from this club
                            for class_data in line_data['classes']:
                                # Add club name if missing in class data
                                if 'club' not in class_data and 'club_name' in line_data:
                                    class_data['club'] = line_data['club_name']
                                # Add area/region if missing
                                if 'region' not in class_data and 'area' in line_data:
                                    class_data['region'] = line_data['area']
                                data.append(class_data)
                    else:
                        # Old format - each line is a single class
                        data.append(line_data)
                        
                except json.JSONDecodeError as decode_err:
                     logging.warning(f"Skipping malformed line in {latest_file}: {decode_err}")
    except FileNotFoundError:
        logging.error(f"Latest file {latest_file} not found during read.")
        return []
    except Exception as read_err:
         logging.error(f"Error reading {latest_file}: {read_err}")
         return []
    return data

@app.get("/clubs")
def get_clubs():
    """Get list of clubs grouped by region from the latest crawl data with status information."""
    all_data = _read_latest_jsonl()
    status_filename = os.path.join(get_data_dir(), "last_crawl_status.json")
    
    # Get unique club names
    club_names = set(item.get("club") for item in all_data if item.get("club"))
    
    # Get status information if available
    club_statuses = {}
    club_to_opening_hours = {}
    short_club_names = {}
    
    # Check if we're using a club format file by looking at the latest file
    latest_file = get_latest_successful_crawl_file()
    is_club_format = latest_file and "holmes_clubs_" in os.path.basename(latest_file)
    
    if is_club_format:
        # Read opening hours directly from the club format file
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        club_data = json.loads(line)
                        if 'club_name' in club_data and 'opening_hours' in club_data:
                            club_to_opening_hours[club_data['club_name']] = club_data['opening_hours']
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logging.error(f"Error reading opening hours from club file: {e}")
    
    # Also check status file as a fallback for older files
    if os.path.exists(status_filename):
        try:
            with open(status_filename, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
                
                # Handle both old and new status file formats
                if isinstance(status_data, dict) and "crawl_results" in status_data:
                    # New format
                    club_statuses = status_data.get("crawl_results", {})
                    # Get opening hours if not already loaded from club format
                    if not club_to_opening_hours:
                        club_to_opening_hours = status_data.get("club_to_opening_hours", {})
                    # Get short club names if available
                    short_club_names = status_data.get("short_club_names", {})
                else:
                    # Old format - direct club statuses
                    club_statuses = status_data
        except Exception as e:
            logging.error(f"Error reading club statuses: {e}")
    
    # Group clubs by region
    clubs_by_region = {}
    for club_name in club_names:
        region = get_club_region(club_name)
        if region not in clubs_by_region:
            clubs_by_region[region] = []
            
        # Get short name or create one if not available
        short_name = short_club_names.get(club_name, club_name)
        if not short_name or short_name == club_name:
            # Create a short name by removing common prefixes
            short_name = club_name
            if "הולמס פלייס" in short_name:
                short_name = short_name.replace("הולמס פלייס", "").strip()
        
        # Create club entry with status and opening hours
        club_entry = {
            "name": club_name,
            "short_name": short_name,
            "region": region,
            "status": club_statuses.get(club_name, {}).get("status", "unknown") if isinstance(club_statuses.get(club_name), dict) else club_statuses.get(club_name, "unknown"),
            "opening_hours": club_to_opening_hours.get(club_name, {})
        }
        
        clubs_by_region[region].append(club_entry)
    
    # Add any clubs from status data that are not in the data file
    for club_name, club_data in club_statuses.items():
        if club_name not in club_names:
            region = get_club_region(club_name)
            if region not in clubs_by_region:
                clubs_by_region[region] = []
                
            # Get or create short name
            short_name = short_club_names.get(club_name, club_name)
            if not short_name or short_name == club_name:
                # Create a short name by removing common prefixes
                short_name = club_name
                if "הולמס פלייס" in short_name:
                    short_name = short_name.replace("הולמס פלייס", "").strip()
            
            status = club_data.get("status", "unknown") if isinstance(club_data, dict) else club_data
            
            clubs_by_region[region].append({
                "name": club_name,
                "short_name": short_name,
                "region": region,
                "status": status,
                "opening_hours": club_to_opening_hours.get(club_name, {})
            })
    
    # Sort clubs alphabetically within each region
    for region in clubs_by_region:
        clubs_by_region[region].sort(key=lambda x: x["name"])
    
    # Convert to list format for easier frontend consumption
    result = []
    for region, clubs in clubs_by_region.items():
        result.append({
            "region": region,
            "clubs": clubs
        })
    
    # Sort regions by predefined order
    region_order = ["מרכז", "שרון", "שפלה", "ירושלים והסביבה", "דרום", "צפון", "לא ידוע"]
    result.sort(key=lambda x: region_order.index(x["region"]) if x["region"] in region_order else len(region_order))
    
    return result

@app.get("/clubs-with-status")
def get_clubs_with_status():
    """Get list of all clubs with their crawl status from the last crawl status file."""
    status_filename = os.path.join(get_data_dir(), "last_crawl_status.json")
    
    try:
        if os.path.exists(status_filename):
            with open(status_filename, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
                
                # Handle both old and new status file formats
                last_status = {}
                crawl_metadata = {}
                
                if isinstance(status_data, dict) and "crawl_results" in status_data:
                    # New format
                    last_status = status_data.get("crawl_results", {})
                    # Extract metadata
                    crawl_metadata = {
                        "was_stopped_early": status_data.get("was_stopped_early", False),
                        "critical_error_occurred": status_data.get("critical_error_occurred", False),
                        "timestamp": status_data.get("timestamp")
                    }
                else:
                    # Old format - direct club statuses
                    last_status = status_data
                
                clubs_with_status = []
                
                for club_name, result in last_status.items():
                    # Add region information for each club
                    region = get_club_region(club_name)
                    clubs_with_status.append({
                        "name": club_name,
                        "url": result.get("url", ""),
                        "status": result.get("status", "unknown"),
                        "region": region
                    })
                
                # Sort clubs by name
                clubs_with_status.sort(key=lambda c: c["name"])
                
                # Return clubs with metadata about the crawl
                response = {"clubs": clubs_with_status}
                if crawl_metadata:
                    response["crawl_status"] = crawl_metadata  # Rename from crawl_metadata to crawl_status
                
                return response
        
        return {"clubs": [], "error": "Last crawl status file not found"}
            
    except Exception as e:
        logging.error(f"Error reading last crawl status: {e}")
        return {"clubs": [], "error": str(e)}

@app.get("/class-names")
def get_class_names():
    """Get list of unique class names from the latest crawl data."""
    all_data = _read_latest_jsonl()
    class_names = set(item.get("name") for item in all_data if item.get("name"))
    return {"class_names": sorted(list(class_names))}

@app.get("/instructors")
def get_instructors():
    """Get list of unique instructor names from the latest crawl data."""
    all_data = _read_latest_jsonl()
    instructors = set(item.get("instructor") for item in all_data if item.get("instructor"))
    return {"instructors": sorted(list(instructors))}

@app.get("/classes")
def get_classes(
    date: Optional[str] = None,
    # Allow multiple selections for these filters
    class_name: Optional[List[str]] = Query(None), 
    club: Optional[List[str]] = Query(None),
    instructor: Optional[List[str]] = Query(None),
    day_name_hebrew: Optional[List[str]] = Query(None) 
):
    """Get filtered class data, now including region and supporting multi-select."""
    logging.info(f"--- Received /classes request with filters ---")
    logging.info(f"  Date: {date}")
    logging.info(f"  Class Names: {class_name}") # Log list
    logging.info(f"  Clubs: {club}")             # Log list
    logging.info(f"  Instructors: {instructor}") # Log list
    logging.info(f"  Day Names (Hebrew): {day_name_hebrew}")
    
    all_classes = _read_latest_jsonl() 
    if not all_classes:
        logging.info("  No data found in JSONL file.")
        return {
            "count": 0,
            "classes": [],
            "regions_found": [],
            "opening_hours": {}
        }
    logging.info(f"  Read {len(all_classes)} classes from file.")
    
    # Get opening hours from the latest crawl file
    opening_hours = {}
    latest_file = get_latest_successful_crawl_file()
    if latest_file and "holmes_clubs_" in os.path.basename(latest_file):
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        club_data = json.loads(line)
                        if 'club_name' in club_data and 'opening_hours' in club_data:
                            opening_hours[club_data['club_name']] = club_data['opening_hours']
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logging.error(f"Error reading opening hours from club file: {e}")
    
    # Apply filters
    filtered_classes = all_classes
    
    # --- Apply List Filters --- 
    if date:
        filtered_classes = [c for c in filtered_classes if c.get("day") == date]
        
    if day_name_hebrew:
        days_to_filter = set(day_name_hebrew) 
        logging.info(f"  Filtering by Hebrew days: {days_to_filter}")
        original_count = len(filtered_classes)
        filtered_classes = [c for c in filtered_classes if c.get("day_name_hebrew") in days_to_filter]
        logging.info(f"  Filtered by day: {original_count} -> {len(filtered_classes)} classes")
    else:
        logging.info("  No Hebrew day filter applied.")

    if class_name:
        class_names_to_filter = set(cn.lower() for cn in class_name) # Lowercase for comparison
        logging.info(f"  Filtering by class names: {class_names_to_filter}")
        original_count = len(filtered_classes)
        # Check if the class name contains any of the filter terms (case-insensitive)
        filtered_classes = [
            c for c in filtered_classes 
            if any(filter_name in c.get("name", "").lower() for filter_name in class_names_to_filter)
        ]
        logging.info(f"  Filtered by class_name: {original_count} -> {len(filtered_classes)} classes")
    
    if club:
        clubs_to_filter = set(c.lower() for c in club) # Lowercase for comparison
        logging.info(f"  Filtering by clubs: {clubs_to_filter}")
        original_count = len(filtered_classes)
        # Check if the club name contains any of the filter terms (case-insensitive)
        # Or use exact match: if c.get("club", "").lower() in clubs_to_filter
        filtered_classes = [
            c for c in filtered_classes
            if any(filter_club in c.get("club", "").lower() for filter_club in clubs_to_filter)
        ]
        logging.info(f"  Filtered by club: {original_count} -> {len(filtered_classes)} classes")
    
    if instructor:
        instructors_to_filter = set(i.lower() for i in instructor) # Lowercase
        logging.info(f"  Filtering by instructors: {instructors_to_filter}")
        original_count = len(filtered_classes)
        # Check if the instructor name contains any of the filter terms (case-insensitive)
        # Or use exact match: if c.get("instructor", "").lower() in instructors_to_filter
        filtered_classes = [
            c for c in filtered_classes 
            if c.get("instructor") and any(filter_inst in c.get("instructor", "").lower() for filter_inst in instructors_to_filter)
        ]
        logging.info(f"  Filtered by instructor: {original_count} -> {len(filtered_classes)} classes")
    
    # Add region to each filtered class and get unique regions found
    regions_found = set()
    processed_classes = []
    for c in filtered_classes:
        region = get_club_region(c.get("club"))
        c['region'] = region
        regions_found.add(region)
        processed_classes.append(c)

    # Define the NEW sort order for regions
    region_sort_order = {
        "מרכז": 1,
        "שרון": 2,
        "שפלה": 3,
        "ירושלים והסביבה": 4,
        "דרום": 5,
        "צפון": 6,
        "לא ידוע": 7 # Keep last
    }
    sorted_regions = sorted(list(regions_found), key=lambda r: region_sort_order.get(r, 99))

    logging.info(f"--- Returning {len(processed_classes)} classes, regions sorted: {sorted_regions} ---") # Log sorted regions
    return {
        "count": len(processed_classes),
        "classes": processed_classes, 
        "regions_found": sorted_regions,
        "opening_hours": opening_hours
    }

@app.post("/start-crawl")
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """Start the crawler in the background, optionally headless."""
    crawler_stop_event.clear()
    logging.info("Cleared crawler stop event. Starting FULL crawl.")
    
    async def run_crawler():
        crawler = HolmesPlaceCrawler(
            websocket_manager=manager, 
            headless=request.headless,
            stop_event=crawler_stop_event,
            output_dir=get_data_dir()
            # clubs_to_process is None for a full crawl
        )
        await crawler.start()
    
    background_tasks.add_task(lambda: asyncio.run(run_crawler()))
    return {"status": f"Crawler started in background ({'headless' if request.headless else 'headed'})."}

@app.post("/retry-failed-crawl")
async def retry_failed_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """Reads the last status file and restarts the crawler only for failed clubs."""
    status_filename = os.path.join(get_data_dir(), "last_crawl_status.json")
    failed_clubs_to_retry = []
    
    try:
        if os.path.exists(status_filename):
            with open(status_filename, 'r', encoding='utf-8') as f:
                last_status = json.load(f)
                for club_name, result in last_status.items():
                    if result.get("status") == "failed":
                        failed_clubs_to_retry.append({"name": club_name, "url": result.get("url")})
        
        if not failed_clubs_to_retry:
            logging.info("Retry request received, but no failed clubs found in last status.")
            return {"status": "No failed clubs found in the last crawl status to retry."}
            
        logging.info(f"Found {len(failed_clubs_to_retry)} failed clubs to retry: {[c['name'] for c in failed_clubs_to_retry]}")
        
        # Clear the stop event before starting the retry crawl
        crawler_stop_event.clear()
        logging.info("Cleared crawler stop event for retry crawl.")
        
        async def run_retry_crawler():
            crawler = HolmesPlaceCrawler(
                websocket_manager=manager, 
                headless=request.headless, # Use headless preference from request
                stop_event=crawler_stop_event,
                output_dir=get_data_dir(),
                clubs_to_process=failed_clubs_to_retry # Pass the list of failed clubs
            )
            await crawler.start()
        
        background_tasks.add_task(lambda: asyncio.run(run_retry_crawler()))
        return {"status": f"Retry crawl started in background for {len(failed_clubs_to_retry)} failed clubs."}

    except FileNotFoundError:
        logging.error("Retry request failed: last_crawl_status.json not found.")
        return {"status": "Error: Cannot retry, last crawl status file not found."}
    except json.JSONDecodeError:
        logging.error("Retry request failed: Error reading last_crawl_status.json.")
        return {"status": "Error: Cannot retry, error reading last crawl status file."}
    except Exception as e:
        logging.error(f"Retry request failed: Unexpected error: {e}", exc_info=True)
        return {"status": f"Error: Unexpected error initiating retry crawl: {e}"}

@app.post("/stop-crawl")
async def stop_crawl():
    """Signals the running crawler to stop."""
    if not crawler_stop_event.is_set():
        crawler_stop_event.set()
        logging.info("Crawler stop event set.")
        return {"status": "Stop signal sent to crawler."}
    else:
        logging.info("Crawler stop event was already set.")
        return {"status": "Crawler stop signal was already sent."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_host = websocket.client.host
    logging.info(f"New WebSocket connection attempt from {client_host}")
    
    await manager.connect(websocket)
    logging.info(f"WebSocket connection successfully accepted for {client_host}")
    
    try:
        # Send initial connection message - confirms acceptance
        await websocket.send_json({
            "type": "connection_established", 
            "message": "Connected to crawler status updates",
            "timestamp": datetime.now().isoformat()
        })
        logging.info(f"Sent connection_established message to {client_host}")
        
        # Keep the connection open and listen for messages
        while True:
            try:
                # Wait for messages from the client
                data = await websocket.receive_text() # Use receive_text or receive_json based on expected format
                logging.info(f"Received message from {client_host}: {data}")
                
                try:
                    message_data = json.loads(data)
                    if isinstance(message_data, dict) and message_data.get("action") == "get_data_info":
                        logging.info(f"Processing get_data_info request from {client_host}")
                        info = get_data_info() # Call the existing function
                        await websocket.send_json({
                            "type": "data_info",
                            "data": info,
                            "timestamp": datetime.now().isoformat()
                        })
                        logging.info(f"Sent data_info response to {client_host}")
                    elif isinstance(message_data, dict) and message_data.get("action") == "get_crawl_status":
                        logging.info(f"Processing get_crawl_status request from {client_host}")
                        info = await get_crawl_status(websocket) # Call the new function
                        await websocket.send_json({
                            "type": "crawl_status",
                            "data": info,
                            "timestamp": datetime.now().isoformat()
                        })
                        logging.info(f"Sent crawl_status response to {client_host}")
                    elif isinstance(message_data, dict) and message_data.get("action") == "start_crawl":
                        logging.info(f"Processing start_crawl request from {client_host}")
                        # Extract headless parameter if provided, default to False
                        headless = message_data.get("headless", False)
                        
                        # Start the crawler using the existing API endpoint
                        crawler_stop_event.clear()
                        logging.info(f"WebSocket: Cleared crawler stop event. Starting FULL crawl with headless={headless}")
                        
                        async def run_ws_crawler():
                            try:
                                crawler = HolmesPlaceCrawler(
                                    websocket_manager=manager, 
                                    headless=headless,
                                    stop_event=crawler_stop_event,
                                    output_dir=get_data_dir()
                                )
                                await crawler.start()
                            except Exception as crawl_err:
                                logging.error(f"Error in WebSocket crawler: {crawl_err}", exc_info=True)
                                await websocket.send_json({
                                    "type": "crawl_error",
                                    "message": f"Crawler error: {str(crawl_err)}",
                                    "timestamp": datetime.now().isoformat()
                                })
                        
                        # Start the crawler in the background
                        asyncio.create_task(run_ws_crawler())
                        
                        # Send confirmation response to client
                        await websocket.send_json({
                            "type": "crawl_started",
                            "message": f"Crawler started in {'headless' if headless else 'headed'} mode",
                            "timestamp": datetime.now().isoformat()
                        })
                        logging.info(f"Sent crawl_started response to {client_host}")
                    elif isinstance(message_data, dict) and message_data.get("action") == "stop_crawl":
                        logging.info(f"Processing stop_crawl request from {client_host}")
                        if not crawler_stop_event.is_set():
                            crawler_stop_event.set()
                            logging.info("WebSocket: Crawler stop event set.")
                            await websocket.send_json({
                                "type": "crawl_stopped",
                                "message": "Stop signal sent to crawler",
                                "timestamp": datetime.now().isoformat()
                            })
                        else:
                            logging.info("WebSocket: Crawler stop event was already set.")
                            await websocket.send_json({
                                "type": "crawl_stopped",
                                "message": "Crawler was already stopping",
                                "timestamp": datetime.now().isoformat()
                            })
                    else:
                        # Handle other message types or ignore
                        logging.warning(f"Received unknown message format or action from {client_host}: {data}")
                        # Send an error response for unknown actions
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown action: {message_data.get('action', 'none')}",
                            "timestamp": datetime.now().isoformat()
                        })
                except json.JSONDecodeError:
                    logging.error(f"Failed to decode JSON message from {client_host}: {data}")
                    # Optional: Send an error message back
                    # await websocket.send_text("Error: Invalid JSON format")
                except Exception as msg_proc_err:
                    logging.error(f"Error processing message from {client_host}: {msg_proc_err}")
                    # Optional: Send an error message back
                    # await websocket.send_text(f"Error processing message: {msg_proc_err}")
                
            except WebSocketDisconnect:
                logging.info(f"WebSocket client {client_host} disconnected gracefully.")
                break # Exit the loop on disconnect
            except Exception as loop_err:
                # Log unexpected errors within the loop but try to keep connection alive if possible
                logging.error(f"Unexpected error in WebSocket loop for {client_host}: {loop_err}\n{traceback.format_exc()}")
                # Depending on the error, you might want to break or continue
                # For robustness, we'll break here to avoid potential infinite error loops
                break
                
    except Exception as e:
        # Catch errors during the initial connection phase or outside the main loop
        logging.error(f"Unhandled error in WebSocket endpoint for {client_host}: {e}\n{traceback.format_exc()}")
    finally:
        # Ensure disconnection logic runs regardless of how the connection ends
        manager.disconnect(websocket)
        logging.info(f"WebSocket connection cleaned up for {client_host}")

@app.get("/crawl-status")
def get_crawl_status_http():
    """HTTP endpoint to get current crawl status (for frontend)"""
    return _get_crawl_status_impl()

@app.websocket("/ws/crawl-status")
async def get_crawl_status_ws(websocket: WebSocket):
    """WebSocket endpoint to get the current crawl status."""
    # Accept the connection
    await websocket.accept()
    try:
        # Send initial status snapshot
        crawl_data = _get_crawl_status_impl()
        await websocket.send_json({
            "type": "crawl_status",
            "data": crawl_data,
            "timestamp": datetime.now().isoformat()
        })
        # Keep connection open until client disconnects
        while True:
            try:
                # Wait for any message or disconnection
                await websocket.receive_text()
            except WebSocketDisconnect:
                logging.info("get_crawl_status_ws: client disconnected")
                break
    except Exception as e:
        logging.error(f"Error in get_crawl_status_ws: {e}")
    finally:
        # Close the connection
        await websocket.close()

@app.get("/data-info")
def get_data_info():
    """Get information about data freshness and available clubs (deprecated, use /crawl-status instead)."""
    logging.warning("The /data-info endpoint is deprecated. Please use /crawl-status instead.")
    return _get_crawl_status_impl()

def _get_crawl_status_impl():
    """Implementation of the crawl status endpoint functionality."""
    data_dir = get_data_dir()
    jsonl_files = glob.glob(os.path.join(data_dir, "*.jsonl"))
    status_filename = os.path.join(data_dir, "last_crawl_status.json")
    
    # Initialize default response
    response = {
        "has_data": False,
        "latest_file": None,
        "latest_file_full_path": None,
        "latest_crawl_date": None,
        "days_since_crawl": None,
        "is_stale": True,  # Default to stale if no data
        "clubs": [], # Will contain {name, status, url, region}
        "is_complete_crawl": False  # Default to false
    }
    
    # Get the latest successful crawl file
    latest_file = get_latest_successful_crawl_file()
    
    # Check if we have any data files for freshness info
    if latest_file:
        try:
            file_timestamp = os.path.getctime(latest_file)
            file_date = datetime.fromtimestamp(file_timestamp)
            days_since_crawl = (datetime.now() - file_date).days
            
            # Default to treating the crawl as complete unless proven otherwise
            is_complete_crawl = True
            
            # Check the status file to determine if there were any issues with the crawl
            if os.path.exists(status_filename):
                try:
                    with open(status_filename, 'r', encoding='utf-8') as f:
                        status_data = json.load(f)
                        
                        if isinstance(status_data, dict) and "crawl_results" in status_data:
                            # New format - check if the crawl was explicitly marked as problematic
                            was_stopped_early = status_data.get("was_stopped_early", False)
                            critical_error_occurred = status_data.get("critical_error_occurred", False)
                            crawl_results = status_data.get("crawl_results", {})
                            
                            # Mark as incomplete if it was explicitly stopped early or had critical errors
                            # AND it doesn't have enough successful clubs
                            if (was_stopped_early or critical_error_occurred):
                                is_complete_crawl = False
                except Exception as status_err:
                    logging.error(f"Error checking crawl status: {status_err}")
            
            response.update({
                "has_data": True,
                "latest_file": os.path.basename(latest_file),
                "latest_file_full_path": latest_file,
                "latest_crawl_date": file_date.isoformat(),
                "days_since_crawl": days_since_crawl,
                "is_stale": days_since_crawl > 7,
                "is_complete_crawl": is_complete_crawl
            })
            
            # Add crawl metadata from the status file if available
            if os.path.exists(status_filename):
                try:
                    with open(status_filename, 'r', encoding='utf-8') as f:
                        status_data = json.load(f)
                        
                        if isinstance(status_data, dict) and "crawl_results" in status_data:
                            # New format - extract metadata
                            crawl_metadata = {
                                "was_stopped_early": status_data.get("was_stopped_early", False),
                                "critical_error_occurred": status_data.get("critical_error_occurred", False),
                                "timestamp": status_data.get("timestamp")
                            }
                            response["crawl_metadata"] = crawl_metadata
                            
                            # Add summary statistics
                            if "crawl_results" in status_data:
                                clubs_data = status_data["crawl_results"]
                                success_count = sum(1 for _, data in clubs_data.items() if data.get("status") == "success")
                                failed_count = sum(1 for _, data in clubs_data.items() if data.get("status") == "failed")
                                response["success_count"] = success_count
                                response["failed_count"] = failed_count
                                response["total_processed"] = len(clubs_data)
                                
                except Exception as metadata_err:
                    logging.error(f"Error reading crawl metadata: {metadata_err}")
                    
        except Exception as e:
            logging.error(f"Error getting file info: {e}")
    
    # --- Get clubs with region --- 
    clubs_list_with_region = []
    processed_club_names = set()
    club_to_region = {}  # Initialize here, outside the if block

    # STEP 1: First, get all clubs from the latest data file
    if response["has_data"]:
        all_data = _read_latest_jsonl()
        # club_to_region = {}  <-- Remove initialization from here
        
        # Extract all unique clubs from the data
        for item in all_data:
            if club_name := item.get("club"):
                if club_name not in club_to_region:
                    region = get_club_region(club_name)
                    club_to_region[club_name] = region
        
        logging.info(f"Found {len(club_to_region)} unique clubs in the data file")
    
    # STEP 2: Get status info from the status file
    status_info = {}
    if os.path.exists(status_filename):
        try:
            with open(status_filename, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
                
                last_status = {}
                if isinstance(status_data, dict) and "crawl_results" in status_data:
                    # New format
                    last_status = status_data.get("crawl_results", {})
                else:
                    # Old format - direct club statuses
                    last_status = status_data
                
                # Store all status info
                for club_name, result in last_status.items():
                    status_info[club_name] = {
                        "url": result.get("url", ""),
                        "status": result.get("status", "unknown")
                    }
        except Exception as e:
            logging.error(f"Error reading clubs from status file: {e}")
    
    # STEP 3: Combine data and status info
    # -- ADD LOGGING HERE --
    logging.info(f"[_get_crawl_status_impl] Before combining: Type of club_to_region: {type(club_to_region)}, Value: {club_to_region}")
    # ---------------------

    # First, add all clubs from the data file (regardless of status)
    for club_name, region in club_to_region.items():
        status = "unknown"
        url = ""
        
        # Add status info if available
        if club_name in status_info:
            status = status_info[club_name]["status"]
            url = status_info[club_name]["url"]
            
        clubs_list_with_region.append({
            "name": club_name,
            "url": url,
            "status": status,
            "region": region
        })
        processed_club_names.add(club_name)
    
    # Then, add any additional clubs from the status file that weren't in the data
    if status_info:
        for club_name, info in status_info.items():
            if club_name not in processed_club_names:
                region = get_club_region(club_name)
                clubs_list_with_region.append({
                    "name": club_name,
                    "url": info["url"],
                    "status": info["status"],
                    "region": region
                })
                processed_club_names.add(club_name)

    # Sort the final list by name and add to response
    clubs_list_with_region.sort(key=lambda c: c["name"])
    response["clubs"] = clubs_list_with_region
    # Fallback: mark has_data True if clubs list is non-empty
    if response.get("clubs"):
        response["has_data"] = True
    # ---------------------------
    
    logging.info(f"Returning crawl status with {len(response['clubs'])} clubs.")
    return response

@app.get("/bypass-completeness-check")
def bypass_completeness_check():
    """Temporarily use the latest data file regardless of completeness status.
    For debugging purposes only."""
    data_dir = get_data_dir()
    
    # Look for both old and new format files
    class_jsonl_files = glob.glob(os.path.join(data_dir, "holmes_place_schedule_*.jsonl"))
    club_jsonl_files = glob.glob(os.path.join(data_dir, "holmes_clubs_*.jsonl"))
    
    all_jsonl_files = class_jsonl_files + club_jsonl_files
    
    if not all_jsonl_files:
        return {"success": False, "message": "No data files found"}
    
    try:
        # Simply use the most recent file
        latest_file = max(all_jsonl_files, key=os.path.getctime)
        is_club_format = "holmes_clubs_" in os.path.basename(latest_file)
        logging.info(f"BYPASS: Using most recent file regardless of completeness: {os.path.basename(latest_file)} (club format: {is_club_format})")
        
        # Read the data
        data = []
        with open(latest_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    line_data = json.loads(line)
                    
                    # If this is a club format file, extract the classes
                    if is_club_format:
                        # Each line is a club with 'classes' field containing class data
                        if 'classes' in line_data and isinstance(line_data['classes'], list):
                            # Extract all classes from this club
                            for class_data in line_data['classes']:
                                # Add club name if missing in class data
                                if 'club' not in class_data and 'club_name' in line_data:
                                    class_data['club'] = line_data['club_name']
                                # Add area/region if missing
                                if 'region' not in class_data and 'area' in line_data:
                                    class_data['region'] = line_data['area']
                                data.append(class_data)
                    else:
                        # Old format - each line is a single class
                        data.append(line_data)
                except json.JSONDecodeError as e:
                    logging.warning(f"Skipping malformed line in {latest_file}: {e}")
        
        # Return success info
        return {
            "success": True, 
            "message": "Using latest file regardless of completeness", 
            "filename": os.path.basename(latest_file),
            "count": len(data)
        }
    except Exception as e:
        logging.error(f"Error in bypass endpoint: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}

@app.get("/screenshots/{filename}")
def get_screenshot(filename: str):
    """Serve screenshot files from the screenshots directory."""
    screenshots_dir = os.path.join(os.path.dirname(get_data_dir()), "screenshots")
    return FileResponse(os.path.join(screenshots_dir, filename))

if __name__ == "__main__":
    import uvicorn
    try:
        logging.info("Starting FastAPI server on port 8080...")
        uvicorn.run(app, host="0.0.0.0", port=8080)
    except OSError as e:
        logging.error(f"Failed to start server: {str(e)}")
        if "address already in use" in str(e).lower():
            logging.error("Port 8080 is already in use. Please free the port and try again.")
    except Exception as e:
        logging.error(f"Unexpected error starting server: {str(e)}") 