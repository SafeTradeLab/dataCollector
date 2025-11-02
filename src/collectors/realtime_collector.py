"""
Real-time Data Collector using Binance WebSocket API
Streams live OHLCV data and updates database every 5 minutes
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
import websockets
from binance.client import Client

from ..database.connection import db
from ..database.models import OHLCVData
from ..utils.config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RealtimeDataCollector:
    """
    Collects real-time OHLCV data from Binance using WebSocket API
    Updates database every time a 5-minute candle closes
    """

    def __init__(self, symbol: str, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """Initialize WebSocket collector for a specific symbol"""
        self.api_key = api_key or Config.BINANCE_API_KEY
        self.api_secret = api_secret or Config.BINANCE_API_SECRET
        self.symbol = symbol
        self.interval = Config.INTERVAL

        # WebSocket URL for kline/candlestick streams
        # Format: wss://stream.binance.com:9443/ws/<symbol>@kline_<interval>
        self.ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@kline_{self.interval}"

        # Connection state
        self.is_running = False
        self.websocket = None

        # Binance client for REST API fallback
        self.client = Client(self.api_key, self.api_secret)

        logger.info(f"Real-time collector initialized for {self.symbol} ({self.interval})")
        logger.info(f"WebSocket URL: {self.ws_url}")

    def save_kline_to_database(self, kline_data: dict) -> bool:
        """
        Save completed kline to database

        Args:
            kline_data: Kline data from WebSocket message

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Extract kline information
            kline = kline_data['k']

            # Only save if candle is closed
            if not kline['x']:
                logger.debug(f"Candle not closed yet for {self.symbol} at {kline['t']}")
                return False

            # Save to database
            with db.get_session() as session:
                from sqlalchemy import and_
                from datetime import timezone as tz

                # Create timestamps (UTC and Turkey)
                utc_time = datetime.fromtimestamp(kline['t'] / 1000, tz=tz.utc)
                turkey_time = utc_time + timedelta(hours=3)  # Add 3 hours for Turkey time

                # Check if already exists (using Turkey timestamp)
                existing = session.query(OHLCVData).filter(
                    and_(
                        OHLCVData.timestamp_turkey == turkey_time,
                        OHLCVData.symbol == self.symbol,
                        OHLCVData.timeframe == self.interval
                    )
                ).first()

                if existing:
                    # Update existing record
                    existing.timestamp_utc = utc_time
                    existing.open = float(kline['o'])
                    existing.high = float(kline['h'])
                    existing.low = float(kline['l'])
                    existing.close = float(kline['c'])
                    existing.volume = float(kline['v'])
                else:
                    # Create new record inside session
                    ohlcv = OHLCVData(
                        timestamp_utc=utc_time,
                        timestamp_turkey=turkey_time,
                        symbol=self.symbol,
                        timeframe=self.interval,
                        open=float(kline['o']),
                        high=float(kline['h']),
                        low=float(kline['l']),
                        close=float(kline['c']),
                        volume=float(kline['v'])
                    )
                    session.add(ohlcv)

                session.commit()

                # Log after commit
                logger.info(
                    f"✓ Saved {self.symbol} candle | "
                    f"Turkey: {turkey_time} | UTC: {utc_time} | "
                    f"Close: ${float(kline['c']):.2f} | "
                    f"Volume: {float(kline['v']):.4f}"
                )

            return True

        except Exception as e:
            logger.error(f"Error saving kline to database: {e}")
            return False

    async def handle_message(self, message: str):
        """
        Handle incoming WebSocket message

        Args:
            message: Raw WebSocket message (JSON string)
        """
        try:
            data = json.loads(message)

            # Check if this is a kline message
            if 'e' in data and data['e'] == 'kline':
                kline = data['k']

                # Log current candle info
                logger.debug(
                    f"Candle update | "
                    f"Symbol: {kline['s']} | "
                    f"Close: ${float(kline['c']):.2f} | "
                    f"Volume: {float(kline['v']):.4f} | "
                    f"Closed: {kline['x']}"
                )

                # Save to database when candle closes (every 5 minutes)
                if kline['x']:  # x = is candle closed
                    self.save_kline_to_database(data)

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def connect_and_stream(self):
        """
        Connect to WebSocket and start streaming data
        Automatically reconnects on connection loss
        """
        retry_count = 0
        max_retries = 5
        retry_delay = 5  # seconds

        while self.is_running and retry_count < max_retries:
            try:
                logger.info(f"Connecting to Binance WebSocket... (Attempt {retry_count + 1})")

                async with websockets.connect(self.ws_url) as websocket:
                    self.websocket = websocket
                    logger.info("✓ Connected to Binance WebSocket")
                    logger.info(f"Streaming {self.symbol} {self.interval} candles...")

                    # Reset retry count on successful connection
                    retry_count = 0

                    # Listen for messages
                    async for message in websocket:
                        if not self.is_running:
                            break
                        await self.handle_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                retry_count += 1

                if retry_count < max_retries:
                    logger.info(f"Reconnecting in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("Max retries reached. Stopping collector.")
                    self.is_running = False

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                retry_count += 1

                if retry_count < max_retries:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("Max retries reached. Stopping collector.")
                    self.is_running = False

    async def start(self):
        """Start the real-time data collector"""
        logger.info("Starting Real-time Data Collector")

        # Test database connection
        if not db.test_connection():
            logger.error("Database connection failed. Cannot start collector.")
            return

        # Create tables if they don't exist
        db.create_tables()

        # IMPORTANT: Fill any missing candles before starting WebSocket
        logger.info("Checking for missing candles before real-time stream...")
        await self.fill_missing_candles_before_start()

        # Start streaming
        self.is_running = True

        try:
            await self.connect_and_stream()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal. Stopping collector...")
            self.stop()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.stop()

    async def fill_missing_candles_before_start(self):
        """
        Fill any missing candles between last record and now using REST API
        This ensures no gaps when real-time collector starts
        """
        try:
            from datetime import timezone
            from sqlalchemy import func

            # Get last record timestamp (Turkey time)
            with db.get_session() as session:
                last_record = session.query(func.max(OHLCVData.timestamp_turkey)).filter(
                    OHLCVData.symbol == self.symbol,
                    OHLCVData.timeframe == self.interval
                ).scalar()

            if not last_record:
                logger.info("No previous records, skipping gap fill")
                return

            # last_record is Turkey time (+3 hours), convert to UTC for comparison
            last_record_turkey = last_record
            last_record_utc = last_record - timedelta(hours=3)

            # Get current local time and convert to UTC
            local_time = datetime.now()
            now_utc = local_time.astimezone(timezone.utc)
            

            logger.info(f"Local time: {local_time}")
            logger.info(f"Current time (UTC): {now_utc}")

            # Calculate missing time (compare Turkey times)
            time_diff = now_utc - last_record_utc
            missing_candles = int(time_diff.total_seconds() / 300)  # 5 minutes = 300 seconds

            # Exclude current open candle (not yet closed)
            minutes_since_candle_start = now_utc.minute % 5
            if minutes_since_candle_start < 5:
                # There's an open candle, don't count it
                missing_candles = max(0, missing_candles - 1)

            logger.info(f"Time difference: {time_diff}")
            logger.info(f"Missing CLOSED candles: {missing_candles}")

            if missing_candles < 1:
                logger.info(f"No missing closed candles (gap: {time_diff})")
                return

            logger.info(f"Found gap of {missing_candles} candles ({time_diff})")
            logger.info(f"Filling from {last_record} to {now}")

            # Fetch missing candles using REST API
            start_ms = int((last_record.timestamp() + 300) * 1000)  # +5 minutes in milliseconds
            end_ms = int(now.timestamp() * 1000)

            klines = self.client.get_historical_klines(
                symbol=self.symbol,
                interval=self.interval,
                start_str=str(start_ms),
                end_str=str(end_ms),
                limit=1000
            )

            if not klines:
                logger.warning("No klines returned from Binance for gap fill")
                return

            # Save to database
            saved_count = 0
            with db.get_session() as session:
                from sqlalchemy import and_

                for kline in klines:
                    from datetime import timezone as tz
                    utc_time = datetime.fromtimestamp(kline[0] / 1000, tz=tz.utc)
                    turkey_time = utc_time + timedelta(hours=3)  # Add 3 hours for Turkey time

                    # Check if already exists (using Turkey timestamp)
                    existing = session.query(OHLCVData).filter(
                        and_(
                            OHLCVData.timestamp_turkey == turkey_time,
                            OHLCVData.symbol == self.symbol,
                            OHLCVData.timeframe == self.interval
                        )
                    ).first()

                    if not existing:
                        ohlcv = OHLCVData(
                            timestamp_utc=utc_time,
                            timestamp_turkey=turkey_time,
                            symbol=self.symbol,
                            timeframe=self.interval,
                            open=float(kline[1]),
                            high=float(kline[2]),
                            low=float(kline[3]),
                            close=float(kline[4]),
                            volume=float(kline[5])
                        )
                        session.add(ohlcv)
                        saved_count += 1

                session.commit()

            logger.info(f"✓ Filled {saved_count} missing candles before starting WebSocket")

        except Exception as e:
            logger.error(f"Error filling missing candles: {e}")

    def stop(self):
        """Stop the collector"""
        logger.info("Stopping Real-time Data Collector")
        self.is_running = False

        if self.websocket:
            asyncio.create_task(self.websocket.close())

    async def fetch_and_save_current_kline(self):
        """
        Fetch current kline using REST API and save to database
        Useful for initial state or as fallback
        """
        try:
            logger.info(f"Fetching current {self.interval} kline for {self.symbol}")

            # Get latest klines (limit=1 returns most recent)
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=self.interval,
                limit=2  # Get last 2 to ensure we have a closed candle
            )

            if klines and len(klines) >= 2:
                # Save the second-to-last kline (which is definitely closed)
                closed_kline = klines[-2]

                with db.get_session() as session:
                    from sqlalchemy import and_
                    from datetime import timezone as tz

                    # Create timestamps (UTC and Turkey)
                    utc_time = datetime.fromtimestamp(closed_kline[0] / 1000, tz=tz.utc)
                    turkey_time = utc_time + timedelta(hours=3)  # Add 3 hours for Turkey time

                    # Check if already exists (using Turkey timestamp)
                    existing = session.query(OHLCVData).filter(
                        and_(
                            OHLCVData.timestamp_turkey == turkey_time,
                            OHLCVData.symbol == self.symbol,
                            OHLCVData.timeframe == self.interval
                        )
                    ).first()

                    if existing:
                        # Update existing
                        existing.timestamp_utc = utc_time
                        existing.open = float(closed_kline[1])
                        existing.high = float(closed_kline[2])
                        existing.low = float(closed_kline[3])
                        existing.close = float(closed_kline[4])
                        existing.volume = float(closed_kline[5])
                        close_price = existing.close
                    else:
                        # Create new record inside session
                        ohlcv = OHLCVData(
                            timestamp_utc=utc_time,
                            timestamp_turkey=turkey_time,
                            symbol=self.symbol,
                            timeframe=self.interval,
                            open=float(closed_kline[1]),
                            high=float(closed_kline[2]),
                            low=float(closed_kline[3]),
                            close=float(closed_kline[4]),
                            volume=float(closed_kline[5])
                        )
                        session.add(ohlcv)
                        close_price = ohlcv.close

                    session.commit()
                    logger.info(f"Saved current kline: Turkey: {turkey_time} | UTC: {utc_time} - ${float(close_price):.2f}")

                return True

        except Exception as e:
            logger.error(f"Error fetching current kline: {e}")
            return False


async def main():
    """Main function for running the real-time collector"""
    logger.info("="*60)
    logger.info("SafeTradeLab Real-time Data Collector")
    logger.info(f"Symbols: {', '.join(Config.SYMBOLS)}")
    logger.info(f"Interval: {Config.INTERVAL}")
    logger.info(f"Update Frequency: Every {Config.UPDATE_FREQUENCY_MINUTES} minutes")
    logger.info("="*60)

    # Create collectors for all symbols
    collectors = [RealtimeDataCollector(symbol=symbol) for symbol in Config.SYMBOLS]

    # Fetch current klines for all symbols
    for collector in collectors:
        await collector.fetch_and_save_current_kline()

    # Start all collectors concurrently
    tasks = [collector.start() for collector in collectors]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        # Run the async main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nCollector stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
