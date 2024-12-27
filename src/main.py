import argparse
import logging
from scraper.scrape_manager import run_scraper
from augment_news.news_analyzer import NewsAnalyzer
from augment_news.news_processor import NewsProcessor
from dotenv import load_dotenv

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
# Augmentation-Related Function
# -------------------------------------------------------------------------------------


def run_augment(args):
    """
    Executes the augmentation (news classification) logic using the arguments
    provided by the 'augment' subcommand.
    """
    # Initialize the NewsAnalyzer and NewsProcessor
    analyzer = NewsAnalyzer()
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
        run_scraper(args.agency, args.min_date, args.max_date, args.sequential)
    elif args.command == "augment":
        run_augment(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
