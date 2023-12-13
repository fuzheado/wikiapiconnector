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

def upload_to_commons(url: str, filename: str, description: str) -> None:
    """Upload the file to Wikimedia Commons using UploadRobot."""
    site = pywikibot.Site('commons', 'commons')

    # See this example for more parameters -
    # https://doc.wikimedia.org/pywikibot/master/_modules/scripts/upload.html
    expanded_url = get_final_url(url)
    upload_bot = UploadRobot(url=expanded_url,
                             description=description,
                             use_filename=filename,
                             keep_filename=True,
                             verify_description=False,
                             target_site=site)
    upload_bot.run()

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
                upload_to_commons(url, filename, description)
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
            upload_to_commons(url, filename, description)
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