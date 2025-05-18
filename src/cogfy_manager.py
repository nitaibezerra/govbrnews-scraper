import requests
from typing import Dict, Optional, List, Set, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin

@dataclass
class Collection:
    id: str
    name: str

@dataclass
class Field:
    id: str
    name: str
    type: str
    operation: Optional[str]

class CogfyClient:
    def __init__(self, api_key: str, base_url: str):
        """Initialize the Cogfy client with an API key.

        Args:
            api_key (str): Your Cogfy API key
            base_url (str): The base URL for the Cogfy API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Api-Key": api_key
        }

    def list_collections(self, page_number: int = 0, page_size: int = 10) -> Dict:
        """List collections from the Cogfy server.

        Args:
            page_number (int): The page number to retrieve (starts at 0)
            page_size (int): Number of results per page

        Returns:
            Dict: Response containing collections data and pagination info
        """
        url = urljoin(f"{self.base_url}/", "collections")
        params = {
            "pageNumber": page_number,
            "pageSize": page_size
        }

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes

        return response.json()

    def find_collection(self, collection_id: str) -> Optional[Collection]:
        """Find a collection by its ID.

        Args:
            collection_id (str): The ID of the collection to find

        Returns:
            Optional[Collection]: The collection if found, None otherwise
        """
        url = urljoin(f"{self.base_url}/", f"collections/{collection_id}")

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return Collection(id=data["id"], name=data["name"])
        except requests.exceptions.RequestException:
            return None

    def get_collection_id(self, collection_name: str) -> Optional[str]:
        """Find a collection ID by its name.

        Args:
            collection_name (str): The name of the collection to find

        Returns:
            Optional[str]: The collection ID if found, None otherwise
        """
        page_number = 0
        page_size = 100  # Use a larger page size to reduce number of requests

        while True:
            result = self.list_collections(page_number=page_number, page_size=page_size)

            # Search in current page
            for collection in result["data"]:
                if collection["name"] == collection_name:
                    return collection["id"]

            # Check if we've reached the last page
            if (page_number + 1) * page_size >= result["totalSize"]:
                break

            page_number += 1

        return None

    def list_fields(self, collection_id: str) -> List[Field]:
        """List all fields in a collection.

        Args:
            collection_id (str): The ID of the collection to list fields from

        Returns:
            List[Field]: List of fields in the collection
        """
        url = urljoin(f"{self.base_url}/", f"collections/{collection_id}/fields")

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        data = response.json()
        return [Field(**field) for field in data["data"]]

    def create_field(self, collection_id: str, name: str, field_type: str) -> Field:
        """Create a new field in a collection.

        Args:
            collection_id (str): The ID of the collection to add the field to
            name (str): The name of the new field
            field_type (str): The type of the new field (e.g., "text", "number", "boolean")

        Returns:
            Field: The created field

        Raises:
            requests.exceptions.RequestException: If the API request fails
        """
        url = urljoin(f"{self.base_url}/", f"collections/{collection_id}/fields")
        payload = {
            "name": name,
            "type": field_type
        }

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        # The POST API only returns the field ID
        field_id = response.json()

        # Fetch the complete field details
        fields = self.list_fields(collection_id)
        for field in fields:
            if field.id == field_id:
                return field

        raise ValueError(f"Created field {field_id} not found in collection {collection_id}")

class CollectionManager:
    def __init__(self, client: CogfyClient, collection_identifier: str):
        """Initialize the CollectionManager with a collection name or ID.

        Args:
            client (CogfyClient): An initialized CogfyClient instance
            collection_identifier (str): Either the collection name or ID
        """
        self.client = client
        self.collection_id = None
        self.collection_name = None

        # Check if the identifier looks like a UUID (collection ID)
        if len(collection_identifier) == 36 and collection_identifier.count('-') == 4:
            # Try to find the collection by ID
            collection = client.find_collection(collection_identifier)
            if collection:
                self.collection_id = collection.id
                self.collection_name = collection.name
            else:
                raise ValueError(f"Collection not found with ID: {collection_identifier}")
        else:
            # Assume it's a collection name
            self.collection_name = collection_identifier
            self.collection_id = client.get_collection_id(collection_identifier)

        if not self.collection_id:
            raise ValueError(f"Collection not found: {collection_identifier}")

    @property
    def id(self) -> str:
        """Get the collection ID.

        Returns:
            str: The collection ID
        """
        return self.collection_id

    @property
    def name(self) -> str:
        """Get the collection name.

        Returns:
            str: The collection name
        """
        return self.collection_name

    def list_columns(self) -> List[Field]:
        """List all fields (columns) in the collection.

        Returns:
            List[Field]: List of fields in the collection
        """
        return self.client.list_fields(self.collection_id)

    def ensure_fields(self, fields: Dict[str, str]) -> List[Field]:
        """Ensure that all specified fields exist in the collection, creating any that don't.

        Args:
            fields (Dict[str, str]): Dictionary mapping field names to their types

        Returns:
            List[Field]: List of all fields in the collection after ensuring the specified ones exist
        """
        # Get current fields
        current_fields = self.list_columns()
        current_field_names = {field.name for field in current_fields}

        # Create any missing fields
        for name, field_type in fields.items():
            if name not in current_field_names:
                self.client.create_field(self.collection_id, name, field_type)

        # Return updated list of fields
        return self.list_columns()