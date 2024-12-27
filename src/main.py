import argparse
import logging

from augment_news.classifier_summarizer import ClassifierSummarizer
from augment_news.news_processor import NewsProcessor
from dataset_manager import DatasetManager
from dotenv import load_dotenv
from scraper.scrape_manager import ScrapeManager

# -------------------------------------------------------------------------------------
# Common Initialization
# -------------------------------------------------------------------------------------

# Load environment variables from .env
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def run_scraper(args):
    """
    Executes the scraper logic using the arguments provided by the 'scrape' subcommand.
    """
    dataset_manager = DatasetManager()
    scrape_manager = ScrapeManager(dataset_manager)
    scrape_manager.run_scraper(
        args.agency, args.min_date, args.max_date, args.sequential
    )


# -------------------------------------------------------------------------------------
# Augmentation-Related Function
# -------------------------------------------------------------------------------------


def run_augment(args):
    """
    Executes the augmentation (news classification) logic using the arguments
    provided by the 'augment' subcommand.
    """
    # Initialize the ClassifierSummarizer and NewsProcessor
    inference_engine = ClassifierSummarizer()
    processor = NewsProcessor(inference_engine=inference_engine)

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
