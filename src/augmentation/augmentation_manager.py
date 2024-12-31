from augmentation.classifier_summarizer import ClassifierSummarizer
from dataset_manager import DatasetManager


class AugmentationManager:
    def __init__(self):
        self.dataset_manager = DatasetManager()  # Uses the shared DatasetManager
        self.analyzer = ClassifierSummarizer()  # The text classification / summarizer

    def classify_and_update_dataset(self, min_date: str, max_date: str):
        """
        1. Retrieve articles between min_date and max_date.
        2. Classify them by calling analyzer.get_themes_and_summary.
        3. Add columns for summary and up to three inferred (theme, theme_code) pairs.
        4. Update the dataset on Hugging Face Hub.
        """
        # 1. Fetch existing articles from the DatasetManager
        df = self.dataset_manager.get(min_date, max_date)

        if df.empty:
            print("No articles found in the specified date range.")
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

            # Update summary
            df.at[index, "summary"] = summary

            # Up to 3 themes
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
