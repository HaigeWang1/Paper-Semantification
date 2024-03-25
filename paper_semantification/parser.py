import requests as req
import re
import dblp
import os
from wikidata.client import Client
from dataclasses import dataclass
from typing import Optional, List
from bs4 import BeautifulSoup 
import string
from spellchecker import SpellChecker
from fuzzywuzzy import fuzz
import pandas as pd
import paper_semantification.parser_openai as openai
from paper_semantification.knowledge_graph.main import Neo4jConnection
from paper_semantification.knowledge_graph.utils import create_neo4j_graph, create_neo4j_graph_preface
from paper_semantification import NEO4J_URI
from email_validator import validate_email, EmailNotValidError
from ftfy import fix_text
import grobid_tei_xml
from xml.etree import ElementTree as ET
from unidecode import unidecode

import warnings
warnings.filterwarnings("ignore")


@dataclass
class Author:
    name: str
    affiliation: Optional[List[str]] = None
    email: Optional[List[str]] = None
    
    def __eq__(self, other):
        if isinstance(other, Author):
            return self.name == other.name and str(self.email) == str(other.email) and str(self.affiliation) == str(other.affiliation) 
        return False
  
# ### GROBID
    """
class GrobitFile():
    def __init__(self, filename):
        self.grobidxml = BeautifulSoup(req.get(filename).text, 'lxml')
        self._title = ''


    @property
    def title(self):
        if not self._title:
            self._title = self.grobidxml.title.getText().strip()
        return self._title


    @property
    def authors(self):
        try:

            authors_in_header = self.grobidxml.analytic.find_all('author')
        except:
            print('Grobid could not find any authors')
            return []
        result = []
        authors_list = []
        affs = []
        emails = []
        for author in authors_in_header:
            persname = author.persname
            affiliations = author.findAll('affiliation')

            if persname: 
                firstname = elem_to_text(persname.find("forename", type="first"))
                middlename = elem_to_text(persname.find("forename", type="middle"))
                surname = elem_to_text(persname.surname)
                name = ' '.join(list(filter(None, [firstname, middlename, surname])))
                authors_list.append(name)
                emails.append(elem_to_text(author.email))
        
                if affiliations:
                    aff_list = []
                    for affiliation in affiliations:
                        root = etree.fromstring(str(affiliation))
                        affiliation_text = ' '.join(root.xpath('.//text()'))
                        aff = ', '.join([aff.strip() for aff in affiliation_text.split('\n') if aff.strip() != ''])
                        aff_list += [strip_space_and_special_chars(aff)]
                    affs += [aff_list]
                else:
                    # if no affiliation is found, add empty list
                    affs += [[]]
            elif affiliations: 
                aff_list = []
                for affiliation in affiliations:
                    root = etree.fromstring(str(affiliation))
                    affiliation_text = ' '.join(root.xpath('.//text()'))
                    aff = ', '.join([aff.strip() for aff in affiliation_text.split('\n') if aff.strip() != ''])
                    aff_list += [strip_space_and_special_chars(aff)]
                affs += [aff_list]

        # assume affiliations are correctly assigned if the number of authors is the same as the number of affiliations
        for i in range(len(authors_list)):
            if True:
                author_name = authors_list[i]
                author_affiliation = affs[i] if affs[i] else []
                author_email = [emails[i]] if emails[i] else []
                
                # Put the strings through fix_text in order to solve potential encoding/decoding problems (e.g with german umlauts)
                author_name = fix_text(author_name)
                author_affiliation = [fix_text(aff_name) for aff_name in author_affiliation]
                
                author = Author(author_name, author_affiliation, author_email,aff_ok=True)
                result.append(author)
            else:
                author_name = authors_list[i]
                author_email = [emails[i]] if emails[i] else []
                
                # Put the strings through fix_text in order to solve potential encoding/decoding problems (e.g with german umlauts)
                author_name = fix_text(author_name)
                
                author = Author(author_name, [], author_email)
                result.append(author)

        return result
"""

class GrobitFile():
    def __init__(self, url):
        response = req.get(url)
        if response.status_code == 200:
            # Parse the XML content
            root = ET.fromstring(response.content)
            xml_content = ET.tostring(root, encoding='unicode')
            self.tei_xml = grobid_tei_xml.parse_document_xml(xml_content)

    @property
    def title(self):
        try:            
            paper_title = self.tei_xml.header.title
            return paper_title
        except:
            return ''


    @property
    def authors(self):
        try:
            author_list = []
            for author in self.tei_xml.header.authors:
                affiliation = []
                if author.affiliation:
                    if author.affiliation.address:
                        affiliation =  ', '.join([part for part in [author.affiliation.laboratory, author.affiliation.department, author.affiliation.institution,
                                                                author.affiliation.address.addr_line, author.affiliation.address.post_code, 
                                                                author.affiliation.address.settlement, author.affiliation.address.country] if part])
                    affiliation =  ', '.join([part for part in [author.affiliation.laboratory, author.affiliation.department, author.affiliation.institution] if part])
                author_list.append(Author(author.full_name, affiliation, author.email))
            return author_list
        except:
            return []
    
# ### CERMINE
class CermineFile():
    def __init__(self, filename):
        self.cermine = BeautifulSoup(req.get(filename).text, 'lxml')
        self._title = ''


    @property
    def title(self):
        if not self._title:
            self._title = elem_to_text(self.cermine.find('article-title')).strip()
        return self._title


    @property
    def authors(self):
        try:
            authors_in_header = self.cermine.find('article-meta').find('contrib-group').findAll('contrib')
        except:
            print('Cermine could not find any authors')
            return []
        
        result = []

        for author in authors_in_header:
            name = elem_to_text(author.find('string-name'))
            email = []
            for e in author.findAll('email'):
                email.append(elem_to_text(e))
            #email = elem_to_text(author.email)

            #xref_aff_ids = 'aff' + elem_to_text(author.xref)
            xref_aff = author.findAll('xref')
            xref_aff_id = ['aff' + elem_to_text(a) for a in xref_aff]
            affiliations = []
            for xref_id in xref_aff_id:
                aff_tag = self.cermine.find('article-meta').find('contrib-group').find('aff', {'id': xref_id})
                institutions = aff_tag.findAll('institution')
                addr = aff_tag.findAll('addr-line')
                countries = aff_tag.findAll('country')
                if aff_tag:
                    affl = []
                    if len(institutions) == len(addr):
                        if len(countries) != 0:
                                if len(countries) == len(institutions):
                                    for i in range(len(institutions)):
                                        affiliation = elem_to_text(institutions[i]) +  ', ' + elem_to_text(addr[i]) + ', ' + elem_to_text(countries[i])
                                        affl += [strip_space_and_special_chars(affiliation)]
                                elif len(countries) == 1:
                                    for i in range(len(institutions)):                                    
                                        affiliation = elem_to_text(institutions[i]) +  ', ' + elem_to_text(addr[i]) + ', ' + elem_to_text(countries[0])
                                        affl += [strip_space_and_special_chars(affiliation)]
                                else:
                                    for i in range(len(institutions)):
                                        affiliation = elem_to_text(institutions[i]) +  ', ' + elem_to_text(addr[i])
                                        affl += [strip_space_and_special_chars(affiliation)]
                        else:
                            for i in range(len(institutions)): 
                                affiliation = elem_to_text(institutions[i]) + ', ' +  elem_to_text(addr[i])
                                affl += [strip_space_and_special_chars(affiliation)]
                        affiliations += [(', ').join(affl)]
                   
                    elif len(addr)== 0:
                        if len(countries) != 0:
                                if len(countries) == len(institutions):
                                    for i in range(len(institutions)):
                                        affiliation = elem_to_text(institutions[i]) +  ', ' + elem_to_text(countries[i])
                                        affl += [strip_space_and_special_chars(affiliation)]
                                elif len(countries) == 1:
                                    for i in range(len(institutions)):                                    
                                        affiliation = elem_to_text(institutions[i]) +  ', ' + elem_to_text(countries[0])
                                        affl += [strip_space_and_special_chars(affiliation)]
                                else:
                                    for i in range(len(institutions)):
                                        affiliation = elem_to_text(institutions[i]) 
                                        affl += [strip_space_and_special_chars(affiliation)]
                        else:
                            for i in range(len(institutions)): 
                                affiliation = elem_to_text(institutions[i]) 
                                affl += [strip_space_and_special_chars(affiliation)]
                        affiliations += [(', ').join(affl)]

                    else:
                        for i in range(len(institutions)): #aff_tag.findAll('institution'):                                        
                            affiliation = elem_to_text(institutions[i]) 
                            affl += [strip_space_and_special_chars(affiliation)]
                        affiliations += [(', ').join(affl)]
                        
                else:
                    print(f"Author: {name}, Institution not found")
            
            # Put the strings through fix_text in order to solve potential encoding/decoding problems (e.g with german umlauts)
            name = fix_text(name)
            affiliations = [fix_text(aff_name) for aff_name in affiliations]
            
            author = Author(name, affiliations, email)
            result.append(author)

        return result
    
# Parsing proceedings and events using JSON
class JsonFile():
    def __init__(self, filename):
        self.json = filename.json()    
    @property
    def events(self):

        if "wd.eventLabel" in self.json.keys() and self.json["wd.eventLabel"]:
            self._events = self.json["wd.eventLabel"]
        else:
            self._events = ''
        return self._events

    @property
    def proceedings(self):
        if "wd.itemLabel" in self.json.keys() and self.json["wd.itemLabel"]:
            self._proceedings = self.json["wd.itemLabel"]
        else:
            self._proceedings =  ''
        return self._proceedings

    @property
    def eventSeries(self):
        if "wd.eventSeriesLabel" in self.json.keys() and self.json["wd.eventSeriesLabel"] != '':
            self._eventSeries = self.json["wd.eventSeriesLabel"]
            return self._eventSeries
        else:
            print("No event series found")
            return '' 

def get_eventsAndProceedings(jsonfile):
    result = { 'proceedings':jsonfile.proceedings,'event':jsonfile.events, 'event series': jsonfile.eventSeries}
    return result

def elem_to_text(elem = None):
    if elem:
        return elem.getText()
    return ''

def strip_space_and_special_chars(text):
    special_chars_list = [' ', ',', '-']
    res_text = text
    cur_text = text
    while True:
        for char in special_chars_list:
            cur_text = cur_text.strip(char)
        if cur_text == res_text:
            return res_text
        else:
            res_text = cur_text
           
def spell_check_correct(text):
    spell = SpellChecker()
    corrected_words = [spell.correction(word) if spell.correction(word) is not None else word for word in text.split()]
    corrected_sentence = ' '.join(corrected_words)
    return corrected_sentence

def get_cleaned_text(str_list):
    cleaned_list = []
    for s in str_list:
        for c in list(set(string.punctuation)):
                s = s.replace(c, '')
        cleaned_list.append(s)
    return cleaned_list

def issubset(l1, l2):
    list_1 = get_cleaned_text(l1)
    list_2 = get_cleaned_text(l2)

    for a in list_1:
        flag = False
        for b in list_2:
            # account for small deviations
            if fuzz.token_set_ratio(a, b) >= 70:
                flag = True
                break
        if not flag:
            return False
    return True

def approximate_lists(l1, l2):
    """
    Check if two lists are approximately the same.
    """
    flag = False
    for a in l1:
        for b in l2:
            if fuzz.token_set_ratio(a, b) >= 70:
                flag = True
        if not flag:
            return False
    return True

def check_email(email_adrs): 
    try: 
        for email in email_adrs:
            validate_email(email) 
        if email_adrs!= []:
            return True    
        else:
            return False
    except EmailNotValidError: 
        return False

def get_paper_title(title1: str, title2: str, pdf_path: str) -> str:
    if title1 == '':
        return title2
    elif title2 == '':
        return title1
    # use dblp for cross check
    dblp_result = pd.DataFrame() 
    if not dblp.search([title1]).empty:
        dblp_result = dblp.search([title1])
    elif not dblp.search([title2]).empty:
        dblp_result = dblp.search([title2])

    # account for spell errors 
    g_title = spell_check_correct(title1)
    c_title = spell_check_correct(title2)

    # consider version before spell errors as this might add another layer of inconsistence
    g_title2 = title1
    c_title2 = title2
    title_list = [g_title, c_title, g_title2, c_title2]

    # remove all spaces and special characters to have a more flexible comparison of the string values
    for t in title_list:    
        for c in list(set(string.punctuation).union(set([' ', '\n', '\t', '∗']))):
            t = t.replace(c, '')
    #merge title
    if not dblp_result.empty:
        if len(dblp_result) > 1:
            if not dblp_result[dblp_result['Link'].apply(lambda x: pdf_path in x)].empty:
                dblp_result = dblp_result[dblp_result['Link'].apply(lambda x: pdf_path in x)].reset_index()
        return dblp_result['Title'][0]
    elif title1.lower() == title2.lower():
        return title2
    elif g_title.lower() == c_title.lower() or g_title2.lower() == c_title2.lower():
        return g_title2
    elif g_title.lower() in c_title.lower() or title1.lower() in title2.lower() or g_title2.lower() in c_title2.lower():
        return  title1
    elif c_title.lower() in g_title.lower() or title2.lower() in title1.lower() or c_title2.lower() in g_title2.lower():
        return title2
    else:
        #check if string similarity is above a threshold ussing fuzzy matching
        if fuzz.token_set_ratio(title2, title1) > 85:
            #assign randomly to the cermine title
            return c_title
        else :
            return ''

def get_final_paper_title(grobid_title, cermine_title,  openai_title, pdf_path):
    merged_title = get_paper_title(grobid_title, cermine_title, pdf_path)
    final_title = get_paper_title(merged_title, openai_title, pdf_path)
    return final_title


def merge_author_info(aff_grobid, aff_cermine, email_grobid, email_cermine):
    #assign affiliations to each author
    if not aff_grobid:
        aff_author = aff_cermine
    elif not aff_cermine:
        aff_author = aff_grobid
    elif issubset(aff_grobid, aff_cermine):
        aff_author = aff_cermine
    elif issubset(aff_cermine, aff_grobid):
        aff_author = aff_grobid
    else:
        aff_author = aff_cermine

    # assign emails to each author
    if not email_cermine:
        email_author = email_grobid
    elif not email_grobid:
        email_author = email_cermine
    elif check_email(email_cermine):
        email_author = email_cermine
    elif check_email(email_grobid):
        email_author = email_grobid
    elif set(email_cermine).issubset(set(email_grobid)):
        email_author = email_grobid # take common email address
    elif set(email_grobid).issubset(set(email_cermine)):
        email_author = email_cermine # take common email address (check whether this works better like this or the other way around)
    else:
        email_author = email_cermine
    return(aff_author, email_author)


def get_author_info(grobid, cermine, openAI):                   
    #merge author information
    dblp_authors = []
    openAI_authors = []
    paper_authors_gr = []
    paper_authors_ce = []
    paper_authors = []
    #author name from openAI
    for e in openAI:
        openAI_authors.append(e['name'])

    # use dblp for cross check
    dblp_result = pd.DataFrame() 
    if not dblp.search([grobid.title]).empty:
        dblp_result = dblp.search([grobid.title])
    elif not dblp.search([cermine.title]).empty:
        dblp_result = dblp.search([cermine.title])

    if not dblp_result.empty:     
        dblp_authors = dblp_result['Authors'][0] 

    #check results from grobid      
    paper_authors_gr = {}
    if not dblp_result.empty: #len(dblp_authors) == len(grobid.authors):
        for a1 in dblp_authors:
            for a2 in grobid.authors:
                #only add correct names from dblp
                if fuzz.token_set_ratio(a1, a2.name) >= 80:
                    paper_authors_gr[a1] = Author(name = a1, affiliation=a2.affiliation, email = a2.email)
                    break
    #cross check the author name with openAI iff dblp entry is empty
    else:
        for a1 in openAI_authors:
            for a2 in grobid.authors:
                if fuzz.token_set_ratio(a1, a2.name) >= 80:
                    paper_authors_gr[a1] = Author(name = a1, affiliation=a2.affiliation, email = a2.email)
                else:
                    paper_authors_gr[a1] = Author(name = a1, affiliation=[], email = a2.email)
                break


    paper_authors_ce = {}
    if not dblp_result.empty: #len(dblp_authors) == len(cermine.authors):  -- not sure if we need this here, needs for validation
        for a1 in dblp_authors:
            for a2 in cermine.authors:
                #only add correct names from dblp
                if fuzz.token_set_ratio(a1, a2.name) >= 80:
                    paper_authors_ce[a1] = Author(name = a1, affiliation=a2.affiliation, email = a2.email)
                    break
    #cross check the author name with openAI iff dblp entry is empty
    else:
        for a1 in openAI_authors:
            for a2 in cermine.authors:
                if fuzz.token_set_ratio(a1, a2.name) >= 80:
                    paper_authors_ce[a1] = Author(name = a1, affiliation=a2.affiliation, email = a2.email)
                else:
                    paper_authors_ce[a1] = Author(name = a1, affiliation=[], email = a2.email)
                break

    aff_author = []
    email_author = ''
    aff_grobid = []
    aff_cermine = []
    email_grobid = ''
    email_cermine = ''
    aff_openAI = []
    email_openAI = ''


    if not dblp_result.empty:
        for a in dblp_authors:
            
            # check affiliation and email address from grobid and cermine
            if a in paper_authors_gr:
                aff_grobid = [paper_authors_gr[a].affiliation] if paper_authors_gr[a].affiliation != [] else []
                email_grobid = paper_authors_gr[a].email

            if a in paper_authors_ce:
                aff_cermine = paper_authors_ce[a].affiliation
                email_cermine = paper_authors_ce[a].email
            
            aff_author, email_author = merge_author_info(aff_grobid, aff_cermine, email_grobid, email_cermine)
            paper_authors.append(Author(name=a, affiliation=aff_author, email=email_author))



    else:
        #print('No dblp entry: merge results from cermine and grobid')
        #only possibility here is to automatically merge only in those cases when the authors are the same for both grobid and cermine, otherweise a manual check is required
        authors_gr = [a.name for a in grobid.authors]
        authors_ce = [a.name for a in cermine.authors]
        if len(authors_gr) != len(authors_ce):
            #print('Number of extracted authors is not the same while comparing grobid and cermine! We take the intersection of both lists')
            # take the intersection of both lists
            paper_authors = []
            authors_intersection = [a for a in authors_gr if a in authors_ce]
            for iter_author_name in authors_intersection:
                iter_author_grobid = [a for a in grobid.authors if a.name == iter_author_name][0]
                iter_author_cermine = [a for a in cermine.authors if a.name == iter_author_name][0]
                iter_aff_grobid = iter_author_grobid.affiliation
                iter_aff_cermine = iter_author_cermine.affiliation
                iter_email_grobid = iter_author_grobid.email
                iter_email_cermine = iter_author_cermine.email
                aff_author, email_author = merge_author_info(iter_aff_grobid, iter_aff_cermine, iter_email_grobid, iter_email_cermine)
                paper_authors.append(Author(name=iter_author_name, affiliation=aff_author, email=email_author))

        elif approximate_lists(authors_gr, authors_ce): # list of authors is (almost) the same
            author_info = []
            paper_authors = []
            for a in grobid.authors:
                for b in cermine.authors:
                    if fuzz.token_set_ratio(a.name, b.name) >= 70:
                        author_info.append((b.name, a.affiliation, b.affiliation, a.email, b.email))
                        
            for a_name, aff_grobid, aff_cermine, email_grobid, email_cermine in author_info:
                #merge results from cermine and grobid
                aff_author, email_author = merge_author_info(aff_grobid, aff_cermine, email_grobid, email_cermine)
                paper_authors.append(Author(name=a_name, affiliation=aff_author, email=email_author))
   
        
    #print('Crosschecking via openAI')
    tmp_paper_authors = []
    for a in paper_authors:
        name_author = a.name
        aff_author = a.affiliation
        email_author = a.email

        for b in openAI_authors:
            if fuzz.token_set_ratio(name_author, b) >= 80:
                tmp = list(filter(lambda person: person['name'] == b, openAI))[0]['email']
                if not tmp:
                    email_openAI = ''
                else:
                    email_openAI = tmp[0]
                aff_openAI = list(filter(lambda person: person['name'] == b, openAI))[0]['affiliation']

            #aff_author, email_author = merge_author_info_openAI(aff_grobid, aff_cermine,aff_openAI,email_grobid,email_cermine, email_openAI)
                aff_author, email_author = merge_author_info(aff_author,aff_openAI, email_author, email_openAI)
                tmp_paper_authors.append(Author(name=name_author, affiliation=aff_author, email= email_author))
                break # to skip remaining authors in the list
        tmp_paper_authors.append(Author(name=name_author, affiliation=aff_author, email= email_author))
    paper_authors = tmp_paper_authors
    return paper_authors

def calculate_similarity(row):
    return fuzz.token_set_ratio(row['Author Affiliations_exp'], row['Author Affiliations_act'])

def preprocess_df(expected_df, actual_df):
    pattern = r'([A-Za-z])\.'
    pattern_sp = r'[^a-zA-Z0-9\s]'
    expected_df['URL'] = expected_df['URL'].str.replace('https', 'http')
    # Replace the matched pattern with an empty string
    actual_df['Author name'] = actual_df['Author name'].str.replace(pattern, '', regex=True).str.strip().str.replace('  ', ' ').str.lower()
    expected_df['Author name'] = expected_df['Author name'].str.replace(pattern, '', regex=True).str.strip().str.replace('  ', ' ').str.lower()

    actual_df['Author name'] = actual_df['Author name'].apply(lambda x: unidecode(x))
    expected_df['Author name'] = expected_df['Author name'].apply(lambda x: unidecode(x))

    actual_df['Paper title'] = actual_df['Paper title'].str.replace('.', '').str.lower()
    expected_df['Paper title'] = expected_df['Paper title'].str.replace('.', '').str.lower()

    actual_df['Author Affiliations mod'] = actual_df['Author Affiliations'].str.replace('\n', '').str.lower().str.replace(pattern_sp, '', regex=True).str.replace(' ', '')
    expected_df['Author Affiliations mod'] = expected_df['Author Affiliations'].str.replace('\n', '').str.lower().str.replace(pattern_sp, '', regex=True).str.replace(' ', '')

    actual_df['Author E-Mail'] = actual_df['Author E-Mail'].str.lower()
    expected_df['Author E-Mail'] = expected_df['Author E-Mail'].str.lower()
    return expected_df, actual_df

def evaluate_results(expected_df, actual_df):
    expected_df, actual_df = preprocess_df(expected_df, actual_df)

    merged_df = pd.merge(expected_df, actual_df, on=['URL', 'Author name', 'Paper title'] , suffixes=('_exp', '_act'), how='left')

    test_no = merged_df['Paper title'].nunique()
    #1) author names and paper titles: exact matching
    score_1 = merged_df[merged_df['Proceedings_act'].notna()]['Paper title'].nunique()
    merged_df[merged_df['Proceedings_act'].isna()].to_csv('no_matches.csv', encoding='utf-8')
    print(f'Exact matching of paper titles and author names: {score_1} out of {test_no}')

    #2) exact matching of title, author names and email
    score_2 = merged_df[~((merged_df['Proceedings_act'] == merged_df['Proceedings_exp']) 
                        & ((merged_df['Author E-Mail_exp'] == merged_df['Author E-Mail_act']) |
                        (merged_df['Author E-Mail_exp'].isna() & merged_df['Author E-Mail_act'].isna())))]['Paper title'].nunique()
    print(f'Exact matching of title, names and emails: {test_no - score_2} out of {test_no}')

    #3) exact matching, all attributes
    score_3 = merged_df[~((merged_df['Proceedings_act'] == merged_df['Proceedings_exp']) 
                        & ((merged_df['Author E-Mail_exp'] == merged_df['Author E-Mail_act']) |
                        (merged_df['Author E-Mail_exp'].isna() & merged_df['Author E-Mail_act'].isna()))
                        & (merged_df['Author Affiliations mod_exp'] == merged_df['Author Affiliations mod_act']))]['Paper title'].nunique()
    print(f'Exact matching of all atts: {test_no - score_3} out of {test_no}')


    df = merged_df[(merged_df['Proceedings_act'] == merged_df['Proceedings_exp']) 
                        & ((merged_df['Author E-Mail_exp'] == merged_df['Author E-Mail_act']) |
                        (merged_df['Author E-Mail_exp'].isna() & merged_df['Author E-Mail_act'].isna()))]
    df['similarity_aff'] = df.apply(calculate_similarity, axis=1)

    # Filter rows where the similarity ratio is over 80
    result = df[df['similarity_aff'] < 80]['Paper title'].nunique()
    print(f'Exact matching of title, names and emails; app. matching of affiliations: {test_no - score_2-result} out of {test_no}')

def is_iterable(obj):
    try:
        iter(obj)
        return True
    except TypeError:
        return False
    
def parse_volumes(volumes: List[int] = None, all_volumes: bool = False, construct_graph = False, do_evaluation: bool = False) -> List:
    if not volumes and not all_volumes:
        raise ValueError("Either volumes or all_volumes must be specified")
    if all_volumes:
        print("Fetching all volumes from http://ceurspt.wikidata.dbis.rwth-aachen.de/index.html")
        Web = req.get('http://ceurspt.wikidata.dbis.rwth-aachen.de/index.html') 
        S = BeautifulSoup(Web.text, 'lxml') 
        html_txt = S.prettify()
        #extract all volumes
        reg1 = r'Vol-(\d+)">'
        #all volumes from the ceurspt api
        cur_volumes = re.findall(reg1, html_txt)
    elif volumes:
        cur_volumes = [str(v) for v in volumes]

    cur_volumes = [x for x in cur_volumes if x <= '3552']
    print(cur_volumes)
    if construct_graph:
        print("Setting up Neo4j connection")
        neo4j_conn = Neo4jConnection(uri=NEO4J_URI)  
        neo4j_conn.connect()
    else:
        neo4j_conn = None

    #extract all pages for each vol
    papers = {}
    events = {}
    for v in cur_volumes:
        url = 'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-' + v
        Web = req.get(url) 
        reg2 = rf'Vol-{v}/(.*?).pdf'
        #reg2 = r'paper(\d+).pdf' ##needs to be changed to reg2 = r'paper(\d+).pdf' to accound for more papers that do not follow this format.
        papers[int(v)] = sorted(list(set(re.findall(reg2, BeautifulSoup(Web.text, 'lxml').prettify()))))

    # remove contents that are not papers
    for v in cur_volumes:
        #papers[int(v)] =  [ele for ele in papers[int(v)] if 'paper' in ele or 'short'  in ele]
        papers[int(v)] =  [ele for ele in papers[int(v)] if 'preface' not in ele.lower() and 'index' not in ele.lower() and 'invited' not in ele.lower()] #'paper' in ele or 'short'  in ele]

    # parsing the events and proceedings as a nested dictionary using key = volume number, value = the json dictionary
    for v in cur_volumes:
        url = 'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-' + v + '.json'
        response = req.get(url)

        try:
            json_event = JsonFile(response)
        except:
            print('Json file could not get parsed correctly')
        events[int(v)] = get_eventsAndProceedings(json_event)

    
    data = []
       
    for k in papers.keys():
        for _, paper_key in enumerate(papers[k]):
            paper_path, paper_title, name, affiliation, email, proceeding, event = process_single_paper(k, paper_key, events, construct_graph, neo4j_conn)
            # Append author details to the data list
            data.append({'Proceedings':  proceeding, 'Event': event, 'Paper title': paper_title,
                            'Author name': name, 'Author Affiliations': affiliation, 'Author E-Mail': email, 'URL': f'{paper_path}.pdf'})
    
    if do_evaluation:
        df = pd.DataFrame(data)
        df.to_csv('actual_df.csv', index=False, encoding='utf-8')    
        df.reset_index(drop=True, inplace=True)
        expected_df = pd.read_excel("../test/Lab_test_set_402papers.xlsx")
        if not df.empty:
            evaluate_results(expected_df=expected_df, actual_df=df)

def process_single_paper(volume_id, paper_key, events: Optional[dict] = None, construct_graph = False, neo4j_conn = None):
    paper_path = f'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-{volume_id}/{paper_key}'
    path_pdf = paper_path + ".pdf"
    print(f'{paper_path}.pdf')
    grobid, cermine = None, None
    try:
        grobid =  GrobitFile(paper_path + '.grobid')
        grobid_title = grobid.title
    except:
        print('Grobid file could not get parsed correctly')
        grobid_title = ''
    try:
        cermine =  CermineFile(paper_path + '.cermine')
        cermine_title = cermine.title
    except:
        print('Cermine file could not get parsed correctly')
        cermine_title = ''

    try: 
        openAI = openai.OpenAIPapersParser()
        openAI_author = openAI.parse_authors(path_pdf)
        openAI_title = openAI.extract_title(path_pdf)
    except Exception as e:
        print(e)
        print('OpenAI could not get parsed correctly')
        openAI_author = []
        openAI_title = ''
    paper_title = ''
    author_list = []
    if cermine and grobid and openAI:
        paper_title = get_final_paper_title(grobid_title, cermine_title, openAI_title,  paper_path + ".pdf")
        author_list = get_author_info(grobid, cermine,openAI_author)
    elif grobid and openai:
        # TODOO: need merge function for only two components (grobid & cermine)
        paper_title = get_paper_title(grobid_title, openai.paper_title, paper_path + ".pdf")
        author_list = openai.paper_authors
    elif cermine:
        paper_title = cermine_title
        author_list = cermine.authors
    author_list_final = []
    for author in author_list:
        if author not in author_list_final:
            author_list_final.append(author)

    if events:
        proceeding = events[int(volume_id)]['proceedings']
        event = events[int(volume_id)]['event']
    else:
        proceeding = ''
        event = ''
    print(paper_title)
    print(author_list_final)
    if construct_graph:
        print(f"Creating graph for paper {paper_title}")
        create_neo4j_graph(author_list=author_list_final, title=paper_title, proceeding=proceeding, event=event, neo4j_connection=neo4j_conn, url=paper_path+'.pdf') 
    
    name = ""
    affiliation = ""
    email = ""
    proceeding = ""
    event = ""
    for author in author_list_final:
        # Extract author details
        name = author.name

        if isinstance(author.affiliation, list):
            affiliation = '; '.join(author.affiliation)
        elif author.affiliation:
            affiliation = author.affiliation
        else:
            affiliation = ''

        if isinstance(author.email, list):
            email = ', '.join(author.email)
        elif author.email:
            email = author.email
        else:
            email = ''
    return paper_path, paper_title, name, affiliation, email, proceeding, event


if __name__ == '__main__':
    construct_graph = False
    volumes = [2452]#3498, 3582, 3581, 3037, 3108, 2002, 3601, 3576, 2000, 2003, 2650, 2455, 2960, 2453, 2452, 2451, 2450 , 2344, 2456,2,1003]
   # volumes = 
    all_volumes = False
    # Set construct_graph to True to construct the graph. Otherwise the graph construction is skipped.
    parse_volumes(volumes=volumes, all_volumes=all_volumes, construct_graph=construct_graph)


