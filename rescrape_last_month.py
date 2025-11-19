#!/usr/bin/env python3
"""
Re-scrape the last month of news articles to update the dataset with improved metadata.
This script will:
1. Scrape all agencies from the last 30 days
2. Update existing articles with new fields (tags, editorial_lead, subtitle, improved categories)
3. Use allow_update=True to overwrite existing entries

Usage:
    poetry run python rescrape_last_month.py [--agencies AGENCY1 AGENCY2 ...] [--days N]

Examples:
    # Re-scrape all agencies for last 30 days (default)
    poetry run python rescrape_last_month.py

    # Re-scrape specific agencies for last 30 days
    poetry run python rescrape_last_month.py --agencies secom agricultura mec

    # Re-scrape all agencies for last 7 days
    poetry run python rescrape_last_month.py --days 7
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dataset_manager import DatasetManager
from scraper.scrape_manager import ScrapeManager
from scraper.ebc_scrape_manager import EBCScrapeManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def main():
    parser = argparse.ArgumentParser(
        description='Re-scrape last month of news to update metadata'
    )
    parser.add_argument(
        '--agencies',
        nargs='+',
        help='Specific agencies to scrape (default: all agencies)',
        default=None
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to go back (default: 30)'
    )
    parser.add_argument(
        '--sequential',
        action='store_true',
        help='Process agencies sequentially instead of in bulk'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt (auto-confirm)'
    )

    args = parser.parse_args()

    # Calculate date range
    today = datetime.now().date()
    start_date = today - timedelta(days=args.days)

    logging.info("="*80)
    logging.info("GOVBRNEWS RE-SCRAPING - METADATA UPDATE")
    logging.info("="*80)
    logging.info(f"Date range: {start_date} to {today}")
    logging.info(f"Days: {args.days}")
    logging.info(f"Agencies: {args.agencies if args.agencies else 'ALL'}")
    logging.info(f"Mode: {'Sequential' if args.sequential else 'Bulk'}")
    logging.info(f"Update mode: ENABLED (will overwrite existing entries)")
    logging.info("="*80)

    # Confirm before proceeding (skip if --yes flag is used)
    if not args.yes:
        response = input("\nThis will UPDATE existing articles in the dataset. Continue? (y/n): ")
        if response.lower() != 'y':
            logging.info("Cancelled by user.")
            return
    else:
        logging.info("Auto-confirmed (--yes flag used)")
        logging.info("")

    try:
        # Initialize dataset manager
        dataset_manager = DatasetManager()

        # Re-scrape gov.br agencies
        logging.info("\n" + "="*80)
        logging.info("STEP 1: Re-scraping GOV.BR agencies")
        logging.info("="*80)

        scrape_manager = ScrapeManager(dataset_manager)
        scrape_manager.run_scraper(
            agencies=args.agencies,
            min_date=start_date.strftime('%Y-%m-%d'),
            max_date=today.strftime('%Y-%m-%d'),
            sequential=args.sequential,
            allow_update=True  # IMPORTANT: This enables updating existing entries
        )

        # Re-scrape EBC sources
        logging.info("\n" + "="*80)
        logging.info("STEP 2: Re-scraping EBC sources (Agência Brasil + TV Brasil)")
        logging.info("="*80)

        ebc_manager = EBCScrapeManager(dataset_manager)
        ebc_manager.run_scraper(
            min_date=start_date.strftime('%Y-%m-%d'),
            max_date=today.strftime('%Y-%m-%d'),
            sequential=True,  # EBC always sequential
            allow_update=True  # IMPORTANT: This enables updating existing entries
        )

        logging.info("\n" + "="*80)
        logging.info("RE-SCRAPING COMPLETED SUCCESSFULLY!")
        logging.info("="*80)
        logging.info(f"Updated articles from {start_date} to {today}")
        logging.info("New fields added: tags, editorial_lead, subtitle")
        logging.info("Categories improved with fallback strategy")
        logging.info("="*80)

    except Exception as e:
        logging.error(f"\n{'='*80}")
        logging.error(f"ERROR DURING RE-SCRAPING: {e}")
        logging.error(f"{'='*80}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
