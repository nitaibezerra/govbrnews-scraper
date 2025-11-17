import json
import logging
import random
import re
import time
from datetime import date, datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import numpy as np
from scipy.stats import truncnorm
from retry import retry

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)



class EBCWebScraper:
    def __init__(self, min_date: str, max_date: Optional[str] = None):
        """
        Initialize the EBC scraper with minimum and maximum dates.

        :param min_date: The minimum date for scraping news (format: YYYY-MM-DD).
        :param max_date: The maximum date for scraping news (format: YYYY-MM-DD).
        """
        self.base_url = "https://memoria.ebc.com.br/noticias"
        self.min_date = datetime.strptime(min_date, "%Y-%m-%d").date()
        if max_date:
            self.max_date = datetime.strptime(max_date, "%Y-%m-%d").date()
        else:
            self.max_date = None
        self.news_data = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def smart_sleep(self, min_val=1.0, max_val=2.0, mean=1.5, std=0.4):
        """Return a random time from truncated normal distribution"""
        a = (min_val - mean) / std
        b = (max_val - mean) / std
        sleep_time = truncnorm.rvs(a, b, loc=mean, scale=std)
        return sleep_time

    def _parse_ebc_datetime(self, date_str: str) -> Optional[datetime]:
        """
        Parse EBC datetime string to datetime object with timezone.
        Handles formats:
        - "DD/MM/YYYY - HH:MM" (Agência Brasil format)
        - "DD/MM/YYYY" (date only, returns midnight)

        :param date_str: Date string from EBC.
        :return: datetime object with timezone or None if parsing fails.
        """
        brasilia_tz = timezone(timedelta(hours=-3))

        try:
            if not date_str:
                return None

            # Clean the string
            date_str = date_str.strip()

            # Pattern 1: DD/MM/YYYY - HH:MM (with time)
            match = re.search(r'(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{1,2}):(\d{2})', date_str)
            if match:
                day, month, year, hour, minute = match.groups()
                return datetime(
                    int(year), int(month), int(day),
                    int(hour), int(minute),
                    tzinfo=brasilia_tz
                )

            # Pattern 2: DD/MM/YYYY (date only - use midnight)
            match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_str)
            if match:
                day, month, year = match.groups()
                return datetime(
                    int(year), int(month), int(day),
                    0, 0,  # midnight
                    tzinfo=brasilia_tz
                )

        except Exception as e:
            logging.warning(f"Could not parse EBC datetime '{date_str}': {e}")

        return None

    def _extract_datetime_from_jsonld(self, soup) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Extract datetime from JSON-LD NewsArticle schema for EBC sites.

        :param soup: BeautifulSoup object of the article page.
        :return: Tuple of (published_datetime, updated_datetime). Either can be None.
        """
        published_dt = None
        updated_dt = None

        try:
            script_tags = soup.find_all('script', type='application/ld+json')

            for script in script_tags:
                try:
                    data = json.loads(script.string)

                    if isinstance(data, list):
                        items = data
                    else:
                        items = [data]

                    for item in items:
                        if item.get('@type') == 'NewsArticle':
                            if 'datePublished' in item and not published_dt:
                                published_dt = datetime.fromisoformat(item['datePublished'])
                            if 'dateModified' in item and not updated_dt:
                                updated_dt = datetime.fromisoformat(item['dateModified'])

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logging.debug(f"Error parsing JSON-LD: {e}")
                    continue

        except Exception as e:
            logging.debug(f"Error extracting datetime from JSON-LD: {e}")

        return published_dt, updated_dt

    def scrape_news(self) -> List[Dict[str, str]]:
        """
        Scrape news from EBC website until the min_date is reached.

        :return: A list of dictionaries containing news data.
        """
        page = 0

        while True:
            current_page_url = f"{self.base_url}?page={page}"
            page += 1

            logging.info(f"Fetching latest news from index page: {current_page_url}")

            try:
                news_urls = self.scrape_index_page(current_page_url)

                if not news_urls:
                    logging.info("No more news URLs found. Stopping.")
                    break

                should_continue = self.process_news_urls(news_urls)

                if not should_continue:
                    logging.info("Reached minimum date limit. Stopping scraper.")
                    break

            except requests.exceptions.RequestException as e:
                logging.error(f"Error fetching page {current_page_url}: {e}")
                break

        return self.news_data

    def scrape_index_page(self, url: str) -> List[str]:
        """
        Scrape a single index page to extract news URLs.

        :param url: The URL of the index page to scrape.
        :return: List of news URLs found on the page.
        """
        response = self.fetch_page(url)
        if not response:
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        news_container = soup.find('div', {'id': 'view-ultimas-noticias-ajax'})

        if news_container is None:
            logging.warning("HTML news container not found at index page, probably no more news")
            return []

        news_divs = news_container.find_all('div', class_=['ultima_isotope', 'cmpGeneric'])
        news_urls = []

        for i, div in enumerate(news_divs):
            try:
                # Find all <a> tags in this div
                all_links = div.find_all('a')

                # Look for the <a> tag that has a title but doesn't have class="imgHeading"
                title_link = None
                for link in all_links:
                    # Check if it has a title and doesn't have imgHeading class
                    if link.get('title') and 'imgHeading' not in link.get('class', []):
                        title_link = link
                        break

                if title_link:
                    # Extract URL information
                    url = title_link.get('href', '').strip()
                    news_urls.append(url)

            except Exception as e:
                logging.error(f"Error processing div {i}: {e}")
                continue

        return news_urls

    def process_news_urls(self, news_urls: List[str]) -> bool:
        """
        Process a list of news URLs and extract article data.

        :param news_urls: List of news URLs to process.
        :return: True if should continue scraping, False if min_date reached.
        """
        for url in news_urls:
            time.sleep(self.smart_sleep())

            # Skip audio news
            if "radios.ebc.com.br" not in url:
                logging.info(f"Retrieving news from: {url}")

                full_news = self.scrape_news_page(url)

                if full_news.get("error"):
                    logging.warning(f"Error scraping {url}: {full_news['error']}")
                    continue

                # Check if current date is before minimum date
                parsed_date = self.parse_date(full_news["date"])
                if parsed_date:
                    if parsed_date < self.min_date:
                        logging.info(f"Reached minimum date limit. Current news date: {full_news['date']}, Minimum date: {self.min_date.strftime('%d/%m/%Y')}")
                        return False

                    if self.max_date and parsed_date > self.max_date:
                        logging.info(f"Skipping news dated {full_news['date']} as it is newer than max_date {self.max_date.strftime('%d/%m/%Y')}")
                        continue

                # Add to our data collection
                self.news_data.append(full_news)

        return True

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

        :param url: The URL to fetch.
        :return: The Response object or None if the request fails.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed for {url}: {e}")
            return None

    def scrape_news_page(self, url: str) -> Dict[str, str]:
        """
        Scrape a single news page from EBC and return structured data.

        :param url: URL of the news article.
        :return: Dictionary with keys including 'published_datetime' and 'updated_datetime'
        """
        try:
            response = self.fetch_page(url)
            if not response:
                return {
                    'title': '',
                    'url': url,
                    'source': '',
                    'date': '',
                    'published_datetime': None,
                    'updated_datetime': None,
                    'content': '',
                    'image': '',
                    'video_url': '',
                    'agency': '',
                    'error': 'Failed to fetch page'
                }

            soup = BeautifulSoup(response.content, 'html.parser')

            # Initialize result dictionary
            news_data = {
                'title': '',
                'url': url,
                'source': '',
                'date': '',
                'published_datetime': None,
                'updated_datetime': None,
                'content': '',
                'image': '',
                'video_url': '',
                'agency': '',
                'error': '',
            }

            # Try to extract datetime from JSON-LD first (most reliable)
            published_dt, updated_dt = self._extract_datetime_from_jsonld(soup)
            if published_dt:
                news_data['published_datetime'] = published_dt
                news_data['updated_datetime'] = updated_dt

            # Check if this is a TV Brasil URL (different structure)
            is_tvbrasil = 'tvbrasil.ebc.com.br' in url

            if is_tvbrasil:
                # TV Brasil scraping strategy
                news_data['agency'] = 'tvbrasil'
                self._scrape_tvbrasil_content(soup, news_data)
            else:
                # Original Agência Brasil scraping strategy
                news_data['agency'] = 'agencia_brasil'
                self._scrape_agencia_brasil_content(soup, news_data)

            # If JSON-LD didn't work, try parsing from the date field extracted by scrape methods
            if not news_data['published_datetime'] and news_data['date']:
                parsed_dt = self._parse_ebc_datetime(news_data['date'])
                if parsed_dt:
                    news_data['published_datetime'] = parsed_dt

            # Clean up the content - remove excessive whitespace
            if news_data['content']:
                news_data['content'] = re.sub(r'\n\s*\n', '\n\n', news_data['content']).strip()

            return news_data

        except Exception as e:
            logging.error(f"Error parsing content from {url}: {e}")
            return {
                'title': '',
                'url': url,
                'source': '',
                'date': '',
                'published_datetime': None,
                'updated_datetime': None,
                'content': '',
                'image': '',
                'video_url': '',
                'agency': '',
                'error': str(e)
            }

    def _scrape_tvbrasil_content(self, soup: BeautifulSoup, news_data: Dict[str, str]):
        """Scrape content from TV Brasil pages."""
        # Extract title - just <h1> without class
        title_elem = soup.find('h1')
        if title_elem:
            news_data['title'] = title_elem.get_text(strip=True)

        # Extract source/author - <h4 class="txtNoticias"> with <a> tag
        author_elem = soup.find('h4', class_='txtNoticias')
        if author_elem:
            link_elem = author_elem.find('a')
            if link_elem:
                news_data['source'] = link_elem.get_text(strip=True)
            else:
                news_data['source'] = author_elem.get_text(strip=True)

        # Extract publication date - <h5> with "No AR em" text
        date_elem = soup.find('h5')
        if date_elem:
            # Look for span with date-display-single class
            date_span = date_elem.find('span', class_='date-display-single')
            if date_span:
                news_data['date'] = date_span.get_text(strip=True)
            else:
                # Fallback to extracting from h5 text
                date_text = date_elem.get_text(strip=True)
                if 'No AR em' in date_text:
                    date_part = date_text.replace('No AR em', '').strip()
                    news_data['date'] = date_part

        # Extract main content from <article> tag
        article_elem = soup.find('article')
        if article_elem:
            paragraphs = article_elem.find_all('p')
            content_parts = []

            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 10:  # Only include substantial text
                    # Skip certain unwanted content
                    if not (text.startswith('*Restrição de uso') or
                           text.startswith('Clique aqui para saber') or
                           text.startswith('Tags:')):
                        content_parts.append(text)

            news_data['content'] = '\n\n'.join(content_parts)

        # Extract video URL
        news_data['video_url'] = self._extract_video_url(soup)

    def _scrape_agencia_brasil_content(self, soup: BeautifulSoup, news_data: Dict[str, str]):
        """Scrape content from Agência Brasil pages."""
        # Extract title
        title_elem = soup.find('h1', class_='titulo-materia')
        if title_elem:
            news_data['title'] = title_elem.get_text(strip=True)

        # Extract source/author
        author_elem = soup.find('div', class_='autor-noticia')
        if author_elem:
            source_text = author_elem.get_text(strip=True)
            # Remove asterisk if present (like "Agência Brasil*")
            news_data['source'] = source_text.replace('*', '').strip()

        # Extract publication date
        date_elem = soup.find('div', class_='data')
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            # Extract the date part after "Publicado em"
            if 'Publicado em' in date_text:
                date_part = date_text.replace('Publicado em', '').strip()
                news_data['date'] = date_part
            else:
                news_data['date'] = date_text

        # Extract main content
        content_div = soup.find('div', class_='conteudo-noticia')
        if content_div:
            # Get all paragraphs and clean them
            paragraphs = content_div.find_all('p')
            content_parts = []

            for p in paragraphs:
                # Skip paragraphs that contain only images or tracking pixels
                text = p.get_text(strip=True)
                if text and len(text) > 10:  # Only include substantial text
                    # Clean up any tracking pixels or empty content
                    if not text.startswith('*Com informações') or len(content_parts) == 0:
                        content_parts.append(text)

            news_data['content'] = '\n\n'.join(content_parts)

        # Extract image URL (simplified version without download)
        figure_elem = soup.find('figure')
        if figure_elem:
            img_elem = figure_elem.find('img')
            if img_elem:
                image_url = None

                # Priority 1: Check data-echo attribute (lazy loading)
                if img_elem.get('data-echo'):
                    image_url = img_elem.get('data-echo')

                # Priority 2: Check noscript tag for actual image URL
                elif figure_elem.find('noscript'):
                    noscript = figure_elem.find('noscript')
                    noscript_img = noscript.find('img')
                    if noscript_img and noscript_img.get('src'):
                        image_url = noscript_img.get('src')

                # Priority 3: Fallback to src (might be loading gif)
                elif img_elem.get('src') and not img_elem.get('src').endswith('loading_v2.gif'):
                    image_url = img_elem.get('src')

                # Handle relative URLs
                if image_url and image_url.startswith('/'):
                    base_url = 'https://agenciabrasil.ebc.com.br'
                    image_url = base_url + image_url

                news_data['image'] = image_url or ''

        # Extract video URL
        news_data['video_url'] = self._extract_video_url(soup)

    def _extract_video_url(self, soup: BeautifulSoup) -> str:
        """
        Extract video URL from EBC page.

        :param soup: BeautifulSoup object of the page.
        :return: Video URL string or empty string if not found.
        """
        try:
            # Find video element
            video_elem = soup.find('video')
            if video_elem:
                # Find source tag with MP4 type
                source_elem = video_elem.find('source', {'type': 'video/mp4'})
                if source_elem and source_elem.get('src'):
                    video_url = source_elem.get('src')

                    # Handle relative URLs
                    if video_url.startswith('/'):
                        video_url = 'https://tvbrasil.ebc.com.br' + video_url

                    logging.info(f"Found video URL: {video_url}")
                    return video_url
        except Exception as e:
            logging.warning(f"Error extracting video URL: {e}")

        return ''

    def parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse date string from EBC format to date object.
        Expected format: "16/09/2025 - 13:40"

        :param date_str: Date string from EBC.
        :return: Date object or None if parsing fails.
        """
        try:
            # Remove extra whitespace and split by ' - '
            date_part = date_str.strip().split(' - ')[0]
            # Parse the date part (DD/MM/YYYY)
            return datetime.strptime(date_part, '%d/%m/%Y').date()
        except:
            logging.warning(f"Could not parse date '{date_str}'")
            return None
