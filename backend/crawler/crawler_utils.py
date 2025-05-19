import logging
import json
import re
import asyncio
from datetime import datetime
import os

# Configure logging
logger = logging.getLogger(__name__)

# Control characters for BiDi: RTL override / Pop directional formatting
BIDI_RTL = "\u202B"
BIDI_POP = "\u202C"

class CrawlerUtils:
    """Utility functions for the crawler."""
    
    def __init__(self, crawler):
        """Initialize with reference to parent crawler."""
        self.crawler = crawler
        self._status_buffer = []  # Buffer for status messages if websocket is disconnected

    async def send_status(self, type_str, message, data=None):
        """Helper to send status updates via WebSocket and log with proper Hebrew display."""
        # Reverse Hebrew segments for correct readability
        def adjust_message(msg):
            # If contains Hebrew characters, reverse order for readability in logs
            if re.search('[\u0590-\u05FF]', msg):
                return msg[::-1]
            return msg
            
        adj_message = adjust_message(message)
        
        if self.crawler.websocket_manager:
            status_data = {
                "type": type_str,
                "message": adj_message,
                "timestamp": datetime.now().isoformat(),
            }
            if data:
                status_data["data"] = data
                
            try:
                # Use broadcast method if ConnectionManager has it
                if hasattr(self.crawler.websocket_manager, 'broadcast'):
                    await self.crawler.websocket_manager.broadcast(json.dumps(status_data))
                else:
                    logger.warning("Websocket manager does not have a broadcast method.")
            except Exception as ws_err:
                logger.error(f"Failed to send WebSocket status: {ws_err}")
                # Handle disconnection case specifically
                if "disconnected" in str(ws_err).lower() or "connection" in str(ws_err).lower():
                    logger.warning("WebSocket appears to be disconnected. Will continue crawling but some status updates may be missed.")
                    # Buffer up to 100 messages to avoid memory issues
                    if len(self._status_buffer) < 100:
                        self._status_buffer.append(status_data)
        
        # Log the message with proper direction for Hebrew text
        logger.info(f"Status Update ({type_str}): {BIDI_RTL}{message}{BIDI_POP} {data or ''}")

    async def take_screenshot(self, stage_name):
        """Takes a screenshot for debugging and returns the path."""
        if self.crawler.page:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"error_{stage_name}_{timestamp}.png"
                path = os.path.join(self.crawler.screenshot_dir, filename)
                await self.crawler.page.screenshot(path=path)
                logger.info(f"Screenshot saved to {path}")
                await self.send_status('error_screenshot', f"שגיאה בשלב {stage_name}. צילום מסך נשמר.")
                return filename  # Return just the filename, not the full path
            except Exception as ss_error:
                logger.error(f"Failed to take screenshot: {ss_error}")
                return None
        else:
            logger.warning("Cannot take screenshot, page object is not available.")
            return None

    async def check_stop_event(self, context_msg=""):
        """Checks if the stop event is set and raises an exception if it is."""
        if self.crawler.stop_event and self.crawler.stop_event.is_set():
            logger.warning(f"Stop event detected during: {context_msg}. Stopping crawl.")
            raise asyncio.CancelledError(f"Crawler stop requested during {context_msg}")

    def format_hebrew_text(self, text):
        """Formats Hebrew text with proper bidirectional control characters for display."""
        if re.search('[\u0590-\u05FF]', text):
            return f"{BIDI_RTL}{text}{BIDI_POP}"
        return text

    def extract_day_from_hebrew(self, day_text):
        """Extract day name from Hebrew text."""
        hebrew_days = {
            'ראשון': 'Sunday',
            'שני': 'Monday',
            'שלישי': 'Tuesday',
            'רביעי': 'Wednesday',
            'חמישי': 'Thursday',
            'שישי': 'Friday',
            'שבת': 'Saturday'
        }
        
        for heb_day, eng_day in hebrew_days.items():
            if heb_day in day_text:
                return {
                    'hebrew': heb_day,
                    'english': eng_day
                }
        
        return {
            'hebrew': 'לא ידוע',
            'english': 'unknown'
        }

    def clean_text(self, text):
        """Clean and standardize text."""
        if not text:
            return ""
            
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', text).strip()
        
        # Remove non-printable characters
        cleaned = ''.join(c for c in cleaned if c.isprintable() or c.isspace())
        
        return cleaned 