import os
import pytest
from pathlib import Path
from dotenv import load_dotenv
from src.cogfy_manager import CogfyClient, CollectionManager

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

@pytest.mark.skip(reason="find_collection API is currently broken")
def test_collection_manager_by_id(client):
    """Test CollectionManager initialization with a collection ID."""
    collection_id = "8af5bb9c-e79e-4607-ad81-3b2769910766"
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

@pytest.mark.skip(reason="find_collection API is currently broken")
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

@pytest.mark.skip(reason="find_collection API is currently broken")
def test_cogfy_client_find_invalid_collection(client):
    """Test finding a non-existent collection."""
    collection = client.find_collection("00000000-0000-0000-0000-000000000000")
    assert collection is None