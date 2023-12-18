# Wiki API Connector

This project is designed to provide a quick way to transfer image files from one repository (typically a museum/library/archive GLAM institution) to Wikimedia Commons and to work at scale.

In short - How might we make the classic extract-transform-load (ETL) pipeline as simple as possible for oridnary users wanting to bring images and metadata from an institution into Wikimedia Commons?

This proof of conept is specific to the Smithsonian Institution and Wikimedia Commons files using wikitext and was developed as part of the author's role as the Smithsonian's _Wikimedian at Large_.

A brief description of the problem and solution can be found at this [presentation from WikidataCon and Hack4OpenGLAM](https://docs.google.com/presentation/d/e/2PACX-1vQ9oOHFnTNcB7ox0UDzzsgvhk_R5NF-G5G78o2h2o72tBxLwhBPj7wQq_44u_Z-wZBX49LwNgdDGYy_/pub?start=false&loop=false&delayms=3000)

Examples of uploads using this tool can be found in the catgory:
* [Category:Wiki_API_Connector_Upload](https://commons.wikimedia.org/wiki/Category:Wiki_API_Connector_Upload)

## Problem
Donating an image (or set of images) to Wikimedia Commons is often a cumbersome process for a number of reasons:
* Metadata and modeling - This requires a deep understanding of the metadata of the data set, which the user typically wants to work with over time. Spreadsheet tools such as OpenRefine and Google Sheets may help for one-time load of data for a given session, but they are usually a poor fit for long-term repeated use, or sharing a best practice with others is difficult.
* Wikimedia experience - Users need to know the intricacies of Wikimedia Commons templates, copyright, categories, and file naming before they can contribute.
* Working at scale - Even if one image can be uploaded, scaling it to dozens or hundreds of images is hard, requiring knowledge of API rate limits or categorization issues.
* Technical - Supporting an upload of large size and complexity requires quite a bit of technical expertise in scripting with Python or other tools.

Today, for the nontechnical users, the tools used include Google Sheets, Microsoft Excel, and/or Pattypan. Instead of relying on training with those tools, it would be nice to be able to specify an object identifier for a GLAM organization's API, and have it automatically uploaded to Wikimedia Commons with proper permissions and metadata.

### Previous solutions
Solutions for this problem include tools such as

* [OpenRefine](https://commons.wikimedia.org/wiki/Commons:OpenRefine) - active and robust community, though operation is complex
* [Pattypan](https://commons.wikimedia.org/wiki/Commons:Pattypan) - easy to use spreadsheet-based uploading but provides no facility to help map metadata
* [GLAM Wiki Toolset](https://commons.wikimedia.org/wiki/Commons:GLAMwiki_Toolset_Project) - deprecated
* [GLAMpipe](https://github.com/GLAMpipe/GLAMpipe) - inactive
* [glam2commons](https://phabricator.wikimedia.org/T138464) - inactive, [github repository](https://github.com/infobliss/sibutest2)

## Solution

This proof of concept focuses on the needs of the Smithsonian Institution, and consists of three utilities described below. However, there is a convenience script that encapsulates all the functions into one command line.

### Easy invocation
The ingestion pipeline can be invoked in one line with the tool "siwikiapiconnect.py" executed with the following parameters:

> python siwikiapiconnect.py \\\
> -c config.yml \\\
> -b nmnh-pteridophyte \\\
> -u "Smithsonian National Museum of Natural History taxonomy" \\\
> -s "https://collections.si.edu/search/results.htm?q=&fq=online_visual_material%3Atrue&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=object_type%3A%22Isotypes%22&media.CC0=true&fq=tax_class:%22Pteridophyte%22"

"-c" defines a config.yml file that contains the specific info about the institutional unit, the location of their API endpoint, how to map those fields to Wikimedia Commons, and how to format the desired Commons filename. This is by far the hardest part of the process, but once someone has determined these mappings, future users can use this configuration file without needing too know all the details. A sample file can be found in "config-SAMPLE.yml"

"-b" – Defines a basename for all intermediate working files, which consist of <basename>.txt and <basename>.csv files. These are currently kept and not deleted when finished.

"-u" – Specifies the unit in the config.yml file to use as a basis for the uploads. This is a string that should match the one in the config file.

"-s" - Specifies the search URL that results in the listing of objects from the Smithsonian collections search interface. A script uses this URL and scrapes all the relevant Smithsonian resource IDs, which typically consist of unit name and accession number/unique number (e.g. saam_1921.1.1)

The script will kick off each of the scripts described below in succession. The user will see progress bars for each of the tools, showing estimated time remaining for each execution stage. The final stage will show actual uploads to Wikimedia Commons.

By default, the script places all uploads into a category called "Category:Wiki API Connector Upload" in addition to others the user can specify in the YAML file.


### Detailed invocation

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

 
## Caveats
* The examples here use the Smithsonian Institution Open Access API, which is hosted at Data.gov and requires use of an API key. Therefore, the code examples here will not work out of the box. They will require getting an API key (free), or you can find the DEMO_KEY from the Data.gov code examples which are free to use, but have a very low quota.

* Even with the full registered API key, there is a rate limit (as of 2023) of 1,000 API requests per hour which may impact the speed of ingestion depending on your working set. To avoid repeated hits against the API during a user's testing phase, the tools make extensive use of the requests-cache package, which saves the return values of requests to URLs for a number of days. This can be adjusted as needed and is best to have as a parameter from the configuration file in the future.
    * See: https://api.data.gov/docs/developer-manual/
    * Signup: https://api.data.gov/signup/

* This code uses jsonpath-ng to make creating configurations files easier for those who don't need to code. However, a major shortcoming is that if there is an error in parsing the JSON from a unit's API (ie. missing field) there is no safe way to fail, and the entire metadata generation fails. We will need to investigate different ways of handling this error, including a backup "safe" configuration that can be done to re-parse the JSON. Another option might be to actually extend/enhance json-path by going in and finding out which are the problem statements, and skipping those individually.

* While this works with wiki markup and Commons, in theory, this same framework could be extended to create Wikidata items, or do Wikibase/Wikidata edits.

## Contact
Andrew Lih (User:Fuzheado)

