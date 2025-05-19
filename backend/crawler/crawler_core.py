import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pytz
import sys
import os

# Add parent directory to path to enable relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from backend.utils.config import Config

# Import from other crawler modules
from .crawler_browser import BrowserManager
from .crawler_clubs import ClubProcessor
from .crawler_classes import ClassExtractor
from .crawler_utils import CrawlerUtils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HolmesPlaceCrawler:
    """Handles crawling Holmes Place website for class schedules."""
    
    def __init__(self, base_url="https://www.holmesplace.co.il/", 
                 output_dir=None, headless=False, clubs_filter=None,
                 websocket_manager=None, stop_event=None, clubs_to_process=None):
        """Initializes the HolmesPlaceCrawler with configuration settings."""
        self.base_url = base_url
        self.output_dir = output_dir or Config.OUTPUT_DIR
        self.headless = headless
        self.clubs_filter = clubs_filter
        self.browser = None
        self.page = None
        self.found_classes = []
        self.processed_clubs = {}
        self.club_to_region = {}
        self.club_to_opening_hours = {}  # Store opening hours for each club
        self.club_to_classes = {}  # Store classes by club
        self.club_to_address = {}  # Store club addresses
        self.club_start_times = {}  # Track when crawl for each club started
        self.club_end_times = {}    # Track when crawl for each club ended
        self.stop_event = stop_event if stop_event else asyncio.Event()
        self.total_clubs = 0
        self.current_club_index = 0
        self.websocket_manager = websocket_manager
        self.clubs_to_process = clubs_to_process
        self.crawl_results = {}  # Initialize crawl_results dictionary
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Store screenshot directory
        self.screenshot_dir = os.path.join(os.path.dirname(str(self.output_dir)), "screenshots")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # Use a single output JSONL file for all crawls
        self.filename = os.path.join(self.output_dir, "holmes.jsonl")
        self.collected_class_data = [] # Store all class data in memory
        
        # Initialize helper modules
        self.browser_manager = BrowserManager(self)
        self.club_processor = ClubProcessor(self)
        self.class_extractor = ClassExtractor(self)
        self.utils = CrawlerUtils(self)

    async def start(self):
        """Main entry point for crawling."""
        
        # Set up proper error tracking
        error_occurred = False
        
        try:
            # Update status
            if self.websocket_manager:
                await self.websocket_manager.update_status(
                    is_running=True,
                    progress=0,
                    current_club=None,
                    error=None
                )
            
            # Launch browser
            try:
                logger.info("Initializing browser...")
                # Give a little time before browser launch
                await asyncio.sleep(0.5)
                
                self.browser = await self.browser_manager.launch_browser()
                if not self.browser:
                    error_msg = "Failed to launch browser"
                    logger.error(error_msg)
                    await self.utils.send_status('error', "שגיאה בפתיחת הדפדפן")
                    raise Exception(error_msg)
                
                # Get the page that was already created during browser launch
                self.page = self.browser_manager.page
                if not self.page:
                    error_msg = "Browser launched but no page was created"
                    logger.error(error_msg)
                    await self.utils.send_status('error', "שגיאה ביצירת עמוד חדש")
                    raise Exception(error_msg)
                
                # Verify the page is working with a simple test
                await self.page.evaluate("1 + 1")
                
                logger.info("Browser and page successfully initialized")
            except Exception as e:
                error_occurred = True
                error_msg = f"Error initializing browser: {str(e)}"
                logger.error(error_msg, exc_info=True)
                await self.utils.send_status('error', f"‫שגיאה באתחול הדפדפן: {str(e)}‬ ")
                raise Exception(error_msg)
            
            # Start crawling
            try:
                await self.utils.send_status('info', "התחלת איסוף נתונים")
                
                if self.clubs_to_process:
                    # Check if we need to fetch club URLs from the homepage
                    missing_urls = any(not club_info.get("url") for club_info in self.clubs_to_process)
                    if missing_urls:
                        await self.utils.send_status('info', "מחפש קישורים למועדונים באתר הולמס פלייס")
                        club_urls = await self._fetch_club_urls_from_website()
                        
                        # Update clubs_to_process with URLs from website
                        for club_info in self.clubs_to_process:
                            club_name = club_info.get("name", "")
                            if not club_info.get("url") and club_name in club_urls:
                                club_info["url"] = club_urls[club_name]
                                await self.utils.send_status('info', f"נמצא קישור למועדון {club_name}")
                    
                    self.total_clubs = len(self.clubs_to_process)
                    logger.info(f"Processing {self.total_clubs} clubs provided directly")
                    
                    # Process each club
                    for i, club_info in enumerate(self.clubs_to_process):
                        # Skip clubs with no URL
                        if not club_info.get("url"):
                            logger.warning(f"Skipping club {club_info['name']} - no URL available")
                            continue
                            
                        # Update current club index
                        self.current_club_index = i
                        
                        # Update progress
                        if self.websocket_manager:
                            progress = int((i / self.total_clubs) * 100)
                            await self.websocket_manager.update_status(
                                progress=progress,
                                current_club=club_info["name"]
                            )
                        
                        try:
                            # Process club
                            await self.club_processor.process_club(club_info)
                        except Exception as e:
                            logger.error(f"Error processing club {club_info['name']}: {str(e)}")
                            await self.utils.send_status('error', f"שגיאה בעיבוד {club_info['name']}: {str(e)}")
                            # Continue with next club even if this one fails
                else:
                    logger.warning("No clubs provided to process")
                    await self.utils.send_status('warning', "לא נמצאו מועדונים לעיבוד")
                
                # Save results to file
                await self._save_results()
                
            except Exception as e:
                error_occurred = True
                error_msg = f"Error during data collection: {str(e)}"
                logger.error(error_msg, exc_info=True)
                await self.utils.send_status('error', f"‫שגיאה באיסוף נתונים: {str(e)}‬ ")
                raise
                
            # Update final status
            if self.websocket_manager:
                await self.websocket_manager.update_status(
                    is_running=False,
                    progress=100,
                    current_club=None,
                    error=None
                )
            
            logger.info("Crawling completed successfully")
            await self.utils.send_status('success', "איסוף הנתונים הושלם בהצלחה")
            
        except Exception as e:
            error_occurred = True
            error_msg = f"Error during crawling: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Update error status
            if self.websocket_manager:
                await self.websocket_manager.update_status(
                    is_running=False,
                    error=error_msg
                )
            
            await self.utils.send_status('error', f"‫שגיאה באיסוף נתונים: {str(e)}‬ ")
            raise
        finally:
            # Close browser properly using the cleanup method
            try:
                logger.info("Cleaning up browser resources...")
                if hasattr(self.browser_manager, '_cleanup'):
                    await self.browser_manager._cleanup()
                elif self.browser:
                    logger.info("Falling back to direct browser close...")
                    await self.browser.close()
            except Exception as e:
                logger.error(f"Error during browser cleanup: {str(e)}")

    async def _fetch_club_urls_from_website(self):
        """Fetch club URLs directly from the Holmes Place website."""
        club_urls = {}
        try:
            # Check if page is valid
            if not self.page:
                logger.error("Cannot fetch club URLs: page object is None")
                await self.utils.send_status('error', "שגיאה בטעינת העמוד")
                return {}
                
            # Navigate to the homepage
            success = await self.browser_manager.navigate_to(
                self.page, 
                self.base_url, 
                "Holmes Place homepage"
            )
            if not success:
                await self.utils.send_status('error', "שגיאה בטעינת האתר")
                await self.utils.take_screenshot("navigation_failed")
                return {}
            
            # Wait for the page to load
            await asyncio.sleep(2)
            
            # Try to find the clubs menu/links
            # First try the main navigation
            try:
                # Wait for the menu to be available and click to open it if needed
                menu_selector = "button.navbar-toggler"
                if await self.page.locator(menu_selector).count() > 0:
                    await self.page.click(menu_selector)
                    await asyncio.sleep(1)
                
                # Try various selectors that might contain club links
                selectors = [
                    "nav a[href*='club-page']",
                    ".dropdown-menu a[href*='club']",
                    "footer a[href*='club']",
                    "a[href*='club-page']"
                ]
                
                for selector in selectors:
                    links = await self.page.locator(selector).all()
                    if links:
                        logger.info(f"Found {len(links)} potential club links with selector: {selector}")
                        for link in links:
                            try:
                                href = await link.get_attribute("href")
                                text = await link.text_content()
                                if href and text and "club" in href.lower():
                                    text = text.strip()
                                    club_urls[text] = href if href.startswith("http") else self.base_url + href.lstrip("/")
                                    logger.info(f"Found club: {text} -> {club_urls[text]}")
                            except Exception as e:
                                logger.warning(f"Error extracting link info: {e}")
            except Exception as e:
                logger.warning(f"Error finding club links in navigation: {e}")
            
            # If we didn't find any clubs, try to find a "Clubs" page and navigate to it
            if not club_urls:
                try:
                    clubs_page_selectors = [
                        "a[href*='clubs']", 
                        "a:text('מועדונים')", 
                        "a:text('Clubs')",
                        "a[href*='locations']"
                    ]
                    
                    for selector in clubs_page_selectors:
                        clubs_links = await self.page.locator(selector).all()
                        if clubs_links:
                            # Click the first matching link
                            await clubs_links[0].click()
                            logger.info("Navigated to clubs listing page")
                            await asyncio.sleep(2)
                            
                            # Now try to find club links on this page
                            club_links = await self.page.locator("a[href*='club']").all()
                            for link in club_links:
                                try:
                                    href = await link.get_attribute("href")
                                    text = await link.text_content()
                                    if href and text:
                                        text = text.strip()
                                        club_urls[text] = href if href.startswith("http") else self.base_url + href.lstrip("/")
                                        logger.info(f"Found club: {text} -> {club_urls[text]}")
                                except Exception as e:
                                    logger.warning(f"Error extracting link info: {e}")
                            
                            # If we found clubs, break out of the loop
                            if club_urls:
                                break
                except Exception as e:
                    logger.warning(f"Error navigating to clubs page: {e}")
            
            # Take a screenshot for debugging
            if not club_urls:
                await self.utils.take_screenshot("homepage_clubs_not_found")
                logger.warning("Could not find club links on the website")
            
            return club_urls
            
        except Exception as e:
            logger.error(f"Error fetching club URLs from website: {str(e)}")
            await self.utils.take_screenshot("fetch_club_urls_error")
            return {}

    async def _save_results(self):
        """Save the crawling results to a JSONL file."""
        try:
            # Count successful and failed clubs
            successful_clubs = sum(1 for club in self.crawl_results.values() if club.get('status') == 'success')
            failed_clubs = sum(1 for club in self.crawl_results.values() if club.get('status') == 'failed')
            
            # Process all classes for output
            all_classes = []
            for club_name, classes in self.club_to_classes.items():
                for class_info in classes:
                    # Add club name to each class
                    class_with_club = class_info.copy()
                    class_with_club['club'] = club_name
                    # Add area/region if available
                    if club_name in self.club_to_region:
                        class_with_club['region'] = self.club_to_region[club_name]
                    all_classes.append(class_with_club)
            
            # Create a summary object
            results = {
                "crawl_timestamp": datetime.now().isoformat(),
                "total_clubs": self.total_clubs,
                "successful_clubs": successful_clubs,
                "failed_clubs": failed_clubs,
                "clubs": self.crawl_results,
                "classes": all_classes
            }
            
            # Write to JSONL file - append this result to existing file
            with open(self.filename, 'a') as f:
                f.write(json.dumps(results, ensure_ascii=False) + '\n')
            
            logger.info(f"Results saved to {self.filename}")
            await self.utils.send_status('info', f"התוצאות נשמרו ל {self.filename}")
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            await self.utils.send_status('error', f"שגיאה בשמירת התוצאות: {str(e)}")

    def get_results(self):
        """Returns a dictionary of all clubs with their classes."""
        results = {}
        
        # Create consolidated results with one entry per club
        for club_name, club_data in self.crawl_results.items():
            # Create club entry with all available data
            club_entry = {
                "club_name": club_name,
                "address": self.club_to_address.get(club_name, ""),
                "opening_hours": self.club_to_opening_hours.get(club_name, ""),
                "area": self.club_to_region.get(club_name, ""),
                "start_time": self.club_start_times.get(club_name, ""),
                "end_time": self.club_end_times.get(club_name, ""),
                "duration": self._calculate_duration(
                    self.club_start_times.get(club_name), 
                    self.club_end_times.get(club_name)
                ),
                "status": club_data['status']
            }
            
            # For successful clubs, include class data
            if club_data['status'] == 'success':
                club_entry["classes"] = self.club_to_classes.get(club_name, [])
            # For failed clubs, include error info and screenshot link if available
            else:
                club_entry["classes"] = []  # Empty array for failed clubs
                club_entry["error_reason"] = club_data.get('error_reason', "Unknown error")
                
                # Check for screenshot link in crawl_results
                if 'screenshot' in club_data and club_data['screenshot']:
                    # Include full URL for screenshot
                    base_url = "http://localhost:8000/screenshots/"
                    club_entry["screenshot_url"] = base_url + club_data['screenshot']
                # If no screenshot in crawl_results, look in screenshots directory
                else:
                    screenshots_dir = os.path.join(os.path.dirname(self.output_dir), "screenshots")
                    if os.path.exists(screenshots_dir):
                        # Look for screenshots with the club name in them
                        club_screenshots = [
                            f 
                            for f in os.listdir(screenshots_dir) 
                            if club_name in f and f.endswith(".png")
                        ]
                        if club_screenshots:
                            # Sort by timestamp (newest first) and take the most recent one
                            club_screenshots.sort(reverse=True)
                            # Include full URL for screenshot
                            base_url = "http://localhost:8000/screenshots/"
                            club_entry["screenshot_url"] = base_url + club_screenshots[0]
            
            results[club_name] = club_entry
            
        return results

    def _calculate_duration(self, start_time_str, end_time_str):
        """Calculate duration in seconds between two ISO format timestamps"""
        if not start_time_str or not end_time_str:
            return None
            
        try:
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
            duration = (end_time - start_time).total_seconds()
            return duration
        except Exception as e:
            logging.warning(f"Error calculating duration: {e}")
            return None

# Example usage (if run directly)
async def main():
    crawler = HolmesPlaceCrawler(headless=True)  # Enable headless mode
    await crawler.start()

if __name__ == "__main__":
    # To run this crawler directly for testing:
    # Ensure you have a running asyncio event loop
    # You might need to install playwright browsers: python -m playwright install
    asyncio.run(main()) 