"""Document readers and chunking that preserve source positions."""

from proofline.ingestion.document_reader import SourceChunk, chunk_text_by_heading, ingest_document, read_document_text

__all__ = [
    "SourceChunk",
    "chunk_text_by_heading",
    "ingest_document",
    "read_document_text",
]
