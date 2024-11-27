import hashlib
import logging
from collections import OrderedDict
from datetime import date
from typing import Dict, List

from datasets import Dataset, load_dataset
from datasets.exceptions import DatasetNotFoundError

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

        # Preprocess new data
        new_data = self.preprocess_data(news_data)

        # Check if the dataset already exists
        try:
            existing_dataset = load_dataset(self.dataset_path, split="train")
            logging.info("Existing dataset loaded from Hugging Face Hub.")

            # Get the set of existing unique_ids
            existing_unique_ids = set(existing_dataset["unique_id"])
            logging.info(f"Existing dataset has {len(existing_unique_ids)} entries.")

            # Filter out new data that has duplicate unique_ids
            new_unique_ids = set(new_data["unique_id"])
            unique_ids_to_add = new_unique_ids - existing_unique_ids

            if not unique_ids_to_add:
                logging.info("No new unique news items to add. Dataset is up to date.")
                return

            # Create filtered new data
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

            # Combine existing data with filtered new data
            combined_data = {
                key: existing_dataset[key] + filtered_new_data.get(key, [])
                for key in existing_dataset.features.keys()
            }

        except DatasetNotFoundError:
            logging.info("No existing dataset found. Creating a new dataset.")
            combined_data = new_data

        # Sort the combined data by 'agency' (asc) and 'published_at' (desc)
        sorted_data = sorted(
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

        # Convert sorted data back to columnar format
        column_data = {
            key: [item.get(key, None) for item in sorted_data]
            for key in combined_data.keys()
        }

        # Create the combined dataset
        combined_dataset = Dataset.from_dict(column_data)

        # Push the combined dataset to the Hub
        self.push_dataset_to_hub(combined_dataset)

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

    def generate_unique_id(self, agency, published_at_value, title):
        """
        Generate a unique identifier based on the agency, published_at, and title.

        :param agency: The agency name.
        :param published_at_value: The published_at date of the news item (datetime.date).
        :param title: The title of the news item.
        :return: A unique hash string.
        """
        date_str = (
            published_at_value.isoformat()
            if isinstance(published_at_value, date)
            else "Unknown Date"
        )
        hash_input = f"{agency}_{date_str}_{title}".encode("utf-8")
        return hashlib.md5(hash_input).hexdigest()
