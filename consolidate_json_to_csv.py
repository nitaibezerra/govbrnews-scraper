import json
import os
import zipfile

import pandas as pd

RAW_EXTRACTIONS_FOLDER = "raw_extractions"
OUTPUT_CSV_PATH = os.path.join(
    RAW_EXTRACTIONS_FOLDER, "full_history_since_20240101.csv"
)
OUTPUT_ZIP_PATH = os.path.join(
    RAW_EXTRACTIONS_FOLDER, "full_history_since_20240101.zip"
)


def consolidate_json_to_csv():
    # List to store all the news data
    consolidated_data = []

    # Traverse the raw_extractions folder
    for agency_folder in os.listdir(RAW_EXTRACTIONS_FOLDER):
        agency_path = os.path.join(RAW_EXTRACTIONS_FOLDER, agency_folder)

        if os.path.isdir(agency_path):
            # Process each JSON file in the agency folder
            for json_file in os.listdir(agency_path):
                if json_file.endswith(".json"):
                    json_file_path = os.path.join(agency_path, json_file)

                    # Read the JSON data
                    with open(json_file_path, "r", encoding="utf-8") as f:
                        news_items = json.load(f)

                        # Prepare each news item and add the agency name
                        for news_item in news_items:
                            news_item["tags"] = ",".join(
                                news_item.get("tags", [])
                            )  # Convert list to comma-separated string
                            news_item["agency"] = agency_folder  # Add the agency name
                            consolidated_data.append(news_item)

    # Convert the list of dictionaries into a pandas DataFrame
    df = pd.DataFrame(consolidated_data)

    # Reorder columns so that 'agency' is first
    columns_order = ["agency", "title", "url", "date", "category", "tags", "content"]
    df = df[columns_order]

    # Sort the DataFrame by 'agency' and 'date' in ascending order
    df["date"] = pd.to_datetime(
        df["date"], errors="coerce"
    )  # Ensure the date is in datetime format
    df = df.sort_values(by=["agency", "date"], ascending=[True, True])

    # Save the DataFrame to a CSV file
    df.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8")

    print(f"CSV consolidation complete: {OUTPUT_CSV_PATH}")


def compress_csv_to_zip():
    # Compress the CSV file into a ZIP archive
    with zipfile.ZipFile(OUTPUT_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(OUTPUT_CSV_PATH, os.path.basename(OUTPUT_CSV_PATH))

    print(f"CSV compressed into ZIP: {OUTPUT_ZIP_PATH}")


if __name__ == "__main__":
    consolidate_json_to_csv()
    compress_csv_to_zip()
