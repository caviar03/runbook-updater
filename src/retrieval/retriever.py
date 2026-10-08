from qdrant_client import models

from src.retrieval.vector_store import (
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    get_qdrant_client,
)


def retrieve_chunks(
    query: str,
    limit: int = 5,
):

    client = get_qdrant_client()

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=models.Document(
            text=query,
            model=EMBEDDING_MODEL,
        ),
        limit=limit,
    )

    return results.points


def retrieve_for_queries(
    queries: list[str],
    limit: int = 5,
):
    # Run several queries and drop chunks returned more than once,
    # keeping the order in which they were first retrieved.
    unique_chunks = {}

    for query in queries:
        for chunk in retrieve_chunks(query, limit=limit):
            unique_chunks.setdefault(chunk.id, chunk)

    return list(unique_chunks.values())


def format_chunks(chunks) -> str:
    # Label each chunk with its runbook and section so agents can
    # report exactly where an issue or change belongs.
    return "\n\n".join(
        f"[Runbook: {chunk.payload['source']}]\n"
        f"[Section: {' > '.join(chunk.payload.get('headings') or [])}]\n"
        f"{chunk.payload['text']}"
        for chunk in chunks
    )