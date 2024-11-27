import argparse
import hashlib
import json
import logging
import os
import random
import time
from collections import OrderedDict
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import requests
import yaml
from bs4 import BeautifulSoup
from datasets import Dataset, load_dataset
from datasets.exceptions import DatasetNotFoundError
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SLEEP_TIME_INTERVAL = (1, 3)
DATASET_PATH = "nitaibezerra/govbrnews"  # The name of the Hugging Face dataset
RAW_EXTRACTIONS_PATH = (
    "raw_extractions"  # Directory where existing JSON files are stored
)


def load_urls_from_yaml(file_path: str) -> Dict[str, str]:
    """
    Load URLs from a YAML file.

    :param file_path: The path to the YAML file.
    :return: A dictionary with agency names as keys and URLs as values.
    """
    with open(file_path, "r") as f:
        return yaml.safe_load(f)["agencies"]


class GovBRNewsScraper:
    def __init__(self, min_date: str, base_url: str):
        """
        Initialize the scraper with a minimum date and base URL.

        :param min_date: The minimum date for scraping news (format: YYYY-MM-DD).
        :param base_url: The base URL of the agency's news page.
        """
        self.base_url = base_url
        self.min_date = datetime.strptime(min_date, "%Y-%m-%d").date()
        self.news_data = []
        self.agency = self.get_agency_name()

    def get_agency_name(self) -> str:
        """
        Extract the agency name from the base URL for naming files.

        :return: The agency name.
        """
        return self.base_url.split("/")[3]

    def scrape_news(self) -> List[Dict[str, str]]:
        """
        Scrape news from the website until the min_date is reached.

        :return: A list of dictionaries containing news data.
        """

        current_offset = 0

        while True:
            current_page_url = f"{self.base_url}?b_start:int={current_offset}"
            should_continue, items_per_page = self.scrape_page(current_page_url)

            # If no items were found, break the loop to avoid infinite requests
            if items_per_page == 0:
                logging.info("No more news items found. Stopping.")
                break

            if not should_continue:
                break

            # Increment the offset only if items were found
            current_offset += items_per_page
            logging.info(f"Moving to next page with offset {current_offset}")

        return self.news_data

    def scrape_page(self, page_url: str) -> Tuple[bool, int]:
        """
        Scrape a single page of news.

        :param page_url: The URL of the page to scrape.
        :return: A tuple (continue_scraping, items_per_page).
        """
        logging.info(f"Fetching news from {page_url}")

        # Sleep for a random amount of time between 1 and 3 seconds
        time.sleep(random.uniform(*SLEEP_TIME_INTERVAL))

        response = requests.get(page_url)
        soup = BeautifulSoup(response.content, "html.parser")
        news_items = soup.find_all("article", class_="tileItem")

        # Second HTML structure type
        if not news_items:
            news_list = soup.find("ul", class_="noticias")
            if news_list:
                news_items = news_list.find_all("li")
            else:
                news_items = []

        items_per_page = len(news_items)
        logging.info(f"Found {items_per_page} news items on the page")

        for item in news_items:
            news_info = self.extract_news_info(item)
            if news_info:
                self.news_data.append(news_info)
            else:
                return (
                    False,
                    items_per_page,
                )  # Stop if news older than min_date is found

        return True, items_per_page

    def extract_news_info(self, item) -> Optional[Dict[str, str]]:
        """
        Extract the news information from an HTML element.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: A dictionary containing the news data or None if the news is older than the min_date.
        """
        title, url = self.extract_title_and_url(item)
        category = self.extract_category(item)
        news_date = self.extract_date(item)
        if news_date and news_date < self.min_date:
            logging.info(
                f"Stopping scrape. Found news older than min date: {news_date}"
            )
            return None
        tags = self.extract_tags(item)
        content = self.get_article_content(url)

        return {
            "title": title,
            "url": url,
            "published_at": news_date if news_date else None,
            "category": category,
            "tags": tags,
            "content": content,
            "agency": self.agency,
            "extracted_at": datetime.now(),
        }

    def extract_title_and_url(self, item) -> Tuple[str, str]:
        """
        Extract the title and URL from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: A tuple (title, url).
        """
        # First structure: Look for 'a' with class 'summary url'
        title_tag = item.find("a", class_="summary url")

        # Second structure: Look for a plain 'a' tag if 'summary url' is not found
        if not title_tag:
            title_tag = item.find("a")

        title = title_tag.get_text().strip() if title_tag else "No Title"
        url = title_tag["href"] if title_tag else "No URL"
        return title, url

    def extract_category(self, item) -> str:
        """
        Extract the category from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The category as a string.
        """
        # First structure: Look for 'span' with class 'subtitle'
        category_tag = item.find("span", class_="subtitle")

        # Second structure: Look for 'div' with class 'subtitulo-noticia'
        if not category_tag:
            category_tag = item.find("div", class_="subtitulo-noticia")

        # Third structure: Look for 'div' with class 'categoria-noticia'
        if not category_tag:
            category_tag = item.find("div", class_="categoria-noticia")

        return category_tag.get_text().strip() if category_tag else "No Category"

    def extract_date(self, item) -> Optional[date]:
        """
        Extract the date from a news item using multiple strategies.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime.date object or None if not found.
        """
        result = self.extract_date_1(item)
        if not result:
            result = self.extract_date_2(item)

        if not result:
            logging.error("No date found in news item.")
            return None

        return result.date()

    def extract_date_1(self, item) -> Optional[datetime]:
        """
        Extract the date from a news item using the first strategy.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime.datetime object or None if not found.
        """
        date_tag = item.find("span", class_="documentByLine")
        date_str = date_tag.get_text().strip() if date_tag else ""

        if date_str:
            date_parts = date_str.split()
            if len(date_parts) > 1:
                clean_date_str = date_parts[1]
                try:
                    return datetime.strptime(clean_date_str, "%d/%m/%Y")
                except ValueError:
                    logging.warning(f"Date format not recognized: {clean_date_str}")
                    return None
        return None

    def extract_date_2(self, item) -> Optional[datetime]:
        """
        Extract the date from a news item using the second strategy.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime.datetime object or None if not found.
        """
        date_tag = item.find("span", class_="data")

        # Extract the date string
        date_str = date_tag.get_text().strip() if date_tag else None

        if not date_str:
            return None

        try:
            # Assuming the format is 'dd/mm/yyyy'
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            logging.warning(f"Date format not recognized: {date_str}")
            return None

    def extract_tags(self, item) -> List[str]:
        """
        Extract the tags from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: A list of tags as strings.
        """
        # First structure: Look for 'div' with class 'keywords'
        tags_div = item.find("div", class_="keywords")

        # Second structure: Look for 'div' with class 'subject-noticia'
        if not tags_div:
            tags_div = item.find("div", class_="subject-noticia")

        if tags_div:
            tag_links = tags_div.find_all("a", class_="link-category")
            return [tag.get_text().strip() for tag in tag_links]

        return []

    def get_article_content(self, url: str) -> str:
        """
        Get the content of a news article from its URL.

        :param url: The URL of the article.
        :return: The content of the article as a string.
        """
        try:
            logging.info(f"Retrieving content from {url}")
            time.sleep(random.uniform(*SLEEP_TIME_INTERVAL))
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            article_body = soup.find("div", id="content-core")
            return (
                article_body.get_text().strip() if article_body else "No content found"
            )
        except Exception as e:
            logging.error(f"Error retrieving content from {url}: {str(e)}")
            return "Error retrieving content"


def append_to_huggingface_dataset(news_data: List[Dict[str, str]]):
    """
    Append the scraped news data to a Hugging Face dataset, ensuring no duplicates are added,
    and sort the final dataset by agency (asc) and published_at (desc).
    """
    if not news_data:
        logging.info("No news data to append.")
        return

    # Preprocess new data
    new_data = preprocess_data(news_data)

    # Check if the dataset already exists
    try:
        existing_dataset = load_dataset(DATASET_PATH, split="train")
        logging.info("Existing dataset loaded from Hugging Face Hub.")

        # Get the set of existing unique_ids
        existing_unique_ids = set(existing_dataset["unique_id"])
        logging.info(f"Existing dataset has {len(existing_unique_ids)} entries.")

        # Filter out new data that has duplicate unique_ids
        new_unique_ids = set(new_data["unique_id"])
        unique_ids_to_add = new_unique_ids - existing_unique_ids

        if not unique_ids_to_add:
            logging.info("No new unique news items to add. Dataset is up to date.")
            return

        # Create filtered new data
        filtered_new_data = {
            key: [
                value
                for idx, value in enumerate(values)
                if new_data["unique_id"][idx] in unique_ids_to_add
            ]
            for key, values in new_data.items()
        }

        logging.info(
            f"Adding {len(filtered_new_data['unique_id'])} new unique news items to the dataset."
        )

        # Combine existing data with filtered new data
        combined_data = {
            key: existing_dataset[key] + filtered_new_data.get(key, [])
            for key in existing_dataset.features.keys()
        }

    except DatasetNotFoundError:
        logging.info("No existing dataset found. Creating a new dataset.")
        combined_data = new_data

    # Sort the combined data by 'agency' (asc) and 'published_at' (desc)
    sorted_data = sorted(
        [
            {key: combined_data[key][i] for key in combined_data.keys()}
            for i in range(len(combined_data["unique_id"]))
        ],
        key=lambda x: (
            x.get("agency", ""),
            -x.get("published_at").toordinal()
            if isinstance(x.get("published_at"), date)
            else float("-inf"),
        ),
    )

    # Convert sorted data back to columnar format
    column_data = {
        key: [item.get(key, None) for item in sorted_data]
        for key in combined_data.keys()
    }

    # Create the combined dataset
    combined_dataset = Dataset.from_dict(column_data)

    # Push the combined dataset to the Hub
    push_dataset_to_hub(combined_dataset, DATASET_PATH)


def preprocess_data(data: List[Dict[str, str]]) -> OrderedDict:
    """
    Preprocess data by:
    - Adding the unique_id column.
    - Reordering columns.

    :param data: List of news items as dictionaries.
    :return: An OrderedDict with the processed data.
    """
    # Generate unique_id for each record
    for item in data:
        item["unique_id"] = generate_unique_id(
            item.get("agency", ""), item.get("published_at", ""), item.get("title", "")
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
    ordered_column_data.update(column_data)

    return ordered_column_data


def push_dataset_to_hub(dataset: Dataset, dataset_path: str):
    """
    Push a dataset to the Hugging Face Hub.

    :param dataset: The dataset to push.
    :param dataset_path: The Hugging Face Hub path.
    """
    dataset.push_to_hub(dataset_path, private=False)
    logging.info(f"Dataset pushed to Hugging Face Hub at {dataset_path}.")


def generate_unique_id(agency, published_at_value, title):
    """
    Generate a unique identifier based on the agency, published_at, and title.

    :param agency: The agency name.
    :param published_at_value: The published_at date of the news item (datetime.date).
    :param title: The title of the news item.
    :return: A unique hash string.
    """
    date_str = (
        published_at_value.isoformat()
        if isinstance(published_at_value, date)
        else "Unknown Date"
    )
    hash_input = f"{agency}_{date_str}_{title}".encode("utf-8")
    return hashlib.md5(hash_input).hexdigest()


def create_scrapers(urls: List[str], min_date: str) -> List[GovBRNewsScraper]:
    """
    Create a list of GovBRNewsScraper instances for each URL.

    :param urls: List of URLs to scrape.
    :param min_date: The minimum date for scraping news.
    :return: List of GovBRNewsScraper instances.
    """
    return [GovBRNewsScraper(min_date, url) for url in urls]


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Scrape news data to a Hugging Face dataset."
    )
    parser.add_argument(
        "--min-date",
        required=True,
        help="The minimum date for scraping news (format: YYYY-MM-DD).",
    )
    args = parser.parse_args()

    urls = list(load_urls_from_yaml("site_urls.yaml").values())
    scrapers = create_scrapers(urls, args.min_date)

    all_news_data = []

    for scraper in scrapers:
        news_data = scraper.scrape_news()
        all_news_data.extend(news_data)

    # After collecting all news data, append to the dataset
    append_to_huggingface_dataset(all_news_data)


if __name__ == "__main__":
    main()