# Holmes Place Crawler

This crawler extracts class schedules from Holmes Place gyms. The crawler has been organized into a proper Python package structure for better organization and maintenance.

## Module Structure

The crawler code is now organized in the `backend/crawler` package with the following modules:

- `crawler_core.py` - Main crawler class with initialization and orchestration logic
- `crawler_browser.py` - Browser management and interaction handling
- `crawler_clubs.py` - Club data extraction and processing
- `crawler_classes.py` - Class schedule extraction and formatting
- `crawler_utils.py` - Utility functions for status updates, screenshots, etc.

## Usage

The main crawler can be imported directly from the package:

```python
from backend.crawler import HolmesPlaceCrawler

async def main():
    crawler = HolmesPlaceCrawler(headless=True)
    await crawler.start()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Dependencies

- Playwright for browser automation
- FastAPI for API endpoints
- Python 3.7+ with asyncio 