import logging
import random
import time
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SLEEP_TIME_INTERVAL = (1, 3)


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
