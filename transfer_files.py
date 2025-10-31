# transfer_files.py
import pandas as pd
import io
from google.cloud import storage
from datetime import datetime
import json 

def run():
    with open("config.json") as f:
        config=json.load(f)

    SOURCE_BUCKET_NAME = config["SOURCE_BUCKET_NAME"]
    SOURCE_BLOB_NAME = config["SOURCE_BLOB_NAME"]
    DESTINATION_BUCKET_NAME = config["DESTINATION_BUCKET_NAME"]
    storage_client = storage.Client()

    # Download CSV from source bucketa
    source_bucket = storage_client.bucket(SOURCE_BUCKET_NAME)
    source_blob = source_bucket.blob(SOURCE_BLOB_NAME)
    csv_bytes = source_blob.download_as_bytes()
    df = pd.read_csv(io.BytesIO(csv_bytes))

    # Timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    destination_blob_name = f"carauction_data/carauction_{timestamp}.csv"

    # Upload to destination bucket
    dest_bucket = storage_client.bucket(DESTINATION_BUCKET_NAME)
    dest_blob = dest_bucket.blob(destination_blob_name)

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    dest_blob.upload_from_string(csv_buffer.getvalue(), content_type="text/csv")

    print(f"CSV copied to gs://{DESTINATION_BUCKET_NAME}/{destination_blob_name} successfully!")
