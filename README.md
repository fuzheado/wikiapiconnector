# Wiki API Connector

This project is designed to provide a quick way to transfer image files from one repository (typically a museum/library/archive GLAM institution) to Wikimedia Commons and to work at scale.

## Problem
Donating an image (or set of images) to Wikimedia Commons is often a cumbersome process for a number of reasons:
* Metadata and modeling - It requires a deep understanding of the metadata of the data set, which may work for a one-time upload. Spreadsheet tools such as OpenRefine and Google Sheets may help for one-time load of data for a given session, but they usually are usually a poor fit for long-term repeated use. 
* Wikimedia experience - Users need to know quite a bit about Wikimedia templates, copyright, categories, and file naming before they can contribute.
* Working at scale - Even if one image can be uploaded, scaling it to dozens or hundreds of images is hard, requiring knowledge of API rate limits or categorization issues.
* Technical - Supporting an upload of large size and complexity requires quite a bit of technical expertise in scripting with Python or other tools.

Today, for the nontechnical users, the tools used include Google Sheets, Microsoft Excel, and/or Pattypan. Instead of relying on training with those tools, it would be nice to be able to specify an object identifier for a GLAM organization's API, and have it automatically uploaded to Wikimedia Commons with proper permissions and metadata.

## Solution

This proof of concept focuses on the needs of the Smithsonian Institution, and consists of three utilities:

* __si-collections-search-dumper.py__ (scrape of collections.si.edu)
    * Input: URL of a collections.si.edu search string, producing SERP
    * Output: List of identifiers (list), one per line, scraped from the SERP (ie. saam_1922.1.1)

* __wikiapiconnector-generator.py__ - Lookup object identifiers and use config file to create Commons file/metadata/template for upload
    * Input: List of identifiers (list); YAML configuration file with crosswalk mapping from organizational API to Wikimedia Commons template fields
    * Output: CSV file of external image URLs, desired commons filename, Commons template (ie. Artwork or Information)

* __commons-upload-csv.py__ - Upload of SI images and metadata to Commons
    * Input: CSV file of Commons-ready metadata (csv table)
    * Output: File uploaded to Wikimedia Commons

* Critical files
    * config.yml - YAML file with crosswalk mappings and definition of "units," as in institutional units of a museum and library
## Example Run

> python si-collections-search-dumper.py \\\
>     -o kelantan.txt \
>     "https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22"

> python wikiapiconnector-generator.py \\\
>    -c config-smithsonian.yml \\\
>    -u "Smithsonian National Museum of Natural History" \\\
>    -i kelantan.txt \\\
>    -o kelantan.csv

> python commons-upload-csv.py \\\
>     kelantan.csv 


Example searches:

https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22

https://collections.si.edu/search/results.htm?q=&fq=online_visual_material%3Atrue&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=object_type%3A%22Isotypes%22&fq=topic%3A%22Bryopsida%22&media.CC0=true&fq=place:%22Africa%22

## Contact
Andrew Lih (User:Fuzheado)

