#!/usr/bin/env python3
"""
Database cleanup script for SafeTradeLab
Deletes all collected OHLCV data from the database
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db
from src.database.models import OHLCVData
from src.utils.logger import get_logger

logger = get_logger(__name__)


def cleanup_database(confirm: bool = False):
    """
    Delete all OHLCV data from the database

    Args:
        confirm: If True, skip confirmation prompt
    """
    try:
        # Test connection
        if not db.test_connection():
            logger.error("Database connection failed!")
            return False

        # Get count before deletion
        with db.get_session() as session:
            total_records = session.query(OHLCVData).count()

        if total_records == 0:
            logger.info("Database is already empty. No records to delete.")
            return True

        logger.info(f"Found {total_records:,} records in the database")

        # Confirm deletion
        if not confirm:
            print(f"\n{'='*60}")
            print(f"WARNING: You are about to delete {total_records:,} records!")
            print(f"{'='*60}")
            response = input("Are you sure you want to continue? (yes/no): ")

            if response.lower() not in ['yes', 'y']:
                logger.info("Cleanup cancelled by user")
                return False

        # Delete all records
        logger.info("Starting database cleanup...")

        with db.get_session() as session:
            deleted_count = session.query(OHLCVData).delete()
            session.commit()

        logger.info(f"✓ Successfully deleted {deleted_count:,} records")
        logger.info("Database cleanup completed!")

        return True

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return False


def cleanup_specific_symbol(symbol: str, confirm: bool = False):
    """
    Delete data for a specific symbol

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        confirm: If True, skip confirmation prompt
    """
    try:
        if not db.test_connection():
            logger.error("Database connection failed!")
            return False

        with db.get_session() as session:
            total_records = session.query(OHLCVData).filter(
                OHLCVData.symbol == symbol
            ).count()

        if total_records == 0:
            logger.info(f"No records found for {symbol}")
            return True

        logger.info(f"Found {total_records:,} records for {symbol}")

        if not confirm:
            print(f"\n{'='*60}")
            print(f"WARNING: You are about to delete {total_records:,} records for {symbol}!")
            print(f"{'='*60}")
            response = input("Are you sure you want to continue? (yes/no): ")

            if response.lower() not in ['yes', 'y']:
                logger.info("Cleanup cancelled by user")
                return False

        logger.info(f"Deleting records for {symbol}...")

        with db.get_session() as session:
            deleted_count = session.query(OHLCVData).filter(
                OHLCVData.symbol == symbol
            ).delete()
            session.commit()

        logger.info(f"✓ Successfully deleted {deleted_count:,} records for {symbol}")

        return True

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return False


def show_statistics():
    """Show database statistics"""
    try:
        if not db.test_connection():
            logger.error("Database connection failed!")
            return

        with db.get_session() as session:
            from sqlalchemy import func

            # Total records
            total = session.query(OHLCVData).count()

            # Records per symbol
            stats = session.query(
                OHLCVData.symbol,
                func.count(OHLCVData.id).label('count'),
                func.min(OHLCVData.timestamp_turkey).label('first'),
                func.max(OHLCVData.timestamp_turkey).label('last')
            ).group_by(OHLCVData.symbol).all()

        print(f"\n{'='*80}")
        print(f"DATABASE STATISTICS")
        print(f"{'='*80}")
        print(f"Total records: {total:,}")
        print(f"\nPer Symbol:")
        print(f"{'-'*80}")

        for stat in stats:
            print(f"  {stat.symbol:12} | {stat.count:>10,} records | {stat.first} → {stat.last}")

        print(f"{'='*80}\n")

    except Exception as e:
        logger.error(f"Error showing statistics: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Database cleanup script')
    parser.add_argument(
        '--all',
        action='store_true',
        help='Delete all records from database'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        help='Delete records for specific symbol (e.g., BTCUSDT)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    # Show statistics
    if args.stats:
        show_statistics()
        sys.exit(0)

    # Delete all records
    if args.all:
        success = cleanup_database(confirm=args.yes)
        sys.exit(0 if success else 1)

    # Delete specific symbol
    if args.symbol:
        success = cleanup_specific_symbol(args.symbol, confirm=args.yes)
        sys.exit(0 if success else 1)

    # No arguments - show help
    parser.print_help()
    print("\nExamples:")
    print("  python scripts/cleanup_database.py --stats              # Show statistics")
    print("  python scripts/cleanup_database.py --all                # Delete all records (with confirmation)")
    print("  python scripts/cleanup_database.py --all --yes          # Delete all records (no confirmation)")
    print("  python scripts/cleanup_database.py --symbol BTCUSDT     # Delete BTCUSDT records")
