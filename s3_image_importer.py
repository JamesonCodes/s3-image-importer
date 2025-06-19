import pandas as pd
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import os
import logging
import requests  # <-- Required for downloading from public URLs
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from tqdm import tqdm
from dotenv import load_dotenv

# --- SCRIPT SETUP ---
load_dotenv()  # Load variables from .env file

# --- CONFIGURATION ---
CSV_FILE_PATH = 'your_image_urls.csv'       # Your CSV filename
URL_COLUMN_NAME = 'URL'                     # Column with image URLs (update if your CSV uses a different column name)
DEST_S3_BUCKET = 'your-s3-bucket-name'      # Your destination S3 bucket
DEST_S3_FOLDER = 'your/s3/folder'           # The folder (prefix) within the bucket (e.g., 'Batch1' or 'images/')

MAX_WORKERS = 30                            # Adjust based on your system. 20-50 is a reasonable range.

PROGRESS_FILE = 'processed_indices.log'
ERROR_LOG_FILE = 'failed_urls.log'

# --- SCRIPT ---

def setup_logging():
    """Sets up two loggers: one for errors and one for general info."""
    error_logger = logging.getLogger('error_logger')
    if not error_logger.handlers:
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(ERROR_LOG_FILE)
        error_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        error_logger.addHandler(error_handler)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        force=True)

def load_processed_indices():
    """Loads the set of already processed CSV row indices from the progress file."""
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE, 'r') as f:
        return {int(line.strip()) for line in f if line.strip()}

def log_processed_index(index):
    """Appends a successfully processed index to the progress file."""
    with open(PROGRESS_FILE, 'a') as f:
        f.write(f"{index}\n")

def process_image_download_upload(s3_client, source_url, original_index):
    """
    Downloads an image from a public URL and uploads it to our S3 bucket.
    """
    error_logger = logging.getLogger('error_logger')
    
    try:
        # 1. Download the image from the public URL
        response = requests.get(source_url, timeout=30)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)

        # 2. Get the binary image data
        image_data = response.content
        
        # 3. Define the destination key
        # Extract filename from URL path to keep it readable
        filename = os.path.basename(urlparse(source_url).path)
        if not filename: # Handle case where URL ends with a /
             filename = f"image_{original_index}.jpg" # fallback filename
        dest_key = f"{DEST_S3_FOLDER}/{original_index}_{filename}"

        # 4. Upload the image data to our S3 bucket
        s3_client.put_object(
            Bucket=DEST_S3_BUCKET,
            Key=dest_key,
            Body=image_data,
            ContentType=response.headers.get('Content-Type', 'image/jpeg') # Preserve content type
        )
        return original_index

    except requests.exceptions.RequestException as e:
        # Handle download errors (network issues, invalid URL, timeouts)
        error_message = f"RequestException downloading {source_url}: {e}"
        logging.warning(error_message)
        error_logger.error(f"{source_url} - {error_message}")
        raise e
    except ClientError as e:
        # Handle S3 upload errors (e.g., AccessDenied to *our* bucket)
        error_code = e.response.get("Error", {}).get("Code")
        error_message = f"AWS ClientError uploading {source_url}: {error_code}"
        logging.warning(error_message)
        error_logger.error(f"{source_url} - {error_message}")
        raise e
    except Exception as e:
        # Handle any other unexpected errors
        error_message = f"An unexpected error occurred for URL {source_url}: {e}"
        logging.warning(error_message)
        error_logger.error(f"{source_url} - {error_message}")
        raise e

def main():
    """Main function to orchestrate the image import process."""
    setup_logging()
    
    try:
        s3_client = boto3.client('s3')
    except NoCredentialsError:
        logging.error("Failed to create Boto3 client. Check credentials in .env file.")
        return

    try:
        df = pd.read_csv(CSV_FILE_PATH)
        if URL_COLUMN_NAME not in df.columns:
            logging.error(f"Column '{URL_COLUMN_NAME}' not found in {CSV_FILE_PATH}.")
            return
    except FileNotFoundError:
        logging.error(f"CSV file not found at: {CSV_FILE_PATH}")
        return

    processed_indices = load_processed_indices()
    logging.info(f"Found {len(processed_indices)} already processed images. Resuming...")
    
    tasks_to_process = df[~df.index.isin(processed_indices)]
    
    if tasks_to_process.empty:
        logging.info("All images have already been processed. Nothing to do.")
        return
        
    logging.info(f"Starting to download and upload {len(tasks_to_process)} new images...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_index = {
            # Call the new download/upload function
            executor.submit(process_image_download_upload, s3_client, row[URL_COLUMN_NAME], index): index
            for index, row in tasks_to_process.iterrows()
        }

        progress_bar = tqdm(as_completed(future_to_index), total=len(tasks_to_process), desc="Downloading/Uploading Images")
        
        for future in progress_bar:
            original_index = future_to_index[future]
            try:
                result_index = future.result()
                log_processed_index(result_index)
            except Exception as e:
                logging.warning(f"Failed to process row index {original_index}. See {ERROR_LOG_FILE} for details.")

    logging.info("Script finished.")

if __name__ == "__main__":
    main()