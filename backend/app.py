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
    headless: bool = True # Default to headless

# Define a simple region mapping (can be expanded)
REGION_MAP = {
    "צפון": ["קריון", "גרנד קניון", "חיפה", "קיסריה"], 
    "שרון": ["רעננה", "כפר סבא", "נתניה", "הוד השרון"],
    "מרכז": ["תל אביב", "פתח תקווה", "רמת גן", "גבעתיים", "ראש העין", "עזריאלי", "דיזנגוף", "גבעת שמואל", "ראשון לציון"], 
    "שפלה": ["נס ציונה", "רחובות"],
    "ירושלים והסביבה": ["ירושלים", "מבשרת ציון", "מודיעין"],
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
    jsonl_files = glob.glob(os.path.join(data_dir, "*.jsonl"))
    if not jsonl_files:
        return {"filename": None, "count": 0, "data": []}
    
    # Find the most recent file
    latest_file = max(jsonl_files, key=os.path.getctime)
    
    # Read and return the data
    data = []
    with open(latest_file, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    
    return {"filename": os.path.basename(latest_file), "count": len(data), "data": data}

def _read_latest_jsonl():
    """Helper function to read all data from the latest JSONL file."""
    data_dir = get_data_dir()
    jsonl_files = glob.glob(os.path.join(data_dir, "*.jsonl"))
    if not jsonl_files:
        return []
    latest_file = max(jsonl_files, key=os.path.getctime)
    data = []
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data.append(json.loads(line))
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
    """Get list of unique clubs from the latest crawl data."""
    all_data = _read_latest_jsonl()
    clubs = set(item.get("club") for item in all_data if item.get("club"))
    return {"clubs": sorted(list(clubs))}

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
            "regions_found": []
        }
    logging.info(f"  Read {len(all_classes)} classes from file.")
    
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
        "regions_found": sorted_regions 
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
            stop_event=crawler_stop_event 
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
    
    try:
        await manager.connect(websocket)
        logging.info(f"WebSocket connection successfully established with {client_host}")
        
        # Send initial connection message
        await websocket.send_json({
            "type": "connection_established", 
            "message": "Connected to crawler status updates",
            "timestamp": datetime.now().isoformat()
        })
        logging.info(f"Sent connection_established message to {client_host}")
        
        # Keep the connection alive until the client disconnects
        while True:
            try:
                # Wait for messages from the client
                data = await websocket.receive_text()
                logging.info(f"Received message from {client_host}: {data}")
                
                # Echo the message back
                await websocket.send_text(f"Message received: {data}")
                
            except WebSocketDisconnect:
                logging.info(f"WebSocket client {client_host} disconnected")
                break
            except Exception as e:
                logging.error(f"Error in WebSocket connection with {client_host}: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logging.info(f"WebSocket client {client_host} disconnected during connection setup")
    except Exception as e:
        logging.error(f"Error establishing WebSocket connection with {client_host}: {str(e)}")
    finally:
        manager.disconnect(websocket)
        logging.info(f"WebSocket connection cleaned up for {client_host}")

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