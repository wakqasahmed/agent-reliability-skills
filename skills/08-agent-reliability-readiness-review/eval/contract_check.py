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
skills_root = skill_dir.parent
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
    "name: 08-agent-reliability-readiness-review",
    "version: 1.0.0",
    "../00-agent-reliability-guardrails/SKILL.md",
    "does not change a running agent, prompt, retrieval configuration, abstention threshold or routing rule",
    "`surface_state`",
    "`no_surface_yet`",
    "`about_to_ship`",
    "`live`",
    "`readiness.retrieval_test[]`",
    "`06-accuracy-ownership-separation`",
    "`present`",
    "`evidence`",
    "`points_to`",
    "`readiness.retrieved`",
    "`missing[]`",
    "`owning_skill`",
    "`retrieval_item`",
    "`readiness.status`",
    "`READY`",
    "`HOLD`",
    "`CLEAR`",
    "`BLOCK`",
    "`guardrail_status`",
    "An unnamed accuracy owner",
    "so `READY` is impossible without one",
    "`readiness.commerce_delegation.storefront`",
    "[`agentic-commerce-skills`](https://github.com/wakqasahmed/agentic-commerce-skills)",
    "`answered_here`",
    "`readiness-audit`",
    "(gate 1)",
    "(gate 2)",
    "(gate 4)",
    "(gate 6)",
    "execution_status",
    "not_applied",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    ".readiness",
    ".surface_state",
    ".route",
    ".retrieval_test",
    ".points_to",
    ".retrieved",
    ".missing",
    ".owning_skill",
    ".retrieval_item",
    "accuracy_owner",
    "06-accuracy-ownership-separation",
    ".commerce_delegation",
    "agentic-commerce-skills",
    ".answered_here",
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
    print("FAIL: 08-agent-reliability-readiness-review contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

expected_sections = [
    "The surface state is set and the route follows its order of work",
    "The four retrieval items are listed once each, with evidence and real contract fields",
    "A present item is backed by what was retrieved",
    "Every item that is not present names the missing artefact and the skill that produces it",
    "READY is impossible with anything missing or an unnamed accuracy owner",
    "Commerce concerns are delegated, not answered here",
    "Guardrail status is preserved and changes remain non-autonomous",
    "No raw customer identifiers enter the record",
]
section_blocks = dict(
    re.findall(r"^## (.+?)\n.*?^```bash\n(.*?)^```", raw_checks_md, re.MULTILINE | re.DOTALL)
)
if list(section_blocks) != expected_sections:
    sys.exit("FAIL: checks.md must contain exactly the eight documented executable check sections")

failures = []

# The skills the router names are real directories in this pack.
skill_dirs = {path.name for path in skills_root.iterdir() if (path / "SKILL.md").is_file()}
by_number = {name[:2]: name for name in skill_dirs}
for number in ("01", "02", "03", "04", "05", "06", "07"):
    if number not in by_number:
        failures.append(f"skill {number} does not exist in this pack")


def full(number):
    return by_number[number]


ORDERS = {
    "no_surface_yet": ["01", "02", "03", "06", "04", "05", "07"],
    "about_to_ship": ["01", "02", "04", "05", "06", "03", "07"],
    "live": ["04", "05", "06", "01", "02", "03", "07"],
}
CATALOGUE = {
    "scope_statement": ("01", "scope_and_refusal"),
    "refusal_rule": ("01", "scope_and_refusal"),
    "source_registry": ("02", "input_list_with_acknowledgement_dates"),
    "owner_acknowledgements": ("02", "input_list_with_acknowledgement_dates"),
    "error_budget": ("05", "budget_with_sample_size"),
    "sample_size": ("04", "budget_with_sample_size"),
    "alert_recipient": ("05", "alert_recipient_name"),
    "accuracy_owner": ("06", None),
}
REQUIRED_POINTS = {
    "scope_and_refusal": ["answer_surface.scope_statement", "answer_surface.refusal_rule"],
    "input_list_with_acknowledgement_dates": ["source_registry", "owner_acknowledgements.acknowledged_at"],
    "budget_with_sample_size": ["error_budget", "measurements.sample_size"],
    "alert_recipient_name": ["alerts.pages"],
}
ITEM_IDS = list(REQUIRED_POINTS)

# SKILL.md tables must say what the checks enforce.
order_rows = dict(re.findall(r"^[ \t]*\| `(no_surface_yet|about_to_ship|live)` \| ([^|\n]+) \|", raw_skill_md, re.MULTILINE))
parsed_orders = {state: re.findall(r"`(\d\d)`", cell) for state, cell in order_rows.items()}
if parsed_orders != ORDERS:
    failures.append(f"SKILL.md order-of-work table {parsed_orders!r} does not match the enforced orders")
artefact_rows = re.findall(r"^[ \t]*\| `(\w+)` \| `(\d\d)-[a-z0-9-]+` \| (`\w+`|none) \|", raw_skill_md, re.MULTILINE)
parsed_catalogue = {a: (n, None if i == "none" else i.strip("`")) for a, n, i in artefact_rows}
if parsed_catalogue != CATALOGUE:
    failures.append(f"SKILL.md artefact table {parsed_catalogue!r} does not match the enforced catalogue")
for artefact, (number, _) in CATALOGUE.items():
    if f'"{artefact}": ["{full(number)}"' not in raw_checks_md:
        failures.append(f"checks.md does not enforce {artefact!r} -> {full(number)!r}")
for state, numbers in ORDERS.items():
    expected_row = ", ".join(f'"{full(n)}"' for n in numbers)
    if expected_row not in raw_checks_md:
        failures.append(f"checks.md does not enforce the {state!r} order")

# Every contract field the items point to exists in the skill that defines it.
FIELD_OWNER = {
    "answer_surface.scope_statement": "01",
    "answer_surface.refusal_rule": "01",
    "source_registry": "02",
    "source_registry.owning_team": "02",
    "owner_acknowledgements.acknowledged_at": "02",
    "error_budget": "05",
    "error_budget.value": "05",
    "error_budget.unit": "05",
    "error_budget.window": "05",
    "measurements.sample_size": "04",
    "alerts.pages": "05",
    "ownership.accuracy_owner": "06",
}
for field, number in FIELD_OWNER.items():
    owner_dir = skills_root / full(number)
    text = (owner_dir / "SKILL.md").read_text(encoding="utf-8") + (owner_dir / "references" / "checks.md").read_text(encoding="utf-8")
    top, _, leaf = field.partition(".")
    if top not in text or (leaf and leaf not in text):
        failures.append(f"contract field {field!r} is not defined in skill {number}")
for items in REQUIRED_POINTS.values():
    for field in items:
        if field not in FIELD_OWNER:
            failures.append(f"required points_to field {field!r} has no owning skill")
for field in FIELD_OWNER:
    if f'"{field}"' not in raw_checks_md:
        failures.append(f"checks.md does not list known field {field!r}")


def iso(days=0):
    return (utc_today + timedelta(days=days)).isoformat()


def retrieval_items(present):
    evidence = {
        "scope_and_refusal": "Answer surface definition, section 1, found in 20 seconds",
        "input_list_with_acknowledgement_dates": "Input exposure inventory source table lists each source with its acknowledgement date",
        "budget_with_sample_size": "Error budget page, first screen, with the sample size beside it",
        "alert_recipient_name": "On-call rota names who the burn-rate alert reaches",
    }
    absent_evidence = {
        "budget_with_sample_size": "Searched the error budget page and the measurement log: no budget with a window, and the only error rate quotes no sample size",
        "alert_recipient_name": "On-call rota has no burn-rate alert for the order-status surface",
    }
    return [
        {
            "id": item_id,
            "present": item_id in present,
            "evidence": evidence[item_id] if item_id in present else absent_evidence.get(item_id, f"Looked for {item_id} and did not find it"),
            "points_to": list(REQUIRED_POINTS[item_id]),
        }
        for item_id in ITEM_IDS
    ]


def missing_entries(*artefacts):
    return [
        {"artefact": a, "owning_skill": full(CATALOGUE[a][0]), "retrieval_item": CATALOGUE[a][1]}
        for a in artefacts
    ]


def commerce(storefront=True):
    if storefront:
        return {
            "storefront": True,
            "delegate_to": "agentic-commerce-skills",
            "url": "https://github.com/wakqasahmed/agentic-commerce-skills",
            "delegated_concerns": ["catalogue", "feed", "policy", "protocol"],
            "answered_here": False,
        }
    return {"storefront": False, "delegated_concerns": []}


RECOMMENDATIONS = [
    {
        "recommended_action": "Have an operator run 04-accuracy-sampling-plan, then 05-error-budget-and-burn-alerting, for the order-status surface.",
        "automation_level": "1-Recommend",
        "execution_status": "not_applied",
    }
]

hold_report = {
    "readiness": {
        "surface_state": "live",
        "route": [full("04"), full("05")],
        "retrieval_test": retrieval_items({"scope_and_refusal", "input_list_with_acknowledgement_dates"}),
        "retrieved": {
            "scope_statement": "The agent answers order-status questions for authenticated customers using the order management record.",
            "refusal_rule": "The agent declines every question outside order status even when related material can be retrieved.",
            "inputs": [{"source_id": "order-system", "owning_team": "Order operations", "acknowledged_at": "2026-09-11"}],
            "error_budget": None,
            "alert_recipient": None,
            "accuracy_owner": "Priya Nair",
        },
        "missing": missing_entries("error_budget", "sample_size", "alert_recipient"),
        "commerce_delegation": commerce(True),
        "status": "HOLD",
    },
    "recommendations": copy.deepcopy(RECOMMENDATIONS),
    "guardrail_status": "CLEAR",
}

ready_report = copy.deepcopy(hold_report)
ready_report["readiness"].update(
    route=[],
    retrieval_test=retrieval_items(set(ITEM_IDS)),
    retrieved={
        **hold_report["readiness"]["retrieved"],
        "error_budget": {"value": 0.04, "unit": "fraction_of_answers", "window": "28d", "sample_size": 200},
        "alert_recipient": "order-support-on-call",
    },
    missing=[],
    status="READY",
)


def run_check(command, report):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as report_file:
        json.dump(report, report_file)
        report_file.flush()
        environment = os.environ.copy()
        environment["REPORT"] = report_file.name
        return subprocess.run(
            ["bash", "-c", command], env=environment, capture_output=True, text=True, check=False
        )


def mutated(base, change):
    report = copy.deepcopy(base)
    change(report)
    return report


def ready(report):
    return report["readiness"]


def item(report, identifier):
    return next(entry for entry in ready(report)["retrieval_test"] if entry["id"] == identifier)


def retrieved(report):
    return ready(report)["retrieved"]


def delegation(report):
    return ready(report)["commerce_delegation"]


S = expected_sections
negative_controls = []


def add(section, label, change, base=hold_report):
    negative_controls.append((label, S[section], mutated(base, change)))


def set_ready(key, value):
    return lambda r: ready(r).__setitem__(key, value)


def del_ready(key):
    return lambda r: ready(r).pop(key)


# Section 0: the surface state and the order of work.
add(0, "surface_state missing", del_ready("surface_state"))
add(0, "surface_state null", set_ready("surface_state", None))
add(0, "surface_state unknown", set_ready("surface_state", "launched"))
add(0, "surface_state with different case", set_ready("surface_state", "Live"))
add(0, "no readiness object", lambda r: r.pop("readiness"))
add(0, "route missing", del_ready("route"))
add(0, "route is prose", set_ready("route", "Run 04 and then 05"))
add(0, "live route in the wrong order", set_ready("route", [full("05"), full("04")]))
add(0, "live route in the pre-launch order", set_ready("route", [full("04"), full("06"), full("05")]))
add(0, "route repeats a skill", set_ready("route", [full("04"), full("04"), full("05")]))
add(0, "route names a skill outside 01 to 07", set_ready("route", [full("04"), "09-commerce-readiness", full("05")]))
add(0, "route names a skill without its number", set_ready("route", ["accuracy-sampling-plan", full("05")]))
add(0, "route omits the skill that produces a missing artefact", set_ready("route", [full("05")]))
add(0, "route is empty with artefacts missing", set_ready("route", []))
add(0, "pre-launch route in the wrong order",
    lambda r: ready(r).update(surface_state="about_to_ship", route=[full("06"), full("04"), full("05")]))
add(0, "no_surface_yet route in the wrong order",
    lambda r: ready(r).update(surface_state="no_surface_yet", route=[full("05"), full("04")]))
add(0, "no_surface_yet route puts scope after the owner",
    lambda r: ready(r).update(surface_state="no_surface_yet", route=[full("06"), full("01"), full("04"), full("05")]))
add(0, "about_to_ship given the live order",
    lambda r: ready(r).update(surface_state="about_to_ship", route=[full("05"), full("04")]))
add(0, "missing is not a list", set_ready("missing", "error budget"))

# Section 1: the four retrieval items.
add(1, "retrieval test written as prose", set_ready("retrieval_test", "Everything is on the wiki."))
add(1, "no retrieval test", del_ready("retrieval_test"))
add(1, "empty retrieval test", set_ready("retrieval_test", []))
for identifier in ITEM_IDS:
    add(1, f"item missing: {identifier}", lambda r, i=identifier: ready(r)["retrieval_test"].remove(item(r, i)))
    add(1, f"item present flag missing: {identifier}", lambda r, i=identifier: item(r, i).pop("present"))
    add(1, f"item present flag is a string: {identifier}", lambda r, i=identifier: item(r, i).update(present="true"))
    add(1, f"item without evidence: {identifier}", lambda r, i=identifier: item(r, i).pop("evidence"))
    add(1, f"item with blank evidence: {identifier}", lambda r, i=identifier: item(r, i).update(evidence=" "))
    add(1, f"item with placeholder evidence: {identifier}", lambda r, i=identifier: item(r, i).update(evidence="TBD"))
    add(1, f"item with a bare yes as evidence: {identifier}", lambda r, i=identifier: item(r, i).update(evidence="yes"))
    add(1, f"item points at nothing: {identifier}", lambda r, i=identifier: item(r, i).update(points_to=[]))
    add(1, f"item without points_to: {identifier}", lambda r, i=identifier: item(r, i).pop("points_to"))
    add(1, f"item points_to is a string: {identifier}", lambda r, i=identifier: item(r, i).update(points_to=REQUIRED_POINTS[i][0]))
    for field in REQUIRED_POINTS[identifier]:
        add(1, f"item {identifier} omits {field}",
            lambda r, i=identifier, f=field: item(r, i).update(points_to=[x for x in item(r, i)["points_to"] if x != f]))
    add(1, f"item {identifier} points at an invented field",
        lambda r, i=identifier: item(r, i)["points_to"].append("answer_surface.tone_of_voice"))
    add(1, f"item {identifier} points at a commerce field",
        lambda r, i=identifier: item(r, i)["points_to"].append("catalogue.feed_status"))
add(1, "duplicate item", lambda r: ready(r)["retrieval_test"].append(copy.deepcopy(ready(r)["retrieval_test"][0])))
add(1, "unknown extra item", lambda r: ready(r)["retrieval_test"].append({**copy.deepcopy(ready(r)["retrieval_test"][0]), "id": "catalogue_readiness"}))

# Section 2: a present item is backed by a retrieved value. Built on the READY report, where all four are present.
def add_ready(section, label, change):
    add(section, label, change, base=ready_report)


add_ready(2, "retrieved missing", lambda r: ready(r).pop("retrieved"))
add_ready(2, "retrieved is prose", lambda r: ready(r).__setitem__("retrieved", "All found"))
add_ready(2, "retrieved carries an extra field", lambda r: retrieved(r).update(catalogue_completeness=0.9))
add_ready(2, "scope present with no scope statement", lambda r: retrieved(r).update(scope_statement=None))
add_ready(2, "scope present with a blank scope statement", lambda r: retrieved(r).update(scope_statement=" "))
add_ready(2, "scope present with no refusal rule", lambda r: retrieved(r).pop("refusal_rule"))
add_ready(2, "scope statement is two sentences",
    lambda r: retrieved(r).update(scope_statement="The agent answers order status. It also answers returns."))
add_ready(2, "refusal rule is two sentences",
    lambda r: retrieved(r).update(refusal_rule="The agent declines everything else. It always hands off."))
add_ready(2, "inputs present with no inputs", lambda r: retrieved(r).update(inputs=[]))
add_ready(2, "inputs is prose", lambda r: retrieved(r).update(inputs="All inputs acknowledged"))
add_ready(2, "inputs missing", lambda r: retrieved(r).pop("inputs"))
add_ready(2, "input with no acknowledgement date", lambda r: retrieved(r)["inputs"][0].pop("acknowledged_at"))
add_ready(2, "input with a null acknowledgement date", lambda r: retrieved(r)["inputs"][0].update(acknowledged_at=None))
add_ready(2, "input with an impossible date", lambda r: retrieved(r)["inputs"][0].update(acknowledged_at="2026-02-31"))
add_ready(2, "input with a wrongly formatted date", lambda r: retrieved(r)["inputs"][0].update(acknowledged_at="11/09/2026"))
add_ready(2, "input acknowledged in the future", lambda r: retrieved(r)["inputs"][0].update(acknowledged_at=iso(1)))
add_ready(2, "input with a blank owning team", lambda r: retrieved(r)["inputs"][0].update(owning_team=" "))
add_ready(2, "input with no source id", lambda r: retrieved(r)["inputs"][0].pop("source_id"))
add_ready(2, "one of two inputs unacknowledged",
    lambda r: retrieved(r)["inputs"].append({"source_id": "returns-policy", "owning_team": "Returns", "acknowledged_at": ""}))
add_ready(2, "budget present with no budget", lambda r: retrieved(r).update(error_budget=None))
add_ready(2, "budget is prose", lambda r: retrieved(r).update(error_budget="Four percent"))
add_ready(2, "budget of zero", lambda r: retrieved(r)["error_budget"].update(value=0))
add_ready(2, "negative budget", lambda r: retrieved(r)["error_budget"].update(value=-0.04))
add_ready(2, "budget as a string", lambda r: retrieved(r)["error_budget"].update(value="0.04"))
add_ready(2, "budget with no value", lambda r: retrieved(r)["error_budget"].pop("value"))
add_ready(2, "budget with an unknown unit", lambda r: retrieved(r)["error_budget"].update(unit="bananas"))
add_ready(2, "budget with no unit", lambda r: retrieved(r)["error_budget"].pop("unit"))
add_ready(2, "budget with a prose window", lambda r: retrieved(r)["error_budget"].update(window="28 days"))
add_ready(2, "budget with no window", lambda r: retrieved(r)["error_budget"].pop("window"))
add_ready(2, "budget with a zero window", lambda r: retrieved(r)["error_budget"].update(window="0d"))
add_ready(2, "budget with no sample size", lambda r: retrieved(r)["error_budget"].pop("sample_size"))
add_ready(2, "budget with a zero sample size", lambda r: retrieved(r)["error_budget"].update(sample_size=0))
add_ready(2, "budget with a fractional sample size", lambda r: retrieved(r)["error_budget"].update(sample_size=20.5))
add_ready(2, "budget with a sample size as a string", lambda r: retrieved(r)["error_budget"].update(sample_size="200"))
add_ready(2, "alert present with no recipient", lambda r: retrieved(r).update(alert_recipient=None))
add_ready(2, "alert recipient is a team", lambda r: retrieved(r).update(alert_recipient="Support team"))
add_ready(2, "alert recipient is a queue", lambda r: retrieved(r).update(alert_recipient="support queue"))
add_ready(2, "alert recipient is a placeholder", lambda r: retrieved(r).update(alert_recipient="TBD"))
add_ready(2, "alert recipient is a generic function", lambda r: retrieved(r).update(alert_recipient="support"))
add_ready(2, "alert recipient is blank", lambda r: retrieved(r).update(alert_recipient=""))
add_ready(2, "alert recipient is a number", lambda r: retrieved(r).update(alert_recipient=7))
for phrase in ("Zero tolerance for wrong answers", "The agent must deliver 100% accuracy", "Error budget of zero",
               "No errors allowed on this surface"):
    add_ready(2, f"zero target in prose: {phrase}", lambda r, p=phrase: item(r, "budget_with_sample_size").update(evidence=p))

# Section 3: every missing item names the artefact and the owning skill.
for artefact, (number, retrieval_item) in CATALOGUE.items():
    add(3, f"{artefact} routed to the wrong skill",
        lambda r, a=artefact, n=number: (ready(r)["missing"].append(
            {"artefact": a, "owning_skill": full("03" if n != "03" else "07"), "retrieval_item": CATALOGUE[a][1]})))
    add(3, f"{artefact} with no owning skill",
        lambda r, a=artefact: ready(r)["missing"].append({"artefact": a, "retrieval_item": CATALOGUE[a][1]}))
    add(3, f"{artefact} with an unnumbered owning skill",
        lambda r, a=artefact: ready(r)["missing"].append(
            {"artefact": a, "owning_skill": "answer-surface-definition", "retrieval_item": CATALOGUE[a][1]}))
for artefact in ("error_budget", "sample_size", "alert_recipient"):
    add(3, f"{artefact} listed twice", lambda r, a=artefact: ready(r)["missing"].append(
        next(e for e in ready(r)["missing"] if e["artefact"] == a)))
add(3, "error_budget against the wrong item",
    lambda r: next(e for e in ready(r)["missing"] if e["artefact"] == "error_budget").update(retrieval_item="alert_recipient_name"))
for artefact in ("product_feed", "catalogue_readiness", "checkout_flow", "policy_clarity", "protocol_support", "unnamed"):
    add(3, f"artefact outside the catalogue: {artefact}",
        lambda r, a=artefact: ready(r)["missing"].append({"artefact": a, "owning_skill": full("01"), "retrieval_item": None}))
add(3, "artefact with no name", lambda r: ready(r)["missing"].append({"owning_skill": full("01")}))
add(3, "missing entry is prose", lambda r: ready(r)["missing"].append("error budget"))
add(3, "absent budget item with nothing missing against it",
    lambda r: ready(r).update(missing=missing_entries("alert_recipient")))
add(3, "absent alert item with nothing missing against it",
    lambda r: ready(r).update(missing=missing_entries("error_budget", "sample_size")))
add(3, "absent item with an empty missing list", set_ready("missing", []))
add(3, "missing entry for an item that is present",
    lambda r: ready(r)["missing"].extend(missing_entries("scope_statement")))
add(3, "missing entry for an input list that is present",
    lambda r: ready(r)["missing"].extend(missing_entries("owner_acknowledgements")))

# Section 4: READY and HOLD.
for label, owner in (
    ("a team", "Support team"), ("a department", "Customer operations department"),
    ("a queue", "Support queue"), ("a placeholder", "TBD"), ("a generic function", "support"),
    ("blank", ""), ("the word owner", "owner"), ("null", None), ("a number", 7), ("a list", ["Priya Nair"]),
    ("a committee", "Quality committee"),
):
    add_ready(4, f"READY with the accuracy owner as {label}", lambda r, o=owner: retrieved(r).update(accuracy_owner=o))
add_ready(4, "READY with no accuracy owner field", lambda r: retrieved(r).pop("accuracy_owner"))
add_ready(4, "READY with no retrieved block at all", lambda r: ready(r).pop("retrieved"))
add_ready(4, "READY with the accuracy owner missing and listed missing",
    lambda r: (retrieved(r).update(accuracy_owner="Support team"), ready(r).update(missing=missing_entries("accuracy_owner"))))
add_ready(4, "READY with an alert item missing",
    lambda r: (item(r, "alert_recipient_name").update(present=False),
               ready(r).update(missing=missing_entries("alert_recipient"), route=[full("05")]), ))
add_ready(4, "READY with an item not present and nothing missing",
    lambda r: item(r, "alert_recipient_name").update(present=False))
add_ready(4, "READY with a missing entry but all items present",
    lambda r: ready(r).update(missing=missing_entries("sample_size"), route=[full("04")]))
add_ready(4, "READY with blocked guardrails", lambda r: r.__setitem__("guardrail_status", "BLOCK"))
add_ready(4, "READY with unknown guardrail status", lambda r: r.__setitem__("guardrail_status", "OK"))
add_ready(4, "HOLD with nothing missing", set_ready("status", "HOLD"))
add_ready(4, "status is GO", set_ready("status", "GO"))
add_ready(4, "status is lowercase", set_ready("status", "ready"))
add_ready(4, "status is CLEAR", set_ready("status", "CLEAR"))
add_ready(4, "status missing", del_ready("status"))
add(4, "HOLD with an unnamed accuracy owner and no missing entry for it",
    lambda r: retrieved(r).update(accuracy_owner="Support team"))
add(4, "HOLD with a null accuracy owner and no missing entry for it",
    lambda r: retrieved(r).update(accuracy_owner=None))
add(4, "HOLD with a named accuracy owner listed as missing",
    lambda r: ready(r)["missing"].extend(missing_entries("accuracy_owner")))
add(3, "accuracy owner listed against the abstention skill instead of 06",
    lambda r: (retrieved(r).update(accuracy_owner="TBD"),
               ready(r)["missing"].append({"artefact": "accuracy_owner", "owning_skill": full("03"), "retrieval_item": None})))
add(4, "HOLD with blocked guardrails and nothing missing",
    lambda r: (ready(r).update(status="HOLD"), r.update(guardrail_status="BLOCK")), base=ready_report)

# Section 5: commerce concerns are delegated.
add(5, "no commerce_delegation", lambda r: ready(r).pop("commerce_delegation"))
add(5, "commerce_delegation is prose", set_ready("commerce_delegation", "Not a storefront"))
add(5, "storefront flag missing", lambda r: delegation(r).pop("storefront"))
add(5, "storefront flag is a string", lambda r: delegation(r).update(storefront="true"))
add(5, "storefront delegated to the wrong repository", lambda r: delegation(r).update(delegate_to="ai-visibility-skills"))
add(5, "storefront with no delegate", lambda r: delegation(r).pop("delegate_to"))
add(5, "storefront delegated with the wrong link",
    lambda r: delegation(r).update(url="https://github.com/wakqasahmed/ai-visibility-skills"))
add(5, "storefront with no link", lambda r: delegation(r).pop("url"))
for concern in ("catalogue", "feed", "policy", "protocol"):
    add(5, f"storefront does not delegate {concern}",
        lambda r, c=concern: delegation(r).update(delegated_concerns=[x for x in delegation(r)["delegated_concerns"] if x != c]))
add(5, "storefront delegates nothing", lambda r: delegation(r).update(delegated_concerns=[]))
add(5, "delegated_concerns is prose", lambda r: delegation(r).update(delegated_concerns="catalogue, feed, policy, protocol"))
add(5, "delegated concern outside the vocabulary", lambda r: delegation(r)["delegated_concerns"].append("pricing"))
add(5, "storefront concerns answered here", lambda r: delegation(r).update(answered_here=True))
add(5, "answered_here missing", lambda r: delegation(r).pop("answered_here"))
add(5, "non-storefront still delegates", lambda r: delegation(r).update(storefront=False))
add(5, "non-storefront with a delegate",
    lambda r: ready(r).update(commerce_delegation={"storefront": False, "delegated_concerns": [], "delegate_to": "agentic-commerce-skills"}))
add(5, "non-storefront with a link",
    lambda r: ready(r).update(commerce_delegation={"storefront": False, "delegated_concerns": [], "url": "https://github.com/wakqasahmed/agentic-commerce-skills"}))
for key in ("catalogue_readiness", "feed_status", "protocol_support", "policy_clarity", "product_data", "checkout_flow", "Catalog"):
    add(5, f"readiness assesses a commerce concern: {key}", lambda r, k=key: ready(r).__setitem__(k, {"score": 0.8}))

# Section 6: guardrails.
add(6, "applied recommendation", lambda r: r["recommendations"][0].update(execution_status="applied"))
add(6, "autonomous recommendation", lambda r: r["recommendations"][0].update(automation_level="3-Auto"))
add(6, "recommendation with no action", lambda r: r["recommendations"][0].update(recommended_action=" "))
add(6, "no recommendations", lambda r: r.pop("recommendations"))
add(6, "unknown guardrail status", lambda r: r.__setitem__("guardrail_status", "READY"))
add(6, "guardrail status missing", lambda r: r.pop("guardrail_status"))
add(6, "READY despite blocked guardrails", lambda r: r.__setitem__("guardrail_status", "BLOCK"), base=ready_report)

# Section 7: privacy.
add(7, "customer email in evidence", lambda r: item(r, "scope_and_refusal").update(evidence="Wiki page for jo@example.com"))
add(7, "order number in evidence", lambda r: item(r, "scope_and_refusal").update(evidence="Wiki page for order #482913"))
add(7, "phone number in a recommendation",
    lambda r: r["recommendations"][0].update(recommended_action="Call +44 7700 900123 about the alert."))

positive_controls = []
all_sections = list(expected_sections)


def positive(label, base, change=None):
    report = mutated(base, change) if change else copy.deepcopy(base)
    positive_controls.append((label, all_sections, report))


positive("canonical live HOLD", hold_report)
positive("canonical READY", ready_report)
positive("READY with follow-on skills in the route", ready_report, set_ready("route", [full("03"), full("07")]))
positive("READY with a non-storefront", ready_report, set_ready("commerce_delegation", commerce(False)))
positive("HOLD with a non-storefront", hold_report, set_ready("commerce_delegation", commerce(False)))
positive("storefront that also delegates discoverability and agent actions", hold_report,
    lambda r: delegation(r).update(delegated_concerns=["catalogue", "feed", "policy", "protocol", "discoverability", "agent_actions"]))
positive("everything missing before anything is built", hold_report,
    lambda r: ready(r).update(
        surface_state="no_surface_yet",
        route=[full(n) for n in ORDERS["no_surface_yet"] if n in ("01", "02", "04", "05", "06")],
        retrieval_test=retrieval_items(set()),
        retrieved={"scope_statement": None, "refusal_rule": None, "inputs": [], "error_budget": None,
                   "alert_recipient": None, "accuracy_owner": None},
        missing=missing_entries("scope_statement", "refusal_rule", "source_registry", "owner_acknowledgements",
                                "error_budget", "sample_size", "alert_recipient", "accuracy_owner")))
positive("pre-launch HOLD in the pre-launch order", hold_report,
    lambda r: ready(r).update(surface_state="about_to_ship", route=[full("04"), full("05")]))
positive("pre-launch HOLD with the accuracy owner missing", hold_report,
    lambda r: (ready(r).update(surface_state="about_to_ship", route=[full("04"), full("05"), full("06")]),
               retrieved(r).update(accuracy_owner="Support team"),
               ready(r)["missing"].extend(missing_entries("accuracy_owner"))))
positive("only the sample size missing", ready_report,
    lambda r: (item(r, "budget_with_sample_size").update(present=False),
               retrieved(r).update(error_budget={"value": 0.04, "unit": "fraction_of_answers", "window": "28d"}),
               ready(r).update(missing=missing_entries("sample_size"), route=[full("04")], status="HOLD")))
positive("only the input acknowledgements missing", ready_report,
    lambda r: (item(r, "input_list_with_acknowledgement_dates").update(present=False),
               ready(r).update(missing=missing_entries("owner_acknowledgements"), route=[full("02")], status="HOLD")))
positive("blocked guardrails force HOLD with a named gap", hold_report, lambda r: r.__setitem__("guardrail_status", "BLOCK"))
positive("an on-call function as the accuracy owner and the alert recipient", ready_report,
    lambda r: retrieved(r).update(accuracy_owner="order-quality-on-call", alert_recipient="order-support-on-call"))
positive("percent budget over a week", ready_report,
    lambda r: retrieved(r).update(error_budget={"value": 4, "unit": "percent_of_answers", "window": "1w", "sample_size": 1}))
positive("errors per thousand budget", ready_report,
    lambda r: retrieved(r).update(error_budget={"value": 40, "unit": "errors_per_1000_answers", "window": "720h", "sample_size": 5298}))
positive("acknowledgement dated today", ready_report,
    lambda r: retrieved(r)["inputs"][0].update(acknowledged_at=iso()))
positive("a hyphenated scope statement with an abbreviation-free sentence", ready_report,
    lambda r: retrieved(r).update(scope_statement="The agent answers order-status questions, and only those, for signed-in customers."))
positive("evidence that mentions a budget without a zero target", ready_report,
    lambda r: item(r, "budget_with_sample_size").update(evidence="Error budget of 4% over 28 days with 200 graded answers"))

for section, command in section_blocks.items():
    for label, base in (("hold", hold_report), ("ready", ready_report)):
        result = run_check(command, base)
        if result.returncode != 0:
            failures.append(f"canonical {label} report failed {section!r}: {result.stderr.strip()}")

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

# Order of work: the full order is accepted for each state, every adjacent swap and rotation is rejected.
order_command = section_blocks[S[0]]
order_checks = 0
for state, numbers in ORDERS.items():
    names = [full(n) for n in numbers]
    candidates = [("canonical", names, True)]
    for i in range(len(names) - 1):
        swapped = names[:i] + [names[i + 1], names[i]] + names[i + 2:]
        candidates.append((f"swap {i}", swapped, False))
    candidates.append(("rotated", names[1:] + names[:1], False))
    candidates.append(("reversed", list(reversed(names)), False))
    for label, route, accepted in candidates:
        report = mutated(hold_report, lambda r, s=state, rt=route: ready(r).update(surface_state=s, route=rt, missing=[]))
        passed = run_check(order_command, report).returncode == 0
        order_checks += 1
        if passed != accepted:
            failures.append(f"route check for {state!r} {label} should be {'accepted' if accepted else 'rejected'}")

# A READY with an unnamed accuracy owner is impossible whatever else is true: sweep owner values on a READY report.
unnamed_owners = ["", " ", "TBD", "tbd", "TODO", "pending", "unknown", "n/a", "none", "owner", "someone", "support",
                  "Support team", "the support team", "Quality queue", "Quality committee", "On-call", "operations",
                  None, 0, False, [], {}]
for owner in unnamed_owners:
    report = mutated(ready_report, lambda r, o=owner: retrieved(r).update(accuracy_owner=o))
    if all(run_check(section_blocks[section], report).returncode == 0 for section in expected_sections):
        failures.append(f"READY was accepted with accuracy_owner {owner!r}")
named_owners = ["Priya Nair", "order-quality-on-call", "Zoë Müller", "Head of Accuracy, Orders"]
for owner in named_owners:
    report = mutated(ready_report, lambda r, o=owner: retrieved(r).update(accuracy_owner=o))
    if not all(run_check(section_blocks[section], report).returncode == 0 for section in expected_sections):
        failures.append(f"READY was rejected with the named accuracy owner {owner!r}")

# The example in SKILL.md must be a report the checks accept once its illustrative date is made current.
example = re.search(r"```json\n(.*?)\n```", raw_skill_md, re.DOTALL)
if not example:
    failures.append("SKILL.md has no JSON example")
else:
    try:
        example_report = json.loads(example.group(1))
    except json.JSONDecodeError as error:
        failures.append(f"SKILL.md example is not valid JSON: {error}")
    else:
        for entry in example_report["readiness"]["retrieved"]["inputs"]:
            entry["acknowledged_at"] = iso(-30)
        for section, command in section_blocks.items():
            if run_check(command, example_report).returncode != 0:
                failures.append(f"SKILL.md example failed {section!r}")

if failures:
    print("FAIL: 08-agent-reliability-readiness-review executable contract checks failed:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print(
    "PASS: 08-agent-reliability-readiness-review contract and executable checks passed "
    f"({len(section_blocks)} gates, {len(negative_controls)} negative controls, "
    f"{len(positive_controls)} positive controls, {order_checks} route-order checks, "
    f"{len(unnamed_owners)} unnamed and {len(named_owners)} named accuracy owners)."
)
