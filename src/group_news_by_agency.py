import os
import asyncio
import datetime
from collections import defaultdict
import httpx

source_collection_id = "7e8540e7-2ed6-4aac-9408-a9a38005561d"
target_collection_id = "5ab91622-af3b-4fda-a663-bf479325f779"
base_api_url = "https://api.cogfy.com"
api_key = os.getenv("COGFY_API_KEY")

async def main():
    async with httpx.AsyncClient(
        headers={"Api-Key": api_key}
    ) as client:
        # --- Step 1: Query source collection ---
        query_endpoint_url = f"{base_api_url}/collections/{source_collection_id}/records/query"
        records_query = {
            "filter": {
                "type": "and",
                "and": {
                    "filters": [
                        {
                            "type": "greaterThanOrEquals",
                            "greaterThanOrEquals": {
                                "fieldId": "732a7629-4fb8-41f7-b9f1-c087a780a7a1",
                                "value": (
                                    datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
                                ).isoformat().replace("+00:00", "Z")
                            }
                        }
                    ]
                }
            }
        }

        query_response = await client.post(query_endpoint_url, json=records_query)
        query_response.raise_for_status()
        response_records = query_response.json().get("data", [])

        # --- Step 2: Parse records ---
        parsed_records = [
            {
                "id": record["id"],
                "agency": record["properties"].get("1177bf35-e71b-4e65-a6e2-10b3e965032a")["text"]["value"],
                "title": record["properties"].get("32dce3ba-7ef2-4d82-a901-43b515d4ffe5")["text"]["value"],
                "category": record["properties"].get("040d8543-2b84-42d4-8176-c4dd044c7014")["text"]["value"],
                "content": record["properties"].get("6eb744d4-f7d8-4c92-be16-4955ef04e6ae")["text"]["value"]
            }
            for record in response_records
        ]

        # --- Step 3: Group by agency ---
        grouped_records = defaultdict(list)
        for record in parsed_records:
            grouped_records[record["agency"]].append(record)

        # --- Step 4: Prepare async insert tasks ---
        insert_endpoint_url = f"{base_api_url}/collections/{target_collection_id}/records"
        tasks = []
        for agency, agency_records in grouped_records.items():
            record_to_create = {
                "properties": {
                    "81ff2da8-4b46-4483-9843-ec01ba66a994": {
                        "type": "json",
                        "json": {
                            "value": {
                                "agency": agency,
                                "records": agency_records
                            }
                        }
                    }
                }
            }
            tasks.append(client.post(insert_endpoint_url, json=record_to_create))

        # --- Step 5: Run all inserts in parallel ---
        responses = await asyncio.gather(*tasks)
        for r in responses:
            r.raise_for_status()

        print(f"Inserted {len(grouped_records)} grouped records into target collection.")

if __name__ == "__main__":
    asyncio.run(main())
