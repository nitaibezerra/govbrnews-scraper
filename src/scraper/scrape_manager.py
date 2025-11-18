import hashlib
import logging
import os
from collections import OrderedDict
from datetime import date
from typing import Dict, List

import yaml
from dataset_manager import DatasetManager
from scraper.webscraper import WebScraper

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ScrapeManager:
    """
    A class that focuses on:
      - Loading and filtering URLs from a YAML file.
      - Running web scrapers for the specified agencies and date ranges.
      - Preprocessing, transforming, and preparing raw news data into a well-structured format
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

    def _load_urls_from_yaml(self, file_name: str, agency: str = None) -> List[str]:
        """
        Load URLs from a YAML file located in the same directory as this script.

        :param file_name: The name of the YAML file.
        :param agency: Specific agency key to filter URLs. If None, load all URLs.
        :return: A list of URLs.
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, file_name)

        with open(file_path, "r") as f:
            agencies = yaml.safe_load(f)["agencies"]

        if agency:
            if agency in agencies:
                return [agencies[agency]]
            else:
                raise ValueError(f"Agency '{agency}' not found in the YAML file.")

        return list(agencies.values())

    def run_scraper(
        self,
        agencies: List[str],
        min_date: str,
        max_date: str,
        sequential: bool,
        allow_update: bool = False,
    ):
        """
        Executes the web scraping process for the given agencies, date range,
        and whether the scraping should happen sequentially or in bulk.

        :param agencies: A list of agency names to scrape news from. If None, all agencies are scraped.
        :param min_date: The minimum date for filtering news.
        :param max_date: The maximum date for filtering news.
        :param sequential: Whether to scrape sequentially (True) or in bulk (False).
        :param allow_update: If True, overwrite existing entries in the dataset.
        """
        try:
            all_urls = []
            # Load URLs for each agency in the list
            if agencies:
                for agency in agencies:
                    try:
                        urls = self._load_urls_from_yaml("site_urls.yaml", agency)
                        all_urls.extend(urls)
                    except ValueError as e:
                        logging.warning(f"Skipping agency '{agency}': {e}")
            else:
                # Load all agency URLs if agencies list is None or empty
                all_urls = self._load_urls_from_yaml("site_urls.yaml")

            webscrapers = [
                WebScraper(min_date, url, max_date=max_date) for url in all_urls
            ]

            if sequential:
                for scraper in webscrapers:
                    scraped_data = scraper.scrape_news()
                    if scraped_data:
                        logging.info(
                            f"Appending news for {scraper.agency} to HF dataset."
                        )
                        self._process_and_upload_data(scraped_data, allow_update)
                    else:
                        logging.info(f"No news found for {scraper.agency}.")
            else:
                all_news_data = []
                for scraper in webscrapers:
                    scraped_data = scraper.scrape_news()
                    if scraped_data:
                        all_news_data.extend(scraped_data)
                    else:
                        logging.info(f"No news found for {scraper.agency}.")

                if all_news_data:
                    logging.info("Appending all collected news to HF dataset.")
                    self._process_and_upload_data(all_news_data, allow_update)
                else:
                    logging.info("No news found for any agency.")
        except ValueError as e:
            logging.error(e)

    def _process_and_upload_data(self, new_data, allow_update: bool):
        """
        Process the news data and upload it to the dataset, with the option to update existing entries.

        :param new_data: The list of news items to process.
        :param allow_update: If True, overwrite existing entries in the dataset.
        """
        new_data = self._preprocess_data(new_data)
        self.dataset_manager.insert(new_data, allow_update=allow_update)

    def _preprocess_data(self, data: List[Dict[str, str]]) -> OrderedDict:
        """
        Preprocess data by:z
        - Adding the unique_id column.
        - Reordering columns.

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
        column_data = {
            key: [item.get(key, None) for item in data] for key in data[0].keys()
        }

        # Reorder columns
        ordered_column_data = OrderedDict()
        if "unique_id" in column_data:
            ordered_column_data["unique_id"] = column_data.pop("unique_id")
        if "agency" in column_data:
            ordered_column_data["agency"] = column_data.pop("agency")
        if "published_at" in column_data:
            ordered_column_data["published_at"] = column_data.pop("published_at")
        if "published_datetime" in column_data:
            ordered_column_data["published_datetime"] = column_data.pop("published_datetime")
        if "updated_datetime" in column_data:
            ordered_column_data["updated_datetime"] = column_data.pop("updated_datetime")
        if "title" in column_data:
            ordered_column_data["title"] = column_data.pop("title")
        if "editorial_lead" in column_data:
            ordered_column_data["editorial_lead"] = column_data.pop("editorial_lead")
        if "subtitle" in column_data:
            ordered_column_data["subtitle"] = column_data.pop("subtitle")
        ordered_column_data.update(column_data)

        return ordered_column_data

    def _generate_unique_id(
        self, agency: str, published_at_value: str, title: str
    ) -> str:
        """
        Generate a unique identifier based on the agency, published_at, and title.

        :param agency: The agency name.
        :param published_at_value: The published_at date of the news item (string format or datetime.date).
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
