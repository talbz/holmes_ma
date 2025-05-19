from fastapi import APIRouter, Response
from typing import List, Optional
from models.models import ClassData
from utils.logger import logger
import json
from pathlib import Path
from utils.config import Config

router = APIRouter()

def get_latest_jsonl_file() -> Optional[Path]:
    """Get the latest JSONL file from the output directory"""
    output_dir = Config.OUTPUT_DIR
    jsonl_files = list(output_dir.glob("*.jsonl"))
    if not jsonl_files:
        logger.info("No JSONL files found in output directory")
        return None
    return max(jsonl_files, key=lambda x: x.stat().st_mtime)

def read_jsonl_data(file_path: Path) -> List[dict]:
    """Read and parse JSONL file"""
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON line: {str(e)}")
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
    return data

@router.get("/class-names")
async def get_class_names() -> List[str]:
    """Get all unique class names from the latest data file"""
    try:
        latest_file = get_latest_jsonl_file()
        if not latest_file:
            return []
            
        data = read_jsonl_data(latest_file)
        class_names = set()
        
        for club_data in data:
            if 'classes' in club_data:
                for class_data in club_data['classes']:
                    if 'class_name' in class_data and class_data['class_name']:
                        class_names.add(class_data['class_name'])
        
        return sorted(list(class_names))
    except Exception as e:
        logger.error(f"Error getting class names: {str(e)}")
        return []

@router.get("/instructors")
async def get_instructors() -> List[str]:
    """Get all unique instructor names from the latest data file"""
    try:
        latest_file = get_latest_jsonl_file()
        if not latest_file:
            return []
            
        data = read_jsonl_data(latest_file)
        instructors = set()
        
        for club_data in data:
            if 'classes' in club_data:
                for class_data in club_data['classes']:
                    if 'instructor' in class_data and class_data['instructor']:
                        instructors.add(class_data['instructor'])
        
        return sorted(list(instructors))
    except Exception as e:
        logger.error(f"Error getting instructors: {str(e)}")
        return []

@router.get("/classes")
async def get_classes(
    class_name: Optional[str] = None,
    day_name_hebrew: Optional[str] = None
) -> List[ClassData]:
    """Get classes with optional filtering by class name and day"""
    try:
        latest_file = get_latest_jsonl_file()
        if not latest_file:
            return []
            
        data = read_jsonl_data(latest_file)
        classes = []
        
        for club_data in data:
            if 'classes' in club_data:
                for class_data in club_data['classes']:
                    if class_name and class_data.get('class_name') != class_name:
                        continue
                    if day_name_hebrew and class_data.get('day_name_hebrew') != day_name_hebrew:
                        continue
                    classes.append(class_data)
        
        return classes
    except Exception as e:
        logger.error(f"Error getting classes: {str(e)}")
        return [] 