import glob
import os
import sys

from src.retrieval.parser import chunk_runbook, parse_runbook, prepare_chunks
from src.retrieval.vector_store import create_collection, get_qdrant_client, index_chunks


def index_runbooks(runbook_paths: list[str]) -> None:

    client = get_qdrant_client()

    create_collection(client)

    for path in runbook_paths:
        document = parse_runbook(path)
        chunks = prepare_chunks(chunk_runbook(document))

        index_chunks(client, chunks)

        print(f"INDEXER: indexed {len(chunks)} chunks from {os.path.basename(path)}")


if __name__ == "__main__":
    # Usage: python -m src.retrieval.index_runbooks [runbook.docx ...]
    # Defaults to every runbook in test_data/input.
    paths = sys.argv[1:] or sorted(glob.glob("test_data/input/*.docx"))
    index_runbooks(paths)
