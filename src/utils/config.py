"""
Configuration module for SafeTradeLab Data Collector
Loads environment variables and provides configuration settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the data collector"""

    # Binance API Configuration
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')

    # Trading Pair Configuration
    SYMBOLS = os.getenv('SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT').split(',')
    INTERVAL = os.getenv('INTERVAL', '5m')  # 5 minute candlesticks
    UPDATE_FREQUENCY_MINUTES = int(os.getenv('UPDATE_FREQUENCY_MINUTES', '5'))

    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', '5432'))
    DB_NAME = os.getenv('DB_NAME', 'safetradelab')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'safetradelab123')

    # Alternative: Use DATABASE_URL if provided
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )

    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/datacollector.log')

    # Application Settings
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    LOGS_DIR = BASE_DIR / 'logs'

    @classmethod
    def validate(cls):
        """Validate configuration settings"""
        errors = []

        if not cls.SYMBOLS:
            errors.append("SYMBOLS is required")

        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is required")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        return True

    @classmethod
    def ensure_dirs(cls):
        """Ensure required directories exist"""
        cls.LOGS_DIR.mkdir(exist_ok=True)


# Validate configuration on import
Config.validate()
Config.ensure_dirs()
