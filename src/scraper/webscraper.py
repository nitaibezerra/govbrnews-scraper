import logging
import random
import re
import time
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from retry import retry

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SLEEP_TIME_INTERVAL = (0.5, 1.5)


class WebScraper:
    def __init__(self, min_date: str, base_url: str, max_date: Optional[str] = None):
        """
        Initialize the scraper with minimum and maximum dates, and base URL.

        :param min_date: The minimum date for scraping news (format: YYYY-MM-DD).
        :param base_url: The base URL of the agency's news page.
        :param max_date: The maximum date for scraping news (format: YYYY-MM-DD).
        """
        self.base_url = base_url
        self.min_date = datetime.strptime(min_date, "%Y-%m-%d").date()
        if max_date:
            self.max_date = datetime.strptime(max_date, "%Y-%m-%d").date()
        else:
            self.max_date = None
        self.news_data = []
        self.agency = self.get_agency_name()

    def get_agency_name(self) -> str:
        """
        Extract the agency name from the base URL for naming files.

        :return: The agency name.
        """
        return self.base_url.split("/")[3]

    def scrape_news(self) -> List[Dict[str, str]]:
        """
        Scrape news from the website until the min_date is reached.
        If the agency's URL consistently fails, skip it.

        :return: A list of dictionaries containing news data.
        """
        current_offset = 0

        while True:
            current_page_url = f"{self.base_url}?b_start:int={current_offset}"

            try:
                should_continue, items_per_page = self.scrape_page(current_page_url)

                # If no items were found, break the loop to avoid infinite requests
                if items_per_page == 0:
                    logging.info(
                        f"No more news items found for {self.agency}. Stopping."
                    )
                    break

                if not should_continue:
                    break

                # Increment the offset only if items were found
                current_offset += items_per_page
                logging.info(f"Moving to next page with offset {current_offset}")

            except requests.exceptions.HTTPError as e:
                logging.error(
                    f"Skipping agency {self.agency} due to persistent HTTP error: {str(e)}"
                )
                break

            except requests.exceptions.RequestException as e:
                logging.error(
                    f"Skipping agency {self.agency} due to network error: {str(e)}"
                )
                break

        return self.news_data

    @retry(
        exceptions=requests.exceptions.RequestException,
        tries=5,
        delay=2,
        backoff=3,
        jitter=(1, 3),
    )
    def fetch_page(self, url: str) -> Optional[requests.Response]:
        """
        Fetch the page content from the given URL with retry logic.
        If the request fails permanently, return None.

        :param url: The URL to fetch.
        :return: The Response object or None if the request fails.
        """
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            return response

        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error when accessing {url}: {e}")
            return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed for {url}: {e}")
            return None

    def scrape_page(self, page_url: str) -> Tuple[bool, int]:
        """
        Scrape a single page of news with logic to skip pages where news is newer than max_date.
        If the request fails, return (False, 0).

        :param page_url: The URL of the page to scrape.
        :return: A tuple (continue_scraping, items_per_page).
        """
        logging.info(f"Fetching site news list: {page_url}")

        response = self.fetch_page(page_url)
        if not response:
            logging.error(f"Skipping page due to repeated failures: {page_url}")
            return False, 0

        soup = BeautifulSoup(response.content, "html.parser")
        news_items = soup.find_all("article", class_="tileItem")

        # Second HTML structure type
        if not news_items:
            news_list = soup.find("ul", class_="noticias")
            if news_list:
                news_items = news_list.find_all("li")
            else:
                news_items = []

        items_per_page = len(news_items)
        logging.info(f"Found {items_per_page} news articles on the page")

        if items_per_page == 0:
            return False, 0  # No items to process

        # Check the date of the last news item to decide whether to process the page
        last_news_item = news_items[-1]
        last_news_date = self.extract_date(last_news_item)
        if not last_news_date:
            logging.warning(
                "Could not extract date from last news item; processing page."
            )
        elif self.max_date and last_news_date > self.max_date:
            logging.info(
                f"Last news date {last_news_date} is newer than max_date {self.max_date}. Skipping page."
            )
            time.sleep(random.uniform(*SLEEP_TIME_INTERVAL))
            return True, items_per_page  # Skip this page

        # Process all items on the page
        for item in news_items:
            # Sleep for a random amount of time between intervals
            time.sleep(random.uniform(*SLEEP_TIME_INTERVAL))

            must_continue = self.extract_news_info(item)
            if not must_continue:
                # Stop if news older than min_date is found
                return False, items_per_page

        return True, items_per_page

    def extract_news_info(self, item) -> bool:
        """
        Extract the news information from an HTML element.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: A boolean indicating whether to continue processing further news items.
        """
        title, url = self.extract_title_and_url(item)
        category = self.extract_category(item)
        news_date = self.extract_date(item)

        if news_date:
            if news_date < self.min_date:
                logging.info(
                    f"Stopping scrape. Found news older than min_date: {news_date}"
                )
                return False  # Stop processing items
            if self.max_date and news_date > self.max_date:
                logging.info(
                    f"Skipping news dated {news_date} as it is newer than max_date {self.max_date}."
                )
                return True  # Skip this item

        tags = self.extract_tags(item)
        content, image_url = self.get_article_content(
            url
        )  # Now returns (content, image)

        logging.info(f"Retrieved article: {news_date} - {url}\n")

        self.news_data.append(
            {
                "title": title,
                "url": url,
                "published_at": news_date if news_date else None,
                "category": category,
                "tags": tags,
                "content": content,
                "image": image_url,
                "agency": self.agency,
                "extracted_at": datetime.now(),
            }
        )

        return True  # Continue processing items

    def extract_title_and_url(self, item) -> Tuple[str, str]:
        """
        Extract the title and URL from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: A tuple (title, url).
        """
        # First structure: Look for 'a' with class 'summary url'
        title_tag = item.find("a", class_="summary url")

        # Second structure: Look for a plain 'a' tag if 'summary url' is not found
        if not title_tag:
            title_tag = item.find("a")

        title = title_tag.get_text().strip() if title_tag else "No Title"
        url = title_tag["href"] if title_tag else "No URL"
        return title, url

    def extract_category(self, item) -> str:
        """
        Extract the category from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The category as a string.
        """
        # First structure: Look for 'span' with class 'subtitle'
        category_tag = item.find("span", class_="subtitle")

        # Second structure: Look for 'div' with class 'subtitulo-noticia'
        if not category_tag:
            category_tag = item.find("div", class_="subtitulo-noticia")

        # Third structure: Look for 'div' with class 'categoria-noticia'
        if not category_tag:
            category_tag = item.find("div", class_="categoria-noticia")

        return category_tag.get_text().strip() if category_tag else "No Category"

    def extract_date(self, item) -> Optional[date]:
        """
        Extract the date from a news item using multiple strategies.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime.date object or None if not found.
        """
        result = self.extract_date_1(item)
        if not result:
            result = self.extract_date_2(item)

        if not result:
            logging.error("No date found in news item.")
            return None

        return result.date()

    def extract_date_1(self, item) -> Optional[datetime]:
        """
        Extract the date from a news item using the first strategy.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime.datetime object or None if not found.
        """
        date_tag = item.find("span", class_="documentByLine")
        date_str = date_tag.get_text().strip() if date_tag else ""

        if date_str:
            date_parts = date_str.split()
            if len(date_parts) > 1:
                clean_date_str = date_parts[1]
                try:
                    return datetime.strptime(clean_date_str, "%d/%m/%Y")
                except ValueError:
                    logging.warning(f"Date format not recognized: {clean_date_str}")
                    return None
        return None

    def extract_date_2(self, item) -> Optional[datetime]:
        """
        Extract the date from a news item using the second strategy.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime.datetime object or None if not found.
        """
        date_tag = item.find("span", class_="data")

        # Extract the date string
        date_str = date_tag.get_text().strip() if date_tag else None

        if not date_str:
            return None

        try:
            # Assuming the format is 'dd/mm/yyyy'
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            logging.warning(f"Date format not recognized: {date_str}")
            return None

    def extract_tags(self, item) -> List[str]:
        """
        Extract the tags from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: A list of tags as strings.
        """
        # First structure: Look for 'div' with class 'keywords'
        tags_div = item.find("div", class_="keywords")

        # Second structure: Look for 'div' with class 'subject-noticia'
        if not tags_div:
            tags_div = item.find("div", class_="subject-noticia")

        if tags_div:
            tag_links = tags_div.find_all("a", class_="link-category")
            return [tag.get_text().strip() for tag in tag_links]

        return []

    def get_article_content(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Get the content of a news article from its URL, converting the HTML to Markdown
        to preserve formatting, links, and media references. Extracts the first image
        and removes introductory clutter, sharing links, metadata, and other junk content.

        :param url: The URL of the article.
        :return: A tuple containing the article content in Markdown format and the first image URL (or None).
        """
        try:
            response = self.fetch_page(url)
            if not response:
                return "Error retrieving content", None

            soup = BeautifulSoup(response.content, "html.parser")
            article_body = soup.find("div", id="content")

            if not article_body:
                return "No content found", None

            # Extract the first image before cleaning
            first_img = article_body.find("img")
            image_url = first_img["src"] if first_img else None

            # Clean the HTML content by removing junk elements
            cleaned_html = self._clean_html_content(article_body)

            # Convert the cleaned HTML content to Markdown
            content = md(str(cleaned_html))

            # Apply additional text-based cleaning
            cleaned_content = self._clean_markdown_content(content)

            return cleaned_content, image_url

        except Exception as e:
            logging.error(f"Error retrieving content from {url}: {str(e)}")
            return "Error retrieving content", None

    def _clean_html_content(self, article_body):
        """
        Clean HTML content by removing junk elements like sharing buttons,
        metadata, social media links, and other non-content elements.

        :param article_body: BeautifulSoup element representing the article content
        :return: Cleaned BeautifulSoup element
        """
        # Make a copy to avoid modifying the original
        cleaned_body = BeautifulSoup(str(article_body), 'html.parser')

        # Remove title (H1) as it's already extracted separately
        h1_tags = cleaned_body.find_all('h1')
        for h1 in h1_tags:
            h1.decompose()

        # Remove sharing elements
        self._remove_sharing_elements(cleaned_body)

        # Remove metadata elements
        self._remove_metadata_elements(cleaned_body)

        # Remove social media links and contact info
        self._remove_contact_elements(cleaned_body)

        # Remove script tags
        scripts = cleaned_body.find_all('script')
        for script in scripts:
            script.decompose()

        return cleaned_body

    def _remove_sharing_elements(self, soup):
        """
        Remove sharing buttons and related elements.

        :param soup: BeautifulSoup object to clean
        """
        # Remove elements containing "Compartilhe"
        share_elements = soup.find_all(string=lambda text: text and "Compartilhe" in text)
        for elem in share_elements:
            if elem.parent:
                elem.parent.decompose()

        # Remove social media links by domain
        social_domains = ["facebook.com", "twitter.com", "linkedin.com", "whatsapp.com", "api.whatsapp.com"]
        for domain in social_domains:
            links = soup.find_all("a", href=lambda href: href and domain in href)
            for link in links:
                link.decompose()

        # Remove elements with social-related classes
        social_classes = ["social-links", "share", "sharing", "social-media"]
        for class_name in social_classes:
            elements = soup.find_all(class_=lambda c: c and any(social in str(c).lower() for social in [class_name]))
            for elem in elements:
                elem.decompose()

    def _remove_metadata_elements(self, soup):
        """
        Remove metadata elements like publication date, category info, etc.

        :param soup: BeautifulSoup object to clean
        """
        # Remove publication date elements
        date_keywords = ["Publicado em", "Atualizado em", "publicado em", "atualizado em"]
        for keyword in date_keywords:
            elements = soup.find_all(string=lambda text: text and keyword in text)
            for elem in elements:
                if elem.parent and elem.parent.name in ['p', 'div', 'span']:
                    elem.parent.decompose()

        # Remove elements with date-related classes
        date_classes = ["documentByLine", "publishedDate", "updatedDate", "date-info"]
        for class_name in date_classes:
            elements = soup.find_all(class_=lambda c: c and class_name in str(c) if c else False)
            for elem in elements:
                elem.decompose()

        # Remove category/tag elements that appear at the end
        category_keywords = ["Categoria", "Tags:", "categoria", "tags:"]
        for keyword in category_keywords:
            elements = soup.find_all(string=lambda text: text and keyword in text)
            for elem in elements:
                if elem.parent:
                    # Remove the parent and its siblings (usually the category content)
                    parent = elem.parent
                    while parent and parent.find_next_sibling():
                        sibling = parent.find_next_sibling()
                        sibling.decompose()
                    parent.decompose()

    def _remove_contact_elements(self, soup):
        """
        Remove contact information and press/communications elements.

        :param soup: BeautifulSoup object to clean
        """
        # Remove assessoria/communication elements
        contact_keywords = [
            "Assessoria de Comunicação", "Assessoria de Imprensa",
            "assessoria de comunicação", "assessoria de imprensa",
            "ascom@", "comunicacao@", "imprensa@"
        ]

        for keyword in contact_keywords:
            elements = soup.find_all(string=lambda text: text and keyword in text)
            for elem in elements:
                if elem.parent:
                    elem.parent.decompose()

        # Remove phone numbers (pattern: (XX) XXXX-XXXX)
        phone_elements = soup.find_all(string=lambda text: text and re.search(r'\(\d{2}\)\s*\d{4}[-\s]?\d{4}', text) if text else False)
        for elem in phone_elements:
            if elem.parent:
                elem.parent.decompose()

        # Remove social media handles (like @minaseenergia, facebook.com/xxx)
        social_handles = soup.find_all(string=lambda text: text and any(
            pattern in text.lower() for pattern in [
                "facebook.com/", "twitter.com/", "instagram.com/",
                "linkedin.com/", "youtube.com/", "flickr.com/"
            ]
        ) if text else False)

        for elem in social_handles:
            if elem.parent:
                elem.parent.decompose()

    def _clean_markdown_content(self, content: str) -> str:
        """
        Apply additional cleaning to the markdown content.

        :param content: Raw markdown content
        :return: Cleaned markdown content
        """
        if not content:
            return content

        lines = content.split('\n')
        cleaned_lines = []

        # Track if we've found the main content start
        content_started = False

        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines at the beginning
            if not content_started and not line_stripped:
                continue

            # Skip lines that are obviously junk
            if self._is_junk_line(line_stripped):
                continue

            # Remove title lines with "===" patterns (markdown headers from HTML conversion)
            if re.match(r'^=+$', line_stripped):
                continue

            # Start including content after we find a meaningful line
            if not content_started and line_stripped and not self._is_junk_line(line_stripped):
                content_started = True

            if content_started:
                cleaned_lines.append(line)

        # Join lines and clean up excessive whitespace
        cleaned_content = '\n'.join(cleaned_lines)

        # Remove multiple consecutive empty lines
        cleaned_content = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_content)

        # Remove leading/trailing whitespace
        cleaned_content = cleaned_content.strip()

        return cleaned_content

    def _is_junk_line(self, line: str) -> bool:
        """
        Check if a line contains junk content that should be removed.

        :param line: Line to check
        :return: True if the line is junk, False otherwise
        """
        if not line:
            return False

        line_lower = line.lower()

        # Junk patterns
        junk_patterns = [
            # Navigation/breadcrumb
            r'^notícias?$',
            r'^home\s*$',
            r'^voltar\s*$',

            # Social media text
            r'compartilhe',
            r'facebook\.com',
            r'twitter\.com',
            r'linkedin\.com',
            r'whatsapp\.com',
            r'instagram\.com',
            r'youtube\.com',

            # Metadata
            r'^publicado em',
            r'^atualizado em',
            r'^categoria',
            r'^tags?:',

            # Contact info
            r'assessoria',
            r'comunicação',
            r'imprensa',
            r'ascom@',
            r'\(\d{2}\)\s*\d{4}[-\s]?\d{4}',  # Phone numbers

            # Copy link text
            r'copiar para área de transferência',
            r'copiar link',
        ]

        for pattern in junk_patterns:
            if re.search(pattern, line_lower):
                return True

        return False

    def _remove_intro_lines(self, content: str) -> str:
        """
        Remove unnecessary introductory lines before the first title.

        :param content: The raw Markdown content extracted.
        :return: Cleaned Markdown content with the title at the beginning.
        """
        lines = content.split("\n")

        # Find the first title occurrence, marked by "=====" or "# Title"
        for i, line in enumerate(lines):
            if re.match(r"^=+$", line.strip()) or line.startswith("# "):
                return "\n".join(
                    lines[i - 1 :]
                )  # Keep the title and everything after it

        return content  # If no title is found, return as-is
