import logging
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, OrderedDict

import pandas as pd
import requests
from datasets import Dataset, load_dataset
from datasets.exceptions import DatasetNotFoundError
from huggingface_hub import HfApi, HfFolder
from retry import retry

DATASET_PATH = "nitaibezerra/govbrnews"  # The main dataset
REDUCED_DATASET_PATH = (
    "nitaibezerra/govbrnews-reduced"  # Reduced dataset for faster downloads
)


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

    def insert(self, new_data: OrderedDict, allow_update: bool = False):
        """
        Insert new rows into the dataset, ignoring duplicates by default based on 'unique_id'.
        If 'allow_update' is True, then any rows with existing 'unique_id' are overwritten
        with values from 'new_data'. Afterwards, push the result to the Hugging Face Hub.

        :param new_data: An OrderedDict of data to insert.
        :param allow_update: If True, overwrite rows that already exist (same 'unique_id').
                            If False (default), skip those duplicates.
        """
        dataset = self._load_existing_dataset()
        if dataset is None:
            logging.info("No existing dataset found. Creating from scratch...")
            # If there is no existing dataset, just create a new one from new_data
            dataset = Dataset.from_dict(new_data)
        else:
            # Merge or update new rows into the existing dataset
            dataset = self._merge_new_into_dataset(
                dataset, new_data, allow_update=allow_update
            )

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

    def get(
        self, min_date: str, max_date: str, agency: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Return rows where 'published_at' is between min_date and max_date (inclusive).
        Optionally filter by a specific 'agency' if provided.

        :param min_date: The minimum date in YYYY-MM-DD format (e.g. '2023-01-01').
        :param max_date: The maximum date in YYYY-MM-DD format (e.g. '2023-12-31').
        :param agency:   An optional string representing the agency name/key to filter by.
                        If None, no filtering by agency is done.
        :return:         A pandas DataFrame with rows that match the given date range
                        (and agency if provided).
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

        # If an agency is provided, filter further
        if agency is not None:
            df = df[df["agency"] == agency]

        # Print the count of articles found
        logging.info(f"Found {len(df)} articles matching the specified criteria.")

        return df

    def _load_existing_dataset(self) -> Optional[Dataset]:
        """
        Load an existing dataset from the Hugging Face Hub, or return None if not found.
        """
        try:
            # Clear cache to avoid schema corruption issues when fields are added
            cache_dir = Path.home() / ".cache" / "huggingface" / "datasets" / self.dataset_path.replace("/", "___")
            if cache_dir.exists():
                logging.info(f"Clearing cached dataset at {cache_dir}")
                shutil.rmtree(cache_dir, ignore_errors=True)

            existing_dataset = load_dataset(self.dataset_path, split="train", download_mode="force_redownload")
            logging.info(
                f"Existing dataset loaded from {self.dataset_path}. "
                f"\nRow count: {len(existing_dataset)}"
            )
            return existing_dataset
        except DatasetNotFoundError:
            logging.info(f"No existing dataset found at {self.dataset_path}.")
            return None

    def _merge_new_into_dataset(
        self, hf_dataset: Dataset, new_data: OrderedDict, allow_update: bool = False
    ) -> Dataset:
        """
        Merge new rows into the existing HF Dataset. If 'allow_update' is False,
        we skip duplicates (based on 'unique_id'). If 'allow_update' is True,
        we overwrite matching duplicates with data from 'new_data'.
        """
        df_existing = hf_dataset.to_pandas()
        df_new = pd.DataFrame(new_data)

        # Clean datetime columns in new data to avoid NaT conversion issues
        datetime_cols = ['published_at', 'updated_datetime', 'extracted_at']
        for col in datetime_cols:
            if col in df_new.columns:
                # Replace None with pd.NaT for proper datetime handling
                df_new[col] = pd.to_datetime(df_new[col], errors='coerce')

        # Ensure both DataFrames have same columns
        all_cols = set(df_existing.columns).union(df_new.columns)
        for col in all_cols:
            if col not in df_existing.columns:
                df_existing[col] = None
            if col not in df_new.columns:
                df_new[col] = None

        # Drop duplicates in existing / new data by 'unique_id' column
        df_existing.drop_duplicates(subset="unique_id", keep="first", inplace=True)
        df_new.drop_duplicates(subset="unique_id", keep="first", inplace=True)

        # Set 'unique_id' as the index
        df_existing.set_index("unique_id", inplace=True)
        df_new.set_index("unique_id", inplace=True)

        if allow_update:
            # Overwrite existing rows with new data if there's a matching unique_id
            df_existing.update(df_new)

            # Find truly new items (unique_ids not in df_existing)
            missing_ids = df_new.index.difference(df_existing.index)
            if not missing_ids.empty:
                logging.info(f"Inserting {len(missing_ids)} brand new rows.")
                df_existing = pd.concat([df_existing, df_new.loc[missing_ids]], axis=0)
            else:
                logging.info(
                    "All 'unique_id's in 'new_data' already existed and were updated."
                )
        else:
            # If not updating, skip duplicates
            duplicates = df_new.index.intersection(df_existing.index)
            if not duplicates.empty:
                logging.info(
                    f"Skipping {len(duplicates)} duplicates (already in dataset)."
                )

            # Filter to only new rows (unique_id not present in the existing dataset)
            df_filtered = df_new.loc[df_new.index.difference(df_existing.index)]
            if df_filtered.empty:
                logging.info("No new unique items to add; dataset is up to date.")
            else:
                logging.info(f"Adding {len(df_filtered)} new items.")
                df_existing = pd.concat([df_existing, df_filtered], axis=0)

        df_existing.reset_index(inplace=True)

        # Convert back to a HF Dataset
        return Dataset.from_pandas(df_existing, preserve_index=False)

    def _apply_updates(self, hf_dataset: Dataset, updated_df: pd.DataFrame) -> Dataset:
        """
        For each row in 'updated_df', update matching rows in the existing dataset by 'unique_id'.
        If new columns are present, they will be added to the DataFrame with default None,
        then filled for any matching row.
        """
        df = hf_dataset.to_pandas()

        # Clean datetime columns in updated_df to avoid NaT conversion issues
        datetime_cols = ['published_at', 'updated_datetime', 'extracted_at']
        for col in datetime_cols:
            if col in updated_df.columns:
                # Replace None with pd.NaT for proper datetime handling
                updated_df[col] = pd.to_datetime(updated_df[col], errors='coerce')

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
        Additionally, push a reduced version of the dataset (govbrnews-small) containing only
        'published_at', 'agency', 'title', and 'url' columns.
        """
        # Convert the dataset to a Pandas DataFrame once
        df = dataset.to_pandas()

        self._push_dataset_to_hub(dataset)
        self._push_reduced_dataset(df)
        # self._push_global_csv(dataset)
        # self._push_csvs_by_agency(df)
        # self._push_csvs_by_year(df)

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

    def _push_csvs_by_agency(self, df: pd.DataFrame):
        """
        Split the dataset by 'agency' and upload CSV files for each agency.

        :param df: The Pandas DataFrame representation of the full dataset.
        """
        self._push_csvs_by_group(df, group_by_column="agency", subfolder="agencies")

    def _push_csvs_by_year(self, df: pd.DataFrame):
        """
        Split the dataset by year (derived from 'published_at') and upload CSV files for each year.

        :param df: The Pandas DataFrame representation of the full dataset.
        """
        self._push_csvs_by_group(df, group_by_column="year", subfolder="years")

    def _push_csvs_by_group(
        self, df: pd.DataFrame, group_by_column: str, subfolder: str = ""
    ):
        """
        Split the dataset by a specified column (e.g., 'agency' or 'year') and upload CSV files
        for each distinct group in that column.

        :param df: The Pandas DataFrame representation of the full dataset.
        :param group_by_column: Column name to group by (e.g., 'agency' or 'year').
        :param subfolder: Optional subfolder in the repository to place the CSV file.
        """
        # If grouping by 'year', ensure the column is extracted from 'published_at'
        if group_by_column == "year":
            df["year"] = df["published_at"].apply(
                lambda x: x.year if hasattr(x, "year") else None
            )

        groups = df.groupby(group_by_column)
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

    def _push_reduced_dataset(self, df: pd.DataFrame):
        """
        Create a reduced version of the dataset containing only specific columns,
        and push it to the Hugging Face Hub.

        :param df: The Pandas DataFrame representation of the full dataset.
        """
        reduced_df = df[["published_at", "agency", "title", "url"]]
        reduced_dataset = Dataset.from_pandas(reduced_df, preserve_index=False)

        # Push the reduced dataset to the Hugging Face Hub
        reduced_dataset.push_to_hub(REDUCED_DATASET_PATH, private=False)
        logging.info(
            f"Reduced dataset pushed to Hugging Face Hub at {REDUCED_DATASET_PATH}."
        )
