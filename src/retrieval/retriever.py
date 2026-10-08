from qdrant_client import QdrantClient, models

from src.retrieval.vector_store import (
    QDRANT_URL,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
)


def retrieve_chunks(
    query: str,
    limit: int = 5,
):

    client = QdrantClient(url=QDRANT_URL)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=models.Document(
            text=query,
            model=EMBEDDING_MODEL,
        ),
        limit=limit,
    )

    return results.points