#!/usr/bin/env python3
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


skill_dir = Path(__file__).resolve().parents[1]
skill_path = skill_dir / "SKILL.md"
checks_path = skill_dir / "references" / "checks.md"
utc_today = datetime.now(timezone.utc).date()

try:
    raw_skill_md = skill_path.read_text(encoding="utf-8")
    raw_checks_md = checks_path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as error:
    sys.exit(f"FAIL: unable to read contract files: {error}")

skill_md = " ".join(raw_skill_md.split())
checks_md = " ".join(raw_checks_md.split())

REQUIRED_SKILL_PHRASES = [
    "name: 03-abstention-policy-design",
    "version: 1.0.0",
    "last_reviewed: 2026-09-11",
    "../00-agent-reliability-guardrails/SKILL.md",
    "`source_id`, `owning_team`, `agent_speaks_from`, `owner_exposure`, `freshness_basis`, and `freshness_detail`",
    "no_supporting_source",
    "conflicting_sources",
    "source_older_than_freshness_basis",
    "out_of_scope_question",
    "refuse_and_handoff",
    "accuracy_owner",
    "coverage_owner",
    "review_cadence",
    "expected_coverage_impact",
    "does not change a running agent",
    "[SRC-CHOW-REJECT-TRADEOFF]",
    "[SRC-OPENAI-HALLUCINATION-EVALS]",
    "execution_status",
    "not_applied",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    ".abstention_policy",
    ".trigger_conditions",
    '"conflicting_sources"',
    ".customer_behaviour.disposition",
    '"refuse_and_handoff"',
    ".handoff.target",
    ".handoff.instructions",
    ".threshold_owner.accountability",
    '"accuracy_owner"',
    ".review_cadence.interval_days",
    ".review_cadence.change_evidence",
    "$impact.value",
    ".expected_coverage_impact.coverage_owner.accountability",
    '"coverage_owner"',
    ".expected_coverage_impact.agreement_status",
    '"agreed"',
    ".execution_status == \"not_applied\"",
    "source_registry",
    "freshness_detail",
]

missing = []
for phrase in REQUIRED_SKILL_PHRASES:
    if phrase not in skill_md:
        missing.append(f"missing required skill phrase: {phrase!r}")

for phrase in REQUIRED_CHECK_PHRASES:
    if phrase not in checks_md:
        missing.append(f"missing required checks.md phrase: {phrase!r}")

if missing:
    print("FAIL: 03-abstention-policy-design contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

expected_sections = [
    "Source registry preserves the interoperable contract",
    "Every mandatory evidence trigger is present",
    "Customer behaviour is a useful refusal with handoff",
    "The operating point has a distinct accuracy owner",
    "Review cadence requires evidence for change",
    "The coverage owner agrees a known numeric impact",
    "Guardrail status is preserved and changes remain non-autonomous",
    "No raw customer identifiers enter the policy report",
]
section_blocks = dict(
    re.findall(r"^## (.+?)\n.*?^```bash\n(.*?)^```", raw_checks_md, re.MULTILINE | re.DOTALL)
)
if list(section_blocks) != expected_sections:
    sys.exit(
        "FAIL: checks.md must contain exactly the eight documented executable check sections"
    )

valid_report = {
    "source_registry": [
        {
            "source_id": "order-system",
            "owning_team": "Order operations",
            "agent_speaks_from": True,
            "owner_exposure": "acknowledged",
            "freshness_basis": "event_driven",
            "freshness_detail": "Order events appear within 60 seconds",
        }
    ],
    "abstention_policy": {
        "trigger_conditions": [
            "no_supporting_source",
            "conflicting_sources",
            "source_older_than_freshness_basis",
            "out_of_scope_question",
        ],
        "customer_behaviour": {
            "disposition": "refuse_and_handoff",
            "explain_reason": True,
            "offer_handoff": True,
            "message": "I cannot verify that reliably, so I will connect you with order support.",
        },
        "handoff": {
            "type": "human",
            "target": {"type": "on_call_function", "name": "order-support-on-call"},
            "instructions": "Transfer the question and cited source IDs for human review.",
        },
        "operating_point": {
            "metric": "qualified_answer_score",
            "answer_threshold": 0.85,
            "trigger_precedence": "mandatory_abstention",
        },
        "threshold_owner": {
            "accountability": "accuracy_owner",
            "type": "person",
            "name": "Amina Shah",
        },
        "review_cadence": {
            "interval_days": 30,
            "change_evidence": [
                "system_of_record_error_measurement",
                "abstention_rate_measurement",
                "coverage_impact_measurement",
            ],
        },
        "expected_coverage_impact": {
            "value": 8,
            "unit": "percentage_points",
            "direction": "coverage_decrease",
            "coverage_owner": {
                "accountability": "coverage_owner",
                "type": "person",
                "name": "Omar Khan",
            },
            "agreement_status": "agreed",
            "agreed_at": utc_today.isoformat(),
        },
    },
    "recommendations": [
        {
            "recommended_action": "Have an operator apply the accepted abstention policy.",
            "automation_level": "2-HITL",
            "execution_status": "not_applied",
        }
    ],
    "guardrail_status": "CLEAR",
    "status": "CLEAR",
}


def invalid_reports():
    reports = []

    report = copy.deepcopy(valid_report)
    report["source_registry"][0]["freshness_detail"] = "TBD"
    reports.append(("placeholder source freshness", expected_sections[0], report))

    report = copy.deepcopy(valid_report)
    report["abstention_policy"]["trigger_conditions"].remove("conflicting_sources")
    reports.append(("missing conflicting-evidence trigger", expected_sections[1], report))

    for target_name in ("owner", "someone", "on-call"):
        report = copy.deepcopy(valid_report)
        report["abstention_policy"]["handoff"]["target"]["name"] = target_name
        reports.append((f"generic handoff target {target_name!r}", expected_sections[2], report))

        report = copy.deepcopy(valid_report)
        report["abstention_policy"]["threshold_owner"]["name"] = target_name
        reports.append((f"generic threshold owner {target_name!r}", expected_sections[3], report))

        report = copy.deepcopy(valid_report)
        report["abstention_policy"]["expected_coverage_impact"]["coverage_owner"][
            "name"
        ] = target_name
        reports.append((f"generic coverage owner {target_name!r}", expected_sections[5], report))

    report = copy.deepcopy(valid_report)
    report["abstention_policy"]["customer_behaviour"]["disposition"] = "terminate"
    del report["abstention_policy"]["handoff"]
    reports.append(("terminating refusal without handoff", expected_sections[2], report))

    report = copy.deepcopy(valid_report)
    report["abstention_policy"]["expected_coverage_impact"]["coverage_owner"]["name"] = "Amina-Shah"
    reports.append(("normalized duplicate owner", expected_sections[3], report))

    report = copy.deepcopy(valid_report)
    report["abstention_policy"]["review_cadence"]["change_evidence"].remove(
        "coverage_impact_measurement"
    )
    reports.append(("missing review evidence class", expected_sections[4], report))

    coverage_failures = (
        (101, "percentage_points", utc_today.isoformat(), "101 percentage points"),
        (1001, "answers_per_1000", utc_today.isoformat(), "1001 answers per 1000"),
        (1e308, "percent_relative", utc_today.isoformat(), "unbounded finite number"),
        (8, "percentage_points", "2026-02-31", "invalid calendar date"),
        (
            8,
            "percentage_points",
            (utc_today + timedelta(days=1)).isoformat(),
            "future agreement date",
        ),
    )
    for value, unit, agreed_at, label in coverage_failures:
        report = copy.deepcopy(valid_report)
        impact = report["abstention_policy"]["expected_coverage_impact"]
        impact.update(value=value, unit=unit, agreed_at=agreed_at)
        reports.append((label, expected_sections[5], report))

    report = copy.deepcopy(valid_report)
    report["recommendations"][0]["execution_status"] = "applied"
    reports.append(("applied recommendation", expected_sections[6], report))

    report = copy.deepcopy(valid_report)
    report["abstention_policy"]["customer_behaviour"]["message"] = (
        "Contact customer@example.com for review."
    )
    reports.append(("raw customer identifier", expected_sections[7], report))

    return reports


def run_check(command, report):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as report_file:
        json.dump(report, report_file)
        report_file.flush()
        environment = os.environ.copy()
        environment["REPORT"] = report_file.name
        return subprocess.run(
            ["bash", "-c", command],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )


failures = []
for section, command in section_blocks.items():
    result = run_check(command, valid_report)
    if result.returncode != 0:
        failures.append(f"canonical valid report failed {section!r}")

zero_impact_report = copy.deepcopy(valid_report)
zero_impact_report["abstention_policy"]["expected_coverage_impact"]["value"] = 0
zero_result = run_check(
    section_blocks["The coverage owner agrees a known numeric impact"], zero_impact_report
)
if zero_result.returncode != 0:
    failures.append("verified and agreed zero coverage impact was rejected")

adversarial_reports = invalid_reports()
for label, section, report in adversarial_reports:
    result = run_check(section_blocks[section], report)
    if result.returncode == 0:
        failures.append(f"targeted invalid report passed {section!r}: {label}")

if failures:
    print("FAIL: 03-abstention-policy-design executable contract checks failed:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print(
    "PASS: 03-abstention-policy-design contract and executable checks passed "
    f"({len(section_blocks)} gates, {len(adversarial_reports)} adversarial reports)."
)
