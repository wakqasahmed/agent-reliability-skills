#!/usr/bin/env python3
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
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
    "name: 06-accuracy-ownership-separation",
    "version: 1.0.0",
    "../00-agent-reliability-guardrails/SKILL.md",
    "does not change a running agent, a threshold, a routing rule or anyone's reporting line",
    "not a veto",
    "`threshold_owner`",
    "`03-abstention-policy-design`",
    "accuracy_owner",
    "coverage_owner",
    "accuracy_owner_authority",
    "coverage_owner_authority",
    "escalation_path",
    "accuracy_requirement_stands",
    "review_cadence",
    "require_abstention_on_question_class",
    "without the coverage owner's agreement",
    "can only file an opinion",
    "punctuation stripped, parenthetical suffixes removed, whitespace collapsed, lowercased",
    '`"Support quality lead"`',
    '`"Support quality lead."`',
    '`"Support quality lead (support)"`',
    "retrieval_test[]",
    "scope_and_refusal",
    "input_list_with_acknowledgement_dates",
    "budget_with_sample_size",
    "alert_recipient_name",
    "seconds_to_find",
    "longer than a minute",
    "(gate 6)",
    "(gate 4)",
    "[SRC-SR-26-2]",
    "execution_status",
    "not_applied",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    ".ownership.accuracy_owner",
    ".ownership.coverage_owner",
    ".accuracy_owner_authority",
    ".coverage_owner_authority",
    "require_abstention_on_question_class",
    ".escalation_path",
    "accuracy_requirement_stands",
    ".review_cadence",
    ".retrieval_test",
    "seconds_to_find",
    ".execution_status == \"not_applied\"",
    "[SRC-SR-26-2]",
]

missing = []
for phrase in REQUIRED_SKILL_PHRASES:
    if phrase not in skill_md:
        missing.append(f"missing required skill phrase: {phrase!r}")
for phrase in REQUIRED_CHECK_PHRASES:
    if phrase not in checks_md:
        missing.append(f"missing required checks.md phrase: {phrase!r}")

if missing:
    print("FAIL: 06-accuracy-ownership-separation contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

expected_sections = [
    "Two distinct named roles",
    "The accuracy owner can require abstention without agreement, and neither owner holds a veto",
    "Disagreement has a named escalation path and the accuracy requirement stands meanwhile",
    "The split has a reviewer who is neither owner and a review date",
    "The one-minute retrieval test is a checkable list",
    "Guardrail status is preserved and changes remain non-autonomous",
    "No raw customer identifiers enter the record",
]
section_blocks = dict(
    re.findall(r"^## (.+?)\n.*?^```bash\n(.*?)^```", raw_checks_md, re.MULTILINE | re.DOTALL)
)
if list(section_blocks) != expected_sections:
    sys.exit("FAIL: checks.md must contain exactly the seven documented executable check sections")


def iso(days=0):
    return (utc_today + timedelta(days=days)).isoformat()


def normalise(role):
    """Reference implementation of the documented normalisation, compared with whitespace removed."""
    role = re.sub(r"[A-Z]", lambda m: m.group(0).lower(), role)
    role = re.sub(r"\([^)]*\)", "", role)
    role = "".join(c for c in role if unicodedata.category(c)[0] in "LN" or c.isspace())
    return "".join(role.split())


# The three cases named by the issue are one role; a distinct role is not.
statistics_failures = []
for equal in ("Support quality lead.", "Support quality lead (support)", "  SUPPORT   quality lead "):
    if normalise(equal) != normalise("Support quality lead"):
        statistics_failures.append(f"{equal!r} should normalise to the same role")
if normalise("Support quality lead") == normalise("Self-service product lead"):
    statistics_failures.append("distinct roles collapsed")
if statistics_failures:
    print("FAIL: 06-accuracy-ownership-separation normalisation checks failed:")
    for failure in statistics_failures:
        print(f"  - {failure}")
    sys.exit(1)


def retrieval_items():
    return [
        {
            "id": "scope_and_refusal",
            "location": "Answer surface definition, section 1",
            "points_to": ["answer_surface.scope_statement", "answer_surface.refusal_rule"],
            "found": True,
            "seconds_to_find": 20,
            "checked_on": iso(),
        },
        {
            "id": "input_list_with_acknowledgement_dates",
            "location": "Input exposure inventory, source table",
            "points_to": ["source_registry", "owner_acknowledgements.acknowledged_at"],
            "found": True,
            "seconds_to_find": 35,
            "checked_on": iso(),
        },
        {
            "id": "budget_with_sample_size",
            "location": "Error budget page, first screen",
            "points_to": ["error_budget", "measurements.sample_size"],
            "found": True,
            "seconds_to_find": 25,
            "checked_on": iso(),
        },
        {
            "id": "alert_recipient_name",
            "location": "On-call rota, order support",
            "points_to": ["alerts.pages"],
            "found": True,
            "seconds_to_find": 15,
            "checked_on": iso(),
        },
    ]


valid_report = {
    "ownership": {
        "accuracy_owner": "Support quality lead",
        "coverage_owner": "Self-service product lead",
        "accuracy_owner_authority": [
            "require_abstention_on_question_class",
            "set_answer_bar",
            "require_regression_case",
        ],
        "coverage_owner_authority": [
            "prioritise_input_fixes",
            "expand_scope_within_the_bar",
            "propose_answer_bar_change",
        ],
        "escalation_path": {
            "escalates_to": "Head of customer operations",
            "trigger": "The owners disagree about a question class after one working session",
            "decision_within_days": 5,
            "interim_rule": "accuracy_requirement_stands",
        },
        "review_cadence": {
            "interval_days": 90,
            "reviewer": "Chief of staff, operations",
            "next_review": iso(90),
        },
    },
    "retrieval_test": retrieval_items(),
    "recommendations": [
        {
            "recommended_action": "Have an operator record the accuracy owner's abstention requirement for the returns question class.",
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


def own(report):
    return report["ownership"]


def accuracy_authority(report):
    return own(report)["accuracy_owner_authority"]


def escalation(report):
    return own(report)["escalation_path"]


def review(report):
    return own(report)["review_cadence"]


def item(report, identifier):
    return next(entry for entry in report["retrieval_test"] if entry["id"] == identifier)


def set_in(getter, key, value):
    def change(report):
        getter(report)[key] = value
    return change


def delete_from(getter, key):
    def change(report):
        del getter(report)[key]
    return change


S = expected_sections
negative_controls = []


def add(section, label, change):
    negative_controls.append((label, S[section], mutated(change)))


# Section 0: equal and non-role owners.
for label, other in (
    ("identical", "Support quality lead"),
    ("trailing punctuation", "Support quality lead."),
    ("parenthetical suffix", "Support quality lead (support)"),
    ("parenthetical with punctuation", "Support quality lead. (Support team)"),
    ("case and whitespace", "  SUPPORT   quality   LEAD "),
    ("internal punctuation", "Support, quality - lead"),
    ("hyphen against space", "Support-quality lead"),
    ("every normalisation at once", "support QUALITY lead. (support)"),
):
    add(0, f"coverage owner equals accuracy owner: {label}", set_in(own, "coverage_owner", other))
add(0, "accuracy owner is the variant, coverage owner the base",
    lambda r: own(r).update(accuracy_owner="Support quality lead (support)", coverage_owner="support quality lead."))
add(0, "on-call function names equal after normalisation",
    lambda r: own(r).update(accuracy_owner="Order-support on-call", coverage_owner="order support on call."))
for label, name in (
    ("team", "Support team"),
    ("department", "Customer operations department"),
    ("group", "Quality group"),
    ("queue", "Support queue"),
    ("committee", "Quality committee"),
    ("squad", "Support squad"),
    ("organisation", "Support organisation"),
    ("distribution list", "Support distribution list"),
    ("placeholder", "TBD"),
    ("generic function", "support"),
    ("generic on-call", "on-call"),
    ("blank", ""),
    ("only a parenthetical", "(support)"),
):
    add(0, f"accuracy owner is a {label}", set_in(own, "accuracy_owner", name))
    add(0, f"coverage owner is a {label}", set_in(own, "coverage_owner", name))
add(0, "accuracy owner missing", delete_from(own, "accuracy_owner"))
add(0, "coverage owner missing", delete_from(own, "coverage_owner"))
add(0, "owners given as a list", set_in(own, "accuracy_owner", ["Support quality lead"]))
add(0, "no ownership at all", lambda r: r.pop("ownership"))

# Section 1: authority.
add(1, "accuracy owner cannot require abstention", set_in(own, "accuracy_owner_authority", ["set_answer_bar"]))
add(1, "accuracy owner can only advise", set_in(own, "accuracy_owner_authority", ["advise_only"]))
add(1, "accuracy owner can only file an opinion", set_in(own, "accuracy_owner_authority", ["file_opinion"]))
add(1, "abstention requires the coverage owner's agreement",
    set_in(own, "accuracy_owner_authority", ["require_abstention_with_coverage_owner_agreement"]))
add(1, "empty accuracy authority", set_in(own, "accuracy_owner_authority", []))
add(1, "accuracy authority missing", delete_from(own, "accuracy_owner_authority"))
add(1, "accuracy authority is prose",
    set_in(own, "accuracy_owner_authority", "Can require abstention on a question class"))
add(1, "duplicate accuracy authority",
    set_in(own, "accuracy_owner_authority", ["require_abstention_on_question_class", "require_abstention_on_question_class"]))
add(1, "accuracy authority with an unknown value",
    lambda r: accuracy_authority(r).append("close_the_surface"))
for veto in ("veto_abstention", "override_abstention", "block_abstention", "approve_abstention"):
    add(1, f"coverage owner holds {veto}", lambda r, veto=veto: own(r)["coverage_owner_authority"].append(veto))
add(1, "coverage authority missing", delete_from(own, "coverage_owner_authority"))
add(1, "empty coverage authority", set_in(own, "coverage_owner_authority", []))

# Section 2: escalation.
add(2, "no escalation path", delete_from(own, "escalation_path"))
add(2, "escalation path is prose", set_in(own, "escalation_path", "Escalate to the VP"))
add(2, "escalates to the accuracy owner", set_in(escalation, "escalates_to", "Support quality lead."))
add(2, "escalates to the coverage owner", set_in(escalation, "escalates_to", "Self-service product lead (product)"))
add(2, "escalates to a team", set_in(escalation, "escalates_to", "Operations leadership team"))
add(2, "escalates to nobody", delete_from(escalation, "escalates_to"))
add(2, "blank trigger", set_in(escalation, "trigger", " "))
add(2, "no deadline", delete_from(escalation, "decision_within_days"))
add(2, "zero-day deadline", set_in(escalation, "decision_within_days", 0))
add(2, "open-ended deadline", set_in(escalation, "decision_within_days", 31))
add(2, "fractional deadline", set_in(escalation, "decision_within_days", 2.5))
add(2, "deadline as a string", set_in(escalation, "decision_within_days", "5"))
add(2, "coverage agreement required in the meantime", set_in(escalation, "interim_rule", "coverage_agreement_required"))
add(2, "requirement suspended while escalated", set_in(escalation, "interim_rule", "requirement_suspended"))
add(2, "no interim rule", delete_from(escalation, "interim_rule"))

# Section 3: review.
add(3, "no review cadence", delete_from(own, "review_cadence"))
add(3, "reviewer is the accuracy owner", set_in(review, "reviewer", "Support quality lead (support)"))
add(3, "reviewer is the coverage owner", set_in(review, "reviewer", "self-service product lead."))
add(3, "reviewer is a team", set_in(review, "reviewer", "Operations team"))
add(3, "reviewer is a placeholder", set_in(review, "reviewer", "TBD"))
add(3, "no reviewer", delete_from(review, "reviewer"))
add(3, "review date in the past", set_in(review, "next_review", iso(-1)))
add(3, "impossible review date", set_in(review, "next_review", "2027-02-31"))
add(3, "review date in the wrong format", set_in(review, "next_review", "15/01/2027"))
add(3, "no review date", delete_from(review, "next_review"))
add(3, "zero-day interval", set_in(review, "interval_days", 0))
add(3, "interval of several years", set_in(review, "interval_days", 1000))
add(3, "interval as a string", set_in(review, "interval_days", "90"))

# Section 4: retrieval test.
add(4, "retrieval test written as prose",
    set_in(lambda r: r, "retrieval_test", "Everything is on the wiki and takes about a minute to find."))
add(4, "no retrieval test", lambda r: r.pop("retrieval_test"))
add(4, "empty retrieval test", set_in(lambda r: r, "retrieval_test", []))
for identifier in ("scope_and_refusal", "input_list_with_acknowledgement_dates", "budget_with_sample_size", "alert_recipient_name"):
    add(4, f"item missing: {identifier}",
        lambda r, identifier=identifier: r["retrieval_test"].remove(item(r, identifier)))
    add(4, f"item not found: {identifier}",
        lambda r, identifier=identifier: item(r, identifier).update(found=False))
    add(4, f"item takes 61 seconds: {identifier}",
        lambda r, identifier=identifier: item(r, identifier).update(seconds_to_find=61))
    add(4, f"item has no timing: {identifier}",
        lambda r, identifier=identifier: item(r, identifier).pop("seconds_to_find"))
    add(4, f"item points at nothing: {identifier}",
        lambda r, identifier=identifier: item(r, identifier).update(points_to=[]))
add(4, "duplicate item", lambda r: r["retrieval_test"].append(copy.deepcopy(r["retrieval_test"][0])))
add(4, "unknown extra item", lambda r: r["retrieval_test"].append({**copy.deepcopy(r["retrieval_test"][0]), "id": "everything_else"}))
add(4, "item takes zero seconds", lambda r: item(r, "scope_and_refusal").update(seconds_to_find=0))
add(4, "item has a future check date", lambda r: item(r, "scope_and_refusal").update(checked_on=iso(1)))
add(4, "item has an impossible check date", lambda r: item(r, "scope_and_refusal").update(checked_on="2026-02-31"))
add(4, "item has no check date", lambda r: item(r, "scope_and_refusal").pop("checked_on"))
add(4, "item has a blank location", lambda r: item(r, "budget_with_sample_size").update(location=" "))
add(4, "item has a placeholder location", lambda r: item(r, "budget_with_sample_size").update(location="TBD"))
add(4, "budget item omits the sample size",
    lambda r: item(r, "budget_with_sample_size").update(points_to=["error_budget"]))
add(4, "input item omits the acknowledgement dates",
    lambda r: item(r, "input_list_with_acknowledgement_dates").update(points_to=["source_registry"]))
add(4, "scope item omits the refusal rule",
    lambda r: item(r, "scope_and_refusal").update(points_to=["answer_surface.scope_statement"]))
add(4, "found is a string", lambda r: item(r, "scope_and_refusal").update(found="yes"))

# Section 5: guardrails.
add(5, "applied recommendation", lambda r: r["recommendations"][0].update(execution_status="applied"))
add(5, "autonomous recommendation", lambda r: r["recommendations"][0].update(automation_level="3-Auto"))
add(5, "ready despite blocked guardrails", set_in(lambda r: r, "guardrail_status", "BLOCK"))

# Section 6: privacy.
add(6, "customer email in the record",
    lambda r: escalation(r).update(trigger="Escalate when jo@example.com complains twice"))
add(6, "order number in the record",
    lambda r: item(r, "scope_and_refusal").update(location="Wiki page for order #482913"))

positive_controls = []
all_sections = list(expected_sections)


def report_with(change):
    return mutated(change)


positive_controls.append((
    "owners with a parenthetical but different roles", all_sections,
    report_with(lambda r: own(r).update(accuracy_owner="Support quality lead (support)",
                                        coverage_owner="Self-service product lead (support)")),
))
positive_controls.append((
    "specific on-call functions", all_sections,
    report_with(lambda r: own(r).update(accuracy_owner="order-support-accuracy-on-call",
                                        coverage_owner="order-support-coverage-on-call")),
))
positive_controls.append((
    "non-ASCII names that differ", all_sections,
    report_with(lambda r: own(r).update(accuracy_owner="Zoë Müller", coverage_owner="Zoé Müller")),
))
positive_controls.append((
    "boundary values", all_sections,
    report_with(lambda r: (
        escalation(r).update(decision_within_days=30),
        review(r).update(interval_days=366, next_review=iso()),
        [entry.update(seconds_to_find=60, checked_on=iso()) for entry in r["retrieval_test"]],
    )),
))
positive_controls.append((
    "minimal accuracy authority and full coverage authority", all_sections,
    report_with(lambda r: own(r).update(
        accuracy_owner_authority=["require_abstention_on_question_class"],
        coverage_owner_authority=["prioritise_input_fixes", "expand_scope_within_the_bar",
                                  "propose_answer_bar_change", "request_abstention_review"])),
))
positive_controls.append((
    "all accuracy authority values", all_sections,
    report_with(lambda r: own(r).update(accuracy_owner_authority=[
        "require_abstention_on_question_class", "set_answer_bar", "approve_answer_bar_change", "require_regression_case"])),
))

failures = []
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

# Differential test: the jq normalisation agrees with the reference implementation on every pair.
role_pairs = [
    ("Support quality lead", "Support quality lead"),
    ("Support quality lead", "Support quality lead."),
    ("Support quality lead", "Support quality lead (support)"),
    ("Support quality lead", "support  QUALITY lead"),
    ("Support quality lead", "Support-quality lead"),
    ("Support quality lead", "Support quality leader"),
    ("Support quality lead", "Self-service product lead"),
    ("Amina Shah", "Amina-Shah"),
    ("Amina Shah", "Omar Khan"),
    ("order-support-on-call", "order support on call"),
    ("order-support-on-call", "returns-support-on-call"),
    ("Zoë Müller", "Zoe Muller"),
    ("Zoë Müller", "Zoë Müller."),
]
for first_role, second_role in role_pairs:
    report = mutated(lambda r: own(r).update(accuracy_owner=first_role, coverage_owner=second_role))
    passed = run_check(section_blocks[S[0]], report).returncode == 0
    reference_distinct = normalise(first_role) != normalise(second_role)
    if passed != reference_distinct:
        failures.append(f"jq and reference normalisation disagree on {first_role!r} vs {second_role!r}")

# The example in SKILL.md must be a report the checks accept once its illustrative dates are made
# current, and its retrieval items must be the same four the checks require.
example = re.search(r"```json\n(.*?)\n```", raw_skill_md, re.DOTALL)
if not example:
    failures.append("SKILL.md has no JSON example")
else:
    try:
        example_report = json.loads(example.group(1))
    except json.JSONDecodeError as error:
        failures.append(f"SKILL.md example is not valid JSON: {error}")
    else:
        example_report["ownership"]["review_cadence"]["next_review"] = iso(90)
        for entry in example_report["retrieval_test"]:
            entry["checked_on"] = iso()
        for section, command in section_blocks.items():
            if run_check(command, example_report).returncode != 0:
                failures.append(f"SKILL.md example failed {section!r}")

if failures:
    print("FAIL: 06-accuracy-ownership-separation executable contract checks failed:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print(
    "PASS: 06-accuracy-ownership-separation contract and executable checks passed "
    f"({len(section_blocks)} gates, {len(negative_controls)} negative controls, "
    f"{len(positive_controls)} positive controls, {len(role_pairs)} normalisation pairs)."
)
