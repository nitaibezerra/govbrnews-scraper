import os
import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

from src.theme_enrichment_manager import ThemeEnrichmentManager


@pytest.mark.unit
class TestThemeEnrichmentManager:
    """Unit tests for ThemeEnrichmentManager class."""

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables."""
        with patch.dict(os.environ, {'COGFY_API_KEY': 'test_api_key'}):
            yield

    @pytest.fixture
    def mock_dataset_manager(self):
        """Mock DatasetManager."""
        mock_manager = Mock()
        mock_dataset = Mock()
        mock_dataset.to_pandas.return_value = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],
            'published_at': ['2025-09-11', '2025-09-12', '2025-09-13'],
            'title': ['Title 1', 'Title 2', 'Title 3']
        })
        mock_manager._load_existing_dataset.return_value = mock_dataset
        return mock_manager

    @pytest.fixture
    def mock_cogfy_client(self):
        """Mock CogfyClient."""
        return Mock()

    @pytest.fixture
    def mock_collection_manager(self):
        """Mock CollectionManager."""
        mock_manager = Mock()
        # Mock collection fields for list_columns()
        mock_field1 = Mock()
        mock_field1.id = 'field1'
        mock_field1.name = 'unique_id'
        mock_field1.type = 'text'

        mock_field2 = Mock()
        mock_field2.id = 'field2'
        mock_field2.name = 'theme_1_level_1'
        mock_field2.type = 'select'
        mock_field2.data = {
            'select': {
                'options': [
                    {'id': 'theme1', 'label': 'Education'},
                    {'id': 'theme2', 'label': 'Health'}
                ]
            }
        }

        mock_field3 = Mock()
        mock_field3.id = 'field3'
        mock_field3.name = 'published_at'
        mock_field3.type = 'date'

        mock_manager.list_columns.return_value = [mock_field1, mock_field2, mock_field3]
        return mock_manager

    @pytest.fixture
    def enrichment_manager(self, mock_env_vars, mock_dataset_manager, mock_cogfy_client, mock_collection_manager):
        """Create ThemeEnrichmentManager with mocked dependencies."""
        with patch('src.theme_enrichment_manager.DatasetManager') as mock_dm_class:
            with patch('src.theme_enrichment_manager.CogfyClient') as mock_client_class:
                with patch('src.theme_enrichment_manager.CollectionManager') as mock_cm_class:
                    mock_dm_class.return_value = mock_dataset_manager
                    mock_client_class.return_value = mock_cogfy_client
                    mock_cm_class.return_value = mock_collection_manager

                    manager = ThemeEnrichmentManager()
                    return manager

    def test_init(self, mock_env_vars):
        """Test ThemeEnrichmentManager initialization."""
        with patch('src.theme_enrichment_manager.DatasetManager') as mock_dm:
            with patch('src.theme_enrichment_manager.CogfyClient') as mock_client:
                with patch('src.theme_enrichment_manager.CollectionManager') as mock_cm:
                    manager = ThemeEnrichmentManager()

                    assert manager.server_url == "https://api.cogfy.com/"
                    assert manager.collection_name == "noticiasgovbr-all-news"
                    mock_dm.assert_called_once()
                    mock_client.assert_called_once_with("test_api_key", base_url="https://api.cogfy.com/")

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('src.theme_enrichment_manager.DatasetManager'):
                with pytest.raises(ValueError, match="COGFY_API_KEY environment variable is not set"):
                    ThemeEnrichmentManager()

    def test_setup_cogfy_mappings(self, enrichment_manager):
        """Test _setup_cogfy_mappings method."""
        enrichment_manager._setup_cogfy_mappings()

        assert enrichment_manager._unique_id_field_id == 'field1'
        assert enrichment_manager._theme_field_id == 'field2'
        assert len(enrichment_manager._theme_options) == 2
        assert enrichment_manager._theme_options[0]['id'] == 'theme1'
        assert enrichment_manager._theme_options[0]['label'] == 'Education'
        assert enrichment_manager._theme_options[1]['id'] == 'theme2'
        assert enrichment_manager._theme_options[1]['label'] == 'Health'

    def test_extract_theme_id_from_record(self, enrichment_manager):
        """Test _extract_theme_id_from_record method."""
        enrichment_manager._theme_field_id = 'theme_field'

        # Test successful extraction
        record = {
            "properties": {
                "theme_field": {
                    "select": {
                        "value": [{"id": "theme1"}]
                    }
                }
            }
        }
        result = enrichment_manager._extract_theme_id_from_record(record)
        assert result == "theme1"

        # Test missing theme field
        record_no_theme = {"properties": {}}
        result = enrichment_manager._extract_theme_id_from_record(record_no_theme)
        assert result is None

        # Test empty select value
        record_empty = {
            "properties": {
                "theme_field": {
                    "select": {"value": []}
                }
            }
        }
        result = enrichment_manager._extract_theme_id_from_record(record_empty)
        assert result is None

    def test_map_theme_id_to_label(self, enrichment_manager):
        """Test _map_theme_id_to_label method."""
        enrichment_manager._theme_options = [
            {'id': 'theme1', 'label': 'Education'},
            {'id': 'theme2', 'label': 'Health'}
        ]

        # Test successful mapping
        assert enrichment_manager._map_theme_id_to_label('theme1') == 'Education'
        assert enrichment_manager._map_theme_id_to_label('theme2') == 'Health'

        # Test unknown theme
        assert enrichment_manager._map_theme_id_to_label('unknown') is None

        # Test None input
        assert enrichment_manager._map_theme_id_to_label(None) is None

    def test_build_single_day_filters(self, enrichment_manager):
        """Test _build_single_day_filters method."""
        enrichment_manager._field_map = {"published_at": "pub_field_id"}

        # Test with a single date
        filters = enrichment_manager._build_single_day_filters("2025-01-15")
        assert len(filters) == 2
        assert filters[0]["type"] == "greaterThanOrEquals"
        assert filters[1]["type"] == "lessThanOrEquals"
        assert "2025-01-15T00:00:00" in filters[0]["greaterThanOrEquals"]["value"]
        assert "2025-01-15T23:59:59" in filters[1]["lessThanOrEquals"]["value"]

        # Test missing published_at field
        enrichment_manager._field_map = {}
        with pytest.raises(ValueError, match="Required field 'published_at' not found"):
            enrichment_manager._build_single_day_filters("2025-01-15")

    def test_generate_date_range(self, enrichment_manager):
        """Test _generate_date_range method."""
        # Test with string dates
        date_range = enrichment_manager._generate_date_range("2025-01-15", "2025-01-17")
        assert len(date_range) == 3
        assert date_range[0].strftime("%Y-%m-%d") == "2025-01-15"
        assert date_range[1].strftime("%Y-%m-%d") == "2025-01-16"
        assert date_range[2].strftime("%Y-%m-%d") == "2025-01-17"

        # Test with datetime objects
        start_dt = pd.to_datetime("2025-01-15")
        end_dt = pd.to_datetime("2025-01-15")
        date_range = enrichment_manager._generate_date_range(start_dt, end_dt)
        assert len(date_range) == 1
        assert date_range[0].strftime("%Y-%m-%d") == "2025-01-15"

    def test_build_filter_criteria(self, enrichment_manager):
        """Test _build_filter_criteria method."""
        # Test with filters
        filters = [{"type": "equals", "equals": {"fieldId": "test", "value": "test"}}]
        criteria = enrichment_manager._build_filter_criteria(filters)
        assert criteria["type"] == "and"
        assert "filters" in criteria["and"]

        # Test with no filters
        criteria = enrichment_manager._build_filter_criteria([])
        assert criteria is None

    def test_query_single_day(self, enrichment_manager):
        """Test _query_single_day method."""
        enrichment_manager._field_map = {"published_at": "pub_field_id"}

        # Mock successful query
        enrichment_manager.collection_manager.query_records.return_value = {
            "data": [{"id": "record1", "properties": {}}],
            "totalSize": 1
        }

        result = enrichment_manager._query_single_day("2025-01-15")
        assert len(result) == 1
        assert result[0]["id"] == "record1"

        # Test no records found (should still succeed)
        enrichment_manager.collection_manager.query_records.return_value = {
            "data": [],
            "totalSize": 0
        }
        result = enrichment_manager._query_single_day("2025-01-15")
        assert len(result) == 0

        # Test API failure (should raise exception)
        enrichment_manager.collection_manager.query_records.side_effect = Exception("API Error")
        with pytest.raises(Exception, match="Query failed for day 2025-01-15"):
            enrichment_manager._query_single_day("2025-01-15")

    def test_query_cogfy_bulk_fail_fast(self, enrichment_manager):
        """Test _query_cogfy_bulk fail-fast behavior."""
        enrichment_manager._field_map = {"published_at": "pub_field_id"}

        # Mock first day success, second day failure
        def mock_query_records(*args, **kwargs):
            # First call succeeds, second call fails
            if not hasattr(mock_query_records, 'call_count'):
                mock_query_records.call_count = 0
            mock_query_records.call_count += 1

            if mock_query_records.call_count == 1:
                return {"data": [{"id": "record1"}], "totalSize": 1}
            else:
                raise Exception("API Error")

        enrichment_manager.collection_manager.query_records.side_effect = mock_query_records

        # Should fail on the second day
        with pytest.raises(Exception, match="Day-by-day query failed on day 2025-01-16"):
            enrichment_manager._query_cogfy_bulk("2025-01-15", "2025-01-16")

    def test_extract_unique_id_from_record(self, enrichment_manager):
        """Test _extract_unique_id_from_record method."""
        enrichment_manager._unique_id_field_id = 'field1'

        # Test successful extraction
        record = {
            "properties": {
                "field1": {
                    "text": {"value": "test_id"}
                }
            }
        }
        result = enrichment_manager._extract_unique_id_from_record(record)
        assert result == "test_id"

        # Test missing field
        record_no_field = {"properties": {}}
        result = enrichment_manager._extract_unique_id_from_record(record_no_field)
        assert result is None

        # Test empty value
        record_empty = {
            "properties": {
                "field1": {"text": {"value": ""}}
            }
        }
        result = enrichment_manager._extract_unique_id_from_record(record_empty)
        assert result is None

    def test_create_theme_mapping(self, enrichment_manager):
        """Test _create_theme_mapping method."""
        enrichment_manager._unique_id_field_id = 'field1'
        enrichment_manager._theme_field_id = 'theme_field'
        enrichment_manager._theme_options = [
            {'id': 'theme1', 'label': 'Education'}
        ]

        cogfy_records = [
            {
                "properties": {
                    "field1": {"text": {"value": "id1"}},
                    "theme_field": {"select": {"value": [{"id": "theme1"}]}}
                }
            },
            {
                "properties": {
                    "field1": {"text": {"value": "id2"}},
                    "theme_field": {"select": {"value": []}}
                }
            }
        ]

        mapping = enrichment_manager._create_theme_mapping(cogfy_records)
        assert len(mapping) == 1
        assert mapping["id1"] == "Education"

    def test_update_dataframe_with_themes(self, enrichment_manager):
        """Test _update_dataframe_with_themes method."""
        df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],
            'theme_1_level_1': [None, 'Existing', None]
        })

        theme_map = {'id1': 'Education', 'id3': 'Health'}

        # Test without force update
        successful, failed = enrichment_manager._update_dataframe_with_themes(df, theme_map, False)
        assert successful == 2  # id1 and id3 (id2 skipped due to existing theme)
        assert failed == 0
        assert df.iloc[0]['theme_1_level_1'] == 'Education'
        assert df.iloc[1]['theme_1_level_1'] == 'Existing'  # Unchanged
        assert df.iloc[2]['theme_1_level_1'] == 'Health'

        # Test with force update
        df2 = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],
            'theme_1_level_1': [None, None, None]  # All None for force update test
        })
        successful, failed = enrichment_manager._update_dataframe_with_themes(df2, theme_map, True)
        assert successful == 2  # Only id1 and id3 have themes in the map
        assert failed == 1  # id2 not in theme map

    def test_load_dataset_from_huggingface(self, enrichment_manager):
        """Test _load_dataset_from_huggingface method."""
        df = enrichment_manager._load_dataset_from_huggingface()
        assert len(df) == 3
        assert list(df['unique_id']) == ['id1', 'id2', 'id3']

    def test_apply_date_filtering(self, enrichment_manager):
        """Test _apply_date_filtering method."""
        df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],
            'published_at': ['2025-09-11', '2025-09-12', '2025-09-13']
        })

        # Test with date range
        filtered_df = enrichment_manager._apply_date_filtering(df, "2025-09-12", "2025-09-12")
        assert len(filtered_df) == 1
        assert filtered_df.iloc[0]['unique_id'] == 'id2'

        # Test without dates
        no_filter_df = enrichment_manager._apply_date_filtering(df)
        assert len(no_filter_df) == 3

    def test_load_full_dataset(self, enrichment_manager):
        """Test _load_full_dataset method."""
        df = enrichment_manager._load_full_dataset()
        assert len(df) == 3

    def test_ensure_theme_column_exists(self, enrichment_manager):
        """Test _ensure_theme_column_exists method."""
        df = pd.DataFrame({'unique_id': ['id1', 'id2']})

        # Test adding column
        result = enrichment_manager._ensure_theme_column_exists(df)
        assert 'theme_1_level_1' in result.columns
        assert result['theme_1_level_1'].isna().all()

        # Test existing column
        df_with_theme = pd.DataFrame({
            'unique_id': ['id1', 'id2'],
            'theme_1_level_1': ['Education', 'Health']
        })
        result = enrichment_manager._ensure_theme_column_exists(df_with_theme)
        assert result.equals(df_with_theme)

    def test_apply_theme_updates_to_full_dataset(self, enrichment_manager):
        """Test _apply_theme_updates_to_full_dataset method."""
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],
            'theme_1_level_1': [None, None, None]
        })

        enriched_df = pd.DataFrame({
            'unique_id': ['id1', 'id3'],
            'theme_1_level_1': ['Education', 'Health']
        })

        updates_applied = enrichment_manager._apply_theme_updates_to_full_dataset(full_df, enriched_df)
        assert updates_applied == 2
        assert full_df.iloc[0]['theme_1_level_1'] == 'Education'
        assert full_df.iloc[1]['theme_1_level_1'] is None
        assert full_df.iloc[2]['theme_1_level_1'] == 'Health'


    def test_load_and_filter_dataset(self, enrichment_manager):
        """Test _load_and_filter_dataset method."""
        # Test without date filtering
        df = enrichment_manager._load_and_filter_dataset()
        assert len(df) == 3
        assert list(df['unique_id']) == ['id1', 'id2', 'id3']

        # Test with date filtering
        df_filtered = enrichment_manager._load_and_filter_dataset(
            start_date="2025-09-12",
            end_date="2025-09-12"
        )
        assert len(df_filtered) == 1
        assert df_filtered.iloc[0]['unique_id'] == 'id2'

    def test_prepare_dataset_for_enrichment(self, enrichment_manager):
        """Test _prepare_dataset_for_enrichment method."""
        df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3', None],
            'theme_1_level_1': [None, 'Education', None, None]
        })

        # Test without force update (only missing themes)
        result = enrichment_manager._prepare_dataset_for_enrichment(df, force_update=False)
        assert len(result) == 2  # id1 and id3 (id2 has theme, None is filtered out)
        assert list(result['unique_id']) == ['id1', 'id3']

        # Test with force update (all records with unique_id)
        result_force = enrichment_manager._prepare_dataset_for_enrichment(df, force_update=True)
        assert len(result_force) == 3  # All except None
        assert list(result_force['unique_id']) == ['id1', 'id2', 'id3']

    def test_process_bulk_cogfy_results(self, enrichment_manager):
        """Test _process_bulk_cogfy_results method."""
        enrichment_manager._unique_id_field_id = 'field1'
        enrichment_manager._theme_field_id = 'theme_field'
        enrichment_manager._theme_options = [
            {'id': 'theme1', 'label': 'Education'}
        ]

        df = pd.DataFrame({
            'unique_id': ['id1', 'id2'],
            'theme_1_level_1': [None, None]
        })

        cogfy_records = [
            {
                "properties": {
                    "field1": {"text": {"value": "id1"}},
                    "theme_field": {"select": {"value": [{"id": "theme1"}]}}
                }
            }
        ]

        successful, failed = enrichment_manager._process_bulk_cogfy_results(cogfy_records, df, False)
        assert successful == 1
        assert failed == 1
        assert df.iloc[0]['theme_1_level_1'] == 'Education'
        assert pd.isna(df.iloc[1]['theme_1_level_1'])

    def test_merge_with_full_dataset(self, enrichment_manager):
        """Test _merge_with_full_dataset method."""
        # Test with date filtering (should merge with full dataset)
        enriched_df = pd.DataFrame({
            'unique_id': ['id2'],
            'theme_1_level_1': ['Health']
        })

        # Mock the full dataset load
        full_dataset_mock = Mock()
        full_df = pd.DataFrame({
            'unique_id': ['id1', 'id2', 'id3'],
            'theme_1_level_1': [None, None, None]
        })
        full_dataset_mock.to_pandas.return_value = full_df
        enrichment_manager.dataset_manager._load_existing_dataset.return_value = full_dataset_mock

        # Since we're mocking the enrichment_manager method, let's test the outcome indirectly
        result = enrichment_manager._merge_with_full_dataset(
            enriched_df,
            start_date="2025-09-12"
        )

        # The method should be called and return the full dataset
        enrichment_manager.dataset_manager._load_existing_dataset.assert_called_once()
        assert len(result) == 3  # Should return full dataset size

        # Test without date filtering (should return input df)
        result_no_filter = enrichment_manager._merge_with_full_dataset(enriched_df)
        assert result_no_filter.equals(enriched_df)

    def test_upload_enriched_dataset(self, enrichment_manager):
        """Test _upload_enriched_dataset method."""
        df = pd.DataFrame({'col1': [1, 2], 'col2': ['a', 'b']})

        with patch('datasets.Dataset') as mock_dataset_class:
            mock_dataset = Mock()
            mock_dataset_class.from_pandas.return_value = mock_dataset

            enrichment_manager._upload_enriched_dataset(df)

            mock_dataset_class.from_pandas.assert_called_once_with(df, preserve_index=False)
            enrichment_manager.dataset_manager._push_dataset_and_csvs.assert_called_once_with(mock_dataset)

    def test_enrich_dataset_with_themes_no_records(self, enrichment_manager):
        """Test enrich_dataset_with_themes with no records to process."""
        # Mock empty dataset
        empty_df = pd.DataFrame({'unique_id': [], 'theme_1_level_1': []})

        with patch.object(enrichment_manager, '_load_and_filter_dataset', return_value=empty_df):
            with patch.object(enrichment_manager, '_setup_cogfy_mappings'):
                enrichment_manager.enrich_dataset_with_themes()

                # Should return early without processing
                enrichment_manager.dataset_manager._push_dataset_and_csvs.assert_not_called()

    def test_enrich_dataset_with_themes_full_flow(self, enrichment_manager):
        """Test the complete enrich_dataset_with_themes flow."""
        # Mock all the private methods
        mock_df = pd.DataFrame({
            'unique_id': ['id1', 'id2'],
            'theme_1_level_1': [None, None]
        })

        with patch.object(enrichment_manager, '_setup_cogfy_mappings'):
            with patch.object(enrichment_manager, '_load_and_filter_dataset', return_value=mock_df):
                with patch.object(enrichment_manager, '_prepare_dataset_for_enrichment', return_value=mock_df):
                    with patch.object(enrichment_manager, '_query_cogfy_bulk', return_value=[{"id": "test", "properties": {}}]):
                        with patch.object(enrichment_manager, '_process_bulk_cogfy_results', return_value=(2, 0)):
                            with patch.object(enrichment_manager, '_report_enrichment_statistics'):
                                with patch.object(enrichment_manager, '_merge_with_full_dataset', return_value=mock_df):
                                    with patch.object(enrichment_manager, '_upload_enriched_dataset'):

                                        enrichment_manager.enrich_dataset_with_themes(
                                            start_date="2025-09-11",
                                            end_date="2025-09-12",
                                            force_update=True
                                        )

                                        # Verify all methods were called
                                        enrichment_manager._setup_cogfy_mappings.assert_called_once()
                                        enrichment_manager._load_and_filter_dataset.assert_called_once_with("2025-09-11", "2025-09-12")
                                        enrichment_manager._prepare_dataset_for_enrichment.assert_called_once_with(mock_df, True)
                                        enrichment_manager._query_cogfy_bulk.assert_called_once_with("2025-09-11", "2025-09-12")
                                        enrichment_manager._process_bulk_cogfy_results.assert_called_once()
                                        enrichment_manager._report_enrichment_statistics.assert_called_once()
                                        enrichment_manager._merge_with_full_dataset.assert_called_once()
                                        enrichment_manager._upload_enriched_dataset.assert_called_once()
