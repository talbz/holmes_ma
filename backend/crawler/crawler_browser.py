import logging
import asyncio
import time
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

# Configure logging
logger = logging.getLogger(__name__)

class BrowserManager:
    """Handles browser initialization and management for the crawler."""
    
    def __init__(self, crawler):
        """Initialize with reference to parent crawler."""
        self.crawler = crawler
        self.retries = 3  # Increased from 2 to 3 for browser operations
        self.retry_delay = 2  # Increased from 1 to 2 seconds between retries
        self.default_timeout = 4000  # Default timeout in milliseconds
        self.navigation_timeout = 10000  # Navigation timeout in milliseconds
        self._playwright = None
        self.browser = None
        self.context = None  # Store reference to the browser context
        self.page = None  # Store reference to the active page

    async def ensure_browsers_installed(self):
        """Make sure the required browsers are installed before trying to use them."""
        logger.info("Ensuring browsers are installed...")
        try:
            import subprocess
            import sys
            
            # Run the install command with --with-deps to ensure all dependencies are installed
            logger.info("Running playwright install for Chromium...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
                capture_output=True,
                text=True
            )
            
            logger.info(f"Playwright install result: {result.returncode}")
            if result.stdout:
                logger.info(f"Playwright install output: {result.stdout}")
            if result.stderr:
                logger.warning(f"Playwright install warnings: {result.stderr}")
                
            # Give a moment for any background processes to complete
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Error ensuring browsers are installed: {str(e)}")
            return False

    async def launch_browser(self):
        """Launch a new browser instance with context and page in a single operation."""
        logger.info("Attempting to launch browser...")
        
        # Make sure any previous instances are cleaned up first
        await self._cleanup()
        
        # Ensure browsers are installed
        await self.ensure_browsers_installed()
        
        # Try multiple times to launch the browser
        for attempt in range(self.retries):
            try:
                logger.info(f"Browser launch attempt {attempt + 1}/{self.retries}")
                
                # Start playwright - store reference to prevent garbage collection
                self._playwright = await async_playwright().start()
                logger.info(f"Launching Chromium (headless={self.crawler.headless})...")
                
                # Launch with reasonable defaults for stability
                self.browser = await self._playwright.chromium.launch(
                    headless=self.crawler.headless,
                    args=[
                        '--disable-gpu', 
                        '--no-sandbox', 
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--disable-extensions'
                    ]
                )
                logger.info("Browser launched successfully.")
                
                # Create a browser context
                logger.info("Creating browser context...")
                self.context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    ignore_https_errors=True
                )
                
                # Create a page and wait to ensure it's fully initialized
                logger.info("Creating page from context...")
                self.page = await self.context.new_page()
                
                # Verify the page is working by running a simple evaluation
                await self.page.evaluate("1 + 1")
                
                # Configure page settings
                self.page.set_default_timeout(self.default_timeout)
                self.page.set_default_navigation_timeout(self.navigation_timeout)
                
                logger.info("Successfully created browser, context and page")
                return self.browser
                
            except Exception as e:
                logger.error(f"Browser launch attempt {attempt + 1} failed: {str(e)}")
                
                # Clean up any partial initialization
                await self._cleanup()
                
                # Try to save error details
                try:
                    # Ensure the screenshots directory exists
                    os.makedirs(self.crawler.screenshot_dir, exist_ok=True)
                    
                    # Create a simple error HTML file
                    error_html_path = os.path.join(self.crawler.screenshot_dir, "browser_launch_error.html")
                    with open(error_html_path, "w") as f:
                        f.write(f"<html><body><h1>Browser Launch Error</h1><p>{str(e)}</p></body></html>")
                    
                    logger.info(f"Saved browser launch error details to {error_html_path}")
                except Exception as screenshot_err:
                    logger.error(f"Failed to save error details: {str(screenshot_err)}")
                
                # If this isn't the last attempt, wait before retrying
                if attempt < self.retries - 1:
                    logger.info(f"Waiting {self.retry_delay} seconds before retrying browser launch...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to launch browser after {self.retries} attempts")
                    raise

    async def _cleanup(self):
        """Clean up browser resources."""
        try:
            if self.page:
                logger.info("Closing page...")
                try:
                    await self.page.close()
                except Exception as e:
                    logger.error(f"Error closing page: {str(e)}")
                self.page = None
                
            if self.context:
                logger.info("Closing browser context...")
                try:
                    await self.context.close()
                except Exception as e:
                    logger.error(f"Error closing context: {str(e)}")
                self.context = None
                
            if self.browser:
                logger.info("Closing browser...")
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.error(f"Error closing browser: {str(e)}")
                self.browser = None
                
            if self._playwright:
                logger.info("Stopping Playwright...")
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.error(f"Error stopping playwright: {str(e)}")
                self._playwright = None
                
            # Force garbage collection
            import gc
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error during browser cleanup: {str(e)}")

    async def create_page(self, browser):
        """Return the already created page or create a new one if needed."""
        try:
            # If we already have a valid page, return it
            if self.page:
                try:
                    # Check if page is still valid
                    await self.page.evaluate("1 + 1")
                    logger.info("Using existing page")
                    return self.page
                except Exception:
                    logger.warning("Existing page is no longer valid, creating a new one")
                    self.page = None
            
            # If we have a context but no page, create a new page
            if self.context:
                try:
                    logger.info("Creating new page from existing context...")
                    self.page = await self.context.new_page()
                    self.page.set_default_timeout(self.default_timeout)
                    self.page.set_default_navigation_timeout(self.navigation_timeout)
                    logger.info("Successfully created a new page")
                    return self.page
                except Exception as e:
                    logger.error(f"Error creating page: {str(e)}")
                    self.page = None
                    
                    # Context might be invalid if page creation failed
                    try:
                        await self.context.close()
                    except Exception:
                        pass
                    self.context = None
            
            # If we have no context but have a browser, create both
            if self.browser and not self.context:
                try:
                    logger.info("Creating new context and page...")
                    self.context = await self.browser.new_context(
                        viewport={'width': 1280, 'height': 800},
                        ignore_https_errors=True
                    )
                    self.page = await self.context.new_page()
                    self.page.set_default_timeout(self.default_timeout)
                    self.page.set_default_navigation_timeout(self.navigation_timeout)
                    logger.info("Successfully created a new context and page")
                    return self.page
                except Exception as e:
                    logger.error(f"Error creating context and page: {str(e)}")
                    # Clean up
                    await self._cleanup()
            
            # If we got here, we couldn't create a page
            logger.error("Failed to create a page - browser resources may be invalid")
            return None
                
        except Exception as e:
            logger.error(f"Unexpected error in create_page: {str(e)}", exc_info=True)
            return None

    async def close_interfering_modal(self, page, description="unknown"):
        """Checks for and closes a potentially interfering modal."""
        # Generic selectors for modals and close buttons
        interfering_modal_selector = "div.modal.fade.show[id]:not(#select-club)"  # Generic visible modal, not our target one
        close_button_selector = f"{interfering_modal_selector} button.close, {interfering_modal_selector} [aria-label='Close']"  # Common close buttons
        
        try:
            modal_element = await page.query_selector(interfering_modal_selector)
            if modal_element and await modal_element.is_visible():
                logger.warning(f"Interfering modal detected ({description}). Attempting to close.")
                await self.crawler.utils.send_status('warning', f"זוהה חלון קופץ שמפריע ({description}). מנסה לסגור...")
                
                close_button = await page.query_selector(close_button_selector)
                if close_button and await close_button.is_visible():
                    await close_button.click()
                    logger.info("Successfully closed interfering modal.")
                    return True
                else:
                    # Try hitting Escape key as fallback
                    await page.keyboard.press("Escape")
                    logger.info("Tried closing modal with Escape key.")
                    return True
        except Exception as e:
            logger.warning(f"Error handling interfering modal: {str(e)}")
        
        return False

    async def retry_operation(self, operation, description):
        """Attempts an async operation with retries, checking stop event."""
        last_exception = None
        for attempt in range(self.retries + 1):
            await self.crawler.utils.check_stop_event(f"retry attempt {attempt+1} for {description}")
            try:
                result = await operation()
                if attempt > 0:
                    logger.info(f"Operation '{description}' succeeded on attempt {attempt + 1}.")
                return result
            except (PlaywrightTimeoutError, PlaywrightError, asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
                if isinstance(e, asyncio.CancelledError):
                    raise e
                
                last_exception = e
                logger.warning(f"Attempt {attempt + 1}/{self.retries + 1} failed for: {description}. Error: {type(e).__name__} - {str(e)}")
                
                if attempt < self.retries:
                    await self.crawler.utils.check_stop_event(f"delay before retry {attempt+2} for {description}") 
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"Operation failed after {self.retries + 1} attempts: {description}. Final Error: {type(e).__name__} - {str(e)}")
                    await self.crawler.utils.send_status('error', f"הפעולה '{description}' נכשלה סופית לאחר {self.retries + 1} ניסיונות.")
                    
                    # Take a screenshot and store the path
                    screenshot_path = await self.crawler.utils.take_screenshot(f"failed_{description.replace(' ', '_')}")
                    
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
                    if club_name and club_name in self.crawler.crawl_results:
                        error_message = f"Operation '{description}' failed: {type(e).__name__} - {str(e)}"
                        self.crawler.crawl_results[club_name]['error_reason'] = error_message
                        if screenshot_path:
                            self.crawler.crawl_results[club_name]['screenshot'] = screenshot_path
                            
                    raise last_exception  # Re-raise the last captured exception
                    
        raise RuntimeError(f"Operation '{description}' failed unexpectedly without raising an exception after retries.") 

    async def navigate_to(self, page, url, description="page"):
        """Navigate to a URL with error handling."""
        if not page:
            logger.error(f"Cannot navigate to {url}: page object is None")
            return False
            
        try:
            logger.info(f"Navigating to {url}...")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            if not response:
                logger.warning(f"No response received when navigating to {url}")
                return False
                
            status = response.status
            if status >= 400:
                logger.error(f"Error navigating to {url}: HTTP status {status}")
                return False
                
            logger.info(f"Successfully navigated to {description} ({url})")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {str(e)}")
            return False 