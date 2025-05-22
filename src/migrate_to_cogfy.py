from datetime import datetime, time, date
import logging
import os
from time import sleep
import numpy
import random

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

def map_hf_type_to_cogfy_type(hf_type: str) -> str:
    """
    Maps HuggingFace dataset field types to Cogfy field types.

    Args:
        hf_type: The HuggingFace field type

    Returns:
        The corresponding Cogfy field type
    """
    type_mapping = {
        "string": "text",
        "date32": "date",
        "timestamp[us]": "date",
        "timestamp[ns]": "date",
        "list": "text"  # For tags, we'll store as comma-separated text
    }
    return type_mapping.get(hf_type, "text")  # Default to text if type not found

def load_and_prepare_dataset() -> tuple[pd.DataFrame, dict]:
    """
    Loads the dataset from HuggingFace and prepares it for migration.

    Returns:
        tuple: (pd.DataFrame, dict) The prepared dataset and its features
    """
    dataset_manager = DatasetManager()
    dataset = dataset_manager._load_existing_dataset()

    if dataset is None:
        logging.error("Failed to load dataset from HuggingFace")
        return None, None

    df = dataset.to_pandas()
    return df.sort_values(by="published_at", ascending=True), dataset.features

def initialize_cogfy_interface() -> CollectionManager:
    """
    Initializes the Cogfy client and collection manager.

    Returns:
        CollectionManager: The Cogfy collection manager
    """
    api_key = os.getenv("COGFY_API_KEY")
    if not api_key:
        raise ValueError("COGFY_API_KEY environment variable is not set")

    client = CogfyClient(api_key, base_url="https://public-api.serpro.cogfy.com/")
    collection_manager = CollectionManager(client, "noticiasgovbr-all-news")
    return collection_manager

def setup_collection_fields(dataset_features: dict, collection_manager: CollectionManager) -> dict:
    """
    Sets up the collection fields and returns the field ID mapping.

    Args:
        dataset_features: The dataset features dictionary
        collection_manager: The Cogfy collection manager

    Returns:
        dict: Mapping of field names to their IDs
    """
    field_mapping = {
        field_name: map_hf_type_to_cogfy_type(field_type.dtype)
        for field_name, field_type in dataset_features.items()
    }

    logging.info("Ensuring fields exist in Cogfy collection...")
    collection_manager.ensure_fields(field_mapping)

    fields = collection_manager.list_columns()
    return {field.name: field.id for field in fields}

def create_record_properties(row: pd.Series, field_id_map: dict, field_mapping: dict) -> dict:
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

def create_record_with_retry(collection_manager: CollectionManager, properties: dict, max_retries: int = 20) -> bool:
    """
    Attempts to create a record with exponential backoff retry, capped at 10 minutes.

    Args:
        collection_manager: The Cogfy collection manager
        properties: The record properties
        max_retries: Maximum number of retry attempts

    Returns:
        bool: True if successful, False if all retries failed
    """
    base_delay = 0.15  # initial delay in seconds
    max_delay = 600    # cap delay at 10 minutes (600 seconds)

    for attempt in range(max_retries):
        try:
            collection_manager.create_record(properties)
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

def migrate_dataset_to_cogfy():
    """
    Migrates the GovBR News dataset from HuggingFace to Cogfy.
    """
    # Load and prepare dataset
    df, features = load_and_prepare_dataset()

    # Initialize Cogfy client
    collection_manager = initialize_cogfy_interface()

    # Setup collection fields
    field_id_map = setup_collection_fields(features, collection_manager)
    field_mapping = {
        field_name: map_hf_type_to_cogfy_type(field_type.dtype)
        for field_name, field_type in features.items()
    }

    # Process records
    total_rows = len(df)
    logging.info(f"Starting migration of {total_rows} records...")

    for index, row in df.iterrows():
        properties = create_record_properties(row, field_id_map, field_mapping)
        if create_record_with_retry(collection_manager, properties):
            logging.info(f"Created record {index + 1}/{total_rows}. Agency: "
                        f"{row['agency']} | Published at: {row['published_at']}")
        else:
            logging.error(f"Failed to create record {index + 1}/{total_rows}")

        sleep(0.15)
    logging.info("Migration completed!")

if __name__ == "__main__":
    migrate_dataset_to_cogfy()