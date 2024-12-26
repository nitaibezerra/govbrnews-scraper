import argparse
import logging
import os
from typing import Dict, List

import yaml
from augment_news.news_analyzer import NewsAnalyzer
from augment_news.news_processor import NewsProcessor
from dataset_manager import DatasetManager
from dotenv import load_dotenv
from scraper.data_processor import DataProcessor
from scraper.webscraper import WebScraper

# -------------------------------------------------------------------------------------
# Common Initialization
# -------------------------------------------------------------------------------------

# Load environment variables from .env
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DATASET_PATH = "nitaibezerra/govbrnews"  # The name of the Hugging Face dataset

# -------------------------------------------------------------------------------------
# Scraper-Related Functions
# -------------------------------------------------------------------------------------


def load_urls_from_yaml(file_name: str, agency: str = None) -> List[str]:
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


def create_scrapers(urls: List[str], min_date: str, max_date: str = None):
    """
    Create a list of WebScraper instances for each URL.
    """
    return [WebScraper(min_date, url, max_date=max_date) for url in urls]


def process_and_upload_data(
    news_data,
    data_processor,
    dataset_manager,
):
    """
    Process the news data and upload it to the Hugging Face dataset.
    """
    new_data = data_processor.preprocess_data(news_data)
    existing_data = dataset_manager.load_existing_dataset()
    combined_data = data_processor.load_existing_and_merge_with_new(
        new_data, existing_data
    )
    sorted_data = data_processor.sort_combined_data(combined_data)
    column_data = data_processor.convert_to_columnar_format(sorted_data)

    dataset_manager.create_and_push_dataset(column_data)


def run_scraper(args):
    """
    Executes the scraping logic using the arguments provided by the 'scraper' subcommand.
    """
    try:
        urls = load_urls_from_yaml("scraper/site_urls.yaml", args.agency)
        scrapers = create_scrapers(urls, args.min_date, args.max_date)

        # Initialize the DataProcessor and DatasetManager
        data_processor = DataProcessor(DATASET_PATH)
        dataset_manager = DatasetManager(DATASET_PATH)

        if args.sequential:
            # Process each agency's news sequentially
            for scraper in scrapers:
                news_data = scraper.scrape_news()
                if news_data:
                    logging.info(f"Appending news for {scraper.agency} to HF dataset.")
                    process_and_upload_data(news_data, data_processor, dataset_manager)
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
                logging.info("Appending all collected news to HF dataset.")
                process_and_upload_data(all_news_data, data_processor, dataset_manager)
            else:
                logging.info("No news found for any agency.")
    except ValueError as e:
        logging.error(e)


# -------------------------------------------------------------------------------------
# Augmentation-Related Function
# -------------------------------------------------------------------------------------


def run_augment(args):
    """
    Executes the augmentation (news classification) logic using the arguments
    provided by the 'augment' subcommand.
    """
    openai_api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OpenAI API key must be provided.")

    # Initialize the NewsAnalyzer and NewsProcessor
    analyzer = NewsAnalyzer(openai_api_key=openai_api_key)
    processor = NewsProcessor(analyzer=analyzer)

    # Process the files (e.g., classify AI-related articles)
    processor.process_files(min_date=args.min_date, agency=args.agency)


# -------------------------------------------------------------------------------------
# Main: Sets up subcommands and dispatches to run_scraper or run_augment
# -------------------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Main entry point to run either the scraper or the news augmentation."
    )

    # Create subparsers for 'scraper' and 'augment'
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to run.")

    # ------------------ SCRAPER SUBPARSER ------------------
    scraper_parser = subparsers.add_parser(
        "scraper", help="Scrape news data and upload to a Hugging Face dataset."
    )
    scraper_parser.add_argument(
        "--min-date",
        required=True,
        help="The minimum date for scraping news (format: YYYY-MM-DD).",
    )
    scraper_parser.add_argument(
        "--max-date",
        help="The maximum date for scraping news (format: YYYY-MM-DD).",
    )
    scraper_parser.add_argument(
        "--agency",
        help="Scrape news for a specific agency (key in the YAML).",
    )
    scraper_parser.add_argument(
        "--sequential",
        action="store_true",
        help="Process and upload each agency's news sequentially.",
    )

    # ------------------ AUGMENT SUBPARSER ------------------
    augment_parser = subparsers.add_parser(
        "augment", help="Process news files and classify AI-related articles."
    )
    augment_parser.add_argument(
        "--openai_api_key",
        type=str,
        default=None,
        help="OpenAI API key (will use OPENAI_API_KEY env var if not provided).",
    )
    augment_parser.add_argument(
        "--min-date",
        type=str,
        default=None,
        help="Minimum date to process files from (format: 'YYYY-MM-DD').",
    )
    augment_parser.add_argument(
        "--agency",
        type=str,
        default=None,
        help="Agency to filter the files by.",
    )

    # Parse the command-line arguments and dispatch
    args = parser.parse_args()

    if args.command == "scraper":
        run_scraper(args)
    elif args.command == "augment":
        run_augment(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
