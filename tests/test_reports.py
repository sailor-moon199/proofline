"""Scaffold test for the report module."""

from proofline import reports


def test_reports_package_imports() -> None:
    """Keep report generation importable independently."""
    assert reports.__doc__ is not None
