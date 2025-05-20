from collections.abc import Sequence
from datetime import datetime, time, date
import logging
import os
from time import sleep
import numpy

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

def migrate_dataset_to_cogfy():
    """
    Migrates the GovBR News dataset from HuggingFace to Cogfy.
    """
    # Initialize DatasetManager to load data from HuggingFace
    dataset_manager = DatasetManager()

    # Load the dataset
    dataset = dataset_manager._load_existing_dataset()
    if dataset is None:
        logging.error("Failed to load dataset from HuggingFace")
        return

    # Convert to pandas DataFrame
    df = dataset.to_pandas()

    # sort by published_at asc
    df = df.sort_values(by="published_at", ascending=True)
    # Initialize Cogfy client and collection manager
    api_key = os.getenv("COGFY_API_KEY")
    if not api_key:
        logging.error("COGFY_API_KEY environment variable is not set")
        return

    client = CogfyClient(api_key, base_url="https://public-api.serpro.cogfy.com/")
    collection_manager = CollectionManager(client, "noticiasgovbr-all-news")

    # Get dataset features and create field mapping
    features = dataset.features
    field_mapping = {}

    for field_name, field_type in features.items():
        cogfy_type = map_hf_type_to_cogfy_type(field_type.dtype)
        field_mapping[field_name] = cogfy_type

    # Ensure all fields exist in the collection
    logging.info("Ensuring fields exist in Cogfy collection...")
    collection_manager.ensure_fields(field_mapping)

    # Get all fields from the collection
    fields = collection_manager.list_columns()
    field_id_map = {field.name: field.id for field in fields}

    # Process each row and create records
    total_rows = len(df)
    logging.info(f"Starting migration of {total_rows} records...")

    for index, row in df.iterrows():
        # Create properties dictionary for the record
        properties = {}

        for field_name, field_id in field_id_map.items():
            value = row.get(field_name)

            # Skip None values
            if (isinstance(value, numpy.ndarray) and value.size == 0) or pd.isna(value):
                continue

            # Handle different field types
            if field_mapping[field_name] == "text":
                properties[field_id] = {
                    "type": "text",
                    "text": {"value": str(value)}
                }
            elif field_mapping[field_name] == "date":
                # Convert to ISO format if it's a datetime
                if isinstance(value, pd.Timestamp):
                    # For Timestamp, ensure we have time component
                    value = value.strftime("%Y-%m-%dT%H:%M:%SZ")
                elif isinstance(value, date):
                    # For date objects without time, use noon UTC
                    value = datetime.combine(value, time(hour=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
                properties[field_id] = {
                    "type": "date",
                    "date": {"value": value}
                }

        # Create the record
        collection_manager.create_record(properties)
        logging.info(f"Created record {index + 1}/{total_rows}. Agency: "
                     f"{row['agency']} | Published at: {row['published_at']}")

        # Sleep to avoid overwhelming the API
        sleep(0.3)
        return

    logging.info("Migration completed!")

if __name__ == "__main__":
    migrate_dataset_to_cogfy()