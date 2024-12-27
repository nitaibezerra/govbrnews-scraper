import argparse
import logging
import os
from typing import List

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


def run_scraper(args):
    """
    Executes the scraping logic using the arguments provided by the 'scraper' subcommand.
    """
    try:
        urls = load_urls_from_yaml("scraper/site_urls.yaml", args.agency)
        scrapers = [
            WebScraper(args.min_date, url, max_date=args.max_date) for url in urls
        ]

        # Initialize the DatasetManager and DataProcessor
        dataset_manager = DatasetManager()
        data_processor = DataProcessor(dataset_manager=dataset_manager)

        if args.sequential:
            # Process each agency's news sequentially
            for scraper in scrapers:
                scraped_data = scraper.scrape_news()
                if scraped_data:
                    logging.info(f"Appending news for {scraper.agency} to HF dataset.")
                    data_processor.process_and_upload_data(scraped_data)
                else:
                    logging.info(f"No news found for {scraper.agency}.")
        else:
            # Accumulate all news and process together
            all_news_data = []
            for scraper in scrapers:
                scraped_data = scraper.scrape_news()
                if scraped_data:
                    all_news_data.extend(scraped_data)
                else:
                    logging.info(f"No news found for {scraper.agency}.")

            if all_news_data:
                logging.info("Appending all collected news to HF dataset.")
                data_processor.process_and_upload_data(all_news_data)
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
        "scrape", help="Scrape news data and upload to a Hugging Face dataset."
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

    if args.command == "scrape":
        run_scraper(args)
    elif args.command == "augment":
        run_augment(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
