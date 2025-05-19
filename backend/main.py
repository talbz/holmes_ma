from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import json
from typing import List, Dict, Any
import os
import sys
import argparse
import logging
from datetime import datetime
import signal

# Add project root to sys.path to allow for absolute imports from backend
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.utils.websocket_manager import websocket_manager
from backend.utils.data_utils import (
    get_latest_jsonl_file,
    read_jsonl_file,
    calculate_days_since_crawl
)
from backend.crawler import HolmesPlaceCrawler

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend/dist"), name="static")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception:
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
        # Update status to running
        await websocket_manager.update_status(
            is_running=True,
            progress=0,
            current_club=None,
            error=None
        )
        
        # Start crawler in background
        asyncio.create_task(run_crawler())
        
        return {"message": "Crawl started successfully"}
    except Exception as e:
        await websocket_manager.update_status(
            is_running=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data")
async def get_data():
    """Get the latest crawl data."""
    try:
        latest_file = get_latest_jsonl_file("data")
        if not latest_file:
            raise HTTPException(status_code=404, detail="No data available")
        
        data = read_jsonl_file(latest_file)
        days_since_crawl = calculate_days_since_crawl(latest_file)
        
        return {
            "data": data,
            "days_since_crawl": days_since_crawl
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_crawler():
    """Run the crawler and update status."""
    try:
        # Get the latest clubs data to determine which clubs to crawl
        latest_file = get_latest_jsonl_file()
        if not latest_file:
            raise Exception("No data available to determine clubs")
        
        data = read_jsonl_file(latest_file)
        clubs_to_process = []
        
        # Extract clubs from the data
        for entry in data:
            if "clubs" in entry:
                clubs_data = entry["clubs"]
                for club_name, club_info in clubs_data.items():
                    clubs_to_process.append({
                        "name": club_name,
                        "url": club_info.get("url", ""),
                        "status": club_info.get("status", "unknown")
                    })
            elif "club_name" in entry:
                clubs_to_process.append({
                    "name": entry["club_name"],
                    "url": entry.get("url", ""),
                    "status": entry.get("status", "unknown")
                })
        
        if not clubs_to_process:
            raise Exception("No clubs found in data")
            
        # Import the crawler here to ensure it's loaded only when needed
        from backend.crawler import HolmesPlaceCrawler
        
        # Create crawler instance
        crawler = HolmesPlaceCrawler(
            websocket_manager=websocket_manager,
            headless=False,  # Set to False for debugging visibility
            clubs_to_process=clubs_to_process
        )
        
        # Start the crawler
        await crawler.start()
        
        await websocket_manager.update_status(
            is_running=False,
            progress=100,
            current_club=None,
            error=None
        )
    except Exception as e:
        await websocket_manager.update_status(
            is_running=False,
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 