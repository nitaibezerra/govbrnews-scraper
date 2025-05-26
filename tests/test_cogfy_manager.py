import os
import pytest
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, date, time
from src.cogfy_manager import CogfyClient, CollectionManager, Field

@pytest.fixture
def api_key():
    """Fixture to load API key from .env file."""
    root_dir = Path(__file__).parent.parent
    load_dotenv(root_dir / ".env")

    api_key = os.getenv("COGFY_API_KEY")
    if not api_key:
        pytest.skip("COGFY_API_KEY environment variable is not set")
    return api_key

@pytest.fixture
def client(api_key):
    """Fixture to create a CogfyClient instance."""
    return CogfyClient(api_key, base_url="https://public-api.serpro.cogfy.com/")

def test_collection_manager_by_name(client):
    """Test CollectionManager initialization with a collection name."""
    collection_name = "_collection-for-test-purpose-only"
    manager = CollectionManager(client, collection_name)

    assert manager.name == collection_name
    assert manager.id is not None
    assert len(manager.id) == 36  # UUID length
    assert manager.id.count('-') == 4  # UUID format

def test_collection_manager_by_id(client):
    """Test CollectionManager initialization with a collection ID."""
    collection_id = "19c6ec3a-354e-4164-9a69-30040fd81c5b"
    manager = CollectionManager(client, collection_id)

    assert manager.id == collection_id
    assert manager.name is not None
    assert len(manager.name) > 0

def test_collection_manager_invalid_name(client):
    """Test CollectionManager initialization with an invalid collection name."""
    with pytest.raises(ValueError, match="Collection not found"):
        CollectionManager(client, "invalid-collection-name")

def test_collection_manager_invalid_id(client):
    """Test CollectionManager initialization with an invalid collection ID."""
    with pytest.raises(ValueError, match="Collection not found with ID"):
        CollectionManager(client, "00000000-0000-0000-0000-000000000000")

def test_cogfy_client_list_collections(client):
    """Test listing collections from the Cogfy server."""
    result = client.list_collections(page_size=100)

    assert "data" in result
    assert "totalSize" in result
    assert "pageNumber" in result
    assert "pageSize" in result
    assert isinstance(result["data"], list)
    assert len(result["data"]) > 0

def test_cogfy_client_find_collection(client):
    """Test finding a collection by ID."""
    # First get a valid collection ID
    result = client.list_collections(page_size=1)
    collection_id = result["data"][0]["id"]

    # Test finding the collection
    collection = client.find_collection(collection_id)
    assert collection is not None
    assert collection.id == collection_id
    assert collection.name is not None

def test_cogfy_client_find_invalid_collection(client):
    """Test finding a non-existent collection."""
    collection = client.find_collection("00000000-0000-0000-0000-000000000000")
    assert collection is None

def test_collection_manager_list_columns(client):
    """Test listing columns (fields) of a collection."""
    collection_name = "_collection-for-test-purpose-only"
    manager = CollectionManager(client, collection_name)

    fields = manager.list_columns()

    # Check that we got the expected number of fields
    assert len(fields) == 8

    # Check that all fields are Field objects
    assert all(isinstance(field, Field) for field in fields)

    # Check that we have all the expected fields
    field_names = {field.name for field in fields}
    expected_fields = {
        "text_field_01",
        "text_field_02",
        "number_field_01",
        "boolean_field_01"
    }
    assert field_names.issuperset(expected_fields)

    # Check field types
    field_types = {field.name: field.type for field in fields}
    assert field_types["text_field_01"] == "text"
    assert field_types["text_field_02"] == "text"
    assert field_types["number_field_01"] == "number"
    assert field_types["boolean_field_01"] == "boolean"

def test_collection_manager_ensure_fields(client):
    """Test ensuring additional fields exist in the collection."""
    collection_name = "_collection-for-test-purpose-only"
    manager = CollectionManager(client, collection_name)

    # Define new fields to ensure
    new_fields = {
        "text_field_03": "text",
        "number_field_02": "number",
        "boolean_field_02": "boolean",
        "date_field_01": "date"
    }

    # Ensure the fields exist
    fields = manager.ensure_fields(new_fields)

    # Check that we have all fields (original + new)
    field_names = {field.name for field in fields}
    expected_fields = {
        # Original fields
        "text_field_01",
        "text_field_02",
        "number_field_01",
        "boolean_field_01",
        # New fields
        "text_field_03",
        "number_field_02",
        "boolean_field_02",
        "date_field_01"
    }
    assert field_names == expected_fields

    # Check field types
    field_types = {field.name: field.type for field in fields}
    assert field_types["text_field_03"] == "text"
    assert field_types["number_field_02"] == "number"
    assert field_types["boolean_field_02"] == "boolean"
    assert field_types["date_field_01"] == "date"

def test_create_record_single_field(client):
    """Test creating a record with a single text field."""
    collection_name = "_collection-for-test-purpose-only"
    manager = CollectionManager(client, collection_name)

    # Get the text field
    fields = manager.list_columns()
    text_field = next(field for field in fields if field.name == "text_field_01")

    # Create a record with a single text field
    properties = {
        text_field.id: {
            "type": "text",
            "text": {"value": "Test text 1"}
        }
    }

    # Create the record
    record_id = manager.create_record(properties)

    # Verify the record was created successfully
    assert record_id is not None
    assert isinstance(record_id, str)
    assert len(record_id) > 0

def test_create_record_all_fields(client):
    """Test creating a record with all field types."""
    collection_name = "_collection-for-test-purpose-only"
    manager = CollectionManager(client, collection_name)

    # Get all fields
    fields = manager.list_columns()
    field_map = {field.name: field for field in fields}

    # Get current datetime in format YYYY-MM-DDTHH:MM:SSZ
    current_datetime = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create a record with all fields
    properties = {
        field_map["text_field_01"].id: {
            "type": "text",
            "text": {"value": "Test text 1"}
        },
        field_map["text_field_02"].id: {
            "type": "text",
            "text": {"value": "Test text 2"}
        },
        field_map["text_field_03"].id: {
            "type": "text",
            "text": {"value": "Test text 3"}
        },
        field_map["number_field_01"].id: {
            "type": "number",
            "number": {"value": 42}
        },
        field_map["number_field_02"].id: {
            "type": "number",
            "number": {"value": 3.14}
        },
        field_map["boolean_field_01"].id: {
            "type": "boolean",
            "boolean": {"value": True}
        },
        field_map["boolean_field_02"].id: {
            "type": "boolean",
            "boolean": {"value": False}
        },
        field_map["date_field_01"].id: {
            "type": "date",
            'date': {'value': current_datetime}
        }
    }

    # Create the record
    record_id = manager.create_record(properties)

    # Verify the record was created successfully
    assert record_id is not None
    assert isinstance(record_id, str)
    assert len(record_id) > 0

    # Test querying the created record
    filter_criteria = {
        "type": "and",
        "and": {
            "filters": [
                {
                    "type": "equals",
                    "equals": {
                        "fieldId": field_map["text_field_01"].id,
                        "value": "Test text 1"
                    }
                }
            ]
        }
    }

    result = manager.query_records(filter=filter_criteria)
    assert result["totalSize"] > 0
    assert len(result["data"]) > 0

    # Verify the date field format
    record = result["data"][0]
    date_field_value = record["properties"][field_map["date_field_01"].id]["date"]["value"]
    assert date_field_value == current_datetime

def test_query_records(client):
    """Test querying records from the test collection."""
    collection_name = "_collection-for-test-purpose-only"
    manager = CollectionManager(client, collection_name)

    # Query all records
    result = manager.query_records()

    # Verify the response structure

    assert "data" in result
    assert "totalSize" in result
    assert isinstance(result["data"], list)

    # Verify we have at least one record
    assert result["totalSize"] > 0
    assert len(result["data"]) > 0

    # Test filtering by text field
    text_field = next(field for field in manager.list_columns() if field.name == "text_field_01")
    filter_criteria = {
        "type": "and",
        "and": {
            "filters": [
                {
                    "type": "equals",
                    "equals": {
                        "fieldId": text_field.id,
                        "value": "Test text 1"
                    }
                }
            ]
        }
    }

    filtered_result = manager.query_records(filter=filter_criteria)
    assert filtered_result["totalSize"] > 0
    assert len(filtered_result["data"]) > 0

    # Test ordering by text field
    order_criteria = [
        {
            "fieldId": text_field.id,
            "direction": "asc"
        }
    ]

    ordered_result = manager.query_records(order_by=order_criteria)
    assert ordered_result["totalSize"] > 0
    assert len(ordered_result["data"]) > 0
