# Script for processing a CSV file of metadata to upload to Commons
# CSV file format and columns:
# record_id, source_image_url, commons_filename, edit_summary, description

# Example row:
# nmnhbotany_2546215,https://ids.si.edu/ids/download?id=NMNH-00651834.jpg,Etlingera sp._nmnhbotany_2546215_NMNH-00651834.jpg,Uploaded by Wiki API Connector,"{{Information... }}"

import os
import sys
import requests
import hashlib
import pywikibot
import csv
import argparse
import logging
import tqdm

from urllib.parse import urlparse
from typing import Optional, List, Tuple
from pywikibot.specialbots import UploadRobot

# Configure logging
logging.basicConfig(level=logging.INFO)  # Adjust the logging level as needed
logger = logging.getLogger(__name__)

# Configure Pywikibot
from pywikibot import config
config.usernames['commons']['commons'] = 'Fuzheado'

def get_final_url(url: str, max_redirects: int = 10, current_redirects: int = 0) -> Optional[str]:
    """
    Get the final URL after following redirects up to a specified maximum number.

    This function sends an HTTP GET request to the provided URL and follows redirects
    until the final URL is reached or the maximum number of redirects is exceeded.
    """
    try:
        if current_redirects >= max_redirects:
            return None

        response = requests.get(url, allow_redirects=False)
        status_code = response.status_code

        # print ('Status code: ', status_code)
        if status_code == 200:
            return url
        elif status_code in [301, 302, 307, 308]:
            redirected_url = response.headers.get("Location")
            if redirected_url:
                return get_final_url(redirected_url, max_redirects, current_redirects + 1)
            else:
                return None
        else:
            return None  # Handle other status codes as needed

    except requests.RequestException as e:
        return None

def is_valid_url(url: str) -> bool:
    """Check if the URL is well-formed."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])  # Check if scheme and netloc (domain) are present
    except ValueError:
        return False

def download_image(url: str, filename: str) -> Optional[str]:
    """Download the image from the URL and save it as the given filename."""
    if not url:
        logger.debug("URL is empty or None. Skipping.")
        return None        
    if not is_valid_url(url):
        logger.error("Invalid URL: ", url)
        return None
    try:
        response = requests.get(url, allow_redirects=True, timeout=10)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            f.write(response.content)
        return filename
    except requests.RequestException as e:
        logger.error(f"Error occurred while downloading the image: {e}")
        return None

def file_exists_on_commons(filename: str) -> bool:
    """Check if the file already exists on Wikimedia Commons using SHA1 hash."""
    site = pywikibot.Site('commons', 'commons')
    sha1_hash = hashlib.sha1(open(filename, 'rb').read()).hexdigest()
    return any(page.exists() for page in site.allimages(sha1=sha1_hash))

def upload_to_commons(filepath: str, filename: str, description: str, edit_summary: str) -> None:
    """
    Upload the file to Wikimedia Commons using UploadRobot.
    """
    if not filepath:
        logger.debug(f"Missing filepath, skipping")
        return

    # TODO: Don't open a site each time, pass it in via parameter
    site = pywikibot.Site('commons', 'commons')

    with open('/dev/null', 'w') as f:
        # UploadRobot is noisy, and I cannot shut off its description output, so this is a fix
        # sys.stdout = f
        # sys.stderr = f

        # When always is set to True, ignore_warning or aborts must be set to True.
        upload_bot = UploadRobot([filepath],
                                 description=description,
                                 use_filename=filename,
                                 keep_filename=True,
                                 verify_description=False,
                                 summary=edit_summary,
                                 target_site=site,
                                 always=True,
                                 aborts=True   # Alternative is to set ignore_warning=True,
                                 )
        upload_bot.run()

    # Reset standard output
    sys.stdout = sys.__stdout__    
    sys.stderr = sys.__stderr__    

def process_csv(csv_file: str) -> None:
    """
    Process each row of the CSV file and upload images.
    """
    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row
        with tqdm.tqdm(total=len(list(reader)), unit='record') as pbar:
            file.seek(0)  # Reset the file pointer to the beginning
            next(reader)  # Skip the header row again
            for row in reader:
                record_id, url, filename, edit_summary, description = row
                pbar.set_description(f"Processing {record_id}")
    
                # Check if url or filename is None or empty
                if not url or not filename:
                    pbar.set_description(f"Skipping, empty URL or filename")
                    logger.debug(f"Skipping record {record_id} due to missing url or filename.")
                    continue  # Skip this record and move to the next one
        
                filepath = download_image(url, filename)
                if filepath and not file_exists_on_commons(filepath):
                    upload_to_commons(filepath, filename, description, edit_summary)
                    pbar.set_description(f"Uploaded {filename} to Wikimedia Commons.")
                else:
                    pbar.set_description(f"File {filename} already exists on Wikimedia Commons or download failed.")
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
                pbar.update(1) 

def main() -> None:
    parser = argparse.ArgumentParser(description="Upload images to Wikimedia Commons from a CSV file.")
    parser.add_argument("csv_file", help="Path to the CSV file containing the image URLs, filenames, and descriptions.")
    args = parser.parse_args()

    process_csv(args.csv_file)

if __name__ == "__main__":
    main()
