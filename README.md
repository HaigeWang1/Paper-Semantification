# RWTH2023WS-KG-LAB-Task1_Paper-Semantification
[![GitHub last commit](https://img.shields.io/github/last-commit/HaigeWang1/Paper-Semantification)](https://github.com/HaigeWang1/Paper-Semantification/commits/main)
[![Issues](https://img.shields.io/github/issues-raw/HaigeWang1/Paper-Semantification)](https://github.com/HaigeWang1/Paper-Semantification/issues)  
![Python Version](https://img.shields.io/badge/Python-3.10%2B-brightgreen)


# Goal
The purpose of this task is to comprehensively process scholarly papers by leveraging metadata extraction services such as CERMINE and GROBID APIs.

## Working Procedure
### 1. Input Processing
#### Extract metadata for each paper using CERMINE and GROBID (provided through API), including title, authors, affiliations, publication year, etc.
- Available APIs
- - ceurspt provides CERMINE and GROBID
  - http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-2462/paper1.html
  - http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-2462/paper1.grobid
  - http://ceurspt.wikidata.dbis.rwth-aachen.de/Vol-2462/paper1.cermine
- [OPTIONAL] The ceur-ws template introduced a structure into the PDFs and recommended to at least provide a e-mail address or other identifier
  - optimization to extract author information based on the template

### 2. Entity Disambiguation
#### Utilize ORCID, DBLP, and Wikidata APIs for disambiguation:

- Search paper title in DBLP for the DBLP ID.
- Match author names with potential ORCID identifiers.
- Cross-reference paper with Wikidata entries.

### 3. Validation
#### Compare results from CERMINE and GROBID; conduct manual checks for discrepancies. If DBLP data is present, match against CERMINE and GROBID results.

### 4. Knowledge Graph (KG) Construction
#### Create nodes for Proceedings, Event, Author, Paper, Affiliations. Ensure papers are connected to proceedings and event. Connect authors to affiliations and papers.

### 5. Output and Syncing
#### Store KG privately, ensuring security of personal data such as email addresses. If pushing to a public KG, sanitize private data. Synchronize entities linked to Wikidata.

### 6. SemPubFlow Integration
#### Invoke metadata extraction modules for uploaded PDFs to auto-populate and validate necessary fields.

# Current Status of task
- [ ] 
- [ ] 
- [ ] 

# Deadline
- [ ] Midterm coordination
- [ ] Project result delivery
- [ ] Final presentation
