
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


si-collections-search-dumper.py
    "https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22"
    -o kelantan.txt

wikiapiconnector-generator.py 
    -c config-smithsonian.yml 
    -u "Smithsonian National Museum of Natural History" 
    -i kelantan.txt 
    -o kelantan-csv.txt

commons-upload-csv.py
    kelantan.csv 


Example searches:

https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=place%3A%22Malaysia%22&fq=data_source%3A%22NMNH+-+Botany+Dept.%22&fq=place%3A%22Kelantan%22

python wikiapiconnector-generator.py -c config-smithsonian.yml -u "Smithsonian National Museum of Natural History" -i kelantan.txt -o kelantan-csv.txt

python commons-upload-csv.py  kelantan.csv 

