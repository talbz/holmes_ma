import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from .config import Config  # Import Config

logger = logging.getLogger(__name__)

def get_latest_jsonl_file() -> str:
    """Get the path to the latest JSONL file in the configured OUTPUT_DIR."""
    data_dir = Config.OUTPUT_DIR  # Use Config.OUTPUT_DIR directly
    
    logger.info(f"Looking for JSONL files in: {data_dir}")
    if not data_dir.exists():
        logger.warning(f"Data directory does not exist: {data_dir}")
        return None
    
    # Look specifically for holmes.jsonl file
    holmes_file = data_dir / "holmes.jsonl"
    if not holmes_file.exists():
        logger.warning(f"holmes.jsonl not found in directory: {data_dir}")
        
        # Also check in the project root data directory as fallback
        root_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        holmes_file = root_data_dir / "holmes.jsonl"
        
        if not holmes_file.exists():
            # Final fallback to head_holmes.jsonl
            holmes_file = root_data_dir / "head_holmes.jsonl"
            if not holmes_file.exists():
                logger.warning("holmes.jsonl not found in any location")
                return None
    
    logger.info(f"Found holmes.jsonl file: {holmes_file}")
    return str(holmes_file)

def read_jsonl_file(file_path: str) -> List[Dict[str, Any]]:
    """Read a JSONL file and return its contents as a list of dictionaries."""
    entries = []
    try:
        # Always read line by line for JSONL format (multiple JSON objects, one per line)
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    # For each valid entry, add it to our list
                    entries.append(entry)
                    # Log information about this entry
                    if 'clubs' in entry:
                        club_count = len(entry['clubs']) if entry['clubs'] else 0
                        logger.info(f"Found entry with {club_count} clubs")
                        if club_count > 0:
                            logger.info(f"First club name: {list(entry['clubs'].keys())[0] if entry['clubs'] else 'None'}")
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON line in {file_path}: {e}")
        
        # Log how many entries we found
        logger.info(f"Found {len(entries)} entries in {file_path}")
        
        # Return the most recent entry (last one) if we found any
        if entries:
            latest_entry = entries[-1]  # Get the last entry, which is the most recent
            logger.info(f"Using latest entry with timestamp: {latest_entry.get('crawl_timestamp', 'unknown')}")
            return [latest_entry]  # Return as a list to maintain compatibility
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
    return entries

def append_to_jsonl_file(file_path: str, data: Dict[str, Any]) -> None:
    """Append a dictionary to a JSONL file."""
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data) + '\n')
    except Exception as e:
        raise Exception(f"Error appending to JSONL file: {str(e)}")

def calculate_days_since_crawl(file_path: str) -> int:
    """Calculate the number of days since the file was last modified."""
    if not file_path or not Path(file_path).exists(): # Add check for file existence
        return float('inf')
    
    try: # Add error handling for getmtime
        file_time = os.path.getmtime(file_path)
        current_time = datetime.now().timestamp()
        days_since_crawl = (current_time - file_time) / (24 * 60 * 60)
        return int(days_since_crawl)
    except FileNotFoundError:
        logger.warning(f"File not found when calculating days since crawl: {file_path}")
        return float('inf')
    except Exception as e:
        logger.error(f"Error calculating days since crawl for {file_path}: {e}")
        return float('inf') # Return infinity on error 