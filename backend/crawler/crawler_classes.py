import logging
import re
from datetime import datetime
import pytz

# Configure logging
logger = logging.getLogger(__name__)

class ClassExtractor:
    """Handles class schedule extraction and processing."""
    
    def __init__(self, crawler):
        """Initialize with reference to parent crawler."""
        self.crawler = crawler

    async def process_schedule_content(self, club_name, container_selector):
        """Extracts classes from the entire schedule content area. Handles multiple days within."""
        total_classes_found = 0
        logging.info(f"Extracting all classes within container '{container_selector}' for {club_name}...")

        # Selector for the columns/divs that group classes by day
        day_column_selector = "div.col-sm.text-center"
        day_header_selector = "div.day.sticky"
        class_item_selector = "div.time.box-day"

        try:
            day_columns = await self.crawler.page.query_selector_all(f"{container_selector} {day_column_selector}")
            if not day_columns:
                logging.warning(f"No day columns found using selector '{container_selector} {day_column_selector}' for {club_name}.")
                await self.crawler.utils.send_status('warning', f"לא נמצאו עמודות ימים לעיבוד עבור {club_name}")
                return 0
                
            logging.info(f"Found {len(day_columns)} potential day columns to process for {club_name}.")

            # Process each day column
            for day_index, day_column in enumerate(day_columns):
                # Check if we should stop crawling
                await self.crawler.utils.check_stop_event(f"processing day column {day_index+1}/{len(day_columns)} for {club_name}")
                
                # Extract the day name from the header
                day_header = await day_column.query_selector(day_header_selector)
                if not day_header:
                    logging.warning(f"No day header found in column {day_index+1} for {club_name}.")
                    continue
                    
                day_name = await day_header.text_content()
                day_name = day_name.strip() if day_name else "Unknown"
                logging.info(f"Processing day: {day_name} (Column {day_index+1}/{len(day_columns)}) for {club_name}")
                
                # Get day information
                day_info = self.crawler.utils.extract_day_from_hebrew(day_name)
                hebrew_day = day_info['hebrew']
                english_day = day_info['english']
                
                # Extract all class items for this day
                class_items = await day_column.query_selector_all(class_item_selector)
                if not class_items:
                    logging.warning(f"No class items found for day '{day_name}' in {club_name}.")
                    continue
                    
                logging.info(f"Found {len(class_items)} classes for day '{day_name}' in {club_name}.")
                
                # Process each class item
                for class_index, class_item in enumerate(class_items):
                    try:
                        # Extract class information
                        class_data = await self._extract_class_info(club_name, class_item, hebrew_day, english_day)
                        
                        if class_data:
                            # Add class to the list for this club
                            self.crawler.club_to_classes[club_name].append(class_data)
                            self.crawler.found_classes.append(class_data)
                            total_classes_found += 1
                        
                    except Exception as class_err:
                        logging.error(f"Error extracting class {class_index+1} from day '{day_name}' in {club_name}: {str(class_err)}")
                        # Continue with the next class
                        continue
                
            logging.info(f"Total classes extracted for {club_name}: {total_classes_found}")
            return total_classes_found
            
        except Exception as e:
            logging.error(f"Error processing schedule content for {club_name}: {str(e)}")
            raise

    async def _extract_class_info(self, club_name, class_element, hebrew_day, english_day):
        """Extract information from a single class element."""
        class_info = {
            "club": club_name,
            "day_name_hebrew": hebrew_day,
            "day_name_english": english_day,
            "day": english_day[:3].lower(),  # sun, mon, tue, etc.
            "timestamp": datetime.now(pytz.timezone('Asia/Jerusalem')).isoformat()
        }
        
        try:
            # Extract class time
            time_selector = "div.title"
            time_element = await class_element.query_selector(time_selector)
            if time_element:
                time_text = await time_element.text_content()
                time_text = time_text.strip() if time_text else ""
                if time_text:
                    class_info["time"] = time_text
                else:
                    logging.warning(f"Empty time for a class in {club_name} on {hebrew_day}")
                    class_info["time"] = "00:00"  # Default time
            else:
                logging.warning(f"No time element found for a class in {club_name} on {hebrew_day}")
                class_info["time"] = "00:00"  # Default time
            
            # Extract class name
            name_selector = "div.sub-title"
            name_element = await class_element.query_selector(name_selector)
            if name_element:
                name_text = await name_element.text_content()
                name_text = name_text.strip() if name_text else ""
                if name_text:
                    class_info["name"] = name_text
                else:
                    logging.warning(f"Empty name for a class in {club_name} on {hebrew_day} at {class_info.get('time', 'unknown')}")
                    class_info["name"] = "Unknown Class"  # Default name
            else:
                logging.warning(f"No name element found for a class in {club_name} on {hebrew_day} at {class_info.get('time', 'unknown')}")
                class_info["name"] = "Unknown Class"  # Default name
            
            # Extract instructor name
            instructor_selector = "div.trainer-name"
            instructor_element = await class_element.query_selector(instructor_selector)
            if instructor_element:
                instructor_text = await instructor_element.text_content()
                instructor_text = instructor_text.strip() if instructor_text else ""
                if instructor_text:
                    # Clean up common prefixes like "מדריך: " or "מדריכה: "
                    instructor_text = re.sub(r'^מדריכ[ה]?\s*[:]?\s*', '', instructor_text)
                    class_info["instructor"] = instructor_text
                else:
                    class_info["instructor"] = ""  # No instructor specified
            else:
                class_info["instructor"] = ""  # No instructor specified
            
            # Extract location
            location_selector = "div.location"
            location_element = await class_element.query_selector(location_selector)
            if location_element:
                location_text = await location_element.text_content()
                location_text = location_text.strip() if location_text else ""
                if location_text:
                    class_info["location"] = location_text
                else:
                    class_info["location"] = ""  # No location specified
            else:
                class_info["location"] = ""  # No location specified
            
            # Check if we have enough data to make this a valid class entry
            if not class_info.get("name") or class_info.get("name") == "Unknown Class":
                logging.warning(f"Skipping class with missing name in {club_name} on {hebrew_day} at {class_info.get('time', 'unknown')}")
                return None  # Skip this class
                
            # Apply any custom cleaning or formatting
            class_info["name"] = self.crawler.utils.clean_text(class_info["name"])
            class_info["instructor"] = self.crawler.utils.clean_text(class_info["instructor"])
            class_info["location"] = self.crawler.utils.clean_text(class_info["location"])
            
            # Log the extracted class
            logging.info(f"Extracted class: {class_info['name']} at {class_info['time']} with {class_info['instructor']} in {club_name} on {hebrew_day}")
            
            return class_info
            
        except Exception as e:
            logging.error(f"Error extracting class info in {club_name} on {hebrew_day}: {str(e)}")
            return None 