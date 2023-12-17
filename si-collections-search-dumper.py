# Script to take collections.si.edu search and dump out all identifiers that match

# Use Beautiful Soup screen scraper to find the "next" page link on the page, and craft the URL to get there
# !%pip install requests-cache

from bs4 import BeautifulSoup
# from urllib.request import urlopen
import requests
import requests_cache
import sys
from tqdm import tqdm
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(levelname)s:%(message)s'  # Define the log message format
)

url=''

def scrape_siid_by_url_recursive(inurl: str, bar) -> list:
    '''Take the result of a collections.si.edu search and get all the multi-page'''
    bar.update(1)
    logging.debug(inurl)
    page = requests.get(inurl)
    html = page.text
    soup = BeautifulSoup(html, "html.parser")

    returnlist = scrape_siid(soup)
    nexturl = scrape_nextlink(inurl, soup)
    if (nexturl):
        returnlist.extend(scrape_siid_by_url_recursive(nexturl, bar))
    return returnlist

def scrape_siid_by_url(inurl: str) -> list:
    '''Scrape page given URL string'''
    page = requests.get(inurl)
    html = page.text
    soup = BeautifulSoup(html, "html.parser")
    return scrape_siid(soup)

def scrape_siid(soup) -> list:
    '''Scrape collections.si.edu SERP and return list edan-url of format saam_1234.56'''
    idlist = []

    for i in soup.find_all('dl', class_='details edan-url'):
        foundid = i.find('dd').string.rsplit(':', 1)[-1]
        # TODO: should sanity check this string for right format
        if foundid:
            idlist.append(foundid)
    return idlist

def scrape_nextlink(inurl: str, soup) -> str:
    '''Parse collections.si.edu search results page for the next page link'''
    nextlink = None
    try:
        for i in soup.find('div', class_='pagination').find('ul').find_all('li'):
            if i.find('a').string == 'next':
                nextlink = i.find('a').get('href')
        if nextlink:
            return inurl.rsplit('?', 1)[0] + nextlink
        else:
            return None
            
    except ScrapingError as e:
        logging.error(f"Scraping Error: {e}")
        return None

def process_scrape(url, output_file) -> None:
    """
    Given a url link to Smithsonian collections search, return all ids found
    """
    print ('Scrape collections.si.edu search results from:', url)
    n = 25 # Max number of pages from SI collections search, 500 items, 20 items per page
    bar = tqdm(total=n)
    edanlist = scrape_siid_by_url_recursive(url, bar=bar)

    output_stream = sys.stdout if output_file is None else open(output_file, 'w')

    # Output the entries
    print("\n".join(edanlist), file=output_stream)
    
    if output_file is not None:
        output_stream.close()        

    
def main():
    parser = argparse.ArgumentParser(description="Process a list of identifiers")

    # Add the positional argument for identifiers (accepts multiple values)
    parser.add_argument("url", nargs="*", metavar="URL", help="URL to scrape")

    # Add optional command line options
    parser.add_argument("-o", "--output", dest="output_file", help="Output file (default is stdout)")

    # Parse the command line arguments
    args = parser.parse_args()

    # If identifiers are not provided as command line arguments or in a file, read from standard input
    if not args.url:
        url = input("Enter a URL: ")
    else:
        url = args.url[0]

    # Call the process_identifiers function with the provided arguments
    if url:
        process_scrape(url, args.output_file)
    else:
        logging.error('Requires at least one URL')

if __name__ == "__main__":

    requests_cache.install_cache('sicollections_cache', backend='sqlite', expire_after=259200) # 3 days
    logging.getLogger().setLevel(logging.INFO)
    main()

    # TEST CASE
# https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22&fq=topic:%22Monocotyledonae%22
