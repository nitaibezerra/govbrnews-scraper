import argparse
import concurrent.futures
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

MAX_WORKERS = 3
DESTINATION_FOLDER = "raw_extractions"
SLEEP_TIME_INTERVAL = (1, 3)


class GovBRNewsScraper:
    def __init__(self, max_date: str, base_url: str):
        """
        Initialize the scraper with a maximum date and base URL.

        :param max_date: The maximum date for scraping news (format: YYYY-MM-DD).
        :param base_url: The base URL of the agency's news page.
        """
        self.base_url = base_url
        self.max_date = datetime.strptime(max_date, "%Y-%m-%d")
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
        Scrape news from the website until the max_date is reached.

        :return: A list of dictionaries containing news data.
        """

        if self.json_file_exists():
            logging.info(f"JSON file already exists for {self.agency}. Skipping.")
            return []

        current_offset = 0

        while True:
            current_page_url = f"{self.base_url}?b_start:int={current_offset}"
            should_continue, items_per_page = self.scrape_page(current_page_url)

            # If no items were found, break the loop to avoid infinite requests
            if items_per_page == 0:
                logging.info(f"No more news items found. Stopping.")
                break

            if not should_continue:
                break

            # Increment the offset only if items were found
            current_offset += items_per_page
            logging.info(f"Moving to next page with offset {current_offset}")

        # Save the scraped data to a JSON file
        self.save_news_to_json()

        return self.news_data

    def scrape_page(self, page_url: str) -> Tuple[bool, int]:
        """
        Scrape a single page of news.

        :param page_url: The URL of the page to scrape.
        :return: A tuple (continue_scraping, items_per_page).
        """
        logging.info(f"Fetching news from {page_url}")

        # Sleep for a random amount of time between 1 and 3 seconds
        time.sleep(random.uniform(*SLEEP_TIME_INTERVAL))

        response = requests.get(page_url)
        soup = BeautifulSoup(response.content, "html.parser")
        news_items = soup.find_all("article", class_="tileItem")

        # Second html structure type
        if not news_items:
            news_items = soup.find("ul", class_="noticias").find_all("li")

        items_per_page = len(news_items)
        logging.info(f"Found {items_per_page} news items on the page")

        for item in news_items:
            news_info = self.extract_news_info(item)
            if news_info:
                self.news_data.append(news_info)
            else:
                return (
                    False,
                    items_per_page,
                )  # Stop if news older than max_date is found

        return True, items_per_page

    def extract_news_info(self, item) -> Optional[Dict[str, str]]:
        """
        Extract the news information from an HTML element.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: A dictionary containing the news data or None if the news is older than the max_date.
        """
        title, url = self.extract_title_and_url(item)
        category = self.extract_category(item)
        news_date = self.extract_date(item)
        if news_date and news_date <= self.max_date:
            logging.info(
                f"Stopping scrape. Found news older than max date: {news_date.strftime('%Y-%m-%d')}"
            )
            return None
        tags = self.extract_tags(item)
        content = self.get_article_content(url)

        return {
            "title": title,
            "url": url,
            "date": news_date.strftime("%Y-%m-%d") if news_date else "Unknown Date",
            "category": category,
            "tags": tags,
            "content": content,
        }

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

    def extract_date(self, item) -> Optional[datetime]:
        result = self.extract_date_1(item)
        if not result:
            result = self.extract_date_2(item)

        if not result:
            logging.error(f"\n\nNo date found!\n")

        return result

    def extract_date_1(self, item) -> Optional[datetime]:
        """
        Extract the date from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime object or None if the date is invalid.
        """
        date_tag = item.find("span", class_="documentByLine")
        date_str = date_tag.get_text().strip() if date_tag else "No Date"
        date_parts = date_str.split()
        clean_date_str = date_parts[1] if len(date_parts) > 1 else "No Date"

        try:
            return datetime.strptime(clean_date_str, "%d/%m/%Y")
        except ValueError:
            return None

    def extract_date_2(self, item) -> Optional[datetime]:
        """
        Extract the date from a news item.

        :param item: A BeautifulSoup tag representing a single news item.
        :return: The date as a datetime object or None if the date is invalid.
        """
        date_tag = item.find("span", class_="data")

        # Extract the date string
        date_str = date_tag.get_text().strip() if date_tag else None

        if not date_str:
            return None

        # Try to extract the date from the string using common date formats
        try:
            # Assuming the format is 'dd/mm/yyyy' as per your previous script
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
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

    def get_article_content(self, url: str) -> str:
        """
        Get the content of a news article from its URL.

        :param url: The URL of the article.
        :return: The content of the article as a string.
        """
        try:
            logging.info(f"Retrieving content from {url}")
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            article_body = soup.find("div", id="content-core")
            return (
                article_body.get_text().strip() if article_body else "No content found"
            )
        except Exception as e:
            logging.error(f"Error retrieving content from {url}: {str(e)}")
            return "Error retrieving content"

    def save_news_to_json(self):
        """
        Save the scraped news data to a JSON file in the raw_extractions/agency folder.
        """
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Create a folder for each agency inside raw_extractions
        agency_folder = os.path.join(DESTINATION_FOLDER, self.agency)
        if not os.path.exists(agency_folder):
            os.makedirs(agency_folder)

        # Save one JSON file for each day
        for news_item in self.news_data:
            news_date = news_item["date"]
            filename = f"{self.agency}_{news_date}.json"
            filepath = os.path.join(agency_folder, filename)

            # Append to the existing JSON file if it exists, otherwise create a new one
            if os.path.exists(filepath):
                with open(filepath, "r+", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_data.append(news_item)
                    f.seek(0)
                    json.dump(existing_data, f, ensure_ascii=False, indent=4)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([news_item], f, ensure_ascii=False, indent=4)

        logging.info(f"News data saved to {agency_folder}")

    # List of URLs to scrape

    def json_file_exists(self) -> bool:
        """
        Check if the JSON file for the current scraping already exists.

        :return: True if the file exists, False otherwise.
        """
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = (
            f"{self.agency}_{self.max_date.strftime('%Y-%m-%d')}_{current_date}.json"
        )
        filepath = os.path.join(DESTINATION_FOLDER, filename)
        return os.path.exists(filepath)


urls = [
    "https://www.gov.br/agricultura/pt-br/assuntos/noticias",
    "https://www.gov.br/agu/pt-br/comunicacao/noticias",
    "https://www.gov.br/casacivil/pt-br/assuntos/noticias",
    "https://www.gov.br/cgu/pt-br/assuntos/noticias/ultimas-noticias",
    "https://www.gov.br/cidades/pt-br/assuntos/noticias-1",
    "https://www.gov.br/cultura/pt-br/assuntos/noticias",
    "https://www.gov.br/defesa/pt-br/centrais-de-conteudo/noticias",
    "https://www.gov.br/esporte/pt-br/noticias-e-conteudos/esporte",
    "https://www.gov.br/fazenda/pt-br/assuntos/noticias",
    "https://www.gov.br/gestao/pt-br/assuntos/noticias/noticias",
    "https://www.gov.br/gsi/pt-br/centrais-de-conteudo/noticias/2024",
    "https://www.gov.br/igualdaderacial/pt-br/assuntos/copy2_of_noticias",
    "https://www.gov.br/mcom/pt-br/noticias",
    "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/noticias/ultimas-noticias",
    "https://www.gov.br/mda/pt-br/noticias",
    "https://www.gov.br/mdh/pt-br/assuntos/noticias",
    "https://www.gov.br/mdic/pt-br/assuntos/noticias",
    "https://www.gov.br/mdr/pt-br/noticias",
    "https://www.gov.br/mds/pt-br/noticias-e-conteudos/desenvolvimento-social/noticias-desenvolvimento-social",
    "https://www.gov.br/mec/pt-br/assuntos/noticias",
    "https://www.gov.br/memp/pt-br/assuntos/noticias",
    "https://www.gov.br/mj/pt-br/assuntos/noticias",
    "https://www.gov.br/mma/pt-br/assuntos/noticias/ultimas-noticias",
    "https://www.gov.br/mme/pt-br/assuntos/noticias",
    "https://www.gov.br/mpa/pt-br/assuntos/noticias",
    "https://www.gov.br/mre/pt-br/canais_atendimento/imprensa/notas-a-imprensa/notas-a-imprensa",
    "https://www.gov.br/mulheres/pt-br/central-de-conteudos/noticias",
    "https://www.gov.br/planalto/pt-br/acompanhe-o-planalto/noticias",
    "https://www.gov.br/planejamento/pt-br/assuntos/noticias",
    "https://www.gov.br/portos-e-aeroportos/pt-br/assuntos/noticias",
    "https://www.gov.br/previdencia/pt-br/noticias-e-conteudos",
    "https://www.gov.br/reconstrucaors/pt-br/acompanhe-a-reconstrucao/noticias",
    "https://www.gov.br/saude/pt-br/assuntos/noticias",
    "https://www.gov.br/secom/pt-br/assuntos/noticias",
    "https://www.gov.br/secretariageral/pt-br/noticias",
    "https://www.gov.br/sri/pt-br/noticias/mais-noticias/ultimas-noticias",
    "https://www.gov.br/trabalho-e-emprego/pt-br/noticias-e-conteudo",
    "https://www.gov.br/transportes/pt-br/assuntos/noticias",
    "https://www.gov.br/turismo/pt-br/assuntos/noticias",
    "https://www.gov.br/aeb/pt-br/assuntos/noticias",
    "https://www.gov.br/ana/pt-br/assuntos/noticias-e-eventos/noticias",
    "https://www.gov.br/anac/pt-br/noticias/ultimas-noticias-1",
    "https://www.gov.br/anatel/pt-br/assuntos/noticias",
    "https://www.gov.br/ancine/pt-br/assuntos/noticias",
    "https://www.gov.br/aneel/pt-br/assuntos/noticias",
    "https://www.gov.br/anm/pt-br/assuntos/noticias/ultimas-noticias",
    "https://www.gov.br/anp/pt-br/canais_atendimento/imprensa/noticias-comunicados",
    "https://www.gov.br/anpd/pt-br/assuntos/noticias",
    "https://www.gov.br/ans/pt-br/assuntos/noticias",
    "https://www.gov.br/antaq/pt-br/noticias",
    "https://www.gov.br/antt/pt-br/assuntos/ultimas-noticias",
    "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa",
    "https://www.gov.br/cade/pt-br/assuntos/noticias",
    "https://www.gov.br/capes/pt-br/assuntos/noticias",
    "https://www.gov.br/cnen/pt-br/assunto/ultimas-noticias",
    "https://www.gov.br/cnpq/pt-br/assuntos/noticias",
    "https://www.gov.br/cvm/pt-br/assuntos/noticias",
    "https://www.gov.br/dnit/pt-br/assuntos/noticias/",
    "https://www.gov.br/dnocs/pt-br/assuntos/noticias",
    "https://www.gov.br/fnde/pt-br/assuntos/noticias",
    "https://www.gov.br/fundacentro/pt-br/comunicacao/noticias/noticias/ultimas-noticias",
    "https://www.gov.br/ibama/pt-br/assuntos/noticias/2024",
    "https://www.gov.br/icmbio/pt-br/assuntos/noticias/ultimas-noticias",
    "https://www.gov.br/incra/pt-br/assuntos/noticias",
    "https://www.gov.br/inep/pt-br/assuntos/noticias",
    "https://www.gov.br/inmetro/pt-br/centrais-de-conteudo/noticias",
    "https://www.gov.br/inpa/pt-br/assuntos/noticias",
    "https://www.gov.br/inpe/pt-br/assuntos/ultimas-noticias",
    "https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias",
    "https://www.gov.br/inss/pt-br/noticias/ultimas-noticias",
    "https://www.gov.br/iphan/pt-br/assuntos/noticias",
    "https://www.gov.br/iti/pt-br/assuntos/noticias/indice-de-noticias/",
    "https://www.gov.br/museus/pt-br/assuntos/noticias",
    "https://www.gov.br/pf/pt-br/assuntos/noticias/noticias-destaque",
    "https://www.gov.br/previc/pt-br/noticias",
    "https://www.gov.br/prf/pt-br/noticias/nacionais",
    "https://www.gov.br/sudam/pt-br/noticias-1",
    "https://www.gov.br/sudeco/pt-br/assuntos/noticias",
    "https://www.gov.br/sudene/pt-br/assuntos/noticias",
    "https://www.gov.br/suframa/pt-br/publicacoes/noticias/ultimas-noticias",
    "https://www.gov.br/susep/pt-br/central-de-conteudos/noticias",
]


def create_scrapers(urls: List[str], max_date: str) -> List[GovBRNewsScraper]:
    """
    Create a list of GovBRNewsScraper instances for each URL.

    :param urls: List of URLs to scrape.
    :param max_date: The maximum date for scraping news.
    :return: List of GovBRNewsScraper instances.
    """
    return [GovBRNewsScraper(max_date, url) for url in urls]


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Scrape news from multiple gov.br agencies up to a given date."
    )
    parser.add_argument(
        "max_date", help="The maximum date for scraping news (format: YYYY-MM-DD)"
    )
    args = parser.parse_args()

    # Create scrapers for each URL
    scrapers = create_scrapers(urls, args.max_date)

    # Run scrapers in parallel with a maximum of 10 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(scraper.scrape_news) for scraper in scrapers]
        concurrent.futures.wait(futures)


if __name__ == "__main__":
    main()
