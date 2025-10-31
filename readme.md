🚗 Car Auction Data Pipeline (GCP + Airflow)
📘 Project Overview

This project automates an end-to-end data pipeline for scraping, storing, and publishing daily car auction data from City Motor Auction.

The pipeline is orchestrated using Apache Airflow and integrates multiple Google Cloud Platform (GCP) services:

Cloud Storage (GCS) → stores raw and processed CSVs

Cloud SQL (MySQL) → stores car listings with incremental updates

Pub/Sub → publishes daily auction updates for downstream systems

🧩 Data Flow Overview

<img width="1024" height="812" alt="Gemini_Generated_Image_b1dkb3b1dkb3b1dk" src="https://github.com/user-attachments/assets/defd9675-7231-4714-985c-babdd0e1ac60" />

🧠 Components
1. scrape_listings.py

Scrapes data from the City Motor Auction website using BeautifulSoup.

Cleans and structures the dataset.

Uploads the CSV file to a GCS bucket (auctioncsv/datas/carauction.csv).

Inserts/updates car listings into Cloud SQL (car_listings table) using incremental upsert logic.

2. transfer_files.py

Fetches the daily CSV from the source bucket.

Creates a timestamped copy in the destination bucket (daily_auction_csv/carauction_data/).

3. publish_data.py

Queries Cloud SQL for today’s listings.

Publishes each record to a Pub/Sub topic (auction) as JSON messages.

Handles type conversions and empty results gracefully.

4. auction_data_pipeline.py

Airflow DAG that automates all steps:

scrape_listings.run()
transfer_files.run()
publish_data.run()


Runs daily at 9:00 PM UTC (3:45 AM NPT).

Ensures sequential execution:

scrape_listings → transfer_files → publish_data

🧰 Setup Instructions
1. Clone the repository
git clone https://github.com/your-username/car-auction-pipeline.git
cd car-auction-pipeline

2. Create a Python virtual environment
python -m venv venv
source venv/bin/activate    # Linux/Mac
venv\Scripts\activate       # Windows

3. Install dependencies
pip install -r requirements.txt


Example requirements:

pandas
sqlalchemy
pymysql
google-cloud-storage
google-cloud-pubsub
beautifulsoup4
requests
pytz
apache-airflow

4. Set up Google Cloud credentials
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"

5. Run scripts individually (optional)
python scrape_listings.py
python transfer_files.py
python publish_data.py

6. Deploy the DAG to Airflow / Cloud Composer

Copy auction_data_pipeline.py to your Airflow DAGs folder.

Verify it appears in the Airflow UI.

Trigger the DAG manually or wait for the scheduled run.

📊 Output Example

Cloud SQL Table (car_listings):

ID	Title	Make	Odometer	Fuel_Type	last_seen_date
abc123	2020 TOYOTA CAMRY	TOYOTA	22,000	PETROL	2025-10-31

Pub/Sub Message (JSON):

{
  "ID": "abc123",
  "Title": "2020 TOYOTA CAMRY",
  "Make": "TOYOTA",
  "Fuel_Type": "PETROL",
  "Odometer": "22,000",
  "last_seen_date": "2025-10-31"
}

🛡️ Security Notes

All sensitive credentials are loaded from config.json (never hardcoded).

config.json and service-account-key.json are included in .gitignore.

Database passwords are URL-encoded using urllib.parse.quote_plus.

👨‍💻 Author

Milan Paudel
Data Engineering & Cloud Enthusiast
🚀 Passionate about building scalable data pipelines and cloud-native ETL solutions.
