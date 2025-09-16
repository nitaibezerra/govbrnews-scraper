#!/usr/bin/env python3
"""
PostgreSQL Database Initialization Script for GovBR News Dataset

This script downloads the govbrnews dataset from HuggingFace and populates
a PostgreSQL database with the news data.
"""

import os
import sys
import logging
import time
import psycopg2
from datasets import load_dataset
import pandas as pd
from psycopg2.extras import execute_values

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': os.getenv('POSTGRES_DB', 'govbrnews'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
    'port': '5432'
}

# HuggingFace dataset configuration
DATASET_PATH = "nitaibezerra/govbrnews"

def wait_for_postgres():
    """Wait for PostgreSQL to be ready."""
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.close()
            logger.info("PostgreSQL is ready!")
            return True
        except psycopg2.OperationalError as e:
            retry_count += 1
            logger.info(f"Waiting for PostgreSQL... ({retry_count}/{max_retries})")
            time.sleep(2)
    
    logger.error("PostgreSQL is not ready after maximum retries")
    return False

def create_tables():
    """Create the news table with appropriate schema."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # Create the news table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            unique_id VARCHAR(255) UNIQUE NOT NULL,
            agency VARCHAR(255),
            published_at TIMESTAMP,
            title TEXT,
            url TEXT,
            image TEXT,
            category VARCHAR(255),
            tags TEXT[],
            content TEXT,
            extracted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes for better query performance
        CREATE INDEX IF NOT EXISTS idx_news_agency ON news(agency);
        CREATE INDEX IF NOT EXISTS idx_news_published_at ON news(published_at);
        CREATE INDEX IF NOT EXISTS idx_news_unique_id ON news(unique_id);
        CREATE INDEX IF NOT EXISTS idx_news_category ON news(category);
        """
        
        cursor.execute(create_table_sql)
        conn.commit()
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def download_and_process_dataset():
    """Download the HuggingFace dataset and convert to pandas DataFrame."""
    try:
        logger.info("Downloading govbrnews dataset from HuggingFace...")
        dataset = load_dataset(DATASET_PATH, split="train")
        logger.info(f"Dataset downloaded successfully. Total records: {len(dataset)}")
        
        # Convert to pandas DataFrame for easier processing
        df = dataset.to_pandas()
        
        # Convert published_at and extracted_at to datetime
        df['published_at'] = pd.to_datetime(df['published_at'], errors='coerce')
        df['extracted_at'] = pd.to_datetime(df['extracted_at'], errors='coerce')
        
        # Handle tags column (convert list to PostgreSQL array format)
        if 'tags' in df.columns:
            df['tags'] = df['tags'].apply(lambda x: x if isinstance(x, list) else [])
        else:
            df['tags'] = [[] for _ in range(len(df))]
        
        logger.info("Dataset processed successfully")
        return df
        
    except Exception as e:
        logger.error(f"Error downloading/processing dataset: {e}")
        raise

def insert_data_to_postgres(df):
    """Insert the DataFrame data into PostgreSQL."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        logger.info("Inserting data into PostgreSQL...")
        
        # Prepare data for insertion
        columns = [
            'unique_id', 'agency', 'published_at', 'title', 'url', 
            'image', 'category', 'tags', 'content', 'extracted_at'
        ]
        
        # Fill missing columns with None
        for col in columns:
            if col not in df.columns:
                df[col] = None
        
        # Convert DataFrame to list of tuples
        data_tuples = []
        for _, row in df.iterrows():
            data_tuple = tuple(
                row[col] if pd.notna(row[col]) else None 
                for col in columns
            )
            data_tuples.append(data_tuple)
        
        # Insert data using execute_values for better performance
        insert_sql = """
        INSERT INTO news (unique_id, agency, published_at, title, url, image, 
                         category, tags, content, extracted_at)
        VALUES %s
        ON CONFLICT (unique_id) DO UPDATE SET
            agency = EXCLUDED.agency,
            published_at = EXCLUDED.published_at,
            title = EXCLUDED.title,
            url = EXCLUDED.url,
            image = EXCLUDED.image,
            category = EXCLUDED.category,
            tags = EXCLUDED.tags,
            content = EXCLUDED.content,
            extracted_at = EXCLUDED.extracted_at
        """
        
        execute_values(
            cursor, insert_sql, data_tuples, 
            template=None, page_size=1000
        )
        
        conn.commit()
        logger.info(f"Successfully inserted {len(data_tuples)} records into PostgreSQL")
        
        # Get some statistics
        cursor.execute("SELECT COUNT(*) FROM news")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT agency) FROM news")
        agency_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(published_at), MAX(published_at) FROM news WHERE published_at IS NOT NULL")
        date_range = cursor.fetchone()
        
        logger.info(f"Database statistics:")
        logger.info(f"  Total news records: {total_count}")
        logger.info(f"  Unique agencies: {agency_count}")
        if date_range[0] and date_range[1]:
            logger.info(f"  Date range: {date_range[0]} to {date_range[1]}")
        
    except Exception as e:
        logger.error(f"Error inserting data: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function to orchestrate the database initialization."""
    try:
        logger.info("Starting GovBR News database initialization...")
        
        # Wait for PostgreSQL to be ready
        if not wait_for_postgres():
            sys.exit(1)
        
        # Create database tables
        create_tables()
        
        # Download and process dataset
        df = download_and_process_dataset()
        
        # Insert data into PostgreSQL
        insert_data_to_postgres(df)
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
