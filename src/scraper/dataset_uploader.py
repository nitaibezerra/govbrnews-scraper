import logging
import os
import tempfile

from datasets import Dataset
from huggingface_hub import HfApi, HfFolder


class HuggingFaceDatasetUploader:
    """
    A class responsible for uploading datasets and files to the Hugging Face Hub.
    """

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path

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
            repo_id = self.dataset_path

            # Define the destination path for the CSV in the repository
            path_in_repo = os.path.basename(csv_file_path)

            # Use the HfApi.upload_file method to upload the file directly
            api.upload_file(
                path_or_fileobj=csv_file_path,
                path_in_repo=path_in_repo,
                repo_id=repo_id,
                repo_type="dataset",
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
            repo_id = self.dataset_path

            for agency, csv_file_path in csv_paths:
                # Define the destination path for the CSV in the repository
                path_in_repo = f"{agency}_news_dataset.csv"

                # Use the HfApi.upload_file method to upload the file directly
                api.upload_file(
                    path_or_fileobj=csv_file_path,
                    path_in_repo=path_in_repo,
                    repo_id=repo_id,
                    repo_type="dataset",
                    token=token,
                )

                logging.info(
                    f"CSV for agency '{agency}' uploaded to the Hugging Face repository: {repo_id}/{path_in_repo}"
                )

    def create_and_push_dataset(self, column_data: dict):
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
