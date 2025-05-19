import logging
from datetime import datetime
import re
import asyncio

# Configure logging
logger = logging.getLogger(__name__)

class ClubProcessor:
    """Handles club data extraction and processing."""
    
    def __init__(self, crawler):
        """Initialize with reference to parent crawler."""
        self.crawler = crawler

    async def process_club(self, club_info):
        """Processes a single club, extracting schedules and saving data."""
        club_name = club_info["name"]
        club_url = club_info["url"]
        
        # Record start time for this club
        self.crawler.club_start_times[club_name] = datetime.now().isoformat()
        
        # Initialize crawl results for this club
        self.crawler.crawl_results[club_name] = {
            "status": "processing",
            "url": club_url,  # Save the URL
            "error_reason": None
        }
        
        try:
            await self.crawler.browser_manager.retry_operation(
                lambda: self.crawler.page.goto(club_url, wait_until="networkidle"),
                f"Navigate to club page: {club_url}"
            )
            
            # Determine area based on club name
            area = self._determine_club_area(club_name)
            
            # Store area for this club
            self.crawler.club_to_region[club_name] = area
            
            # Extract opening hours and address before processing the schedule
            opening_hours = await self._extract_club_opening_hours(club_name)
            address = await self._extract_club_address(club_name)
            
            # Save opening hours to crawl results
            self.crawler.crawl_results[club_name]["opening_hours"] = opening_hours
            self.crawler.crawl_results[club_name]["address"] = address
            
            # Initialize an empty list for this club's classes
            self.crawler.club_to_classes[club_name] = []
            
            # Process the class schedule
            classes_count = await self._process_club_schedule(club_name)
            
            # Record end time for this club
            self.crawler.club_end_times[club_name] = datetime.now().isoformat()
            
            # Update status to success
            self.crawler.crawl_results[club_name]["status"] = "success"
            self.crawler.crawl_results[club_name]["classes_count"] = classes_count
            
        except Exception as e:
            logger.error(f"Error processing club {club_name}: {str(e)}")
            self.crawler.crawl_results[club_name]["status"] = "failed"
            self.crawler.crawl_results[club_name]["error_reason"] = str(e)
            raise

    def _determine_club_area(self, club_name):
        """Determine the geographic area for a club based on its name."""
        if "ירושלים" in club_name or "מבשרת" in club_name or "מודיעין" in club_name:
            return "ירושלים והסביבה"
        elif "תל אביב" in club_name or "רמת גן" in club_name or "בני ברק" in club_name or "גבעתיים" in club_name or "דיזנגוף" in club_name or "עזריאלי" in club_name or "פתח תקווה" in club_name or "ראש העין" in club_name or "גבעת שמואל" in club_name or "קריית אונו" in club_name:
            return "מרכז"
        elif "חיפה" in club_name or "קריות" in club_name or "קריון" in club_name or "גרנד קניון" in club_name or "חדרה" in club_name or "קיסריה" in club_name or "נהריה" in club_name:
            return "צפון"
        elif "באר שבע" in club_name or "אשדוד" in club_name or "אילת" in club_name:
            return "דרום"
        elif "נתניה" in club_name or "הרצליה" in club_name or "רעננה" in club_name or "כפר סבא" in club_name or "שבעת הכוכבים" in club_name or "הוד השרון" in club_name:
            return "שרון"
        elif "רחובות" in club_name or "ראשון לציון" in club_name or "נס ציונה" in club_name or "לוד" in club_name or "יבנה" in club_name:
            return "שפלה"
        else:
            return "מרכז"  # Default to מרכז instead of אחר

    async def _extract_club_opening_hours(self, club_name):
        """Extract opening hours from the club page."""
        logger.info(f"Extracting opening hours for club: {club_name}")
        opening_hours = {}
        
        try:
            # Look for opening hours information
            opening_hours_section = "div.club-details-info h3:contains('שעות פתיחה'), div.club-details-info h4:contains('שעות פתיחה')"
            opening_hours_element = await self.crawler.page.query_selector(opening_hours_section)
            
            if opening_hours_element:
                # Get the parent container
                parent_element = await opening_hours_element.evaluate_handle("el => el.parentElement")
                if parent_element:
                    # Get all text lines in the container
                    opening_hours_text = await parent_element.inner_text()
                    if opening_hours_text:
                        # Extract opening hours information
                        lines = opening_hours_text.strip().split('\n')
                        # Skip the header ("שעות פתיחה")
                        for line in lines[1:]:
                            line = line.strip()
                            if not line:
                                continue
                                
                            # Format is typically "day: hours" or "day hours"
                            if ':' in line:
                                day_part, hours_part = line.split(':', 1)
                                opening_hours[day_part.strip()] = hours_part.strip()
                            elif '-' in line:  # Look for time ranges like "06:00-23:00"
                                # Try to find the last occurrence of a letter before the time
                                parts = re.split(r'(\d+:\d+)', line, 1)
                                if len(parts) >= 2:
                                    day_part = parts[0].strip()
                                    hours_part = ''.join(parts[1:]).strip()
                                    opening_hours[day_part] = hours_part
                            else:
                                # Just store the whole line if we can't parse it
                                opening_hours[f"info_{len(opening_hours)}"] = line
            
            logger.info(f"Extracted opening hours for {club_name}: {opening_hours}")
            # Save to the crawler's dictionary
            self.crawler.club_to_opening_hours[club_name] = opening_hours
            return opening_hours
            
        except Exception as e:
            logger.error(f"Error extracting opening hours for {club_name}: {e}")
            return opening_hours

    async def _extract_club_address(self, club_name):
        """Extract address information from the club page."""
        logger.info(f"Extracting address for club: {club_name}")
        address = ""
        
        try:
            # Look for the address in the contact info section
            address_selector = "div.club-details-info.contact-info a[href*='waze.com'] i.fas.fa-map-marker-alt"
            address_element = await self.crawler.page.query_selector(address_selector)
            
            if address_element:
                # Get the parent <a> element
                parent_element = await address_element.evaluate_handle("el => el.parentElement")
                if parent_element:
                    address_text = await parent_element.text_content()
                    # Clean up the address text (remove the icon text)
                    if address_text:
                        address = address_text.replace("ברק בן אבינועם", "").strip()
                        
            if address:
                logger.info(f"Found address for {club_name}: {address}")
                self.crawler.club_to_address[club_name] = address
            else:
                logger.warning(f"Could not find address for {club_name}")
                
        except Exception as e:
            logger.error(f"Error extracting address for {club_name}: {e}")
            
        return address

    async def _process_club_schedule(self, club_name):
        """Process the club schedule page to extract classes."""
        total_classes = 0
        logger.info(f"Processing schedule page for club: {club_name}")
        
        try:
            # Look for the schedule container
            schedule_container = "div.schedule-wrap"
            
            # Check if the schedule element exists
            container_element = await self.crawler.page.query_selector(schedule_container)
            
            if not container_element:
                logger.warning(f"No schedule container found for {club_name}")
                await self.crawler.utils.send_status('warning', f"לוח השיעורים לא נמצא עבור {club_name}")
                return 0
            
            # Process the schedule content
            await self.crawler.utils.send_status('info', f"מעבד את לוח השיעורים של {club_name}")
            
            # Call the class extractor to process the schedule content
            total_classes = await self.crawler.class_extractor.process_schedule_content(club_name, schedule_container)
            
            logger.info(f"Extracted {total_classes} classes from {club_name}")
            await self.crawler.utils.send_status('success', f"נמצאו {total_classes} שיעורים ב-{club_name}")
            
            return total_classes
            
        except Exception as e:
            logger.error(f"Error processing schedule for {club_name}: {e}")
            await self.crawler.utils.send_status('error', f"שגיאה בעיבוד לוח השיעורים של {club_name}: {str(e)}")
            raise 