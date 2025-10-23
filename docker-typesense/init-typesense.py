#!/usr/bin/env python3
"""
Typesense Database Initialization Script for GovBR News Dataset

This script downloads the govbrnews dataset from HuggingFace and indexes it
into a Typesense search engine.
"""

import os
import sys
import logging
import time
import json
from typing import List, Dict, Any
import typesense
import requests
from datasets import load_dataset
import pandas as pd
import numpy as np

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Typesense configuration
TYPESENSE_HOST = os.getenv('TYPESENSE_HOST', 'localhost')
TYPESENSE_PORT = os.getenv('TYPESENSE_PORT', '8108')
TYPESENSE_API_KEY = os.getenv('TYPESENSE_API_KEY', 'govbrnews_api_key_change_in_production')
COLLECTION_NAME = 'news'

# HuggingFace dataset configuration
DATASET_PATH = "nitaibezerra/govbrnews"

def wait_for_typesense(max_retries=30):
    """Wait for Typesense to be ready."""
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Use requests directly to check health endpoint
            health_url = f"http://{TYPESENSE_HOST}:{TYPESENSE_PORT}/health"
            response = requests.get(health_url, timeout=5)

            if response.status_code == 200:
                logger.info("Typesense is ready!")
                # Now create and return the client
                client = typesense.Client({
                    'nodes': [{
                        'host': TYPESENSE_HOST,
                        'port': TYPESENSE_PORT,
                        'protocol': 'http'
                    }],
                    'api_key': TYPESENSE_API_KEY,
                    'connection_timeout_seconds': 10
                })
                return client

        except Exception as e:
            retry_count += 1
            logger.info(f"Typesense not ready yet, attempt {retry_count}/{max_retries}: {e}")
            time.sleep(2)

    logger.error("Typesense not ready after maximum retries")
    return None

def create_collection(client):
    """Create the news collection with appropriate schema."""
    try:
        # Try to get the collection first
        try:
            existing = client.collections[COLLECTION_NAME].retrieve()
            logger.info(f"Collection '{COLLECTION_NAME}' already exists")

            # Check if we should recreate it (for schema updates)
            # For now, we'll keep the existing collection
            return True

        except typesense.exceptions.ObjectNotFound:
            logger.info(f"Collection '{COLLECTION_NAME}' not found, creating new one")

        # Define the schema (excluding tags to avoid array handling complexity)
        schema = {
            'name': COLLECTION_NAME,
            'fields': [
                {'name': 'unique_id', 'type': 'string', 'facet': True, 'sort': True},
                {'name': 'agency', 'type': 'string', 'facet': True, 'optional': True},
                {'name': 'published_at', 'type': 'int64', 'facet': False},  # Unix timestamp - required for sorting
                {'name': 'title', 'type': 'string', 'facet': False, 'optional': True},
                {'name': 'url', 'type': 'string', 'facet': False, 'optional': True},
                {'name': 'image', 'type': 'string', 'facet': False, 'optional': True},
                {'name': 'category', 'type': 'string', 'facet': True, 'optional': True},
                {'name': 'content', 'type': 'string', 'facet': False, 'optional': True},
                {'name': 'extracted_at', 'type': 'int64', 'facet': False, 'optional': True},
                {'name': 'theme_1_level_1', 'type': 'string', 'facet': True, 'optional': True},
                {'name': 'published_year', 'type': 'int32', 'facet': True, 'optional': True},
                {'name': 'published_month', 'type': 'int32', 'facet': True, 'optional': True},
                {'name': 'published_week', 'type': 'int32', 'facet': True, 'optional': True, 'index': True},
            ],
            'default_sorting_field': 'published_at'
        }

        client.collections.create(schema)
        logger.info("Collection created successfully with search-optimized schema")
        return True

    except Exception as e:
        logger.error(f"Error creating collection: {e}")
        raise

def calculate_published_week(timestamp):
    """
    Calculate ISO 8601 week in format YYYYWW from Unix timestamp.

    Args:
        timestamp: Unix timestamp in seconds

    Returns:
        int in format YYYYWW (e.g., 202543 for week 43 of 2025)
        Returns None if timestamp is invalid

    Examples:
        >>> calculate_published_week(1704110400)  # 2024-01-01
        202401  # Week 1 of 2024

        >>> calculate_published_week(1729641600)  # 2025-10-23
        202543  # Week 43 of 2025
    """
    if pd.isna(timestamp) or timestamp <= 0:
        return None

    try:
        dt = pd.to_datetime(timestamp, unit='s')
        iso_year, iso_week, _ = dt.isocalendar()
        return iso_year * 100 + iso_week
    except Exception:
        return None


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

        # Extract year and month for faceting
        df['published_year'] = df['published_at'].dt.year
        df['published_month'] = df['published_at'].dt.month

        # Convert datetime to Unix timestamp (seconds) for Typesense
        df['published_at_ts'] = df['published_at'].astype('int64') // 10**9
        df['extracted_at_ts'] = df['extracted_at'].astype('int64') // 10**9

        # Calculate ISO 8601 week (YYYYWW format) for temporal analysis
        logger.info("Calculating ISO 8601 weeks for temporal optimization...")
        df['published_week'] = df['published_at_ts'].apply(calculate_published_week)

        # Log some statistics
        valid_weeks = df['published_week'].notna().sum()
        logger.info(f"Published week calculated for {valid_weeks}/{len(df)} records")

        # Tags field removed to simplify processing

        logger.info("Dataset processed successfully")
        return df

    except Exception as e:
        logger.error(f"Error downloading/processing dataset: {e}")
        raise

def prepare_document(row: pd.Series) -> Dict[str, Any]:
    """Prepare a document for Typesense indexing."""
    doc = {
        'unique_id': str(row['unique_id']) if pd.notna(row['unique_id']) else f"doc_{row.name}",
        # published_at is required (default sorting field), use 0 if not available
        'published_at': int(row['published_at_ts']) if pd.notna(row.get('published_at_ts')) and row['published_at_ts'] > 0 else 0
    }

    # Add optional fields only if they have valid values
    if pd.notna(row.get('agency')):
        val = str(row['agency']).strip()
        if val:
            doc['agency'] = val

    if pd.notna(row.get('title')):
        val = str(row['title']).strip()
        if val:
            doc['title'] = val

    if pd.notna(row.get('url')):
        val = str(row['url']).strip()
        if val:
            doc['url'] = val

    if pd.notna(row.get('image')):
        val = str(row['image']).strip()
        if val:
            doc['image'] = val

    if pd.notna(row.get('category')):
        val = str(row['category']).strip()
        if val:
            doc['category'] = val

    # Tags field removed to avoid array handling complexity

    if pd.notna(row.get('content')):
        val = str(row['content']).strip()
        if val:
            doc['content'] = val

    if pd.notna(row.get('extracted_at_ts')) and row['extracted_at_ts'] > 0:
        doc['extracted_at'] = int(row['extracted_at_ts'])

    if pd.notna(row.get('theme_1_level_1')):
        val = str(row['theme_1_level_1']).strip()
        if val:
            doc['theme_1_level_1'] = val

    if pd.notna(row.get('published_year')) and row['published_year'] > 0:
        doc['published_year'] = int(row['published_year'])

    if pd.notna(row.get('published_month')) and row['published_month'] > 0:
        doc['published_month'] = int(row['published_month'])

    if pd.notna(row.get('published_week')) and row['published_week'] > 0:
        doc['published_week'] = int(row['published_week'])

    return doc

def index_documents_to_typesense(client, df: pd.DataFrame):
    """Index the DataFrame documents into Typesense."""
    try:
        logger.info("Indexing documents into Typesense...")

        # Check if collection already has documents
        collection_info = client.collections[COLLECTION_NAME].retrieve()
        existing_count = collection_info.get('num_documents', 0)

        if existing_count > 0:
            logger.info(f"Collection already contains {existing_count} documents")
            logger.info("Skipping indexing to avoid duplicates. Use 'refresh' command to update.")
            return

        # Prepare documents
        documents = []
        for idx, row in df.iterrows():
            try:
                doc = prepare_document(row)
                documents.append(doc)

                # Index in batches of 1000
                if len(documents) >= 1000:
                    logger.info(f"Indexing batch of {len(documents)} documents... (total processed: {idx + 1})")
                    result = client.collections[COLLECTION_NAME].documents.import_(documents, {'action': 'upsert'})

                    # Check for errors
                    errors = [item for item in result if not item.get('success')]
                    if errors:
                        logger.warning(f"Encountered {len(errors)} errors in batch")
                        for error in errors[:5]:  # Log first 5 errors
                            logger.warning(f"Error: {error}")

                    documents = []

            except Exception as e:
                logger.warning(f"Error preparing document at index {idx}: {e}")
                continue

        # Index remaining documents
        if documents:
            logger.info(f"Indexing final batch of {len(documents)} documents...")
            result = client.collections[COLLECTION_NAME].documents.import_(documents, {'action': 'upsert'})

            errors = [item for item in result if not item.get('success')]
            if errors:
                logger.warning(f"Encountered {len(errors)} errors in final batch")

        # Get final statistics
        collection_info = client.collections[COLLECTION_NAME].retrieve()
        total_docs = collection_info.get('num_documents', 0)

        logger.info(f"Successfully indexed documents into Typesense")
        logger.info(f"Total documents in collection: {total_docs}")

        # Get some statistics
        logger.info("Collection statistics:")
        logger.info(f"  Total news records: {total_docs}")
        logger.info(f"  Collection name: {COLLECTION_NAME}")
        logger.info(f"  Schema fields: {len(collection_info['fields'])}")

    except Exception as e:
        logger.error(f"Error indexing documents: {e}")
        raise

def run_test_queries(client):
    """Run some test queries to verify functionality."""
    try:
        logger.info("Running test queries to verify functionality...")

        # Test 1: Get collection info
        collection_info = client.collections[COLLECTION_NAME].retrieve()
        logger.info(f"✅ Collection has {collection_info['num_documents']} documents")

        # Test 2: Simple search query
        search_params = {
            'q': 'saúde',
            'query_by': 'title,content',
            'limit': 3
        }
        results = client.collections[COLLECTION_NAME].documents.search(search_params)
        logger.info(f"✅ Search query returned {results['found']} results for 'saúde'")

        # Test 3: Faceted search by agency
        search_params = {
            'q': '*',
            'query_by': 'title',
            'facet_by': 'agency',
            'max_facet_values': 5,
            'limit': 0
        }
        results = client.collections[COLLECTION_NAME].documents.search(search_params)
        if results.get('facet_counts'):
            logger.info("✅ Top agencies by document count:")
            for facet in results['facet_counts'][0]['counts'][:5]:
                logger.info(f"   {facet['value']}: {facet['count']} documents")

    except Exception as e:
        logger.warning(f"Test queries encountered an issue: {e}")

def main():
    """Main function to orchestrate the Typesense initialization."""
    try:
        logger.info("Starting GovBR News Typesense initialization...")

        # Wait for Typesense to be ready
        client = wait_for_typesense()
        if not client:
            logger.error("Could not connect to Typesense")
            sys.exit(1)

        # Create collection
        create_collection(client)

        # Download and process dataset
        df = download_and_process_dataset()

        # Index documents into Typesense
        index_documents_to_typesense(client, df)

        # Run test queries
        run_test_queries(client)

        logger.info("Typesense initialization completed successfully!")

    except Exception as e:
        logger.error(f"Typesense initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
