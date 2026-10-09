from qdrant_client import QdrantClient, models

from src.retrieval.runtime import current_scope

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "runbook_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def get_qdrant_client():
    scope = current_scope()
    return scope[0] if scope else QdrantClient(url=QDRANT_URL)


def collection_name():
    scope = current_scope()
    return scope[1] if scope else COLLECTION_NAME


def create_collection(client):
    if client.collection_exists(collection_name()):
        return

    client.create_collection(
        collection_name=collection_name(),
        vectors_config=models.VectorParams(
            size=client.get_embedding_size(EMBEDDING_MODEL),
            distance=models.Distance.COSINE,
        ),
    )


def index_chunks(client, chunks):

    # Remove any previously indexed chunks for these runbooks so a
    # re-indexed (possibly shorter) runbook doesn't leave stale chunks.
    sources = sorted({chunk["source"] for chunk in chunks})

    if sources:
        client.delete(
            collection_name=collection_name(),
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source",
                            match=models.MatchAny(any=sources),
                        )
                    ]
                )
            ),
        )

    client.upload_collection(
        collection_name=collection_name(),

        vectors=[
            models.Document(
                text=chunk["text"],
                model=EMBEDDING_MODEL,
            )
            for chunk in chunks
        ],

        payload=[
            {
                "text": chunk["text"],
                "headings": chunk["headings"],
                "source": chunk["source"],
            }
            for chunk in chunks
        ],

        ids=[
            chunk["id"]
            for chunk in chunks
        ],
    )