import logging
import os
import tempfile
from typing import Optional, OrderedDict

import pandas as pd
import requests
from datasets import Dataset, load_dataset
from datasets.exceptions import DatasetNotFoundError
from huggingface_hub import HfApi, HfFolder
from retry import retry

DATASET_PATH = "nitaibezerra/govbrnews"  # The name of the Hugging Face dataset


class DatasetManager:
    """
    A simplified class responsible for interacting with the Hugging Face Hub for datasets.

    Major changes compared to previous versions:
      - Use Hugging Face Dataset + pandas as main data structures.
      - Eliminate repeated dict conversions by operating primarily in DataFrame form.
    """

    def __init__(self):
        self.dataset_path = DATASET_PATH
        self.api = HfApi()
        self.token = HfFolder.get_token()
        if not self.token:
            raise ValueError(
                "Hugging Face authentication token is missing. "
                "Please login using `huggingface-cli login`."
            )

    def insert(self, new_data: OrderedDict):
        """
        Insert new rows into the dataset, ignoring duplicates based on 'unique_id',
        then push the result to the Hugging Face Hub.
        """
        dataset = self._load_existing_dataset()
        if dataset is None:
            logging.info("No existing dataset found. Creating from scratch...")
            # If there is no existing dataset, just create a new one from new_data
            dataset = Dataset.from_dict(new_data)
        else:
            # Merge new rows into the existing dataset
            dataset = self._merge_new_into_dataset(dataset, new_data)

        # Sort the dataset before pushing
        dataset = self._sort_dataset(dataset)

        # Push updated dataset (and CSVs) to the Hub
        self._push_dataset_and_csvs(dataset)

    def update(self, updated_df: pd.DataFrame):
        """
        Update existing rows in the dataset based on 'unique_id',
        overwriting fields in matching rows with the new values from the provided DataFrame.
        Also supports adding entirely new columns if they don't exist yet.
        """
        dataset = self._load_existing_dataset()
        if dataset is None:
            logging.info(
                "No existing dataset found. Cannot update a non-existent dataset."
            )
            return

        # Apply row-by-row updates
        dataset = self._apply_updates(dataset, updated_df)

        # Sort again after updates
        dataset = self._sort_dataset(dataset)

        # Push updated dataset (and CSVs) to the Hub
        self._push_dataset_and_csvs(dataset)

    def get(self, min_date: str, max_date: str) -> pd.DataFrame:
        """
        Return rows where 'published_at' is between min_date and max_date (inclusive).

        :param min_date: The minimum date in YYYY-MM-DD format (e.g. '2023-01-01').
        :param max_date: The maximum date in YYYY-MM-DD format (e.g. '2023-12-31').
        :return: A pandas DataFrame with rows that match the date range.
        """
        dataset = self._load_existing_dataset()
        if dataset is None:
            logging.info("No existing dataset found. Returning empty DataFrame.")
            return pd.DataFrame()

        df = dataset.to_pandas()
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

        # Filter by date range
        df = df[
            (df["published_at"] >= pd.to_datetime(min_date))
            & (df["published_at"] <= pd.to_datetime(max_date))
        ]

        return df

    def _load_existing_dataset(self) -> Optional[Dataset]:
        """
        Load an existing dataset from the Hugging Face Hub, or return None if not found.
        """
        try:
            existing_dataset = load_dataset(self.dataset_path, split="train")
            logging.info(
                f"Existing dataset loaded from {self.dataset_path}. "
                f"\nRow count: {len(existing_dataset)}"
            )
            return existing_dataset
        except DatasetNotFoundError:
            logging.info(f"No existing dataset found at {self.dataset_path}.")
            return None

    def _merge_new_into_dataset(
        self, hf_dataset: Dataset, new_data: OrderedDict
    ) -> Dataset:
        """
        Merge new rows into the existing HF Dataset, ignoring duplicates by 'unique_id'.
        """
        df_existing = hf_dataset.to_pandas()
        df_new = pd.DataFrame(new_data)

        # Identify duplicates
        unique_ids_existing = set(df_existing["unique_id"])
        df_filtered = df_new[~df_new["unique_id"].isin(unique_ids_existing)]

        if df_filtered.empty:
            logging.info("No new unique items to add; dataset is up to date.")
            return hf_dataset

        logging.info(f"Adding {len(df_filtered)} new items.")
        df_combined = pd.concat([df_existing, df_filtered], ignore_index=True)

        # Use preserve_index=False to avoid adding __index_level_0__ column
        return Dataset.from_pandas(df_combined, preserve_index=False)

    def _apply_updates(self, hf_dataset: Dataset, updated_df: pd.DataFrame) -> Dataset:
        """
        For each row in 'updated_df', update matching rows in the existing dataset by 'unique_id'.
        If new columns are present, they will be added to the DataFrame with default None,
        then filled for any matching row.
        """
        df = hf_dataset.to_pandas()

        # 1. Identify & add new columns if needed
        for col in updated_df.columns:
            if col not in df.columns:
                df[col] = None

        # 2. Overwrite rows that match on 'unique_id'
        df.set_index("unique_id", inplace=True)
        updated_df.set_index("unique_id", inplace=True)

        # Intersection of indexes to ensure we only update existing rows
        intersection = df.index.intersection(updated_df.index)
        if intersection.empty:
            logging.info(
                "No matching 'unique_id' found in existing dataset; no rows updated."
            )
        else:
            # Overwrite the row data
            df.loc[intersection, updated_df.columns] = updated_df.loc[intersection]

        df.reset_index(drop=False, inplace=True)
        updated_df.reset_index(drop=False, inplace=True)

        return Dataset.from_pandas(df, preserve_index=False)

    def _sort_dataset(self, hf_dataset: Dataset) -> Dataset:
        """
        Sort the dataset by 'agency' ascending and 'published_at' descending using pandas,
        then convert back to a HF Dataset.
        """
        df = hf_dataset.to_pandas()

        # If 'published_at' is a datetime or something else, you'll want to parse or coerce properly.
        # For simplicity, we'll assume 'published_at' is comparable in descending order:
        df.sort_values(
            by=["agency", "published_at"], ascending=[True, False], inplace=True
        )
        return Dataset.from_pandas(df, preserve_index=False)

    def _push_dataset_and_csvs(self, dataset: Dataset):
        """
        Push the HF Dataset to the Hub and generate CSV variants for easy download.
        """
        self._push_dataset_to_hub(dataset)
        self._push_global_csv(dataset)
        self._push_csvs_by_agency(dataset)
        self._push_csvs_by_year(dataset)

    def _push_dataset_to_hub(self, dataset: Dataset):
        """
        Push the entire dataset to the Hugging Face Hub.
        """
        dataset.push_to_hub(self.dataset_path, private=False)
        logging.info(f"Dataset pushed to Hugging Face Hub at {self.dataset_path}.")

    def _push_global_csv(self, dataset: Dataset):
        """
        Save the entire dataset as a single CSV file and upload it.
        """
        self._save_and_upload_csv(dataset, file_name="govbr_news_dataset.csv")

    def _push_csvs_by_agency(self, dataset: Dataset):
        """
        Split the dataset by 'agency' and upload CSV files for each agency.
        """
        self._push_csvs_by_group(
            dataset, group_by_column="agency", subfolder="agencies"
        )

    def _push_csvs_by_year(self, dataset: Dataset):
        """
        Split the dataset by year (derived from 'published_at') and upload CSV files for each year.
        """
        self._push_csvs_by_group(dataset, group_by_column="year", subfolder="years")

    def _push_csvs_by_group(
        self, dataset: Dataset, group_by_column: str, subfolder: str = ""
    ):
        """
        Split the dataset by a specified column (e.g., 'agency' or 'year') and upload CSV files
        for each distinct group in that column.
        """
        df = dataset.to_pandas()

        # If grouping by 'year', extract it from 'published_at'
        if group_by_column == "year":
            # Ensure 'published_at' is a datetime if you want to extract year
            # df["published_at"] = pd.to_datetime(df["published_at"], errors='coerce')
            df["year"] = df["published_at"].apply(
                lambda x: x.year if hasattr(x, "year") else None
            )
            group_column = "year"
        else:
            group_column = group_by_column

        groups = df.groupby(group_column)
        for group_name, group_df in groups:
            file_name = f"{group_name}_news_dataset.csv"
            temp_dataset = Dataset.from_pandas(group_df.reset_index(drop=True))

            self._save_and_upload_csv(temp_dataset, file_name, subfolder=subfolder)
            logging.info(
                f"CSV for '{group_name}' uploaded under '{subfolder}' directory."
            )

    @retry(
        exceptions=requests.exceptions.RequestException,
        tries=5,
        delay=2,
        backoff=3,
        jitter=(1, 3),
    )
    def _upload_file(self, path_or_fileobj, path_in_repo, repo_id):
        """
        Low-level file upload helper to the Hugging Face Hub with retry logic.
        """
        self.api.upload_file(
            path_or_fileobj=path_or_fileobj,
            path_in_repo=path_in_repo,
            repo_id=repo_id,
            repo_type="dataset",
            token=self.token,
        )

    def _save_and_upload_csv(
        self, dataset: Dataset, file_name: str, subfolder: str = ""
    ):
        """
        Save a dataset to a CSV file and upload it to the Hugging Face dataset repository.

        :param dataset: The dataset to save and upload.
        :param file_name: The name of the CSV file.
        :param subfolder: Optional subfolder in the repository to place the CSV file.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_file_path = os.path.join(tmp_dir, file_name)
            dataset.to_csv(csv_file_path)
            logging.info(f"Temporary CSV file created at {csv_file_path}")

            # Define the destination path for the CSV in the repository
            if subfolder:
                path_in_repo = f"{subfolder}/{file_name}"
            else:
                path_in_repo = file_name

            # Upload the file to the Hugging Face repository
            self._upload_file(csv_file_path, path_in_repo, self.dataset_path)

            logging.info(
                f"CSV file '{file_name}' uploaded to the Hugging Face repository at '{path_in_repo}'."
            )
