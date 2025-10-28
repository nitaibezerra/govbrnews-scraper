import os
import sys
import time
import argparse
import datetime
from typing import List, Optional
from urllib.parse import urljoin

# Add parent directory to path to import cogfy_manager
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import pandas as pd
from dotenv import load_dotenv
from cogfy_manager import CogfyClient


class CalculateRecordsManager:
    """Manages batch calculation of fields across records in a Cogfy collection."""

    def __init__(self, api_key: str, base_url: str = "https://api.cogfy.com"):
        """Initialize the manager with Cogfy client.

        Args:
            api_key (str): Cogfy API key
            base_url (str): Base URL for Cogfy API
        """
        self.client = CogfyClient(api_key, base_url)
        self.base_url = base_url

    def discover_collection_id(self, collection_name: str) -> Optional[str]:
        """Discover collection ID from collection name.

        Args:
            collection_name (str): Name of the collection

        Returns:
            Optional[str]: Collection ID if found, None otherwise
        """
        print(f"Discovering collection ID for '{collection_name}'...")
        collection_id = self.client.get_collection_id(collection_name)

        if collection_id:
            print(f"Found collection ID: {collection_id}")
        else:
            print(f"Collection '{collection_name}' not found")

        return collection_id

    def discover_field_id(self, collection_id: str, field_name: str, verbose: bool = True) -> Optional[str]:
        """Discover field ID from field name in a collection.

        Args:
            collection_id (str): The collection ID
            field_name (str): Name of the field
            verbose (bool): Whether to print status messages

        Returns:
            Optional[str]: Field ID if found, None otherwise
        """
        if verbose:
            print(f"Discovering field ID for '{field_name}'...")

        fields = self.client.list_fields(collection_id)

        for field in fields:
            if field.name == field_name:
                if verbose:
                    print(f"Found field ID: {field.id}")
                return field.id

        if verbose:
            print(f"Field '{field_name}' not found in collection")
        return None

    def discover_multiple_field_ids(self, collection_id: str, field_names: List[str]) -> dict:
        """Discover field IDs for multiple field names.

        Args:
            collection_id (str): The collection ID
            field_names (List[str]): List of field names

        Returns:
            dict: Dictionary mapping field names to field IDs
        """
        print(f"Discovering field IDs for {len(field_names)} fields...")

        # Fetch fields once
        fields = self.client.list_fields(collection_id)
        field_map = {field.name: field.id for field in fields}

        result = {}
        for field_name in field_names:
            field_id = field_map.get(field_name)
            if field_id:
                print(f"  ✓ '{field_name}' -> {field_id}")
                result[field_name] = field_id
            else:
                print(f"  ✗ '{field_name}' not found")

        return result

    def generate_date_range(self, start_date: str, end_date: str) -> List[str]:
        """Generate a list of dates from start_date to end_date in descending order.

        Args:
            start_date (str): Start date (YYYY-MM-DD)
            end_date (str): End date (YYYY-MM-DD)

        Returns:
            List[str]: List of date strings in descending order
        """
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        date_range = pd.date_range(start=start, end=end, freq='D')
        # Convert to list of strings in descending order
        dates = [date.strftime('%Y-%m-%d') for date in reversed(date_range)]

        return dates

    def query_records_for_date_batch(
        self,
        collection_id: str,
        start_date: str,
        end_date: str,
        date_field_id: str,
        verbose: bool = True
    ) -> List[str]:
        """Query all record IDs for a date range batch.

        Args:
            collection_id (str): The collection ID
            start_date (str): Start date to query (YYYY-MM-DD)
            end_date (str): End date to query (YYYY-MM-DD)
            date_field_id (str): ID of the date field to filter on
            verbose (bool): Whether to print progress messages

        Returns:
            List[str]: List of record IDs for that date range
        """
        if verbose:
            if start_date == end_date:
                print(f"  Querying records for {start_date}...", end=" ")
            else:
                print(f"  Querying records from {start_date} to {end_date}...", end=" ")

        # Convert dates to ISO format with timezone
        # Start of first day
        start_datetime = pd.to_datetime(start_date).tz_localize(datetime.timezone.utc)
        # End of last day
        end_datetime = pd.to_datetime(end_date).tz_localize(datetime.timezone.utc) + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)

        start_date_iso = start_datetime.isoformat().replace("+00:00", "Z")
        end_date_iso = end_datetime.isoformat().replace("+00:00", "Z")

        # Build filter for date range
        filter_criteria = {
            "type": "and",
            "and": {
                "filters": [
                    {
                        "type": "greaterThanOrEquals",
                        "greaterThanOrEquals": {
                            "fieldId": date_field_id,
                            "value": start_date_iso
                        }
                    },
                    {
                        "type": "lessThanOrEquals",
                        "lessThanOrEquals": {
                            "fieldId": date_field_id,
                            "value": end_date_iso
                        }
                    }
                ]
            }
        }

        # Query records with pagination
        record_ids = []
        page_number = 0
        page_size = 500

        while True:
            result = self.client.query_records(
                collection_id,
                filter=filter_criteria,
                page_number=page_number,
                page_size=page_size
            )

            # Extract record IDs from current page
            for record in result.get("data", []):
                record_ids.append(record["id"])

            # Check if we've reached the last page
            total_size = result.get("totalSize", 0)
            if (page_number + 1) * page_size >= total_size:
                break

            page_number += 1
            # time.sleep(1)  # Sleep between pagination requests

        if verbose:
            print(f"found {len(record_ids)} records")

        return record_ids

    def calculate_records_in_batches(
        self,
        collection_id: str,
        field_id: str,
        field_name: str,
        record_ids: List[str],
        batch_size: int = 100,
        verbose: bool = True
    ) -> dict:
        """Calculate field values for records in batches.

        Args:
            collection_id (str): The collection ID
            field_id (str): The field ID to calculate
            field_name (str): The field name (for display purposes)
            record_ids (List[str]): List of record IDs to process
            batch_size (int): Number of records per batch
            verbose (bool): Whether to print detailed progress

        Returns:
            dict: Summary of the calculation results
        """
        total_records = len(record_ids)

        if total_records == 0:
            return {
                "field_name": field_name,
                "total_records": 0,
                "total_batches": 0,
                "successful_batches": 0,
                "failed_batches": 0
            }

        if verbose:
            print(f"    Calculating '{field_name}' for {total_records} records (batch size: {batch_size})...")

        # Split record IDs into batches
        batches = [record_ids[i:i + batch_size] for i in range(0, total_records, batch_size)]

        successful_batches = 0
        failed_batches = 0

        for batch_num, batch in enumerate(batches, 1):
            if verbose:
                print(f"      Batch {batch_num}/{len(batches)} ({len(batch)} records)...", end=" ")

            try:
                self._call_calculate_api(collection_id, field_id, batch)
                successful_batches += 1
                if verbose:
                    print("✓")
            except Exception as e:
                failed_batches += 1
                if verbose:
                    print(f"✗ Error: {e}")

            # Sleep between batches (except after the last batch)
            # if batch_num < len(batches):
            #     time.sleep(1)

        return {
            "field_name": field_name,
            "total_records": total_records,
            "total_batches": len(batches),
            "successful_batches": successful_batches,
            "failed_batches": failed_batches
        }

    def process_by_date_and_fields(
        self,
        collection_id: str,
        field_map: dict,
        start_date: str,
        end_date: str,
        date_field_name: str,
        batch_size: int = 100,
        days_per_batch: int = 5
    ) -> dict:
        """Process records in date batches (descending) and field by field.

        Args:
            collection_id (str): The collection ID
            field_map (dict): Dictionary mapping field names to field IDs
            start_date (str): Start date (YYYY-MM-DD)
            end_date (str): End date (YYYY-MM-DD)
            date_field_name (str): Name of the date field to filter on
            batch_size (int): Number of records per batch
            days_per_batch (int): Number of days to process per query batch

        Returns:
            dict: Overall summary of the processing
        """
        print(f"\n{'='*70}")
        print("Starting multi-field calculation process")
        print(f"Date range: {start_date} to {end_date} (processing in descending order)")
        print(f"Fields to calculate: {', '.join(field_map.keys())}")
        print(f"Record batch size: {batch_size}")
        print(f"Days per batch: {days_per_batch}")
        print(f"{'='*70}\n")

        # Get date field ID
        date_field_id = self.discover_field_id(collection_id, date_field_name, verbose=False)
        if not date_field_id:
            raise ValueError(f"Date field '{date_field_name}' not found in collection")

        # Generate date range (descending order)
        all_dates = self.generate_date_range(start_date, end_date)
        print(f"Processing {len(all_dates)} days in batches of {days_per_batch}...\n")

        # Split dates into batches
        date_batches = [all_dates[i:i + days_per_batch] for i in range(0, len(all_dates), days_per_batch)]

        overall_stats = {
            "total_days": len(all_dates),
            "total_fields": len(field_map),
            "date_batches_processed": 0,
            "date_batches_with_records": 0,
            "total_records_processed": 0,
            "field_results": {field_name: {"successful_batches": 0, "failed_batches": 0, "total_records": 0}
                             for field_name in field_map.keys()}
        }

        # Process each date batch
        for batch_num, date_batch in enumerate(date_batches, 1):
            batch_start = date_batch[0]  # Most recent date in batch (descending order)
            batch_end = date_batch[-1]   # Oldest date in batch

            if len(date_batch) == 1:
                print(f"[Batch {batch_num}/{len(date_batches)}] Processing {batch_start}:")
            else:
                print(f"[Batch {batch_num}/{len(date_batches)}] Processing {len(date_batch)} days ({batch_end} to {batch_start}):")

            # Query records for this date batch
            record_ids = self.query_records_for_date_batch(
                collection_id,
                batch_end,    # Start with oldest date
                batch_start,  # End with newest date
                date_field_id,
                verbose=True
            )

            overall_stats["date_batches_processed"] += 1

            if not record_ids:
                print("  No records found, skipping...\n")
                continue

            overall_stats["date_batches_with_records"] += 1
            overall_stats["total_records_processed"] += len(record_ids)

            # Process each field for this day's records
            for field_num, (field_name, field_id) in enumerate(field_map.items(), 1):
                print(f"  [{field_num}/{len(field_map)}] Field: '{field_name}'")

                result = self.calculate_records_in_batches(
                    collection_id,
                    field_id,
                    field_name,
                    record_ids,
                    batch_size,
                    verbose=True
                )

                # Accumulate stats
                overall_stats["field_results"][field_name]["successful_batches"] += result["successful_batches"]
                overall_stats["field_results"][field_name]["failed_batches"] += result["failed_batches"]
                overall_stats["field_results"][field_name]["total_records"] += result["total_records"]

            print()  # Empty line between days

        # Print final summary
        self._print_final_summary(overall_stats)

        return overall_stats

    def _print_final_summary(self, stats: dict):
        """Print a comprehensive summary of the processing."""
        print(f"\n{'='*70}")
        print("FINAL SUMMARY")
        print(f"{'='*70}")
        print(f"Total days: {stats['total_days']}")
        print(f"Date batches processed: {stats['date_batches_processed']}")
        print(f"Date batches with records: {stats['date_batches_with_records']}")
        print(f"Total records processed: {stats['total_records_processed']}")
        print("\nPer-field results:")

        for field_name, field_stats in stats["field_results"].items():
            success = field_stats["successful_batches"]
            failed = field_stats["failed_batches"]
            total_batches = success + failed
            total_records = field_stats["total_records"]

            print(f"  • {field_name}:")
            print(f"      Records: {total_records}")
            print(f"      Batches: {success}/{total_batches} successful, {failed} failed")

        print(f"{'='*70}\n")

    def _call_calculate_api(
        self,
        collection_id: str,
        field_id: str,
        record_ids: List[str]
    ):
        """Call the Cogfy calculate records API.

        Args:
            collection_id (str): The collection ID
            field_id (str): The field ID to calculate
            record_ids (List[str]): List of record IDs to process

        Raises:
            requests.exceptions.RequestException: If the API request fails
        """
        url = urljoin(f"{self.base_url}/", f"collections/{collection_id}/records/calculate")

        payload = {
            "fieldId": field_id,
            "recordIds": record_ids
        }

        headers = {
            "Api-Key": self.client.api_key,
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=payload)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"API Error: {e}")
            print(f"Response: {response.text}")
            raise


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Calculate field values for records in a Cogfy collection. '
                    'Processes records day by day in descending order to prevent query overload.'
    )

    parser.add_argument(
        '--start-date',
        required=True,
        help='Start date for filtering records (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        required=True,
        help='End date for filtering records (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--collection-name',
        default='noticiasgovbr-all-news',
        help='Name of the Cogfy collection (default: noticiasgovbr-all-news)'
    )
    parser.add_argument(
        '--field-names',
        required=True,
        help='Comma-separated list of field names to calculate (e.g., "summary,tags,sentiment")'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of records to process per batch (default: 100)'
    )
    parser.add_argument(
        '--days-per-batch',
        type=int,
        default=5,
        help='Number of days to query per batch to prevent overload (default: 5)'
    )
    parser.add_argument(
        '--server-url',
        default='https://api.cogfy.com/',
        help='Cogfy server URL (default: https://api.cogfy.com/)'
    )
    parser.add_argument(
        '--date-field',
        default='published_at',
        help='Name of the date field to filter on (default: published_at)'
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()
    api_key = os.getenv("COGFY_API_KEY")

    if not api_key:
        print("Error: COGFY_API_KEY environment variable is required")
        sys.exit(1)

    # Parse field names from comma-separated string
    field_names = [name.strip() for name in args.field_names.split(',')]

    if not field_names:
        print("Error: At least one field name must be provided")
        sys.exit(1)

    try:
        # Initialize manager
        manager = CalculateRecordsManager(api_key, base_url=args.server_url)

        # Discover collection ID
        collection_id = manager.discover_collection_id(args.collection_name)
        if not collection_id:
            print(f"Error: Collection '{args.collection_name}' not found")
            sys.exit(1)

        # Discover field IDs for all field names
        field_map = manager.discover_multiple_field_ids(collection_id, field_names)

        if not field_map:
            print("Error: None of the specified fields were found in the collection")
            sys.exit(1)

        if len(field_map) < len(field_names):
            missing_fields = set(field_names) - set(field_map.keys())
            print(f"\nWarning: The following fields were not found and will be skipped: {', '.join(missing_fields)}")
            print(f"Proceeding with {len(field_map)} field(s)...\n")

        # Process by date and fields
        manager.process_by_date_and_fields(
            collection_id,
            field_map,
            args.start_date,
            args.end_date,
            args.date_field,
            args.batch_size,
            args.days_per_batch
        )

        print("Calculation completed successfully!")

    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
