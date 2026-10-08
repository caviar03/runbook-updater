import uuid

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker


def parse_runbook(file_path: str):
    converter = DocumentConverter()
    result = converter.convert(file_path)
    return result.document


def chunk_runbook(document):
    chunker = HybridChunker()

    chunks = list(
        chunker.chunk(dl_doc=document)
    )

    return chunks


def prepare_chunks(chunks):
    prepared_chunks = []

    for i, chunk in enumerate(chunks):

        source = chunk.meta.origin.filename

        prepared_chunks.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}#{i}")),
            "text": chunk.text,
            "headings": chunk.meta.headings,
            "source": source,
        })

    return prepared_chunks