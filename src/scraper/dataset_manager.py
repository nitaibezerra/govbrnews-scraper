import hashlib
import logging
import os
import tempfile
from collections import OrderedDict
from datetime import date
from typing import Dict, List

from datasets import Dataset, load_dataset
from datasets.exceptions import DatasetNotFoundError
from huggingface_hub import HfApi, HfFolder

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DATASET_PATH = "nitaibezerra/govbrnews"  # The name of the Hugging Face dataset


class DatasetManager:
    def __init__(self, dataset_path: str = DATASET_PATH):
        self.dataset_path = dataset_path

    def append_to_huggingface_dataset(self, news_data: List[Dict[str, str]]):
        """
        Append the scraped news data to a Hugging Face dataset, ensuring no duplicates are added,
        and sort the final dataset by agency (asc) and published_at (desc).
        """
        if not news_data:
            logging.info("No news data to append.")
            return

        # Step 1: Preprocess the new data
        new_data = self.preprocess_data(news_data)

        # Step 2: Load existing dataset or initialize combined_data
        combined_data = self.load_existing_and_merge_with_new(new_data)

        # Step 3: Sort the combined data
        sorted_data = self.sort_combined_data(combined_data)

        # Step 4: Convert sorted data to columnar format
        column_data = self.convert_to_columnar_format(sorted_data)

        # Step 5: Create and push the dataset to Hugging Face
        self.create_and_push_dataset(column_data)

    def load_existing_and_merge_with_new(self, new_data: OrderedDict) -> OrderedDict:
        """
        Load the existing dataset from Hugging Face and merge it with the new data,
        avoiding duplicates. If no new data is found, return the existing dataset
        in columnar format.

        :param new_data: The new data to be added, in columnar format.
        :return: The combined dataset in columnar format, or the existing dataset
                if no new data is found.
        """
        try:
            existing_dataset = load_dataset(self.dataset_path, split="train")
            logging.info("Existing dataset loaded from Hugging Face Hub.")

            # Identify unique IDs already in the existing dataset
            existing_unique_ids = set(existing_dataset["unique_id"])
            logging.info(f"Existing dataset has {len(existing_unique_ids)} entries.")

            # Filter out new data that has duplicate unique_ids
            unique_ids_to_add = set(new_data["unique_id"]) - existing_unique_ids
            if not unique_ids_to_add:
                logging.info("No new unique news items to add. Dataset is up to date.")
                # Return the existing dataset in columnar format
                return {
                    key: existing_dataset[key]
                    for key in existing_dataset.features.keys()
                }

            filtered_new_data = {
                key: [
                    value
                    for idx, value in enumerate(values)
                    if new_data["unique_id"][idx] in unique_ids_to_add
                ]
                for key, values in new_data.items()
            }
            logging.info(
                f"Adding {len(filtered_new_data['unique_id'])} "
                "new unique news items to the dataset."
            )

            # Combine existing and filtered new data
            combined_data = {
                key: existing_dataset[key] + filtered_new_data.get(key, [])
                for key in existing_dataset.features.keys()
            }

        except DatasetNotFoundError:
            logging.info("No existing dataset found. Initializing with new data.")
            combined_data = new_data

        return combined_data

    def sort_combined_data(self, combined_data: OrderedDict) -> List[Dict[str, str]]:
        """
        Sort the combined dataset by 'agency' (asc) and 'published_at' (desc).
        """
        return sorted(
            [
                {key: combined_data[key][i] for key in combined_data.keys()}
                for i in range(len(combined_data["unique_id"]))
            ],
            key=lambda x: (
                x.get("agency", ""),
                -x.get("published_at").toordinal()
                if isinstance(x.get("published_at"), date)
                else float("-inf"),
            ),
        )

    def convert_to_columnar_format(
        self, sorted_data: List[Dict[str, str]]
    ) -> OrderedDict:
        """
        Convert sorted data from list-of-dictionaries format to columnar format.
        """
        return {
            key: [item.get(key, None) for item in sorted_data]
            for key in sorted_data[0].keys()
        }

    def create_and_push_dataset(self, column_data: OrderedDict):
        """
        Create a Hugging Face Dataset from the columnar data and push it to the Hub,
        along with a CSV file version for easy download.
        """
        # Create the Dataset
        combined_dataset = Dataset.from_dict(column_data)

        # Push the dataset
        self.push_dataset_to_hub(combined_dataset)

        # Push the CSVs
        self.push_global_csv(combined_dataset)
        self.push_csvs_by_agency(combined_dataset)

    def preprocess_data(self, data: List[Dict[str, str]]) -> OrderedDict:
        """
        Preprocess data by:
        - Adding the unique_id column.
        - Reordering columns.

        :param data: List of news items as dictionaries.
        :return: An OrderedDict with the processed data.
        """
        # Generate unique_id for each record
        for item in data:
            item["unique_id"] = self.generate_unique_id(
                item.get("agency", ""),
                item.get("published_at", ""),
                item.get("title", ""),
            )

        # Convert to columnar format
        column_data = {
            key: [item.get(key, None) for item in data] for key in data[0].keys()
        }

        # Reorder columns
        ordered_column_data = OrderedDict()
        if "unique_id" in column_data:
            ordered_column_data["unique_id"] = column_data.pop("unique_id")
        if "agency" in column_data:
            ordered_column_data["agency"] = column_data.pop("agency")
        if "published_at" in column_data:
            ordered_column_data["published_at"] = column_data.pop("published_at")
        ordered_column_data.update(column_data)

        return ordered_column_data

    def push_dataset_to_hub(self, dataset: Dataset):
        """
        Push a dataset to the Hugging Face Hub.

        :param dataset: The dataset to push.
        """
        dataset.push_to_hub(self.dataset_path, private=False)
        logging.info(f"Dataset pushed to Hugging Face Hub at {self.dataset_path}.")

    def push_global_csv(self, dataset: Dataset):
        """
        Save the dataset as a CSV file in a temporary directory and push it
        to the Hugging Face dataset repository using git-lfs.

        :param dataset: The dataset to save and upload as a CSV file.
        """
        # Ensure the user is authenticated
        token = HfFolder.get_token()
        if not token:
            raise ValueError(
                "Hugging Face authentication token is missing. Please login using `huggingface-cli login`."
            )

        # Create a temporary directory for storing the CSV file
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_file_path = os.path.join(tmp_dir, "govbr_news_dataset.csv")

            # Save the dataset as a CSV file
            dataset.to_csv(csv_file_path)
            logging.info(f"Temporary CSV file created at {csv_file_path}")

            # Upload the file to the Hugging Face repository
            api = HfApi()
            repo_id = self.dataset_path  # e.g., "nitaibezerra/govbrnews"

            # Define the destination path for the CSV in the repository
            path_in_repo = os.path.basename(csv_file_path)

            # Use the HfApi.upload_file method to upload the file directly
            api.upload_file(
                path_or_fileobj=csv_file_path,
                path_in_repo=path_in_repo,
                repo_id=repo_id,
                repo_type="dataset",  # Ensure this uploads to the dataset repository
                token=token,
            )

            logging.info(
                f"CSV file uploaded to the Hugging Face repository: {repo_id}/{path_in_repo}"
            )

    def push_csvs_by_agency(self, dataset: Dataset):
        """
        Split the dataset by agency and publish one CSV file per agency to the Hugging Face dataset repository.

        :param dataset: The dataset to split and upload as CSV files.
        """
        # Ensure the user is authenticated
        token = HfFolder.get_token()
        if not token:
            raise ValueError(
                "Hugging Face authentication token is missing. Please login using `huggingface-cli login`."
            )

        # Create a temporary directory for storing the CSV files
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Split dataset by agency
            agency_groups = dataset.to_pandas().groupby("agency")

            csv_paths = []
            for agency, group in agency_groups:
                # Create a CSV file for each agency
                csv_file_path = os.path.join(tmp_dir, f"{agency}_news_dataset.csv")
                group.to_csv(csv_file_path, index=False)
                csv_paths.append((agency, csv_file_path))
                logging.info(
                    f"Temporary CSV for agency '{agency}' created at {csv_file_path}"
                )

            # Upload each CSV file to Hugging Face
            api = HfApi()
            repo_id = self.dataset_path  # e.g., "nitaibezerra/govbrnews"

            for agency, csv_file_path in csv_paths:
                # Define the destination path for the CSV in the repository
                path_in_repo = f"{agency}_news_dataset.csv"

                # Use the HfApi.upload_file method to upload the file directly
                api.upload_file(
                    path_or_fileobj=csv_file_path,
                    path_in_repo=path_in_repo,
                    repo_id=repo_id,
                    repo_type="dataset",  # Ensure this uploads to the dataset repository
                    token=token,
                )

                logging.info(
                    f"CSV for agency '{agency}' uploaded to the Hugging Face repository: {repo_id}/{path_in_repo}"
                )

    def generate_unique_id(
        self, agency: str, published_at_value: str, title: str
    ) -> str:
        """
        Generate a unique identifier based on the agency, published_at, and title.

        :param agency: The agency name.
        :param published_at_value: The published_at date of the news item (string format or datetime.date).
        :param title: The title of the news item.
        :return: A unique hash string.
        """
        date_str = (
            published_at_value.isoformat()
            if isinstance(published_at_value, date)
            else str(published_at_value)
        )
        hash_input = f"{agency}_{date_str}_{title}".encode("utf-8")
        return hashlib.md5(hash_input).hexdigest()
