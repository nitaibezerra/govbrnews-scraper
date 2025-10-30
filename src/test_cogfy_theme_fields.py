#!/usr/bin/env python3
"""
Test script to validate Cogfy API response structure for theme fields.

This script helps understand how theme_1_level_1, theme_1_level_2, and theme_1_level_3
are structured in the Cogfy API to properly implement extraction logic.
"""

import os
import sys
import json
from dotenv import load_dotenv

# Add parent directory to path to import cogfy_manager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cogfy_manager import CogfyClient, CollectionManager


def analyze_field_structure(collection_manager):
    """Analyze structure of theme fields in Cogfy collection."""
    print("\n" + "="*60)
    print("ANALYZING FIELD STRUCTURES")
    print("="*60)

    fields = collection_manager.list_columns()

    theme_fields = ['theme_1_level_1', 'theme_1_level_2', 'theme_1_level_3']

    for field in fields:
        if field.name in theme_fields:
            print(f"\nField: {field.name}")
            print(f"  ID: {field.id}")
            print(f"  Type: {field.type}")

            if field.data:
                print(f"  Has data: Yes")
                if field.type == "select" and "select" in field.data:
                    options = field.data["select"].get("options", [])
                    print(f"  Options count: {len(options)}")
                    if options:
                        print(f"  Sample option: {json.dumps(options[0], ensure_ascii=False)}")
                else:
                    print(f"  Data keys: {list(field.data.keys())}")
            else:
                print(f"  Has data: No")


def query_and_analyze_records(collection_manager, target_date="2025-10-28"):
    """Query records and analyze theme field values."""
    print("\n" + "="*60)
    print(f"QUERYING RECORDS FOR DATE: {target_date}")
    print("="*60)

    # Get field map
    fields = collection_manager.list_columns()
    field_map = {f.name: f.id for f in fields}

    published_at_field_id = field_map.get("published_at")

    if not published_at_field_id:
        print("❌ published_at field not found!")
        return

    # Build filter for specific date
    filters = {
        "type": "and",
        "and": {
            "filters": [
                {
                    "type": "greaterThanOrEquals",
                    "greaterThanOrEquals": {
                        "fieldId": published_at_field_id,
                        "value": f"{target_date}T00:00:00"
                    }
                },
                {
                    "type": "lessThanOrEquals",
                    "lessThanOrEquals": {
                        "fieldId": published_at_field_id,
                        "value": f"{target_date}T23:59:59"
                    }
                }
            ]
        }
    }

    try:
        result = collection_manager.query_records(
            filter=filters,
            page_size=5  # Just get a few samples
        )
    except Exception as e:
        print(f"❌ Error querying records: {e}")
        return

    records = result.get("data", [])
    print(f"\nRetrieved {len(records)} sample records")

    if not records:
        print("⚠️  No records found for this date!")
        return

    # Analyze theme fields in each record
    theme_field_ids = {
        'theme_1_level_1': field_map.get('theme_1_level_1'),
        'theme_1_level_2': field_map.get('theme_1_level_2'),
        'theme_1_level_3': field_map.get('theme_1_level_3')
    }

    for idx, record in enumerate(records[:3], 1):  # Show first 3
        print(f"\n{'='*60}")
        print(f"RECORD {idx}")
        print('='*60)

        properties = record.get("properties", {})

        # Show unique_id for reference
        unique_id_field = field_map.get("unique_id")
        if unique_id_field and unique_id_field in properties:
            unique_id_prop = properties[unique_id_field]
            if unique_id_prop and "text" in unique_id_prop:
                unique_id = unique_id_prop["text"].get("value", "N/A")
                print(f"Unique ID: {unique_id}")

        for theme_name, field_id in theme_field_ids.items():
            print(f"\n{theme_name}:")
            print("-" * 40)

            if not field_id:
                print("  ❌ FIELD NOT FOUND IN COLLECTION")
                continue

            theme_prop = properties.get(field_id)

            if not theme_prop:
                print("  ℹ️  Value: None (field empty or not set)")
            else:
                print(f"  Structure keys: {list(theme_prop.keys())}")
                print(f"  Full raw value:")
                print(json.dumps(theme_prop, indent=4, ensure_ascii=False))


def main():
    load_dotenv()

    api_key = os.getenv("COGFY_API_KEY")
    if not api_key:
        print("❌ COGFY_API_KEY environment variable not set!")
        print("Please set it in your .env file or environment")
        return 1

    server_url = "https://api.cogfy.com/"
    collection_name = "noticiasgovbr-all-news"

    print("="*60)
    print("COGFY THEME FIELDS VALIDATION SCRIPT")
    print("="*60)
    print(f"\nConnecting to Cogfy...")
    print(f"  Server: {server_url}")
    print(f"  Collection: {collection_name}")

    try:
        client = CogfyClient(api_key, server_url)
        collection_manager = CollectionManager(client, collection_name)

        print("✅ Connected successfully!\n")

        # Run analysis
        analyze_field_structure(collection_manager)
        query_and_analyze_records(collection_manager, "2025-10-28")

        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        print("\nKey Questions to Answer:")
        print("1. Is theme_1_level_2 a 'select' type or 'text' type?")
        print("2. Is theme_1_level_3 a 'select' type or 'text' type?")
        print("3. Do level 2/3 need ID→label mapping like level 1?")
        print("4. Or do level 2/3 store the label directly?")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
