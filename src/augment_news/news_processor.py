import json
import logging
import os
from typing import Dict, Optional

from news_analyzer import NewsAnalyzer


class NewsProcessor:
    def __init__(
        self,
        raw_extractions_dir: str = "raw_extractions",
        augmented_news_dir: str = "augmented_news",
        analyzer: Optional[NewsAnalyzer] = None,
    ):
        """
        Initialize the NewsProcessor with directories and a NewsAnalyzer instance.

        :param raw_extractions_dir: Directory containing raw news extractions.
        :param augmented_news_dir: Directory where augmented news will be saved.
        :param analyzer: An instance of NewsAnalyzer for analyzing news entries.
        """
        self.raw_extractions_dir = raw_extractions_dir
        self.augmented_news_dir = augmented_news_dir
        self.analyzer = analyzer

        # Ensure the augmented_news directory exists
        if not os.path.exists(self.augmented_news_dir):
            os.makedirs(self.augmented_news_dir)
            logging.info(f"Created directory: {self.augmented_news_dir}")

    def process_files(
        self, min_date: Optional[str] = None, agency: Optional[str] = None
    ):
        """
        Process all JSON files in the raw_extractions directory and save augmented files to the augmented_news directory.
        Only processes files from a specified agency (if provided) and files with a date greater than or equal to min_date (if provided).

        :param min_date: Minimum date to process (format: 'YYYY-MM-DD').
        :param agency: Agency to filter by (only process files from this agency).
        """
        for root, dirs, files in os.walk(self.raw_extractions_dir):
            # Filter by agency if provided
            if agency and agency not in root:
                continue

            for filename in files:
                # Skip non-JSON files
                if not filename.endswith(".json"):
                    continue

                # Extract the date from the filename (assuming filename has format like 'agency_YYYY-MM-DD.json')
                file_date = filename.split("_")[-1].replace(".json", "")

                # Filter by date if provided
                if min_date and file_date < min_date:
                    continue

                file_path = os.path.join(root, filename)
                augmented_file_path = self.get_augmented_file_path(file_path)

                if self.should_skip_file(augmented_file_path):
                    continue

                news_data = self.load_json_file(file_path)
                if news_data is None:
                    continue

                augmented_data = self.process_news_entries(news_data)
                self.save_augmented_file(augmented_file_path, augmented_data)

    def get_augmented_file_path(self, file_path: str) -> str:
        """
        Construct the augmented file path based on the raw file path, preserving the directory structure.

        :param file_path: The original file path.
        :return: The augmented file path.
        """
        relative_path = os.path.relpath(file_path, self.raw_extractions_dir)
        return os.path.join(self.augmented_news_dir, relative_path)

    def should_skip_file(self, augmented_file_path: str) -> bool:
        """
        Check if the augmented file already exists to decide if the processing can be skipped.

        :param augmented_file_path: The path to the augmented file.
        :return: True if the file should be skipped, False otherwise.
        """
        if os.path.exists(augmented_file_path):
            logging.info(f"Skipping already processed file: {augmented_file_path}")
            return True
        return False

    def load_json_file(self, file_path: str) -> Optional[Dict]:
        """
        Load the JSON file and return its content. Log an error if the file cannot be read.

        :param file_path: Path to the JSON file.
        :return: The content of the JSON file as a dictionary.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f"Error reading JSON file: {file_path}. Error: {e}")
            return None

    def process_news_entries(self, news_data: Dict) -> Dict:
        """
        Process each news entry in the JSON data to determine if it is AI-related and generate explanations.

        :param news_data: The news data loaded from the JSON file.
        :return: The augmented news data with AI-related information.
        """
        for news_entry in news_data:
            is_ai_related_flag, ai_mention = (
                self.analyzer.classify_and_generate_ai_explanation(news_entry)
            )
            news_entry["is_ai_related_flag"] = is_ai_related_flag
            if is_ai_related_flag:
                news_entry["ai_mention"] = ai_mention
                logging.info(
                    f"\n\nArtigo relacionado à IA:\nTítulo: {news_entry['title']}\n\nMenção destacada: {ai_mention}\n"
                )
        return news_data

    def save_augmented_file(self, augmented_file_path: str, augmented_data: Dict):
        """
        Save the augmented data to the specified file path, creating directories if necessary.

        :param augmented_file_path: The path where the augmented file will be saved.
        :param augmented_data: The augmented news data to be saved.
        """
        augmented_dir = os.path.dirname(augmented_file_path)
        if not os.path.exists(augmented_dir):
            os.makedirs(augmented_dir)
            logging.info(f"Created directory: {augmented_dir}")

        try:
            with open(augmented_file_path, "w", encoding="utf-8") as f:
                json.dump(augmented_data, f, ensure_ascii=False, indent=4)
            logging.info(f"Saved augmented file: {augmented_file_path}")
        except OSError as e:
            logging.error(
                f"Error saving augmented file: {augmented_file_path}. Error: {e}"
            )
