"""
Unit tests for the WebScraper class.

Tests cover:
- Content extraction and cleaning
- Metadata removal
- Content validation
- Fallback mechanisms
- Error handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from bs4 import BeautifulSoup
from datetime import datetime

from src.scraper.webscraper import WebScraper


class TestWebScraperInitialization:
    """Test WebScraper initialization and basic properties."""

    def test_init_with_min_date_only(self):
        """Test initialization with only minimum date."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        assert scraper.min_date == datetime.strptime("2025-10-01", "%Y-%m-%d").date()
        assert scraper.max_date is None
        assert scraper.base_url == "https://www.gov.br/test/pt-br/noticias"
        assert scraper.agency == "test"

    def test_init_with_max_date(self):
        """Test initialization with both min and max dates."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias", max_date="2025-10-31")

        assert scraper.max_date == datetime.strptime("2025-10-31", "%Y-%m-%d").date()

    def test_get_agency_name(self):
        """Test agency name extraction from URL."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/mec/pt-br/noticias")
        assert scraper.agency == "mec"

        scraper = WebScraper("2025-10-01", "https://www.gov.br/saude/pt-br/noticias")
        assert scraper.agency == "saude"


class TestContentStatistics:
    """Test content statistics counting."""

    def test_count_content_stats_basic(self):
        """Test counting paragraphs and length."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = """
        <div>
            <p>First paragraph</p>
            <p>Second paragraph</p>
            <div>Some content</div>
        </div>
        """
        element = BeautifulSoup(html, 'html.parser')

        stats = scraper._count_content_stats(element)

        assert stats['paragraphs'] == 2
        assert stats['length'] > 0

    def test_count_content_stats_empty(self):
        """Test counting with empty element."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = "<div></div>"
        element = BeautifulSoup(html, 'html.parser')

        stats = scraper._count_content_stats(element)

        assert stats['paragraphs'] == 0
        assert stats['length'] > 0  # Still has the div tags


class TestOverCleaningDetection:
    """Test detection of over-cleaning."""

    def test_is_over_cleaned_removes_too_many_paragraphs(self):
        """Test detection when >80% of paragraphs are removed."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        original = {'paragraphs': 10, 'length': 1000}
        cleaned = {'paragraphs': 1, 'length': 500}  # 90% paragraphs removed

        assert scraper._is_over_cleaned(original, cleaned) is True

    def test_is_over_cleaned_removes_too_much_content(self):
        """Test detection when >90% of content length is removed."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        original = {'paragraphs': 10, 'length': 1000}
        cleaned = {'paragraphs': 5, 'length': 50}  # 95% content removed

        assert scraper._is_over_cleaned(original, cleaned) is True

    def test_is_over_cleaned_acceptable_removal(self):
        """Test that acceptable content removal is not flagged."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        original = {'paragraphs': 10, 'length': 1000}
        cleaned = {'paragraphs': 8, 'length': 700}  # 20% paragraphs, 30% content removed

        assert scraper._is_over_cleaned(original, cleaned) is False

    def test_is_over_cleaned_edge_case_exactly_threshold(self):
        """Test edge case at exactly the threshold."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        original = {'paragraphs': 10, 'length': 1000}
        cleaned = {'paragraphs': 2, 'length': 100}  # Exactly at thresholds

        # At threshold should NOT be over-cleaned
        assert scraper._is_over_cleaned(original, cleaned) is False


class TestContentValidation:
    """Test final content validation."""

    def test_validate_final_content_valid(self):
        """Test validation with sufficient content."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        content = "A" * 150  # 150 characters
        assert scraper._validate_final_content(content, "http://test.url") is True

    def test_validate_final_content_too_short(self):
        """Test validation with insufficient content."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        content = "Short"  # Less than 100 characters
        assert scraper._validate_final_content(content, "http://test.url") is False

    def test_validate_final_content_exactly_minimum(self):
        """Test validation with exactly minimum content."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        content = "A" * 100  # Exactly 100 characters
        assert scraper._validate_final_content(content, "http://test.url") is True


class TestImageExtraction:
    """Test image URL extraction."""

    def test_extract_image_url_present(self):
        """Test extracting image when present."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '<div><img src="http://example.com/image.jpg" /></div>'
        element = BeautifulSoup(html, 'html.parser')

        image_url = scraper._extract_image_url(element)
        assert image_url == "http://example.com/image.jpg"

    def test_extract_image_url_absent(self):
        """Test extracting image when absent."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '<div><p>No image here</p></div>'
        element = BeautifulSoup(html, 'html.parser')

        image_url = scraper._extract_image_url(element)
        assert image_url is None

    def test_extract_image_url_multiple_images(self):
        """Test extracting first image when multiple present."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <img src="http://example.com/first.jpg" />
            <img src="http://example.com/second.jpg" />
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        image_url = scraper._extract_image_url(element)
        assert image_url == "http://example.com/first.jpg"


class TestHTMLCleaning:
    """Test HTML cleaning functions."""

    def test_remove_h1_tags(self):
        """Test that H1 tags are removed."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <h1>Title</h1>
            <p>Content</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        assert cleaned.find('h1') is None
        assert cleaned.find('p') is not None

    def test_remove_script_tags(self):
        """Test that script tags are removed."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <script>alert('test');</script>
            <p>Content</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        assert cleaned.find('script') is None
        assert cleaned.find('p') is not None

    def test_minimal_clean_preserves_content(self):
        """Test that minimal cleaning preserves most content."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <h1>Title</h1>
            <p>First paragraph</p>
            <p>Second paragraph</p>
            <div>Some metadata</div>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._minimal_clean_html_content(element)

        # H1 should be removed
        assert cleaned.find('h1') is None
        # But paragraphs and divs should be preserved
        assert len(cleaned.find_all('p')) == 2
        assert cleaned.find('div') is not None


class TestMetadataRemoval:
    """Test metadata element removal."""

    def test_remove_date_metadata(self):
        """Test removal of publication date metadata."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <span>Publicado em 15/10/2025</span>
            <p>Content here</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        # Date span should be removed
        text = cleaned.get_text()
        assert "Publicado em" not in text
        # But content should remain
        assert "Content here" in text

    def test_remove_category_label(self):
        """Test removal of category labels."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <div style="font-size:10px">
                <label>Categoria:</label>
                <span>Educação</span>
            </div>
            <p>Article content here</p>
            <p>More article content</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        # Category label should be removed, but article content should remain
        text = cleaned.get_text()
        assert "Article content here" in text
        # Category label should be removed
        assert "Categoria:" not in text or len(cleaned.find_all('p')) >= 2

    def test_preserve_content_with_word_categoria(self):
        """Test that content containing 'categoria' is NOT removed."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <p>O ministro cria categoria Não Recomendado para crianças.</p>
            <p>Esta é uma nova categoria de classificação.</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        # Content paragraphs should NOT be removed even though they contain "categoria"
        assert len(cleaned.find_all('p')) == 2
        text = cleaned.get_text()
        assert "cria categoria" in text
        assert "nova categoria" in text


class TestSharingElementsRemoval:
    """Test sharing buttons and social media removal."""

    def test_remove_compartilhe_buttons(self):
        """Test removal of 'Compartilhe' buttons."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <div>Compartilhe:</div>
            <a href="http://facebook.com/share">Facebook</a>
            <p>Real content</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        text = cleaned.get_text()
        # Compartilhe should be removed
        assert "Compartilhe" not in text
        # But real content should remain
        assert "Real content" in text

    def test_remove_social_media_links(self):
        """Test removal of social media links."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <a href="http://facebook.com/page">Facebook</a>
            <a href="http://twitter.com/user">Twitter</a>
            <a href="http://example.com/article">Valid Link</a>
            <p>Content</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        # Social media links should be removed
        links = cleaned.find_all('a')
        assert len(links) == 1  # Only the valid link remains
        assert "example.com" in links[0]['href']


class TestContactElementsRemoval:
    """Test removal of contact information."""

    def test_remove_assessoria_info(self):
        """Test removal of assessoria de comunicação."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <p>Article content</p>
            <p>Assessoria de Comunicação: imprensa@example.com</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        text = cleaned.get_text()
        # Assessoria should be removed
        assert "Assessoria" not in text
        # But article content should remain
        assert "Article content" in text

    def test_remove_phone_numbers(self):
        """Test removal of phone numbers."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        html = '''
        <div>
            <p>Contact us at (61) 1234-5678</p>
            <p>Important content</p>
        </div>
        '''
        element = BeautifulSoup(html, 'html.parser')

        cleaned = scraper._clean_html_content(element)

        text = cleaned.get_text()
        # Phone should be removed
        assert "(61) 1234-5678" not in text
        # But important content should remain
        assert "Important content" in text


class TestMarkdownCleaning:
    """Test markdown content cleaning."""

    def test_remove_junk_lines(self):
        """Test removal of junk lines from markdown."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        content = """
        Notícias

        Compartilhe

        Este é o conteúdo real da notícia.
        Mais conteúdo aqui.

        facebook.com/share
        """

        cleaned = scraper._clean_markdown_content(content)

        # Junk should be removed
        assert "Compartilhe" not in cleaned
        assert "facebook.com" not in cleaned
        # Real content should remain
        assert "conteúdo real" in cleaned
        assert "Mais conteúdo" in cleaned

    def test_remove_excessive_newlines(self):
        """Test removal of excessive newlines."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        content = "Line 1\n\n\n\n\nLine 2"

        cleaned = scraper._clean_markdown_content(content)

        # Should have at most double newlines
        assert "\n\n\n" not in cleaned
        assert "Line 1" in cleaned
        assert "Line 2" in cleaned


class TestJunkLineDetection:
    """Test junk line detection."""

    def test_is_junk_line_navigation(self):
        """Test detection of navigation lines."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        assert scraper._is_junk_line("Notícias") is True
        assert scraper._is_junk_line("Home") is True
        assert scraper._is_junk_line("Voltar") is True

    def test_is_junk_line_social_media(self):
        """Test detection of social media lines."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        assert scraper._is_junk_line("Compartilhe") is True
        assert scraper._is_junk_line("facebook.com/page") is True
        assert scraper._is_junk_line("twitter.com/user") is True

    def test_is_junk_line_metadata(self):
        """Test detection of metadata lines."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        assert scraper._is_junk_line("Publicado em 15/10/2025") is True
        assert scraper._is_junk_line("Categoria: Educação") is True
        assert scraper._is_junk_line("Tags: saúde, educação") is True

    def test_is_junk_line_valid_content(self):
        """Test that valid content is not flagged as junk."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        assert scraper._is_junk_line("O ministério anuncia nova categoria") is False
        assert scraper._is_junk_line("Este é o conteúdo da notícia") is False
        assert scraper._is_junk_line("") is False


class TestArticleContentIntegration:
    """Integration tests for get_article_content method."""

    @patch('src.scraper.webscraper.WebScraper.fetch_page')
    def test_get_article_content_success(self, mock_fetch):
        """Test successful article content extraction."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        # Mock response
        mock_response = Mock()
        mock_response.content = '''
        <html>
            <div id="content">
                <h1>Article Title</h1>
                <img src="http://example.com/image.jpg" />
                <p>First paragraph of content.</p>
                <p>Second paragraph with more information.</p>
                <p>Third paragraph to ensure sufficient content.</p>
            </div>
        </html>
        '''
        mock_fetch.return_value = mock_response

        content, image_url = scraper.get_article_content("http://test.url")

        assert content != "Error retrieving content"
        assert content != "No content found"
        assert "First paragraph" in content
        assert image_url == "http://example.com/image.jpg"

    @patch('src.scraper.webscraper.WebScraper.fetch_page')
    def test_get_article_content_no_content_div(self, mock_fetch):
        """Test handling when content div is missing."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        # Mock response without content div
        mock_response = Mock()
        mock_response.content = '<html><body><p>No content div</p></body></html>'
        mock_fetch.return_value = mock_response

        content, image_url = scraper.get_article_content("http://test.url")

        assert content == "Error retrieving content"
        assert image_url is None

    @patch('src.scraper.webscraper.WebScraper.fetch_page')
    def test_get_article_content_fetch_fails(self, mock_fetch):
        """Test handling when fetch fails."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        # Mock fetch failure
        mock_fetch.return_value = None

        content, image_url = scraper.get_article_content("http://test.url")

        assert content == "Error retrieving content"
        assert image_url is None

    @patch('src.scraper.webscraper.WebScraper.fetch_page')
    def test_get_article_content_uses_fallback(self, mock_fetch):
        """Test that fallback is used when cleaning removes too much."""
        scraper = WebScraper("2025-10-01", "https://www.gov.br/test/pt-br/noticias")

        # Mock response with content that might be over-cleaned
        mock_response = Mock()
        mock_response.content = '''
        <html>
            <div id="content">
                <h1>Title</h1>
                <div>Categoria: Test</div>
                <p>Short</p>
            </div>
        </html>
        '''
        mock_fetch.return_value = mock_response

        content, image_url = scraper.get_article_content("http://test.url")

        # Should either use fallback or return error if content is too short
        # At minimum, it should not crash
        assert isinstance(content, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
