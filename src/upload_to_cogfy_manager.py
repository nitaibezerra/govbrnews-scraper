from datetime import datetime, time, date, timezone, timedelta
import logging
import os
from time import sleep
import numpy
import random
from typing import Optional, Union, Set

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

    def _setup_collection_fields(self, features: dict) -> tuple:
        """
        Sets up the collection fields and returns the field ID and type mappings.

        Args:
            features: The dataset features dictionary

        Returns:
            tuple: (field_id_map, cogfy_type_map) where:
                - field_id_map: Mapping of field names to their IDs
                - cogfy_type_map: Mapping of field names to their Cogfy types
        """
        field_mapping = {
            field_name: self._map_hf_type_to_cogfy_type(field_type.dtype)
            for field_name, field_type in features.items()
        }

        logging.info("Ensuring fields exist in Cogfy collection...")
        self.collection_manager.ensure_fields(field_mapping)

        fields = self.collection_manager.list_columns()
        field_id_map = {field.name: field.id for field in fields}
        # Use actual Cogfy types instead of mapped HuggingFace types
        cogfy_type_map = {field.name: field.type for field in fields}

        return field_id_map, cogfy_type_map

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

        # Check for timestamp with timezone (e.g., "timestamp[us, tz=pytz.FixedOffset(-180)]")
        if "timestamp[" in hf_type:
            return "date"

        return type_mapping.get(hf_type, "text")

    # Fields to exclude from upload (legacy/deprecated fields)
    EXCLUDED_FIELDS = {
        'published_at_old',      # Legacy field from migration
        'published_datetime',    # Legacy field, replaced by published_at
    }

    def _create_record_properties(self, row: pd.Series, field_id_map: dict, field_mapping: dict) -> dict:
        """
        Creates the properties dictionary for a record.

        Args:
            row: The pandas Series containing the record data
            field_id_map: Mapping of field names to their IDs
            field_mapping: Mapping of field names to their Cogfy types

        Returns:
            dict: The properties dictionary for the record
        """
        properties = {}

        for field_name, field_id in field_id_map.items():
            # Skip excluded/legacy fields
            if field_name in self.EXCLUDED_FIELDS:
                continue

            # Skip fields that don't exist in the row data
            if field_name not in row.index:
                continue

            value = row.get(field_name)

            if value is None or (isinstance(value, str) and value == "") or (isinstance(value, numpy.ndarray) and value.size == 0):
                continue

            # Skip NaT (Not a Time) values for datetime fields (but not for arrays)
            if not isinstance(value, numpy.ndarray):
                try:
                    if pd.isna(value):
                        continue
                except (ValueError, TypeError):
                    pass  # Value is not NA-checkable, proceed

            cogfy_type = field_mapping.get(field_name, "text")

            if cogfy_type == "text":
                properties[field_id] = {
                    "type": "text",
                    "text": {"value": str(value)}
                }
            elif cogfy_type == "date":
                if isinstance(value, pd.Timestamp):
                    # Convert to UTC before formatting with Z suffix
                    if value.tzinfo is not None:
                        value_utc = value.tz_convert('UTC')
                    else:
                        value_utc = value
                    value = value_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                elif isinstance(value, date):
                    value = datetime.combine(value, time(hour=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
                properties[field_id] = {
                    "type": "date",
                    "date": {"value": value}
                }

        return properties

    def _create_record_with_retry(self, properties: dict, max_retries: int = 3) -> bool:
        """
        Attempts to create a record with exponential backoff retry.

        Args:
            properties: The record properties
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            bool: True if successful, False if all retries failed
        """
        base_delay = 1.0  # 1 second initial delay
        max_delay = 60    # cap delay at 60 seconds

        # Exceptions that should NOT be retried (permanent errors)
        NON_RETRYABLE_ERRORS = (
            ValueError,           # Data validation errors
            KeyError,            # Missing fields
            TypeError,           # Wrong data type
        )

        for attempt in range(max_retries + 1):
            try:
                self.collection_manager.create_record(properties)
                if attempt > 0:
                    logging.info(f"Successfully created record after {attempt + 1} attempts")
                return True

            except NON_RETRYABLE_ERRORS as e:
                # Permanent errors: do not retry
                logging.error(f"Non-retryable error creating record: {str(e)}")
                return False

            except Exception as e:
                # Potentially transient errors
                error_msg = str(e)

                # Check for authentication/permission errors (also should not retry)
                if any(keyword in error_msg.lower() for keyword in ['unauthorized', 'forbidden', 'authentication', 'permission']):
                    logging.error(f"Authentication/permission error: {error_msg}")
                    return False

                # 400 Bad Request indicates schema/type mismatch - fatal error, do not retry
                if "400" in error_msg and "bad request" in error_msg.lower():
                    logging.error(f"Bad Request error (schema mismatch): {error_msg}")
                    raise Exception(f"Fatal schema error: {error_msg}")

                if attempt < max_retries:
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    delay += random.uniform(0, 0.5)  # add jitter

                    logging.warning(
                        f"Failed to create record (attempt {attempt + 1}/{max_retries + 1}): {error_msg}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    sleep(delay)
                else:
                    # All retries exhausted - log and continue
                    logging.error(
                        f"Failed to create record after {max_retries + 1} attempts: {error_msg}. "
                        f"Skipping record and continuing..."
                    )
                    return False

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

    def _build_day_filter(self, date_str: str, published_at_field_id: str) -> dict:
        """Build filter to cover an entire day using published_at field."""
        return {
            "type": "and",
            "and": {
                "filters": [
                    {
                        "type": "greaterThanOrEquals",
                        "greaterThanOrEquals": {
                            "fieldId": published_at_field_id,
                            "value": f"{date_str}T00:00:00"
                        }
                    },
                    {
                        "type": "lessThanOrEquals",
                        "lessThanOrEquals": {
                            "fieldId": published_at_field_id,
                            "value": f"{date_str}T23:59:59"
                        }
                    }
                ]
            }
        }

    def _extract_unique_id_from_record(self, record: dict) -> Optional[str]:
        """Extract unique_id value from a Cogfy record."""
        if not self._unique_id_field_id:
            return None

        properties = record.get("properties", {})
        unique_property = properties.get(self._unique_id_field_id)
        if not unique_property:
            return None

        text_data = unique_property.get("text", {})
        return text_data.get("value")

    def _fetch_existing_ids_for_day(
        self,
        day: pd.Timestamp,
        published_at_field_id: Optional[str],
        max_retries: int = 2
    ) -> Set[str]:
        """
        Fetch existing unique_ids from Cogfy for a specific day with retry logic.

        Args:
            day: The day to fetch records for
            published_at_field_id: Field ID for published_at
            max_retries: Maximum number of retry attempts (default: 2)

        Returns:
            Set[str]: Set of existing unique_ids (empty set on persistent failure)
        """
        if published_at_field_id is None:
            return set()

        date_str = day.strftime("%Y-%m-%d")
        filter_criteria = self._build_day_filter(date_str, published_at_field_id)
        order_by = [
            {
                "fieldId": published_at_field_id,
                "direction": "asc"
            }
        ]

        base_delay = 2.0  # 2 seconds initial delay

        for attempt in range(max_retries + 1):
            try:
                result = self.collection_manager.query_records(
                    filter=filter_criteria,
                    order_by=order_by,
                    page_number=0,
                    page_size=1000
                )

                # Success - process results
                existing_ids: Set[str] = set()
                for record in result.get("data", []):
                    unique_value = self._extract_unique_id_from_record(record)
                    if unique_value:
                        existing_ids.add(unique_value)

                logging.info(
                    f"Prefetch for {date_str}: retrieved {len(result.get('data', []))} records, "
                    f"cached {len(existing_ids)} unique_id(s)"
                )

                return existing_ids

            except Exception as e:
                error_msg = str(e)
                is_timeout = any(code in error_msg for code in ["504", "502", "timeout", "Gateway"])

                if attempt < max_retries and is_timeout:
                    # Retry only for timeouts/gateway errors
                    delay = base_delay * (2 ** attempt)
                    logging.warning(
                        f"Timeout fetching day {date_str} (attempt {attempt + 1}/{max_retries + 1}): "
                        f"{error_msg}. Retrying in {delay:.1f}s..."
                    )
                    sleep(delay)
                else:
                    # Permanent failure or last attempt
                    if is_timeout:
                        logging.error(f"Server timeout for day {date_str} after {attempt + 1} attempts: {error_msg}")
                    else:
                        logging.error(f"Error prefetching day {date_str}: {error_msg}")

                    logging.warning(f"Proceeding without prefetch for {date_str} - may re-upload existing records")
                    return set()

        return set()

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

        # Brasília timezone (UTC-3)
        brasilia_tz = timezone(timedelta(hours=-3))

        if start_date:
            if isinstance(start_date, str):
                start_date = pd.to_datetime(start_date)
            # Make start_date timezone-aware if it's naive
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=brasilia_tz)
            df = df[df['published_at'] >= start_date]

        if end_date:
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
            # Make end_date timezone-aware if it's naive
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=brasilia_tz)
            df = df[df['published_at'] <= end_date]

        if df.empty:
            logging.warning("No records found matching the specified filters")
            return

        # Setup collection fields and get actual Cogfy types
        field_id_map, cogfy_type_map = self._setup_collection_fields(features)
        self._unique_id_field_id = self._get_unique_id_field_id(field_id_map)

        # Use actual Cogfy types instead of HuggingFace mapped types
        field_mapping = cogfy_type_map

        # Get published_at field ID for querying
        published_at_field_id = field_id_map.get('published_at')
        if published_at_field_id is None:
            logging.warning("'published_at' field not found in Cogfy collection. Prefetch skipped.")

        # Group records by day and process day by day
        df['published_date'] = df['published_at'].dt.normalize()
        unique_days = sorted(df['published_date'].unique())

        total_rows = len(df)
        logging.info(f"Starting migration of {total_rows} records across {len(unique_days)} day(s)...")

        total_created = 0
        total_skipped = 0
        total_failed = 0

        for day_index, day in enumerate(unique_days, 1):
            date_str = day.strftime("%Y-%m-%d")
            logging.info(f"Processing day {day_index}/{len(unique_days)}: {date_str}")

            # Fetch existing IDs for this specific day
            existing_ids_for_day: Set[str] = set()
            if published_at_field_id is not None:
                existing_ids_for_day = self._fetch_existing_ids_for_day(day, published_at_field_id)

            # Get records for this day
            day_df = df[df['published_date'] == day]
            logging.info(f"Found {len(day_df)} record(s) to process for {date_str}")

            # Process records for this day
            day_created = 0
            day_skipped = 0
            day_failed = 0

            for _, row in day_df.iterrows():
                unique_id = row.get('unique_id')
                if not unique_id:
                    logging.warning("Skipping row without unique_id")
                    continue

                if unique_id in existing_ids_for_day:
                    logging.info(f"Skipping existing record. Unique ID: {unique_id}")
                    day_skipped += 1
                    continue

                properties = self._create_record_properties(row, field_id_map, field_mapping)
                if self._create_record_with_retry(properties):
                    logging.info(f"Created record. Agency: {row['agency']} | Unique ID: {unique_id}")
                    existing_ids_for_day.add(unique_id)
                    day_created += 1
                else:
                    logging.error(f"Failed to create record after retries. Unique ID: {unique_id}")
                    day_failed += 1

                sleep(1)

            total_created += day_created
            total_skipped += day_skipped
            total_failed += day_failed

            logging.info(
                f"Day {date_str} completed: {day_created} created, {day_skipped} skipped, "
                f"{day_failed} failed"
            )

        logging.info(
            f"Migration completed! Total: {total_created} created, {total_skipped} skipped, "
            f"{total_failed} failed"
        )

        # Clean up temporary column
        df.drop(columns=['published_date'], inplace=True)

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
