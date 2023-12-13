# Script for processing a CSV file of metadata to upload to Commons
# CSV file format and columns:
# record_id, source_image_url, commons_filename, edit_summary, description

# Example row:
# nmnhbotany_2546215,https://ids.si.edu/ids/download?id=NMNH-00651834.jpg,Etlingera sp._nmnhbotany_2546215_NMNH-00651834.jpg,Uploaded by Wiki API Connector,"{{Information... }}"

import sys
import requests
import hashlib
import pywikibot
import csv
import argparse
from io import BytesIO
from typing import Optional, List, Tuple
from pywikibot.specialbots import UploadRobot

# Configure your Pywikibot
from pywikibot import config
config.usernames['commons']['commons'] = 'Fuzheado'

def download_image(url: str) -> Optional[BytesIO]:
    """Download the image from the URL and return it as a BytesIO object."""
    try:
        response = requests.get(url, allow_redirects=True, timeout=10)
        response.raise_for_status()
        return BytesIO(response.content)
    except requests.RequestException as e:
        print(f"Error occurred while downloading the image: {e}")
        return None

def file_exists_on_commons(image_data: BytesIO, filename: str) -> bool:
    """Check if the file already exists on Wikimedia Commons using SHA1 hash."""
    site = pywikibot.Site('commons', 'commons')
    sha1_hash = hashlib.sha1(image_data.getvalue()).hexdigest()
    return any(page.exists() for page in site.allimages(sha1=sha1_hash))

def upload_to_commons(image_data: BytesIO, filename: str, description: str) -> None:
    """Upload the file to Wikimedia Commons."""
    site = pywikibot.Site('commons', 'commons')
    file_page = pywikibot.FilePage(site, 'File:' + filename)  # Create a new file page
    file_page.text = description

    # Upload the image
    pywikibot.upload.upload(image_data, file_page, comment=description, ignore_warnings=True)

def process_csv(csv_file: str) -> None:
    """Process each row of the CSV file and upload images."""
    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row
        for row in reader:
            record_id, url, filename, edit_summary, description = row
            print (f"Processing {record_id}")
            image_data = download_image(url)
            if image_data and not file_exists_on_commons(image_data, filename):
                upload_to_commons(image_data, filename, description)
                print(f"Uploaded {filename} to Wikimedia Commons.")
            else:
                print(f"File {filename} already exists on Wikimedia Commons or download failed.")

def process_csv_data(csv_data: List[List[str]]) -> None:
    """Process each row of the CSV data and upload images."""
    for row in csv_data:
        # record_id, source_image_url, commons_filename, edit_summary, description
        record_id, url, filename, edit_summary, description = row
        print (f"Processing {record_id}")
        image_data = download_image(url)
        if image_data and not file_exists_on_commons(image_data, filename):
            upload_to_commons(image_data, filename, description)
            print(f"Uploaded {filename} to Wikimedia Commons.")
        else:
            print(f"File {filename} already exists on Wikimedia Commons or download failed.")

def read_csv_from_stdin() -> List[List[str]]:
    """Read CSV formatted data from stdin and return it as a list of lists."""
    reader = csv.reader(sys.stdin)
    return list(reader)

def main() -> None:
    parser = argparse.ArgumentParser(description="Upload images to Wikimedia Commons from a CSV file or stdin.")
    parser.add_argument("csv_file", nargs='?', help="Path to the CSV file containing the image URLs, filenames, and descriptions. If omitted, reads from stdin.")
    args = parser.parse_args()

    if args.csv_file:
        process_csv(args.csv_file)
    else:
        csv_data = read_csv_from_stdin()
        process_csv_data(csv_data)

if __name__ == "__main__":
    main()