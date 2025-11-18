#!/usr/bin/env python3
"""
Test script to verify extraction of new fields (tags, editorial_lead, subtitle, category)
from real news articles for both standard gov.br agencies and EBC sources.
"""

import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scraper.webscraper import WebScraper
from scraper.ebc_webscraper import EBCWebScraper


def test_standard_scraper():
    """Test new field extraction from standard gov.br agencies"""

    # Test with SECOM (has editorial leads) and other agencies
    test_agencies = [
        ("secom", "https://www.gov.br/secom/pt-br/assuntos/noticias"),
        ("agricultura", "https://www.gov.br/agricultura/pt-br/assuntos/noticias"),
        ("mec", "https://www.gov.br/mec/pt-br/assuntos/noticias"),
    ]

    print("=" * 80)
    print("TESTING STANDARD GOV.BR SCRAPER - NEW FIELDS")
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

                # Test new fields
                print(f"\n  NEW FIELDS:")
                print(f"  ───────────")

                # Tags
                tags = article.get('tags', [])
                print(f"  Tags ({len(tags)}): {tags if tags else '(empty)'}")
                if tags:
                    print(f"    ✓ TAGS EXTRACTED SUCCESSFULLY")
                else:
                    print(f"    ⚠ No tags found (may be normal for this article)")

                # Editorial Lead
                editorial_lead = article.get('editorial_lead')
                print(f"  Editorial Lead: {editorial_lead if editorial_lead else '(none)'}")
                if editorial_lead:
                    print(f"    ✓ EDITORIAL LEAD EXTRACTED")

                # Subtitle
                subtitle = article.get('subtitle')
                print(f"  Subtitle: {subtitle[:80] + '...' if subtitle and len(subtitle) > 80 else subtitle if subtitle else '(none)'}")
                if subtitle:
                    print(f"    ✓ SUBTITLE EXTRACTED")

                # Category
                category = article.get('category', 'N/A')
                print(f"  Category: {category}")
                if category != "No Category":
                    print(f"    ✓ CATEGORY EXTRACTED")
                else:
                    print(f"    ⚠ No category (may indicate fallback needed)")

                # Content check (should NOT contain editorial_lead or subtitle as standalone element)
                content = article.get('content', '')
                # Check if editorial lead appears as a standalone line (not embedded in longer text)
                content_lines = [line.strip() for line in content.split('\n') if line.strip()]
                if editorial_lead:
                    # Check if editorial lead appears as standalone line
                    if editorial_lead in content_lines:
                        print(f"\n  ✗ WARNING: Editorial lead still in content as standalone element!")
                    else:
                        # Check if it's part of natural article text (acceptable)
                        if editorial_lead in content:
                            print(f"  ℹ Editorial lead appears in article text (natural mention - OK)")
                        else:
                            print(f"  ✓ Editorial lead properly removed from content")

                if subtitle and subtitle in content:
                    print(f"  ✗ WARNING: Subtitle still in content!")
                elif subtitle:
                    print(f"  ✓ Subtitle properly removed from content")

            else:
                print(f"✗ No news found for date range {yesterday} to {today}")

        except Exception as e:
            print(f"✗ Error testing {agency_name}: {str(e)}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*80}\n")


def test_ebc_scraper():
    """Test new field extraction from EBC sources"""

    print("=" * 80)
    print("TESTING EBC SCRAPER - NEW FIELDS (Tags)")
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

                # Test tags
                tags = article.get('tags', [])
                print(f"\n  NEW FIELD - Tags ({len(tags)}): {tags if tags else '(empty)'}")
                if tags:
                    print(f"    ✓ TAGS EXTRACTED FROM EBC PAGE")
                else:
                    print(f"    ⚠ No tags found (may be normal for this article)")

        else:
            print(f"✗ No EBC news found for date range {yesterday} to {today}")

    except Exception as e:
        print(f"✗ Error testing EBC scraper: {str(e)}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*80}\n")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("NEW FIELDS EXTRACTION TEST - REAL NEWS SCRAPING")
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
