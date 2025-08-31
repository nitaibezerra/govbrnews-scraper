import pytest
import datetime
from unittest.mock import Mock, MagicMock, patch
from collections import defaultdict

# Import the module to test
import sys
import os

# Add src to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from news_grouper import NewsGrouper


class TestNewsGrouper:
    """Test suite for NewsGrouper class."""

    @pytest.fixture
    def news_grouper(self):
        """Create a NewsGrouper instance for testing."""
        return NewsGrouper("test_api_key", "https://test.api.com")

    @pytest.fixture
    def mock_field(self):
        """Create a mock field object."""
        field = Mock()
        field.name = "test_field"
        field.id = "field_123"
        field.type = "text"
        return field

    @pytest.fixture
    def mock_theme_field(self):
        """Create a mock theme field object."""
        field = Mock()
        field.name = "theme_1_level_1"
        field.id = "theme_field_123"
        field.type = "select"
        field.data = {
            "select": {
                "options": [
                    {"id": "theme_1", "label": "Meio Ambiente"},
                    {"id": "theme_2", "label": "Economia"},
                    {"id": "theme_3", "label": "Saúde"}
                ]
            }
        }
        return field

    @pytest.fixture
    def sample_raw_records(self):
        """Sample raw records from Cogfy API."""
        return [
            {
                "id": "record_1",
                "properties": {
                    "agency_field": {"text": {"value": "Ministério do Meio Ambiente"}},
                    "title_field": {"text": {"value": "Operação no Pantanal"}},
                    "category_field": {"text": {"value": "Meio Ambiente"}},
                    "content_field": {"text": {"value": "Conteúdo da notícia..."}},
                    "theme_field": {"select": {"value": [{"id": "theme_1"}]}}
                }
            },
            {
                "id": "record_2",
                "properties": {
                    "agency_field": {"text": {"value": "Ministério da Economia"}},
                    "title_field": {"text": {"value": "Nova política econômica"}},
                    "category_field": {"text": {"value": "Economia"}},
                    "content_field": {"text": {"value": "Conteúdo econômico..."}},
                    "theme_field": {"select": {"value": [{"id": "theme_2"}]}}
                }
            }
        ]

    @pytest.fixture
    def sample_parsed_records(self):
        """Sample parsed records."""
        return [
            {
                "id": "record_1",
                "agency": "Ministério do Meio Ambiente",
                "title": "Operação no Pantanal",
                "category": "Meio Ambiente",
                "content": "Conteúdo da notícia...",
                "theme_1_level_1": "Meio Ambiente"
            },
            {
                "id": "record_2",
                "agency": "Ministério da Economia",
                "title": "Nova política econômica",
                "category": "Economia",
                "content": "Conteúdo econômico...",
                "theme_1_level_1": "Economia"
            }
        ]

    def test_initialization(self, news_grouper):
        """Test NewsGrouper initialization."""
        assert news_grouper.client is not None
        assert news_grouper._source_manager is None
        assert news_grouper._target_manager is None
        assert news_grouper._source_field_map is None
        assert news_grouper._target_field_map is None

    @patch('news_grouper.CollectionManager')
    @patch('news_grouper.CogfyClient')
    def test_setup_collections(self, mock_cogfy_client, mock_collection_manager, news_grouper):
        """Test setup_collections method."""
        # Mock field objects
        mock_source_field = Mock()
        mock_source_field.name = "test_field"
        mock_source_field.id = "field_123"

        mock_target_field = Mock()
        mock_target_field.name = "target_field"
        mock_target_field.id = "target_field_123"

        # Mock collection managers
        mock_source_manager = Mock()
        mock_source_manager.list_columns.return_value = [mock_source_field]

        mock_target_manager = Mock()
        mock_target_manager.list_columns.return_value = [mock_target_field]

        mock_collection_manager.side_effect = [mock_source_manager, mock_target_manager]

        # Call method
        news_grouper.setup_collections("source_collection", "target_collection")

        # Assertions
        assert news_grouper._source_manager == mock_source_manager
        assert news_grouper._target_manager == mock_target_manager
        assert news_grouper._source_field_map == {"test_field": "field_123"}
        assert news_grouper._target_field_map == {"target_field": "target_field_123"}

    def test_validate_source_setup_success(self, news_grouper):
        """Test _validate_source_setup when setup is correct."""
        news_grouper._source_field_map = {"test": "field_123"}

        # Should not raise exception
        news_grouper._validate_source_setup()

    def test_validate_source_setup_failure(self, news_grouper):
        """Test _validate_source_setup when setup is missing."""
        news_grouper._source_field_map = None

        with pytest.raises(ValueError, match="Source collection not setup"):
            news_grouper._validate_source_setup()

    def test_get_required_field_ids_success(self, news_grouper):
        """Test _get_required_field_ids with all required fields present."""
        news_grouper._source_field_map = {
            "agency": "agency_field",
            "title": "title_field",
            "category": "category_field",
            "content": "content_field",
            "theme_1_level_1": "theme_field"
        }

        result = news_grouper._get_required_field_ids()

        expected = {
            "agency": "agency_field",
            "title": "title_field",
            "category": "category_field",
            "content": "content_field",
            "theme_1_level_1": "theme_field"
        }
        assert result == expected

    def test_get_required_field_ids_missing_field(self, news_grouper):
        """Test _get_required_field_ids when a required field is missing."""
        news_grouper._source_field_map = {
            "agency": "agency_field",
            "title": "title_field"
            # Missing: category, content, theme_1_level_1
        }

        with pytest.raises(ValueError, match="Field 'category' not found"):
            news_grouper._get_required_field_ids()

    def test_get_theme_options(self, news_grouper, mock_theme_field):
        """Test _get_theme_options method."""
        news_grouper._source_manager = Mock()
        news_grouper._source_manager.list_columns.return_value = [mock_theme_field]

        result = news_grouper._get_theme_options()

        expected = [
            {"id": "theme_1", "label": "Meio Ambiente"},
            {"id": "theme_2", "label": "Economia"},
            {"id": "theme_3", "label": "Saúde"}
        ]
        assert result == expected

    def test_extract_theme_id_with_value(self, news_grouper):
        """Test _extract_theme_id when theme value is present."""
        record = {
            "properties": {
                "theme_field": {
                    "select": {
                        "value": [{"id": "theme_123"}]
                    }
                }
            }
        }

        result = news_grouper._extract_theme_id(record, "theme_field")
        assert result == "theme_123"

    def test_extract_theme_id_no_value(self, news_grouper):
        """Test _extract_theme_id when theme value is empty."""
        record = {
            "properties": {
                "theme_field": {
                    "select": {
                        "value": []
                    }
                }
            }
        }

        result = news_grouper._extract_theme_id(record, "theme_field")
        assert result is None

    def test_extract_theme_id_missing_field(self, news_grouper):
        """Test _extract_theme_id when theme field is missing."""
        record = {"properties": {}}

        result = news_grouper._extract_theme_id(record, "theme_field")
        assert result is None

    def test_extract_theme_label_found(self, news_grouper):
        """Test _extract_theme_label when theme ID is found."""
        theme_options = [
            {"id": "theme_1", "label": "Meio Ambiente"},
            {"id": "theme_2", "label": "Economia"}
        ]

        result = news_grouper._extract_theme_label("theme_1", theme_options)
        assert result == "Meio Ambiente"

    def test_extract_theme_label_not_found(self, news_grouper):
        """Test _extract_theme_label when theme ID is not found."""
        theme_options = [
            {"id": "theme_1", "label": "Meio Ambiente"},
            {"id": "theme_2", "label": "Economia"}
        ]

        result = news_grouper._extract_theme_label("theme_999", theme_options)
        assert result is None

    def test_extract_theme_label_none_id(self, news_grouper):
        """Test _extract_theme_label when theme ID is None."""
        theme_options = [{"id": "theme_1", "label": "Meio Ambiente"}]

        result = news_grouper._extract_theme_label(None, theme_options)
        assert result is None

    def test_parse_single_record_success(self, news_grouper):
        """Test _parse_single_record with valid data."""
        record = {
            "id": "record_1",
            "properties": {
                "agency_field": {"text": {"value": "Ministério Test"}},
                "title_field": {"text": {"value": "Título Test"}},
                "category_field": {"text": {"value": "Categoria Test"}},
                "content_field": {"text": {"value": "Conteúdo Test"}},
                "theme_field": {"select": {"value": [{"id": "theme_1"}]}}
            }
        }

        field_ids = {
            "agency": "agency_field",
            "title": "title_field",
            "category": "category_field",
            "content": "content_field",
            "theme_1_level_1": "theme_field"
        }

        theme_options = [{"id": "theme_1", "label": "Test Theme"}]

        result = news_grouper._parse_single_record(record, field_ids, theme_options)

        expected = {
            "id": "record_1",
            "agency": "Ministério Test",
            "title": "Título Test",
            "category": "Categoria Test",
            "content": "Conteúdo Test",
            "theme_1_level_1": "Test Theme"
        }

        assert result == expected

    def test_group_by_theme(self, news_grouper, sample_parsed_records):
        """Test group_by_theme method."""
        result = news_grouper.group_by_theme(sample_parsed_records)

        expected = {
            "Meio Ambiente": [sample_parsed_records[0]],
            "Economia": [sample_parsed_records[1]]
        }

        assert result == expected
        assert isinstance(result, dict)
        assert len(result) == 2

    def test_group_by_theme_empty_list(self, news_grouper):
        """Test group_by_theme with empty list."""
        result = news_grouper.group_by_theme([])
        assert result == {}

    @patch('news_grouper.pd')
    @patch('news_grouper.datetime')
    def test_get_news_by_date_range(self, mock_datetime, mock_pd, news_grouper):
        """Test get_news_by_date_range method."""
        # Setup mocks
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        mock_datetime.timedelta = datetime.timedelta
        mock_datetime.timezone = datetime.timezone
        mock_pd.to_datetime.return_value = Mock()
        mock_pd.to_datetime.return_value.tz_localize.return_value = datetime.datetime(2024, 1, 14, 0, 0, 0, tzinfo=datetime.timezone.utc)

        news_grouper._source_manager = Mock()
        news_grouper._source_field_map = {"published_at": "published_field_123"}

        mock_result = {"data": [{"id": "record_1"}, {"id": "record_2"}]}
        news_grouper._source_manager.query_records.return_value = mock_result

        result = news_grouper.get_news_by_date_range(start_date="2024-01-14", end_date="2024-01-15")

        assert result == [{"id": "record_1"}, {"id": "record_2"}]
        news_grouper._source_manager.query_records.assert_called_once()

    def test_get_news_by_date_range_no_setup(self, news_grouper):
        """Test get_news_by_date_range when collections are not setup."""
        with pytest.raises(ValueError, match="Collections not setup"):
            news_grouper.get_news_by_date_range()

    def test_get_news_by_date_range_missing_field(self, news_grouper):
        """Test get_news_by_date_range when published_at field is missing."""
        news_grouper._source_manager = Mock()
        news_grouper._source_field_map = {"other_field": "field_123"}  # Setup field map but missing published_at

        with pytest.raises(ValueError, match="Field 'published_at' not found"):
            news_grouper.get_news_by_date_range()

    def test_insert_grouped_records(self, news_grouper):
        """Test insert_grouped_records method."""
        news_grouper._target_manager = Mock()
        news_grouper._target_field_map = {"news_by_theme_1_level_1": "field_123"}

        grouped_records = {
            "Meio Ambiente": [{"id": "record_1", "title": "News 1"}],
            "Economia": [{"id": "record_2", "title": "News 2"}]
        }

        result = news_grouper.insert_grouped_records(grouped_records)

        assert result == 2
        assert news_grouper._target_manager.create_record.call_count == 2

    def test_insert_grouped_records_no_setup(self, news_grouper):
        """Test insert_grouped_records when target collection is not setup."""
        with pytest.raises(ValueError, match="Target collection not setup"):
            news_grouper.insert_grouped_records({})

    def test_insert_grouped_records_missing_field(self, news_grouper):
        """Test insert_grouped_records when required field is missing."""
        news_grouper._target_manager = Mock()
        news_grouper._target_field_map = {"other_field": "field_123"}  # Setup field map but missing required field

        with pytest.raises(ValueError, match="Field 'news_by_theme_1_level_1' not found"):
            news_grouper.insert_grouped_records({})

    @patch.object(NewsGrouper, 'insert_grouped_records')
    @patch.object(NewsGrouper, 'group_by_theme')
    @patch.object(NewsGrouper, 'parse_news_records')
    @patch.object(NewsGrouper, 'get_news_by_date_range')
    @patch.object(NewsGrouper, 'setup_collections')
    def test_process_news_grouping(self, mock_setup, mock_get_news, mock_parse,
                                 mock_group, mock_insert, news_grouper):
        """Test complete process_news_grouping workflow."""
        # Setup mock returns
        mock_get_news.return_value = [{"raw": "record"}]
        mock_parse.return_value = [{"parsed": "record"}]
        mock_group.return_value = {"theme": [{"grouped": "record"}]}
        mock_insert.return_value = 5

        result = news_grouper.process_news_grouping(start_date="2024-01-14", end_date="2024-01-15")

        # Verify all methods were called
        mock_setup.assert_called_once_with("noticiasgovbr-all-news", "noticiasgovbr-by-theme_1_level_1")
        mock_get_news.assert_called_once_with("2024-01-14", "2024-01-15")
        mock_parse.assert_called_once_with([{"raw": "record"}])
        mock_group.assert_called_once_with([{"parsed": "record"}])
        mock_insert.assert_called_once_with({"theme": [{"grouped": "record"}]})

        assert result == 5

    def test_parse_news_records_integration(self, news_grouper, mock_theme_field):
        """Integration test for parse_news_records with all private methods."""
        # Setup
        news_grouper._source_field_map = {
            "agency": "agency_field",
            "title": "title_field",
            "category": "category_field",
            "content": "content_field",
            "theme_1_level_1": "theme_field"
        }

        news_grouper._source_manager = Mock()
        news_grouper._source_manager.list_columns.return_value = [mock_theme_field]

        raw_records = [
            {
                "id": "record_1",
                "properties": {
                    "agency_field": {"text": {"value": "Ministério Test"}},
                    "title_field": {"text": {"value": "Título Test"}},
                    "category_field": {"text": {"value": "Categoria Test"}},
                    "content_field": {"text": {"value": "Conteúdo Test"}},
                    "theme_field": {"select": {"value": [{"id": "theme_1"}]}}
                }
            }
        ]

        result = news_grouper.parse_news_records(raw_records)

        assert len(result) == 1
        assert result[0]["id"] == "record_1"
        assert result[0]["agency"] == "Ministério Test"
        assert result[0]["theme_1_level_1"] == "Meio Ambiente"

    def test_parse_news_records_skip_invalid(self, news_grouper, mock_theme_field, capsys):
        """Test parse_news_records skips invalid records and prints warnings."""
        # Setup
        news_grouper._source_field_map = {
            "agency": "agency_field",
            "title": "title_field",
            "category": "category_field",
            "content": "content_field",
            "theme_1_level_1": "theme_field"
        }

        news_grouper._source_manager = Mock()
        news_grouper._source_manager.list_columns.return_value = [mock_theme_field]

        raw_records = [
            {
                "id": "invalid_record",
                "properties": {
                    "agency_field": {"text": {"value": "Ministério Test"}},
                    # Missing other required fields to trigger error
                }
            }
        ]

        result = news_grouper.parse_news_records(raw_records)

        # Should return empty list since record was skipped
        assert len(result) == 0

        # Check that warning was printed
        captured = capsys.readouterr()
        assert "Warning: Skipping record invalid_record" in captured.out
