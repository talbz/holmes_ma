#!/usr/bin/env python3
import asyncio
import os
import sys
from playwright.async_api import async_playwright

# Add the parent directory to PYTHONPATH to enable imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.crawler.crawler_utils import CrawlerUtils

async def test_website_crawler():
    """Test fetching club URLs directly from the Holmes Place website."""
    print("Starting website crawler test...")
    base_url = "https://www.holmesplace.co.il/"
    
    async with async_playwright() as p:
        # Launch the browser
        print("Launching browser...")
        browser = await p.chromium.launch(headless=False)
        
        try:
            # Create a new page
            page = await browser.new_page()
            
            # Navigate to the homepage
            print(f"Navigating to {base_url}...")
            await page.goto(base_url)
            
            # Wait for the page to load
            await asyncio.sleep(2)
            
            # Try to find the clubs menu/links
            club_urls = {}
            try:
                # Wait for menu and click it if needed
                menu_selector = "button.navbar-toggler"
                if await page.locator(menu_selector).count() > 0:
                    print("Clicking menu button...")
                    await page.click(menu_selector)
                    await asyncio.sleep(1)
                
                # Try various selectors that might contain club links
                selectors = [
                    "nav a[href*='club-page']",
                    ".dropdown-menu a[href*='club']",
                    "footer a[href*='club']",
                    "a[href*='club-page']"
                ]
                
                for selector in selectors:
                    print(f"Trying selector: {selector}")
                    links = await page.locator(selector).all()
                    if links:
                        print(f"Found {len(links)} potential club links with this selector")
                        for link in links:
                            try:
                                href = await link.get_attribute("href")
                                text = await link.text_content()
                                if href and text and "club" in href.lower():
                                    text = text.strip()
                                    club_urls[text] = href if href.startswith("http") else base_url + href.lstrip("/")
                                    print(f"Found club: {text} -> {club_urls[text]}")
                            except Exception as e:
                                print(f"Error extracting link info: {e}")
            except Exception as e:
                print(f"Error finding club links in navigation: {e}")
            
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
                        print(f"Looking for clubs page with selector: {selector}")
                        clubs_links = await page.locator(selector).all()
                        if clubs_links:
                            # Click the first matching link
                            print("Found clubs page link, clicking it...")
                            await clubs_links[0].click()
                            await asyncio.sleep(2)
                            
                            # Now try to find club links on this page
                            print("Looking for club links on clubs page...")
                            club_links = await page.locator("a[href*='club']").all()
                            for link in club_links:
                                try:
                                    href = await link.get_attribute("href")
                                    text = await link.text_content()
                                    if href and text:
                                        text = text.strip()
                                        club_urls[text] = href if href.startswith("http") else base_url + href.lstrip("/")
                                        print(f"Found club: {text} -> {club_urls[text]}")
                                except Exception as e:
                                    print(f"Error extracting link info: {e}")
                            
                            # If we found clubs, break out of the loop
                            if club_urls:
                                break
                except Exception as e:
                    print(f"Error navigating to clubs page: {e}")
            
            # Take a screenshot for debugging
            if not club_urls:
                screenshot_dir = "screenshots"
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, "homepage_clubs_not_found.png")
                await page.screenshot(path=screenshot_path)
                print(f"No club links found. Screenshot saved to {screenshot_path}")
            
            # Print summary
            print(f"\nFound {len(club_urls)} clubs on the website:")
            for club_name, url in club_urls.items():
                print(f"- {club_name}: {url}")
                
        finally:
            # Close the browser
            print("Closing browser...")
            await browser.close()

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_website_crawler()) 