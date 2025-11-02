"""
SafeTradeLab Data Collector
BTC/USDT, ETH/USDT, SOL/USDT verilerini toplar (hem geçmiş hem real-time)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.collectors.historical_collector import HistoricalDataCollector
from src.collectors.realtime_collector import RealtimeDataCollector
from src.database.connection import db
from src.utils.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_historical_collection():
    """Akıllı veri toplama - sadece eksik candle'ları çeker (tüm semboller için)"""
    logger.info("Eksik veriler kontrol ediliyor...")

    try:
        if not db.test_connection():
            logger.error("Database bağlantısı başarısız!")
            return

        db.create_tables()

        # Her sembol için ayrı collector oluştur
        total_all_symbols = 0
        for symbol in Config.SYMBOLS:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {symbol}")
            logger.info(f"{'='*60}")

            collector = HistoricalDataCollector(symbol=symbol)
            total_saved = collector.backfill_data(days=180)  # Son 6 ay kontrolü
            total_all_symbols += total_saved
            logger.info(f"✓ {symbol}: {total_saved} YENİ kayıt toplandı")

        logger.info(f"\n{'='*60}")
        logger.info(f"TOPLAM: {total_all_symbols} YENİ kayıt toplandı")
        logger.info(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"Hata: {e}")
        raise


async def run_realtime_collection():
    """Real-time veri topla (tüm semboller için)"""
    logger.info("Real-time veri toplama başlıyor...")

    try:
        if not db.test_connection():
            logger.error("Database bağlantısı başarısız!")
            return

        db.create_tables()

        # Her sembol için ayrı collector oluştur
        collectors = [RealtimeDataCollector(symbol=symbol) for symbol in Config.SYMBOLS]

        # İlk kline'ları çek
        for collector in collectors:
            await collector.fetch_and_save_current_kline()

        logger.info(f"\nWebSocket streams başladı ({', '.join(Config.SYMBOLS)})")
        logger.info("Durdurmak için Ctrl+C\n")

        # Tüm collector'ları paralel çalıştır
        tasks = [collector.start() for collector in collectors]
        await asyncio.gather(*tasks)

    except KeyboardInterrupt:
        logger.info("Durduruluyor...")
        for collector in collectors:
            collector.stop()
    except Exception as e:
        logger.error(f"Hata: {e}")
        raise


async def main():
    """Ana fonksiyon - Akıllı veri toplama + real-time"""
    print("SafeTradeLab Data Collector - Smart Mode")
    print("=" * 60)
    print(f"Symbols: {', '.join(Config.SYMBOLS)}")
    print("=" * 60)

    # Akıllı veri toplama (sadece eksik candle'ları çeker)
    run_historical_collection()

    # Sonra real-time'a geç
    await run_realtime_collection()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nDurduruldu")
    except Exception as e:
        logger.error(f"Hata: {e}")
        sys.exit(1)
