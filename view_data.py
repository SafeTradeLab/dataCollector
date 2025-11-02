#!/usr/bin/env python3
"""
Veritabanındaki verileri görüntüle (tüm semboller)
"""
import sys
sys.path.insert(0, '.')

from src.database.connection import db
from src.database.models import OHLCVData
from src.utils.config import Config
from sqlalchemy import func

print("=" * 80)
print("SafeTradeLab - Database Statistics")
print("=" * 80)

with db.get_session() as session:
    # Toplam kayıt sayısı
    total = session.query(func.count(OHLCVData.id)).scalar()
    print(f"\nToplam Kayıt: {total:,}")

    # Her sembol için istatistikler
    for symbol in Config.SYMBOLS:
        print(f"\n{'-' * 80}")
        print(f"Symbol: {symbol}")
        print(f"{'-' * 80}")

        # Sembol için kayıt sayısı
        symbol_count = session.query(func.count(OHLCVData.id))\
            .filter(OHLCVData.symbol == symbol)\
            .scalar()
        print(f"Kayıt Sayısı: {symbol_count:,}")

        # İlk ve son kayıt tarihleri (Turkey time)
        first = session.query(func.min(OHLCVData.timestamp_turkey))\
            .filter(OHLCVData.symbol == symbol)\
            .scalar()
        last = session.query(func.max(OHLCVData.timestamp_turkey))\
            .filter(OHLCVData.symbol == symbol)\
            .scalar()
        print(f"İlk Kayıt (Turkey): {first}")
        print(f"Son Kayıt (Turkey): {last}")

        # Son 5 kayıt
        print(f"\nSon 5 Kayıt:")
        records = session.query(OHLCVData)\
            .filter(OHLCVData.symbol == symbol)\
            .order_by(OHLCVData.timestamp_turkey.desc())\
            .limit(5)\
            .all()

        for r in records:
            print(f"  Turkey: {r.timestamp_turkey} | UTC: {r.timestamp_utc} | ${float(r.close):>10,.2f} | Vol: {float(r.volume):>12,.2f}")

print(f"\n{'=' * 80}")
