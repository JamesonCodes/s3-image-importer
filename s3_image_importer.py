import pandas as pd
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import os
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from tqdm import tqdm
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image as PILImage
from typing import cast # <-- Add this import

# --- SCRIPT SETUP ---
load_dotenv()

# --- CONFIGURATION ---
CSV_FILE_PATH = 'your_csv_file.csv'                    # Path to your CSV file containing image URLs
URL_COLUMN_NAME = 'URL'                                # Name of the column in your CSV that contains the image URLs
DEST_S3_BUCKET = 'your-destination-bucket-name'        # Your AWS S3 bucket name where images will be uploaded
DEST_S3_FOLDER = 'your-folder-name'                    # Folder/prefix within the S3 bucket where images will be stored

MAX_WORKERS = 30                                       # Number of parallel workers (threads) for downloading/uploading. Adjust based on your system and network capacity.

PROGRESS_FILE = 'processed_indices.log'                # File to track which CSV rows have been successfully processed
ERROR_LOG_FILE = 'failed_urls.log'                     # File to log URLs that failed to process

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
    Downloads an image, validates it, determines its true file type,
    and uploads it to our S3 bucket with the correct file extension.
    """
    error_logger = logging.getLogger('error_logger')
    
    try:
        response = requests.get(source_url, timeout=30)
        response.raise_for_status()
        image_data = response.content

        try:
            image = PILImage.open(BytesIO(image_data))
            if not image.format:
                raise ValueError("Could not determine image format from the provided data.")
            image_format = image.format.lower()
        except Exception as e:
            raise ValueError(f"Invalid or unsupported image format. Pillow error: {e}")

        extension_map = {'jpeg': 'jpg'}
        extension = extension_map.get(image_format, image_format)

        base_filename = os.path.splitext(os.path.basename(urlparse(source_url).path))[0]
        if not base_filename:
             base_filename = f"image"

        new_filename = f"{base_filename}.{extension}"
        dest_key = f"{DEST_S3_FOLDER}/{original_index}_{new_filename}"

        s3_client.put_object(
            Bucket=DEST_S3_BUCKET,
            Key=dest_key,
            Body=image_data,
            ContentType=response.headers.get('Content-Type', f'image/{extension}')
        )
        return original_index

    except requests.exceptions.RequestException as e:
        error_message = f"RequestException downloading {source_url}: {e}"
        logging.warning(error_message)
        error_logger.error(f"{source_url} - {error_message}")
        raise e
    except (ClientError, ValueError) as e:
        error_message = f"Data or ClientError for {source_url}: {e}"
        logging.warning(error_message)
        error_logger.error(f"{source_url} - {error_message}")
        raise e
    except Exception as e:
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
    
    # --- FIX IS HERE ---
    # We apply the 'cast' right after the first filtering operation.
    # This tells the type checker that 'unprocessed_df' is still a DataFrame.
    unprocessed_df = cast(
        pd.DataFrame,
        df[~df.index.isin(processed_indices)]
    )
    
    # Now that pyright knows 'unprocessed_df' is a DataFrame, this next line will work correctly.
    tasks_to_process = unprocessed_df[unprocessed_df[URL_COLUMN_NAME].notna()]
    # --- END FIX ---
    
    if tasks_to_process.empty:
        logging.info("All images have already been processed or no new URLs found. Nothing to do.")
        return
        
    logging.info(f"Starting to download and upload {len(tasks_to_process)} new images...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_index = {
            executor.submit(process_image_download_upload, s3_client, row[URL_COLUMN_NAME], index): index
            for index, row in tasks_to_process.iterrows()
        }

        progress_bar = tqdm(as_completed(future_to_index), total=len(tasks_to_process), desc="Downloading/Uploading Images")
        
        for future in progress_bar:
            original_index = future_to_index[future]
            try:
                result_index = future.result()
                log_processed_index(result_index)
            except Exception:
                logging.warning(f"Failed to process row index {original_index}. See {ERROR_LOG_FILE} for details.")

    logging.info("Script finished.")


if __name__ == "__main__":
    main()