import logging
import pandas as pd

from augmentation.classifier_summarizer import ClassifierSummarizer
from dataset_manager import DatasetManager

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")


class AugmentationManager:
    def __init__(self):
        self.dataset_manager = DatasetManager()  # Uses the shared DatasetManager
        self.analyzer = ClassifierSummarizer()  # The text classification / summarizer

    def classify_and_update_dataset(
        self,
        min_date: str,
        max_date: str,
        agency: str = None,
        skip_if_classified: bool = True,
    ):
        """
        Orchestrates the full classification process:
        1. Fetch articles.
        2. Ensure required columns exist.
        3. Classify articles and fill columns.
        4. Update the dataset if changes were made.

        :param min_date:           The minimum date (YYYY-MM-DD) to filter articles.
        :param max_date:           The maximum date (YYYY-MM-DD) to filter articles.
        :param agency:             An optional agency name to further filter articles.
        :param skip_if_classified: If True, skip an article if its 'summary' column is already filled.
        """
        df = self._fetch_articles(min_date, max_date, agency)
        if df is None:
            return

        self._ensure_columns_exist(df)
        has_changes = self._classify_articles(df, skip_if_classified)
        self._update_dataset(df, has_changes)

    def _fetch_articles(
        self, min_date: str, max_date: str, agency: str = None
    ) -> pd.DataFrame:
        """
        Retrieve articles between min_date and max_date, optionally filtered by agency.
        Returns the DataFrame or None if empty.
        """
        df = self.dataset_manager.get(min_date, max_date, agency=agency)
        if df.empty:
            print("No articles found in the specified date/agency range.")
            return None
        return df

    def _ensure_columns_exist(self, df: pd.DataFrame) -> None:
        """
        Ensure the columns needed for classification results exist in the DataFrame.
        If not, create them.
        """
        new_cols = [
            "summary",
            "inferred_theme_1",
            "inferred_theme_code_1",
            "inferred_theme_2",
            "inferred_theme_code_2",
            "inferred_theme_3",
            "inferred_theme_code_3",
        ]
        for col in new_cols:
            if col not in df.columns:
                df[col] = None

    def _classify_articles(self, df: pd.DataFrame, skip_if_classified: bool) -> bool:
        """
        Classify each article (if needed) and populate columns with summary and theme data.
        Returns True if any new classification was performed, otherwise False.
        """
        has_changes = False

        for index, news_entry in df.iterrows():
            if skip_if_classified and pd.notna(news_entry.get("summary")):
                self._log_skipping(news_entry)
                continue

            themes, summary = self.analyzer.get_themes_and_summary(news_entry)
            has_changes = True  # A new classification is performed

            # Update DataFrame with summary and theme info
            self._update_classification_results(df, index, themes, summary)
            self._log_classification(news_entry, themes, summary)

        return has_changes

    def _update_dataset(self, df: pd.DataFrame, has_changes: bool) -> None:
        """
        Update the dataset (e.g., push to Hugging Face) if there are new classifications.
        """
        if has_changes:
            self.dataset_manager.update(df)
            print("Dataset updated successfully with new classification columns.")
        else:
            print("No new classifications were made. Dataset not updated.")

    def _update_classification_results(
        self, df: pd.DataFrame, index: int, themes: list, summary: str
    ) -> None:
        """
        Fill in the summary, inferred_theme, and inferred_theme_code columns for a single article.
        """
        df.at[index, "summary"] = summary
        for i in range(3):
            theme_col = f"inferred_theme_{i+1}"
            code_col = f"inferred_theme_code_{i+1}"

            if i < len(themes):
                df.at[index, theme_col] = themes[i].get("theme")
                df.at[index, code_col] = themes[i].get("theme_code")
            else:
                df.at[index, theme_col] = None
                df.at[index, code_col] = None

    def _log_skipping(self, news_entry: pd.Series) -> None:
        """
        Log that an article is being skipped because it’s already classified,
        including the summary and themes.
        """
        logging.info("\n----- Skipping Article (Already Classified) -----")
        self._log_article_details(news_entry)

    def _log_classification(
        self, news_entry: pd.Series, themes: list, summary: str
    ) -> None:
        """
        Log classification details, including the extracted summary and themes.
        """
        logging.info("\n----- Classifying Article -----")
        self._log_article_details(news_entry, summary, themes)

    def _log_article_details(
        self,
        news_entry: pd.Series,
        summary: str = None,
        themes: list = None,
    ) -> None:
        """
        Generic method to log article details, optionally including summary and themes.

        :param news_entry: The article data as a pandas Series.
        :param summary:    The summary of the article (optional).
        :param themes:     A list of themes associated with the article (optional).
        """
        logging.info(f"Title:        {news_entry.get('title', 'N/A')}")
        logging.info(f"Agency:       {news_entry.get('agency', 'N/A')}")
        logging.info(f"Published at: {news_entry.get('published_at', 'N/A')}")

        if summary is None:
            summary = news_entry["summary"]
        logging.info(f"Summary:      {summary}")

        if themes is not None:
            if themes:
                logging.info("Themes (up to 3):")
                for idx, theme_info in enumerate(themes[:3], start=1):
                    theme_code = theme_info.get("theme_code", "")
                    theme_name = theme_info.get("theme", "")
                    logging.info(f" {idx}. {theme_code} - {theme_name}")
            else:
                logging.info("Themes (up to 3): None")
        elif any(
            f"inferred_theme_{i+1}" in news_entry
            and pd.notna(news_entry[f"inferred_theme_{i+1}"])
            for i in range(3)
        ):
            logging.info("Themes (up to 3):")
            for i in range(3):
                theme = news_entry.get(f"inferred_theme_{i+1}", "N/A")
                theme_code = news_entry.get(f"inferred_theme_code_{i+1}", "N/A")
                if pd.notna(theme):
                    logging.info(f" {i+1}. {theme_code} - {theme}")
                else:
                    logging.info(f" {i+1}. N/A - N/A")
        logging.info("")  # Add an empty line for better readability
