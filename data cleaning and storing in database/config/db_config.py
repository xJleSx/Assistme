"""
Database configuration and connection management.
"""
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

load_dotenv()

logger = logging.getLogger(__name__)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "electronics_db")

# Use URL.create() to properly handle special characters in password (e.g. @)
DATABASE_URL = URL.create(
    drivername="postgresql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    """Get a new database session."""
    session = SessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise


def create_database():
    """Create the database if it doesn't exist."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
        if cur.fetchone():
            logger.info(f"Database '{DB_NAME}' already exists")
        else:
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            logger.info(f"Created database '{DB_NAME}'")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise


def create_tables():
    """Create all tables from schema.sql."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    
    with engine.connect() as conn:
        conn.execute(text(schema_sql))
        conn.commit()
    logger.info("All tables created successfully")
