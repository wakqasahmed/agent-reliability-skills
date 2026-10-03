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
fixtures_path = skill_dir / "eval" / "fixtures" / "held-out-scenarios.json"
upstream_paths = {
    "01": skill_dir.parent / "01-answer-surface-definition" / "SKILL.md",
    "02": skill_dir.parent / "02-input-exposure-inventory" / "SKILL.md",
    "04": skill_dir.parent / "04-accuracy-sampling-plan" / "SKILL.md",
    "06": skill_dir.parent / "06-accuracy-ownership-separation" / "SKILL.md",
}
utc_today = datetime.now(timezone.utc).date()

try:
    raw_skill_md = skill_path.read_text(encoding="utf-8")
    raw_checks_md = checks_path.read_text(encoding="utf-8")
    upstream_md = {k: v.read_text(encoding="utf-8") for k, v in upstream_paths.items()}
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
    sys.exit(f"FAIL: unable to read contract files: {error}")

skill_md = " ".join(raw_skill_md.split())
checks_md = " ".join(raw_checks_md.split())

REQUIRED_SKILL_PHRASES = [
    "name: 07-failure-to-regression-intake",
    "version: 1.0.0",
    "../00-agent-reliability-guardrails/SKILL.md",
    "does not change a running agent, prompt, retrieval configuration, abstention threshold or routing rule",
    "`04-accuracy-sampling-plan`",
    "`measurements[].id`",
    "`graded_against`",
    "`sampling_plan.grading.grader`",
    "`failure_class`",
    "`missing_input`",
    "`stale_input`",
    "`conflicting_inputs`",
    "`out_of_scope_answered`",
    "`wrong_from_correct_inputs`",
    "`fix_owner_role`",
    "`source_owner`",
    "`scope_owner`",
    "`accuracy_owner`",
    "`02-input-exposure-inventory`",
    "`source_registry.owning_team`",
    "`01-answer-surface-definition`",
    "`answer_surface.scope_owner`",
    "`06-accuracy-ownership-separation`",
    "`ownership.accuracy_owner`",
    "`question_shape`",
    "`scenario`",
    "`sanitisation_confirmed`",
    "`channel_reuse_confirmed`",
    "`provenance: production`",
    "`verification_measurement`",
    "`planned_id`",
    "[`skill-model-bench`](https://github.com/wakqasahmed/skill-model-bench)",
    "issue #32",
    "commit `2f22e81`",
    "ignores every other key",
    "is not read by the loader yet",
    "(gate 1)",
    "(gate 5)",
    "(gate 6)",
    "execution_status",
    "not_applied",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    ".regression_cases",
    ".failure_class",
    ".fix_owner_role",
    ".provenance",
    ".sanitisation_confirmed",
    ".channel_reuse_confirmed",
    ".violates_gate",
    ".grading_evidence",
    ".verification_measurement",
    ".planned_id",
    "graded_sample",
    "held-out-scenarios.json",
    ".execution_status == \"not_applied\"",
]

missing = []
for phrase in REQUIRED_SKILL_PHRASES:
    if phrase not in skill_md:
        missing.append(f"missing required skill phrase: {phrase!r}")
for phrase in REQUIRED_CHECK_PHRASES:
    if phrase not in checks_md:
        missing.append(f"missing required checks.md phrase: {phrase!r}")

if missing:
    print("FAIL: 07-failure-to-regression-intake contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

expected_sections = [
    "Every case has a failure class, and the class decides who fixes it",
    "A production case is only valid once sanitisation and channel reuse are confirmed",
    "Case text carries no identifiers, no customer wording and no pasted transcript",
    "Each case loads in skill-model-bench unchanged",
    "Each case cites graded evidence from 04-accuracy-sampling-plan",
    "The fix and the measurement that shows it stayed closed are recorded",
    "Guardrail status is preserved and changes remain non-autonomous",
]
section_blocks = dict(
    re.findall(r"^## (.+?)\n.*?^```bash\n(.*?)^```", raw_checks_md, re.MULTILINE | re.DOTALL)
)
if list(section_blocks) != expected_sections:
    sys.exit("FAIL: checks.md must contain exactly the seven documented executable check sections")

failures = []

# Every upstream field this skill names must exist in the skill that defines it.
for skill_number, field in (
    ("04", "interval_bounds"), ("04", "graded_against"), ("04", "grader"), ("04", "selection_method"),
    ("04", "stratified_by_question_class"), ("04", "oversampled_new_classes"), ("04", "graded_sample"),
    ("02", "owning_team"), ("02", "source_registry"),
    ("01", "scope_owner"), ("01", "scope_statement"),
    ("06", "accuracy_owner"),
):
    if field not in upstream_md[skill_number]:
        failures.append(f"field {field!r} is not defined in skill {skill_number}")

# The failure-class table in SKILL.md and the role mapping the checks enforce must agree.
ROLE_FOR_CLASS = {
    "missing_input": "source_owner",
    "stale_input": "source_owner",
    "conflicting_inputs": "source_owner",
    "out_of_scope_answered": "scope_owner",
    "wrong_from_correct_inputs": "accuracy_owner",
}
table_rows = re.findall(r"^[ \t]*\| `(\w+)` \|[^\n]*?\| `(\w+_owner)` \|", raw_skill_md, re.MULTILINE)
if dict(table_rows) != ROLE_FOR_CLASS or len(table_rows) != len(ROLE_FOR_CLASS):
    failures.append(f"SKILL.md failure-class table {table_rows!r} does not match the enforced mapping")
for class_name, role in ROLE_FOR_CLASS.items():
    if f'"{class_name}": "{role}"' not in raw_checks_md:
        failures.append(f"checks.md does not enforce {class_name!r} -> {role!r}")


def iso(days=0):
    return (utc_today + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------------------------
# Reference model of what skill-model-bench loads. This mirrors, and was read from, the public
# source of wakqasahmed/skill-model-bench at main commit 2f22e81:
#   config_gen._load_fixtures        non-empty JSON list at eval/fixtures/held-out-scenarios.json
#   config_gen._fixture_test_case    ValueError unless 'scenario' is present; reads id, expected,
#                                    violates_gate; ignores every other key
#   assertions.fixture_check         scores `expected` only as 'follow' or 'violates'
# `provenance` is NOT read by that loader at that commit (it is proposed in the bench's issue #32).
# ---------------------------------------------------------------------------------------------
def bench_load_fixture_list(data):
    if not isinstance(data, list) or not data:
        return None
    return data


def bench_fixture_test_case(entry):
    if "scenario" not in entry:
        raise ValueError(f"fixture entry missing required key 'scenario': {entry!r}")
    scenario_vars = {"scenario": entry["scenario"], "expected": entry.get("expected")}
    if "violates_gate" in entry:
        scenario_vars["violates_gate"] = entry["violates_gate"]
    return {
        "description": entry.get("id", "fixture-scenario"),
        "vars": scenario_vars,
        "metadata": {"ground_truth": "fixture", "scenario_id": entry.get("id")},
    }


def bench_accepts(entry):
    """True when the bench loads the entry and can score it (expected is follow or violates)."""
    try:
        case = bench_fixture_test_case(entry)
    except (ValueError, TypeError):
        return False
    return case["vars"]["expected"] in ("follow", "violates") and isinstance(case["vars"]["scenario"], str)


for fixture in fixtures:
    if not bench_accepts(fixture):
        failures.append(f"held-out fixture {fixture.get('id')!r} would not load in skill-model-bench")
if bench_load_fixture_list(fixtures) is None:
    failures.append("held-out fixtures are not a non-empty list")

valid_case = {
    "id": "rc-order-status-0001",
    "question_shape": "Asks for the delivery date of an order whose items shipped in two parcels with different carriers.",
    "scenario": (
        "An order-status agent is asked for the delivery date of an order whose items shipped in two "
        "parcels with different carriers. It gives one date for the whole order with full confidence, "
        "although the order record holds a separate date for each parcel."
    ),
    "failure_class": "wrong_from_correct_inputs",
    "expected": "violates",
    "violates_gate": "confident answer the order record does not support",
    "provenance": "production",
    "sanitisation_confirmed": True,
    "channel_reuse_confirmed": True,
    "fix_owner_role": "accuracy_owner",
    "fix_owner": "Priya Nair",
    "grading_evidence": {
        "measurement_id": "m-order-status-2026-w40",
        "graded_against": "order management system",
        "grader": "Priya Nair",
        "system_of_record_finding": "The order record lists two parcels with different delivery dates; the answer stated one.",
    },
    "fix": {
        "description": "Answer split shipments parcel by parcel, or hand off when the parcels disagree.",
        "status": "closed",
        "closed_by": "Priya Nair",
        "closed_on": iso(),
    },
    "verification_measurement": {
        "planned_id": "m-order-status-split-shipments-2026-w44",
        "selection_method": "stratified_by_question_class",
        "metric": "error_rate",
        "graded_against": "order management system",
        "minimum_sample_size": 200,
    },
}

valid_report = {
    "measurements": [
        {
            "id": "m-order-status-2026-w40",
            "source": "graded_sample",
            "error_rate": 0.03,
            "sample_size": 200,
            "interval_bounds": {"method": "wilson", "level": 0.95, "lower": 0.0138, "upper": 0.0639},
            "graded_against": "order management system",
        }
    ],
    "regression_cases": [valid_case],
    "recommendations": [
        {
            "recommended_action": "Have an operator append rc-order-status-0001 to the target skill's held-out scenarios and book the follow-up graded sample.",
            "automation_level": "2-HITL",
            "execution_status": "not_applied",
        }
    ],
    "guardrail_status": "CLEAR",
    "status": "CLEAR",
}


def run_check(command, report):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as report_file:
        json.dump(report, report_file)
        report_file.flush()
        environment = os.environ.copy()
        environment["REPORT"] = report_file.name
        return subprocess.run(
            ["bash", "-c", command], env=environment, capture_output=True, text=True, check=False
        )


def mutated(change):
    report = copy.deepcopy(valid_report)
    change(report)
    return report


def case(report, index=0):
    return report["regression_cases"][index]


def edit_case(change):
    def apply(report):
        change(case(report))
    return apply


def set_case(key, value):
    return edit_case(lambda c: c.__setitem__(key, value))


def del_case(key):
    return edit_case(lambda c: c.pop(key))


def set_in(key_path, value):
    def apply(c):
        target = c
        for key in key_path[:-1]:
            target = target[key]
        target[key_path[-1]] = value
    return edit_case(apply)


def del_in(key_path):
    def apply(c):
        target = c
        for key in key_path[:-1]:
            target = target[key]
        target.pop(key_path[-1])
    return edit_case(apply)


S = expected_sections
negative_controls = []


def add(section, label, change):
    negative_controls.append((label, S[section], mutated(change)))


# Section 0: a failure class decides the fixer.
add(0, "no failure_class", del_case("failure_class"))
add(0, "failure_class is null", set_case("failure_class", None))
add(0, "failure_class is blank", set_case("failure_class", ""))
add(0, "failure_class is a list", set_case("failure_class", ["stale_input"]))
add(0, "failure_class is unknown", set_case("failure_class", "bad_luck"))
add(0, "failure_class with different case", set_case("failure_class", "Stale_Input"))
for class_name, right_role in ROLE_FOR_CLASS.items():
    for wrong_role in ("source_owner", "scope_owner", "accuracy_owner", "coverage_owner"):
        if wrong_role != right_role:
            add(0, f"{class_name} fixed by {wrong_role}",
                edit_case(lambda c, n=class_name, r=wrong_role: c.update(failure_class=n, fix_owner_role=r)))
add(0, "no fix_owner_role", del_case("fix_owner_role"))
for label, name in (
    ("team", "Support team"), ("department", "Order operations department"), ("queue", "Support queue"),
    ("placeholder", "TBD"), ("generic function", "support"), ("blank", ""), ("number", 7),
    ("TBC placeholder", "TBC"), ("dash", "-"), ("nobody", "nobody"), ("unassigned", "Unassigned"),
    ("placeholder with a hint", "TBD - Priya?"), ("not assigned", "Not assigned yet"),
    ("squad", "Order squad"),
):
    add(0, f"fix_owner is a {label}", set_case("fix_owner", name))
add(0, "no fix_owner", del_case("fix_owner"))
add(0, "no cases", lambda r: r.__setitem__("regression_cases", []))
add(0, "no regression_cases key", lambda r: r.pop("regression_cases"))
add(0, "regression_cases is an object", lambda r: r.__setitem__("regression_cases", case(r)))
add(0, "one of two cases has no class",
    lambda r: (r["regression_cases"].append({**copy.deepcopy(case(r)), "id": "rc-2"}),
               r["regression_cases"][1].pop("failure_class")))

# Section 1: provenance and confirmations.
add(1, "production case with sanitisation_confirmed false", set_case("sanitisation_confirmed", False))
add(1, "sanitisation_confirmed missing", del_case("sanitisation_confirmed"))
add(1, "sanitisation_confirmed is the string true", set_case("sanitisation_confirmed", "true"))
add(1, "sanitisation_confirmed is 1", set_case("sanitisation_confirmed", 1))
add(1, "sanitisation_confirmed is null", set_case("sanitisation_confirmed", None))
add(1, "channel reuse not confirmed", set_case("channel_reuse_confirmed", False))
add(1, "channel reuse missing", del_case("channel_reuse_confirmed"))
add(1, "provenance authored on an intake case", set_case("provenance", "authored"))
add(1, "provenance missing", del_case("provenance"))
add(1, "provenance misspelled", set_case("provenance", "Production"))
add(1, "second case unsanitised",
    lambda r: (r["regression_cases"].append({**copy.deepcopy(case(r)), "id": "rc-2", "sanitisation_confirmed": False})))

# Section 2: identifiers and customer wording. Every dirty string must be caught in every prose field.
DIRTY = {
    "email": "Asks why jo.smith@example.com was charged twice for one order.",
    "plus-addressed email on a subdomain": "Asks to resend the receipt to j+tag@mail.example.co.uk.",
    "bracketed at": "Asks to resend the receipt to jo [at] example dot com.",
    "parenthesised at": "Asks to resend the receipt to jo(at)example.",
    "spelled-out email": "Asks to resend the receipt to jo at example dot com.",
    "international phone": "Asks to be called back on +44 7700 900123 about a late parcel.",
    "bracketed phone": "Asks to be called back on (555) 123-4567 about a late parcel.",
    "bare mobile": "Asks to be called back on 07700900123 about a late parcel.",
    "spaced landline": "Asks to be called back on 020 7946 0958 about a late parcel.",
    "dashed phone": "Asks to be called back on +1-555-123-4567 about a late parcel.",
    "dotted phone": "Asks to be called back on 555.123.4567 about a late parcel.",
    "order hash number": "Asks where order #482913 is.",
    "order number words": "Asks where order number 482913 is.",
    "order with no label": "Asks where order 482913 is.",
    "order code": "Asks where ORD-482913 is.",
    "order id": "Asks where order id 99213 is.",
    "account number": "Asks to close account 12345678.",
    "account code": "Asks to close acct AB-1234.",
    "customer id": "Asks to merge customer id 99213 with another profile.",
    "invoice code": "Asks to correct invoice INV-20231.",
    "ticket number": "Asks for an update on ticket #5521.",
    "booking reference": "Asks to move booking ref ZX-48213.",
    "bare hash number": "Asks about #482913.",
    "short hash number": "Asks about #4829.",
    "uuid": "Asks about 3f2b8c1e-5d4a-4e7b-9c1d-2a6f8e0b4c11.",
    "long digit run": "Asks about the parcel ending 482913.",
    "greeting with a name": "Dear Priya, asks where the parcel is.",
    "casual greeting with a name": "Hi Tom, asks where the parcel is.",
    "title with a name": "Ms Okafor asks where the parcel is.",
    "first person": "My parcel has not arrived and I was told it would.",
    "first person pronoun alone": "Asks what happens to me if the parcel is lost.",
    "braced at": "Asks to resend the receipt to jo{at}example.",
    "spaced email": "Asks to resend the receipt to jo . smith @ example . com.",
    "social handle": "Asks why @jo_smith was charged twice.",
    "glued order code": "Asks where ORD123456 is.",
    "glued reference code": "Asks about AB123456 on a returned item.",
    "multi-line transcript": "Customer asks where it is.\nAgent says it shipped.",
}
CLEAN = [
    "Asks for the delivery date of an order whose items shipped in two parcels with different carriers.",
    "The agent answered on 2026-10-03 using a graded sample of 5298 answers.",
    "Asks whether a returned item bought in a bundle of 3 is refunded in full within 14 days.",
    "The record shows a 12-month warranty, the policy page shows 24 months, and the agent quoted 24.",
    "About 3% of 200 graded answers (6 errors) were wrong, with a 95% interval of 1.4% to 6.4%.",
    "Two orders placed on the same day were merged into one reply.",
    "Order total of 49.99 euros was stated as 59.99 euros.",
    "Asks about 1,500 customers affected by a recall and whether each gets a refund.",
    "Asks whether a 2-year plan can be cancelled in the first 30 days of a 12-month term.",
    "Asks whether a gift bought in-store can be returned online, and the agent says yes without checking the policy.",
]
TEXT_FIELDS = {
    "question_shape": ["question_shape"],
    "scenario": ["scenario"],
    "finding": ["grading_evidence", "system_of_record_finding"],
    "fix description": ["fix", "description"],
}
for label, text in DIRTY.items():
    for field_label, field_path in TEXT_FIELDS.items():
        if label == "multi-line transcript" and field_label in ("finding", "fix description"):
            continue  # newlines are only forbidden in question_shape and scenario
        add(2, f"{label} in {field_label}", set_in(field_path, text))
add(2, "question_shape over 300 characters", set_case("question_shape", "Asks about a delayed parcel. " * 12))
add(2, "scenario over 800 characters", set_case("scenario", "The agent answered a delayed-parcel question. " * 20))
add(2, "question_shape is not a string", set_case("question_shape", ["Asks about a delayed parcel."]))
add(2, "no question_shape", del_case("question_shape"))
add(2, "identifier in a recommendation",
    lambda r: r["recommendations"][0].update(recommended_action="Email jo@example.com about the fix."))
add(2, "order number in a recommendation",
    lambda r: r["recommendations"][0].update(recommended_action="Append the case from order #482913."))
add(2, "identifier in the fix owner field", set_case("fix_owner", "jo@example.com"))
add(2, "identifier in the fix closer", set_in(["fix", "closed_by"], "Priya Nair on +44 7700 900123"))

# Section 3: what skill-model-bench loads.
add(3, "scenario missing", del_case("scenario"))
add(3, "scenario blank", set_case("scenario", "  "))
add(3, "scenario is not a string", set_case("scenario", ["text"]))
# The expected value is varied with violates_gate removed, so only the enum can reject it.
add(3, "expected missing", edit_case(lambda c: (c.pop("expected"), c.pop("violates_gate"))))
add(3, "expected is maybe", edit_case(lambda c: c.update(expected="maybe") or c.pop("violates_gate")))
add(3, "expected is capitalised", edit_case(lambda c: c.update(expected="Follow") or c.pop("violates_gate")))
add(3, "expected is a boolean", edit_case(lambda c: c.update(expected=True) or c.pop("violates_gate")))
add(3, "expected is violate", edit_case(lambda c: c.update(expected="violate")))
add(3, "violates without a violates_gate", del_case("violates_gate"))
add(3, "violates with a blank violates_gate", set_case("violates_gate", " "))
add(3, "violates with a non-string violates_gate", set_case("violates_gate", 5))
add(3, "follow that still carries a violates_gate", set_case("expected", "follow"))
add(3, "provenance outside the enum", set_case("provenance", "synthetic"))
add(3, "id missing", del_case("id"))
add(3, "id blank", set_case("id", ""))
add(3, "id is a number", set_case("id", 1))
add(3, "duplicate ids",
    lambda r: r["regression_cases"].append(copy.deepcopy(case(r))))
add(3, "case is not an object", lambda r: r.__setitem__("regression_cases", ["scenario text"]))
add(3, "no cases to load", lambda r: r.__setitem__("regression_cases", []))

# Section 4: grading evidence from 04.
add(4, "no grading evidence", del_case("grading_evidence"))
add(4, "grading evidence is prose", set_case("grading_evidence", "Confirmed by support."))
add(4, "no measurement id", del_in(["grading_evidence", "measurement_id"]))
add(4, "unknown measurement id", set_in(["grading_evidence", "measurement_id"], "m-not-there"))
add(4, "no measurements", lambda r: r.__setitem__("measurements", []))
add(4, "measurements missing", lambda r: r.pop("measurements"))
add(4, "duplicate measurement ids",
    lambda r: r["measurements"].append(copy.deepcopy(r["measurements"][0])))
add(4, "measurement is a ticket count", lambda r: r["measurements"][0].update(source="ticket_count"))
add(4, "measurement has no source", lambda r: r["measurements"][0].pop("source"))
add(4, "measurement has no sample size", lambda r: r["measurements"][0].pop("sample_size"))
add(4, "measurement has a zero sample size", lambda r: r["measurements"][0].update(sample_size=0))
add(4, "measurement has no rate", lambda r: r["measurements"][0].pop("error_rate"))
add(4, "measurement rate is a percentage", lambda r: r["measurements"][0].update(error_rate=3))
add(4, "measurement interval is Wald", lambda r: r["measurements"][0]["interval_bounds"].update(method="wald"))
add(4, "measurement has no interval", lambda r: r["measurements"][0].pop("interval_bounds"))
for label, text in (
    ("transcript", "conversation transcript"), ("log", "chat log"), ("the agent", "the agent's own output"),
    ("same model", "the same model that wrote the answer"), ("tickets", "support tickets"),
    ("blank", ""),
):
    add(4, f"measurement graded against {label}",
        lambda r, t=text: (r["measurements"][0].update(graded_against=t),
                           case(r)["grading_evidence"].update(graded_against=t)))
    add(4, f"case graded against {label}", set_in(["grading_evidence", "graded_against"], text))
add(4, "case graded_against differs from the measurement",
    set_in(["grading_evidence", "graded_against"], "returns system"))
add(4, "grader is a team", set_in(["grading_evidence", "grader"], "Quality team"))
add(4, "grader missing", del_in(["grading_evidence", "grader"]))
add(4, "finding missing", del_in(["grading_evidence", "system_of_record_finding"]))
add(4, "finding blank", set_in(["grading_evidence", "system_of_record_finding"], " "))

# Section 5: the fix and the measurement that shows it stayed closed.
add(5, "no fix", del_case("fix"))
add(5, "fix is prose", set_case("fix", "Fixed in the last release."))
add(5, "fix without a description", del_in(["fix", "description"]))
add(5, "fix with a blank description", set_in(["fix", "description"], " "))
add(5, "fix status outside the enum", set_in(["fix", "status"], "done"))
add(5, "fix status missing", del_in(["fix", "status"]))
add(5, "closed fix without closed_by", del_in(["fix", "closed_by"]))
add(5, "closed fix closed by a team", set_in(["fix", "closed_by"], "Platform team"))
add(5, "closed fix without a date", del_in(["fix", "closed_on"]))
add(5, "closed fix dated in the future", set_in(["fix", "closed_on"], iso(1)))
add(5, "closed fix with an impossible date", set_in(["fix", "closed_on"], "2026-02-31"))
add(5, "closed fix with the wrong date format", set_in(["fix", "closed_on"], "03/10/2026"))
add(5, "no verification measurement", del_case("verification_measurement"))
add(5, "verification measurement is prose",
    set_case("verification_measurement", "We will watch the dashboard."))
add(5, "verification reuses the detecting measurement",
    set_in(["verification_measurement", "planned_id"], "m-order-status-2026-w40"))
add(5, "verification has no planned id", del_in(["verification_measurement", "planned_id"]))
add(5, "verification has a blank planned id", set_in(["verification_measurement", "planned_id"], ""))
add(5, "verification is a uniform sample", set_in(["verification_measurement", "selection_method"], "uniform"))
add(5, "verification has no selection method", del_in(["verification_measurement", "selection_method"]))
add(5, "verification metric is ticket volume", set_in(["verification_measurement", "metric"], "ticket_volume"))
add(5, "verification has no metric", del_in(["verification_measurement", "metric"]))
add(5, "verification graded against a transcript",
    set_in(["verification_measurement", "graded_against"], "conversation transcript"))
add(5, "verification has no system of record", del_in(["verification_measurement", "graded_against"]))
add(5, "verification minimum sample size zero", set_in(["verification_measurement", "minimum_sample_size"], 0))
add(5, "verification minimum sample size fractional", set_in(["verification_measurement", "minimum_sample_size"], 2.5))
add(5, "verification minimum sample size is a string", set_in(["verification_measurement", "minimum_sample_size"], "200"))
add(5, "verification has no minimum sample size", del_in(["verification_measurement", "minimum_sample_size"]))

# Section 6: guardrails.
add(6, "applied recommendation", lambda r: r["recommendations"][0].update(execution_status="applied"))
add(6, "autonomous recommendation", lambda r: r["recommendations"][0].update(automation_level="3-Auto"))
add(6, "clear despite blocked guardrails", lambda r: r.__setitem__("guardrail_status", "BLOCK"))
add(6, "blocked guardrails with a clear status", lambda r: r.update(guardrail_status="BLOCK", status="CLEAR"))
add(6, "recommendations missing", lambda r: r.pop("recommendations"))
add(6, "unknown status", lambda r: r.__setitem__("status", "READY"))

positive_controls = []
all_sections = list(expected_sections)
loadable_only = [S[3]]


def second_case(**changes):
    def apply(r):
        extra = copy.deepcopy(case(r))
        extra.update(id="rc-order-status-0002", **changes)
        r["regression_cases"].append(extra)
    return apply


positive_controls.append(("a follow case with no violates_gate", all_sections,
    mutated(edit_case(lambda c: (c.update(expected="follow"), c.pop("violates_gate"))))))
positive_controls.append(("an open fix with no closing fields", all_sections,
    mutated(set_in(["fix"], {"description": "Source owner to correct the delivery-times page.", "status": "open"}))))
positive_controls.append(("one case per failure class, each fixed by its own role", all_sections,
    mutated(lambda r: r.__setitem__("regression_cases", [
        {**copy.deepcopy(valid_case), "id": f"rc-{n}", "failure_class": n, "fix_owner_role": role}
        for n, role in ROLE_FOR_CLASS.items()]))))
positive_controls.append(("specific on-call functions as fixers", all_sections,
    mutated(edit_case(lambda c: (c.update(fix_owner="delivery-content-on-call"),
                                 c["grading_evidence"].update(grader="order-quality-on-call"),
                                 c["fix"].update(closed_by="delivery-content-on-call"))))))
positive_controls.append(("oversampled verification and a fix closed today", all_sections,
    mutated(edit_case(lambda c: (c["verification_measurement"].update(selection_method="oversampled_new_classes",
                                                                       minimum_sample_size=1),
                                 c["fix"].update(closed_on=iso()))))))
positive_controls.append(("a fix closed in the past", all_sections,
    mutated(set_in(["fix", "closed_on"], iso(-30)))))
positive_controls.append(("a second measurement that is not the one used", all_sections,
    mutated(lambda r: r["measurements"].append({**copy.deepcopy(r["measurements"][0]), "id": "m-other"}))))
positive_controls.append(("a case with extra pack-only keys the bench ignores", all_sections,
    mutated(set_case("notes_for_operator", "Appended to the fixtures of the abstention skill."))))
positive_controls.append(("an authored provenance still loads in the bench shape", loadable_only,
    mutated(set_case("provenance", "authored"))))
positive_controls.append(("a failure class that names a first-person-free fix", all_sections,
    mutated(set_in(["fix", "description"], "Source owner corrects the delivery-times page and re-publishes it."))))
for clean in CLEAN:
    for field_label, field_path in TEXT_FIELDS.items():
        positive_controls.append((f"clean text in {field_label}: {clean[:40]}", all_sections,
                                  mutated(set_in(field_path, clean))))

for section, command in section_blocks.items():
    result = run_check(command, valid_report)
    if result.returncode != 0:
        failures.append(f"canonical valid report failed {section!r}: {result.stderr.strip()}")

for label, sections, report in positive_controls:
    for section in sections:
        result = run_check(section_blocks[section], report)
        if result.returncode != 0:
            failures.append(f"positive control {label!r} was rejected by {section!r}: {result.stderr.strip()}")

for label, section, report in negative_controls:
    result = run_check(section_blocks[section], report)
    if result.returncode == 0:
        failures.append(f"targeted invalid report passed {section!r}: {label}")
    elif result.returncode != 1:
        # jq -e exits 1 for a false result and 5 for a runtime error; only 1 is a real rejection.
        failures.append(f"targeted invalid report errored instead of failing {section!r}: {label}")

targeted = {section for _, section, _ in negative_controls}
for section in expected_sections:
    if section not in targeted:
        failures.append(f"no negative control targets {section!r}")

# Differential test against the bench reference: whenever the loadability check accepts a report,
# the reference loader accepts every case in it, and it never accepts what the loader rejects.
load_command = section_blocks[S[3]]
bench_probe_reports = [valid_report] + [report for _, section, report in negative_controls if section == S[3]]
for label, section, report in negative_controls:
    if section == S[3]:
        continue
    bench_probe_reports.append(report)
for report in bench_probe_reports:
    cases = report.get("regression_cases")
    jq_accepts = run_check(load_command, report).returncode == 0
    if jq_accepts:
        if not isinstance(cases, list) or not all(isinstance(c, dict) and bench_accepts(c) for c in cases):
            failures.append("loadability check accepted a report the skill-model-bench reference rejects")
for broken in ({k: v for k, v in valid_case.items() if k != "scenario"},):
    if bench_accepts(broken):
        failures.append("reference loader accepted a case with no scenario")
    try:
        bench_fixture_test_case(broken)
        failures.append("reference loader did not raise on a missing scenario")
    except ValueError:
        pass
extra_keys_case = {**valid_case, "unrelated_key": 1}
if bench_fixture_test_case(extra_keys_case)["vars"].keys() != bench_fixture_test_case(valid_case)["vars"].keys():
    failures.append("reference loader no longer ignores unknown keys")

# The exact valid case, written as a fixtures list, round-trips through the reference loader.
roundtrip = json.loads(json.dumps([valid_case]))
if bench_load_fixture_list(roundtrip) is None or not bench_accepts(roundtrip[0]):
    failures.append("a produced case does not round-trip into a bench fixture list")

# The example in SKILL.md must be a report the checks accept once its illustrative date is made
# current.
example = re.search(r"```json\n(.*?)\n```", raw_skill_md, re.DOTALL)
if not example:
    failures.append("SKILL.md has no JSON example")
else:
    try:
        example_report = json.loads(example.group(1))
    except json.JSONDecodeError as error:
        failures.append(f"SKILL.md example is not valid JSON: {error}")
    else:
        for example_case in example_report["regression_cases"]:
            example_case["fix"]["closed_on"] = iso()
            if not bench_accepts(example_case):
                failures.append("SKILL.md example case would not load in skill-model-bench")
        for section, command in section_blocks.items():
            if run_check(command, example_report).returncode != 0:
                failures.append(f"SKILL.md example failed {section!r}")

if failures:
    print("FAIL: 07-failure-to-regression-intake executable contract checks failed:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print(
    "PASS: 07-failure-to-regression-intake contract and executable checks passed "
    f"({len(section_blocks)} gates, {len(negative_controls)} negative controls, "
    f"{len(positive_controls)} positive controls, {len(DIRTY)} dirty and {len(CLEAN)} clean strings, "
    f"{len(fixtures)} held-out fixtures loadable by the bench reference)."
)
