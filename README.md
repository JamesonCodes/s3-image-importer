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
/your-project-folder/
│
├── .env                 # Your secret AWS credentials (not committed to Git)
├── .gitignore           # Ensures .env is not committed to Git
├── your_image_urls.csv  # Your input data file with image URLs
├── s3_image_importer.py # The main Python script
├── requirements.txt     # Python dependencies
├── README.md            # This file
│
# Files generated after running the script:
│
├── processed_indices.log # Tracks successful copies
└── failed_urls.log       # Logs any errors
```

---

## Setup and Installation

### 1. Prerequisites
- Python 3.7 or newer installed.

### 2. Clone the Repository
Clone this repository to your local machine using the following command:

```bash
git clone https://github.com/JamesonCodes/s3-image-importer.git
cd s3-image-importer
```

### 3. Add Your CSV Data File
After cloning the repository, all necessary project files (including `s3_image_importer.py` and `requirements.txt`) are already present.

Place your CSV data file (e.g., `your_image_urls.csv`) in the project folder. This file should contain the image URLs you want to process.

### 4. Install Dependencies
Install all required Python libraries using the provided `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 5. Set Up Credentials (`.env` file)
In the project folder, create a file named `.env` and add your AWS credentials:

```env
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID_HERE
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_AWS_ACCESS_KEY_HERE
AWS_DEFAULT_REGION=us-east-1
```

### 6. Secure Your Credentials (`.gitignore` file)
To prevent accidentally committing your secret credentials to Git, create a file named `.gitignore` and add the following line:

```
.env
```

---

## Configuration

Before running the script, you must configure the constants at the top of the `s3_image_importer.py` file:

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

Once setup and configuration are complete, running the script is simple:

1. Open your terminal or command prompt.
2. Navigate to your project directory.
3. Run the script with the following command:

```bash
python s3_image_importer.py
```

The script will start, display how many images it's resuming, and show a progress bar for the remaining images.

---

## Troubleshooting

- **FileNotFoundError:** The script cannot find your CSV file. Double-check that the `CSV_FILE_PATH` variable in the script exactly matches the filename of your CSV and that the file is in the same folder as the script.
- **NoCredentialsError / Credentials not found:** Boto3 cannot find your AWS credentials.
  - Ensure your `.env` file is named correctly and is in the same folder.
  - Verify that the variable names (`AWS_ACCESS_KEY_ID`, etc.) are spelled correctly.
- **requests.exceptions.RequestException:** There was a problem downloading an image. This can be caused by network issues, a timeout, or a malformed URL. The specific URL will be logged in `failed_urls.log`.
- **HTTPError: 404 Not Found:** A URL in your CSV points to a location where there is no image. This is a common error for broken links.
- **HTTPError: 403 Forbidden:** You do not have permission to access the image at a specific URL, even though it is public. The server hosting the image may be blocking automated requests.
- **ClientError: AccessDenied:** This error comes from AWS S3. It means your credentials do not have permission to upload files to the destination bucket. Ensure your IAM user has `s3:PutObject` permission on the `DEST_S3_BUCKET`.