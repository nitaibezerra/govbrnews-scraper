#!/usr/bin/env python3
"""
Test script to verify datetime extraction from real news articles.
Tests 5 different agencies and 2 EBC sources.
"""

import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scraper.webscraper import WebScraper
from scraper.ebc_webscraper import EBCWebScraper


def test_standard_scraper():
    """Test datetime extraction from standard gov.br agencies"""

    # Test 5 different agencies
    test_agencies = [
        ("agricultura", "https://www.gov.br/agricultura/pt-br/assuntos/noticias"),
        ("cgu", "https://www.gov.br/cgu/pt-br/assuntos/noticias/ultimas-noticias"),
        ("mec", "https://www.gov.br/mec/pt-br/assuntos/noticias"),
        ("receitafederal", "https://www.gov.br/receitafederal/pt-br/assuntos/noticias"),
        ("turismo", "https://www.gov.br/turismo/pt-br/assuntos/noticias"),
    ]

    print("=" * 80)
    print("TESTING STANDARD GOV.BR SCRAPER")
    print("=" * 80)

    # Use yesterday as date range (more likely to have news)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    for agency_name, url in test_agencies:
        print(f"\n{'='*80}")
        print(f"Testing: {agency_name}")
        print(f"URL: {url}")
        print(f"{'='*80}")

        try:
            scraper = WebScraper(yesterday, url, max_date=today)
            news_data = scraper.scrape_news()

            if news_data:
                # Get first article
                article = news_data[0]

                print(f"\n✓ Successfully scraped {len(news_data)} article(s)")
                print(f"\nFirst Article Details:")
                print(f"  Title: {article.get('title', 'N/A')[:80]}...")
                print(f"  URL: {article.get('url', 'N/A')}")
                print(f"  published_at (date): {article.get('published_at')}")
                print(f"  published_datetime: {article.get('published_datetime')}")
                print(f"  updated_datetime: {article.get('updated_datetime')}")

                # Validate datetime extraction
                if article.get('published_datetime'):
                    print(f"\n  ✓ DATETIME EXTRACTION SUCCESSFUL")
                    print(f"  Timezone: {article['published_datetime'].tzinfo}")
                    print(f"  ISO format: {article['published_datetime'].isoformat()}")
                else:
                    print(f"\n  ✗ WARNING: No datetime extracted (only date)")

                if article.get('updated_datetime'):
                    print(f"  ✓ Update datetime also extracted: {article['updated_datetime']}")

            else:
                print(f"✗ No news found for date range {yesterday} to {today}")

        except Exception as e:
            print(f"✗ Error testing {agency_name}: {str(e)}")

    print(f"\n{'='*80}\n")


def test_ebc_scraper():
    """Test datetime extraction from EBC sources"""

    print("=" * 80)
    print("TESTING EBC SCRAPER (Agência Brasil + TV Brasil)")
    print("=" * 80)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        scraper = EBCWebScraper(yesterday, max_date=today)

        print(f"\nScraping EBC news from {yesterday} to {today}...")
        news_data = scraper.scrape_news()

        if news_data:
            print(f"\n✓ Successfully scraped {len(news_data)} article(s)")

            # Show first few articles
            for i, article in enumerate(news_data[:3], 1):
                print(f"\n{'─'*80}")
                print(f"Article {i}:")
                print(f"  Agency: {article.get('agency', 'N/A')}")
                print(f"  Title: {article.get('title', 'N/A')[:80]}...")
                print(f"  URL: {article.get('url', 'N/A')}")
                print(f"  date (string): {article.get('date')}")
                print(f"  published_datetime: {article.get('published_datetime')}")
                print(f"  updated_datetime: {article.get('updated_datetime')}")

                if article.get('published_datetime'):
                    print(f"\n  ✓ DATETIME EXTRACTION SUCCESSFUL")
                    print(f"  Timezone: {article['published_datetime'].tzinfo}")
                    print(f"  ISO format: {article['published_datetime'].isoformat()}")
                else:
                    print(f"\n  ✗ WARNING: No datetime extracted")

        else:
            print(f"✗ No EBC news found for date range {yesterday} to {today}")

    except Exception as e:
        print(f"✗ Error testing EBC scraper: {str(e)}")

    print(f"\n{'='*80}\n")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("DATETIME EXTRACTION TEST - REAL NEWS SCRAPING")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    # Test standard scraper
    test_standard_scraper()

    # Test EBC scraper
    test_ebc_scraper()

    print("="*80)
    print("TESTS COMPLETED")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
