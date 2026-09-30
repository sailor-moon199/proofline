"""Scaffold test for the extraction module."""

from proofline import extraction


def test_extraction_package_imports() -> None:
    """Keep the extraction module importable independently."""
    assert extraction.__doc__ is not None
