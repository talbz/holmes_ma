from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
from models.models import CrawlRequest, CrawlStatus, WebSocketMessage
from utils.websocket_manager import websocket_manager
from utils.logger import logger
from crawler import HolmesPlaceCrawler
import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path
from utils.config import Config

router = APIRouter()

def get_crawl_status() -> CrawlStatus:
    """Get the current crawl status"""
    output_dir = Config.OUTPUT_DIR
    jsonl_files = list(output_dir.glob("*.jsonl"))
    
    if not jsonl_files:
        return CrawlStatus(
            has_data=False,
            latest_file=None,
            latest_file_full_path=None,
            latest_crawl_date=None,
            days_since_crawl=None,
            is_stale=True,
            clubs=[],
            is_complete_crawl=False
        )
    
    latest_file = max(jsonl_files, key=lambda x: x.stat().st_mtime)
    latest_crawl_date = datetime.fromtimestamp(latest_file.stat().st_mtime)
    days_since_crawl = (datetime.now() - latest_crawl_date).days
    
    # Read the latest file to get club information
    clubs = []
    with open(latest_file, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            if 'club_name' in data:
                clubs.append({
                    'name': data['club_name'],
                    'status': 'active',
                    'url': data.get('url', ''),
                    'region': data.get('region', ''),
                    'opening_hours': data.get('opening_hours', {})
                })
    
    return CrawlStatus(
        has_data=True,
        latest_file=latest_file.name,
        latest_file_full_path=str(latest_file),
        latest_crawl_date=latest_crawl_date.isoformat(),
        days_since_crawl=days_since_crawl,
        is_stale=days_since_crawl > Config.DATA_STALE_THRESHOLD,
        clubs=clubs,
        is_complete_crawl=len(clubs) > 0
    )

@router.get("/status", response_model=CrawlStatus)
async def get_status():
    """Get the current crawl status"""
    return get_crawl_status()

@router.post("/start")
async def start_crawl(request: CrawlRequest):
    """Start a new crawl"""
    try:
        crawler = HolmesPlaceCrawler(headless=request.headless)
        asyncio.create_task(crawler.start())
        return {"message": "Crawl started successfully"}
    except Exception as e:
        logger.error(f"Error starting crawl: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                # Handle incoming messages if needed
            except WebSocketDisconnect:
                websocket_manager.disconnect(websocket)
                break
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        websocket_manager.disconnect(websocket) 