import requests as req
import re
import dblp
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
import create_knowledge_graph
from email_validator import validate_email, EmailNotValidError
import warnings
from ftfy import fix_text
warnings.filterwarnings("ignore")


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
        authors_in_header = self.grobidxml.analytic.find_all('author')
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
        authors_in_header = self.cermine.find('article-meta').find('contrib-group').findAll('contrib')
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
            if fuzz.token_set_ratio(a, b) >= 80:
                flag = True
                break
        if not flag:
            return False
    return True

def approximate_lists(l1, l2):
    flag = False
    for a in l1:
        for b in l2:
            if fuzz.token_set_ratio(a, b) >= 80:
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
            print('Manual check is needed! Number of extracted authors is not the same!')
            paper_authors = []
        elif approximate_lists(authors_gr, authors_ce): # list of authors is (almost) the same
            author_info = []
            for a in grobid.authors:
                for b in cermine.authors:
                    if fuzz.token_set_ratio(a, b) >= 80:
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

def main():
    Web = req.get('http://ceurspt.wikidata.dbis.rwth-aachen.de/index.html') 
      
    neo4j_conn = create_knowledge_graph.Neo4jConnection(uri="neo4j+s://607f3c00.databases.neo4j.io", user="neo4j", password="B4ciag8tPs_szFjyrAFWgz6INlti5_jJUCH9aqb8ETY")

    S = BeautifulSoup(Web.text, 'lxml') 
    html_txt = S.prettify()
    #extract all volumes
    reg1 = r'Vol-(\d+)">'
    #all volumes from the ceurspt api
    volumes = re.findall(reg1, html_txt)

    # Here we set the volume we want to consider in the comparisons below
    parser = argparse.ArgumentParser(prog='Web parser', description='Take a list of volume numbers as input and extract the papers')
    parser.add_argument('-v', '--volume', nargs='+', default=[], required=True,help='Volume numbers as integer')     
    args = parser.parse_args()
    cur_volumes = args.volume
    # cur_volumes = [f'{x}' for x in range(2456, 2458) if f'{x}' in volumes]
    assert(all([vol_nr in volumes for vol_nr in cur_volumes]))
    #extract all pages for each vol
    papers = {}
    for v in cur_volumes:
        url = 'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-' + v
        Web = req.get(url) 
        reg2 = rf'Vol-{v}/(.*?).pdf'
        #reg2 = r'paper(\d+).pdf' ##needs to be changed to reg2 = r'paper(\d+).pdf' to accound for more papers that do not follow this format.
        papers[int(v)] = sorted(list(set(re.findall(reg2, BeautifulSoup(Web.text, 'lxml').prettify()))))

    for k in papers.keys():
        for idx, paper_key in enumerate(papers[k]):
            if paper_key in ['inivited1', 'xpreface', 'paper3']:
                continue
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

            #create_knowledge_graph.create_neo4j_graph(author_list,paper_title, neo4j_conn, paper_path+'.pdf') 

    """  
    api = orcid.PublicAPI('APP-WNBUUWPD8MWY07XM', 'a5b8023a-cea1-4aa0-92f0-263c186d5556')
    search_token = api.get_search_token_from_orcid()

    work = api.read_record_public('0000-0002-8997-7517', 'activities', search_token)
    
    author_name = work['employments']['employment-summary'][0]['source']['source-name']['value']
    organization = work['employments']['employment-summary'][0]['organization']['name']
    print(author_name, organization)

    client = Client() 
    entity = client.get('Q57983801', load=True)
    print(f'Wikidata entity: {entity}')
    """

if __name__ == '__main__':
    main()


