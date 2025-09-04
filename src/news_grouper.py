import os
import datetime
import hashlib
from collections import defaultdict
from typing import Dict, List, Optional, Union
import pandas as pd
from cogfy_manager import CogfyClient, CollectionManager
from dotenv import load_dotenv


class NewsGrouper:
    """Groups news records by theme_1_level_1 using Cogfy collections."""

    def __init__(self, api_key: str, base_url: str = "https://api.cogfy.com"):
        """Initialize the NewsGrouper with Cogfy client.

        Args:
            api_key (str): Cogfy API key
            base_url (str): Base URL for Cogfy API
        """
        self.client = CogfyClient(api_key, base_url)
        self._source_manager = None
        self._target_manager = None
        self._source_field_map = None
        self._target_field_map = None

    def setup_collections(self, source_collection_name: str, target_collection_name: str):
        """Setup source and target collection managers.

        Args:
            source_collection_name (str): Name of the source collection
            target_collection_name (str): Name of the target collection
        """
        self._source_manager = CollectionManager(self.client, source_collection_name)
        self._target_manager = CollectionManager(self.client, target_collection_name)

        # Build field mappings
        self._source_field_map = {field.name: field.id for field in self._source_manager.list_columns()}
        self._target_field_map = {field.name: field.id for field in self._target_manager.list_columns()}

    def get_news_by_date_range(self, start_date: Optional[Union[str, datetime.datetime]] = None, end_date: Optional[Union[str, datetime.datetime]] = None) -> List[Dict]:
        """Query news records within a specific date range.

        Args:
            start_date: Start date for filtering (inclusive). If None, defaults to 1 day ago
            end_date: End date for filtering (inclusive). If None, defaults to current time

        Returns:
            List[Dict]: List of news records
        """
        if not self._source_manager or not self._source_field_map:
            raise ValueError("Collections not setup. Call setup_collections() first.")

        # Get the published_at field ID
        published_at_field_id = self._source_field_map.get("published_at")
        if not published_at_field_id:
            raise ValueError("Field 'published_at' not found in source collection")

        # Set default dates if not provided
        if start_date is None:
            start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        elif isinstance(start_date, str):
            start_date = pd.to_datetime(start_date).tz_localize(datetime.timezone.utc)

        if end_date is None:
            end_date = datetime.datetime.now(datetime.timezone.utc)
        elif isinstance(end_date, str):
            end_date = pd.to_datetime(end_date).tz_localize(datetime.timezone.utc)

        # Convert to ISO format for API
        start_date_iso = start_date.isoformat().replace("+00:00", "Z")
        end_date_iso = end_date.isoformat().replace("+00:00", "Z")

        # Build filter for date range
        filter_criteria = {
            "filter": {
                "type": "and",
                "and": {
                    "filters": [
                        {
                            "type": "greaterThanOrEquals",
                            "greaterThanOrEquals": {
                                "fieldId": published_at_field_id,
                                "value": start_date_iso
                            }
                        },
                        {
                            "type": "lessThanOrEquals",
                            "lessThanOrEquals": {
                                "fieldId": published_at_field_id,
                                "value": end_date_iso
                            }
                        }
                    ]
                }
            }
        }

        # Query records
        result = self._source_manager.query_records(filter=filter_criteria.get("filter"))
        return result.get("data", [])

    def parse_news_records(self, raw_records: List[Dict]) -> List[Dict]:
        """Parse raw Cogfy records into simplified news records.

        Args:
            raw_records (List[Dict]): Raw records from Cogfy API

        Returns:
            List[Dict]: Parsed news records with agency, title, category, content, theme_1_level_1
        """
        self._validate_source_setup()
        field_ids = self._get_required_field_ids()
        theme_options = self._get_theme_options()

        parsed_records = []
        for record in raw_records:
            try:
                parsed_record = self._parse_single_record(record, field_ids, theme_options)
                parsed_records.append(parsed_record)
            except (KeyError, TypeError) as e:
                print(f"Warning: Skipping record {record.get('id', 'unknown')} due to missing fields: {e}")
                continue

        return parsed_records

    def _validate_source_setup(self) -> None:
        """Validate that source collection is properly setup.

        Raises:
            ValueError: If source collection is not setup
        """
        if not self._source_field_map:
            raise ValueError("Source collection not setup. Call setup_collections() first.")

    def _get_required_field_ids(self) -> Dict[str, str]:
        """Get field IDs for required fields.

        Returns:
            Dict[str, str]: Mapping of field names to field IDs

        Raises:
            ValueError: If any required field is not found
        """
        required_fields = ["agency", "title", "category", "content", "theme_1_level_1"]
        field_ids = {}
        for field_name in required_fields:
            field_id = self._source_field_map.get(field_name)
            if not field_id:
                raise ValueError(f"Field '{field_name}' not found in source collection")
            field_ids[field_name] = field_id
        return field_ids

    def _get_theme_options(self) -> List[Dict]:
        """Get theme options from the theme_1_level_1 select field.

        Returns:
            List[Dict]: List of theme options with id and label
        """
        theme_field = next(
            (f for f in self._source_manager.list_columns() if f.type == "select" and f.name == "theme_1_level_1"),
            None
        )
        return theme_field.data.get("select").get("options")

    def _parse_single_record(self, record: Dict, field_ids: Dict[str, str], theme_options: List[Dict]) -> Dict:
        """Parse a single record into simplified format.

        Args:
            record (Dict): Raw record from Cogfy API
            field_ids (Dict[str, str]): Mapping of field names to IDs
            theme_options (List[Dict]): List of theme options

        Returns:
            Dict: Parsed record with simplified structure
        """
        theme_id = self._extract_theme_id(record, field_ids["theme_1_level_1"])
        theme_label = self._extract_theme_label(theme_id, theme_options)

        return {
            "id": record["id"],
            "agency": record["properties"].get(field_ids["agency"])["text"]["value"],
            "title": record["properties"].get(field_ids["title"])["text"]["value"],
            "category": record["properties"].get(field_ids["category"])["text"]["value"],
            "content": record["properties"].get(field_ids["content"])["text"]["value"],
            "theme_1_level_1": theme_label
        }

    def _extract_theme_id(self, record: Dict, theme_field_id: str) -> str:
        """Extract theme ID from record properties.

        Args:
            record (Dict): Record with properties
            theme_field_id (str): Field ID for theme field

        Returns:
            str: Theme ID or None if not found
        """
        theme_property = record["properties"].get(theme_field_id)
        if not theme_property or not theme_property["select"]["value"]:
            return None
        return theme_property["select"]["value"][0]["id"]

    def _extract_theme_label(self, theme_id: str, theme_options: List[Dict]) -> str:
        """Extract theme label from theme ID using theme options.

        Args:
            theme_id (str): Theme ID to look up
            theme_options (List[Dict]): List of theme options

        Returns:
            str: Theme label or None if not found
        """
        if not theme_id:
            return None
        return next((opt["label"] for opt in theme_options if opt["id"] == theme_id), None)

    def group_by_theme(self, news_records: List[Dict]) -> Dict[str, List[Dict]]:
        """Group news records by theme.

        Args:
            news_records (List[Dict]): List of parsed news records

        Returns:
            Dict[str, List[Dict]]: Dictionary mapping theme labels to their records
        """
        grouped_records = defaultdict(list)
        for record in news_records:
            grouped_records[record["theme_1_level_1"]].append(record)
        return dict(grouped_records)

    def insert_grouped_records(self, grouped_records: Dict[str, List[Dict]], start_date: str) -> int:
        """Insert grouped records into the target collection.

        Args:
            grouped_records (Dict[str, List[Dict]]): Grouped records by theme
            start_date (str): The reference date for the news (start-date parameter)

        Returns:
            int: Number of records inserted
        """
        if not self._target_manager or not self._target_field_map:
            raise ValueError("Target collection not setup. Call setup_collections() first.")

        # Ensure required fields exist in target collection
        self._ensure_target_fields()

        # Refresh field mapping after ensuring fields
        self._target_field_map = {field.name: field.id for field in self._target_manager.list_columns()}

        # Get field IDs
        field_ids = self._get_target_field_ids()

        inserted_count = 0
        skipped_count = 0

        for theme, theme_records in grouped_records.items():
            # Generate unique_id for this theme group
            unique_id = self._generate_unique_id(theme, start_date)

            # Check if record already exists
            if self._record_exists(unique_id, field_ids["unique_id"]):
                print(f"Skipping existing record for theme '{theme}' on date {start_date}")
                skipped_count += 1
                continue

            # Create record properties with new schema
            record_properties = {
                field_ids["theme_1_level_1"]: {
                    "type": "text",
                    "text": {"value": theme}
                },
                field_ids["group_records"]: {
                    "type": "json",
                    "json": {"value": theme_records}
                },
                field_ids["records_number"]: {
                    "type": "number",
                    "number": {"value": len(theme_records)}
                },
                field_ids["published_at"]: {
                    "type": "text",
                    "text": {"value": start_date}
                },
                field_ids["unique_id"]: {
                    "type": "text",
                    "text": {"value": unique_id}
                },
                field_ids["unique_theme_published_at"]: {
                    "type": "text",
                    "text": {"value": f"{theme}-{start_date}"}
                }
            }

            try:
                self._target_manager.create_record(record_properties)
                inserted_count += 1
                print(f"Inserted record for theme '{theme}' with {len(theme_records)} records")
            except Exception as e:
                print(f"Error inserting record for theme_1_level_1 '{theme}': {e}")
                continue

        print(f"Insert completed: {inserted_count} created, {skipped_count} skipped")
        return inserted_count

    def _ensure_target_fields(self) -> None:
        """Ensure that all required fields exist in the target collection."""
        required_fields = {
            "theme_1_level_1": "text",
            "group_records": "json",
            "records_number": "number",
            "published_at": "text",
            "unique_id": "text",
            "unique_theme_published_at": "text"
        }

        print("Ensuring required fields exist in target collection...")
        self._target_manager.ensure_fields(required_fields)

    def _get_target_field_ids(self) -> Dict[str, str]:
        """Get field IDs for all required target fields.

        Returns:
            Dict[str, str]: Mapping of field names to field IDs

        Raises:
            ValueError: If any required field is not found
        """
        required_fields = ["theme_1_level_1", "group_records", "records_number", "published_at", "unique_id", "unique_theme_published_at"]
        field_ids = {}

        for field_name in required_fields:
            field_id = self._target_field_map.get(field_name)
            if not field_id:
                raise ValueError(f"Field '{field_name}' not found in target collection")
            field_ids[field_name] = field_id

        return field_ids

    def _generate_unique_id(self, theme: str, published_at: str) -> str:
        """Generate a unique identifier based on theme and published_at.

        Args:
            theme (str): The theme name
            published_at (str): The published date (YYYY-MM-DD format)

        Returns:
            str: A unique hash string
        """
        hash_input = f"{theme}_{published_at}".encode("utf-8")
        return hashlib.md5(hash_input).hexdigest()

    def _record_exists(self, unique_id: str, unique_id_field_id: str) -> bool:
        """Check if a record with the given unique_id already exists.

        Args:
            unique_id (str): The unique identifier to check
            unique_id_field_id (str): The field ID for unique_id field

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
                            "fieldId": unique_id_field_id,
                            "value": unique_id
                        }
                    }
                ]
            }
        }

        try:
            result = self._target_manager.query_records(
                filter=filter_criteria,
                page_size=1
            )
            return len(result.get("data", [])) > 0
        except Exception as e:
            print(f"Error checking if record exists: {e}")
            return False

    def process_news_grouping(
        self,
        source_collection_name: str = "noticiasgovbr-all-news",
        target_collection_name: str = "publications-by-theme_level_1",
        start_date: Optional[Union[str, datetime.datetime]] = None,
        end_date: Optional[Union[str, datetime.datetime]] = None
    ) -> int:
        """Complete workflow to group news by theme_1_level_1.

        Args:
            source_collection_name (str): Name of source collection
            target_collection_name (str): Name of target collection
            start_date: Start date for filtering (inclusive). If None, defaults to 1 day ago
            end_date: End date for filtering (inclusive). If None, defaults to current time

        Returns:
            int: Number of grouped records inserted
        """
        # Setup collections
        self.setup_collections(source_collection_name, target_collection_name)

        # Get news within date range
        raw_records = self.get_news_by_date_range(start_date, end_date)
        date_range_str = f"from {start_date or '1 day ago'} to {end_date or 'now'}"
        print(f"Found {len(raw_records)} records {date_range_str}")

        # Parse records
        news_records = self.parse_news_records(raw_records)
        print(f"Successfully parsed {len(news_records)} records")

        # Group by theme_1_level_1
        grouped_records = self.group_by_theme(news_records)
        print(f"Grouped records into {len(grouped_records)} themes")

        # Convert start_date to string for reference
        reference_date = start_date if isinstance(start_date, str) else (start_date.strftime('%Y-%m-%d') if start_date else datetime.datetime.now().strftime('%Y-%m-%d'))

        # Insert grouped records
        inserted_count = self.insert_grouped_records(grouped_records, reference_date)
        print(f"Inserted {inserted_count} grouped records into target collection")

        return inserted_count


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(description='Group GovBR News by theme_1_level_1')
    parser.add_argument('--start-date', help='Start date for filtering (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='Filter by end date (YYYY-MM-DD)')
    parser.add_argument('--source-collection', default="noticiasgovbr-all-news",
                       help='Source Cogfy collection name (default: noticiasgovbr-all-news)')
    parser.add_argument('--target-collection', default="publications-by-theme_level_1",
                       help='Target Cogfy collection name (default: publications-by-theme_level_1)')
    parser.add_argument('--server-url', default="https://api.cogfy.com/",
                       help='Cogfy server URL (default: https://api.cogfy.com/)')

    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("COGFY_API_KEY")
    if not api_key:
        raise ValueError("COGFY_API_KEY environment variable is required")

    try:
        # Create grouper and process
        grouper = NewsGrouper(api_key, base_url=args.server_url)
        grouper.process_news_grouping(
            source_collection_name=args.source_collection,
            target_collection_name=args.target_collection,
            start_date=args.start_date,
            end_date=args.end_date
        )
    except Exception as e:
        print(f"Error during grouping: {str(e)}")
        raise


if __name__ == "__main__":
    main()
