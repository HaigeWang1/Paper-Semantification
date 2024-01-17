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
from neo4j import GraphDatabase
import pandas as pd


@dataclass
class Author:
    name: str
    affiliation: Optional[List[str]] = None
    email: Optional[List[str]] = None
    #aff_ok: Optional[bool] = None
    
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
            #self._title = elem_to_text(self.grobidxml.find('title')).strip()
        return self._title
  

    @property
    def authors(self):
        authors_in_header = self.grobidxml.analytic.find_all('author')
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
                name = ''
                if middlename != '':
                    name = firstname + ' ' + middlename + ' ' + surname
                else:
                    name = firstname + ' ' + surname

                authors_list.append(name)
                emails.append(elem_to_text(author.email))
        
                if len(affiliations) != 0:
                    aff_list = []
                    for affiliation in affiliations:
                        root = etree.fromstring(str(affiliation))
                        affiliation_text = ' '.join(root.xpath('.//text()'))
                        aff = ', '.join([aff.strip() for aff in affiliation_text.split('\n') if aff.strip() != ''])
                        aff_list += [aff.strip()]
                    affs += [aff_list]

            elif len(affiliations) != 0: 
                aff_list = []
                for affiliation in affiliations:
                    root = etree.fromstring(str(affiliation))
                    affiliation_text = ' '.join(root.xpath('.//text()'))
                    aff = ', '.join([aff.strip() for aff in affiliation_text.split('\n') if aff.strip() != ''])
                    aff_list += [aff.strip()]
                affs += [aff_list]
        for i in range(min(len(authors_list), len(affs))):
            author_name = authors_list[i]
            author_affiliation = affs[i] if affs[i] else []
            author_email = [emails[i]] if emails[i] else []
            author = Author(author_name, author_affiliation, author_email)
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
                                        affiliation = elem_to_text(institutions[i]) +  ' ' + elem_to_text(addr[i]) + ' ' + elem_to_text(countries[i])
                                        affl += [affiliation.strip()]
                                elif len(countries) == 1:
                                    for i in range(len(institutions)):                                    
                                        affiliation = elem_to_text(institutions[i]) +  ' ' + elem_to_text(addr[i]) + ' ' + elem_to_text(countries[0])
                                        affl += [affiliation.strip()]
                                else:
                                    for i in range(len(institutions)):
                                        affiliation = elem_to_text(institutions[i]) +  ' ' + elem_to_text(addr[i])
                                        affl += [affiliation.strip()]
                        else:
                            for i in range(len(institutions)): 
                                affiliation = elem_to_text(institutions[i]) + ' ' +  elem_to_text(addr[i])
                                affl += [affiliation.strip()]
                        affiliations += [(', ').join(affl)]
                   
                    elif len(addr)== 0:
                        if len(countries) != 0:
                                if len(countries) == len(institutions):
                                    for i in range(len(institutions)):
                                        affiliation = elem_to_text(institutions[i]) +  ' ' + elem_to_text(countries[i])
                                        affl += [affiliation.strip()]
                                elif len(countries) == 1:
                                    for i in range(len(institutions)):                                    
                                        affiliation = elem_to_text(institutions[i]) +  ' ' + elem_to_text(countries[0])
                                        affl += [affiliation.strip()]
                                else:
                                    for i in range(len(institutions)):
                                        affiliation = elem_to_text(institutions[i]) 
                                        affl += [affiliation.strip()]
                        else:
                            for i in range(len(institutions)): 
                                affiliation = elem_to_text(institutions[i]) 
                                affl += [affiliation.strip()]
                        affiliations += [(', ').join(affl)]

                    else:
                        for i in range(len(institutions)): #aff_tag.findAll('institution'):                                        
                            affiliation = elem_to_text(institutions[i]) 
                            affl += [affiliation.strip()]
                        affiliations += [(', ').join(affl)]
                        
                else:
                    print(f"Author: {name}, Institution not found")
                
            author = Author(name, affiliations, email)
            result.append(author)

        return result

# Neo4j database connection
    
class Neo4jConnection:
    def __init__(self, uri, user, password):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = None

    def close(self):
        if self._driver is not None:
            self._driver.close()

    def connect(self):
        self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))

    def query(self, query, parameters=None, db=None):
        assert self._driver is not None, "Driver not initialized!"
        session = self._driver.session(database=db) if db is not None else self._driver.session()
        result = list(session.run(query, parameters))
        session.close()
        return result
  
def elem_to_text(elem = None):
    if elem:
        return elem.getText()
    return ''

def spell_check_correct(text):
    spell = SpellChecker()
    corrected_words = [spell.correction(word) if spell.correction(word) is not None else word for word in text.split()]
    corrected_sentence = ' '.join(corrected_words)
    return corrected_sentence

 
def are_equal_list_authors(list1: List[Author], list2: List[Author]):
    if len(list1) != len(list2):
        return False
    for author in list1:
        if not any([author == a2 for a2 in list2]):
            return False
    for author in list2:
        if not any([author == a1 for a1 in list1]):
            return False
    return True
        

def create_neo4j_graph_preface(event, preface, author_list,neo4j_connection, url):
    neo4j_connection.connect()

    create_event_query = "CREATE (:Event {event: $event, url: $url})"
    neo4j_connection.query(create_event_query, {"event": event, "url": url})  # Replace with actual URL

    create_preface_query = "CREATE (:Preface {preface: $preface, url: $url})"
    neo4j_connection.query(create_preface_query, {"preface": preface, "url": url})  # Replace with actual URL

    create_relationship_query = "MATCH (e:Event {event: $event}), (p:Preface {preface: $preface}) CREATE (a)-[:HAS]->(p)"
    neo4j_connection.query(create_relationship_query, {"event": event, "preface": preface})

    for author in author_list.authors:
        create_author_query = "CREATE (:Author {name: $name, email: $email, affiliation: $affiliation})"
        neo4j_connection.query(create_author_query, {"name": author.name, "email": author.email, "affiliation": author.affiliation})
        create_relationship_query = "MATCH (a:Author {email: $email}), (p:Preface {title: $title}) CREATE (a)-[:CONTAINS]->(p)"
        neo4j_connection.query(create_relationship_query, {"email": author.email, "title": preface})


    neo4j_connection.close()


# Define a function to create nodes and relationships in Neo4j
def create_neo4j_graph(author_list, title, neo4j_connection, url):
    neo4j_connection.connect()
    
    # Create Paper nodes
    create_paper_query = "MERGE (:Paper {title: $title, url: $url})"
    neo4j_connection.query(create_paper_query, {"title": title, "url": url})  # Replace with actual URL

    # Create Author nodes
    for author in author_list:
        # Create Author nodes
        create_author_query = "MERGE (:Author {name: $name, email: $email})"
        neo4j_connection.query(create_author_query, {"name": author.name, "email": author.email})
        
        # Create Affiliation nodes
        create_aff_query = "MERGE (:Affiliation {affiliation: $affiliation})"
        neo4j_connection.query(create_aff_query, {"affiliation": author.affiliation})

         # Create relationships between Authors and Affiliations
        create_author_aff_query = "MATCH (a:Author {email: $email}), (aff:Affiliation {affiliation: $affiliation}) MERGE (a)-[:AFFILIATED_WITH]->(aff)"
        neo4j_connection.query(create_author_aff_query, {"email": author.email, "affiliation": author.affiliation})      

    
        # Create relationships between Authors and Papers
        create_author_paper_query = "MATCH (a:Author {email: $email}), (p:Paper {title: $title}) MERGE (a)-[:AUTHORED]->(p)"
        neo4j_connection.query(create_author_paper_query, {"email": author.email, "title": title})

     
    neo4j_connection.close()

def compare_title(grobid, cermine, pdf_path):
    # use dblp for cross check
    dblp_result = pd.DataFrame() 
    if not dblp.search([grobid.title]).empty:
        dblp_result = dblp.search([grobid.title])
    elif not dblp.search([cermine.title]).empty:
        dblp_result = dblp.search([cermine.title])

    #account for spell errors 
    g_title1 = spell_check_correct(grobid.title)
    c_title1 = spell_check_correct(cermine.title)

    # also consider version before spell errors as this might add another layer of inconsistence
    g_title2 = grobid.title
    c_title2 = cermine.title
    title_list = [g_title1, c_title1, g_title2, c_title2]

    # remove all spaces and special characters to have a more flexible comparison of the string values
    for c in list(set(string.punctuation).union(set([' ', '\n', '\t', '∗']))):
        for t in title_list:    
            t = t.replace(c, '')

    #merge title and find if the titles are the same or almost same or partial same
    paper_title = ''
    
    if not dblp_result.empty:
        if len(dblp_result) > 1:
            if not dblp_result[dblp_result['Link'].apply(lambda x: pdf_path in x)].empty:
                dblp_result = dblp_result[dblp_result['Link'].apply(lambda x: pdf_path in x)].reset_index()
        paper_title = dblp_result['Title'][0]
        return paper_title
    elif grobid.title.lower() == cermine.title.lower():
        print(f'Same titles: {cermine.title}')
        return cermine.title
    elif g_title1.lower() == c_title1.lower() or g_title2.lower() == c_title2.lower():
        print(f'Almost same titles: {grobid.title}')
        return g_title2
    elif g_title1.lower() in c_title1.lower() or grobid.title.lower() in cermine.title.lower() or g_title2.lower() in c_title2.lower():
        print(f'Partial title: {grobid.title} is part of {cermine.title}')
        return grobid.title
    elif c_title1.lower() in g_title1.lower() or cermine.title.lower() in grobid.title.lower() or c_title2.lower() in g_title2.lower():
        print(f'Partial title: {cermine.title} is part of {grobid.title}')
        return cermine.title
    else:
        #check if string similarity is above a threshold ussing fuzzy matching
        if fuzz.ratio(cermine.title, grobid.title) > 80:
            return cermine.title
        else :
            # TODO: need to decide what to do here
            print('Titles not the same: COME UP with solution on how to resolve the conflicts')
            print(cermine.title, '\n', grobid.title, '\n')

def compare_author(grobid, cermine):
    dblp_authors = []
    paper_authors_gr = []
    paper_authors_ce = []
    paper_authors = []
    
    dblp_result = pd.DataFrame() 
    if not dblp.search([grobid.title]).empty:
        dblp_result = dblp.search([grobid.title])
    elif not dblp.search([cermine.title]).empty:
        dblp_result = dblp.search([cermine.title])

    if not dblp_result.empty:          
        dblp_authors = dblp_result['Authors'][0]      
        #check results from grobid
        
        if len(dblp_authors) == len(grobid.authors):
            for a1 in dblp_authors:
                for a2 in grobid.authors:
                    #only add correct names from dblp
                    if fuzz.ratio(a1, a2.name) >= 85:
                        paper_authors_gr.append(Author(name = a1, affiliation=a2.affiliation, email = a2.email))
                        break

        if len(dblp_authors) == len(cermine.authors):
            for a1 in dblp_authors:
                for a2 in cermine.authors:
                    #only add correct names from dblp
                    if fuzz.ratio(a1, a2.name) >= 85:
                        paper_authors_ce.append(Author(name = a1, affiliation=a2.affiliation, email = a2.email))
                        break

        print(paper_authors_gr, '+++++++++++++++')
        #TODO: need for extra checks here to make sure that all affiliations are included 
        print(len(dblp_authors), len(paper_authors_gr), len(paper_authors_ce))
        if len(dblp_authors) == len(paper_authors_gr) and len(dblp_authors) != len(paper_authors_ce):
            paper_authors = paper_authors_gr
        elif len(dblp_authors) != len(paper_authors_gr) and len(dblp_authors) == len(paper_authors_ce):
            paper_authors = paper_authors_ce
        elif len(dblp_authors) == len(paper_authors_gr) and len(dblp_authors) != len(paper_authors_ce):
            paper_authors = paper_authors_gr
        else:
            #TODO: decide what to do in this case
            paper_authors = dblp_authors

        return paper_authors

def main():
    Web = req.get('http://ceurspt.wikidata.dbis.rwth-aachen.de/index.html') 
    
    # Use Neo4jConnection to connect to Neo4j database
    neo4j_conn = Neo4jConnection(uri="neo4j+s://607f3c00.databases.neo4j.io", user="neo4j", password="B4ciag8tPs_szFjyrAFWgz6INlti5_jJUCH9aqb8ETY")

  
    S = BeautifulSoup(Web.text, 'lxml') 
    html_txt = S.prettify()
    #extract all volumes
    reg1 = r'Vol-(\d+)">'
    #all volumes from the ceurspt api
    volumes = re.findall(reg1, html_txt)

    # Here we set the volume we want to consider in the comparisons below
    parser = argparse.ArgumentParser(prog='Web parser', description='Take a list of volume numbers as input and extract the papers')
    parser.add_argument('-v', '--volume', nargs='+', default=[], required=True,help='Volume numbers as integer')     
    #args = parser.parse_args()
    #cur_volumes = args.volume
    cur_volumes = [f'{x}' for x in range(2450, 2451) if f'{x}' in volumes]
    
    assert(all([vol_nr in volumes for vol_nr in cur_volumes]))
    
    #extract all pages for each vol
    papers = {}
    for v in cur_volumes:
        url = 'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-' + v
        Web = req.get(url) 
        reg2 = rf'Vol-{v}/(.*?).pdf'
        #reg2 = r'paper(\d+).pdf' ##needs to be changed to reg2 = r'paper(\d+).pdf' to accound for more papers that do not follow this format.
        papers[int(v)] = re.findall(reg2, BeautifulSoup(Web.text, 'lxml').prettify())

    for k in papers.keys():
        for p in papers[k]:
            paper_path = f'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-{k}/{p}'
            print(paper_path)
            try:
                url_path = paper_path + ".pdf"

                #check it is preface or paper
                if not p == "Preface":
                    # extract metadata for each paper using GROBID 
                    grobid =  GrobitFile(paper_path + '.grobid')

                    # extract metadata for each paper using CERMINE 
                    cermine =  CermineFile(paper_path + '.cermine')
                    print(k, p)

                    #compare the title and give the final result
                    final_title = compare_title(grobid, cermine, url_path)
                    
                    #merge author information 
                    final_author_list = compare_author(grobid, cermine)
                    final_author_list = grobid.authors

                            
                    # Create Neo4j graph based on extracted metadata
                    create_neo4j_graph(final_author_list,final_title, neo4j_conn, url_path) 
                                 
                #if it is paper, it should belongs to one event
                else:
                    # extract metadata for each paper using GROBID 
                    grobid =  GrobitFile(paper_path + '.grobid')

                    # extract metadata for each paper using CERMINE 
                    cermine =  CermineFile(paper_path + '.cermine')
                    print(k, p)

                    #compare the title and give the final result
                    final_title = compare_title(grobid, cermine, url_path)
                    
                    #merge author information 
                    final_author_list = compare_author(grobid, cermine)
                    final_author_list = grobid.authors
                    
                    # To do: create a event node and a proceeding node
                    # Create Neo4j graph based on extracted metadata
                    create_neo4j_graph(final_author_list,final_title, neo4j_conn, url_path) 
                
            except:
                print('File not found')
            """
            if grobid.title != cermine.title or not are_equal_list_authors(grobid.authors, cermine.authors):
                print(f'\n{"*"*100}\n')
                print(f'Paper {p} PDF: {paper_path}.pdf\n')
                print(f'Paper {p} grobid: {paper_path}.grobid\n')
                print(f'Paper {p} cermine: {paper_path}.cermine\n')

            # check if title is the same
            if grobid.title != cermine.title:
                print(f'Title discrepancies\n')
                print(f'grobid title: {grobid.title} \ncermin title: {cermine.title} \n' )
            
            if not are_equal_list_authors(grobid.authors, cermine.authors):
                print('Author discrepancies\n')
                print(f'grobid authors: {grobid.authors}')
                print('\n')
                print(f'cermine authors: {cermine.authors}')
            """
            # (provided through API), including title, authors, affiliations, publication year


    """
    results = dblp.search([grobid.title])
  
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


