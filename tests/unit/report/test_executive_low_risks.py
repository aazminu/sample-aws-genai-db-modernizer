"""#950: the executive report gives a low risk no card, only one line pointing to
the engineering report, which lists every risk."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.report.executive_report import low_risks_line, render_executive_report_pdf
from src.report.facts import report_facts
from src.report.renderers import render_engineering_report_md
from tests.executive_pdf import normalize, text

FIXTURE = Path(__file__).parent / "fixtures" / "wordpress_report.json"


def _report(*risks: dict) -> dict:
    report: dict = copy.deepcopy(json.loads(FIXTURE.read_text()))
    report["risk_assessment"]["risks"] = list(risks)
    report.pop("facts", None)
    report["facts"] = report_facts(report)
    return report


LOW = {
    "risk_id": "RISK-101",
    "severity": "LOW",
    "risk_type": "MIGRATION_COMPLEXITY",
    "description": "[aurora_mysql] Wave 3: 4 queries were decided by less than 5 points.",
}
MEDIUM = {
    "risk_id": "RISK-102",
    "severity": "MEDIUM",
    "risk_type": "DATA_CONSISTENCY",
    "description": "[dynamodb] Wave 3: 2 reads run on a copy of 1 table that CDC keeps in sync.",
}


def test_a_low_risk_gets_one_line_and_no_card() -> None:
    report = _report(LOW, MEDIUM)
    pdf = normalize(text(render_executive_report_pdf(report)))
    assert "RISK-102" in pdf
    assert "RISK-101" not in pdf
    assert normalize(low_risks_line(1)) in pdf
    # The engineering report still lists it.
    assert "**RISK-101**" in render_engineering_report_md(report)


def test_no_low_line_without_low_risks() -> None:
    pdf = normalize(text(render_executive_report_pdf(_report(MEDIUM))))
    assert "listed in the engineering report" not in pdf


def test_the_line_counts_in_the_plural() -> None:
    assert low_risks_line(1) == "1 low risk, listed in the engineering report."
    assert low_risks_line(3) == "3 low risks, listed in the engineering report."
