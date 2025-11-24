import hashlib
import logging
from collections import OrderedDict
from datetime import date, datetime
from typing import Dict, List

from dataset_manager import DatasetManager
from scraper.ebc_webscraper import EBCWebScraper

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class EBCScrapeManager:
    """
    A class that focuses on:
      - Running EBC web scrapers for the specified date ranges.
      - Preprocessing, transforming, and preparing raw EBC news data into a well-structured format
        ready for dataset creation and analysis.
      - Generating unique identifiers for news items based on their attributes (agency,
        published date, and title).
      - Converting raw data from a list-of-dictionaries format into a columnar (OrderedDict) format.
      - Merging new data with an existing dataset, ensuring no duplicates by comparing unique IDs.
      - Sorting the combined dataset by specified criteria (e.g., agency and publication date).
      - Preparing the final processed data into columnar format suitable for integration with
        a dataset manager.
    """

    def __init__(self, dataset_manager: DatasetManager):
        self.dataset_manager = dataset_manager

    def run_scraper(
        self,
        min_date: str,
        max_date: str,
        sequential: bool,
        allow_update: bool = False,
    ):
        """
        Executes the EBC web scraping process for the given date range.

        :param min_date: The minimum date for filtering news.
        :param max_date: The maximum date for filtering news.
        :param sequential: Whether to process and upload sequentially (always True for EBC since we have only one source).
        :param allow_update: If True, overwrite existing entries in the dataset.
        """
        try:
            logging.info(f"Starting EBC scraping from {min_date} to {max_date}")

            # Create the EBC scraper
            ebc_scraper = EBCWebScraper(min_date, max_date)

            # Scrape the news data
            scraped_data = ebc_scraper.scrape_news()

            if scraped_data:
                logging.info(f"Successfully scraped {len(scraped_data)} articles from EBC")
                logging.info("Processing and uploading EBC news to HF dataset.")
                self._process_and_upload_data(scraped_data, allow_update)
            else:
                logging.info("No EBC news found for the specified date range.")

        except Exception as e:
            logging.error(f"Error during EBC scraping: {e}")
            raise

    def _process_and_upload_data(self, new_data: List[Dict], allow_update: bool):
        """
        Process the EBC news data and upload it to the dataset, with the option to update existing entries.

        :param new_data: The list of EBC news items to process.
        :param allow_update: If True, overwrite existing entries in the dataset.
        """
        # Convert EBC data format to govbrnews format
        processed_data = self._convert_ebc_to_govbr_format(new_data)

        # Preprocess the data (add unique IDs, reorder columns)
        processed_data = self._preprocess_data(processed_data)

        # Insert into dataset
        self.dataset_manager.insert(processed_data, allow_update=allow_update)

    def _convert_ebc_to_govbr_format(self, ebc_data: List[Dict]) -> List[Dict]:
        """
        Convert EBC data format to match the govbrnews schema.

        :param ebc_data: List of EBC news items as dictionaries.
        :return: List of news items in govbrnews format.
        """
        converted_data = []

        for item in ebc_data:
            # Skip items with errors
            if item.get("error"):
                logging.warning(f"Skipping item with error: {item['error']}")
                continue

            # Get datetimes (already extracted by EBCWebScraper)
            published_dt = item.get("published_datetime")
            updated_datetime = item.get("updated_datetime")

            # Use the agency from the scraped data (either 'agencia_brasil' or 'tvbrasil')
            # Fallback to 'ebc' if not specified
            agency = item.get("agency", "ebc")

            converted_item = {
                "title": item.get("title", "").strip(),
                "url": item.get("url", "").strip(),
                "published_at": published_dt if published_dt else None,
                "updated_datetime": updated_datetime,
                "category": "Notícias",  # EBC doesn't have specific categories like gov.br
                "tags": item.get("tags", []),  # Now extracted from article pages
                "editorial_lead": None,  # EBC articles don't typically have editorial leads
                "subtitle": None,  # EBC articles don't typically have subtitles in the same format
                "content": item.get("content", "").strip(),
                "image": item.get("image", "").strip(),
                "video_url": item.get("video_url", "").strip(),
                "agency": agency,
                "extracted_at": datetime.now(),
            }

            # Only add items with essential data
            if converted_item["title"] and converted_item["url"] and converted_item["content"]:
                converted_data.append(converted_item)
            else:
                logging.warning(f"Skipping incomplete item: {item.get('url', 'unknown URL')}")

        return converted_data

    def _parse_ebc_date(self, date_str: str) -> date:
        """
        Parse EBC date string to date object.
        Expected format: "16/09/2025 - 13:40"

        :param date_str: Date string from EBC.
        :return: Date object or current date if parsing fails.
        """
        try:
            if not date_str:
                return datetime.now().date()

            # Remove extra whitespace and split by ' - '
            date_part = date_str.strip().split(' - ')[0]
            # Parse the date part (DD/MM/YYYY)
            return datetime.strptime(date_part, '%d/%m/%Y').date()
        except Exception as e:
            logging.warning(f"Could not parse date '{date_str}': {e}. Using current date.")
            return datetime.now().date()

    def _preprocess_data(self, data: List[Dict[str, str]]) -> OrderedDict:
        """
        Preprocess data by:
        - Adding the unique_id column.
        - Reordering columns to match govbrnews format.

        :param data: List of news items as dictionaries.
        :return: An OrderedDict with the processed data.
        """
        # Generate unique_id for each record
        for item in data:
            item["unique_id"] = self._generate_unique_id(
                item.get("agency", ""),
                item.get("published_at", ""),
                item.get("title", ""),
            )

        # Convert to columnar format
        if not data:
            return OrderedDict()

        column_data = {
            key: [item.get(key, None) for item in data] for key in data[0].keys()
        }

        # Reorder columns to match govbrnews format
        ordered_column_data = OrderedDict()
        if "unique_id" in column_data:
            ordered_column_data["unique_id"] = column_data.pop("unique_id")
        if "agency" in column_data:
            ordered_column_data["agency"] = column_data.pop("agency")
        if "published_at" in column_data:
            ordered_column_data["published_at"] = column_data.pop("published_at")
        if "updated_datetime" in column_data:
            ordered_column_data["updated_datetime"] = column_data.pop("updated_datetime")

        # Add remaining columns in order (matching govbrnews schema)
        for key in ["title", "editorial_lead", "subtitle", "url", "category", "tags", "content", "image", "video_url", "extracted_at"]:
            if key in column_data:
                ordered_column_data[key] = column_data.pop(key)

        # Add any remaining columns
        ordered_column_data.update(column_data)

        return ordered_column_data

    def _generate_unique_id(
        self, agency: str, published_at_value, title: str
    ) -> str:
        """
        Generate a unique identifier based on the agency, published_at, and title.

        :param agency: The agency name.
        :param published_at_value: The published_at date of the news item (string format or date object).
        :param title: The title of the news item.
        :return: A unique hash string.
        """
        date_str = (
            published_at_value.isoformat()
            if isinstance(published_at_value, date)
            else str(published_at_value)
        )
        hash_input = f"{agency}_{date_str}_{title}".encode("utf-8")
        return hashlib.md5(hash_input).hexdigest()
