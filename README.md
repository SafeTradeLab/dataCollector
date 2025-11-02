# SafeTradeLab Data Collector

BTC/USDT 5-minute candle data collector using Binance API.

## Quick Start

1. **Start PostgreSQL (Docker)**
   ```bash
   docker-compose up -d
   ```

2. **Run Data Collector**
   ```bash
   python main.py
   ```

## Features

- **Smart Backfill**: Automatically fills missing 5-minute candles
- **6 Months History**: Maintains last 180 days of data
- **Real-time WebSocket**: Live data updates every 5 minutes
- **No API Key Required**: Uses public Binance API
- **Gap Detection**: Ensures no missing candles

## View Data

```bash
python view_data.py
```

Or use Docker Desktop PostgreSQL terminal:
```sql
psql -U postgres -d safetradelab
SELECT * FROM ohlcv_data ORDER BY timestamp DESC LIMIT 10;
```

## Project Structure

```
datacollector/
├── main.py                 # Main entry point
├── view_data.py           # View database records
├── docker-compose.yml     # PostgreSQL setup
├── src/
│   ├── collectors/        # Data collection modules
│   ├── database/          # Database models & connection
│   └── utils/             # Config & logging
└── logs/                  # Application logs
```

## Requirements

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (via Docker)

## Koç University COMP 491 - SafeTradeLab
