import logging

from augmentation.classifier_summarizer import ClassifierSummarizer
from dataset_manager import DatasetManager

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")


class AugmentationManager:
    def __init__(self):
        self.dataset_manager = DatasetManager()  # Uses the shared DatasetManager
        self.analyzer = ClassifierSummarizer()  # The text classification / summarizer

    def classify_and_update_dataset(
        self, min_date: str, max_date: str, agency: str = None
    ):
        """
        1. Retrieve articles between min_date and max_date, optionally filtered by agency.
        2. Classify them by calling analyzer.get_themes_and_summary.
        3. Add columns for summary and up to three inferred (theme, theme_code) pairs.
        4. Update the dataset on Hugging Face Hub.

        :param min_date: The minimum date (YYYY-MM-DD) to filter articles.
        :param max_date: The maximum date (YYYY-MM-DD) to filter articles.
        :param agency:   An optional agency name to further filter articles.
        """
        # 1. Fetch existing articles from the DatasetManager
        df = self.dataset_manager.get(min_date, max_date, agency=agency)

        if df.empty:
            print("No articles found in the specified date/agency range.")
            return

        # Ensure the columns we want to fill exist (pandas will create them if they don't)
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

        # 2. Classify each article and fill in the new columns
        for index, news_entry in df.iterrows():
            themes, summary = self.analyzer.get_themes_and_summary(news_entry)

            # Update summary in DataFrame
            df.at[index, "summary"] = summary

            # Build the list of themes (code - theme)
            theme_strings = []
            for i in range(3):
                if i < len(themes):
                    theme_code = themes[i].get("theme_code", "")
                    theme_name = themes[i].get("theme", "")
                    theme_strings.append(f"{theme_code} - {theme_name}")
                else:
                    break

            # Print a clean log message
            logging.info("----- Classifying Article -----")
            logging.info(f"Title:         {news_entry.get('title', 'N/A')}")
            logging.info(f"Agency:        {news_entry.get('agency', 'N/A')}")
            logging.info(f"Published at:  {news_entry.get('published_at', 'N/A')}")
            logging.info(f"Summary:       {summary}\n")

            # Print each theme on its own line
            if theme_strings:
                logging.info("Themes (up to 3):")
                for t_str in theme_strings:
                    logging.info(f" - {t_str}")
            else:
                logging.info("Themes (up to 3): None")

            # Fill the DataFrame columns for each theme
            for i in range(3):
                theme_col = f"inferred_theme_{i+1}"
                code_col = f"inferred_theme_code_{i+1}"

                if i < len(themes):
                    df.at[index, theme_col] = themes[i].get("theme", None)
                    df.at[index, code_col] = themes[i].get("theme_code", None)
                else:
                    df.at[index, theme_col] = None
                    df.at[index, code_col] = None

        # 3. Call update() to push our changes to the Hugging Face Hub
        self.dataset_manager.update(df)
        print("Dataset updated successfully with new classification columns.")
