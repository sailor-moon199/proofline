"""Extraction review, evidence verification, merging, and gap reporting."""

from proofline.extraction.pipeline import extract_steps_from_chunks, verify_evidence_for_steps
from proofline.extraction.verify import (
    build_gap_report,
    merge_duplicate_steps,
    normalize_text_for_evidence,
    verify_quote_in_source,
    verify_step_evidence,
)

__all__ = [
    "build_gap_report",
    "extract_steps_from_chunks",
    "merge_duplicate_steps",
    "normalize_text_for_evidence",
    "verify_evidence_for_steps",
    "verify_quote_in_source",
    "verify_step_evidence",
]
