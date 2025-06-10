from datetime import datetime, time, date
import logging
import os
from time import sleep
import numpy
import random
from typing import Optional, Union

import pandas as pd
from dotenv import load_dotenv

from cogfy_manager import CogfyClient, CollectionManager
from dataset_manager import DatasetManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables
load_dotenv()

class UploadToCogfyManager:
    def __init__(self, server_url: str, collection_name: str):
        """
        Initialize the UploadToCogfyManager.

        Args:
            collection_name: Name of the Cogfy collection to upload to
        """
        self.collection_name = collection_name
        self.client = None
        self.collection_manager = None
        self._initialize_cogfy_interface(server_url)
        self._unique_id_field_id = None

    def _initialize_cogfy_interface(self, server_url: str) -> None:
        """Initialize the Cogfy client and collection manager."""
        api_key = os.getenv("COGFY_API_KEY")
        if not api_key:
            raise ValueError("COGFY_API_KEY environment variable is not set")

        self.client = CogfyClient(api_key, base_url=server_url)
        self.collection_manager = CollectionManager(self.client, self.collection_name)

    def _load_and_prepare_dataset(self) -> tuple[pd.DataFrame, dict]:
        """
        Loads the dataset from HuggingFace and prepares it for migration.

        Returns:
            tuple: (pd.DataFrame, dict) The prepared dataset and its features
        """
        dataset_manager = DatasetManager()
        dataset = dataset_manager._load_existing_dataset()

        if dataset is None:
            raise ValueError("Failed to load dataset from HuggingFace")

        df = dataset.to_pandas()
        return df.sort_values(by="published_at", ascending=True), dataset.features

    def _setup_collection_fields(self, features: dict) -> dict:
        """
        Sets up the collection fields and returns the field ID mapping.

        Args:
            features: The dataset features dictionary

        Returns:
            dict: Mapping of field names to their IDs
        """
        field_mapping = {
            field_name: self._map_hf_type_to_cogfy_type(field_type.dtype)
            for field_name, field_type in features.items()
        }

        logging.info("Ensuring fields exist in Cogfy collection...")
        self.collection_manager.ensure_fields(field_mapping)

        fields = self.collection_manager.list_columns()
        return {field.name: field.id for field in fields}

    def _map_hf_type_to_cogfy_type(self, hf_type: str) -> str:
        """
        Maps HuggingFace dataset field types to Cogfy field types.

        Args:
            hf_type: The HuggingFace field type

        Returns:
            str: The corresponding Cogfy field type
        """
        type_mapping = {
            "string": "text",
            "date32": "date",
            "timestamp[us]": "date",
            "timestamp[ns]": "date",
            "list": "text"  # For tags, we'll store as comma-separated text
        }
        return type_mapping.get(hf_type, "text")

    def _create_record_properties(self, row: pd.Series, field_id_map: dict, field_mapping: dict) -> dict:
        """
        Creates the properties dictionary for a record.

        Args:
            row: The pandas Series containing the record data
            field_id_map: Mapping of field names to their IDs
            field_mapping: Mapping of field names to their types

        Returns:
            dict: The properties dictionary for the record
        """
        properties = {}

        for field_name, field_id in field_id_map.items():
            value = row.get(field_name)

            if value is None or (isinstance(value, str) and value == "") or (isinstance(value, numpy.ndarray) and value.size == 0):
                continue

            if field_mapping[field_name] == "text":
                properties[field_id] = {
                    "type": "text",
                    "text": {"value": str(value)}
                }
            elif field_mapping[field_name] == "date":
                if isinstance(value, pd.Timestamp):
                    value = value.strftime("%Y-%m-%dT%H:%M:%SZ")
                elif isinstance(value, date):
                    value = datetime.combine(value, time(hour=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
                properties[field_id] = {
                    "type": "date",
                    "date": {"value": value}
                }

        return properties

    def _create_record_with_retry(self, properties: dict, max_retries: int = 20) -> bool:
        """
        Attempts to create a record with exponential backoff retry, capped at 10 minutes.

        Args:
            properties: The record properties
            max_retries: Maximum number of retry attempts

        Returns:
            bool: True if successful, False if all retries failed
        """
        base_delay = 0.15  # initial delay in seconds
        max_delay = 600    # cap delay at 10 minutes (600 seconds)

        for attempt in range(max_retries):
            try:
                self.collection_manager.create_record(properties)
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"Failed to create record after {max_retries} attempts: {str(e)}")
                    return False

                # Calculate exponential delay and cap it at max_delay
                delay = min(base_delay * (2 ** attempt), max_delay)
                # Add jitter to avoid thundering herd problem
                delay += random.uniform(0, 0.1)

                sleep(delay)
        return False

    def _get_unique_id_field_id(self, field_id_map: dict) -> str:
        """
        Get the field ID for the unique_id field.

        Args:
            field_id_map: Mapping of field names to their IDs

        Returns:
            str: The field ID for unique_id
        """
        for field_name, field_id in field_id_map.items():
            if field_name == 'unique_id':
                return field_id
        raise ValueError("unique_id field not found in collection")

    def _record_exists(self, unique_id: str) -> bool:
        """
        Check if a record with the given unique_id already exists.

        Args:
            unique_id: The unique identifier to check

        Returns:
            bool: True if record exists, False otherwise
        """
        filter_criteria = {
            "type": "and",
            "and": {
                "filters": [
                    {
                        "type": "equals",
                        "equals": {
                            "fieldId": self._unique_id_field_id,
                            "value": unique_id
                        }
                    }
                ]
            }
        }

        try:
            result = self.collection_manager.query_records(
                filter=filter_criteria,
                page_size=1
            )
            return result["totalSize"] > 0
        except Exception as e:
            logging.error(f"Error checking for existing record: {str(e)}")
            raise e

    def upload(self,
              agency: Optional[str] = None,
              start_date: Optional[Union[str, datetime]] = None,
              end_date: Optional[Union[str, datetime]] = None) -> None:
        """
        Upload records to Cogfy with optional filtering.

        Args:
            agency: Filter by agency name
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
        """
        # Load and prepare dataset
        df, features = self._load_and_prepare_dataset()

        # Apply filters
        if agency:
            df = df[df['agency'] == agency]

        # Convert published_at to datetime if it's not already
        df['published_at'] = pd.to_datetime(df['published_at'], errors='coerce')

        # Drop rows where published_at conversion failed
        df = df.dropna(subset=['published_at'])

        if start_date:
            if isinstance(start_date, str):
                start_date = pd.to_datetime(start_date)
            df = df[df['published_at'] >= start_date]

        if end_date:
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
            df = df[df['published_at'] <= end_date]

        if df.empty:
            logging.warning("No records found matching the specified filters")
            return

        # Setup collection fields
        field_id_map = self._setup_collection_fields(features)
        self._unique_id_field_id = self._get_unique_id_field_id(field_id_map)

        field_mapping = {
            field_name: self._map_hf_type_to_cogfy_type(field_type.dtype)
            for field_name, field_type in features.items()
        }

        # Process records
        total_rows = len(df)
        logging.info(f"Starting migration of {total_rows} records...")

        skipped = 0
        for index, row in df.iterrows():
            # Check if record already exists
            if self._record_exists(row['unique_id']):
                published_at = row['published_at'].strftime("%Y-%m-%d")
                logging.info(f"Skipping existing record published at: {published_at} "
                             f"Unique ID: {row['unique_id']}")
                skipped += 1
                continue

            properties = self._create_record_properties(row, field_id_map, field_mapping)
            if self._create_record_with_retry(properties):
                logging.info(f"Created record. Agency: {row['agency']} | "
                             f"Published at: {published_at}")
            else:
                logging.error(f"Failed to create record. Unique ID: {row['unique_id']}")

            sleep(0.15)

        logging.info(f"Migration completed! Created {total_rows - skipped} "
                     f"records, skipped {skipped} existing records.")

def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(description='Upload GovBR News dataset to Cogfy')
    parser.add_argument('--agency', help='Filter by agency name')
    parser.add_argument('--start-date', help='Filter by start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='Filter by end date (YYYY-MM-DD)')
    parser.add_argument('--collection', default="noticiasgovbr-all-news",
                       help='Cogfy collection name (default: noticiasgovbr-all-news)')
    parser.add_argument('--server-url', default="https://api.cogfy.com/",
                       help='Cogfy server URL (default: https://api.cogfy.com/)')

    args = parser.parse_args()

    try:
        uploader = UploadToCogfyManager(server_url=args.server_url, collection_name=args.collection)
        uploader.upload(
            agency=args.agency,
            start_date=args.start_date,
            end_date=args.end_date
        )
    except Exception as e:
        logging.error(f"Error during upload: {str(e)}")
        raise

if __name__ == "__main__":
    main()