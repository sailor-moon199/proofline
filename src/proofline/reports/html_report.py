"""HTML report generation for a scored opportunity register."""

from __future__ import annotations

from html import escape
from typing import Iterable

from proofline.classification.verdicts import ClassificationResult
from proofline.scoring.engine import StepScore


def render_html_report(
    *,
    title: str,
    rows: Iterable[tuple[str, StepScore, ClassificationResult]],
    assumptions: Iterable[str] | None = None,
    gaps: Iterable[str] | None = None,
) -> str:
    """Render an HTML report that exposes formulas and assumptions for each row."""
    rows_html: list[str] = []
    for step_id, score, verdict in rows:
        rows_html.append(
            """
            <tr>
              <td>{step_id}</td>
              <td>{verdict.primary_verdict}</td>
              <td>{annual_runs}</td>
              <td>{hours_saved}</td>
              <td>{cost_saved}</td>
              <td>{payback}</td>
              <td>{reason}</td>
            </tr>
            """.format(
                step_id=escape(step_id),
                verdict=verdict,
                annual_runs=_metric_cell(score.annual_runs),
                hours_saved=_metric_cell(score.hours_saved_per_year),
                cost_saved=_metric_cell(score.cost_saved_per_year),
                payback=_metric_cell(score.payback_months),
                reason=escape(verdict.reason),
            )
        )

    assumption_list = "".join(f"<li>{escape(item)}</li>" for item in (assumptions or []))
    gap_list = "".join(f"<li>{escape(item)}</li>" for item in (gaps or []))

    return f"""
    <!doctype html>
    <html lang=\"en\">
      <head>
        <meta charset=\"utf-8\">
        <title>{escape(title)}</title>
      </head>
      <body>
        <h1>{escape(title)}</h1>
        <h2>Opportunity register</h2>
        <table>
          <thead>
            <tr>
              <th>Step ID</th>
              <th>Verdict</th>
              <th>Annual runs</th>
              <th>Hours saved/year</th>
              <th>Cost saved/year</th>
              <th>Payback (months)</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows_html)}
          </tbody>
        </table>
        <h2>Assumptions</h2>
        <ul>{assumption_list}</ul>
        <h2>Gaps</h2>
        <ul>{gap_list}</ul>
      </body>
    </html>
    """


def _metric_cell(metric: object) -> str:
    """Render metric values and labels without hiding the not-computed state."""
    if hasattr(metric, "status") and getattr(metric, "status").value == "not computed":
        return f"<span>not computed</span>"
    value = getattr(metric, "value", None)
    if value is None:
        return "<span>not computed</span>"
    return f"{value:,.2f}"
