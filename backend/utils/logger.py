import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from .config import Config

def setup_logger(name: str) -> logging.Logger:
    """
    Set up a logger with both file and console handlers.
    
    Args:
        name: The name of the logger
        
    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Create logs directory if it doesn't exist
    logs_dir = Config.BASE_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        logs_dir / f"{name}.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create default logger
logger = setup_logger("holmes_crawler") 