
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
            self._title = self.grobidxml.title.getText()
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
        # assert(len(authors_list)==len(affiliations))
        # assert(len(authors_list)==len(emails))
        for i in range(len(authors_list)):
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
            self._title = elem_to_text(self.cermine.find('article-title'))
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
                    affl = ''
                    if len(institutions) == len(addr):
                        if len(countries) != 0:
                                if len(countries) == len(institutions):
                                    for i in range(len(institutions)): #aff_tag.findAll('institution'):
                                        affl = (', ').join([elem_to_text(institutions[i])]+  [elem_to_text(addr[i])] + [elem_to_text(countries[0])])
                                else:
                                    for i in range(len(institutions)): #aff_tag.findAll('institution'):                                        
                                        affl = (', ').join([elem_to_text(institutions[i])] + [elem_to_text(addr[i])])
                                    affl += elem_to_text(countries[0])
                        else:
                            for i in range(len(institutions)): #aff_tag.findAll('institution'):
                                affl = elem_to_text(institutions[i]) + " " +  elem_to_text(addr[i]) +  ' ' 
                        affiliations += [affl.strip()]
                
                else:
                    print(f"Author: {name}, Institution not found")
            
            author = Author(name=name, affiliation=affiliations, email=email)
            result.append(author)

        return result


  
def elem_to_text(elem = None):
    if elem:
        return elem.getText()
    return ''


 
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
        



def main():
    Web = req.get('http://ceurspt.wikidata.dbis.rwth-aachen.de/index.html') 
  
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
    assert(all([vol_nr in volumes for vol_nr in cur_volumes]))

    
    #extract all pages for each vol
    papers = {}
    for v in cur_volumes:
        url = 'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-' + v 
        Web = req.get(url) 
        reg2 = r'paper(\d+).pdf'
        papers[int(v)] = re.findall(reg2, BeautifulSoup(Web.text, 'lxml').prettify())
            
    for k in papers.keys():
        for p in papers[k]:
            paper_path = f'http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-{k}/paper{p}'
            # extract metadata for each paper using GROBID 
            grobid =  GrobitFile(paper_path+'.grobid')

            # extract metadata for each paper using CERMINE 
            cermine =  CermineFile(paper_path+'.cermine')
            
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
            
            # (provided through API), including title, authors, affiliations, publication year




    
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



if __name__ == '__main__':
    main()


