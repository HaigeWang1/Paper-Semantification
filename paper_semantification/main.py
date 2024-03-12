from fastapi import FastAPI, Query
from paper_semantification.parser import parse_volumes
from typing import List


app = FastAPI()

# Endpoint to extract metadata from a single paper
@app.get("/metadata/single_paper")
async def get_single_paper_metadata(paper_id: str = Query(..., description="Paper ID"),
                                    volume_id: str = Query(..., description="Volume ID")):
    """
    Extracts metadata from a single paper.

    Parameters:
    - paper_id (str): ID of the paper.
    - volume_id (str): ID of the volume.

    Returns:
    - dict: Metadata of the paper.
    """
    # TODO - Replace with actual logic to fetch metadata of the paper
    # Do we need such a function?
    return None

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
