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
def create_neo4j_graph(author_list, title, proceeding, event, neo4j_connection, url):
    neo4j_connection.connect()
    
    # Create Paper nodes
    create_paper_query = "MERGE (:Paper {title: $title, url: $url})"
    neo4j_connection.query(create_paper_query, {"title": title, "url": url})  # Replace with actual URL

    # Create Proceeding nodes
    create_proceeding_query = "MERGE (:Proceeding {proceeding: $proceeding})"
    neo4j_connection.query(create_proceeding_query, {"proceeding": proceeding})

    # Create Event nodes
    create_event_query = "MERGE (:Event {event: $event})"
    neo4j_connection.query(create_event_query, {"event": event})  # Replace with actual URL

    # Create Author nodes
    for author in author_list:
        # Create Author nodes
        create_author_query = "MERGE (:Author {name: $name, email: $email})"
        neo4j_connection.query(create_author_query, {"name": author.name, "email": author.email or ""})
        
        # Create Affiliation nodes
        create_aff_query = "MERGE (:Affiliation {affiliation: $affiliation})"
        neo4j_connection.query(create_aff_query, {"affiliation": author.affiliation})

         # Create relationships between Authors and Affiliations
        create_author_aff_query = "MATCH (a:Author {name: $name}), (aff:Affiliation {affiliation: $affiliation}) MERGE (a)-[:AFFILIATED_WITH]->(aff)"
        neo4j_connection.query(create_author_aff_query, {"name": author.name, "affiliation": author.affiliation})      

    
        # Create relationships between Authors and Papers
        create_author_paper_query = "MATCH (a:Author {name: $name}), (p:Paper {title: $title}) MERGE (a)-[:AUTHORED]->(p)"
        neo4j_connection.query(create_author_paper_query, {"name": author.name, "title": title})

        # Create relationships between Authors and Proceedings
        create_author_proceeding_query = "MATCH (a:Author {name: $name}), (pr:Proceeding {proceeding: $proceeding}) MERGE (a)-[:PRESENTED_AT]->(pr)"
        neo4j_connection.query(create_author_proceeding_query, {"name": author.name, "proceeding": proceeding})

        # Create relationships between Authors and Events
        create_author_event_query = "MATCH (a:Author {name: $name}), (e:Event {event: $event}) MERGE (a)-[:PARTICIPATED_IN]->(e)"
        neo4j_connection.query(create_author_event_query, {"name": author.name, "event": event})

     
    neo4j_connection.close()