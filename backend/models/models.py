from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ClassData(BaseModel):
    class_name: str
    instructor: Optional[str] = None
    day_name_hebrew: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    club_name: Optional[str] = None
    room: Optional[str] = None
    capacity: Optional[int] = None
    registered: Optional[int] = None

class CrawlRequest(BaseModel):
    headless: bool = False  # Default to non-headless mode

class WebSocketMessage(BaseModel):
    type: str
    message: str
    timestamp: str
    data: Optional[Dict[str, Any]] = None

class ClubInfo(BaseModel):
    name: str
    short_name: Optional[str] = None
    status: str
    url: str
    region: str
    opening_hours: Dict[str, str]

class CrawlStatus(BaseModel):
    has_data: bool
    latest_file: Optional[str]
    latest_file_full_path: Optional[str]
    latest_crawl_date: Optional[str]
    days_since_crawl: Optional[int]
    is_stale: bool
    clubs: List[ClubInfo]
    is_complete_crawl: bool
    crawl_metadata: Optional[Dict[str, Any]] = None
    success_count: Optional[int] = None
    failed_count: Optional[int] = None
    total_processed: Optional[int] = None 