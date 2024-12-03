import logging
import os
import tempfile
from typing import Dict, Any

from datasets import Dataset
from huggingface_hub import HfApi, HfFolder


class HuggingFaceDatasetUploader:
    """
    A class responsible for uploading datasets and files to the Hugging Face Hub.

    **Types of Uploads:**
    - **Dataset Upload**: Pushes the entire dataset to the Hugging Face Hub, making it available for use with the 🤗 Datasets library.
    - **Global CSV Upload**: Saves the entire dataset as a single CSV file and uploads it to the dataset repository.
    - **CSV by Agency Upload**: Splits the dataset by the 'agency' column and uploads a separate CSV file for each agency.
    - **CSV by Year Upload**: Splits the dataset by the 'published_at' year and uploads a separate CSV file for each year.

    This class ensures efficient uploading by minimizing code duplication and handling authentication and temporary file management internally.
    """

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.api = HfApi()
        self.token = HfFolder.get_token()
        if not self.token:
            raise ValueError(
                "Hugging Face authentication token is missing. Please login using `huggingface-cli login`."
            )

    def push_dataset_to_hub(self, dataset: Dataset):
        """
        Push the entire dataset to the Hugging Face Hub.

        :param dataset: The dataset to push.
        """
        dataset.push_to_hub(self.dataset_path, private=False)
        logging.info(f"Dataset pushed to Hugging Face Hub at {self.dataset_path}.")

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
            self.api.upload_file(
                path_or_fileobj=csv_file_path,
                path_in_repo=path_in_repo,
                repo_id=self.dataset_path,
                repo_type="dataset",
                token=self.token,
            )

            logging.info(
                f"CSV file '{file_name}' uploaded to the Hugging Face repository at '{path_in_repo}'."
            )

    def push_global_csv(self, dataset: Dataset):
        """
        Save the entire dataset as a CSV file and upload it to the Hugging Face dataset repository.

        :param dataset: The dataset to save and upload as a CSV file.
        """
        self._save_and_upload_csv(dataset, "govbr_news_dataset.csv")

    def push_csvs_by_group(
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

    def push_csvs_by_agency(self, dataset: Dataset):
        """
        Split the dataset by 'agency' and upload CSV files for each agency.

        :param dataset: The dataset to split and upload.
        """
        self.push_csvs_by_group(dataset, group_by_column="agency", subfolder="agencies")

    def push_csvs_by_year(self, dataset: Dataset):
        """
        Split the dataset by 'published_at' year and upload CSV files for each year.

        :param dataset: The dataset to split and upload.
        """
        self.push_csvs_by_group(dataset, group_by_column="year", subfolder="years")

    def create_and_push_dataset(self, column_data: Dict[str, Any]):
        """
        Create a Hugging Face Dataset from the columnar data and push it to the Hub,
        along with CSV file versions for easy download.

        :param column_data: The data in columnar format.
        """
        # Create the Dataset
        combined_dataset = Dataset.from_dict(column_data)

        # Push the dataset
        self.push_dataset_to_hub(combined_dataset)

        # Push the CSVs
        self.push_global_csv(combined_dataset)
        self.push_csvs_by_agency(combined_dataset)
        self.push_csvs_by_year(combined_dataset)
