import argparse
import logging
import os
from typing import List

import yaml
from dataset_manager import DatasetManager
from dotenv import load_dotenv
from govbrnews_scraper import GovBRNewsScraper

# Load environment variables from the .env file
load_dotenv()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_urls_from_yaml(file_name: str) -> List[str]:
    """
    Load URLs from a YAML file located in the same directory as this script.

    :param file_name: The name of the YAML file.
    :return: A list of URLs.
    """
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the full path to the YAML file
    file_path = os.path.join(script_dir, file_name)

    with open(file_path, "r") as f:
        agencies = yaml.safe_load(f)["agencies"]
        return list(agencies.values())


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

    urls = load_urls_from_yaml("site_urls.yaml")
    scrapers = create_scrapers(urls, args.min_date)

    all_news_data = []

    for scraper in scrapers:
        news_data = scraper.scrape_news()
        all_news_data.extend(news_data)

    # After collecting all news data, append to the dataset
    dataset_manager = DatasetManager()
    dataset_manager.append_to_huggingface_dataset(all_news_data)


if __name__ == "__main__":
    main()
