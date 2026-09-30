"""Scaffold test for the evaluation module."""

from proofline import evaluation


def test_evaluation_package_imports() -> None:
    """Keep evaluation tooling importable without provider calls."""
    assert evaluation.__doc__ is not None


def test_evaluation_metrics_match_answer_key() -> None:
    """The evaluation harness uses the approved process + actor + task matching rule."""
    expected = [{
        "process": "Shipment booking",
        "actor": "Coordinator",
        "task": "Enter shipment details",
        "evidence": [{"document": "shipment_booking.txt", "quote": "We book four shipments per week."}],
        "frequency": {"value": 4},
        "minutes_per_run": {"value": 30},
        "people_doing_it": {"value": 3},
        "error_rate": {"value": None},
    }]
    actual = [{
        "process": "Shipment booking",
        "actor": "Coordinator",
        "task": "Enter shipment details",
        "evidence": [{"document": "shipment_booking.txt", "quote": "We book four shipments per week.", "verified": True}],
        "frequency": {"value": 4},
        "minutes_per_run": {"value": 30},
        "people_doing_it": {"value": 3},
        "error_rate": {"value": None},
    }]
    result = evaluation.evaluate_steps(
        actual,
        expected,
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="phase-7",
        source_documents={"shipment_booking.txt": "We book four shipments per week."},
    )
    assert result.steps_found == 1
    assert result.step_precision == 1.0
    assert result.step_recall == 1.0
    assert result.fabricated_quote_count == 0
    assert result.unverified_quote_count == 0
    assert result.numeric_accuracy == 1.0
    assert result.null_handling_accuracy == 1.0
