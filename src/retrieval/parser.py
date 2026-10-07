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