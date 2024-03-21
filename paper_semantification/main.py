from fastapi import FastAPI, Query
from paper_semantification.knowledge_graph.utils import delete_neo4j_graph
from paper_semantification.parser import parse_volumes, process_single_paper
from typing import List


app = FastAPI()

# Endpoint to extract metadata from a single paper
@app.get("/metadata/single_paper")
async def get_single_paper_metadata(volume_id: int = Query(..., description="Volume ID"),
                                    paper_id: int = Query(..., description="Paper ID")):
    """
    Extracts metadata from a single paper.

    Parameters:
    - volume_id (int): ID of the volume.
    - paper_id (int): ID of the paper.

    Returns:
    - dict: Metadata of the paper.
    """
    paper_metadata = process_single_paper(volume_id=str(volume_id), paper_key=f"paper{str(paper_id)}")
    return {"paper_path": paper_metadata[0], "paper_title": paper_metadata[1], "name": paper_metadata[2], "affiliation": paper_metadata[3], "email": paper_metadata[4], "proceeding": paper_metadata[5], "event": paper_metadata[6]}
    # return **paper_metadata

# Endpoint to extract metadata from all papers in a given volume
@app.get("/metadata/volumes")
async def get_all_papers_metadata(volumes_ids: List[int] = Query([], description="Volumes IDs"),
                                  construct_graph: bool = Query(False, description="Construct graph"),
                                  all_volumes: bool = Query(False, description="All volumes")):
    """
    Extracts metadata from all papers in a given volume.

    Parameters:
    - volume_id (str): ID of the volume.

    Returns:
    - list: List of metadata of all papers in the volume.
    """
    # Dummy implementation - Replace with actual logic to fetch metadata of all papers in the volume
    all_papers_metadata = [parse_volumes(volumes = volumes_ids, construct_graph = construct_graph, all_volumes = all_volumes)]
    return all_papers_metadata


# Endpoint to delete the knowledge graph from the neo4j database
@app.delete("/delete_graph")
async def delete_knowledge_graph():
    """
    Deletes the knowledge graph from the Neo4j database.

    Returns:
    - str: Success message.
    """
    # Execute neo4j query that deletes all nodes and relationships
    delete_neo4j_graph()
    return "Knowledge graph deleted successfully!"

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
