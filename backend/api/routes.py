from fastapi import APIRouter, WebSocket, HTTPException
from typing import List, Dict, Any
import asyncio
from datetime import datetime
import os
from pathlib import Path

from .websocket import WebSocketManager
from ..utils.data_utils import (
    get_latest_jsonl_file,
    read_jsonl_file,
    calculate_days_since_crawl
)

router = APIRouter()
websocket_manager = WebSocketManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.handle_websocket(websocket)

@router.get("/status")
async def get_crawl_status():
    """Get current crawl status."""
    return websocket_manager.crawl_status

@router.post("/start")
async def start_crawl():
    """Start the crawler process."""
    if websocket_manager.crawl_status["status"] == "running":
        raise HTTPException(status_code=400, detail="Crawler is already running")
    
    await websocket_manager.update_status("running", 0, "Starting crawler...")
    
    # Start crawler in background
    asyncio.create_task(run_crawler())
    
    return {"message": "Crawler started"}

@router.post("/stop")
async def stop_crawl():
    """Stop the crawler process."""
    if websocket_manager.crawl_status["status"] != "running":
        raise HTTPException(status_code=400, detail="Crawler is not running")
    
    await websocket_manager.update_status("stopping", 0, "Stopping crawler...")
    # TODO: Implement crawler stop logic
    return {"message": "Crawler stopping"}

@router.get("/data")
async def get_data():
    """Get the latest crawl data."""
    output_dir = os.getenv("OUTPUT_DIR", "data")
    latest_file = get_latest_jsonl_file(output_dir)
    
    if not latest_file:
        raise HTTPException(status_code=404, detail="No data available")
    
    try:
        data = read_jsonl_file(latest_file)
        days_since_crawl = calculate_days_since_crawl(latest_file)
        
        return {
            "data": data,
            "days_since_crawl": days_since_crawl,
            "last_updated": datetime.fromtimestamp(os.path.getmtime(latest_file)).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_crawler():
    """Run the crawler process and update status via WebSocket."""
    try:
        # TODO: Implement crawler logic
        # For now, just simulate progress
        for i in range(1, 101):
            await asyncio.sleep(0.1)  # Simulate work
            await websocket_manager.update_status(
                "running",
                i,
                f"Processing... {i}%"
            )
        
        await websocket_manager.update_status(
            "completed",
            100,
            "Crawl completed successfully"
        )
    except Exception as e:
        await websocket_manager.update_status(
            "error",
            0,
            f"Crawl failed: {str(e)}"
        ) 