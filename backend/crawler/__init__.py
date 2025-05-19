# Export HolmesPlaceCrawler class as the main interface
from .crawler_core import HolmesPlaceCrawler

# Also expose the helper classes for advanced usage
from .crawler_browser import BrowserManager
from .crawler_clubs import ClubProcessor
from .crawler_classes import ClassExtractor
from .crawler_utils import CrawlerUtils

__version__ = "1.0.0" 