"""Scaffold test for the document ingestion module."""

from proofline import ingestion


def test_ingestion_package_imports() -> None:
    """Keep document ingestion importable without external services."""
    assert ingestion.__doc__ is not None
