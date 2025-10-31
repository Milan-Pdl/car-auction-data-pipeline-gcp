from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
import scrape_listings
import transfer_files
import publish_data

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 10, 20)
}

dag = DAG(
    'auction_data_pipeline',
    default_args=default_args,
    schedule_interval='0 21 * * *'
)

task_scrape = PythonOperator(
    task_id='scrape_listing_task',
    python_callable=scrape_listings.run,
    dag=dag
)

task_transfer = PythonOperator(
    task_id='transfer_files_task',
    python_callable=transfer_files.run,
    dag=dag
)

task_publish= PythonOperator(
    task_id="publish_files_task",
    python_callable=publish_data.run,
    dag=dag
)

task_scrape >> task_transfer >> task_publish
