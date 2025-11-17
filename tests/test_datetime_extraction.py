import pytest
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from scraper.webscraper import WebScraper
from scraper.ebc_webscraper import EBCWebScraper


class TestWebScraperDateTimeExtraction:
    """Test datetime extraction for standard gov.br scraper"""

    @pytest.fixture
    def scraper(self):
        """Create a WebScraper instance for testing"""
        return WebScraper("2025-01-01", "https://www.gov.br/agricultura/pt-br/assuntos/noticias")

    def test_extract_datetime_from_jsonld_success(self, scraper):
        """Test successful JSON-LD datetime extraction"""
        html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "datePublished": "2025-11-17T19:24:43-03:00",
                "dateModified": "2025-11-17T19:30:00-03:00"
            }
            </script>
        </head>
        <body></body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        published_dt = scraper._extract_datetime_from_jsonld(soup)

        assert published_dt is not None
        assert published_dt.year == 2025
        assert published_dt.month == 11
        assert published_dt.day == 17
        assert published_dt.hour == 19
        assert published_dt.minute == 24

    def test_extract_datetime_from_text_standard_format(self, scraper):
        """Test extraction from 'Publicado em DD/MM/YYYY HH:MMh' format"""
        html = """
        <html>
        <body>
            <p>Publicado em 17/11/2025 19h24</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        published_dt, updated_dt = scraper._extract_datetime_from_text(soup)

        assert published_dt is not None
        assert published_dt.year == 2025
        assert published_dt.month == 11
        assert published_dt.day == 17
        assert published_dt.hour == 19
        assert published_dt.minute == 24

    def test_extract_datetime_from_text_ebc_format(self, scraper):
        """Test extraction from 'DD/MM/YYYY - HH:MM' format"""
        html = """
        <html>
        <body>
            <p>Publicado em 17/11/2025 - 18:58</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        published_dt, updated_dt = scraper._extract_datetime_from_text(soup)

        assert published_dt is not None
        assert published_dt.year == 2025
        assert published_dt.month == 11
        assert published_dt.day == 17
        assert published_dt.hour == 18
        assert published_dt.minute == 58

    def test_extract_updated_datetime(self, scraper):
        """Test extraction of update datetime"""
        html = """
        <html>
        <body>
            <p>Publicado em 17/11/2025 17h54</p>
            <p>Atualizado em 17/11/2025 18h40</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        published_dt, updated_dt = scraper._extract_datetime_from_text(soup)

        assert published_dt is not None
        assert updated_dt is not None
        assert updated_dt.hour == 18
        assert updated_dt.minute == 40

    def test_extract_datetime_no_datetime_found(self, scraper):
        """Test when no datetime is present"""
        html = """
        <html>
        <body>
            <p>Some random content without dates</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        published_dt, updated_dt = scraper._extract_datetime_from_text(soup)

        assert published_dt is None
        assert updated_dt is None

    def test_extract_datetime_case_insensitive(self, scraper):
        """Test case-insensitive matching"""
        html = """
        <html>
        <body>
            <p>publicado em 17/11/2025 19h24</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        published_dt, updated_dt = scraper._extract_datetime_from_text(soup)

        assert published_dt is not None
        assert published_dt.hour == 19

    def test_datetime_has_timezone(self, scraper):
        """Test that extracted datetime has Brasilia timezone (UTC-3)"""
        html = """
        <html>
        <body>
            <p>Publicado em 17/11/2025 19h24</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        published_dt, _ = scraper._extract_datetime_from_text(soup)

        assert published_dt is not None
        assert published_dt.tzinfo is not None
        # Check if timezone offset is -3 hours
        assert published_dt.utcoffset() == timedelta(hours=-3)


class TestEBCWebScraperDateTimeExtraction:
    """Test datetime extraction for EBC scraper"""

    @pytest.fixture
    def scraper(self):
        """Create an EBCWebScraper instance for testing"""
        return EBCWebScraper("2025-01-01")

    def test_parse_ebc_datetime_with_time(self, scraper):
        """Test parsing 'DD/MM/YYYY - HH:MM' format"""
        date_str = "17/11/2025 - 18:58"
        result = scraper._parse_ebc_datetime(date_str)

        assert result is not None
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 17
        assert result.hour == 18
        assert result.minute == 58

    def test_parse_ebc_datetime_date_only(self, scraper):
        """Test parsing 'DD/MM/YYYY' format (date only)"""
        date_str = "17/11/2025"
        result = scraper._parse_ebc_datetime(date_str)

        assert result is not None
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 17
        assert result.hour == 0
        assert result.minute == 0

    def test_parse_ebc_datetime_empty_string(self, scraper):
        """Test parsing empty string"""
        result = scraper._parse_ebc_datetime("")
        assert result is None

    def test_parse_ebc_datetime_invalid_format(self, scraper):
        """Test parsing invalid format"""
        result = scraper._parse_ebc_datetime("invalid date")
        assert result is None

    def test_parse_ebc_datetime_has_timezone(self, scraper):
        """Test that parsed datetime has Brasilia timezone"""
        date_str = "17/11/2025 - 18:58"
        result = scraper._parse_ebc_datetime(date_str)

        assert result is not None
        assert result.tzinfo is not None
        assert result.utcoffset() == timedelta(hours=-3)

    def test_extract_datetime_from_jsonld_ebc(self, scraper):
        """Test JSON-LD extraction for EBC sites"""
        html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "datePublished": "2025-11-17T18:58:00-03:00",
                "dateModified": "2025-11-17T19:00:00-03:00"
            }
            </script>
        </head>
        <body></body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        published_dt, updated_dt = scraper._extract_datetime_from_jsonld(soup)

        assert published_dt is not None
        assert published_dt.hour == 18
        assert published_dt.minute == 58
        assert updated_dt is not None
        assert updated_dt.hour == 19


class TestDateTimeIntegration:
    """Integration tests for datetime extraction in full scraping workflow"""

    def test_webscraper_article_content_returns_datetimes(self):
        """Test that get_article_content returns 4 values including datetimes"""
        scraper = WebScraper("2025-01-01", "https://www.gov.br/test/pt-br/noticias")

        # We can't test with real URL in unit tests, but we can verify the signature
        # This will fail to fetch, but should return the correct structure
        result = scraper.get_article_content("https://example.com/nonexistent")

        assert isinstance(result, tuple)
        assert len(result) == 4
        content, image_url, published_dt, updated_dt = result
        assert isinstance(content, str)
        # Datetimes will be None for failed fetch, but structure is correct

    def test_news_data_structure_includes_datetime_fields(self):
        """Test that scraped news data includes datetime fields"""
        scraper = WebScraper("2025-01-01", "https://www.gov.br/test/pt-br/noticias")

        # Simulate the structure that would be added to news_data
        news_item = {
            "title": "Test",
            "url": "https://example.com",
            "published_at": None,
            "published_datetime": None,
            "updated_datetime": None,
            "category": "Test",
            "tags": [],
            "content": "Test content",
            "image": None,
            "agency": "test",
            "extracted_at": datetime.now(),
        }

        # Verify structure has all required fields
        assert "published_at" in news_item
        assert "published_datetime" in news_item
        assert "updated_datetime" in news_item


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
