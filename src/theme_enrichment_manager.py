import os
import logging
import argparse
from datetime import datetime
from typing import Dict, Optional, Union, Tuple, List
from time import time

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
        if "published_at" not in self._field_map:
            raise ValueError("Required field 'published_at' not found in Cogfy collection")

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
        if not theme_property or not theme_property["select"]["value"]:
            return None

        return theme_property["select"]["value"][0]["id"]

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
    def _query_cogfy_bulk(self, start_date: Optional[Union[str, datetime]] = None, end_date: Optional[Union[str, datetime]] = None) -> List[Dict]:
        """
        Query Cogfy for all records in a date range using bulk query.

        Args:
            start_date: Start date for filtering records (inclusive)
            end_date: End date for filtering records (inclusive)

        Returns:
            List of records from Cogfy
        """
        # Build date filter criteria
        filters = []

        # Add date range filters if specified
        if start_date or end_date:
            # Get the published_at field ID from the field map
            if "published_at" not in self._field_map:
                raise ValueError("Required field 'published_at' not found in Cogfy collection")

            published_at_field_id = self._field_map["published_at"]

            if start_date:
                if isinstance(start_date, str):
                    start_date = pd.to_datetime(start_date)
                start_date_str = start_date.strftime("%Y-%m-%d")
                filters.append({
                    "type": "greaterThanOrEquals",
                    "greaterThanOrEquals": {
                        "fieldId": published_at_field_id,
                        "value": start_date_str
                    }
                })

            if end_date:
                if isinstance(end_date, str):
                    end_date = pd.to_datetime(end_date)
                end_date_str = end_date.strftime("%Y-%m-%d")
                filters.append({
                    "type": "lessThanOrEquals",
                    "lessThanOrEquals": {
                        "fieldId": published_at_field_id,
                        "value": end_date_str
                    }
                })

        # Build the complete filter
        if filters:
            filter_criteria = {
                "type": "and",
                "and": {
                    "filters": filters
                }
            }
        else:
            filter_criteria = None

        all_records = []
        page_number = 0
        page_size = 100  # Reduced page size for better visibility

        try:
            while True:
                result = self.collection_manager.query_records(
                    filter=filter_criteria,
                    page_number=page_number,
                    page_size=page_size
                )

                records = result.get("data", [])
                total_size = result.get("totalSize", 0)
                current_page = result.get("pageNumber", page_number)
                current_page_size = result.get("pageSize", page_size)

                if not records:
                    logging.info(f"Page {page_number + 1}: No more records found")
                    break

                all_records.extend(records)

                # Show detailed page information
                logging.info(f"Page {page_number + 1}: Retrieved {len(records)} records")
                logging.info(f"  - Page number: {current_page}")
                logging.info(f"  - Page size: {current_page_size}")
                logging.info(f"  - Total size: {total_size}")
                logging.info(f"  - Cumulative records: {len(all_records)}")
                logging.info(f"  - Progress: {len(all_records)}/{total_size} ({len(all_records)/total_size*100:.1f}%)")

                # Check if we've reached the end
                if len(all_records) >= total_size:
                    logging.info(f"Reached end of results (total: {total_size})")
                    break

                page_number += 1

            logging.info(f"Bulk query completed: {len(all_records)} total records retrieved across {page_number + 1} pages")
            return all_records

        except Exception as e:
            error_msg = str(e)
            if "504" in error_msg or "502" in error_msg or "Gateway" in error_msg:
                logging.warning(f"Cogfy server timeout/gateway error during bulk query: {error_msg}")
            elif "400" in error_msg:
                logging.warning(f"Cogfy bad request during bulk query: {error_msg}")
            else:
                logging.error(f"Error during bulk query: {error_msg}")
            return []

    def _process_bulk_cogfy_results(self, cogfy_records: List[Dict], df: pd.DataFrame, force_update: bool = False) -> Tuple[int, int]:
        """
        Process bulk Cogfy results and update the DataFrame with theme information.

        Args:
            cogfy_records: List of records from Cogfy bulk query
            df: DataFrame to update
            force_update: If True, update even records that already have theme_1_level_1

        Returns:
            Tuple of (successful_updates, failed_updates)
        """
        successful_updates = 0
        failed_updates = 0

        # Create a mapping from unique_id to theme for efficient lookup
        cogfy_theme_map = {}

        for record in cogfy_records:
            try:
                # Extract unique_id from the record
                unique_id_property = record["properties"].get(self._unique_id_field_id)
                if not unique_id_property or not unique_id_property.get("text", {}).get("value"):
                    continue

                unique_id = unique_id_property["text"]["value"]

                # Extract theme information
                theme_id = self._extract_theme_id_from_record(record)
                theme_label = self._map_theme_id_to_label(theme_id)

                if theme_label:
                    cogfy_theme_map[unique_id] = theme_label

            except Exception as e:
                logging.debug(f"Error processing Cogfy record: {str(e)}")
                continue

        logging.info(f"Created theme mapping for {len(cogfy_theme_map)} records from Cogfy")

        # Now update the DataFrame with the theme information
        for idx, row in df.iterrows():
            unique_id = row['unique_id']

            if not unique_id:
                continue

            # Check if we should update this record
            if not force_update and pd.notna(row.get('theme_1_level_1')):
                continue  # Skip records that already have themes

            # Look up theme in our mapping
            if unique_id in cogfy_theme_map:
                theme_label = cogfy_theme_map[unique_id]
                df.at[idx, 'theme_1_level_1'] = theme_label
                successful_updates += 1

                if successful_updates % 100 == 0:
                    logging.info(f"Updated {successful_updates} records with themes...")
            else:
                failed_updates += 1

        return successful_updates, failed_updates

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

            # Update only the records that were processed - use safe individual updates
            # Create a mapping from unique_id to theme for safe updates
            theme_updates = df.dropna(subset=['theme_1_level_1']).set_index('unique_id')['theme_1_level_1'].to_dict()

            # Apply updates one by one with validation
            updates_applied = 0
            for unique_id, theme in theme_updates.items():
                mask = full_df['unique_id'] == unique_id
                if mask.any():
                    full_df.loc[mask, 'theme_1_level_1'] = theme
                    updates_applied += 1

            logging.info(f"Applied {updates_applied} theme updates to full dataset (out of {len(theme_updates)} available)")

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



        # Use bulk query approach for much better performance
        logging.info(f"Starting bulk theme enrichment for {len(records_to_process)} records...")
        start_time = time()

        # Query Cogfy for all records in the date range
        logging.info("Querying Cogfy for all records in date range...")
        cogfy_records = self._query_cogfy_bulk(start_date, end_date)

        if not cogfy_records:
            logging.warning("No records found in Cogfy for the specified date range")
            return

        # Process the bulk results and update the dataset
        logging.info(f"Processing {len(cogfy_records)} records from Cogfy...")
        successful_updates, failed_updates = self._process_bulk_cogfy_results(cogfy_records, df, force_update)

        total_time = time() - start_time

        if successful_updates > 0:
            avg_time_per_record = total_time / successful_updates
            records_per_min = (successful_updates / total_time) * 60 if total_time > 0 else 0
            logging.info(f"Bulk processing completed in {total_time:.1f}s - Average: {avg_time_per_record:.1f}s per record ({records_per_min:.1f} records/min)")

        # Report final statistics
        self._report_enrichment_statistics(df, successful_updates, failed_updates)

        # Upload the enriched dataset
        if successful_updates > 0:
            logging.info("Uploading enriched dataset to HuggingFace...")
            final_df = self._merge_with_full_dataset(df, start_date, end_date)
            self._upload_enriched_dataset(final_df)
            logging.info("Dataset uploaded successfully")

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
