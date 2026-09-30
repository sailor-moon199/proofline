"""Minimal Streamlit review UI for uploading documents and confirming review tables."""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - depends on Streamlit installation
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - optional UI dependency
    st = None


def render_review_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the edited review table from the user interaction."""
    if st is None:
        return rows
    dataframe = st.data_editor(rows, use_container_width=True)
    return list(dataframe)


def render_file_uploader(label: str = "Upload process material") -> Any:
    """Expose file selection using the official Streamlit uploader API."""
    if st is None:
        return None
    return st.file_uploader(label, accept_multiple_files=True)


def render_page() -> None:
    """Render a simple single-page skeleton for the proofline workflow."""
    if st is None:
        return
    st.title("proofline")
    st.write("Upload source material and review the process evidence before scoring.")
    uploaded = render_file_uploader()
    if uploaded:
        st.write(f"Uploaded {len(uploaded)} file(s) for review.")
