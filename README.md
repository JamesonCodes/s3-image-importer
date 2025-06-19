# S3 Image Importer from CSV

This script efficiently processes a large number of images from public URLs listed in a CSV file. It downloads each image and uploads it directly to a specified AWS S3 bucket.

The script is robust for high-volume tasks, featuring concurrent processing, automatic resumption after failure, and detailed error logging.

---

## Table of Contents
- [Features](#features)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)

---

## Features
- **Reliable Download & Upload:** Downloads images from public URLs and streams them directly to an S3 bucket without saving them to a local disk.
- **Concurrent Processing:** Uses a `ThreadPoolExecutor` to process multiple images simultaneously, dramatically reducing the time required for large datasets.
- **Automatic Resumability:** If the script is stopped for any reason, it can be restarted and will automatically skip any images that were already successfully processed.
- **Robust Error Logging:** Any URLs that fail to process are logged to a separate `failed_urls.log` file with a corresponding error message for easy review and debugging.
- **Secure Credential Management:** Uses a `.env` file to manage AWS credentials, keeping them separate from the source code and out of version control.
- **Live Progress Bar:** Provides a real-time progress bar using `tqdm` so you can monitor the status and estimate the time to completion.

---

## How It Works

The script maintains state and logs errors using two key files:

- **`processed_indices.log`:** Every time an image is successfully downloaded and uploaded, the script writes the corresponding row index from the CSV file into this log. On startup, the script reads this file to know which images to skip.
- **`failed_urls.log`:** If an error occurs (e.g., the URL is broken, a network error occurs, or an upload fails), the script writes the problematic URL and the error details to this file. This creates a clean list of all images that require manual investigation.

---

## Project Structure

```
/s3-image-importer/
│
├── .env                 # Your secret AWS credentials (not committed to Git)
├── .gitignore           # Ensures .env and venv/ are not committed to Git
├── your_image_urls.csv  # Your input data file with image URLs
├── s3_image_importer.py # The main Python script
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── venv/                # The isolated Python virtual environment (not committed)
│
# Files generated after running the script:
│
├── processed_indices.log # Tracks successful copies
└── failed_urls.log       # Logs any errors
```

---

## Setup and Installation

Follow these steps to create a clean, isolated environment for the project.

### 1. Prerequisites
- Python 3.8 or newer installed
- Git installed

### 2. Clone the Repository
Clone this repository to your local machine and navigate into the project directory:

```bash
git clone https://github.com/JamesonCodes/s3-image-importer.git
cd s3-image-importer
```

### 3. Create and Activate a Virtual Environment
This step creates an isolated environment for this project's dependencies.

```bash
# Create the virtual environment (this creates the venv/ folder)
python3 -m venv venv

# Activate the environment (you must do this in every new terminal session)
source venv/bin/activate
```
Your terminal prompt should now be prefixed with `(venv)`.

### 4. Add Your CSV Data File
Place your CSV data file (e.g., `your_image_urls.csv`) in the project folder. This file should contain the image URLs you want to process.

### 5. Install Dependencies
With the virtual environment active, install all required Python libraries using the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 6. Set Up Credentials (`.env` file)
Create a file named `.env` in the project folder and add your AWS credentials:

```env
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID_HERE
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_AWS_ACCESS_KEY_HERE
AWS_DEFAULT_REGION=us-east-1
```

The `.gitignore` file is already configured to ignore `.env` and `venv/`, keeping your secrets and environment files out of version control.

---

## Configuration

Before running the script, you must configure the constants at the top of the `s3_image_importer.py` file to match your needs:

```python
# --- CONFIGURATION ---
CSV_FILE_PATH = 'your_image_urls.csv'       # Your CSV filename
URL_COLUMN_NAME = 'URL'                     # Column with image URLs (update if your CSV uses a different column name)
DEST_S3_BUCKET = 'your-s3-bucket-name'      # Your destination S3 bucket
DEST_S3_FOLDER = 'your/s3/folder'           # The folder (prefix) within the bucket (e.g., 'Batch1' or 'images/')
MAX_WORKERS = 30                            # Number of concurrent downloads
```

---

## Usage

You must activate the virtual environment every time you open a new terminal to work on this project.

```bash
source venv/bin/activate
```

Run the script:

```bash
python s3_image_importer.py
```

The script will start, display how many images it's resuming, and show a progress bar for the remaining images.

When you are finished, you can leave the virtual environment by typing:

```bash
deactivate
```

---

## Troubleshooting

- **error: externally-managed-environment:** You forgot to activate the virtual environment. Stop the command and run `source venv/bin/activate` first.
- **ModuleNotFoundError:** You either forgot to activate the virtual environment or you haven't installed the dependencies yet. Run `source venv/bin/activate` and then `pip install -r requirements.txt`.
- **FileNotFoundError:** The script cannot find your CSV file. Double-check that `CSV_FILE_PATH` in the script configuration exactly matches your filename.
- **NoCredentialsError:** Boto3 cannot find your AWS credentials. Ensure your `.env` file is present, correctly named, and filled out.
- **requests.exceptions.RequestException:** A network error occurred while downloading an image (e.g., timeout, DNS issue). The specific URL will be logged in `failed_urls.log`.
- **HTTPError: 404 Not Found:** A URL in your CSV points to a location where there is no image.
- **HTTPError: 403 Forbidden:** You do not have permission to access the image at a specific URL. The server hosting the image may be blocking automated requests.
- **ClientError: AccessDenied:** This error comes from AWS S3. It means your credentials do not grant `s3:PutObject` permission on the `DEST_S3_BUCKET`.