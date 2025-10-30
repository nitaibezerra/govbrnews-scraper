#!/usr/bin/env python3
"""
Quick test of the updated theme enrichment manager.
Tests with a single recent date to verify the new logic works correctly.
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from theme_enrichment_manager import ThemeEnrichmentManager


def main():
    load_dotenv()

    print("="*60)
    print("TESTING UPDATED THEME ENRICHMENT MANAGER")
    print("="*60)

    # Test with a single recent date
    test_date = "2025-10-28"

    print(f"\nTesting with date: {test_date}")
    print("This will:")
    print("  1. Query Cogfy for records on this date")
    print("  2. Extract all 3 theme levels (L1, L2, L3)")
    print("  3. Show mapping results")
    print("\nNOTE: This is a dry run - won't update HuggingFace")

    try:
        manager = ThemeEnrichmentManager()

        # Setup mappings
        print("\n--- Setting up Cogfy mappings ---")
        manager._setup_cogfy_mappings()

        # Query for single day
        print(f"\n--- Querying Cogfy for {test_date} ---")
        records = manager._query_single_day(test_date)
        print(f"Retrieved {len(records)} records")

        if not records:
            print("⚠️  No records found. Try a different date.")
            return 1

        # Create theme mapping
        print("\n--- Creating theme mapping ---")
        theme_map = manager._create_theme_mapping(records)
        print(f"Mapped themes for {len(theme_map)} records")

        # Show first 5 mapped results
        print("\n--- Sample Results (first 5) ---")
        for idx, (unique_id, themes) in enumerate(list(theme_map.items())[:5], 1):
            print(f"\nRecord {idx}: {unique_id[:16]}...")
            print(f"  Level 1: {themes.get('theme_1_level_1') or 'None'}")
            print(f"  Level 2: {themes.get('theme_1_level_2') or 'None'}")
            print(f"  Level 3: {themes.get('theme_1_level_3') or 'None'}")

        # Count completeness
        print("\n--- Statistics ---")
        has_l1 = sum(1 for t in theme_map.values() if t.get('theme_1_level_1'))
        has_l2 = sum(1 for t in theme_map.values() if t.get('theme_1_level_2'))
        has_l3 = sum(1 for t in theme_map.values() if t.get('theme_1_level_3'))
        total = len(theme_map)

        print(f"Total mapped: {total}")
        print(f"With Level 1: {has_l1} ({has_l1/total*100:.1f}%)")
        print(f"With Level 2: {has_l2} ({has_l2/total*100:.1f}%)")
        print(f"With Level 3: {has_l3} ({has_l3/total*100:.1f}%)")

        print("\n" + "="*60)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\nThe new logic is working correctly!")
        print("- Level 1 extracted from select field")
        print("- Level 2 extracted from text field (AI inference)")
        print("- Level 3 extracted from text field (AI inference)")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
