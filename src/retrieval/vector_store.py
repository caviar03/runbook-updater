from qdrant_client import QdrantClient, models

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "runbook_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def get_qdrant_client():
    return QdrantClient(url=QDRANT_URL)


def create_collection(client):
    if client.collection_exists(COLLECTION_NAME):
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
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
            collection_name=COLLECTION_NAME,
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
        collection_name=COLLECTION_NAME,

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