#!/usr/bin/env python3
import asyncio
import json
import os
from backend.crawler import HolmesPlaceCrawler
import logging
from datetime import datetime

async def test_crawl():
    """Test the crawler's get_results function with some sample data"""
    # Create a crawler instance with a limited scope
    crawler = HolmesPlaceCrawler(output_dir="data/test")
    
    # Simulate some club data
    crawler.club_to_address = {
        "הולמס פלייס שבעת הכוכבים": "קניון שבעת הכוכבים, הרצליה",
        "הולמס פלייס פמלי חדרה": "קניון חדרה, חדרה"
    }
    
    crawler.club_to_opening_hours = {
        "הולמס פלייס שבעת הכוכבים": {
            "א'-ה'": "06:00-23:00", 
            "ו'": "06:00-17:00", 
            "שבת": "08:00-18:00"
        },
        "הולמס פלייס פמלי חדרה": {
            "א'-ה'": "06:00-22:30", 
            "ו'": "06:00-16:00", 
            "שבת": "08:00-17:00"
        }
    }
    
    crawler.club_to_region = {
        "הולמס פלייס שבעת הכוכבים": "שרון",
        "הולמס פלייס פמלי חדרה": "שרון"
    }
    
    crawler.club_start_times = {
        "הולמס פלייס שבעת הכוכבים": "2025-04-26T06:30:00",
        "הולמס פלייס פמלי חדרה": "2025-04-26T06:35:00"
    }
    
    crawler.club_end_times = {
        "הולמס פלייס שבעת הכוכבים": "2025-04-26T06:45:00",
        "הולמס פלייס פמלי חדרה": "2025-04-26T06:50:00"
    }
    
    # Simulate classes for successful club
    crawler.club_to_classes = {
        "הולמס פלייס שבעת הכוכבים": [
            {
                "club": "הולמס פלייס שבעת הכוכבים",
                "day": "2025-04-27",
                "day_name_hebrew": "ראשון",
                "time": "9:00",
                "name": "זומבה",
                "instructor": "דני דניאל",
                "duration": "60 דק'",
                "location": "סטודיו 1",
                "timestamp": "2025-04-26T06:49:30.424622"
            }
        ]
    }
    
    # Simulate crawl results with one success and one failure
    crawler.crawl_results = {
        "הולמס פלייס שבעת הכוכבים": {
            "url": "https://www.holmesplace.co.il/club-page-7-stars/",
            "status": "success"
        },
        "הולמס פלייס פמלי חדרה": {
            "url": "https://www.holmesplace.co.il/club-page-hadera/",
            "status": "failed",
            "error_reason": "Failed to find schedule link",
            "screenshot": "error_schedule_link_failed_20250426_072345.png"
        }
    }
    
    # Get results with our updated function
    results = crawler.get_results()
    
    # Print the results
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    # Test saving the club JSONL file
    os.makedirs("data/test", exist_ok=True)
    test_jsonl_filename = os.path.join("data/test", "test_clubs.jsonl")
    
    with open(test_jsonl_filename, 'w', encoding='utf-8') as f:
        for club_name, club_data in results.items():
            f.write(json.dumps(club_data, ensure_ascii=False) + '\n')
    
    print(f"\nSaved test club data to {test_jsonl_filename}")

if __name__ == "__main__":
    asyncio.run(test_crawl()) 