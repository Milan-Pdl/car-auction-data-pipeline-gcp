# publish_data.py
import pandas as pd
from sqlalchemy import create_engine, text
from google.cloud import pubsub_v1
from urllib.parse import quote_plus
import json
import os


def load_config(config_path: str = "config.json") -> dict:
    """Loads configuration values from the JSON file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    
    with open(config_path) as f:
        config = json.load(f)
    return config


def get_sql_engine(config: dict):
    """Creates and returns the SQLAlchemy engine for Cloud SQL connection."""
    user = config["DB_USER"]
    password = quote_plus(config["DB_PASSWORD"])
    db_name = config["DB_NAME"]
    host = config["CLOUD_SQL_HOST"]

    engine = create_engine(
        f"mysql+pymysql://{user}:{password}@{host}/{db_name}?charset=utf8mb4"
    )
    return engine


def publish_to_pubsub(config: dict):
    """Queries Cloud SQL and publishes the resulting rows to a Pub/Sub topic."""
    GCP_PROJECT_ID = config["GCP_PROJECT_ID"]
    PUBSUB_TOPIC_NAME = config["PUBSUB_TOPIC_NAME"]

    # Initialize database connection
    engine = get_sql_engine(config)

    # Query to get today's listings
    query = """
        SELECT * 
        FROM car_auction.car_listings 
        WHERE last_seen_date = CURRENT_DATE()
    """

    try:
        df_to_publish = pd.read_sql(text(query), engine)
    except Exception as e:
        print(f"Error reading from Cloud SQL: {e}")
        return

    if df_to_publish.empty:
        print("No new records found for today. Nothing to publish.")
        return

    # Initialize Pub/Sub publisher
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GCP_PROJECT_ID, PUBSUB_TOPIC_NAME)

    print(f"Attempting to publish {len(df_to_publish)} records to Pub/Sub topic '{PUBSUB_TOPIC_NAME}'...")

    published_count = 0

    for _, row in df_to_publish.iterrows():
        # Convert each row to JSON
        data_dict = row.to_dict()
        data = json.dumps(data_dict, default=str).encode("utf-8")

        # Publish message
        publisher.publish(topic_path, data)
        published_count += 1

    print(f"Successfully published {published_count} records to '{PUBSUB_TOPIC_NAME}'.")


def run():
    """Main entry point."""
    config = load_config()
    publish_to_pubsub(config)



