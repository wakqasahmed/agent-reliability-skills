#!/usr/bin/env python3
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


skill_dir = Path(__file__).resolve().parents[1]
skill_path = skill_dir / "SKILL.md"
checks_path = skill_dir / "references" / "checks.md"
upstream_skill_path = skill_dir.parent / "04-accuracy-sampling-plan" / "SKILL.md"

try:
    raw_skill_md = skill_path.read_text(encoding="utf-8")
    raw_checks_md = checks_path.read_text(encoding="utf-8")
    raw_upstream_md = upstream_skill_path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as error:
    sys.exit(f"FAIL: unable to read contract files: {error}")

skill_md = " ".join(raw_skill_md.split())
checks_md = " ".join(raw_checks_md.split())

REQUIRED_SKILL_PHRASES = [
    "name: 05-error-budget-and-burn-alerting",
    "version: 1.0.0",
    "../00-agent-reliability-guardrails/SKILL.md",
    "does not page anyone, change a running agent, or stop an answer surface",
    "`04-accuracy-sampling-plan`",
    "error_budget",
    "derived_from",
    "baseline_status",
    "already_in_breach",
    "not_proven_in_breach",
    "interval_bounds.lower",
    "fast_burn",
    "slow_burn",
    "burn_rate",
    "short_window",
    "budget_consumed",
    "graded_answers_in_window",
    "pages",
    "exhaustion_policy",
    "recommended_stop",
    "decided_by",
    "fraction_of_answers",
    "percent_of_answers",
    "errors_per_1000_answers",
    "100% accuracy",
    "zero tolerance",
    "(gate 6)",
    "(gate 4)",
    "[SRC-SRE-BURN-RATE]",
    "execution_status",
    "not_applied",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    ".error_budget",
    ".derived_from",
    ".baseline_status",
    "already_in_breach",
    ".interval_bounds.lower",
    '"fast_burn"',
    '"slow_burn"',
    ".budget_consumed",
    ".graded_answers_in_window",
    ".pages",
    ".exhaustion_policy",
    ".decided_by",
    ".execution_status == \"not_applied\"",
    "[SRC-SRE-BURN-RATE]",
]

missing = []
for phrase in REQUIRED_SKILL_PHRASES:
    if phrase not in skill_md:
        missing.append(f"missing required skill phrase: {phrase!r}")
for phrase in REQUIRED_CHECK_PHRASES:
    if phrase not in checks_md:
        missing.append(f"missing required checks.md phrase: {phrase!r}")

if missing:
    print("FAIL: 05-error-budget-and-burn-alerting contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

expected_sections = [
    "The budget is non-zero, with a unit and a window",
    "The budget derives from a measurement and breach is reported",
    "Fast-burn and slow-burn alerts recompute and can be evaluated",
    "Every alert reaches a named person or on-call function",
    "The exhaustion policy is a recommendation with a named trigger and decider",
    "Guardrail status is preserved and changes remain non-autonomous",
    "No raw customer identifiers enter the plan",
]
section_blocks = dict(
    re.findall(r"^## (.+?)\n.*?^```bash\n(.*?)^```", raw_checks_md, re.MULTILINE | re.DOTALL)
)
if list(section_blocks) != expected_sections:
    sys.exit("FAIL: checks.md must contain exactly the seven documented executable check sections")

HOURS = {"h": 1, "d": 24, "w": 168}


def hours(window):
    return int(window[:-1]) * HOURS[window[-1]]


def consumed(burn_rate, window, budget_window):
    return burn_rate * hours(window) / hours(budget_window)


# The burn-rate arithmetic reproduces the chapter's recommended parameters for a 30-day SLO
# (14.4 over 1h = 2%, 6 over 6h = 5%, 1 over 3d = 10%).
statistics_failures = []
for burn, window, share in ((14.4, "1h", 0.02), (6, "6h", 0.05), (1, "3d", 0.10)):
    if abs(consumed(burn, window, "30d") - share) > 1e-9:
        statistics_failures.append(f"burn {burn} over {window} should consume {share} of a 30d budget")
# The SKILL.md example numbers.
if round(consumed(6, "1d", "28d"), 4) != 0.2143 or round(consumed(1, "7d", "28d"), 4) != 0.25:
    statistics_failures.append("SKILL.md example budget_consumed values do not recompute")
if statistics_failures:
    print("FAIL: 05-error-budget-and-burn-alerting arithmetic checks failed:")
    for failure in statistics_failures:
        print(f"  - {failure}")
    sys.exit(1)


# The measurement comes from skill 04's contract: reuse its documented example so a rename there
# breaks this eval instead of silently drifting.
upstream_example = json.loads(re.search(r"```json\n(.*?)\n```", raw_upstream_md, re.DOTALL).group(1))
upstream_measurement = upstream_example["measurements"][0]
MEASUREMENT_FIELDS = ("id", "error_rate", "sample_size", "interval", "interval_bounds")
shared_measurement = {field: upstream_measurement[field] for field in MEASUREMENT_FIELDS}
MEASUREMENT_ID = shared_measurement["id"]


def alert(kind, burn_rate, window, short_window, graded, pages, budget="28d", signal="Graded answers"):
    return {
        "kind": kind,
        "burn_rate": burn_rate,
        "window": window,
        "short_window": short_window,
        "budget_consumed": round(consumed(burn_rate, window, budget), 4),
        "graded_answers_in_window": graded,
        "signal": signal,
        "pages": pages,
        "action": "page" if kind == "fast_burn" else "open_ticket",
    }


valid_report = {
    "measurements": [shared_measurement],
    "error_budget": {
        "value": 0.04,
        "unit": "fraction_of_answers",
        "window": "28d",
        "derived_from": MEASUREMENT_ID,
        "baseline_status": "not_proven_in_breach",
    },
    "alerts": [
        alert("fast_burn", 6, "1d", "2h", 1500, "order-support-on-call",
              signal="Automated comparison of every answer to the order management system"),
        alert("slow_burn", 1, "7d", "2d", 200, "Priya Nair", signal="Weekly graded sample"),
    ],
    "exhaustion_policy": {
        "trigger": "Budget fully consumed inside the 28d window",
        "recommended_stop": "Recommend the operator restrict the surface to question classes still within budget and abstain on the rest",
        "decided_by": "Amina Shah",
        "automation_level": "2-HITL",
        "execution_status": "not_applied",
    },
    "recommendations": [
        {
            "recommended_action": "Route the fast-burn alert to the order-support on-call rota.",
            "automation_level": "1-Recommend",
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


def budget(report):
    return report["error_budget"]


def fast(report):
    return report["alerts"][0]


def slow(report):
    return report["alerts"][1]


def policy(report):
    return report["exhaustion_policy"]


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


# Section 0: zero budgets in every spelling, and a missing unit or window.
for label, value in (
    ("0", 0),
    ("0.0", 0.0),
    ("string 0", "0"),
    ("string 0%", "0%"),
    ("string zero", "zero"),
    ("string none", "none"),
    ("null", None),
    ("negative", -0.01),
    ("string 0.04", "0.04"),
    ("whole answer surface (1.0 as a fraction)", 1.0),
):
    add(0, f"budget value {label}", set_in(budget, "value", value))
add(0, "0 percent", lambda r: budget(r).update(value=0, unit="percent_of_answers"))
add(0, "0 errors per 1000", lambda r: budget(r).update(value=0, unit="errors_per_1000_answers"))
add(0, "100 percent", lambda r: budget(r).update(value=100, unit="percent_of_answers"))
add(0, "1000 errors per 1000", lambda r: budget(r).update(value=1000, unit="errors_per_1000_answers"))
add(0, "unit is 100% accuracy", set_in(budget, "unit", "100% accuracy"))
add(0, "unknown unit", set_in(budget, "unit", "per_user"))
add(0, "missing unit", delete_from(budget, "unit"))
add(0, "missing window", delete_from(budget, "window"))
add(0, "blank window", set_in(budget, "window", ""))
add(0, "window spelled in words", set_in(budget, "window", "monthly"))
add(0, "zero-length window", set_in(budget, "window", "0d"))
add(0, "no error_budget", lambda r: r.pop("error_budget"))
add(0, "error_budget is not an object", set_in(lambda r: r, "error_budget", "4%"))
for phrase in (
    "Target 100% accuracy on every order answer.",
    "The surface has zero tolerance for wrong answers.",
    "Zero errors allowed in the window.",
    "No errors are permitted.",
    "Set an error budget of zero.",
    "The agent must never be wrong.",
    "Aim for perfect accuracy.",
    "Budget is 0% errors.",
):
    add(0, f"zero target in prose: {phrase}",
        lambda r, phrase=phrase: r["recommendations"][0].update(recommended_action=phrase))

# Section 1: derivation and day-one breach.
add(1, "derived_from missing", delete_from(budget, "derived_from"))
add(1, "derived_from names no measurement", set_in(budget, "derived_from", "m-does-not-exist"))
add(1, "derived_from blank", set_in(budget, "derived_from", ""))
add(1, "no measurements", lambda r: r.pop("measurements"))
add(1, "empty measurements", set_in(lambda r: r, "measurements", []))
add(1, "duplicate measurement id", lambda r: r["measurements"].append(copy.deepcopy(r["measurements"][0])))
add(1, "measurement without interval_bounds", lambda r: r["measurements"][0].pop("interval_bounds"))
add(1, "measurement without sample_size", lambda r: r["measurements"][0].pop("sample_size"))
add(1, "baseline_status missing", delete_from(budget, "baseline_status"))
add(1, "budget below the lower bound accepted silently",
    lambda r: budget(r).update(value=0.01, baseline_status="not_proven_in_breach"))
add(1, "budget below the lower bound as a percentage accepted silently",
    lambda r: budget(r).update(value=1, unit="percent_of_answers", baseline_status="not_proven_in_breach"))
add(1, "budget below the lower bound in errors per 1000 accepted silently",
    lambda r: budget(r).update(value=10, unit="errors_per_1000_answers", baseline_status="not_proven_in_breach"))
add(1, "breach reported without a response",
    lambda r: budget(r).update(value=0.01, baseline_status="already_in_breach"))
add(1, "breach claimed for a budget above the lower bound",
    set_in(budget, "baseline_status", "already_in_breach"))
add(1, "unknown baseline status", set_in(budget, "baseline_status", "fine"))

# Section 2: alert structure and arithmetic.
add(2, "no alerts", lambda r: r.pop("alerts"))
add(2, "empty alerts", set_in(lambda r: r, "alerts", []))
add(2, "fast burn only", lambda r: r["alerts"].pop(1))
add(2, "slow burn only", lambda r: r["alerts"].pop(0))
add(2, "unknown alert kind", set_in(fast, "kind", "medium_burn"))
add(2, "fast burn only opens a ticket", set_in(fast, "action", "open_ticket"))
add(2, "slow burn pages", set_in(slow, "action", "page"))
add(2, "fast burn rate not above slow burn rate",
    lambda r: r["alerts"].__setitem__(0, alert("fast_burn", 1, "1d", "2h", 1500, "order-support-on-call")))
add(2, "fast window not shorter than slow window",
    lambda r: r["alerts"].__setitem__(0, alert("fast_burn", 6, "7d", "2d", 1500, "order-support-on-call")))
add(2, "short window not shorter than the long window",
    lambda r: r["alerts"].__setitem__(0, alert("fast_burn", 6, "1d", "1d", 1500, "order-support-on-call")))
add(2, "alert window longer than the budget window",
    lambda r: r["alerts"].__setitem__(1, alert("slow_burn", 1, "56d", "2d", 200, "Priya Nair")))
add(2, "budget_consumed does not recompute", set_in(fast, "budget_consumed", 0.05))
add(2, "budget_consumed missing", delete_from(fast, "budget_consumed"))
add(2, "alert that would only fire after the budget is gone",
    lambda r: r["alerts"].__setitem__(1, alert("slow_burn", 2, "28d", "7d", 5000, "Priya Nair")))
add(2, "too few graded answers: one bad answer can trip the fast burn", set_in(fast, "graded_answers_in_window", 10))
add(2, "just under the five-expected-error floor", set_in(fast, "graded_answers_in_window", 20))
add(2, "graded_answers_in_window missing", delete_from(fast, "graded_answers_in_window"))
add(2, "graded_answers_in_window not an integer", set_in(fast, "graded_answers_in_window", 1500.5))
add(2, "signal missing", delete_from(fast, "signal"))
add(2, "window spelled in words", set_in(fast, "window", "1 day"))
add(2, "short window missing", delete_from(fast, "short_window"))
add(2, "burn rate zero", set_in(fast, "burn_rate", 0))
add(2, "burn rate as a string", set_in(fast, "burn_rate", "6"))

# Section 3: named recipients.
for label, name in (
    ("team name", "platform team"),
    ("queue", "support queue"),
    ("distribution list", "support distribution list"),
    ("slack channel", "#support-alerts"),
    ("mailing list", "orders mailing list"),
    ("everyone", "everyone"),
    ("placeholder", "TBD"),
    ("bare function", "support"),
    ("bare on-call", "on-call"),
    ("blank", ""),
):
    add(3, f"fast burn pages a {label}", set_in(fast, "pages", name))
add(3, "slow burn reaches a team", set_in(slow, "pages", "Support team"))
add(3, "slow burn reaches nobody", delete_from(slow, "pages"))
add(3, "pages is not a string", set_in(fast, "pages", ["order-support-on-call"]))

# Section 4: exhaustion policy.
add(4, "no exhaustion policy", lambda r: r.pop("exhaustion_policy"))
add(4, "no trigger", delete_from(policy, "trigger"))
add(4, "placeholder trigger", set_in(policy, "trigger", "TBD"))
add(4, "no recommended_stop", delete_from(policy, "recommended_stop"))
add(4, "blank recommended_stop", set_in(policy, "recommended_stop", " "))
add(4, "no decider", delete_from(policy, "decided_by"))
add(4, "decider is a team", set_in(policy, "decided_by", "the leadership team"))
add(4, "decider is a placeholder", set_in(policy, "decided_by", "TBD"))
add(4, "autonomous automation level", set_in(policy, "automation_level", "3-Auto"))
add(4, "applied policy", set_in(policy, "execution_status", "applied"))
add(4, "missing execution status", delete_from(policy, "execution_status"))
for phrase in (
    "Automatically disable the answer surface",
    "Auto-pause the surface when the budget is gone",
    "Shut the surface down without operator approval",
    "Kill switch triggered when the budget reaches zero",
):
    add(4, f"automatic action in wording: {phrase}", set_in(policy, "recommended_stop", phrase))
add(4, "automatic trigger wording", set_in(policy, "trigger", "Budget fully consumed, then the surface stops automatically"))

# Section 5: guardrails.
add(5, "applied recommendation", lambda r: r["recommendations"][0].update(execution_status="applied"))
add(5, "autonomous recommendation", lambda r: r["recommendations"][0].update(automation_level="4-Auto"))
add(5, "ready despite blocked guardrails", set_in(lambda r: r, "guardrail_status", "BLOCK"))
add(5, "ready despite a day-one breach",
    lambda r: budget(r).update(value=0.01, baseline_status="already_in_breach",
                               breach_response="Re-baseline with the accuracy owner"))
add(5, "recommendations missing", lambda r: r.pop("recommendations"))

# Section 6: privacy.
add(6, "customer email in the plan",
    lambda r: fast(r).update(signal="Tickets from jo@example.com about delivery"))
add(6, "order number in the plan",
    lambda r: slow(r).update(signal="Order #482913 as the example"))

positive_controls = []
all_sections = list(expected_sections)


def report_with(change):
    report = copy.deepcopy(valid_report)
    change(report)
    return report


positive_controls.append((
    "day-one breach is reported and blocked", all_sections,
    report_with(lambda r: (
        budget(r).update(value=0.01, baseline_status="already_in_breach",
                         breach_response="Re-baseline against a larger sample or fund remediation; accuracy owner decides"),
        r.update(status="BLOCK"),
        r["alerts"].__setitem__(0, alert("fast_burn", 6, "1d", "2h", 4000, "order-support-on-call")),
        r["alerts"].__setitem__(1, alert("slow_burn", 1, "7d", "2d", 1000, "Priya Nair")),
    )),
))
positive_controls.append((
    "percent unit", all_sections,
    report_with(lambda r: budget(r).update(value=4, unit="percent_of_answers")),
))
positive_controls.append((
    "errors per 1000 unit", all_sections,
    report_with(lambda r: budget(r).update(value=40, unit="errors_per_1000_answers")),
))
positive_controls.append((
    "budget exactly at the lower bound is not a breach", all_sections,
    report_with(lambda r: (
        budget(r).update(value=0.0138),
        r["alerts"].__setitem__(0, alert("fast_burn", 6, "1d", "2h", 4000, "order-support-on-call")),
        r["alerts"].__setitem__(1, alert("slow_burn", 1, "7d", "2d", 1000, "Priya Nair")),
    )),
))
positive_controls.append((
    "two fast burns and one slow burn", all_sections,
    report_with(lambda r: r["alerts"].insert(
        1, alert("fast_burn", 3, "3d", "6h", 2000, "order-support-on-call", signal="Automated comparison"))),
))
positive_controls.append((
    "ninety day budget window", all_sections,
    report_with(lambda r: (
        budget(r).update(window="90d"),
        r["alerts"].__setitem__(0, alert("fast_burn", 6, "1d", "2h", 1500, "order-support-on-call", "90d")),
        r["alerts"].__setitem__(1, alert("slow_burn", 1, "7d", "2d", 200, "Priya Nair", "90d")),
    )),
))
positive_controls.append((
    "recommendation that merely names the zero-budget rule", all_sections,
    report_with(lambda r: r["recommendations"][0].update(
        recommended_action="Keep the budget non-zero and tied to the measurement.")),
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

# The example in SKILL.md must be a report the checks accept, and its measurement must be skill
# 04's measurement, field for field.
example = re.search(r"```json\n(.*?)\n```", raw_skill_md, re.DOTALL)
if not example:
    failures.append("SKILL.md has no JSON example")
else:
    try:
        example_report = json.loads(example.group(1))
    except json.JSONDecodeError as error:
        failures.append(f"SKILL.md example is not valid JSON: {error}")
    else:
        if example_report["measurements"] != [shared_measurement]:
            failures.append("SKILL.md measurement differs from the 04-accuracy-sampling-plan example")
        for section, command in section_blocks.items():
            if run_check(command, example_report).returncode != 0:
                failures.append(f"SKILL.md example failed {section!r}")

if failures:
    print("FAIL: 05-error-budget-and-burn-alerting executable contract checks failed:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print(
    "PASS: 05-error-budget-and-burn-alerting contract and executable checks passed "
    f"({len(section_blocks)} gates, {len(negative_controls)} negative controls, "
    f"{len(positive_controls)} positive controls)."
)
