import hashlib
import logging
from collections import OrderedDict
from datetime import date
from typing import Dict, List, Optional

from dataset_manager import DatasetManager
from datasets import Dataset

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class DataProcessor:
    """
    A class that focuses on the preprocessing, transformation, and preparation of raw news data
    into a well-structured format ready for dataset creation and analysis.

    Responsibilities:
    - Generating unique identifiers for news items based on their attributes (agency, published date, and title).
    - Converting raw data from a list-of-dictionaries format into a columnar (OrderedDict) format.
    - Merging new data with an existing dataset, ensuring no duplicates by comparing unique IDs.
    - Sorting the combined dataset by specified criteria (e.g., agency and publication date).
    - Preparing the final processed data into columnar format suitable for integration with a dataset manager.
    """

    def __init__(self, dataset_manager: DatasetManager):
        self.dataset_manager = dataset_manager

    def process_and_upload_data(self, new_data):
        """
        Process the news data and upload it to the Hugging Face dataset.
        """
        new_data = self._preprocess_data(new_data)
        existing_data = self.dataset_manager.load_existing_dataset()
        combined_data = self.merge_new_data_into_existing(new_data, existing_data)

        self.dataset_manager.create_and_push_dataset(combined_data)

    def _preprocess_data(self, data: List[Dict[str, str]]) -> OrderedDict:
        """
        Preprocess data by:
        - Adding the unique_id column.
        - Reordering columns.

        :param data: List of news items as dictionaries.
        :return: An OrderedDict with the processed data.
        """
        # Generate unique_id for each record
        for item in data:
            item["unique_id"] = self._generate_unique_id(
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

    def _generate_unique_id(
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

    def merge_new_data_into_existing(
        self, new_data: OrderedDict, existing_data: Optional[Dataset]
    ) -> OrderedDict:
        """
        existing_data is now passed in from outside. If it is None, it means no existing dataset.
        """
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
