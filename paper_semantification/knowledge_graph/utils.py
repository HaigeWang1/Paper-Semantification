from paper_semantification.knowledge_graph.main import Neo4jConnection
from paper_semantification import NEO4J_URI

# Parameters name
# Proceeding: proceeding, Event: event, URL: url
# Paper: title
# Author: name, email
# Affiliation: affiliation
def create_neo4j_graph(author_list, title, proceeding, event, neo4j_connection, url):
    neo4j_connection.connect()
    
    # Create Paper nodes
    create_paper_query = "MERGE (p:Paper {title: $title, url: $url})"
    neo4j_connection.query(create_paper_query, {"title": title, "url": url})  # Replace with actual URL

    # Create Proceeding nodes
    create_proceeding_query = "MERGE (pr:Proceeding {proceeding: $proceeding})"
    neo4j_connection.query(create_proceeding_query, {"proceeding": proceeding})

    # Create Event nodes
    create_event_query = "MERGE (e:Event {event: $event})"
    neo4j_connection.query(create_event_query, {"event": event})  # Replace with actual URL

    # Create Author nodes
    for author in author_list:
        # Create Author nodes
        create_author_query = """
                            MERGE (a:Author{name:$name})
                            ON CREATE SET a.email = $email, a.affiliation = $affiliation
                            MERGE (aff:affiliation{affiliation:$affiliation})
                            MERGE (a)-[:AFFILIATED_WITH]->(aff)

                            """
        neo4j_connection.query(create_author_query, {"name": author.name, "email": author.email or "", "affiliation": author.affiliation or ""})  
    
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






def delete_neo4j_graph():
    print("Setting up Neo4j connection")
    neo4j_conn = Neo4jConnection(uri=NEO4J_URI)  
    neo4j_conn.connect()  

    print("Deleting the knowledge graph")
    delete_query = "MATCH (n) DETACH DELETE n"
    neo4j_conn.query(delete_query)
