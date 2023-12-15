import subprocess
import argparse

# Create an argument parser
parser = argparse.ArgumentParser(description="Script to upload files to Wikimedia Commons based on a Smithsonian Collections search result from https://collections.si.edu/", epilog="""

Usage:
  python siwikiapiconnect.py -u <unit> -s <searchurl> -c <config>

Example:
  python wikiapiconnect.py -u "Smithsonian American Art Museum" -s https://collections.si.edu/search/results.htm?q=&view=grid&fq=online_visual_material%3Atrue&media.CC0=true&fq=data_source:%22Smithsonian+American+Art+Museum%22
""")

# Add command-line arguments for FILEBASE, SEARCHURL, and CONFIGFILE
parser.add_argument("-u", "--unit", dest='unit_string', required=True, help="Organizational unit in the config file (required)")
parser.add_argument("-s", "--searchurl", dest='search_url', required=True, help="Search URL from Smithsonian (required)")
parser.add_argument("-b", "--filebase", dest='file_base', default='wacfile', required=False, help="Base filename for intermediate files (default: wac)")
parser.add_argument("-c", "--configfile", dest='config_file', default='config.yml', required=False, help="Configuration file in yaml format (default: config.yml)")

# Parse the command-line arguments
args = parser.parse_args()

# Execute the first Python script with the specified parameters
subprocess.run(["python", "si-collections-search-dumper.py", "-o", f"{args.file_base}.txt", args.search_url])

# Execute the second Python script with the specified parameters
subprocess.run(["python", "wikiapiconnector-generator.py", "-c", args.config_file, "-i", f"{args.file_base}.txt", "-o", f"{args.file_base}.csv", "-u", args.unit_string])

# Execute the third Python script with the specified parameters
subprocess.run(["python", "commons-upload-csv.py", f"{args.file_base}.csv"])
