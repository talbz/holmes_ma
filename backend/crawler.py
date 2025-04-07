import asyncio
import json
import logging
import os
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from typing import Optional, List, Dict, Any # For type hinting
import re

# Assuming ConnectionManager is defined in app.py or a shared module
# If not, you might need to adjust the import or pass it differently.
# from app import ConnectionManager # Example import

MAX_RETRIES = 2 # Total attempts = 1 + MAX_RETRIES
RETRY_DELAY = 1 # Seconds between retries
DEFAULT_TIMEOUT = 4000 # 4 seconds in milliseconds for Playwright actions
NAVIGATION_TIMEOUT = 10000 

# Configure logging (ensure it's configured globally or passed appropriately)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HolmesPlaceCrawler:
    """Handles crawling Holmes Place website for class schedules."""
    # Add type hint for websocket_manager if possible (e.g., from app import ConnectionManager)
    def __init__(self, base_url="https://www.holmesplace.co.il/", websocket_manager: Optional[Any] = None, headless: bool = True, stop_event: Optional[asyncio.Event] = None, clubs_to_process: Optional[List[Dict[str, str]]] = None):
        self.base_url = base_url
        self.websocket_manager = websocket_manager
        self.headless = headless # Store the headless preference
        self.stop_event = stop_event # Store the event
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.screenshot_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.filename = os.path.join(self.data_dir, f"holmes_place_schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        self.playwright = None
        self.browser = None
        self.page = None
        self.clubs_to_process = clubs_to_process # Store clubs if provided for retry
        self.crawl_results = {} # Store status for each club processed {club_name: {url: ..., status: 'success'/'failed'}}
        self.status_filename = os.path.join(self.data_dir, "last_crawl_status.json")

    async def _send_status(self, type: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Helper to send status updates via WebSocket."""
        if self.websocket_manager:
            status_data = {
                "type": type,
                "message": message,
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
        logging.info(f"Status Update ({type}): {message} {data or ''}")

    async def _take_screenshot(self, stage_name: str):
        """Takes a screenshot for debugging."""
        if self.page:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(self.screenshot_dir, f"error_{stage_name}_{timestamp}.png")
                await self.page.screenshot(path=path)
                logging.info(f"Screenshot saved to {path}")
                await self._send_status('error_screenshot', f"שגיאה בשלב {stage_name}. צילום מסך נשמר.")
            except Exception as ss_error:
                logging.error(f"Failed to take screenshot: {ss_error}")
        else:
            logging.warning("Cannot take screenshot, page object is not available.")

    async def _check_stop_event(self, context_msg=""):
        """Checks if the stop event is set and raises an exception if it is."""
        if self.stop_event and self.stop_event.is_set():
            logging.warning(f"Stop event detected during: {context_msg}. Stopping crawl.")
            raise asyncio.CancelledError(f"Crawler stop requested during {context_msg}")

    async def _retry_operation(self, operation: callable, description: str):
        """Attempts an async operation with retries, checking stop event."""
        last_exception = None
        for attempt in range(MAX_RETRIES + 1):
            await self._check_stop_event(f"retry attempt {attempt+1} for {description}") # Check before each attempt
            try:
                result = await operation()
                if attempt > 0:
                     logging.info(f"Operation '{description}' succeeded on attempt {attempt + 1}.")
                return result
            except (PlaywrightTimeoutError, PlaywrightError, asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
                if isinstance(e, asyncio.CancelledError): raise e # Re-raise cancellation immediately
                last_exception = e
                logging.warning(f"Attempt {attempt + 1}/{MAX_RETRIES + 1} failed for: {description}. Error: {type(e).__name__} - {str(e)}")
                if attempt < MAX_RETRIES:
                    await self._check_stop_event(f"delay before retry {attempt+2} for {description}") 
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logging.error(f"Operation failed after {MAX_RETRIES + 1} attempts: {description}. Final Error: {type(e).__name__} - {str(e)}")
                    await self._send_status('error', f"הפעולה '{description}' נכשלה סופית לאחר {MAX_RETRIES + 1} ניסיונות.")
                    await self._take_screenshot(f"failed_{description.replace(' ', '_')}")
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
        await self._send_status('crawl_started', 'תהליך איסוף הנתונים מתחיל...')
        critical_error_occurred = False
        self.browser = None
        self.crawl_results = {} # Reset results for this run
        club_info_list_to_iterate = [] # Define variable to hold the list of clubs to process
        
        try:
            await self._check_stop_event("crawl start")
            async with async_playwright() as p:
                self.playwright = p
                launch_options = {"headless": self.headless}
                logging.info(f"Launching browser with options: {launch_options}")
                self.browser = await self._retry_operation(
                    lambda: self.playwright.chromium.launch(**launch_options),
                    "Launch browser"
                )
                await self._check_stop_event("browser launch")

                self.page = await self._retry_operation(
                    lambda: self.browser.new_page(),
                    "Open new page"
                )
                await self._check_stop_event("page creation")

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
                             await self._send_status('error', f"שגיאה בניווט או עיבוד דף סניף {club_name}")
                             # No need to send club_failed here, handled by finally
                             continue # Continue to next club, but mark this one failed below
                        finally:
                            # Update crawl results status for the current club
                            status = 'success' if club_succeeded else 'failed'
                            self.crawl_results[club_name] = {"url": club_url, "status": status}
                            # Send WebSocket status for the specific club only AFTER attempting it
                            if status == 'success':
                                 await self._send_status('club_success', f"עיבוד סניף {club_name} הסתיים (נמצאו שיעורים)", {"club_name": club_name})
                            else:
                                 await self._send_status('club_failed', f"עיבוד סניף {club_name} נכשל", {"club_name": club_name})
                                 
                    await self._send_status('progress', 'Finished processing all clubs.', {"progress": 95})
        
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
            if self.browser:
                try:
                    await self.browser.close()
                    logging.info("Browser closed.")
                except Exception as close_err:
                     logging.error(f"Error closing browser: {close_err}")
            
            # --- Save Final Status --- 
            try:
                with open(self.status_filename, 'w', encoding='utf-8') as f:
                    json.dump(self.crawl_results, f, ensure_ascii=False, indent=2)
                logging.info(f"Saved final crawl status to {self.status_filename}")
            except Exception as save_err:
                logging.error(f"Failed to save final crawl status: {save_err}")
            # -------------------------

            # Determine overall success/failure for final message
            if self.stop_event and self.stop_event.is_set():
                 if not critical_error_occurred:
                      await self._send_status('crawl_failed', 'תהליך איסוף הנתונים הופסק.')
            elif not critical_error_occurred:
                # Check if any clubs actually failed within the run if it wasn't stopped/critical
                if any(result['status'] == 'failed' for result in self.crawl_results.values()):
                     await self._send_status('crawl_complete', 'איסוף הנתונים הסתיים (עם שגיאות בחלק מהסניפים).', {"progress": 100})
                else:
                     await self._send_status('crawl_complete', 'איסוף הנתונים הסתיים בהצלחה.', {"progress": 100})
            else:
                 # If critical error happened earlier, send failed status
                 await self._send_status('crawl_failed', 'תהליך איסוף הנתונים נכשל.')

    async def _process_club_schedule(self, club_name: str) -> int:
        """Processes schedules for a single club page."""
        logging.info(f"Processing schedule page for club: {club_name}")
        
        schedule_link_selector = 'a.btn-orange:has-text("למערכת השיעורים המלאה")'
        # Selector for the main content area holding the schedule
        schedule_content_selector = "#pills-tab-studioContent"
        # Selector for an individual class item, used to confirm content loaded
        class_item_selector = "div.time.box-day" 
        
        any_classes_processed = False # Track if at least one class was saved for the club
        try:
            # --- Click the Full Schedule Link --- 
            logging.info(f"Looking for full schedule link: {schedule_link_selector}")
            await self._retry_operation(
                lambda: self.page.locator(schedule_link_selector).click(),
                f"Click 'Full Schedule' link for {club_name}"
            )
            logging.info(f"Clicked full schedule link for {club_name}. Waiting for schedule content...")
            
            # --- Wait for Schedule Content to Load --- 
            # Wait for the main container OR the first class item to appear
            # Using schedule_content_selector first as it might appear before items within it
            try:
                 logging.info(f"Waiting for schedule content container: {schedule_content_selector}")
                 await self._retry_operation(
                     lambda: self.page.wait_for_selector(schedule_content_selector, state='visible', timeout=DEFAULT_TIMEOUT * 1.5), # Slightly longer timeout
                     f"Wait for schedule content container '{schedule_content_selector}' for {club_name}"
                 )
                 logging.info(f"Schedule content container '{schedule_content_selector}' found. Verifying class items...")
                 # Add a small delay AFTER container is visible, before checking items inside
                 await self.page.wait_for_timeout(500)
                 # Now ensure at least one class item exists within it
                 await self._retry_operation(
                     lambda: self.page.wait_for_selector(f"{schedule_content_selector} {class_item_selector}", state='visible', timeout=DEFAULT_TIMEOUT),
                     f"Wait for first class item '{class_item_selector}' within container for {club_name}"
                 )
                 logging.info(f"First class item found within schedule container.")
            except Exception as wait_err:
                 logging.error(f"Failed to find schedule content ({schedule_content_selector} or {class_item_selector}) after clicking link for {club_name}: {wait_err}")
                 await self._send_status('error', f"תוכן מערכת השעות לא נטען לאחר לחיצה על הקישור בסניף {club_name}")
                 await self._take_screenshot(f"schedule_content_load_fail_{club_name}")
                 # Consider this a failure for the club if content doesn't load
                 raise wait_err # Re-raise to trigger finally block correctly

            # --- Process Schedule Content (Simplified - No Day Clicking) --- 
            logging.info(f"Processing all schedule content within {schedule_content_selector} for {club_name}")
            # Call the refactored processing function (which now handles multiple days)
            classes_found_count = await self._process_schedule_content(club_name, schedule_content_selector)
            
            if classes_found_count > 0:
                any_classes_processed = True

        except Exception as e:
            # Catch errors during the club schedule processing
            logging.error(f"Critical error processing schedule for club {club_name}: {type(e).__name__} - {e}", exc_info=False) 
            await self._send_status('error', f"שגיאה קריטית בעיבוד מערכת סניף {club_name}: {str(e)}")
            # Failure is determined by any_classes_processed in finally block
        finally:
            # Send final status for THIS club based on whether ANY classes were processed
            if any_classes_processed:
                await self._send_status('club_success', f"עיבוד סניף {club_name} הסתיים (נמצאו שיעורים)", {"club_name": club_name})
                logging.info(f"Club {club_name} marked as SUCCESS as some classes were processed.")
            else:
                # Only mark as failed if NO classes were processed 
                # Error status might have already been sent if content failed to load
                # Ensure we send failed status specifically if no classes were found
                if 'wait_err' not in locals(): # Check if the error was *not* the wait error
                     await self._send_status('club_failed', f"עיבוד סניף {club_name} נכשל (לא נמצאו שיעורים)", {"club_name": club_name})
                logging.warning(f"Club {club_name} marked as FAILED as no classes were processed.")
                
            return classes_found_count

    # Renamed from _process_day_classes as it handles the whole container now
    async def _process_schedule_content(self, club_name: str, container_selector: str) -> int:
        """Extracts classes from the entire schedule content area. Handles multiple days within."""
        total_classes_found = 0
        logging.info(f"Extracting all classes within container '{container_selector}' for {club_name}...")

        # Selector for the columns/divs that group classes by day
        day_column_selector = "div.col-sm.text-center"
        day_header_selector = "div.day.sticky"
        class_item_selector = "div.time.box-day"

        try:
            day_columns = await self.page.query_selector_all(f"{container_selector} {day_column_selector}")
            if not day_columns:
                logging.warning(f"No day columns found using selector '{container_selector} {day_column_selector}' for {club_name}.")
                await self._send_status('warning', f"לא נמצאו עמודות ימים לעיבוד עבור {club_name}")
                return 0
                
            logging.info(f"Found {len(day_columns)} potential day columns to process for {club_name}.")

            for day_col_index, day_column in enumerate(day_columns):
                hebrew_day_name = f"Unknown Day {day_col_index + 1}" # Default
                iso_date_str = None # YYYY-MM-DD format
                day_classes_found_count = 0
                
                try:
                    # Extract Day Name and Date from sticky header
                    day_header_element = await day_column.query_selector(day_header_selector)
                    if day_header_element:
                        day_text_content = await day_header_element.text_content()
                        if day_text_content:
                            day_text_content = day_text_content.strip()
                            # Try to extract date first using regex
                            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', day_text_content)
                            if date_match:
                                date_str_ddmmyyyy = date_match.group(1)
                                try:
                                    parsed_date = datetime.strptime(date_str_ddmmyyyy, '%d/%m/%Y')
                                    iso_date_str = parsed_date.strftime('%Y-%m-%d')
                                    # Try to extract Hebrew name by removing the date
                                    potential_hebrew_name = day_text_content.replace(date_str_ddmmyyyy, '').strip()
                                    # Remove potential leading/trailing non-Hebrew chars if needed
                                    potential_hebrew_name = re.sub(r'^[\W\d]+|[\W\d]+$', '', potential_hebrew_name).strip()
                                    if potential_hebrew_name and any('\u0590' <= char <= '\u05FF' for char in potential_hebrew_name):
                                         hebrew_day_name = potential_hebrew_name
                                    else: # Fallback if extraction failed
                                        hebrew_day_name = day_text_content.split()[0] if day_text_content.split() else "Unknown"
                                except ValueError as date_parse_err:
                                     logging.warning(f"Could not parse date '{date_str_ddmmyyyy}' from header '{day_text_content}': {date_parse_err}")
                                     hebrew_day_name = day_text_content # Use full text as fallback name
                            else:
                                 logging.warning(f"Could not find DD/MM/YYYY date in day header: '{day_text_content}'")
                                 hebrew_day_name = day_text_content # Use full text as fallback name
                                 
                    # Use the Hebrew name for status messages, but the ISO date for data saving
                    logging.info(f"--- Processing Day Column {day_col_index+1}: {hebrew_day_name} (Date: {iso_date_str or 'Not Found'}) ---")
                    await self._send_status('day_processing', f'מעבד את יום {hebrew_day_name}', {"day": hebrew_day_name})
                    
                    if not iso_date_str:
                         logging.error(f"Cannot process classes for day column {day_col_index+1} because date could not be determined.")
                         await self._send_status('warning', f"לא ניתן לעבד שיעורים עבור {hebrew_day_name} - תאריך לא זוהה.")
                         continue # Skip to next day column if date is missing

                    # Find class elements *within this day column*
                    class_elements = await day_column.query_selector_all(class_item_selector)
                    if not class_elements:
                        logging.info(f"No class elements ('{class_item_selector}') found for day '{hebrew_day_name}' (column {day_col_index+1}).")
                        await self._send_status('classes_found', f"לא נמצאו שיעורים ביום {hebrew_day_name}", {"club": club_name, "day": hebrew_day_name, "classes_count": 0})
                        continue # Move to the next day column

                    logging.info(f"Found {len(class_elements)} class elements for day '{hebrew_day_name}'.")

                    # Process each class element within this day column
                    for i, class_element in enumerate(class_elements):
                        try:
                            # --- Extract Data using new selectors --- 
                            class_name_element = await class_element.query_selector('h5.bottom-details')
                            time_duration_element = await class_element.query_selector('span.top-title-d')
                            details_elements = await class_element.query_selector_all('div.bottom-details p')

                            class_name = await self._retry_operation(lambda: class_name_element.text_content(), f"Get class name (day {hebrew_day_name}, item {i+1})") if class_name_element else None
                            time_duration_text = await self._retry_operation(lambda: time_duration_element.text_content(), f"Get time/duration (day {hebrew_day_name}, item {i+1})") if time_duration_element else None

                            instructor = None
                            location = None
                            if len(details_elements) >= 1:
                                p_text_1 = await self._retry_operation(lambda: details_elements[0].text_content(), f"Get details P1 (day {hebrew_day_name}, item {i+1})")
                                if p_text_1 and p_text_1.startswith("מדריך:"):
                                    instructor = p_text_1.replace("מדריך:", "").strip()
                                else:
                                    location = p_text_1.strip() 
                            if len(details_elements) >= 2:
                                p_text_2 = await self._retry_operation(lambda: details_elements[1].text_content(), f"Get details P2 (day {hebrew_day_name}, item {i+1})")
                                if location is None:
                                     location = p_text_2.strip()
                                elif instructor is None and p_text_2.startswith("מדריך:"):
                                    instructor = p_text_2.replace("מדריך:", "").strip()
                                elif not (p_text_1 and p_text_1.startswith("מדריך:")):
                                     location = p_text_2.strip()
                                     
                            class_time = None
                            duration = None
                            if time_duration_text:
                                parts = time_duration_text.split('|')
                                if len(parts) > 0:
                                    time_part = parts[0].replace('<i class="fas fa-chevron-left rotate"></i>', '').strip()
                                    if ':' in time_part:
                                         class_time = time_part
                                if len(parts) > 1:
                                    duration_part = parts[1].strip()
                                    duration_digits = ''.join(filter(str.isdigit, duration_part))
                                    if duration_digits:
                                        duration = f"{duration_digits} דק'"

                            # Clean extracted text
                            class_name = class_name.strip() if class_name else ""
                            instructor = instructor.strip() if instructor else ""
                            location = location.strip() if location else ""
                            class_time = class_time.strip() if class_time else ""
                            duration = duration.strip() if duration else ""

                            # Basic validation
                            if not class_time or not class_name:
                                logging.warning(f"Skipping class element {i+1} for day {hebrew_day_name} with missing time ('{class_time}') or name ('{class_name}')")
                                continue
                                
                            # --- SAVE TO JSONL with standard date --- 
                            class_data = {
                                "club": club_name,
                                "day": iso_date_str, # Use YYYY-MM-DD date
                                "day_name_hebrew": hebrew_day_name, # Store Hebrew name separately
                                "time": class_time,
                                "name": class_name,
                                "instructor": instructor,
                                "duration": duration,
                                "location": location,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            with open(self.filename, 'a', encoding='utf-8') as f:
                                f.write(json.dumps(class_data, ensure_ascii=False) + '\n')
                            day_classes_found_count += 1
                            logging.debug(f"Saved class: {class_name} at {class_time} on {hebrew_day_name} ({iso_date_str}) in {club_name}")

                        except Exception as item_error:
                            logging.error(f"Error processing class item {i+1} for day {hebrew_day_name}: {type(item_error).__name__} - {item_error}", exc_info=True)
                            await self._send_status('warning', f"שגיאה בעיבוד פריט שיעור {i+1} ביום {hebrew_day_name}")
                            continue # Continue with the next class item within the day
                            
                    # Send status after processing all items for the day
                    await self._send_status(
                        'classes_found', 
                        f"נמצאו {day_classes_found_count} שיעורים ביום {hebrew_day_name}",
                        {"club": club_name, "day": hebrew_day_name, "classes_count": day_classes_found_count}
                    )
                    total_classes_found += day_classes_found_count
                    logging.info(f"Finished processing day '{hebrew_day_name}' ({iso_date_str}). Found {day_classes_found_count} classes.")

                except Exception as day_col_error:
                    # Catch errors specific to processing a whole day column (e.g., finding header)
                    logging.error(f"Error processing day column {day_col_index+1} ('{hebrew_day_name}'): {type(day_col_error).__name__} - {day_col_error}", exc_info=True)
                    await self._send_status('error', f"שגיאה בעיבוד עמודת יום {day_col_index+1} ({hebrew_day_name}) בסניף {club_name}")
                    continue # Try the next day column
            
            logging.info(f"Finished processing all day columns for {club_name}. Total classes found: {total_classes_found}")
            return total_classes_found # Return the total count for the club

        except Exception as schedule_processing_error:
             logging.error(f"Critical error processing schedule content in {container_selector} for {club_name}: {type(schedule_processing_error).__name__} - {schedule_processing_error}", exc_info=True)
             await self._send_status('error', f"שגיאה קריטית בעיבוד תוכן המערכת עבור {club_name}: {str(schedule_processing_error)}")
             raise schedule_processing_error

# Example usage (if run directly)
async def main():
    crawler = HolmesPlaceCrawler() # Add websocket_manager if needed
    await crawler.start()

if __name__ == "__main__":
    # To run this crawler directly for testing:
    # Ensure you have a running asyncio event loop
    # You might need to install playwright browsers: python -m playwright install
    asyncio.run(main()) 