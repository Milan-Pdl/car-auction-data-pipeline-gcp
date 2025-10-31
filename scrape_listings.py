# scrape_listings.py
import json
import hashlib
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import io
from google.cloud import storage
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# ------------------------
# Scraping function
# ------------------------
def scrape_to_df():
    """This function will scrap carauction data and return the df"""
    base_url = "https://www.citymotorauction.com.au/search_results.aspx?sitekey=CTY&make=All+Makes&model=All+Models"
    res = requests.get(base_url, timeout=30)
    soup = BeautifulSoup(res.text, "html.parser")
    listings = soup.select('div.result-item')

    car_data = []
    for data in listings:
        title_tag = data.find("h4", class_="result-item-title")
        ul_tag = data.find("ul", class_="inline")
        link_tag = title_tag.find("a") if title_tag else None

        if not title_tag or not ul_tag:
            continue

        title = title_tag.text.strip()
        ul_text = ul_tag.text.strip()

        href = ""
        if link_tag and link_tag.has_attr('href'):
            href = link_tag['href']
            if not href.startswith('http'):
                href = "https://www.citymotorauction.com.au/" + href

        unique_id = hashlib.md5(f"{title}_{href}".encode()).hexdigest()

        car_data.append({
            "ID": unique_id,
            "Title": title,
            "UL_Info": ul_text,
            "Auction_Link": href
        })

    # Extract structured info
    fuel_types = ["PREMIUM", "DIESEL", "PETROL"]

    def get_fuel_type(text):
        for fuel in fuel_types:
            if fuel in text.upper():
                return fuel
        return "Not available"

    Name, Make, Build_date, Body_type, Fuel_Type, Odometer = [], [], [], [], [], []

    for car in car_data:
        title_parts = car["Title"].split()
        build = title_parts[0] if len(title_parts) > 0 else "N/A"
        make = title_parts[1] if len(title_parts) > 1 else "N/A"
        name = " ".join(title_parts[:2]) if len(title_parts) >= 2 else "N/A"

        Build_date.append(build)
        Make.append(make)
        Name.append(name)

        ul_parts = car["UL_Info"].split()
        body = ul_parts[1] if len(ul_parts) > 1 else "N/A"
        odo = ul_parts[-2] if len(ul_parts) >= 2 else "N/A"
        fuel = get_fuel_type(car["UL_Info"])

        Body_type.append(body)
        Odometer.append(odo)
        Fuel_Type.append(fuel)

    # Auction hours left
    sydney_tz = pytz.timezone('Australia/Sydney')
    now = datetime.now(sydney_tz)
    auction_schedule = [(2, 10), (4, 11)]
    hours_left_list = []
    for weekday, hour in auction_schedule:
        days_ahead = (weekday - now.weekday() + 7) % 7
        auction_time = now + timedelta(days=days_ahead)
        auction_time = auction_time.replace(hour=hour, minute=0, second=0, microsecond=0)
        if auction_time < now:
            auction_time += timedelta(days=7)
        hours_left = (auction_time - now).total_seconds() / 3600
        hours_left_list.append(hours_left)

    Hours_left_wed = hours_left_list[0] if hours_left_list else 0.0
    Hours_left_fri = hours_left_list[1] if len(hours_left_list) > 1 else 0.0

    # Build DataFrame
    n = len(car_data)
    df = pd.DataFrame({
        "ID": [car["ID"] for car in car_data],
        "Title": [car["Title"] for car in car_data],
        "UL_Info": [car["UL_Info"] for car in car_data],
        "Name": Name,
        "Make": Make,
        "Build_date": Build_date,
        "Body_type": Body_type,
        "Fuel_Type": Fuel_Type,
        "Odometer": Odometer,
        "Hours_left_wednesday_auction": [Hours_left_wed]*n,
        "Hours_left_friday_auction": [Hours_left_fri]*n,
        "Auction_Link": [car["Auction_Link"] for car in car_data]
    })

    car_types = ['WAGON', 'CABRIOLET', 'SEDAN', 'COUPE', 'HATCHBACK', 'SPORTWAGON']
    return df[df['Body_type'].isin(car_types)].reset_index(drop=True)

def upload_df_to_gcs(df, bucket_name, destination_blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    blob.upload_from_string(csv_buffer.getvalue(), content_type="text/csv")
    print(f"DataFrame uploaded to gs://{bucket_name}/{destination_blob_name}")


def cloud_sql_upsert(df):
    """function to insert data from df to cloud sql database"""
    with open("config.json") as f:
        config = json.load(f)

    user = config["DB_USER"]
    password = quote_plus(config["DB_PASSWORD"])  
    db_name = config["DB_NAME"]
    host = config["DB_HOST"]

    # Create the SQLAlchemy engine
    engine = create_engine(
        f"mysql+pymysql://{user}:{password}@{host}/{db_name}?charset=utf8mb4"
    )
    df = df.copy()
    now = pd.Timestamp.now()
    df['scraped_at'] = now
    df['last_seen_date'] = now.date()
    df['first_seen_date'] = now.date()

    df.to_sql('temp_car_listings', engine, if_exists='replace', index=False)

    upsert_query = """
    INSERT INTO car_listings 
    (id, title, ul_info, name, make, build_date, body_type, fuel_type, 
     odometer, hours_left_wednesday_auction, hours_left_friday_auction, 
     auction_link, scraped_at, last_seen_date, first_seen_date)
    SELECT 
        t.ID, t.Title, t.UL_Info, t.Name, t.Make, t.Build_date, t.Body_type, t.Fuel_Type,
        t.Odometer, t.Hours_left_wednesday_auction, t.Hours_left_friday_auction,
        t.Auction_Link, t.scraped_at, t.last_seen_date, t.first_seen_date
    FROM temp_car_listings t
    ON DUPLICATE KEY UPDATE 
        last_seen_date = VALUES(last_seen_date),
        scraped_at = VALUES(scraped_at),
        title = VALUES(title),
        ul_info = VALUES(ul_info),
        odometer = VALUES(odometer),
        hours_left_wednesday_auction = VALUES(hours_left_wednesday_auction),
        hours_left_friday_auction = VALUES(hours_left_friday_auction)
    """

    with engine.connect() as conn:
        conn.execute(text(upsert_query))
        conn.execute(text("DROP TABLE IF EXISTS temp_car_listings"))

    print(f"Upserted {len(df)} records into Cloud SQL")

def run():
    print("Scraping started...")
    df = scrape_to_df()
    print(f"Scraped {len(df)} records.")
    upload_df_to_gcs(df, bucket_name="auctioncsv", destination_blob_name="datas/carauction.csv")
    cloud_sql_upsert(df)
    print("Scraping + GCS upload + Cloud SQL upsert completed successfully.")
