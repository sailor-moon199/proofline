"""Run the fictional Harborlight demo through the extraction and classification pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proofline.classification.verdicts import classify_step, risk_check
from proofline.extraction import build_gap_report, extract_steps_from_chunks
from proofline.ingestion import ingest_document


def main() -> None:
    """Read the demo docs, extract steps, classify them, and print the review summary."""
    demo_dir = ROOT / "demo_data" / "harborlight"
    all_steps = []
    for path in sorted(demo_dir.glob("*.txt")):
        chunks = ingest_document(path)
        texts = [chunk.text for chunk in chunks]
        extracted = extract_steps_from_chunks(texts)
        all_steps.extend(extracted)

    print("Harborlight demo summary")
    print("=" * 24)
    if not all_steps:
        print("No demo steps were extracted from the sample documents.")
        return

    for step in all_steps:
        verdict = classify_step(step)
        risks = risk_check(step)
        print(f"Step: {step.step_id} | {step.process} | {step.actor}")
        print(f"  Verdict: {verdict.primary_verdict}")
        if verdict.secondary_verdict:
            print(f"  Secondary: {verdict.secondary_verdict}")
        print(f"  Reason: {verdict.reason}")
        if risks.suggested_flags:
            print(f"  Risk flags: {', '.join(risks.suggested_flags)}")
        print()

    gaps = build_gap_report(all_steps)
    print("Gap report")
    print("-" * 24)
    if gaps:
        for item in gaps:
            print(f"- {item}")
    else:
        print("No missing or vague numeric inputs were flagged in the demo sample.")

    print()
    print("Scoring note: savings calculations are intentionally skipped until a confirmed client config is supplied.")
    print("Use config/client.example.toml as the template for client-specific business values and fill them in explicitly.")


if __name__ == "__main__":
    main()
