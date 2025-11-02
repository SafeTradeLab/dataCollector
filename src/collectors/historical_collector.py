"""
Historical Data Collector using Binance REST API
Fetches historical OHLCV data and stores in database
"""
from binance.client import Client
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import time

from ..database.connection import db
from ..database.models import OHLCVData
from ..utils.config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class HistoricalDataCollector:
    """
    Collects historical OHLCV data from Binance using REST API
    """

    def __init__(self, symbol: str, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Binance client
        API keys are optional for public market data
        """
        self.api_key = api_key or Config.BINANCE_API_KEY
        self.api_secret = api_secret or Config.BINANCE_API_SECRET
        self.symbol = symbol
        self.interval = Config.INTERVAL

        # Initialize Binance client
        self.client = Client(self.api_key, self.api_secret)
        logger.info(f"Historical collector initialized for {self.symbol} ({self.interval})")

    def get_last_record_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the last record in database

        Returns:
            Last record timestamp or None if database is empty
        """
        try:
            with db.get_session() as session:
                from sqlalchemy import func
                last_record = session.query(func.max(OHLCVData.timestamp_turkey)).filter(
                    OHLCVData.symbol == self.symbol,
                    OHLCVData.timeframe == self.interval
                ).scalar()

                if last_record:
                    logger.info(f"Last record in database (Turkey time): {last_record}")
                else:
                    logger.info("Database is empty, will fetch full 6 months")

                return last_record
        except Exception as e:
            logger.error(f"Error getting last record time: {e}")
            return None

    def fetch_historical_klines(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[list]:
        """
        Fetch historical kline/candlestick data from Binance

        Args:
            start_date: Start date for historical data (default: 30 days ago)
            end_date: End date for historical data (default: now)
            limit: Maximum number of klines to fetch (max 1000 per request)

        Returns:
            List of klines in Binance format
        """
        try:
            # Set default dates if not provided
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=30)

            logger.info(f"Fetching historical data for {self.symbol} from {start_date} to {end_date}")

            # Convert datetime to millisecond timestamp
            start_str = str(int(start_date.timestamp() * 1000))
            end_str = str(int(end_date.timestamp() * 1000))

            # Fetch klines from Binance
            klines = self.client.get_historical_klines(
                symbol=self.symbol,
                interval=self.interval,
                start_str=start_str,
                end_str=end_str,
                limit=limit
            )

            logger.info(f"Fetched {len(klines)} klines from Binance")
            return klines

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise

    def save_to_database(self, klines: List[list]) -> int:
        """
        Save klines to database (ONLY closed candles)

        Args:
            klines: List of klines in Binance format

        Returns:
            Number of records saved
        """
        from sqlalchemy import and_

        saved_count = 0
        skipped_count = 0
        open_candle_count = 0

        # Current time in UTC
        current_time_utc = datetime.now(timezone.utc)

        with db.get_session() as session:
            for kline in klines:
                # Kline close time (when the candle closes)
                # kline[6] is the close time in milliseconds
                candle_close_time = datetime.fromtimestamp(kline[6] / 1000, tz=timezone.utc)

                # SADECE KAPALI candleları kaydet
                # Eğer candle'ın close time'ı henüz gelmemişse (açık candle), atla
                if candle_close_time > current_time_utc:
                    open_candle_count += 1
                    continue

                # Create OHLCVData object
                ohlcv = OHLCVData.from_binance_kline(
                    kline=kline,
                    symbol=self.symbol,
                    timeframe=self.interval
                )

                # Check if record already exists (using Turkey timestamp)
                existing = session.query(OHLCVData).filter(
                    and_(
                        OHLCVData.timestamp_turkey == ohlcv.timestamp_turkey,
                        OHLCVData.symbol == ohlcv.symbol,
                        OHLCVData.timeframe == ohlcv.timeframe
                    )
                ).first()

                if existing:
                    # Update existing record
                    existing.timestamp_utc = ohlcv.timestamp_utc
                    existing.open = ohlcv.open
                    existing.high = ohlcv.high
                    existing.low = ohlcv.low
                    existing.close = ohlcv.close
                    existing.volume = ohlcv.volume
                    skipped_count += 1
                else:
                    # Add new record
                    session.add(ohlcv)
                    saved_count += 1

            # Commit all at once
            try:
                session.commit()
                if open_candle_count > 0:
                    logger.info(f"Saved {saved_count} new records, updated {skipped_count} existing records, skipped {open_candle_count} open candles")
                else:
                    logger.info(f"Saved {saved_count} new records, updated {skipped_count} existing records")
            except Exception as e:
                session.rollback()
                logger.error(f"Error committing to database: {e}")
                raise

        return saved_count

    def backfill_data(self, days: int = 180) -> int:
        """
        Akıllı veri toplama: Sadece eksik olan candle'ları çeker
        
        İlk çalışma: Son {days} günün tüm verisini çeker
        Sonraki çalışmalar: Sadece eksik candle'ları doldurur
        """
        logger.info(f"Starting smart backfill (max {days} days)")
        
        last_record_time_turkey = self.get_last_record_time()

        # Get current time in UTC
        local_time = datetime.now()
        current_time_utc = local_time.astimezone(timezone.utc)

        logger.info(f"Local time: {local_time}")
        logger.info(f"Current time (UTC): {current_time_utc}")

        # Veritabanı tamamen boşsa: Son {days} günü çek
        if last_record_time_turkey is None:
            logger.info(f"Database is empty. Fetching last {days} days of data...")
            start_time = current_time_utc - timedelta(days=days)
            total_saved = self.fetch_range(start_time, current_time_utc)
            logger.info(f"✓ Initial data collection: {total_saved} candles saved")
            return total_saved

        # Convert Turkey time to UTC for calculations
        last_record_utc = last_record_time_turkey - timedelta(hours=3)

        # Veritabanında veri varsa: Eksik candle'ları kontrol et
        max_start_time = current_time_utc - timedelta(days=days)

        if last_record_utc < max_start_time:
            start_time = max_start_time
            logger.warning(f"Last record too old (Turkey: {last_record_time_turkey}), starting from {days} days ago")
        else:
            start_time = last_record_utc + timedelta(minutes=5)

        # Eksik candle sayısını hesapla (UTC ile)
        # Sadece KAPANMIŞ candle'ları say (şu anki açık candle'ı dahil etme)
        missing_time = current_time_utc - last_record_utc
        estimated_missing = missing_time.total_seconds() / (5 * 60)

        # Şu anki açık candle'ı çıkar (henüz kapanmamış)
        minutes_since_candle_start = current_time_utc.minute % 5
        if minutes_since_candle_start < 5:
            # Henüz kapanmamış bir candle var, onu sayma
            estimated_missing = max(0, estimated_missing - 1)

        logger.info(f"Last record UTC: {last_record_utc} (Turkey: {last_record_time_turkey})")
        logger.info(f"Missing time: {missing_time}")
        logger.info(f"Estimated missing CLOSED candles: {int(estimated_missing)}")

        # Eksik candle yoksa çık
        if estimated_missing < 1:
            logger.info("No missing data, database is up to date")
            return 0
        
        # Eksik candle'ları doldur (UTC zamanlarıyla)
        logger.info(f"Filling gap: {start_time} → {current_time_utc}")
        total_saved = self.fetch_range(start_time, current_time_utc)

        return total_saved

    def fetch_range(self, start_time: datetime, end_time: datetime) -> int:
        """
        Fetch all candles in a time range

        Args:
            start_time: Start datetime (timezone-aware)
            end_time: End datetime (timezone-aware)

        Returns:
            Total number of NEW candles saved
        """
        from datetime import timezone

        total_saved = 0
        current_start = start_time
        max_iterations = 500
        iteration = 0

        logger.info(f"Fetching range: {start_time} → {end_time}")

        while current_start < end_time and iteration < max_iterations:
            iteration += 1

            try:
                # Fetch batch of klines
                klines = self.fetch_historical_klines(
                    start_date=current_start,
                    end_date=end_time,
                    limit=1000
                )

                if not klines:
                    # No data returned, skip forward
                    if (end_time - current_start).total_seconds() > 300:
                        logger.warning(f"No klines returned, skipping 1 hour forward")
                        current_start += timedelta(hours=1)
                        continue
                    else:
                        break

                # Save to database
                saved = self.save_to_database(klines)
                total_saved += saved

                # Move to next batch
                last_kline_time = datetime.fromtimestamp(klines[-1][0] / 1000, tz=timezone.utc)
                next_start = last_kline_time + timedelta(minutes=5)

                # Prevent infinite loop
                if next_start <= current_start:
                    logger.warning(f"Time not advancing, forcing skip")
                    current_start += timedelta(hours=1)
                else:
                    current_start = next_start

                # Rate limiting
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error fetching range: {e}")
                current_start += timedelta(hours=1)
                if current_start >= end_time:
                    break

        logger.info(f"✓ Fetched {total_saved} NEW candles from range")
        return total_saved

    def get_latest_price(self) -> dict:
        """
        Get the latest price for the symbol

        Returns:
            Dictionary with latest price information
        """
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            logger.info(f"Latest price for {self.symbol}: {ticker['price']}")
            return ticker
        except Exception as e:
            logger.error(f"Error fetching latest price: {e}")
            raise


def main():
    """Main function for testing historical collector"""
    logger.info("Starting Historical Data Collector")

    # Test database connection
    if not db.test_connection():
        logger.error("Database connection failed. Exiting.")
        return

    # Create tables if they don't exist
    db.create_tables()

    # Collect data for all symbols
    for symbol in Config.SYMBOLS:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {symbol}")
        logger.info(f"{'='*60}")

        # Initialize collector for this symbol
        collector = HistoricalDataCollector(symbol=symbol)

        # Get latest price
        latest_price = collector.get_latest_price()
        logger.info(f"Current {symbol} price: ${latest_price['price']}")

        # Backfill last 30 days of data
        collector.backfill_data(days=30)

    logger.info("\n✓ Historical data collection completed for all symbols")


if __name__ == "__main__":
    main()
