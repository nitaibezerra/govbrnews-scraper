import argparse
import concurrent.futures
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
import yaml
from bs4 import BeautifulSoup

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

MAX_WORKERS = 3
DESTINATION_FOLDER = "raw_extractions"
SLEEP_TIME_INTERVAL = (1, 3)


def load_urls_from_yaml(file_path: str) -> Dict[str, str]:
    """
    Load URLs from a YAML file.

    :param file_path: The path to the YAML file.
    :return: A dictionary with agency names as keys and URLs as values.
    """
    with open(file_path, "r") as f:
        return yaml.safe_load(f)["agencies"]


class GovBRNewsScraper:
    def __init__(self, max_date: str, base_url: str):
        """
        Initialize the scraper with a maximum date and base URL.

        :param max_date: The maximum date for scraping news (format: YYYY-MM-DD).
        :param base_url: The base URL of the agency's news page.
        """
        self.base_url = base_url
        self.max_date = datetime.strptime(max_date, "%Y-%m-%d")
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
        Scrape news from the website until the max_date is reached.

        :return: A list of dictionaries containing news data.
        """

        if self.json_file_exists():
            logging.info(f"JSON file already exists for {self.agency}. Skipping.")
            return []

        current_offset = 0

        while True:
            current_page_url = f"{self.base_url}?b_start:int={current_offset}"
            should_continue, items_per_page = self.scrape_page(current_page_url)

            # If no items were found, break the loop to avoid infinite requests
            if items_per_page == 0:
                logging.info(f"No more news items found. Stopping.")
                break

            if not should_continue:
                break

            # Increment the offset only if items were found
            current_offset += items_per_page
            logging.info(f"Moving to next page with offset {current_offset}")

        # Save the scraped data to a JSON file
        self.save_news_to_json()

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

        # Second html structure type
        if not news_items:
            news_items = soup.find("ul", class_="noticias").find_all("li")

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
                )  # Stop if news older than max_date is found

        return True, items_per_page

    def extract_news_info(self, item) -> Optional[Dict[str, str]]:
        """
        Extract the news information from an HTML element.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: A dictionary containing the news data or None if the news is older than the max_date.
        """
        title, url = self.extract_title_and_url(item)
        category = self.extract_category(item)
        news_date = self.extract_date(item)
        if news_date and news_date < self.max_date:
            logging.info(
                f"Stopping scrape. Found news older than max date: {news_date.strftime('%Y-%m-%d')}"
            )
            return None
        tags = self.extract_tags(item)
        content = self.get_article_content(url)

        return {
            "title": title,
            "url": url,
            "date": news_date.strftime("%Y-%m-%d") if news_date else "Unknown Date",
            "category": category,
            "tags": tags,
            "content": content,
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

    def extract_date(self, item) -> Optional[datetime]:
        result = self.extract_date_1(item)
        if not result:
            result = self.extract_date_2(item)

        if not result:
            logging.error(f"\n\nNo date found!\n")

        return result

    def extract_date_1(self, item) -> Optional[datetime]:
        """
        Extract the date from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime object or None if the date is invalid.
        """
        date_tag = item.find("span", class_="documentByLine")
        date_str = date_tag.get_text().strip() if date_tag else "No Date"
        date_parts = date_str.split()
        clean_date_str = date_parts[1] if len(date_parts) > 1 else "No Date"

        try:
            return datetime.strptime(clean_date_str, "%d/%m/%Y")
        except ValueError:
            return None

    def extract_date_2(self, item) -> Optional[datetime]:
        """
        Extract the date from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime object or None if the date is invalid.
        """
        date_tag = item.find("span", class_="data")

        # Extract the date string
        date_str = date_tag.get_text().strip() if date_tag else None

        if not date_str:
            return None

        # Try to extract the date from the string using common date formats
        try:
            # Assuming the format is 'dd/mm/yyyy' as per your previous script
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
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
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            article_body = soup.find("div", id="content-core")
            return (
                article_body.get_text().strip() if article_body else "No content found"
            )
        except Exception as e:
            logging.error(f"Error retrieving content from {url}: {str(e)}")
            return "Error retrieving content"

    def save_news_to_json(self):
        """
        Save the scraped news data to a JSON file in the raw_extractions/agency folder.
        """
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Create a folder for each agency inside raw_extractions
        agency_folder = os.path.join(DESTINATION_FOLDER, self.agency)
        if not os.path.exists(agency_folder):
            os.makedirs(agency_folder)

        # Save one JSON file for each day
        for news_item in self.news_data:
            news_date = news_item["date"]
            filename = f"{self.agency}_{news_date}.json"
            filepath = os.path.join(agency_folder, filename)

            # Append to the existing JSON file if it exists, otherwise create a new one
            if os.path.exists(filepath):
                with open(filepath, "r+", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_data.append(news_item)
                    f.seek(0)
                    json.dump(existing_data, f, ensure_ascii=False, indent=4)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([news_item], f, ensure_ascii=False, indent=4)

        logging.info(f"News data saved to {agency_folder}")

    # List of URLs to scrape

    def json_file_exists(self) -> bool:
        """
        Check if the JSON file for the current scraping already exists.

        :return: True if the file exists, False otherwise.
        """
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = (
            f"{self.agency}_{self.max_date.strftime('%Y-%m-%d')}_{current_date}.json"
        )
        filepath = os.path.join(DESTINATION_FOLDER, filename)
        return os.path.exists(filepath)


def create_scrapers(urls: List[str], max_date: str) -> List[GovBRNewsScraper]:
    """
    Create a list of GovBRNewsScraper instances for each URL.

    :param urls: List of URLs to scrape.
    :param max_date: The maximum date for scraping news.
    :return: List of GovBRNewsScraper instances.
    """
    return [GovBRNewsScraper(max_date, url) for url in urls]


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Scrape news from multiple gov.br agencies up to a given date."
    )
    parser.add_argument(
        "max_date", help="The maximum date for scraping news (format: YYYY-MM-DD)"
    )
    args = parser.parse_args()

    urls = list(load_urls_from_yaml("site_urls.yaml").values())

    # Create scrapers for each URL
    scrapers = create_scrapers(urls, args.max_date)

    # Run scrapers in parallel with a maximum of 10 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(scraper.scrape_news) for scraper in scrapers]
        concurrent.futures.wait(futures)


if __name__ == "__main__":
    main()
