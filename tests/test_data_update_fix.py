import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.theme_enrichment_manager import ThemeEnrichmentManager


@pytest.mark.unit
class TestDataUpdateFix:
    """Comprehensive tests for the data update logic fix in ThemeEnrichmentManager."""

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables."""
        with patch.dict(os.environ, {'COGFY_API_KEY': 'test_api_key'}):
            yield

    @pytest.fixture
    def enrichment_manager(self, mock_env_vars):
        """Create ThemeEnrichmentManager with mocked dependencies."""
        with patch('src.theme_enrichment_manager.DatasetManager') as mock_dm:
            with patch('src.theme_enrichment_manager.CogfyClient') as mock_client:
                with patch('src.theme_enrichment_manager.CollectionManager') as mock_cm:
                    # Setup mocks
                    mock_dataset_manager = Mock()
                    mock_cogfy_client = Mock()
                    mock_collection_manager = Mock()

                    mock_dm.return_value = mock_dataset_manager
                    mock_client.return_value = mock_cogfy_client
                    mock_cm.return_value = mock_collection_manager

                    # Mock collection fields
                    mock_field1 = Mock()
                    mock_field1.id = 'field1'
                    mock_field1.name = 'unique_id'
                    mock_field1.type = 'text'

                    mock_field2 = Mock()
                    mock_field2.id = 'field2'
                    mock_field2.name = 'theme_1_level_1'
                    mock_field2.type = 'select'
                    mock_field2.data = {'select': {'options': []}}

                    mock_collection_manager.list_columns.return_value = [mock_field1, mock_field2]

                    manager = ThemeEnrichmentManager()
                    return manager

    def test_merge_with_full_dataset_data_integrity(self, enrichment_manager):
        """Test that _merge_with_full_dataset properly preserves data integrity."""
        # Create enriched data with themes
        enriched_df = pd.DataFrame({
            'unique_id': ['id1', 'id3', 'id999'],  # id999 doesn't exist in full dataset
            'theme_1_level_1': ['Education', 'Health', 'NonExistent'],
            'other_col': ['X', 'Y', 'Z']  # Additional column that should be ignored
        })

        # Mock the full dataset
        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3', 'id4'],
            'theme_1_level_1': [None, 'OriginalTheme', None, None],
            'other_column': ['A', 'B', 'C', 'D']
        })
        full_dataset_mock.to_pandas.return_value = full_df.copy()
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Apply the merge
        result = enrichment_manager._merge_with_full_dataset(enriched_df, start_date="2025-01-01")

        # Verify the results
        assert len(result) == 4  # Should maintain full dataset size
        assert result.loc[result['unique_id'] == 'id1', 'theme_1_level_1'].iloc[0] == 'Education'  # Updated
        assert result.loc[result['unique_id'] == 'id2', 'theme_1_level_1'].iloc[0] == 'OriginalTheme'  # Unchanged
        assert result.loc[result['unique_id'] == 'id3', 'theme_1_level_1'].iloc[0] == 'Health'  # Updated
        assert pd.isna(result.loc[result['unique_id'] == 'id4', 'theme_1_level_1'].iloc[0])  # Still None

        # Verify other columns are preserved
        assert list(result['other_column']) == ['A', 'B', 'C', 'D']

    def test_merge_with_full_dataset_duplicate_unique_ids(self, enrichment_manager):
        """Test handling of duplicate unique_ids in enriched data."""
        # Create enriched data with duplicates
        enriched_df = pd.DataFrame({
            'unique_id': ['id1', 'id1', 'id2'],  # Duplicate id1
            'theme_1_level_1': ['Education', 'Health', 'Science']
        })

        # Mock full dataset
        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2'],
            'theme_1_level_1': [None, None]
        })
        full_dataset_mock.to_pandas.return_value = full_df.copy()
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Apply the merge
        result = enrichment_manager._merge_with_full_dataset(enriched_df, start_date="2025-01-01")

        # Should handle duplicates gracefully - dict conversion keeps last value for each unique_id
        assert len(result) == 2
        assert result.loc[result['unique_id'] == 'id2', 'theme_1_level_1'].iloc[0] == 'Science'
        # id1 should get one of the values (Health, since it's last in the duplicate-removed dict)
        id1_theme = result.loc[result['unique_id'] == 'id1', 'theme_1_level_1'].iloc[0]
        assert id1_theme in ['Education', 'Health']  # Could be either depending on dict ordering

    def test_merge_with_full_dataset_missing_theme_column(self, enrichment_manager):
        """Test creation of theme_1_level_1 column when it doesn't exist."""
        enriched_df = pd.DataFrame({
            'unique_id': ['id1'],
            'theme_1_level_1': ['Education']
        })

        # Mock full dataset without theme column
        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2'],
            'other_column': ['A', 'B']
        })
        full_dataset_mock.to_pandas.return_value = full_df.copy()
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Apply the merge
        result = enrichment_manager._merge_with_full_dataset(enriched_df, start_date="2025-01-01")

        # Should create the column and apply updates
        assert 'theme_1_level_1' in result.columns
        assert result.loc[result['unique_id'] == 'id1', 'theme_1_level_1'].iloc[0] == 'Education'
        assert pd.isna(result.loc[result['unique_id'] == 'id2', 'theme_1_level_1'].iloc[0])

    def test_merge_with_full_dataset_empty_enriched_data(self, enrichment_manager):
        """Test merge with empty enriched DataFrame."""
        enriched_df = pd.DataFrame({
            'unique_id': [],
            'theme_1_level_1': []
        })

        # Mock full dataset
        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2'],
            'theme_1_level_1': [None, None]
        })
        full_dataset_mock.to_pandas.return_value = full_df.copy()
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Apply the merge
        result = enrichment_manager._merge_with_full_dataset(enriched_df, start_date="2025-01-01")

        # Should return unchanged full dataset
        assert len(result) == 2
        assert all(pd.isna(result['theme_1_level_1']))

    def test_merge_with_full_dataset_nan_themes_filtered(self, enrichment_manager):
        """Test that NaN themes are properly filtered out."""
        enriched_df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],
            'theme_1_level_1': ['Education', None, 'Health']  # id2 has None theme
        })

        # Mock full dataset
        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],
            'theme_1_level_1': [None, None, None]
        })
        full_dataset_mock.to_pandas.return_value = full_df.copy()
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Apply the merge
        result = enrichment_manager._merge_with_full_dataset(enriched_df, start_date="2025-01-01")

        # Should only update records with non-None themes
        assert result.loc[result['unique_id'] == 'id1', 'theme_1_level_1'].iloc[0] == 'Education'
        assert pd.isna(result.loc[result['unique_id'] == 'id2', 'theme_1_level_1'].iloc[0])  # Should remain None
        assert result.loc[result['unique_id'] == 'id3', 'theme_1_level_1'].iloc[0] == 'Health'

    def test_merge_with_full_dataset_no_date_filtering(self, enrichment_manager):
        """Test that without date filtering, the enriched df is returned as-is."""
        enriched_df = pd.DataFrame({
            'unique_id': ['id1', 'id2'],
            'theme_1_level_1': ['Education', 'Health']
        })

        # Should not call dataset manager when no date filtering
        result = enrichment_manager._merge_with_full_dataset(enriched_df)

        # Should return the input dataframe unchanged
        assert result.equals(enriched_df)
        enrichment_manager.dataset_manager._load_existing_dataset.assert_not_called()

    def test_merge_with_full_dataset_performance_with_large_data(self, enrichment_manager):
        """Test performance with larger datasets to ensure the fix scales well."""
        # Create larger enriched dataset
        n_records = 1000
        enriched_df = pd.DataFrame({
            'unique_id': [f'id{i}' for i in range(n_records)],
            'theme_1_level_1': [f'Theme{i%10}' for i in range(n_records)]  # 10 different themes
        })

        # Create larger full dataset
        full_n_records = 10000
        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': [f'id{i}' for i in range(full_n_records)],
            'theme_1_level_1': [None] * full_n_records,
            'other_data': [f'data{i}' for i in range(full_n_records)]
        })
        full_dataset_mock.to_pandas.return_value = full_df.copy()
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Apply the merge and time it
        import time
        start_time = time.time()
        result = enrichment_manager._merge_with_full_dataset(enriched_df, start_date="2025-01-01")
        end_time = time.time()

        # Verify results
        assert len(result) == full_n_records

        # Check that first 1000 records got themes
        for i in range(min(100, n_records)):  # Check first 100 for speed
            assert result.loc[result['unique_id'] == f'id{i}', 'theme_1_level_1'].iloc[0] == f'Theme{i%10}'

        # Check that remaining records still have None
        for i in range(n_records, min(n_records + 100, full_n_records)):  # Check first 100 of remaining
            assert pd.isna(result.loc[result['unique_id'] == f'id{i}', 'theme_1_level_1'].iloc[0])

        # Performance should be reasonable (under 5 seconds for this size)
        assert end_time - start_time < 5.0, f"Merge took too long: {end_time - start_time:.2f}s"

    def test_merge_preserves_column_order_and_types(self, enrichment_manager):
        """Test that merge preserves column order and data types."""
        enriched_df = pd.DataFrame({
            'unique_id': ['id1'],
            'theme_1_level_1': ['Education']
        })

        # Full dataset with specific column order and types
        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2'],
            'published_at': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'theme_1_level_1': [None, None],
            'count': [1, 2],
            'title': ['Title1', 'Title2']
        })
        full_dataset_mock.to_pandas.return_value = full_df.copy()
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Apply the merge
        result = enrichment_manager._merge_with_full_dataset(enriched_df, start_date="2025-01-01")

        # Should preserve column order
        assert list(result.columns) == ['unique_id', 'published_at', 'theme_1_level_1', 'count', 'title']

        # Should preserve data types
        assert result['published_at'].dtype == 'datetime64[ns]'
        assert result['count'].dtype == 'int64'
        assert result['unique_id'].dtype == 'object'

        # Should have updated the theme
        assert result.loc[result['unique_id'] == 'id1', 'theme_1_level_1'].iloc[0] == 'Education'

    def test_old_bug_would_have_failed(self, enrichment_manager):
        """Test case that would have failed with the old buggy implementation."""
        # This test simulates the exact scenario that would fail with the old code:
        # Index misalignment between enriched data and full dataset

        enriched_df = pd.DataFrame({
            'unique_id': ['id3', 'id1'],  # Different order than full dataset
            'theme_1_level_1': ['Health', 'Education']
        })

        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],  # Different order than enriched data
            'theme_1_level_1': [None, None, None]
        })
        full_dataset_mock.to_pandas.return_value = full_df.copy()
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Apply the merge
        result = enrichment_manager._merge_with_full_dataset(enriched_df, start_date="2025-01-01")

        # With the fix, this should work correctly despite different ordering
        assert result.loc[result['unique_id'] == 'id1', 'theme_1_level_1'].iloc[0] == 'Education'
        assert result.loc[result['unique_id'] == 'id3', 'theme_1_level_1'].iloc[0] == 'Health'
        assert pd.isna(result.loc[result['unique_id'] == 'id2', 'theme_1_level_1'].iloc[0])

        # The old buggy code would have incorrectly assigned:
        # id1 -> 'Health' (wrong!)
        # id2 -> 'Education' (wrong!)
        # id3 -> None (wrong!)
