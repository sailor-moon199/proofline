"""Scaffold test for the user-interface module."""

from proofline import ui


def test_ui_package_imports() -> None:
    """Keep the UI package importable in offline test environments."""
    assert ui.__doc__ is not None
