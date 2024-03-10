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