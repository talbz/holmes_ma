from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CrawlRequest(BaseModel):
    headless: bool = False

class ClubInfo(BaseModel):
    name: str
    short_name: Optional[str] = None
    status: str
    url: str
    region: str
    opening_hours: Dict[str, Any] = {}

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