#!/bin/bash

FILEBASE='wac-session'
SEARCHURL="https://collections.si.edu/search/results.htm?media.CC0=true&q=&fq=data_source%3A%22NMNH+-+Entomology+Dept.%22&fq=online_visual_material%3Atrue&fq=place:%22Hawaii%22"

python si-collections-search-dumper.py \
    -o $FILEBASE.txt \
    $SEARCHURL

python wikiapiconnector-generator.py \
    -c config-smithsonian.yml \
    -i $FILEBASE.txt \
    -o $FILEBASE.csv \
    -u "Smithsonian National Museum of Natural History" 

python commons-upload-csv.py \
    $FILEBASE.csv 
