#!/usr/bin/env python3
"""
Database initialization script for the Economic Agency Index Dashboard.
This script creates the database and all necessary tables.
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

from app.models.eai import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment variables."""
    load_dotenv()
    
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    return f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

def create_database():
    """Create the database if it doesn't exist."""
    load_dotenv()
    
    # Connect to default postgres database to create new database
    default_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/postgres"
    engine = create_engine(default_url)
    
    try:
        with engine.connect() as conn:
            # Check if database exists
            result = conn.execute(text(
                f"SELECT 1 FROM pg_database WHERE datname = '{os.getenv('DB_NAME')}'"
            ))
            if not result.scalar():
                # Create database
                conn.execute(text(f"CREATE DATABASE {os.getenv('DB_NAME')}"))
                logger.info(f"Created database {os.getenv('DB_NAME')}")
            else:
                logger.info(f"Database {os.getenv('DB_NAME')} already exists")
    except SQLAlchemyError as e:
        logger.error(f"Error creating database: {e}")
        raise
    finally:
        engine.dispose()

def init_database():
    """Initialize the database with all tables."""
    try:
        # Create database if it doesn't exist
        create_database()
        
        # Connect to the application database
        engine = create_engine(get_database_url())
        
        # Create all tables
        Base.metadata.create_all(engine)
        logger.info("Successfully created all database tables")
        
        # Create PostGIS extension if it doesn't exist
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.commit()
            logger.info("PostGIS extension created or already exists")
            
    except SQLAlchemyError as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        engine.dispose()

def main():
    """Main function to run the database initialization."""
    try:
        logger.info("Starting database initialization...")
        init_database()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 