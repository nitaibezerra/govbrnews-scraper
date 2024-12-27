import logging
import os
import tempfile
from datetime import date
from typing import Dict, List, Optional, OrderedDict

import requests
from datasets import Dataset, load_dataset
from datasets.exceptions import DatasetNotFoundError
from huggingface_hub import HfApi, HfFolder
from retry import retry

DATASET_PATH = "nitaibezerra/govbrnews"  # The name of the Hugging Face dataset


class DatasetManager:
    """
    A class responsible for interacting with the Hugging Face Hub for datasets.

    Responsibilities:
    - Load an existing dataset from the Hugging Face Hub.
    - Push new or updated datasets to the Hub.
    - Save datasets as CSV files and upload them for easy download.
    - Split and upload datasets by specific attributes (e.g., by 'agency' or 'year').

    By separating these responsibilities from data processing, the data processing code can
    remain focused solely on merging, cleaning, and transforming the data.
    """

    def __init__(self):
        self.dataset_path = DATASET_PATH
        self.api = HfApi()
        self.token = HfFolder.get_token()
        if not self.token:
            raise ValueError(
                "Hugging Face authentication token is missing. Please login using `huggingface-cli login`."
            )

    def insert(self, new_data: OrderedDict):
        """
        Add new data to the existing dataset and upload to Hugging Face.
        It ignores duplicates based on unique_id keeping the current values.
        """
        updated_dataset = self._merge_new_data_into_existing(new_data)
        self._create_and_push_dataset(updated_dataset)

    def _merge_new_data_into_existing(self, new_data: OrderedDict) -> OrderedDict:
        """
        existing_data is now passed in from outside. If it is None, it means no existing dataset.
        """
        existing_data = self._load_existing_dataset()

        if existing_data is None:
            logging.info("No existing dataset found. Initializing with new data.")
            return new_data

        logging.info("Existing dataset loaded from outside.")

        existing_unique_ids = set(existing_data["unique_id"])
        logging.info(f"Existing dataset has {len(existing_unique_ids)} entries.")

        unique_ids_to_add = set(new_data["unique_id"]) - existing_unique_ids
        if not unique_ids_to_add:
            logging.info("No new unique news items to add. Dataset is up to date.")
            return {key: existing_data[key] for key in existing_data.features.keys()}

        filtered_new_data = {
            key: [
                value
                for idx, value in enumerate(values)
                if new_data["unique_id"][idx] in unique_ids_to_add
            ]
            for key, values in new_data.items()
        }

        logging.info(
            f"Adding {len(filtered_new_data['unique_id'])} new unique news items to the dataset."
        )

        combined_data = {
            key: existing_data[key] + filtered_new_data.get(key, [])
            for key in existing_data.features.keys()
        }

        sorted_data = self._sort_data(combined_data)

        return sorted_data

    def _load_existing_dataset(self) -> Optional[Dataset]:
        """
        Attempt to load an existing dataset from the Hugging Face Hub.
        If the dataset does not exist, return None.
        """
        try:
            existing_dataset = load_dataset(self.dataset_path, split="train")
            logging.info(f"Existing dataset loaded from {self.dataset_path}.")
            return existing_dataset
        except DatasetNotFoundError:
            logging.info(f"No existing dataset found at {self.dataset_path}.")
            return None

    def _sort_data(self, ordered_data: OrderedDict) -> List[Dict[str, str]]:
        """
        Sort the dataset by 'agency' (asc) and 'published_at' (desc).

        :param ordered_data: The combined data in columnar format.
        :return: A list of dictionaries representing the sorted data.
        """
        return sorted(
            [
                {key: ordered_data[key][i] for key in ordered_data.keys()}
                for i in range(len(ordered_data["unique_id"]))
            ],
            key=lambda x: (
                x.get("agency", ""),
                -x.get("published_at").toordinal()
                if isinstance(x.get("published_at"), date)
                else float("-inf"),
            ),
        )

    def _create_and_push_dataset(self, dataset: List[Dict[str, str]]):
        """
        Create a Hugging Face Dataset from the columnar data and push it to the Hub,
        along with CSV file versions for easy download.

        :param column_data: The data in columnar format.
        """
        column_data = self._convert_to_columnar_format(dataset)

        # Create the Dataset
        combined_dataset = Dataset.from_dict(column_data)

        # Push the dataset
        self._push_dataset_to_hub(combined_dataset)

        # Push the CSVs
        self._push_global_csv(combined_dataset)
        self._push_csvs_by_agency(combined_dataset)
        self._push_csvs_by_year(combined_dataset)

    def _convert_to_columnar_format(
        self, sorted_data: List[Dict[str, str]]
    ) -> OrderedDict:
        """
        Convert sorted data from list-of-dictionaries format to columnar format.

        :param sorted_data: The sorted data as a list of dictionaries.
        :return: An OrderedDict representing the data in columnar format.
        """
        return {
            key: [item.get(key, None) for item in sorted_data]
            for key in sorted_data[0].keys()
        }

    def _push_dataset_to_hub(self, dataset: Dataset):
        """
        Push the entire dataset to the Hugging Face Hub.

        :param dataset: The dataset to push.
        """
        dataset.push_to_hub(self.dataset_path, private=False)
        logging.info(f"Dataset pushed to Hugging Face Hub at {self.dataset_path}.")

    @retry(
        exceptions=requests.exceptions.RequestException,
        tries=5,
        delay=2,
        backoff=3,
        jitter=(1, 3),
    )
    def _upload_file(self, path_or_fileobj, path_in_repo, repo_id):
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

    def _push_global_csv(self, dataset: Dataset):
        """
        Save the entire dataset as a CSV file and upload it to the Hugging Face dataset repository.

        :param dataset: The dataset to save and upload as a CSV file.
        """
        self._save_and_upload_csv(dataset, "govbr_news_dataset.csv")

    def _push_csvs_by_group(
        self, dataset: Dataset, group_by_column: str, subfolder: str = ""
    ):
        """
        Split the dataset by a specified column and upload CSV files for each group.

        :param dataset: The dataset to split and upload.
        :param group_by_column: The column to group by (e.g., 'agency' or 'year').
        :param subfolder: Optional subfolder in the repository to place the CSV files.
        """
        df = dataset.to_pandas()

        # If grouping by 'year', extract the year from the 'published_at' column
        if group_by_column == "year":
            df["year"] = df["published_at"].apply(lambda x: x.year)
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

    def _push_csvs_by_agency(self, dataset: Dataset):
        """
        Split the dataset by 'agency' and upload CSV files for each agency.

        :param dataset: The dataset to split and upload.
        """
        self._push_csvs_by_group(
            dataset, group_by_column="agency", subfolder="agencies"
        )

    def _push_csvs_by_year(self, dataset: Dataset):
        """
        Split the dataset by 'published_at' year and upload CSV files for each year.

        :param dataset: The dataset to split and upload.
        """
        self._push_csvs_by_group(dataset, group_by_column="year", subfolder="years")
