import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Base directories
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / "data"
    
    # WebSocket settings
    WS_PING_INTERVAL = 20  # seconds
    WS_PING_TIMEOUT = 20   # seconds
    
    # Crawler settings
    CRAWL_TIMEOUT = 1200  # seconds
    MAX_RETRIES = 5
    
    # Data freshness settings
    DATA_STALE_THRESHOLD = 7  # days
    
    # Browser settings
    HEADLESS_DEFAULT = os.getenv("HEADLESS_DEFAULT", "true").lower() == "true"
    BROWSER_TIMEOUT = 120  # seconds
    
    # API settings
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    
    @classmethod
    def ensure_output_dir(cls):
        """Create output directory if it doesn't exist"""
        # Create the data directory in the workspace root
        workspace_root = Path(os.getcwd())
        data_dir = workspace_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        # Create an empty .gitkeep file to ensure the directory is tracked
        (data_dir / ".gitkeep").touch(exist_ok=True)
        # Update OUTPUT_DIR to point to the workspace data directory
        cls.OUTPUT_DIR = data_dir

# Initialize output directory
Config.ensure_output_dir() 