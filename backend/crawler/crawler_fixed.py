import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from typing import Optional, List, Dict, Any # For type hinting
import re
import pytz
from utils.config import Config

# Assuming ConnectionManager is defined in app.py or a shared module
# If not, you might need to adjust the import or pass it differently.
# from app import ConnectionManager # Example import

MAX_RETRIES = 2 # Total attempts = 1 + MAX_RETRIES
RETRY_DELAY = 1 # Seconds between retries
DEFAULT_TIMEOUT = 4000 # 4 seconds in milliseconds for Playwright actions
NAVIGATION_TIMEOUT = 10000 

# Control characters for BiDi: RTL override / Pop directional formatting
BIDI_RTL = "\u202B"
BIDI_POP = "\u202C"

# Configure logging (ensure it's configured globally or passed appropriately)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HolmesPlaceCrawler:
    """Handles crawling Holmes Place website for class schedules."""
    # Add type hint for websocket_manager if possible (e.g., from app import ConnectionManager)
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
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        # Store screenshot directory
        self.screenshot_dir = os.path.join(os.path.dirname(str(self.output_dir)), "screenshots")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        # Use a single output JSONL file for all crawls
        self.filename = os.path.join(self.output_dir, "holmes.jsonl")
        self.collected_class_data = [] # Store all class data in memory

    async def _send_status(self, type: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Helper to send status updates via WebSocket and log with proper Hebrew display."""
        # Reverse Hebrew segments for correct readability
        def adjust_message(msg):
            # If contains Hebrew characters, reverse order
            if re.search('[\u0590-\u05FF]', msg):
                return msg[::-1]
            return msg
        adj_message = adjust_message(message)
        if self.websocket_manager:
            status_data = {
                "type": type,
                "message": adj_message,
                "timestamp": datetime.now().isoformat(),
            }
            if data:
                status_data["data"] = data
            try:
                # Use broadcast method if ConnectionManager has it
                if hasattr(self.websocket_manager, 'broadcast'):
                     await self.websocket_manager.broadcast(json.dumps(status_data))
                else:
                    logging.warning("Websocket manager does not have a broadcast method.")
            except Exception as ws_err:
                logging.error(f"Failed to send WebSocket status: {ws_err}")
                # Handle disconnection case specifically
                if "disconnected" in str(ws_err).lower() or "connection" in str(ws_err).lower():
                    logging.warning("WebSocket appears to be disconnected. Will continue crawling but some status updates may be missed.")
                    # Store message in a buffer if possible
                    if not hasattr(self, '_status_buffer'):
                        self._status_buffer = []
                    # Buffer up to 100 messages to avoid memory issues
                    if len(self._status_buffer) < 100:
                        self._status_buffer.append(status_data)
                    # Don't try to reconnect here - just note the disconnect and continue crawling
        logging.info(f"Status Update ({type}): {adj_message} {data or ''}")

    async def _take_screenshot(self, stage_name: str):
        """Takes a screenshot for debugging and returns the path."""
        if self.page:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"error_{stage_name}_{timestamp}.png"
                path = os.path.join(self.screenshot_dir, filename)
                await self.page.screenshot(path=path)
                logging.info(f"Screenshot saved to {path}")
                await self._send_status('error_screenshot', f"שגיאה בשלב {stage_name}. צילום מסך נשמר.")
                return filename  # Return just the filename, not the full path
            except Exception as ss_error:
                logging.error(f"Failed to take screenshot: {ss_error}")
                return None
        else:
            logging.warning("Cannot take screenshot, page object is not available.")
            return None

    async def _check_stop_event(self, context_msg=""):
        """Checks if the stop event is set and raises an exception if it is."""
        if self.stop_event and self.stop_event.is_set():
            logging.warning(f"Stop event detected during: {context_msg}. Stopping crawl.")
            raise asyncio.CancelledError(f"Crawler stop requested during {context_msg}")

    async def _retry_operation(self, operation: callable, description: str):
        """Attempts an async operation with retries, checking stop event."""
        last_exception = None
        for attempt in range(MAX_RETRIES + 1):
            await self._check_stop_event(f"retry attempt {attempt+1} for {description}")
            try:
                result = await operation()
                if attempt > 0:
                     logging.info(f"Operation '{description}' succeeded on attempt {attempt + 1}.")
                return result
            except (PlaywrightTimeoutError, PlaywrightError, asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
                if isinstance(e, asyncio.CancelledError): raise e
                last_exception = e
                logging.warning(f"Attempt {attempt + 1}/{MAX_RETRIES + 1} failed for: {BIDI_RTL}{description}{BIDI_POP}. Error: {type(e).__name__} - {str(e)}")
                if attempt < MAX_RETRIES:
                    await self._check_stop_event(f"delay before retry {attempt+2} for {description}") 
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logging.error(f"{BIDI_RTL}Operation failed after {MAX_RETRIES + 1} attempts: {description}{BIDI_POP}. Final Error: {type(e).__name__} - {str(e)}")
                    await self._send_status('error', f"הפעולה '{description}' נכשלה סופית לאחר {MAX_RETRIES + 1} ניסיונות.")
                    
                    # Take a screenshot and store the path
                    screenshot_path = await self._take_screenshot(f"failed_{description.replace(' ', '_')}")
                    
                    # Check if we're processing a club and store the error details
                    club_name = None
                    
                    # Try to extract club name from the description
                    if "for " in description and " for " not in description:
                        parts = description.split("for ")
                        if len(parts) > 1:
                            club_name = parts[1].strip()
                    elif " for " in description:
                        parts = description.split(" for ")
                        if len(parts) > 1:
                            club_name = parts[1].strip()
                            
                    # If we identified a club, store the error details in crawl_results
                    if club_name and club_name in self.crawl_results:
                        error_message = f"Operation '{description}' failed: {type(e).__name__} - {str(e)}"
                        self.crawl_results[club_name]['error_reason'] = error_message
                        if screenshot_path:
                            self.crawl_results[club_name]['screenshot'] = screenshot_path
                            
                    raise last_exception # Re-raise the last captured exception
        raise RuntimeError(f"Operation '{description}' failed unexpectedly without raising an exception after retries.")

    async def _close_interfering_modal(self, description: str):
        """Checks for and closes a potentially interfering modal."""
        # --- GUESSING SELECTORS - ADJUST IF YOU KNOW THEM --- #
        interfering_modal_selector = "div.modal.fade.show[id]:not(#select-club)" # Generic visible modal, not our target one
        close_button_selector = f"{interfering_modal_selector} button.close, {interfering_modal_selector} [aria-label='Close']" # Common close buttons
        # --- END GUESSING --- #
        
        try:
            modal_element = await self.page.query_selector(interfering_modal_selector)
            if modal_element and await modal_element.is_visible():
                logging.warning(f"Interfering modal detected ({description}). Attempting to close.")
                await self._send_status('warning', f"זוהה חלון קופץ שמפריע ({description}). מנסה לסגור...")
                close_button = await self.page.query_selector(close_button_selector)
                if close_button:
                    await self._retry_operation(
                         lambda: close_button.click(timeout=2000), # Quick timeout for close click
                         f"Click close on interfering modal ({description})"
                    )
                    await self.page.wait_for_timeout(500) # Wait briefly for close animation
                    logging.info(f"Clicked close on interfering modal ({description}).")
                else:
                    logging.warning(f"Could not find close button ({close_button_selector}) for interfering modal.")
                    await self._take_screenshot(f"interfering_modal_no_close_btn_{description}")
            # else: No interfering modal found or it's not visible
        except Exception as e:
            logging.error(f"Error checking/closing interfering modal ({description}): {e}")
            # Don't fail the whole crawl, just log it.
        
    async def start(self):
        """Main method to start the crawling process using footer links."""
        try:
            await self._send_status('crawl_started', 'התחלת איסוף נתונים...')
            
            # Launch browser with more robust options
            browser_options = {
                'headless': self.headless,
                'timeout': Config.BROWSER_TIMEOUT * 1000,  # Convert to milliseconds
                'args': [
                    '--disable-gpu',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            }
            
            logging.info(f"Launching browser with options: {browser_options}")
            
            async with async_playwright() as p:
                try:
                    self.browser = await p.chromium.launch(**browser_options)
                    self.page = await self._retry_operation(
                        lambda: self.browser.new_page(),
                        "Open new page"
                    )
                    await self.page.set_default_timeout(Config.BROWSER_TIMEOUT * 1000)
                    await self._check_stop_event("browser launch")
                    
                    # Initialize status buffer for storing messages during disconnection
                    self._status_buffer = []
                    critical_error_occurred = False
                    self.crawl_results = {}  # Reset results for this run
                    self.collected_class_data = []  # Reset collected data
                    club_info_list_to_iterate = []  # Define variable to hold the list of clubs to process
                    
                    # Add connection check before starting
                    try:
                        # Test WebSocket connection if we have a manager
                        if self.websocket_manager:
                            # Simple ping message to check connection
                            ping_data = {"type": "ping", "message": "Checking connection", "timestamp": datetime.now().isoformat()}
                            if hasattr(self.websocket_manager, 'broadcast'):
                                await self.websocket_manager.broadcast(json.dumps(ping_data))
                                logging.info("WebSocket connection checked successfully")
                    except Exception as conn_check_err:
                        logging.warning(f"WebSocket connection check failed: {conn_check_err}. Will continue crawling without real-time updates.")
                        # We continue anyway since the crawler should work even without WebSocket
                    
                    self.page.set_default_timeout(DEFAULT_TIMEOUT)
                    self.page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

                    await self._send_status('progress', 'Navigating to Holmes Place website', {"progress": 5})
                    await self._retry_operation(
                        lambda: self.page.goto(self.base_url, wait_until='domcontentloaded'),
                        f"Navigate to {self.base_url}"
                    )
                    await self._check_stop_event("navigation complete")
                    logging.info("Navigation complete. Checking for interfering modals.")
                    await self._close_interfering_modal("after_navigation")
                    
                    # --- Determine Clubs to Process --- 
                    if self.clubs_to_process:
                        logging.info(f"Retrying specific clubs: {[c['name'] for c in self.clubs_to_process]}")
                        club_info_list_to_iterate = self.clubs_to_process
                        # Send clubs_found based on the retry list
                        await self._send_status('clubs_found', f"מנסה מחדש {len(club_info_list_to_iterate)} סניפים.", {"clubs": [club['name'] for club in club_info_list_to_iterate]})
                    else:
                        logging.info("Starting full crawl, fetching club list from footer...")
                        # --- Get Club Links from Footer --- 
                        await self._send_status('progress', 'Getting club list from footer', {"progress": 10})
                        footer_nav_selector = "div.footer-navigation"
                        club_link_selector = f"{footer_nav_selector} .footer-h4-desktop li a" 
                        await self._retry_operation(lambda: self.page.wait_for_selector(footer_nav_selector, state='attached'), "Wait for footer navigation section")
                        club_link_elements = await self._retry_operation(lambda: self.page.query_selector_all(club_link_selector), "Find club links in footer")
                        club_info_list = []
                        for link_element in club_link_elements:
                            try:
                                href = await link_element.get_attribute('href')
                                name = await link_element.text_content()
                                name = name.strip() if name else None
                                if href and name and href != '#':
                                   if not href.startswith(('http://', 'https://')):
                                       href = self.base_url.rstrip('/') + ('/' if not href.startswith('/') else '') + href
                                   club_info_list.append({"name": name, "url": href})
                            except Exception as link_err:
                                logging.warning(f"Could not extract info from a footer link: {link_err}")
                        # -------------------------------------
                        
                        if not club_info_list:
                            await self._send_status('error', 'Could not find any valid club links in the footer.')
                            critical_error_occurred = True
                        
                        if not critical_error_occurred:
                            # --- Filter Club List --- 
                            keywords_to_include = ["הולמס פלייס", "גו אקטיב"]
                            filtered_club_list = [club for club in club_info_list if any(keyword in club['name'] for keyword in keywords_to_include)]
                            if not filtered_club_list:
                                await self._send_status('error', 'No relevant clubs (Holmes Place / Go Active) found in footer links.')
                                critical_error_occurred = True
                            else:
                                club_info_list_to_iterate = filtered_club_list
                                logging.info(f"Filtered clubs to process: {[club['name'] for club in club_info_list_to_iterate]}")
                                await self._send_status('clubs_found', f"נמצאו {len(club_info_list_to_iterate)} סניפים רלוונטיים לעיבוד.", {"clubs": [club['name'] for club in club_info_list_to_iterate]})
                     # --------------------------------
                    
                    # Proceed only if we have clubs to iterate and no critical error occurred earlier
                    if not critical_error_occurred and club_info_list_to_iterate:
                        total_clubs = len(club_info_list_to_iterate)
                        # --- Iterate Through Club Pages --- 
                        for index, club_info in enumerate(club_info_list_to_iterate):
                            await self._check_stop_event(f"processing club {index+1}")
                            club_name = club_info['name']
                            club_url = club_info['url']
                            progress_percent = int(15 + (index / total_clubs) * 80)
                            
                            await self._send_status(
                                'club_processing', 
                                f'מעבד סניף {index + 1}/{total_clubs}: {club_name}', 
                                {"club_name": club_name, "current": index + 1, "total": total_clubs, "progress_percent": progress_percent}
                            )
                            
                            club_succeeded = False # Track success for this specific club
                            try:
                                # Navigate to the specific club page
                                logging.info(f"Navigating to club page: {club_url}")
                                await self._retry_operation(
                                    lambda: self.page.goto(club_url, wait_until='domcontentloaded'),
                                    f"Navigate to {club_name} page ({club_url})"
                                )
                                logging.info(f"Navigation to {club_name} page successful. Checking for modals.")
                                await self._close_interfering_modal(f"on_{club_name}_page")
                                
                                # Process schedule and check if any classes were found
                                classes_processed_count = await self._process_club_schedule(club_name)
                                if classes_processed_count > 0:
                                    club_succeeded = True
                                    
                            except Exception as page_nav_err:
                                error_message = f"Failed to navigate/process club page {club_name} at {club_url}: {type(page_nav_err).__name__} - {page_nav_err}"
                                logging.error(error_message)
                                
                                # Take a screenshot of the error
                                screenshot_path = await self._take_screenshot(f"navigation_error_{club_name}")
                                
                                await self._send_status('error', f"שגיאה בניווט או עיבוד דף סניף {club_name}")
                                # No need to send club_failed here, handled by finally
                                continue # Continue to next club, but mark this one failed below
                            finally:
                                # Update crawl results status for the current club
                                status = 'success' if club_succeeded else 'failed'
                                if club_name in self.crawl_results:
                                    # Update existing entry
                                    self.crawl_results[club_name]['status'] = status
                                    if not club_succeeded and 'error_reason' not in self.crawl_results[club_name]:
                                        # Add generic error reason if none exists yet
                                        self.crawl_results[club_name]['error_reason'] = "Failed to process club page"
                                        if 'page_nav_err' in locals():
                                            self.crawl_results[club_name]['error_reason'] = str(page_nav_err)
                                        if 'screenshot_path' in locals() and screenshot_path:
                                            self.crawl_results[club_name]['screenshot'] = screenshot_path
                                else:
                                    # Create new entry
                                    result_entry = {"url": club_url, "status": status}
                                    if not club_succeeded:
                                        # Add error information for failed clubs
                                        result_entry['error_reason'] = "Failed to process club page"
                                        if 'page_nav_err' in locals():
                                            result_entry['error_reason'] = str(page_nav_err)
                                        if 'screenshot_path' in locals() and screenshot_path:
                                            result_entry['screenshot'] = screenshot_path
                                    self.crawl_results[club_name] = result_entry
                                    
                                # Send WebSocket status for the specific club only AFTER attempting it
                                if status == 'success':
                                     await self._send_status('club_success', f"עיבוד סניף {club_name} הסתיים (נמצאו שיעורים)", {"club_name": club_name})
                                else:
                                     await self._send_status('club_failed', f"עיבוד סניף {club_name} נכשל", {"club_name": club_name})
                                      
                        await self._send_status('progress', 'Finished processing all clubs.', {"progress": 95})
                except Exception as browser_err:
                    logging.error(f"Browser error: {browser_err}")
                    critical_error_occurred = True
                    await self._send_status('error', f"שגיאה בדפדפן: {str(browser_err)}")
            
        except asyncio.CancelledError:
             critical_error_occurred = True
             logging.warning("Crawler task cancelled (likely due to stop event).")
             await self._send_status('crawl_failed', 'תהליך איסוף הנתונים הופסק.')
        except Exception as e:
             critical_error_occurred = True 
             final_error_message = f"CRITICAL CRAWLING ERROR encountered: {type(e).__name__} - {e}"
             logging.error(final_error_message, exc_info=True)
             await self._send_status('error', f"שגיאה קריטית בתהליך האיסוף: {str(e)}")
             
        finally:
            # Browser cleanup
            if self.browser:
                try:
                    await self.browser.close()
                    logging.info("Browser closed.")
                except Exception as close_err:
                     logging.error(f"Error closing browser: {close_err}")
            
            # --- Save JSONL Data File --- 
            # Only save the data file if the crawl was complete (not stopped early, no critical errors)
            # and if we have collected data from at least one successful club
            was_stopped_early = self.stop_event and self.stop_event.is_set()
            has_successful_clubs = any(result['status'] == 'success' for result in self.crawl_results.values())
            
            if not was_stopped_early and not critical_error_occurred and has_successful_clubs:
                try:
                    # Prepare crawl record with metadata
                    consolidated = self.get_results()
                    timestamp = datetime.now().isoformat()
                    total = len(self.crawl_results)
                    successes = sum(1 for r in self.crawl_results.values() if r['status']=='success')
                    failures = total - successes
                    # Build record
                    record = {
                        "crawl_timestamp": timestamp,
                        "total_clubs": total,
                        "successful_clubs": successes,
                        "failed_clubs": failures,
                        "clubs": consolidated,
                        "classes": self.collected_class_data
                    }
                    # Append single JSONL entry
                    with open(self.filename, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(record, ensure_ascii=False) + '\n')
                    logging.info(f"Appended crawl record to {self.filename}")
                except Exception as save_err:
                    logging.error(f"Failed to append crawl record to {self.filename}: {save_err}")
            else:
                logging.warning(f"Not saving data file due to incomplete crawl: stopped_early={was_stopped_early}, critical_error={critical_error_occurred}, successful_clubs={has_successful_clubs}")
            # -------------------------

            # Determine overall success/failure for final message
            if self.stop_event and self.stop_event.is_set():
                 if not critical_error_occurred:
                    await self._send_status('crawl_failed', 'תהליך איסוף הנתונים הופסק.', {"was_complete": False})
            elif not critical_error_occurred:
                # Check if any clubs actually failed within the run if it wasn't stopped/critical
                if any(result['status'] == 'failed' for result in self.crawl_results.values()):
                    await self._send_status('crawl_complete', 'איסוף הנתונים הסתיים (עם שגיאות בחלק מהסניפים).', {"progress": 100, "was_complete": True})
                else:
                    await self._send_status('crawl_complete', 'איסוף הנתונים הסתיים בהצלחה.', {"progress": 100, "was_complete": True})
            else:
                 # If critical error happened earlier, send failed status
                await self._send_status('crawl_failed', 'תהליך איסוף הנתונים נכשל.', {"was_complete": False})