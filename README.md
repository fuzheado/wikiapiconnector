# Wiki API Connector

This project is designed to provide a quick way to transfer image files from one repository (typically a museum/library/archive GLAM institution) to Wikimedia Commons.

## Problem
Donating an image (or set of images) to Wikimedia Commons is usually a cumbersome process:
* Metadata and modeling - It requires a deep understanding of the metadata of the data set, and the particular way a 
* Wikimedia experience - Users need to know quite a bit about Wikimedia templates, copyright, categories, and file naming.
* Working at scale - Even if one image can be uploaded, scaling it to dozens or hundreds of images is harda
* Technical - This usually requires quite a bit of technical expertise in scripting with Python or other tools

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

si-collections-search-dumper.py
    "https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22"
    -o kelantan.txt

wikiapiconnector-generator.py 
    -c config-smithsonian.yml 
    -u "Smithsonian National Museum of Natural History" 
    -i kelantan.txt 
    -o kelantan.csv

commons-upload-csv.py
    kelantan.csv 


Example searches:

https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22

## Contact
Andrew Lih (User:Fuzheado)

