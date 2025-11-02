"""
Database models for SafeTradeLab
Defines the structure of OHLCV data table
"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from .connection import Base

class OHLCVData(Base):
    """
    OHLCV (Open, High, Low, Close, Volume) data model
    Stores cryptocurrency price data with timestamp
    """
    __tablename__ = 'ohlcv_data'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Timestamps - UTC (Binance time) and Turkey time
    timestamp_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    timestamp_turkey = Column(DateTime(timezone=True), nullable=False, index=True)

    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(5), nullable=False, default='5m')

    # OHLCV data
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(20, 8), nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Unique constraint: one record per timestamp_turkey, symbol, and timeframe
    __table_args__ = (
        UniqueConstraint('timestamp_turkey', 'symbol', 'timeframe', name='uix_timestamp_symbol_timeframe'),
    )

    def __repr__(self) -> str:
        return (
            f"<OHLCVData(symbol={self.symbol}, timestamp_turkey={self.timestamp_turkey}, "
            f"close={self.close}, volume={self.volume})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'timestamp_utc': self.timestamp_utc.isoformat() if self.timestamp_utc else None,
            'timestamp_turkey': self.timestamp_turkey.isoformat() if self.timestamp_turkey else None,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'open': float(self.open) if self.open else None,
            'high': float(self.high) if self.high else None,
            'low': float(self.low) if self.low else None,
            'close': float(self.close) if self.close else None,
            'volume': float(self.volume) if self.volume else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_binance_kline(cls, kline: list, symbol: str, timeframe: str = '5m'):
        """
        Create OHLCVData instance from Binance kline data
        Binance kline format: [timestamp, open, high, low, close, volume, ...]
        """
        from datetime import timedelta

        # UTC timestamp from Binance
        utc_time = datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc)

        # Convert to Turkey time by adding 3 hours (keep as UTC timezone but with +3 hours)
        # This way PostgreSQL will show the actual Turkey time
        turkey_time = utc_time + timedelta(hours=3)

        return cls(
            timestamp_utc=utc_time,
            timestamp_turkey=turkey_time,
            symbol=symbol,
            timeframe=timeframe,
            open=kline[1],
            high=kline[2],
            low=kline[3],
            close=kline[4],
            volume=kline[5]
        )
