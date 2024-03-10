import requests as req
import re
import dblp
import os
import argparse
import orcid
import json
from wikidata.client import Client
from requests import RequestException
from lxml import etree
from dataclasses import dataclass
from typing import Optional, List
from bs4 import BeautifulSoup 
import string
from spellchecker import SpellChecker
from fuzzywuzzy import fuzz
import pandas as pd
from knowledge_graph.main import Neo4jConnection
from knowledge_graph.utils import create_neo4j_graph, create_neo4j_graph_preface
from email_validator import validate_email, EmailNotValidError
import warnings
from ftfy import fix_text
warnings.filterwarnings("ignore")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")


@dataclass
class Author:
    name: str
    affiliation: Optional[List[str]] = None
    email: Optional[List[str]] = None
    aff_ok: Optional[bool] = None
    
    def __eq__(self, other):
        if isinstance(other, Author):
            return self.name == other.name and str(self.email) == str(other.email) and str(self.affiliation) == str(other.affiliation) 
        return False
  
# ### GROBID
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
        aff_ok_is_set = False
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
                    aff_ok = True
                    aff_ok_is_set = True
                else:
                    # if no affiliation is found, add empty list
                    affs += [[]]
                    aff_ok = False
                    aff_ok_is_set = True
            elif affiliations: 
                aff_list = []
                for affiliation in affiliations:
                    root = etree.fromstring(str(affiliation))
                    affiliation_text = ' '.join(root.xpath('.//text()'))
                    aff = ', '.join([aff.strip() for aff in affiliation_text.split('\n') if aff.strip() != ''])
                    aff_list += [strip_space_and_special_chars(aff)]
                affs += [aff_list]
                aff_ok = False
                aff_ok_is_set = True

        # assume affiliations are correctly assigned if the number of authors is the same as the number of affiliations
        if len(authors_list) == len(affs):
            aff_ok = True
        elif not aff_ok_is_set:
            aff_ok = False
        for i in range(len(authors_list)):
            if aff_ok:
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
        self._events = self.json["wd.eventLabel"]
        return self._events
    @property
    def proceedings(self):
        self._proceedings = self.json["wd.itemLabel"]
        return self._proceedings
    @property
    def eventSeries(self):
        if self.json["wd.eventSeriesLabel"] != '':
            self._eventSeries = self.json["wd.eventSeriesLabel"]
            return self._eventSeries
        else:
            print("No event series found")
            return 
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
            valid = validate_email(email) 
        return True    
    except EmailNotValidError: 
        return False

def get_paper_title(grobid, cermine, pdf_path):
    
    # use dblp for cross check
    dblp_result = pd.DataFrame() 
    if not dblp.search([grobid.title]).empty:
        dblp_result = dblp.search([grobid.title])
    elif not dblp.search([cermine.title]).empty:
        dblp_result = dblp.search([cermine.title])

    # account for spell errors 
    g_title = spell_check_correct(grobid.title)
    c_title = spell_check_correct(cermine.title)

    # consider version before spell errors as this might add another layer of inconsistence
    g_title2 = grobid.title
    c_title2 = cermine.title
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
    elif grobid.title.lower() == cermine.title.lower():
        return cermine.title
    elif g_title.lower() == c_title.lower() or g_title2.lower() == c_title2.lower():
        return g_title2
    elif g_title.lower() in c_title.lower() or grobid.title.lower() in cermine.title.lower() or g_title2.lower() in c_title2.lower():
        return  grobid.title
    elif c_title.lower() in g_title.lower() or cermine.title.lower() in grobid.title.lower() or c_title2.lower() in g_title2.lower():
        return cermine.title
    else:
        #check if string similarity is above a threshold ussing fuzzy matching
        if fuzz.token_set_ratio(cermine.title, grobid.title) > 85:
            #assign randomly to the cermine title
            return c_title.title
        else :
            # TODO: need to decide what to do here
            print('Manual check needed!')
            return ''

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
        #TODO: manual check what to do this  
        # Example: http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-2452/paper8.pdf           
        print('Manual check is needed!')
        aff_author = []

    # assign emails to each author
    if not email_cermine:
        email_author = email_grobid
    elif not email_grobid:
        email_author = email_cermine
    elif set(email_cermine).issubset(set(email_grobid)):
        email_author = email_cermine # take common email address
    elif set(email_grobid).issubset(set(email_cermine)):
        email_author = email_grobid # take common email address
    elif check_email(email_grobid):
        email_author = email_grobid
    elif check_email(email_cermine):
        email_author = email_cermine
    else:
        #TODO: manual check what to do this
        print('Manual check is needed!')
        email_author = ''
    return(aff_author, email_author)

def get_author_info(grobid, cermine):                   
    #merge author information
    dblp_authors = []
    paper_authors_gr = []
    paper_authors_ce = []
    paper_authors = []
    
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
    if 1==1: #len(dblp_authors) == len(grobid.authors):
        for a1 in dblp_authors:
            for a2 in grobid.authors:
                #only add correct names from dblp
                if fuzz.token_set_ratio(a1, a2.name) >= 80:
                    if a2.aff_ok:
                        paper_authors_gr[a1] = Author(name = a1, affiliation=a2.affiliation, email = a2.email)
                    else:
                        paper_authors_gr[a1] = Author(name = a1, affiliation=[], email = a2.email)
                    break

    paper_authors_ce = {}
    if 1==1: #len(dblp_authors) == len(cermine.authors):  -- not sure if we need this here, needs for validation
        for a1 in dblp_authors:
            for a2 in cermine.authors:
                #only add correct names from dblp
                if fuzz.token_set_ratio (a1, a2.name) >= 80:
                    paper_authors_ce[a1] = Author(name = a1, affiliation=a2.affiliation, email = a2.email)
                    break

    aff_author = []
    email_author = ''
    aff_grobid = []
    aff_cermine = []
    email_grobid = ''
    email_cermine = ''
    if not dblp_result.empty:
        for a in dblp_authors:
            
            # check affiliation and email address from grobid and cermine
            if a in paper_authors_gr:
                aff_grobid = paper_authors_gr[a].affiliation
                email_grobid = paper_authors_gr[a].email

            if a in paper_authors_ce:
                aff_cermine = paper_authors_ce[a].affiliation
                email_cermine = paper_authors_ce[a].email
            
            aff_author, email_author = merge_author_info(aff_grobid, aff_cermine, email_grobid, email_cermine)
            paper_authors.append(Author(name=a, affiliation=aff_author, email=email_author))


    else:
        print('No dblp entry: merge results from cermine and grobid')
        #only possibility here is to automatically merge only in those cases when the authors are the same for both grobid and cermine, otherweise a manual check is required
        authors_gr = [a.name for a in grobid.authors]
        authors_ce = [a.name for a in cermine.authors]
        if len(authors_gr) != len(authors_ce):
            print('Number of extracted authors is not the same while comparing grobid and cermine! We take the intersection of both lists')
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
            for a in grobid.authors:
                for b in cermine.authors:
                    if fuzz.token_set_ratio(a.name, b.name) >= 70:
                        author_info.append((b.name, a.affiliation, b.affiliation, a.email, b.email))
                        
            for a_name, aff_grobid, aff_cermine, email_grobid, email_cermine in author_info:
                #merge results from cermine and grobid
                aff_author, email_author = merge_author_info(aff_grobid, aff_cermine, email_grobid, email_cermine)
                paper_authors.append(Author(name=a_name, affiliation=aff_author, email=email_author))

        else:            
            #TODO: decide what to do here?
            # I think its a better idea to take the authors from grobid here; cermine shows multiple problems 
            print('Manual check is needed! Number of extracted authors is not the same!')
            paper_authors = []

    print('paper_authors: \n', paper_authors, '\n', '-------------------')
    print('grobid.authors: \n', grobid.authors, '\n', '-------------------')
    print('cermine.authors: \n', cermine.authors, '\n')
    print('==================================================')
    return paper_authors

def parse_volumes(volumes: List[int] = None, all_volumes: bool = False, construct_graph = False) -> List:
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
        print(f"List of all volumes: {cur_volumes}")
    elif volumes:
        cur_volumes = [str(v) for v in volumes]

    if construct_graph:
        print("Setting up Neo4j connection")
        neo4j_conn = Neo4jConnection(uri=NEO4J_URI)  
        neo4j_conn.connect()  

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
        papers[int(v)] =  [ele for ele in papers[int(v)] if ('paper' or 'short')  in ele]
    
    # parsing the events and proceedings as a nested dictionary using key = volume number, value = the json dictionary
    for v in cur_volumes:
        url = 'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-' + v + '.json'
        response = req.get(url)

        try:
            json_event = JsonFile(response)
        except:
            print('Json file could not get parsed correctly')
        events[int(v)] = get_eventsAndProceedings(json_event)
    print("Events and proceedings:")
    print(events)
    
        
    for k in papers.keys():
        for idx, paper_key in enumerate(papers[k]):
            #if paper_key in ['inivited1', 'xpreface', 'paper3']:
            #    continue
            paper_path = f'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-{k}/{paper_key}'
            print(f'{paper_path}.pdf')

            try:
                grobid =  GrobitFile(paper_path + '.grobid')
            except:
                print('Grobid file could not get parsed correctly')
            
            try:
                cermine =  CermineFile(paper_path + '.cermine')
            except:
                print('Cermine file could not get parsed correctly')
                                
            # TODO: check why some titles are output 2 times for volumen 2451 e.g.
            paper_title = get_paper_title(grobid, cermine, paper_path + ".pdf")
            print(f'Parsed title: {paper_title}')
            author_list = []
            if paper_key != 'Preface':
                author_list = get_author_info(grobid, cermine)

            print('------------------------------------------------------')
            
            if construct_graph:
                print(f"Creating graph for paper {paper_title}")
                create_neo4j_graph(author_list,paper_title, neo4j_conn, paper_path+'.pdf') 



if __name__ == '__main__':
    construct_graph = False
    volumes = [2462]
    all_volumes = False
    # Set construct_graph to True to construct the graph. Otherwise the graph construction is skipped.
    parse_volumes(volumes=volumes, all_volumes=all_volumes, construct_graph=construct_graph)


