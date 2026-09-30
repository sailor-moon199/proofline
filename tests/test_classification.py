"""Scaffold test for the classification module."""

from proofline import classification


def test_classification_package_imports() -> None:
    """Keep classification importable without invoking an LLM."""
    assert classification.__doc__ is not None
