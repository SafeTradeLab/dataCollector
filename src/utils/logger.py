"""
Logging configuration for SafeTradeLab Data Collector
Uses loguru for better logging experience
"""
import sys
from loguru import logger
from .config import Config

# Remove default logger
logger.remove()

# Add console logger
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=Config.LOG_LEVEL,
    colorize=True
)

# Add file logger
logger.add(
    Config.LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=Config.LOG_LEVEL,
    rotation="1 day",  # Rotate daily
    retention="30 days",  # Keep logs for 30 days
    compression="zip"  # Compress old logs
)

def get_logger(name: str):
    """Get a logger instance with a specific name"""
    return logger.bind(name=name)
