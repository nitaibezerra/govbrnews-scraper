import argparse
import logging

from augmentation.augmentation_manager import AugmentationManager
from dataset_manager import DatasetManager
from dotenv import load_dotenv
from scraper.scrape_manager import ScrapeManager

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

    # Convert agency input into a list (comma-separated values)
    agencies = args.agencies.split(",") if args.agencies else None

    scrape_manager.run_scraper(
        agencies, args.min_date, args.max_date, args.sequential, args.allow_update
    )


# -------------------------------------------------------------------------------------
# Augmentation-Related Function
# -------------------------------------------------------------------------------------


def run_augment(args):
    """
    Executes the augmentation (news classification) logic using the arguments
    provided by the 'augment' subcommand.
    """
    # If no max_date is provided, default to something like "2100-12-31"
    if not args.max_date:
        args.max_date = "2100-12-31"

    augmentation_manager = AugmentationManager()

    # Pass agencies (if provided), along with the date range
    augmentation_manager.classify_and_update_dataset(
        min_date=args.min_date, max_date=args.max_date, agency=args.agencies
    )


# -------------------------------------------------------------------------------------
# Main: Sets up subcommands and dispatches to run_scraper or run_augment
# -------------------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Main entry point to run either the scraper or the news augmentation."
    )

    # Create subparsers for 'scrape' and 'augment'
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
        "--agencies",
        help="Scrape news for specific agencies (comma-separated, e.g., 'gestao,saude'). Leave empty to scrape all.",
    )
    scraper_parser.add_argument(
        "--sequential",
        action="store_true",
        help="Process and upload each agency's news sequentially.",
    )
    scraper_parser.add_argument(
        "--allow-update",
        action="store_true",
        help="If set, overwrite existing entries in the dataset instead of skipping them.",
    )

    # ------------------ AUGMENT SUBPARSER ------------------
    augment_parser = subparsers.add_parser(
        "augment", help="Process news files and classify articles."
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
        "--max-date",
        type=str,
        default=None,
        help="Maximum date to process files up to (format: 'YYYY-MM-DD').",
    )
    augment_parser.add_argument(
        "--agencies",
        type=str,
        default=None,
        help="Agencies to filter the files by (comma-separated list).",
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
