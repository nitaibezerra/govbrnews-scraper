import os
import logging
import argparse
from datetime import datetime
from typing import Dict, Optional, Union, Tuple, List
from time import time, sleep

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


class EnrichmentManager:
    """
    Manager class for enriching HuggingFace dataset with AI-generated data from Cogfy.

    This class handles the process of:
    1. Loading the HuggingFace dataset
    2. Querying Cogfy for enrichment data (themes L1/L2/L3 and summary from AI inference)
    3. Determining the most specific theme available
    4. Updating the dataset with enriched information
    5. Pushing the updated dataset back to HuggingFace
    """

    def __init__(self, server_url: str = "https://api.cogfy.com/", collection_name: str = "noticiasgovbr-all-news"):
        """
        Initialize the EnrichmentManager.

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
        self._theme_1_level_1_options = None
        self._unique_id_field_id = None
        self._theme_1_level_1_field_id = None
        self._theme_1_level_2_field_id = None
        self._theme_1_level_3_field_id = None
        self._summary_field_id = None

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
        self._theme_1_level_1_field_id = self._field_map["theme_1_level_1"]

        # Check if theme_1_level_2 exists (text field)
        if "theme_1_level_2" in self._field_map:
            self._theme_1_level_2_field_id = self._field_map["theme_1_level_2"]
            logging.info("Found theme_1_level_2 field in Cogfy collection (text field)")
        else:
            logging.warning("theme_1_level_2 field not found in Cogfy collection")

        # Check if theme_1_level_3 exists (text field)
        if "theme_1_level_3" in self._field_map:
            self._theme_1_level_3_field_id = self._field_map["theme_1_level_3"]
            logging.info("Found theme_1_level_3 field in Cogfy collection (text field)")
        else:
            logging.warning("theme_1_level_3 field not found in Cogfy collection")

        # Check if summary exists (text field - AI-generated)
        if "summary" in self._field_map:
            self._summary_field_id = self._field_map["summary"]
            logging.info("Found summary field in Cogfy collection (text field - AI-generated)")
        else:
            logging.warning("summary field not found in Cogfy collection")

        # Get theme_1_level_1 options for ID→label mapping (select field)
        theme_1_level_1_field = next(
            (f for f in fields if f.type == "select" and f.name == "theme_1_level_1"),
            None
        )

        if not theme_1_level_1_field or not theme_1_level_1_field.data:
            raise ValueError("Theme field 'theme_1_level_1' is not properly configured as a select field")

        self._theme_1_level_1_options = theme_1_level_1_field.data.get("select", {}).get("options", [])
        logging.info(f"Loaded {len(self._theme_1_level_1_options)} theme_1_level_1 options for mapping")

    def _extract_theme_from_record(self, record: Dict, field_id: str) -> Optional[str]:
        """
        Extract theme ID from a Cogfy record (for select fields like level 1).

        Args:
            record: Cogfy record with properties
            field_id: Field ID to extract from

        Returns:
            Theme ID string or None if not found
        """
        theme_property = record["properties"].get(field_id)
        if not theme_property or not theme_property.get("select", {}).get("value"):
            return None

        values = theme_property["select"]["value"]
        if not values or len(values) == 0:
            return None

        return values[0]["id"]

    def _extract_text_from_record(self, record: Dict, field_id: str) -> Optional[str]:
        """
        Extract text value from a Cogfy record (for text fields like level 2 and 3).

        Args:
            record: Cogfy record with properties
            field_id: Field ID to extract from

        Returns:
            Text value string or None if not found
        """
        text_property = record["properties"].get(field_id)
        if not text_property or not text_property.get("text", {}).get("value"):
            return None

        return text_property["text"]["value"]

    def _map_theme_id_to_label(self, theme_id: Optional[str], options: List[Dict]) -> Optional[str]:
        """
        Map a theme ID to its human-readable label.

        Args:
            theme_id: Internal theme ID from Cogfy
            options: List of theme options to search in

        Returns:
            Human-readable theme label or None if not found
        """
        if not theme_id or not options:
            return None

        return next(
            (opt["label"] for opt in options if opt["id"] == theme_id),
            None
        )

    def _build_single_day_filters(self, target_date: Union[str, datetime]) -> List[Dict]:
        """
        Build date filter criteria for a single day.

        Args:
            target_date: Date to filter for (inclusive)

        Returns:
            List of filter dictionaries for the specific day
        """
        if "published_at" not in self._field_map:
            raise ValueError("Required field 'published_at' not found in Cogfy collection")

        published_at_field_id = self._field_map["published_at"]

        if isinstance(target_date, str):
            target_date = pd.to_datetime(target_date)

        date_str = target_date.strftime("%Y-%m-%d")

        # Create filters for the entire day (00:00:00 to 23:59:59)
        filters = [
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

        return filters

    def _generate_date_range(self, start_date: Union[str, datetime], end_date: Union[str, datetime]) -> List[datetime]:
        """
        Generate a list of dates between start_date and end_date (inclusive).

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of datetime objects for each day in the range
        """
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)

        # Generate date range
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        return date_range.tolist()

    def _build_filter_criteria(self, filters: List[Dict]) -> Optional[Dict]:
        """
        Build complete filter criteria for Cogfy query.

        Args:
            filters: List of individual filter dictionaries

        Returns:
            Complete filter criteria or None if no filters
        """
        if filters:
            return {
                "type": "and",
                "and": {
                    "filters": filters
                }
            }
        return None

    def _query_single_day(self, target_date: Union[str, datetime]) -> List[Dict]:
        """
        Query Cogfy for all records on a single day.

        Args:
            target_date: Date to query for

        Returns:
            List of records from Cogfy for that day

        Raises:
            Exception: If the query fails for any reason
        """
        filters = self._build_single_day_filters(target_date)
        filter_criteria = self._build_filter_criteria(filters)

        date_str = target_date.strftime("%Y-%m-%d") if isinstance(target_date, datetime) else target_date

        try:
            result = self.collection_manager.query_records(
                filter=filter_criteria,
                page_number=0,
                page_size=1000  # Use larger page size for single day
            )

            records = result.get("data", [])
            total_size = result.get("totalSize", 0)

            logging.info(f"Day {date_str}: Retrieved {len(records)} records (total available: {total_size})")

            return records

        except Exception as e:
            error_msg = str(e)
            if "504" in error_msg or "502" in error_msg or "Gateway" in error_msg:
                logging.error(f"Cogfy server timeout/gateway error for day {date_str}: {error_msg}")
                raise Exception(f"Server timeout/gateway error for day {date_str}: {error_msg}")
            elif "400" in error_msg:
                logging.error(f"Cogfy bad request for day {date_str}: {error_msg}")
                raise Exception(f"Bad request for day {date_str}: {error_msg}")
            else:
                logging.error(f"Error querying Cogfy for day {date_str}: {error_msg}")
                raise Exception(f"Query failed for day {date_str}: {error_msg}")

    @retry(
        exceptions=(requests.exceptions.RequestException, requests.exceptions.HTTPError),
        tries=5,
        delay=2,
        backoff=2,
        jitter=(1, 3)
    )
    def _query_cogfy_bulk(self, start_date: Optional[Union[str, datetime]] = None, end_date: Optional[Union[str, datetime]] = None) -> List[Dict]:
        """
        Query Cogfy for all records in a date range using day-by-day queries.

        Args:
            start_date: Start date for filtering records (inclusive)
            end_date: End date for filtering records (inclusive)

        Returns:
            List of records from Cogfy
        """
        if not start_date or not end_date:
            logging.warning("Both start_date and end_date are required for day-by-day queries")
            return []

        # Generate list of dates to query
        date_range = self._generate_date_range(start_date, end_date)
        logging.info(f"Querying {len(date_range)} days from {start_date} to {end_date}")

        all_records = []
        successful_days = 0
        failed_days = 0

        for i, target_date in enumerate(date_range, 1):
            date_str = target_date.strftime("%Y-%m-%d")
            logging.info(f"Processing day {i}/{len(date_range)}: {date_str}")

            try:
                day_records = self._query_single_day(target_date)
                all_records.extend(day_records)
                successful_days += 1

                logging.info(f"Day {date_str} completed: {len(day_records)} records (cumulative: {len(all_records)})")

                # Add a small delay between requests to be gentle on the server
                if i < len(date_range):  # Don't sleep after the last request
                    sleep(0.5)

            except Exception as e:
                logging.error(f"Failed to query day {date_str}: {str(e)}")
                logging.error(f"Stopping processing due to failure. Processed {successful_days}/{len(date_range)} days successfully.")
                raise Exception(f"Day-by-day query failed on day {date_str} ({i}/{len(date_range)}): {str(e)}")

        logging.info(f"Day-by-day query completed successfully:")
        logging.info(f"  - Total days processed: {len(date_range)}")
        logging.info(f"  - Successful days: {successful_days}")
        logging.info(f"  - Failed days: 0")
        logging.info(f"  - Total records retrieved: {len(all_records)}")

        return all_records

    def _extract_unique_id_from_record(self, record: Dict) -> Optional[str]:
        """
        Extract unique_id from a Cogfy record.

        Args:
            record: Cogfy record with properties

        Returns:
            Unique ID string or None if not found
        """
        unique_id_property = record["properties"].get(self._unique_id_field_id)
        if not unique_id_property or not unique_id_property.get("text", {}).get("value"):
            return None
        return unique_id_property["text"]["value"]

    def _create_theme_mapping(self, cogfy_records: List[Dict]) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Create a mapping from unique_id to theme data from Cogfy records.

        Args:
            cogfy_records: List of records from Cogfy bulk query

        Returns:
            Dictionary mapping unique_id to dict with all 3 levels (level 1, 2, and 3)
        """
        cogfy_theme_map = {}

        for record in cogfy_records:
            try:
                unique_id = self._extract_unique_id_from_record(record)
                if not unique_id:
                    continue

                # Extract level 1 (select field with ID mapping)
                theme_1_level_1_id = self._extract_theme_from_record(record, self._theme_1_level_1_field_id)
                theme_1_level_1_label = self._map_theme_id_to_label(theme_1_level_1_id, self._theme_1_level_1_options)

                # Extract level 2 (text field - direct label) if available
                theme_1_level_2_label = None
                if self._theme_1_level_2_field_id:
                    theme_1_level_2_label = self._extract_text_from_record(record, self._theme_1_level_2_field_id)

                # Extract level 3 (text field - direct label) if available
                theme_1_level_3_label = None
                if self._theme_1_level_3_field_id:
                    theme_1_level_3_label = self._extract_text_from_record(record, self._theme_1_level_3_field_id)

                # Extract summary (text field - AI-generated) if available
                summary = None
                if self._summary_field_id:
                    summary = self._extract_text_from_record(record, self._summary_field_id)

                cogfy_theme_map[unique_id] = {
                    "theme_1_level_1": theme_1_level_1_label,
                    "theme_1_level_2": theme_1_level_2_label,
                    "theme_1_level_3": theme_1_level_3_label,
                    "summary": summary
                }

            except Exception as e:
                logging.debug(f"Error processing Cogfy record: {str(e)}")
                continue

        logging.info(f"Created theme mapping for {len(cogfy_theme_map)} records from Cogfy")
        return cogfy_theme_map

    def _split_theme_code_and_label(self, theme_full: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Split a theme string into code and label parts.

        Args:
            theme_full: Full theme string (e.g., "01.01 - Política Econômica")

        Returns:
            Tuple of (code, label) or (None, None) if parsing fails
        """
        if not theme_full or ' - ' not in theme_full:
            return None, None

        parts = theme_full.split(' - ', 1)
        return parts[0].strip(), parts[1].strip()

    def _update_dataframe_with_themes(self, df: pd.DataFrame, cogfy_theme_map: Dict[str, Dict], force_update: bool = False) -> Tuple[int, int]:
        """
        Update DataFrame with theme information from Cogfy mapping.

        Args:
            df: DataFrame to update
            cogfy_theme_map: Mapping from unique_id to theme data
            force_update: If True, update even records that already have themes

        Returns:
            Tuple of (successful_updates, failed_updates)
        """
        successful_updates = 0
        failed_updates = 0

        # Ensure all enrichment columns exist (themes + summary)
        enrichment_columns = [
            'theme_1_level_1', 'theme_1_level_1_code', 'theme_1_level_1_label',
            'theme_1_level_2_code', 'theme_1_level_2_label',
            'theme_1_level_3_code', 'theme_1_level_3_label',
            'most_specific_theme_code', 'most_specific_theme_label',
            'summary'
        ]
        for col in enrichment_columns:
            if col not in df.columns:
                df[col] = None

        for idx, row in df.iterrows():
            unique_id = row['unique_id']

            if not unique_id:
                continue

            # Check if we should update this record
            if not force_update and pd.notna(row.get('theme_1_level_1')):
                continue  # Skip records that already have themes

            # Look up theme in our mapping
            if unique_id in cogfy_theme_map:
                theme_data = cogfy_theme_map[unique_id]

                # Level 1 (always from Cogfy)
                theme_1_level_1 = theme_data.get("theme_1_level_1")
                level_1_code, level_1_label = None, None
                if theme_1_level_1:
                    df.at[idx, 'theme_1_level_1'] = theme_1_level_1
                    level_1_code, level_1_label = self._split_theme_code_and_label(theme_1_level_1)
                    df.at[idx, 'theme_1_level_1_code'] = level_1_code
                    df.at[idx, 'theme_1_level_1_label'] = level_1_label

                # Level 2 (from Cogfy AI inference)
                theme_1_level_2 = theme_data.get("theme_1_level_2")
                level_2_code, level_2_label = None, None
                if theme_1_level_2:
                    level_2_code, level_2_label = self._split_theme_code_and_label(theme_1_level_2)
                    df.at[idx, 'theme_1_level_2_code'] = level_2_code
                    df.at[idx, 'theme_1_level_2_label'] = level_2_label

                # Level 3 (from Cogfy AI inference)
                theme_1_level_3 = theme_data.get("theme_1_level_3")
                level_3_code, level_3_label = None, None
                if theme_1_level_3:
                    level_3_code, level_3_label = self._split_theme_code_and_label(theme_1_level_3)
                    df.at[idx, 'theme_1_level_3_code'] = level_3_code
                    df.at[idx, 'theme_1_level_3_label'] = level_3_label

                # Determine most specific theme (priority: L3 > L2 > L1)
                if level_3_code:
                    df.at[idx, 'most_specific_theme_code'] = level_3_code
                    df.at[idx, 'most_specific_theme_label'] = level_3_label
                elif level_2_code:
                    df.at[idx, 'most_specific_theme_code'] = level_2_code
                    df.at[idx, 'most_specific_theme_label'] = level_2_label
                elif level_1_code:
                    df.at[idx, 'most_specific_theme_code'] = level_1_code
                    df.at[idx, 'most_specific_theme_label'] = level_1_label

                # Summary (AI-generated from Cogfy)
                summary = theme_data.get("summary")
                if summary:
                    df.at[idx, 'summary'] = summary

                successful_updates += 1

                if successful_updates % 100 == 0:
                    logging.info(f"Updated {successful_updates} records with themes...")
            else:
                failed_updates += 1

        return successful_updates, failed_updates

    def _process_bulk_cogfy_results(self, cogfy_records: List[Dict], df: pd.DataFrame, force_update: bool = False) -> Tuple[int, int]:
        """
        Process bulk Cogfy results and update the DataFrame with theme information.

        Args:
            cogfy_records: List of records from Cogfy bulk query
            df: DataFrame to update
            force_update: If True, update even records that already have themes

        Returns:
            Tuple of (successful_updates, failed_updates)
        """
        # Create theme mapping from Cogfy records
        cogfy_theme_map = self._create_theme_mapping(cogfy_records)

        # Update DataFrame with themes
        return self._update_dataframe_with_themes(df, cogfy_theme_map, force_update)

    def _load_dataset_from_huggingface(self) -> pd.DataFrame:
        """
        Load dataset from HuggingFace.

        Returns:
            pandas DataFrame from HuggingFace dataset
        """
        logging.info("Loading HuggingFace dataset...")
        dataset = self.dataset_manager._load_existing_dataset()
        if dataset is None:
            raise ValueError("Failed to load dataset from HuggingFace")

        df = dataset.to_pandas()
        logging.info(f"Loaded dataset with {len(df)} records")
        return df

    def _apply_date_filtering(self, df: pd.DataFrame, start_date: Optional[Union[str, datetime]] = None, end_date: Optional[Union[str, datetime]] = None) -> pd.DataFrame:
        """
        Apply date filtering to DataFrame.

        Args:
            df: Input DataFrame
            start_date: Start date for filtering records (inclusive)
            end_date: End date for filtering records (inclusive)

        Returns:
            Filtered DataFrame
        """
        if not (start_date or end_date):
            return df

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
        df = self._load_dataset_from_huggingface()
        return self._apply_date_filtering(df, start_date, end_date)

    def _prepare_dataset_for_enrichment(self, df: pd.DataFrame, force_update: bool = False) -> pd.DataFrame:
        """
        Prepare dataset for theme enrichment by adding columns and filtering records.

        Args:
            df: Input DataFrame
            force_update: If True, process all records; if False, only process missing themes

        Returns:
            DataFrame with records that need processing
        """
        # Add enrichment columns if they don't exist (themes + summary)
        enrichment_columns = [
            'theme_1_level_1', 'theme_1_level_1_code', 'theme_1_level_1_label',
            'theme_1_level_2_code', 'theme_1_level_2_label',
            'theme_1_level_3_code', 'theme_1_level_3_label',
            'most_specific_theme_code', 'most_specific_theme_label',
            'summary'
        ]
        for col in enrichment_columns:
            if col not in df.columns:
                df[col] = None

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
        total_level_2 = df['theme_1_level_2_code'].notna().sum()
        total_level_3 = df['theme_1_level_3_code'].notna().sum()
        total_with_summary = df['summary'].notna().sum()

        logging.info("Enrichment completed:")
        logging.info(f"  - Successfully updated: {successful_updates} records")
        logging.info(f"  - Failed updates: {failed_updates} records")
        logging.info(f"  - Total enriched in dataset: {total_enriched} records")
        logging.info(f"  - Total with level 2: {total_level_2} records ({total_level_2/len(df)*100:.1f}%)")
        logging.info(f"  - Total with level 3: {total_level_3} records ({total_level_3/len(df)*100:.1f}%)")
        logging.info(f"  - Total with summary: {total_with_summary} records ({total_with_summary/len(df)*100:.1f}%)")
        logging.info(f"  - Total missing themes: {total_missing} records")
        logging.info(f"  - Overall enrichment rate: {total_enriched/len(df)*100:.1f}%")

        if failed_updates > 0:
            logging.info("Note: Failed updates are often due to Cogfy server instability (502/504 errors)")
            logging.info("Consider retrying during off-peak hours for better success rates")

    def _load_full_dataset(self) -> pd.DataFrame:
        """
        Load the full dataset from HuggingFace.

        Returns:
            Full pandas DataFrame
        """
        full_dataset = self.dataset_manager._load_existing_dataset()
        return full_dataset.to_pandas()

    def _ensure_theme_columns_exist(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure all enrichment columns exist in DataFrame (themes + summary).

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with enrichment columns added if needed
        """
        enrichment_columns = [
            'theme_1_level_1', 'theme_1_level_1_code', 'theme_1_level_1_label',
            'theme_1_level_2_code', 'theme_1_level_2_label',
            'theme_1_level_3_code', 'theme_1_level_3_label',
            'most_specific_theme_code', 'most_specific_theme_label',
            'summary'
        ]
        for col in enrichment_columns:
            if col not in df.columns:
                df[col] = None
        return df

    def _apply_theme_updates_to_full_dataset(self, full_df: pd.DataFrame, enriched_df: pd.DataFrame) -> int:
        """
        Apply enrichment updates from enriched DataFrame to full dataset (themes + summary).

        Args:
            full_df: Full dataset DataFrame
            enriched_df: Enriched DataFrame with updates

        Returns:
            Number of updates applied
        """
        # Get all enrichment columns (themes + summary)
        enrichment_columns = [
            'theme_1_level_1', 'theme_1_level_1_code', 'theme_1_level_1_label',
            'theme_1_level_2_code', 'theme_1_level_2_label',
            'theme_1_level_3_code', 'theme_1_level_3_label',
            'most_specific_theme_code', 'most_specific_theme_label',
            'summary'
        ]

        # Create a mapping from unique_id to enrichment data
        enriched_with_themes = enriched_df[enriched_df['theme_1_level_1'].notna()].copy()
        enrichment_updates = enriched_with_themes.set_index('unique_id')[enrichment_columns].to_dict('index')

        # Apply updates one by one with validation
        updates_applied = 0
        for unique_id, enrichment_data in enrichment_updates.items():
            mask = full_df['unique_id'] == unique_id
            if mask.any():
                for col in enrichment_columns:
                    full_df.loc[mask, col] = enrichment_data[col]
                updates_applied += 1

        logging.info(f"Applied {updates_applied} enrichment updates to full dataset (out of {len(enrichment_updates)} available)")
        return updates_applied

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
            full_df = self._load_full_dataset()
            full_df = self._ensure_theme_columns_exist(full_df)
            self._apply_theme_updates_to_full_dataset(full_df, df)
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
            force_update: If True, update even records that already have themes
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
        try:
            cogfy_records = self._query_cogfy_bulk(start_date, end_date)
        except Exception as e:
            logging.error(f"Failed to retrieve data from Cogfy: {str(e)}")
            logging.error("Theme enrichment process terminated due to Cogfy API failure")
            raise Exception(f"Cogfy API failure: {str(e)}")

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
    """Main entry point for the dataset enrichment script."""
    parser = argparse.ArgumentParser(
        description='Enrich HuggingFace dataset with AI-generated data from Cogfy (themes + summary)'
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
        help='Force update existing enrichment values (default: skip records that already have themes)'
    )

    args = parser.parse_args()

    try:
        enrichment_manager = EnrichmentManager(
            server_url=args.server_url,
            collection_name=args.collection
        )

        enrichment_manager.enrich_dataset_with_themes(
            start_date=args.start_date,
            end_date=args.end_date,
            force_update=args.force
        )

    except Exception as e:
        logging.error(f"Error during dataset enrichment: {str(e)}")
        raise


if __name__ == "__main__":
    main()
