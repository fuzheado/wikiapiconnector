# Wiki API Connector Tool (by Andrew Lih, User:Fuzheado on Wikipedia)
# 
# Utility for transferring images to Wikimedia Commons from an organization's API 
# The tool generates the proper Commons Template, license info and other metadata.

# Currently developed using Smithsonian API as a basis

# Configuration for a particular API is read from a config.yml file using JSONPath, 
#   so no coding should be needed to add additional APIs

# May need to install these depending on environment
#%pip install requests-cache
#%pip install jsonpath_ng

from dataclasses import dataclass, field, asdict
import yaml
import requests
import requests_cache
import json
import re
import os
import sys
from urllib.parse import urlparse, parse_qs
from io import StringIO
import csv
import pprint as pp
import pandas as pd
import pywikibot
from pywikibot.comms import http
from pywikibot.specialbots import UploadRobot

from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse

from typing import List, Dict
import logging

import argparse
import concurrent.futures

from tqdm import tqdm

commons_templates = {}

# TODO: Use
# https://commons.wikimedia.org/wiki/Template:Specimen

# TODO: eventually these should be pulled straight from Commons [[commons:Template...]]
commons_templates['Information']='''\
{{Information
 |description    = 
 |date           = 
 |source         = 
 |author         = 
 |permission     = 
 |other versions = 
}}'''

commons_templates['Artwork']='''\
=={{int:filedesc}}==
{{Artwork
 |artist             = 
 |author             = 
 |title              = 
 |description        = 
 |object type        = 
 |date               = 
 |medium             = 
 |institution        = 
 |department         = 
 |accession number   = 
 |place of creation  = 
 |place of discovery = 
 |object history     = 
 |exhibition history = 
 |credit line        = 
 |inscriptions       = 
 |notes              = 
 |references         = 
 |source             = 
 |permission         = 
 |other_versions     = 
 |wikidata           = 
 |other_fields       = 
}}'''

logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(levelname)s:%(message)s'  # Define the log message format
)

def extract_filename_without_extension(url: str) -> str:
    """
    Extracts a filename from a URL by parsing query parameters and removes the file extension.

    Args:
        url (str): The URL containing query parameters with a 'id' parameter representing the filename.

    Returns:
        str: The extracted filename without the file extension, or an empty string if 'id' is not found.
        
    Example:
        >>> extract_filename_without_extension("https://example.com/download?id=myfile.jpg")
        'myfile'
    """
    parsed_url = urlparse(url)     # Parse the URL to get the path component
    query_params = parse_qs(parsed_url.query)     # Extract the query parameters
    
    # Get the 'id' parameter and remove the ".jpg" extension
    if 'id' in query_params:
        fragment = os.path.splitext(query_params['id'][0])[0]
    else:
        logging.error("URL does not contain the 'id' parameter.")
        fragment = None

    return fragment

# SIunit class/dataclass (requires Python 3.7+)
#   Encapsulates all the info about a GLAM entity with a functioning API
#   The configuration should be read in from a YAML file, using the class method .from_yaml(file)

@dataclass
class SIunit:
    spec: dict = None  # Specification dictionary, as brought in by a YAML file or the like

    def __post_init__(self):
        requests_cache.install_cache('siapi_cache', backend='sqlite', expire_after=86400)

    def to_dict(self):
        return dict(self.spec)

    def to_string(self):
        return json.dumps(self.spec)

    @classmethod
    def from_yaml(cls, filename: str, organization_name: str):
        '''
        Functions as an alt-constructor: open a YAML file and bring in the org with proper name
        Parameters
        ----------
        filename: valid YAML file 
        organization_name: full string of "name" field in YAML file
        '''
        _incoming_dict = {}
        with open(filename, "r") as stream:
            try:
                _incoming_dict = dict(yaml.safe_load(stream))
            except yaml.YAMLError as exc:
                logging.error(exc) # TODO: raise properly
        try:
            for o in _incoming_dict['units']:
                if o['unit']['name'] == organization_name:
                    return cls(o['unit'])
        except IndexError as exc:
            logging.error(exc)  # TODO: raise proper error

        # TODO: should raise a not found exception
        return None
        
    @staticmethod
    def extract_template_field(wiki_template: str, field: str) -> str:
        '''
        Extract a particular field from a wiki template, passed in as a string
        '''
        _base_search_string = r'^\s*\|{}\s*=.*$'
        _search_string = _base_search_string.format(field)

        m = re.search(_search_string, wiki_template, re.MULTILINE)
        if m:
            match_string = m.group(0).split('=')[1].strip()
        return match_string

    @staticmethod
    def gen_url2commons_command(primary_img: str, template: str, wiki_title: str, autorun: bool = False) -> str:
        '''
        Returns a url2commons command given a URL and valid template
        '''
        # TODO - have a more robust way of crafting the filename on Commons
        url2commons_url = 'https://tools.wmflabs.org/url2commons/index.html'

        if not (primary_img and template): # Check to make sure both are valid
            return None
        # Craft the url2commons command to upload
        runstring = ''
        if autorun:
            runstring = '&run=1'
        quoted_url = urllib.parse.quote(str.replace(primary_img, '_', '%5F'))
        url2commons_command = url2commons_url + '?' + 'urls=' + quoted_url + '%20' + \
                              urllib.parse.quote(wiki_title) + \
                              runstring + '&desc=' + urllib.parse.quote(template)
        return url2commons_command

    @staticmethod
    def gen_wikibase_postdata(in_list: list, media_id: str = 'MISSING_MID', csrftoken: str = 'MISSING_TOKEN', summary: str = '') -> list:
        '''
        Returns a list of JSON dicts ready to be sent as POST data to Mediawiki API as wbcreateclaim statements

        Parameters
        ----------
        in_dict: dictionary of property/value pairs, such as:
        
        {'P4765': ['https://ids.si.edu/ids/download?id=SAAM-1916.8.1_1.jpg'], 
         'P275': 'Q6938433', 'P6216': 'Q88088423', 
         'P4704': ['19670'], 'P7851': ['saam_1916.8.1'], 
         'P9473': ['http://n2t.net/ark:/65665/vk7d0705dcb-a8b3-41ef-a91b-b6bd3e11fd8c']}

        mid: media ID of the Commons file, created by M + pageid
        csrftoken: CSRF token from API for authentication, like:
        https://commons.wikimedia.org/w/api.php?action=query&meta=tokens&type=csrf&format=json

        TODO: handle qualifiers in some way, right now it's simple P/Q or P/text statements
        
        Output
        ------
        list of JSON dicts ready to be sent as POST data to Mediawiki API as wbcreateclaim statements
        
        Ready for command:
        http.fetch(u'https://commons.wikimedia.org/w/api.php', method='POST', data=postdata)
        '''
        _return_list = []
        
        logging.debug ('in_list:', in_list)
        pp.pprint (in_list)
        for i in in_list:
            if not isinstance(i, dict):
                raise ValueError('gen_wikibase_postdata: found list item not a dict')
            pid = i['property']
            # print ('pid:', pid)
            # TODO: need more sophisticated handling if handed a list of statements
            if isinstance(i['value'], list):
                postvalue = i['value'][0]
            else:
                postvalue = i['value']

            # TODO: Weird bug is always setting P4765, need to figure out
            # TODO: in future have summary as a possible value
#             if 'summary' in i:
#                 summary = i['summary']
#             elif not summary:
#                 summary = 'added %s via Wiki API connector' % (pid, )

            summary = 'added %s via Wiki API connector' % (pid, )

            pid = i['property']
            # TODO: value check i['property']
            # TODO: value check i['value']
            # TODO: value check i['summary']
            
            _new_postdata = {  # Format needed for Mediawiki API call
                u'action' : u'wbcreateclaim',
                u'format' : u'json',
                u'entity' : media_id,
                u'property' : pid,
                u'snaktype' : u'value',
                u'value' : postvalue,
                u'token' : csrftoken,
                u'bot' : 1,
                u'summary' : summary
                }
            _return_list.append(_new_postdata)

        return _return_list

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Wikimedia Commons does not allow certain characters for filenames, so make the incoming name safe
        """
        # Define a mapping of forbidden characters and their alternatives
        char_mapping = {
            '#': '___',
            '<': '(',
            '>': ')',
            '[': '(',
            ']': ')',
            '|': '___',
            ':': '___',
            '{': '(',
            '}': ')',
            '/': '___',
            '.': '_',
        }
    
        # Replace forbidden characters with their alternatives
        sanitized_filename = filename
        for char, replacement in char_mapping.items():
            sanitized_filename = sanitized_filename.replace(char, replacement)
    
        # Replace sequences of tilde characters (~) with a single underscore (_)
        sanitized_filename = re.sub(r'~+', '_', sanitized_filename)
    
        # Remove leading underscores (if any)
        sanitized_filename = sanitized_filename.lstrip('_')
    
        return sanitized_filename

    def api_template(self) -> str:
        '''
        Return template for API call
        '''
        # TODO: check for existence
        _url = self.spec['api']['api_url']
        # TODO: check for existence
        _apikey = self.spec['api']['api_key_string']

        return _url.format('{}', _apikey)

    def api_lookup(self, incoming_id: str, output_type: str = 'raw') -> dict:
        '''
        Return content from API call
        '''
        _api_url = self.api_template().format(incoming_id)

        _result = requests.get(_api_url)
        if _result.status_code == 200:
            _oa_dict = dict(_result.json())
            return _oa_dict
        elif _result.status_code == 404:
            logging.error ('%s, status code %s' % (incoming_id, _result.status_code))
            return None
        else:
            raise ValueError('%s, status code %s' % (incoming_id, _result.status_code))

    @staticmethod
    def validate_filename_parameters(input_string: str) -> bool:
        """
        Validate whether the input string has the right words
        """
        # Split the input string into words using comma and space as separators
        words = input_string.split(", ")
    
        # Define a set of valid names
        valid_names = {"title", "identifier", "basefilename"}
    
        # Check if all words are valid names
        for word in words:
            if word.lower() not in valid_names:
                return False
    
        return True

    @staticmethod
    def generate_commons_filename(
        title: str,
        identifier: str,
        basefilename: str,
        order: list[str] = ['title', 'identifier', 'basefilename'],
        extension: str = "jpg") -> str:
        """
        Take in the parameters and the order defined by a list, to generate a Commons filename such as:
        "Guernica saam 1941.1.2 IMG1234.jpg"
        """
        # Create a dictionary to map variable names to their values
        variables = {
            "title": title,
            "identifier": identifier,
            "basefilename": basefilename,
        }
    
        # Initialize an empty list to store the selected values
        selected_values = []
    
        # Iterate through the order list and append the corresponding values
        for item in order:
            selected_values.append(variables.get(item, ""))
    
        # Join the selected values into a single string
        combined_string = " ".join(selected_values)

        # Append the extension to the combined string
        combined_string += '.' + extension
    
        return combined_string
    
    def fill_wiki_template(self, wiki_template: str, field_dict: dict) -> str:
        '''
        Fill in a Commons template using a dict with the keys matching the field names such as:
         |artist             = 
         |author             = 
         |title              = 
        Need to consult local crosswalk database, if it exists, for mapping things like:
            CC0 -> {{CC-zero}}

        Parameters
        ----------
        wiki_template: text of Template in wikimarkup
        field_dict: dict of keyword/value pairs that match the parameters of the Template

        Output
        ------
        Wiki template filled in
        '''

        base_search_string = r'^\s*\|{}\s*=\s*$'
        new_template = wiki_template

        for k in field_dict.keys():
            search_string = base_search_string.format(k)  # Form search regexp for template parameter
            # print (search_string)
            m = re.search(search_string, new_template, re.MULTILINE)
            if m:
                match_string = m.group(0)
                # Determine what to add to the template:
                #   Use item from dict as a list item zero, or assume it's a string
                # DEBUG
                # print ('field_dict: ', field_dict)
                try:
                    # Grab first element of list, though need to think about this more on how to handle list
                    # TODO
                    added_string = field_dict[k][0] if isinstance(field_dict[k], list) else field_dict[k]
                except IndexError as error:
                    # Output expected IndexErrors.
                    # Logging.log_exception(error)
                    # Handle an empty list
                    added_string = ''
                # TODO: lookup any crosswalk that needs to be done here, like CC0 -> {{cc-zero}}
                if added_string == 'CC0':
                    added_string = '{{Cc-zero}}' 
                # Append the value after the equals sign in the Template parameter
                new_string = match_string + ' ' + added_string
                # print ('new string: ', new_string)
                new_template = new_template.replace(match_string, new_string)

        # Add final parts of template, categories or otherwise from config
        new_template += self.spec['commons_template']['append']
        new_template += '\n\n'
        new_template += self.spec['commons_template']['categories']

        # print ('fill_wiki_template:', new_template)
        return new_template
    
    def id_to_commonswblist(self, incoming_id: str, wb_template_dict: dict) -> list:
        '''
        Return a list of Wikidata statements corresponding to add them to Wikibase
        
        Parameters
        ----------
        incoming_id: item identifier
        commons_template_dict: definition brought in from YAML file
            Probably most keys are Wikidata properties like P180
        
        Output
        ------
        list of dicts, format: [{'property': 'P3634', 'value': "1234"},
                                {'property': 'P180', 'value': : '{"entity-type": "item", "numeric-id": "12345"}' },
                                 ...
                                # TODO: Add a summary field perhaps?
        '''
        _return_list = []
        _outstring = ''

        _oa_dict = self.api_lookup(incoming_id)  # Get JSON/dict returned from API

        # Iterate over fields defined in YAML and look them up from JSON/dict returned from API
        # print ('wb_template_dict:', wb_template_dict)
        for i in wb_template_dict['statements']:
            _outstring += 'statement: ' + i
            _return_item = {}
            _return_item['property'] = i  # Should be Wikidata property, e.g. P180
            _return_item['value'] = ''    # To be filled in below
            # TODO: have a summary option

            # TODO: need to handle multiple instances of a property in the file
            tvar = wb_template_dict['statements'][i]  # Grab list of fields

            if isinstance(tvar, dict):
                # print ('  ', tvar.keys())
                matches = []
                if 'jsonpath' in tvar:
                    # print ("  jsonpath:", tvar['jsonpath'])
                    # TODO - make API call with that path
                    jsonpath_expr = parse(tvar['jsonpath'])
                    matches = [match.value for match in jsonpath_expr.find(_oa_dict)]
                    _outstring += '  ' + str(matches)
                    # TODO: handle a list of matches better
                    # TODO: handle if this is a Q number with entity-type
                    _return_item['value'] = matches
                    # next?
                if 'static' in tvar:
                    _outstring += '  static: ' + str(tvar['static'])
                    # If normal
                    instring = tvar['static']
                    # If entity-type is item
                    if 'entity-type' in tvar and tvar['entity-type'] == 'item':
                        jstring = {"entity-type":"item","numeric-id": instring.replace(u'Q', u'')}
                        postvalue = json.dumps(jstring)
                        _outstring += '    item: ' + postvalue
                    else: # Assume it is string, TODO: check claimtype == 'string'
                        postvalue = '"'+instring+'"'
                        _outstring += '    generic/string: ' + postvalue
                    _return_item['value'] = postvalue
                    pass
#                 if 'action' in tvar.keys():
#                     # TODO: process action like reconciliation
#                     # print ("  ", tvar['action'])
#                     _outstring += '  action: ' + str(tvar['action'])
#                     # TODO: handle the actions here
#                     pass
#                 if 'append' in tvar.keys():
#                     # print ("  ", tvar['static'])
#                     _outstring += '  append: ' + str(tvar['append'])
#                     # TODO: Need to handle this more elegantly in case there is a real list
#                     _return_dict[i] = _return_dict[i][0] + ' ' + tvar['append']
#                     pass
            _return_list.append(_return_item)
            _outstring += '\n'
        logging.debug (_outstring)
        # print (_return_dict)
        return _return_list

    def id_to_commonsdict(self, incoming_id: str, commons_template_dict: dict):
        '''
        Return a dict of keyword/value pairs corresponding to how to fill in the template
        
        Parameters
        ----------
        incoming_id: item identifier
        commons_template_dict: definition brought in from YAML file
            At a minimum, 'url' and 'fields' should be valid keys
        
        Output
        ------
        dict of format: {'title': ['Old Arrow Maker'], 'accession number': ['1983.95.182'], ...
        '''
        _return_dict = {}
        _outstring = ''

        try:
            _oa_dict = self.api_lookup(incoming_id)  # Get JSON/dict returned from API
        except ValueError:
            raise ValueError('id_to_commonsdict: %s' % (incoming_id,))

        if not _oa_dict:
            return None

        # Iterate over fields defined in YAML and look them up from JSON/dict returned from API
        for i in commons_template_dict['fields']:
            _outstring += 'field: ' + i
            tvar = commons_template_dict['fields'][i]  # Grab list of fields
            if isinstance(tvar, dict):
                # print ('  ', tvar.keys())
                matches = []
                if 'jsonpath' in tvar.keys():
                    # print ("  jsonpath:", tvar['jsonpath'])
                    # TODO - make API call with that path
                    logging.debug ('debug: ', tvar['jsonpath'])
                    jsonpath_expr = parse(tvar['jsonpath'])
                    matches = [match.value for match in jsonpath_expr.find(_oa_dict)]
                    # Use special formatting string
                    if matches and 'formatstring' in tvar.keys():
                        formatstring = tvar['formatstring']
                        # TODO: check for exception if bad format string
                        # TODO: check for just one element in matches
                        returnstring = formatstring % matches[0]
                    else:
                        returnstring = matches
                    _outstring += '  ' + str(returnstring)
                    _return_dict[i] = returnstring
                if 'action' in tvar.keys():
                    # TODO: process action like reconciliation
                    # print ("  ", tvar['action'])
                    _outstring += '  action: ' + str(tvar['action'])
                    # TODO: handle the actions here
                    pass
                if 'static' in tvar.keys():
                    # print ("  ", tvar['static'])
                    _outstring += '  static: ' + str(tvar['static'])
                    _return_dict[i] = tvar['static']
                    pass
                if 'append' in tvar.keys():
                    # print ("  ", tvar['static'])
                    _outstring += '  append: ' + str(tvar['append'])
                    # TODO: Need to handle this more elegantly in case there is a real list
                    _return_dict[i] = _return_dict[i][0] + ' ' + tvar['append']
                    pass
            _outstring += '\n'
        logging.debug (_outstring)
        # print (_return_dict)
        return _return_dict

    def api_crossformat(self, incoming_id: str, crossformat: str = 'commons_template') -> list:
        '''
        Crossformat out the API content into a format as specified
        
        Parameters
        ----------
        incmong_id: identifier
        format: 
          commons_template is usually desired, otherwise 
          commons_wikibase is for SDC
        
        Return
        ------
        A list of media/metadata pairs in a dict
        
        If 'commons_template' then a list of dicts:
        [{'title': 'Dog playing Poker', 'url': 'https://...', 'template': '...'}, {'url'... ]
        If 'commons_wikibase' then a list of dicts
        '''
        _newspec = self.to_dict()
        # print ('api_crossformat newspec:', _newspec)
        _return_list = []
        _return_dict = {}
        
        _outstring = incoming_id + '\n'
        if crossformat == 'commons_template':
            _object_dict = self.id_to_commonsdict(incoming_id, _newspec['commons_template'])

            if not _object_dict:
                return None

            # Set the name/title part of dict
            if 'title' in _object_dict:
                try:
                    _return_dict['title'] = _object_dict['title'][0]
                except IndexError:
                    logging.error ('IndexError:', incoming_id, 'object_dict:', _object_dict)
                    _return_dict['title'] = None
            else:
                _return_dict['title'] = None

            # Set the image part of dict
            if '_image' in _object_dict and _object_dict['_image']:
                _return_dict['url'] = _object_dict['_image'][0]
            else:
                logging.debug ("_object_dict['image'] is empty, skipping")
                _return_dict['url'] = None
    
            # Set the Commons template filled out
            # Grab this from config file
            commons_template_type = self.spec['commons_template']['type']
            # TODO: May want to download directly from Commons in the future
            commons_template_skeleton = commons_templates[commons_template_type]
            _filled_template = self.fill_wiki_template(commons_template_skeleton, _object_dict)

            if _filled_template:
                _return_dict['template'] = _filled_template
            else:
                _return_dict['template'] = None

            # TODO: In theory there could be a whole list of images returned for a given object
            _return_list.append(_return_dict)
            
        elif crossformat == 'commons_wikibase':
            # TODO: Suspect I can re-use the id_to_commonsdict by some slight rewrite
            _object_dict = self.id_to_commonswblist(incoming_id, _newspec['commons_wikibase'])
            _return_list.append(_object_dict)

        return _return_list

    def identifier_to_url2commons(self, identifier: str, autorun: bool = False) -> str:
        '''
        Take an identifier to the API and generate the url2commons command for it
        '''
        master_list = []
        u2c_command = None

        # Each call returns a dict in a list with 'url' and 'template' ready for url2commons use
        item_list = self.api_crossformat(identifier)
        # TODO: Handle a list and not just one
        # Craft filename: data['title'] + ' data['accessionNumber'] + '.jpg'
        if item_list:
            master_list += item_list
            item = item_list[0]  # Grab the parameter from list
            # TODO: line below gets the formatted title after formatstring which
            # is not what we likely want. We need the raw title string
            original_title = SIunit.extract_template_field(item['template'], 'title')

            # TODO - replace characters that Commons doesn't like
            commons_title = original_title.replace('[','(').replace(']',')')
            wiki_filename = '{}-{}.jpg'.format(commons_title,identifier)

            u2c_command = SIunit.gen_url2commons_command(item['url'], item['template'], wiki_filename, autorun)

        return u2c_command

    def identifier_to_commons_csv_entry(self, identifier: str) -> List[Dict[str, str]]:
        '''
        Take an identifier to the API and generate a CSV entry (or entries) of the crucial fields for Commons upload
        Example:

        record_id, source_image_url, commons_filename, edit_summary, description
        nmaahc_2018.59.3, https://ids.si.edu/ids/download?id=NMAAHC-2018_59_3_001.jpg, nmaahc-2018_116_8_001.jpg, "Upload from Smithsonian NMAAHC", "..."
        nmaahc_2018.59.3, https://ids.si.edu/ids/download?id=NMAAHC-2018_59_3_002.jpg, nmaahc-2018_116_8_002.jpg, "Upload from Smithsonian NMAAHC", "..."

        This can then be passed to a pywikibot upload command like the following.
        Note that the source_image_url may need to be checked for redirects and expanded.

        pwb -family:commons -lang:commons \
        upload.py -noverify -keep \
        -filename:<commons_filename> \
        -summary:"<edit summary>" \
        <source_image_url>
        -descfile:<`basename commons_filename`>.desc

        Expanded example:
        pwb -family:commons -lang:commons \
        upload.py -noverify -keep \
        -filename:nmaahc-2018_116_8_002.jpg \
        -summary:"Upload from Smithsonian NMAAHC" \
        https://smithsonian-open-access.s3-us-west-2.amazonaws.com/media/nmaahc/NMAAHC-2018_116_8_002.jpg \
        -descfile:nmaahc-2018_116_8_002.desc

        '''
        csv_values = []  # List of dicts that return the rows of the CSV

        # Want to fill each of these: 
        #   record_id, source_image_url, commons_filename, edit_summary, description
        
        # Each call returns a dict in a list with 'url' and 'template' ready for Commons use
        logging.debug('starting: ', identifier)
        item_list = self.api_crossformat(identifier)
        
        # TODO: Handle a list and not just one
        for item in item_list if item_list is not None else []:
            csv_entry = {}
            csv_entry['record_id'] = identifier

            # TODO - fix this for the CSV so filename is more meaningful
            # original_title = SIunit.extract_template_field(item['template'], 'title')

            # TODO - replace characters that Commons doesn't like
            # commons_title = original_title.replace('[','(').replace(']',')')

            #TODO handle case of None for basefilename
            if item['url']:
                csv_entry['source_image_url'] = item['url']

                # If https://ids.si.edu..../SAAM-1234.jpg
                #   Extract: SAAM-1234
                logging.debug('url: ', item['url'])
                basefilename = extract_filename_without_extension(item['url'])
                logging.debug('basefilename: ', basefilename)

                # Clean title for Commons compliance
                # Remove # < > [ ] | : { } / . and sequences of tilde characters (~~~)
                if item['title']:
                    title = SIunit.sanitize_filename(item['title'])
                else:
                    title = 'Unknown'
                
                # Grab commons_filename_format parameter from YAML
                # Valid values title, identifier, basename
                commons_filename_format = self.spec['commons_template']['commons_filename_format']

                # Validate the commons_filename_format                
                commons_filename_order = [word.strip() for word in commons_filename_format.split(",")]

                csv_entry['commons_filename'] = SIunit.generate_commons_filename (title, identifier, basefilename, commons_filename_order, 'jpg')

                # csv_entry['commons_filename'] = '{}_{}_{}.jpg'.format(title, identifier, basefilename)
            else:
                logging.debug('Warning, no URL found at API')
                csv_entry['source_image_url'] = ''
                csv_entry['commons_filename'] = ''

            # TODO: Grab this from config file
            csv_entry['edit_summary'] = 'Uploaded by Wiki API Connector'
            csv_entry['description'] = item['template']

            # Convert dictionary values to CSV format
            csv_values.append(csv_entry)

        return csv_values

    def identifier_to_wbcreateclaims(self, identifier: str) -> list:
        '''
        Take an identifier to the API and generate a list of wikibase statements
        '''
        _return_list = []
        u2c_command = None

        # Each call returns a dict in a list with 'url' and 'template' ready for url2commons use
        item_list = self.api_crossformat(identifier, crossformat='commons_wikibase')

        # (in_dict: dict, media_id: str = 'MISSING_MID', csrftoken: str = 'MISSING_TOKEN', summary: str = '') -> list:
  
        for i in item_list:
            _return_list.append(self.gen_wikibase_postdata(i))
        
        # TODO: Handle a list and not just one
        # Craft filename: data['title'] + ' data['accessionNumber'] + '.jpg'
        # TODO: Optionally, execute the commands

        return _return_list

    @staticmethod
    def addClaimByDict(claims_dict: dict, destination_wiki='commons', test_mode=False) -> int:
        """addClaimByDict - add a Wikibase claim to Commons

        claims_dict: ready to go JSON with wbcreateclaim as the action
        """
        if not destination_wiki == 'commons':
            raise ValueError('Destination wiki for pywikibot not implemented yet:', destination_wiki)

        # site = pywikibot.Site(u'commons', u'commons')
        site = pywikibot.Site(u'test', u'commons')

        pywikibot.output(u'addClaimByDict: %s' % (claims_dict,))

        # Check for existing entry - if it exists at all, skip and honor existing entry
        pywikibot.output(u'  Checking: %s' % claims_dict['entity'])
        request = site._simple_request(action='wbgetentities',ids=claims_dict['entity'])
        data = request.submit()

        # Check in case there are no SDC statements, or existing pid statement
        try:
            if (data.get(u'entities').get(claims_dict.entity).get(u'statements').get(claims_dict.property)):
                pywikibot.output(u'  Existing entry: skipping to be safe.')
                return 0  # Skip
        except AttributeError:
            pass  # TODO: need better error handling here

        if claims_dict['token'] == 'MISSING_TOKEN':
            # Acquire authentication token for Mediawiki
            tokenrequest = http.fetch(u'https://test-commons.wikimedia.org/w/api.php?action=query&meta=tokens&type=csrf&format=json')

            tokendata = json.loads(tokenrequest.text)
            token = tokendata.get(u'query').get(u'tokens').get(u'csrftoken')
            claims_dict['token'] = token

        # pywikibot.output(u'  Error: improper claimtype passed %s' % (claimtype,))

        pywikibot.output(u'addClaimByDict FILLED: %s' % (claims_dict,))

        if test_mode:
            pywikibot.output('TEST_MODE: addClaimByDict: %s' % (claims_dict,))
            pass
        else:
            apipage = http.fetch(u'https://test-commons.wikimedia.org/w/api.php', method='POST', data=claims_dict)
            if not apipage.ok:
                pywikibot.output('  Error http status code %s: %s %s' % (apipage.status_code, claimtype, postdata))
                return -2

        return 1  # Successful add

#     @staticmethod
#     def upload_to_commons(site):

    def test_identifiers(self, idlist: list) -> None:
        """
        Test out genereating entries for a particular unit, pass in list of identifiers
        """
        for identifier in idlist:
            csvrowlist = self.identifier_to_commons_csv_entry(identifier)
            for row in csvrowlist:
                # Each row is a dict, so print it like a JSON structure
                print(json.dumps(row, indent=4))
                # record_id, url, filename, edit_summary, description = csvrow
                # print ('{record_id}, {url}, {filename}, {description}')
        return

    @staticmethod
    def test_si_unit(configfile: str, unitname: str, idlist: list) -> None:
        """
        Test out genereating entries for a particular unit, pass in list of identifiers
        Example: 'config.yml', 'Smithsonian American Art Museum', [saam_1923.1, saam_1922.5]
        """
        si_unit = SIunit.from_yaml(configfile, unitname)
        si_unit.test_identifiers(idlist) if idlist else logging.error("idlist is empty, cannot proceed.")

        return

def run_test_saam():
    """
    Test Smithsonian American Art Museum
    """
    saamidlist = [
        'saam_1929.6.127',   # painting
        'saam_1906.9.18',    # painting
        'saam_1983.95.179',  # sculpture
        'saam_1974.88.10',
        'saam_1967.39.2',
        'saam_1983.95.179',  # Old Arrow Maker
        'saam_1916.8.1',     # The Dying Tecumseh
    ]
    SIunit.test_si_unit('config-smithsonian.yml', 'Smithsonian American Art Museum', saamidlist)

def run_test() -> None:
    """
    Runs a series of tests on identifiers
    """
    
    testids = '''\
    nmnhbotany_2546215
    nmnhbotany_14852557
    nmnhbotany_14342425
    nmnhbotany_13710783
    nmnhbotany_13830928
    nmnhbotany_15406983
    nmnhbotany_15428938
    nmnhbotany_12449951
    nmnhbotany_12526151
    '''

    # Define a regular expression pattern to match valid lines
    pattern = r'^[a-zA-Z0-9_]+$'

    # Convert lines into a list of strings, excluding invalid lines
    testidlist = [line.strip() for line in testids.splitlines() if re.match(pattern, line.strip())]

    SIunit.test_si_unit('config-smithsonian.yml', 'Smithsonian National Museum of Natural History', testidlist)
    return


def process_identifiers(identifiers, config_file, unit_string, output_file) -> None:
    # Your processing logic goes here
    logging.info(f"Configuration file: {config_file}\n")
    logging.info(f"Unit string: {unit_string}\n")

    si_unit = SIunit.from_yaml(config_file, unit_string)
    if not si_unit:
        logging.error('Creating unit failed')
        sys.exit(1)
        
    csv_master_list = []  # List of dicts
    with tqdm(total=len(identifiers), desc="Processing") as pbar:
        for identifier in identifiers:
            logging.debug(f"Processing: {identifier}\n")
            csv_entries = si_unit.identifier_to_commons_csv_entry(identifier)
            if not csv_entries:
                logging.error('No valid identifier_to_commons_csv_entry result for', identifier)
            else:
                csv_master_list.extend(csv_entries)
            pbar.update(1)

    output_stream = sys.stdout if output_file is None else open(output_file, 'w')

    if csv_master_list:
        logging.debug ('Processing csv_master_list')
        example_dict = csv_master_list[0] # Example item for creating field names
        csv_writer = csv.DictWriter(output_stream, fieldnames=example_dict.keys())
        csv_writer.writeheader()
        csv_writer.writerows(csv_master_list)
    
    if output_file is not None:
        output_stream.close()        

def main():
    # Create an ArgumentParser
    parser = argparse.ArgumentParser(description="Process a list of identifiers")

    # Add the positional argument for identifiers (accepts multiple values)
    parser.add_argument("identifiers", nargs="*", metavar="IDENTIFIER", help="List of identifiers")

    # Add optional command line options
    parser.add_argument("-c", "--config", dest="config_file", help="Configuration file in YAML format")
    parser.add_argument("-u", "--unit", dest="unit_string", help="Unit string, name of entity in config file")
    parser.add_argument("-o", "--output", dest="output_file", help="Output file (default is stdout)")
    parser.add_argument("-i", "--input", dest="input_file", help="Input file with identifiers (one per line)")

    # Parse the command line arguments
    args = parser.parse_args()

    # Check if -c and -u options are set; display usage message and quit if not set
    if not args.config_file or not args.unit_string:
        parser.print_usage()
        logging.error('Need to define -c and -u parameters')
        sys.exit(1)

    # If an input file is provided, read identifiers from the file
    if args.input_file:
        with open(args.input_file, 'r') as input_file:
            # TODO: Some basic data validation here
            identifiers = [line.strip() for line in input_file]
    else:
        # Read identifiers from command line arguments or standard input
        if args.identifiers:
            # If identifiers are provided as command line arguments, split them by spaces or newlines
            identifiers = [item for arg in args.identifiers for item in arg.split()]
        else:
            # Prompt the user to enter identifiers, separated by spaces or newlines
            print("Enter identifiers, separated by spaces or newlines (press Enter after each):")
            identifiers = []
            while True:
                try:
                    input_line = input()
                    if not input_line:
                        break
                    identifiers.extend(input_line.split())
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break

    # Call the process_identifiers function with the provided arguments
    process_identifiers(identifiers, args.config_file, args.unit_string, args.output_file)

if __name__ == "__main__":

    # Install a cache for faster testing
    # requests_cache.install_cache('si_scraper_cache')
    
    # Set debugging level
    logging.getLogger().setLevel(logging.INFO)

    # run_test()
    # run_test_saam()
    main()
    
    # TODO: Add category for the file upload
    # TODO: Add Wikidata SDC info for metadata
    # TODO: Grab the resulting filename
    # TODO: Try pywikibot upload and adding template manually