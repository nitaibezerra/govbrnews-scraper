import argparse
import logging
import os
from typing import List, Dict

import yaml
from data_processor import DataProcessor
from dataset_uploader import HuggingFaceDatasetUploader
from dotenv import load_dotenv
from govbrnews_scraper import GovBRNewsScraper

# Load environment variables from the .env file
load_dotenv()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DATASET_PATH = "nitaibezerra/govbrnews"  # The name of the Hugging Face dataset


def load_urls_from_yaml(file_name: str, agency: str = None) -> List[str]:
    """
    Load URLs from a YAML file located in the same directory as this script.

    :param file_name: The name of the YAML file.
    :param agency: Specific agency key to filter URLs. If None, load all URLs.
    :return: A list of URLs.
    """
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the full path to the YAML file
    file_path = os.path.join(script_dir, file_name)

    with open(file_path, "r") as f:
        agencies = yaml.safe_load(f)["agencies"]

    if agency:
        if agency in agencies:
            return [agencies[agency]]
        else:
            raise ValueError(f"Agency '{agency}' not found in the YAML file.")

    return list(agencies.values())


def create_scrapers(urls: List[str], min_date: str) -> List[GovBRNewsScraper]:
    """
    Create a list of GovBRNewsScraper instances for each URL.

    :param urls: List of URLs to scrape.
    :param min_date: The minimum date for scraping news.
    :return: List of GovBRNewsScraper instances.
    """
    return [GovBRNewsScraper(min_date, url) for url in urls]


def process_and_upload_data(
    news_data: List[Dict[str, str]],
    data_processor: DataProcessor,
    uploader: HuggingFaceDatasetUploader,
):
    """
    Process the news data and upload it to the Hugging Face dataset.

    :param news_data: List of news items as dictionaries.
    :param data_processor: An instance of DataProcessor.
    :param uploader: An instance of HuggingFaceDatasetUploader.
    """
    # Data preprocessing
    new_data = data_processor.preprocess_data(news_data)
    combined_data = data_processor.load_existing_and_merge_with_new(new_data)
    sorted_data = data_processor.sort_combined_data(combined_data)
    column_data = data_processor.convert_to_columnar_format(sorted_data)
    # Create and push the dataset
    uploader.create_and_push_dataset(column_data)


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
    parser.add_argument(
        "--agency",
        help="The agency key to scrape news for a specific agency.",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Process and upload each agency's news sequentially, one at a time.",
    )
    args = parser.parse_args()

    try:
        urls = load_urls_from_yaml("site_urls.yaml", args.agency)
        scrapers = create_scrapers(urls, args.min_date)

        # Initialize the DataProcessor and HuggingFaceDatasetUploader
        data_processor = DataProcessor(DATASET_PATH)
        uploader = HuggingFaceDatasetUploader(DATASET_PATH)

        if args.sequential:
            # Process each agency's news sequentially
            for scraper in scrapers:
                news_data = scraper.scrape_news()
                if news_data:
                    logging.info(
                        f"Appending news for {scraper.agency} to Hugging Face dataset."
                    )
                    process_and_upload_data(news_data, data_processor, uploader)
                else:
                    logging.info(f"No news found for {scraper.agency}.")
        else:
            # Accumulate all news and process together
            all_news_data = []
            for scraper in scrapers:
                news_data = scraper.scrape_news()
                if news_data:
                    all_news_data.extend(news_data)
                else:
                    logging.info(f"No news found for {scraper.agency}.")

            if all_news_data:
                logging.info("Appending all collected news to Hugging Face dataset.")
                process_and_upload_data(all_news_data, data_processor, uploader)
            else:
                logging.info("No news found for any agency.")
    except ValueError as e:
        logging.error(e)


if __name__ == "__main__":
    main()
