"""Scaffold test for the provider module."""

from proofline import providers


def test_providers_package_imports() -> None:
    """Keep provider interfaces importable without API keys or network access."""
    assert providers.__doc__ is not None
