import argparse
import logging
import os

from dotenv import load_dotenv
from news_analyzer import NewsAnalyzer
from news_processor import NewsProcessor

# Load environment variables from the .env file
load_dotenv()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Process news files and classify AI-related articles."
    )
    parser.add_argument(
        "--openai_api_key",
        type=str,
        default=None,
        help="OpenAI API key (if not provided, will use OPENAI_API_KEY environment variable).",
    )
    parser.add_argument(
        "--min_date",
        type=str,
        default=None,
        help="Minimum date to process files from (format: 'YYYY-MM-DD').",
    )
    parser.add_argument(
        "--agency",
        type=str,
        default=None,
        help="Agency to filter the files by.",
    )
    args = parser.parse_args()

    # Fetch the OpenAI API key from arguments or environment variable
    openai_api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OpenAI API key must be provided.")

    # Initialize the NewsAnalyzer
    analyzer = NewsAnalyzer(openai_api_key=openai_api_key)

    # Initialize the NewsProcessor with the analyzer
    processor = NewsProcessor(analyzer=analyzer)

    # Pass the min_date and agency to the process_files method
    processor.process_files(min_date=args.min_date, agency=args.agency)
