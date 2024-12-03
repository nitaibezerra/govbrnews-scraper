import hashlib
import logging
from collections import OrderedDict
from datetime import date
from typing import Dict, List

from datasets import load_dataset
from datasets.exceptions import DatasetNotFoundError

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class DataProcessor:
    """
    A class responsible for data preprocessing, manipulation, and formatting.
    """

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path

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

        :param combined_data: The combined data in columnar format.
        :return: A list of dictionaries representing the sorted data.
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

        :param sorted_data: The sorted data as a list of dictionaries.
        :return: An OrderedDict representing the data in columnar format.
        """
        return {
            key: [item.get(key, None) for item in sorted_data]
            for key in sorted_data[0].keys()
        }
