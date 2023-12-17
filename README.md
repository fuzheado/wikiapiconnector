# Wiki API Connector

This project is designed to provide a quick way to transfer image files from one repository (typically a museum/library/archive GLAM institution) to Wikimedia Commons and to work at scale.

## Problem
Donating an image (or set of images) to Wikimedia Commons is often a cumbersome process for a number of reasons:
* Metadata and modeling - It requires a deep understanding of the metadata of the data set, which may work for a one-time upload. However, it would be nice to make capture this process for future use. Spreadsheet tools such as OpenRefine and Google Sheets may help for one session, but they usually are not useful for long-term repeated use.
* Wikimedia experience - Users need to know quite a bit about Wikimedia templates, copyright, categories, and file naming before they can contribute.
* Working at scale - Even if one image can be uploaded, scaling it to dozens or hundreds of images is hard.
* Technical - Supporting an upload of large size and complexity requires quite a bit of technical expertise in scripting with Python or other tools.

Today, for the nontechnical, the tools used include Google Sheets, Microsoft Excel, and/or Pattypan.

## Solution

This proof of concept focuses on the needs of the Smithsonian Institution, and consists of three utilities:

Search url (str)
|
 . si-collections-search-dumper.py (scrape of collections.si.edu)
|
List of identifiers (list)
|
 . wikiapiconnector-generator.py
|
List of SI images and metadata via SI API lookup (list)
|
 . wikiapiconnector-generator.py
|
CSV file of Commons-ready metadata (csv table)
|
 . commons-upload-csv.py - Upload of SI images and metadata to Commons
|
Images on Commons

## Example Run

python si-collections-search-dumper.py \
    -o kelantan.txt \
    "https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22"

python wikiapiconnector-generator.py \
    -c config-smithsonian.yml \
    -u "Smithsonian National Museum of Natural History" \
    -i kelantan.txt \
    -o kelantan.csv

python commons-upload-csv.py \
    kelantan.csv 


Example searches:

https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22

https://collections.si.edu/search/results.htm?q=&fq=online_visual_material%3Atrue&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=object_type%3A%22Isotypes%22&fq=topic%3A%22Bryopsida%22&media.CC0=true&fq=place:%22Africa%22

## Contact
Andrew Lih (User:Fuzheado)

