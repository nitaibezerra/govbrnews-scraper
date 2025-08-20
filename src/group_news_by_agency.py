import os
import datetime
from collections import defaultdict
from typing import Dict, List
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

    def get_recent_news(self, days_back: int = 1) -> List[Dict]:
        """Query news records from the last N days.

        Args:
            days_back (int): Number of days to look back

        Returns:
            List[Dict]: List of news records
        """
        if not self._source_manager or not self._source_field_map:
            raise ValueError("Collections not setup. Call setup_collections() first.")

        # Get the published_at field ID
        published_at_field_id = self._source_field_map.get("published_at")
        if not published_at_field_id:
            raise ValueError("Field 'published_at' not found in source collection")

        # Build filter for recent records
        cutoff_date = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_back)
        ).isoformat().replace("+00:00", "Z")

        filter_criteria = {
            "filter": {
                "type": "and",
                "and": {
                    "filters": [
                        {
                            "type": "greaterThanOrEquals",
                            "greaterThanOrEquals": {
                                "fieldId": published_at_field_id,
                                "value": cutoff_date
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
        if not self._source_field_map:
            raise ValueError("Source collection not setup. Call setup_collections() first.")

        # Get field IDs
        required_fields = ["agency", "title", "category", "content", "theme_1_level_1"]
        field_ids = {}
        for field_name in required_fields:
            field_id = self._source_field_map.get(field_name)
            if not field_id:
                raise ValueError(f"Field '{field_name}' not found in source collection")
            field_ids[field_name] = field_id

        parsed_records = []
        for record in raw_records:
            try:
                parsed_record = {
                    "id": record["id"],
                    "agency": record["properties"].get(field_ids["agency"])["text"]["value"],
                    "title": record["properties"].get(field_ids["title"])["text"]["value"],
                    "category": record["properties"].get(field_ids["category"])["text"]["value"],
                    "content": record["properties"].get(field_ids["content"])["text"]["value"]
                }
                parsed_records.append(parsed_record)
            except (KeyError, TypeError) as e:
                print(f"Warning: Skipping record {record.get('id', 'unknown')} due to missing fields: {e}")
                continue

        return parsed_records

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

    def insert_grouped_records(self, grouped_records: Dict[str, List[Dict]]) -> int:
        """Insert grouped records into the target collection.

        Args:
            grouped_records (Dict[str, List[Dict]]): Grouped records by theme

        Returns:
            int: Number of records inserted
        """
        if not self._target_manager or not self._target_field_map:
            raise ValueError("Target collection not setup. Call setup_collections() first.")

        # Get the news_by_theme_1_level_1 field ID
        news_by_theme_1_level_1_field_id = self._target_field_map.get("news_by_theme_1_level_1")
        if not news_by_theme_1_level_1_field_id:
            raise ValueError("Field 'news_by_theme_1_level_1' not found in target collection")

        inserted_count = 0
        for agency, agency_records in grouped_records.items():
            record_properties = {
                news_by_agency_field_id: {
                    "type": "json",
                    "json": {
                        "value": {
                            "agency": agency,
                            "records": agency_records
                        }
                    }
                }
            }

            try:
                self._target_manager.create_record(record_properties)
                inserted_count += 1
            except Exception as e:
                print(f"Error inserting record for theme_1_level_1 '{theme}': {e}")
                continue

        return inserted_count

    def process_news_grouping(
        self,
        source_collection_name: str = "noticiasgovbr-all-news",
        target_collection_name: str = "noticiasgovbr-by-theme_1_level_1",
        days_back: int = 1
    ) -> int:
        """Complete workflow to group news by theme_1_level_1.

        Args:
            source_collection_name (str): Name of source collection
            target_collection_name (str): Name of target collection
            days_back (int): Number of days to look back

        Returns:
            int: Number of grouped records inserted
        """
        # Setup collections
        self.setup_collections(source_collection_name, target_collection_name)

        # Get recent news
        raw_records = self.get_recent_news(days_back)
        print(f"Found {len(raw_records)} records from the last {days_back} day(s)")

        # Parse records
        news_records = self.parse_news_records(raw_records)
        print(f"Successfully parsed {len(news_records)} records")

        # Group by theme_1_level_1
        grouped_records = self.group_by_theme(news_records)
        print(f"Grouped records into {len(grouped_records)} themes")

        # Insert grouped records
        inserted_count = self.insert_grouped_records(grouped_records)
        print(f"Inserted {inserted_count} grouped records into target collection")

        return inserted_count


def main():
    """Main function to run the news grouping process."""
    load_dotenv()
    api_key = os.getenv("COGFY_API_KEY")
    if not api_key:
        raise ValueError("COGFY_API_KEY environment variable is required")

    # Create grouper and process
    grouper = NewsGrouper(api_key)
    grouper.process_news_grouping(days_back=1)


if __name__ == "__main__":
    main()
