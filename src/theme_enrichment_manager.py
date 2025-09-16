import os
import logging
import argparse
from datetime import datetime
from typing import Dict, Optional, Union, Tuple
from time import sleep

import pandas as pd
from dotenv import load_dotenv
from retry import retry
import requests

try:
    from .cogfy_manager import CogfyClient, CollectionManager
    from .dataset_manager import DatasetManager
except ImportError:
    from cogfy_manager import CogfyClient, CollectionManager
    from dataset_manager import DatasetManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables
load_dotenv()


class ThemeEnrichmentManager:
    """
    Manager class for enriching HuggingFace dataset with theme_1_level_1 data from Cogfy.

    This class handles the process of:
    1. Loading the HuggingFace dataset
    2. Querying Cogfy for theme data one record at a time
    3. Mapping theme IDs to human-readable labels
    4. Updating the dataset with enriched theme information
    5. Pushing the updated dataset back to HuggingFace
    """

    def __init__(self, server_url: str = "https://api.cogfy.com/", collection_name: str = "noticiasgovbr-all-news"):
        """
        Initialize the ThemeEnrichmentManager.

        Args:
            server_url: Cogfy server URL
            collection_name: Name of the Cogfy collection containing news data
        """
        self.server_url = server_url
        self.collection_name = collection_name
        self.dataset_manager = DatasetManager()
        self.cogfy_client = None
        self.collection_manager = None
        self._field_map = None
        self._theme_options = None
        self._unique_id_field_id = None
        self._theme_field_id = None

        self._initialize_cogfy_interface()

    def _initialize_cogfy_interface(self) -> None:
        """Initialize Cogfy client and collection manager."""
        api_key = os.getenv("COGFY_API_KEY")
        if not api_key:
            raise ValueError("COGFY_API_KEY environment variable is not set")

        self.cogfy_client = CogfyClient(api_key, base_url=self.server_url)
        self.collection_manager = CollectionManager(self.cogfy_client, self.collection_name)

        logging.info(f"Initialized Cogfy interface for collection: {self.collection_name}")

    def _setup_cogfy_mappings(self) -> None:
        """
        Setup field mappings and theme options for ID→label conversion.

        This method must be called before any theme enrichment operations.
        """
        # Get field ID mappings
        fields = self.collection_manager.list_columns()
        self._field_map = {field.name: field.id for field in fields}

        # Validate required fields exist
        if "unique_id" not in self._field_map:
            raise ValueError("Required field 'unique_id' not found in Cogfy collection")
        if "theme_1_level_1" not in self._field_map:
            raise ValueError("Required field 'theme_1_level_1' not found in Cogfy collection")

        self._unique_id_field_id = self._field_map["unique_id"]
        self._theme_field_id = self._field_map["theme_1_level_1"]

        # Get theme options for ID→label mapping
        theme_field = next(
            (f for f in fields if f.type == "select" and f.name == "theme_1_level_1"),
            None
        )

        if not theme_field or not theme_field.data:
            raise ValueError("Theme field 'theme_1_level_1' is not properly configured as a select field")

        self._theme_options = theme_field.data.get("select", {}).get("options", [])
        logging.info(f"Loaded {len(self._theme_options)} theme options for mapping")

    def _extract_theme_id_from_record(self, record: Dict) -> Optional[str]:
        """
        Extract theme ID from a Cogfy record.

        Args:
            record: Cogfy record with properties

        Returns:
            Theme ID string or None if not found
        """
        theme_property = record["properties"].get(self._theme_field_id)
        if not theme_property or not theme_property.get("select", {}).get("value"):
            return None

        theme_values = theme_property["select"]["value"]
        if not theme_values or len(theme_values) == 0:
            return None

        return theme_values[0]["id"]

    def _map_theme_id_to_label(self, theme_id: Optional[str]) -> Optional[str]:
        """
        Map a theme ID to its human-readable label.

        Args:
            theme_id: Internal theme ID from Cogfy

        Returns:
            Human-readable theme label or None if not found
        """
        if not theme_id or not self._theme_options:
            return None

        return next(
            (opt["label"] for opt in self._theme_options if opt["id"] == theme_id),
            None
        )

    @retry(
        exceptions=(requests.exceptions.RequestException, requests.exceptions.HTTPError),
        tries=5,
        delay=2,
        backoff=2,
        jitter=(1, 3)
    )
    def _query_cogfy_single(self, unique_id: str) -> Optional[Dict]:
        """
        Query Cogfy for a single record by unique_id.

        Args:
            unique_id: Unique ID to query for

        Returns:
            Single record dict or None if not found
        """
        if not unique_id:
            return None

        # Build filter for single unique_id (following news_grouper.py pattern)
        filter_criteria = {
            "filter": {
                "type": "equals",
                "equals": {
                    "fieldId": self._unique_id_field_id,
                    "value": unique_id
                }
            }
        }

        try:
            result = self.collection_manager.query_records(
                filter=filter_criteria.get("filter"),
                page_number=0,
                page_size=1
            )

            records = result.get("data", [])
            if records:
                return records[0]
            return None

        except Exception as e:
            error_msg = str(e)
            if "504" in error_msg or "502" in error_msg or "Gateway" in error_msg:
                logging.warning(f"Cogfy server timeout/gateway error for {unique_id}: {error_msg}")
            elif "400" in error_msg:
                logging.warning(f"Cogfy bad request for {unique_id}: {error_msg}")
            else:
                logging.error(f"Error querying Cogfy for unique_id {unique_id}: {error_msg}")
            return None

    def _get_theme_for_unique_id(self, unique_id: str) -> Optional[str]:
        """
        Get theme label for a single unique ID from Cogfy.

        Args:
            unique_id: Unique ID to get theme for

        Returns:
            Theme label string or None if not found
        """
        if not unique_id:
            return None

        try:
            record = self._query_cogfy_single(unique_id)
            if not record:
                logging.debug(f"No record found for unique_id: {unique_id}")
                return None

            # Extract and map theme
            theme_id = self._extract_theme_id_from_record(record)
            theme_label = self._map_theme_id_to_label(theme_id)

            if theme_label:
                logging.debug(f"Mapped {unique_id} -> {theme_label}")
            else:
                logging.debug(f"No theme found for unique_id: {unique_id}")

            return theme_label

        except Exception as e:
            error_msg = str(e)
            if "504" in error_msg or "502" in error_msg or "Gateway" in error_msg:
                logging.debug(f"Cogfy server timeout/gateway error for {unique_id}: {error_msg}")
            else:
                logging.error(f"Error getting theme for unique_id {unique_id}: {error_msg}")
            return None

    def _load_and_filter_dataset(
        self,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None
    ) -> pd.DataFrame:
        """
        Load dataset from HuggingFace and apply date filtering if specified.

        Args:
            start_date: Start date for filtering records (inclusive)
            end_date: End date for filtering records (inclusive)

        Returns:
            Filtered pandas DataFrame
        """
        logging.info("Loading HuggingFace dataset...")
        dataset = self.dataset_manager._load_existing_dataset()
        if dataset is None:
            raise ValueError("Failed to load dataset from HuggingFace")

        df = dataset.to_pandas()
        original_count = len(df)
        logging.info(f"Loaded dataset with {original_count} records")

        # Apply date filtering if specified
        if start_date or end_date:
            df['published_at'] = pd.to_datetime(df['published_at'], errors='coerce')
            df = df.dropna(subset=['published_at'])

            if start_date:
                if isinstance(start_date, str):
                    start_date = pd.to_datetime(start_date)
                df = df[df['published_at'] >= start_date]

            if end_date:
                if isinstance(end_date, str):
                    end_date = pd.to_datetime(end_date)
                df = df[df['published_at'] <= end_date]

            logging.info(f"Filtered to {len(df)} records in date range")

        return df

    def _prepare_dataset_for_enrichment(self, df: pd.DataFrame, force_update: bool = False) -> pd.DataFrame:
        """
        Prepare dataset for theme enrichment by adding columns and filtering records.

        Args:
            df: Input DataFrame
            force_update: If True, process all records; if False, only process missing themes

        Returns:
            DataFrame with records that need processing
        """
        # Add theme_1_level_1 column if it doesn't exist
        if 'theme_1_level_1' not in df.columns:
            df['theme_1_level_1'] = None

        # Filter records that need processing
        if force_update:
            records_to_process = df[df['unique_id'].notna()].copy()
            logging.info(f"Force update enabled: processing all {len(records_to_process)} records")
        else:
            records_to_process = df[(df['unique_id'].notna()) & (df['theme_1_level_1'].isna())].copy()
            logging.info(f"Processing {len(records_to_process)} records without existing themes")

        return records_to_process

    def _process_records_for_themes(self, df: pd.DataFrame, records_to_process: pd.DataFrame) -> Tuple[int, int]:
        """
        Process records one by one to get theme information from Cogfy.

        Args:
            df: Full DataFrame to update
            records_to_process: Records that need theme enrichment

        Returns:
            Tuple of (successful_updates, failed_updates)
        """
        successful_updates = 0
        failed_updates = 0

        for idx, row in records_to_process.iterrows():
            unique_id = row['unique_id']

            try:
                theme_label = self._get_theme_for_unique_id(unique_id)

                if theme_label:
                    df.at[idx, 'theme_1_level_1'] = theme_label
                    successful_updates += 1

                    if successful_updates % 10 == 0:
                        logging.info(f"Processed {successful_updates} records...")
                else:
                    failed_updates += 1

                # Longer delay to help with server stability
                sleep(1.0)

            except Exception as e:
                logging.error(f"Error processing record {unique_id}: {str(e)}")
                failed_updates += 1
                continue

        return successful_updates, failed_updates

    def _report_enrichment_statistics(self, df: pd.DataFrame, successful_updates: int, failed_updates: int) -> None:
        """
        Report statistics about the enrichment process.

        Args:
            df: DataFrame with enriched data
            successful_updates: Number of successful theme updates
            failed_updates: Number of failed theme updates
        """
        total_enriched = df['theme_1_level_1'].notna().sum()
        total_missing = df['theme_1_level_1'].isna().sum()

        logging.info("Enrichment completed:")
        logging.info(f"  - Successfully updated: {successful_updates} records")
        logging.info(f"  - Failed updates: {failed_updates} records")
        logging.info(f"  - Total enriched in dataset: {total_enriched} records")
        logging.info(f"  - Total missing themes: {total_missing} records")
        logging.info(f"  - Overall enrichment rate: {total_enriched/len(df)*100:.1f}%")
        
        if failed_updates > 0:
            logging.info("Note: Failed updates are often due to Cogfy server instability (502/504 errors)")
            logging.info("Consider retrying during off-peak hours for better success rates")

    def _merge_with_full_dataset(
        self,
        df: pd.DataFrame,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None
    ) -> pd.DataFrame:
        """
        Merge enriched data with the full dataset if filtering was applied.

        Args:
            df: Enriched DataFrame
            start_date: Start date used for filtering
            end_date: End date used for filtering

        Returns:
            Final DataFrame ready for upload
        """
        if start_date or end_date:
            # We filtered the dataset, so we need to update only the filtered records
            # Load the full dataset again and update only the records we processed
            full_dataset = self.dataset_manager._load_existing_dataset()
            full_df = full_dataset.to_pandas()

            # Add theme_1_level_1 column if it doesn't exist
            if 'theme_1_level_1' not in full_df.columns:
                full_df['theme_1_level_1'] = None

            # Update only the records that were processed - use the enriched df
            update_mask = full_df['unique_id'].isin(df['unique_id'])
            full_df.loc[update_mask, 'theme_1_level_1'] = df.set_index('unique_id')['theme_1_level_1']

            return full_df
        else:
            # We processed the entire dataset
            return df

    def _upload_enriched_dataset(self, df: pd.DataFrame) -> None:
        """
        Convert DataFrame back to dataset and upload to HuggingFace.

        Args:
            df: Final enriched DataFrame
        """
        logging.info("Updating HuggingFace dataset...")
        from datasets import Dataset
        updated_dataset = Dataset.from_pandas(df, preserve_index=False)

        # Use the dataset manager's update method
        self.dataset_manager._push_dataset_and_csvs(updated_dataset)

    def enrich_dataset_with_themes(
        self,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        force_update: bool = False
    ) -> None:
        """
        Main method to enrich the HuggingFace dataset with theme information from Cogfy.

        Args:
            start_date: Start date for filtering records (inclusive)
            end_date: End date for filtering records (inclusive)
            force_update: If True, update even records that already have theme_1_level_1
        """
        logging.info("Starting theme enrichment process...")

        # Setup Cogfy mappings
        self._setup_cogfy_mappings()

        # Load and filter dataset
        df = self._load_and_filter_dataset(start_date, end_date)

        if df.empty:
            logging.warning("No records found matching the specified criteria")
            return

        # Prepare dataset for enrichment
        records_to_process = self._prepare_dataset_for_enrichment(df, force_update)

        if records_to_process.empty:
            logging.info("No records need theme enrichment")
            return

        # Process records for themes
        successful_updates, failed_updates = self._process_records_for_themes(df, records_to_process)

        # Report statistics
        self._report_enrichment_statistics(df, successful_updates, failed_updates)

        # Merge with full dataset if needed
        final_df = self._merge_with_full_dataset(df, start_date, end_date)

        # Upload enriched dataset
        self._upload_enriched_dataset(final_df)

        logging.info("Theme enrichment completed successfully!")


def main():
    """Main entry point for the theme enrichment script."""
    parser = argparse.ArgumentParser(
        description='Enrich HuggingFace dataset with theme_1_level_1 data from Cogfy'
    )
    parser.add_argument(
        '--start-date',
        help='Start date for filtering records (YYYY-MM-DD format)'
    )
    parser.add_argument(
        '--end-date',
        help='End date for filtering records (YYYY-MM-DD format)'
    )
    parser.add_argument(
        '--collection',
        default="noticiasgovbr-all-news",
        help='Cogfy collection name (default: noticiasgovbr-all-news)'
    )
    parser.add_argument(
        '--server-url',
        default="https://api.cogfy.com/",
        help='Cogfy server URL (default: https://api.cogfy.com/)'
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Force update existing theme values (default: skip records that already have themes)'
    )

    args = parser.parse_args()

    try:
        enrichment_manager = ThemeEnrichmentManager(
            server_url=args.server_url,
            collection_name=args.collection
        )

        enrichment_manager.enrich_dataset_with_themes(
            start_date=args.start_date,
            end_date=args.end_date,
            force_update=args.force
        )

    except Exception as e:
        logging.error(f"Error during theme enrichment: {str(e)}")
        raise


if __name__ == "__main__":
    main()
