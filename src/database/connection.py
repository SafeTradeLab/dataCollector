"""
Database connection manager using SQLAlchemy
Provides connection pooling and session management
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from typing import Generator

from ..utils.config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Create base class for declarative models
Base = declarative_base()

class DatabaseConnection:
    """Database connection manager with connection pooling"""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize()

    def _initialize(self):
        """Initialize database engine and session factory"""
        try:
            # Create engine with connection pooling
            self.engine = create_engine(
                Config.DATABASE_URL,
                pool_size=10,  # Number of connections to keep open
                max_overflow=20,  # Max additional connections
                pool_timeout=30,  # Timeout for getting connection from pool
                pool_pre_ping=True,  # Verify connections before using
                echo=False  # Set to True for SQL query logging
            )

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            logger.info(f"Database connection established: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")

        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise

    def create_tables(self):
        """Create all tables defined in models"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions
        Usage:
            with db.get_session() as session:
                session.query(Model).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            from sqlalchemy import text
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")


# Global database instance
db = DatabaseConnection()
