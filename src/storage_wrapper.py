"""
Storage wrapper that uses StorageAdapter when available,
falls back to DatasetManager for legacy operations.

This wrapper enables dual-write mode where data is written to both
PostgreSQL and HuggingFace simultaneously.

Environment variables:
- STORAGE_BACKEND: 'huggingface' (default), 'postgres', or 'dual_write'
- STORAGE_READ_FROM: 'huggingface' (default) or 'postgres'
- DATABASE_URL: PostgreSQL connection string (required for postgres/dual_write)
- HF_TOKEN: HuggingFace token (required for huggingface/dual_write)
"""

import logging
import os
from typing import Optional, OrderedDict

import pandas as pd

logger = logging.getLogger(__name__)


class StorageWrapper:
    """
    Unified storage interface that abstracts backend selection.

    Supports three modes:
    - huggingface: Write to HuggingFace only (legacy behavior)
    - postgres: Write to PostgreSQL only
    - dual_write: Write to both backends (migration phase)
    """

    def __init__(self):
        self.backend = os.getenv("STORAGE_BACKEND", "huggingface").lower()
        self._storage = None
        self._use_adapter = False

        logger.info(f"StorageWrapper initializing with backend: {self.backend}")

        if self.backend in ("postgres", "dual_write"):
            self._init_storage_adapter()
        else:
            self._init_dataset_manager()

    def _init_storage_adapter(self):
        """Initialize StorageAdapter from data-platform."""
        try:
            from data_platform.managers import StorageAdapter

            logger.info("Using StorageAdapter for storage operations")
            self._storage = StorageAdapter()
            self._use_adapter = True
        except ImportError as e:
            logger.error(
                f"Failed to import StorageAdapter: {e}. "
                "Make sure data-platform is installed: pip install -e ../data-platform"
            )
            raise ImportError(
                "StorageAdapter not found. Install data-platform or set STORAGE_BACKEND=huggingface"
            ) from e

    def _init_dataset_manager(self):
        """Initialize legacy DatasetManager."""
        from dataset_manager import DatasetManager

        logger.info("Using DatasetManager (HuggingFace) for storage operations")
        self._storage = DatasetManager()
        self._use_adapter = False

    def insert(self, new_data: OrderedDict, allow_update: bool = False) -> int:
        """
        Insert new records into storage.

        Args:
            new_data: OrderedDict with arrays for each column
            allow_update: If True, update existing records with same unique_id

        Returns:
            Number of records inserted/updated
        """
        total = len(new_data.get("unique_id", []))
        logger.info(f"Inserting {total} records (backend={self.backend})")

        result = self._storage.insert(new_data, allow_update=allow_update)

        # DatasetManager doesn't return count, so return total
        if not self._use_adapter:
            return total
        return result

    def update(self, updated_df: pd.DataFrame) -> int:
        """
        Update existing records in storage.

        Args:
            updated_df: DataFrame with updates (must include unique_id column)

        Returns:
            Number of records updated
        """
        total = len(updated_df)
        logger.info(f"Updating {total} records (backend={self.backend})")

        result = self._storage.update(updated_df)

        # DatasetManager doesn't return count, so return total
        if not self._use_adapter:
            return total
        return result

    def get(
        self, min_date: str, max_date: str, agency: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get records from storage by date range.

        Args:
            min_date: Minimum date (YYYY-MM-DD)
            max_date: Maximum date (YYYY-MM-DD)
            agency: Optional agency filter

        Returns:
            DataFrame with matching records
        """
        logger.info(f"Getting records: {min_date} to {max_date} (backend={self.backend})")
        return self._storage.get(min_date, max_date, agency=agency)

    # -------------------------------------------------------------------------
    # Legacy methods for enrichment (only work with DatasetManager)
    # -------------------------------------------------------------------------

    def _load_existing_dataset(self):
        """
        Load existing dataset from HuggingFace.

        Note: This method only works with DatasetManager backend.
        For StorageAdapter, use get() instead.
        """
        if self._use_adapter:
            raise NotImplementedError(
                "_load_existing_dataset() is not available with StorageAdapter. "
                "Use get(min_date, max_date) instead."
            )
        return self._storage._load_existing_dataset()

    def _push_dataset_and_csvs(self, dataset):
        """
        Push dataset and CSVs to HuggingFace.

        Note: This method only works with DatasetManager backend.
        StorageAdapter handles push automatically on insert/update.
        """
        if self._use_adapter:
            raise NotImplementedError(
                "_push_dataset_and_csvs() is not available with StorageAdapter. "
                "Data is pushed automatically on insert/update."
            )
        return self._storage._push_dataset_and_csvs(dataset)

    @property
    def dataset_path(self) -> str:
        """Get the HuggingFace dataset path (for legacy compatibility)."""
        if self._use_adapter:
            return "nitaibezerra/govbrnews"  # Default path
        return self._storage.dataset_path
