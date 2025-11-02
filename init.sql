-- SafeTradeLab Database Schema
-- OHLCV Data Table

CREATE TABLE IF NOT EXISTS ohlcv_data (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(5) NOT NULL DEFAULT '5m',
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp, symbol, timeframe)
);

-- Create indexes for better query performance
CREATE INDEX idx_ohlcv_timestamp ON ohlcv_data(timestamp DESC);
CREATE INDEX idx_ohlcv_symbol ON ohlcv_data(symbol);
CREATE INDEX idx_ohlcv_symbol_timestamp ON ohlcv_data(symbol, timestamp DESC);

-- Create a function to clean old data (optional, keeps last 90 days)
CREATE OR REPLACE FUNCTION clean_old_data() RETURNS void AS $$
BEGIN
    DELETE FROM ohlcv_data
    WHERE timestamp < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE ohlcv_data IS 'Stores OHLCV (Open, High, Low, Close, Volume) data from Binance';
COMMENT ON COLUMN ohlcv_data.timestamp IS 'Candle open timestamp with timezone';
COMMENT ON COLUMN ohlcv_data.symbol IS 'Trading pair symbol (e.g., BTCUSDT)';
COMMENT ON COLUMN ohlcv_data.timeframe IS 'Candle timeframe (e.g., 1m, 5m, 1h)';
