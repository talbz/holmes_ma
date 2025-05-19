#!/usr/bin/env python3
import asyncio
import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.crawler import HolmesPlaceCrawler

async def test_crawler_initialization():
    """Test that the crawler can initialize correctly without NoneType errors."""
    logger.info("Starting crawler initialization test...")
    
    # Create a test crawler instance
    crawler = HolmesPlaceCrawler(
        output_dir="data/test",
        headless=True,  # Use headless mode for testing
    )
    
    try:
        # Launch browser
        logger.info("Launching browser...")
        crawler.browser = await crawler.browser_manager.launch_browser()
        if not crawler.browser:
            logger.error("Failed to launch browser")
            return False
            
        logger.info("Creating page...")
        crawler.page = await crawler.browser_manager.create_page(crawler.browser)
        if not crawler.page:
            logger.error("Failed to create page")
            return False
            
        # Test navigation
        logger.info("Testing navigation...")
        success = await crawler.browser_manager.navigate_to(
            crawler.page, 
            "https://www.holmesplace.co.il/", 
            "Homepage"
        )
        if not success:
            logger.error("Failed to navigate to homepage")
            return False
            
        logger.info("Navigation successful")
        return True
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        return False
    finally:
        # Close browser
        if crawler.browser:
            logger.info("Closing browser...")
            await crawler.browser.close()

if __name__ == "__main__":
    success = asyncio.run(test_crawler_initialization())
    if success:
        print("\n✅ Test passed: Crawler initialization and navigation work correctly")
        sys.exit(0)
    else:
        print("\n❌ Test failed: Crawler initialization or navigation failed")
        sys.exit(1) 