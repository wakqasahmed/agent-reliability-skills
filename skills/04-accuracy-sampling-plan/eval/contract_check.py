#!/usr/bin/env python3
import copy
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from statistics import NormalDist


skill_dir = Path(__file__).resolve().parents[1]
skill_path = skill_dir / "SKILL.md"
checks_path = skill_dir / "references" / "checks.md"

try:
    raw_skill_md = skill_path.read_text(encoding="utf-8")
    raw_checks_md = checks_path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as error:
    sys.exit(f"FAIL: unable to read contract files: {error}")

skill_md = " ".join(raw_skill_md.split())
checks_md = " ".join(raw_checks_md.split())

REQUIRED_SKILL_PHRASES = [
    "name: 04-accuracy-sampling-plan",
    "version: 1.0.0",
    "../00-agent-reliability-guardrails/SKILL.md",
    "detection channel, not a measurement",
    "lower bound on the error rate",
    "measurements[]",
    "error_rate",
    "sample_size",
    "interval",
    "graded_against",
    "cadence",
    "selection_method",
    "detectable_difference",
    "cannot_support",
    "funded_question",
    "large_regression",
    "small_difference",
    "approximation_valid",
    "uniform",
    "stratified_by_question_class",
    "oversampled_new_classes",
    "system of record",
    "grader_built_surface",
    "gate 3",
    "regression_intake",
    "does not sample, grade or change a running agent",
    "[SRC-BROWN-CAI-DASGUPTA-BINOMIAL]",
    "execution_status",
    "not_applied",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    "interval_bounds",
    ".graded_against",
    '.source == "graded_sample"',
    ".selection_method",
    ".detectable_difference",
    ".cannot_support",
    ".required_sample_size",
    "approximation_valid",
    ".sampling_plan.regression_intake",
    ".execution_status == \"not_applied\"",
    "[SRC-BROWN-CAI-DASGUPTA-BINOMIAL]",
]

missing = []
for phrase in REQUIRED_SKILL_PHRASES:
    if phrase not in skill_md:
        missing.append(f"missing required skill phrase: {phrase!r}")
for phrase in REQUIRED_CHECK_PHRASES:
    if phrase not in checks_md:
        missing.append(f"missing required checks.md phrase: {phrase!r}")

if missing:
    print("FAIL: 04-accuracy-sampling-plan contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

expected_sections = [
    "Every reported rate carries a sample and a Wilson interval that recomputes",
    "Graded against the system of record",
    "Ticket counts are never an error rate",
    "Selection, cadence and grading are recorded",
    "The detectable difference is stated and recomputes",
    "Confirmed failures have a route into regression cases",
    "Guardrail status is preserved and changes remain non-autonomous",
    "No raw customer identifiers enter the plan",
]
section_blocks = dict(
    re.findall(r"^## (.+?)\n.*?^```bash\n(.*?)^```", raw_checks_md, re.MULTILINE | re.DOTALL)
)
if list(section_blocks) != expected_sections:
    sys.exit("FAIL: checks.md must contain exactly the eight documented executable check sections")


# ---------------------------------------------------------------------------
# Independent statistics. These are the reference the jq checks are compared to.
# ---------------------------------------------------------------------------
NORMAL = NormalDist()
JQ_CONFIDENCE_Z = {0.9: 1.644854, 0.95: 1.959964, 0.99: 2.575829}
JQ_POWER_Z = {0.8: 0.841621, 0.9: 1.281552, 0.95: 1.644854}


def z_confidence(level):
    return NORMAL.inv_cdf(1 - (1 - level) / 2)


def wilson(k, n, z):
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


def wald(k, n, z):
    p = k / n
    half = z * math.sqrt(p * (1 - p) / n)
    return p - half, p + half


def min_detectable_difference(p0, n, confidence=0.95, power=0.8):
    za, zb = z_confidence(confidence), NORMAL.inv_cdf(power)
    d = 0.05
    for _ in range(500):
        p1 = min(p0 + d, 0.9999)
        d = (za + zb) * math.sqrt((p0 * (1 - p0) + p1 * (1 - p1)) / n)
    return d


def required_sample_size(p0, p1, confidence=0.95, power=0.8):
    za, zb = z_confidence(confidence), NORMAL.inv_cdf(power)
    return math.ceil((za + zb) ** 2 * (p0 * (1 - p0) + p1 * (1 - p1)) / (p1 - p0) ** 2)


def binomial_pmf(n, p):
    return [
        math.exp(
            math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log(1 - p)
        )
        for k in range(n + 1)
    ]


def exact_power(p0, p1, n, alpha=0.05):
    """Exact power of the two-sided pooled two-proportion z-test, by full enumeration."""
    critical = NORMAL.inv_cdf(1 - alpha / 2)
    a, b = binomial_pmf(n, p0), binomial_pmf(n, p1)
    total = 0.0
    for i in range(n + 1):
        for j in range(n + 1):
            pooled = (i + j) / (2 * n)
            if pooled in (0, 1):
                continue
            if abs(j - i) / n / math.sqrt(pooled * (1 - pooled) * 2 / n) >= critical:
                total += a[i] * b[j]
    return total


def interval_coverage(p, n, method, level=0.95):
    z = z_confidence(level)
    total = 0.0
    for k, weight in enumerate(binomial_pmf(n, p)):
        lower, upper = method(k, n, z)
        if lower <= p <= upper:
            total += weight
    return total


statistics_failures = []


def expect(label, condition):
    if not condition:
        statistics_failures.append(label)


# The jq constants are hard-coded, so pin them to the standard normal quantiles.
for level, constant in JQ_CONFIDENCE_Z.items():
    expect(f"jq confidence z {level}", abs(z_confidence(level) - constant) < 1e-5)
for power, constant in JQ_POWER_Z.items():
    expect(f"jq power z {power}", abs(NORMAL.inv_cdf(power) - constant) < 1e-5)

# The worked example: true rate near 3%, 200 graded answers.
standard_error = math.sqrt(0.03 * 0.97 / 200)
expect("standard error is about 1.2 points", abs(standard_error * 100 - 1.2) < 0.01)
expect("Wald half-width is about 2.4 points", abs(1.959964 * standard_error * 100 - 2.4) < 0.05)
w_lower, w_upper = wilson(6, 200, z_confidence(0.95))
expect("Wilson interval for 6/200 is 1.4% to 6.4%", round(w_lower * 100, 1) == 1.4 and round(w_upper * 100, 1) == 6.4)
expect("Wilson interval is asymmetric about 3%", (0.03 - w_lower) < 0.02 and (w_upper - 0.03) > 0.03)
expect("Wilson bounds invert the score test", all(
    abs(abs(6 / 200 - bound) - z_confidence(0.95) * math.sqrt(bound * (1 - bound) / 200)) < 1e-9
    for bound in (w_lower, w_upper)
))
expect("zero errors in 200 has a Wilson upper bound near 1.9%", round(wilson(0, 200, z_confidence(0.95))[1] * 100, 1) == 1.9)
expect("zero errors in 200 collapses the Wald interval", wald(0, 200, 1.96) == (0.0, 0.0))

# 3% versus 4% needs thousands, 3% versus 8% needs a few hundred per sample.
expect("3% vs 4% needs about 5,300 per sample", required_sample_size(0.03, 0.04) == 5298)
expect("3% vs 8% needs about 320 per sample", 300 <= required_sample_size(0.03, 0.08) <= 340)
expect("minimum detectable difference at 3%, n=200 is 6.8 points", round(min_detectable_difference(0.03, 200) * 100, 1) == 6.8)
power_3_to_8 = exact_power(0.03, 0.08, 200)
expect(f"3% to 8% at n=200 has about 60% power (got {power_3_to_8:.3f})", 0.55 <= power_3_to_8 <= 0.65)

# The detectable-difference formula holds up against exact power, including small counts.
for p0, n in ((0.03, 200), (0.01, 200), (0.05, 100), (0.10, 200), (0.20, 400), (0.03, 1000)):
    power = exact_power(p0, p0 + min_detectable_difference(p0, n), n)
    expect(f"formula power at p0={p0}, n={n} within 0.77-0.87 (got {power:.3f})", 0.77 <= power <= 0.87)

# Quoted coverage figures in SKILL.md.
coverage = {
    "wald_3": interval_coverage(0.03, 200, wald),
    "wilson_3": interval_coverage(0.03, 200, wilson),
    "wald_1": interval_coverage(0.01, 200, wald),
    "wilson_1": interval_coverage(0.01, 200, wilson),
}
expect("quoted coverage at 3%", (round(coverage["wald_3"] * 100, 1), round(coverage["wilson_3"] * 100, 1)) == (93.3, 94.4))
expect("quoted coverage at 1%", (round(coverage["wald_1"] * 100, 1), round(coverage["wilson_1"] * 100, 1)) == (86.5, 94.8))

if statistics_failures:
    print("FAIL: 04-accuracy-sampling-plan statistics checks failed:")
    for failure in statistics_failures:
        print(f"  - {failure}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Canonical report and adversarial variants.
# ---------------------------------------------------------------------------
def measurement(identifier, errors, n, *, level=0.95, baseline=None, comparison=None,
                confidence=0.95, power=0.8, funded=None):
    rate = errors / n
    lower, upper = wilson(errors, n, z_confidence(level))
    baseline = rate if baseline is None else baseline
    minimum = min_detectable_difference(baseline, n, confidence, power)
    comparison = baseline + 0.01 if comparison is None else comparison
    valid = n * baseline >= 5 and n * (1 - baseline) >= 5
    detectable = {
        "design": "two_independent_samples_equal_size",
        "baseline_rate": baseline,
        "confidence_level": confidence,
        "power": power,
        "minimum_difference": round(minimum, 4),
        "approximation": "normal",
        "approximation_valid": valid,
        "funded_question": funded or ("large_regression" if minimum > 0.01 else "small_difference"),
        "cannot_support": {
            "comparison_rate": comparison,
            "required_sample_size": required_sample_size(baseline, comparison, confidence, power),
        },
    }
    if not valid:
        detectable["caveat"] = "Expected error count is below 5; treat the difference as indicative only."
    return {
        "id": identifier,
        "source": "graded_sample",
        "error_rate": rate,
        "sample_size": n,
        "interval": f"{round(level * 100)}% Wilson interval {lower * 100:.1f}% to {upper * 100:.1f}%",
        "interval_bounds": {"method": "wilson", "level": level, "lower": round(lower, 4), "upper": round(upper, 4)},
        "graded_against": "order management system",
        "cadence": "weekly",
        "selection_method": "uniform",
        "detectable_difference": detectable,
    }


valid_report = {
    "sampling_plan": {
        "frame": "Answers sent on the order-status surface, one calendar week",
        "grading": {
            "rubric": "Correct only if every stated order fact matches the order system",
            "grader": "Priya Nair",
            "grader_built_surface": False,
        },
        "regression_intake": {"destination": "regression case backlog", "owner": "Priya Nair"},
    },
    "measurements": [measurement("m-order-status-2026-w40", 6, 200, baseline=0.03, comparison=0.04)],
    "recommendations": [
        {
            "recommended_action": "Book the weekly review as a large-regression check, not a trend review.",
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


def first(report):
    return report["measurements"][0]


def detectable(report):
    return first(report)["detectable_difference"]


def set_in(getter, key, value):
    def change(report):
        getter(report)[key] = value
    return change


def delete_from(getter, key):
    def change(report):
        del getter(report)[key]
    return change


def bounds(report):
    return first(report)["interval_bounds"]


def grading(report):
    return report["sampling_plan"]["grading"]


S = expected_sections
negative_controls = []


def add(section, label, change):
    negative_controls.append((label, S[section], mutated(change)))


# Section 0: sample size and interval.
add(0, "rate without sample_size", delete_from(first, "sample_size"))
add(0, "rate without interval", delete_from(first, "interval"))
add(0, "rate without interval_bounds", delete_from(first, "interval_bounds"))
add(0, "rate without id", delete_from(first, "id"))
add(0, "blank interval string", set_in(first, "interval", "  "))
add(0, "interval string does not name the method", set_in(first, "interval", "95% interval 1.4% to 6.4%"))
add(0, "interval string does not state its level", set_in(first, "interval", "Wilson interval 1.4% to 6.4%"))
add(0, "interval string states bounds that disagree with interval_bounds", set_in(first, "interval", "95% Wilson interval 0.1% to 0.2%"))
add(0, "interval string states a different level", set_in(first, "interval", "90% Wilson interval 1.4% to 6.4%"))
add(0, "interval bounds missing while the string is present", lambda r: bounds(r).pop("lower"))
add(0, "wrong Wilson lower bound", set_in(bounds, "lower", 0.0))
add(0, "wrong Wilson upper bound", set_in(bounds, "upper", 0.0239))
add(0, "Wald interval presented as the interval", lambda r: bounds(r).update(method="wald", lower=0.0064, upper=0.0536))
add(0, "interval level outside the supported set", set_in(bounds, "level", 0.97))
add(0, "percentage rate instead of a fraction", set_in(first, "error_rate", 3))
add(0, "zero sample size", set_in(first, "sample_size", 0))
add(0, "fractional sample size", set_in(first, "sample_size", 200.5))
add(0, "string sample size", set_in(first, "sample_size", "200"))
add(0, "empty measurements", lambda r: r.update(measurements=[]))
add(0, "no measurements key", lambda r: r.pop("measurements"))
add(0, "duplicate measurement ids", lambda r: r["measurements"].append(copy.deepcopy(r["measurements"][0])))

# Section 1: grading source.
for label, value in (
    ("conversation transcript", "conversation transcript"),
    ("transcript wording", "the call transcript"),
    ("chat history", "chat history"),
    ("conversation log", "conversation log"),
    ("agent output", "the agent's own output"),
    ("same model", "the same model that wrote the answer"),
    ("model self-grade", "model self-grading"),
    ("llm judge", "LLM judge"),
    ("ticket count", "support ticket count"),
    ("ticket volume", "ticket volume by week"),
    ("complaint log", "complaints received"),
    ("satisfaction survey", "customer satisfaction survey"),
    ("placeholder", "TBD"),
    ("blank", ""),
):
    add(1, f"graded_against {label}", set_in(first, "graded_against", value))
add(1, "graded_against missing", delete_from(first, "graded_against"))

# Section 2: tickets are not a rate.
add(2, "ticket counts as the source", set_in(first, "source", "support tickets"))
add(2, "complaint counts as the source", set_in(first, "source", "complaint count"))
add(2, "missing source", delete_from(first, "source"))

# Section 3: selection, cadence and grading.
add(3, "unknown selection method", set_in(first, "selection_method", "convenience"))
add(3, "missing selection method", delete_from(first, "selection_method"))
add(3, "placeholder cadence", set_in(first, "cadence", "TBD"))
add(3, "missing cadence", delete_from(first, "cadence"))
add(3, "grader built the surface", set_in(grading, "grader_built_surface", True))
add(3, "grader_built_surface omitted", delete_from(grading, "grader_built_surface"))
add(3, "grader is a team", set_in(grading, "grader", "the support team"))
add(3, "grader is the model", set_in(grading, "grader", "the same model"))
add(3, "grader is a placeholder", set_in(grading, "grader", "TBD"))
add(3, "no rubric", delete_from(grading, "rubric"))
add(3, "no frame", lambda r: r["sampling_plan"].pop("frame"))

# Section 4: detectable difference.
add(4, "no detectable_difference", delete_from(first, "detectable_difference"))
add(4, "detectable_difference not an object", set_in(first, "detectable_difference", "about 5 points"))
add(4, "minimum difference does not recompute", set_in(detectable, "minimum_difference", 0.02))
add(4, "minimum difference is zero", set_in(detectable, "minimum_difference", 0))
add(4, "confidence level outside the supported set", set_in(detectable, "confidence_level", 0.97))
add(4, "power outside the supported set", set_in(detectable, "power", 0.75))
add(4, "no cannot_support", delete_from(detectable, "cannot_support"))
add(4, "cannot_support comparison is one the sample can separate",
    lambda r: detectable(r)["cannot_support"].update(
        comparison_rate=0.12, required_sample_size=required_sample_size(0.03, 0.12)))
add(4, "cannot_support required size does not recompute",
    lambda r: detectable(r)["cannot_support"].update(required_sample_size=500))
add(4, "cannot_support comparison equals the baseline", lambda r: detectable(r)["cannot_support"].update(comparison_rate=0.03))
add(4, "approximation_valid is wrong for the sample",
    set_in(detectable, "approximation_valid", False))
add(4, "unknown funded question", set_in(detectable, "funded_question", "trend_review"))
add(4, "small_difference funded at a multi-point difference", set_in(detectable, "funded_question", "small_difference"))
add(4, "unsupported approximation name", set_in(detectable, "approximation", "exact"))
add(4, "unknown design", set_in(detectable, "design", "paired"))
add(4, "baseline of zero", set_in(detectable, "baseline_rate", 0))


def small_sample_without_caveat(report):
    report["measurements"][0] = measurement("m-small", 1, 40, baseline=0.025, comparison=0.05)
    del report["measurements"][0]["detectable_difference"]["caveat"]


def small_sample_claims_valid(report):
    report["measurements"][0] = measurement("m-small", 1, 40, baseline=0.025, comparison=0.05)
    report["measurements"][0]["detectable_difference"]["approximation_valid"] = True


add(4, "small-count approximation without a caveat", small_sample_without_caveat)
add(4, "small-count approximation claims to be valid", small_sample_claims_valid)

# Section 5: regression intake.
add(5, "no regression intake", lambda r: r["sampling_plan"].pop("regression_intake"))
add(5, "regression intake owned by a team",
    lambda r: r["sampling_plan"]["regression_intake"].update(owner="QA team"))
add(5, "regression intake owner placeholder",
    lambda r: r["sampling_plan"]["regression_intake"].update(owner="TBD"))
add(5, "regression intake without destination",
    lambda r: r["sampling_plan"]["regression_intake"].pop("destination"))

# Section 6: guardrails.
add(6, "applied recommendation", lambda r: r["recommendations"][0].update(execution_status="applied"))
add(6, "autonomous automation level", lambda r: r["recommendations"][0].update(automation_level="3-Auto"))
add(6, "ready despite blocked guardrails", set_in(lambda r: r, "guardrail_status", "BLOCK"))

# Section 7: privacy.
add(7, "customer email in the plan",
    lambda r: r["sampling_plan"].update(frame="Sample of chats such as jo@example.com asking about delivery"))
add(7, "order number in the plan",
    lambda r: r["sampling_plan"].update(frame="Include order #482913 as an example"))

positive_controls = []


def add_positive(label, section_names, report):
    positive_controls.append((label, section_names, report))


def with_measurement(*entries):
    report = copy.deepcopy(valid_report)
    report["measurements"] = list(entries)
    return report


all_sections = list(expected_sections)
add_positive("zero errors observed", all_sections, with_measurement(measurement("m-zero", 0, 200, baseline=0.03, comparison=0.04)))
add_positive("0.99 confidence level", all_sections,
             with_measurement(measurement("m-99", 6, 200, level=0.99, confidence=0.99, baseline=0.03, comparison=0.04)))
add_positive("small count is allowed with a caveat", all_sections,
             with_measurement(measurement("m-small", 1, 40, baseline=0.025, comparison=0.05)))
add_positive("small_difference funded with thousands of answers", all_sections,
             with_measurement(measurement("m-big", 360, 12000, baseline=0.03, comparison=0.035)))
add_positive("two question classes measured separately", all_sections,
             with_measurement(
                 measurement("m-orders", 6, 200, baseline=0.03, comparison=0.04),
                 {**measurement("m-returns", 10, 120, baseline=0.08, comparison=0.1),
                  "selection_method": "oversampled_new_classes"}))
add_positive("a ticketing system can be the system of record for ticket-status answers", all_sections,
             with_measurement({**measurement("m-tickets", 6, 200, baseline=0.03, comparison=0.04),
                               "graded_against": "helpdesk ticket system record for the ticket"}))
add_positive("different non-transcript system of record", all_sections,
             with_measurement({**measurement("m-catalogue", 6, 200, baseline=0.03, comparison=0.04),
                               "graded_against": "product catalogue database"}))

failures = []
for section, command in section_blocks.items():
    result = run_check(command, valid_report)
    if result.returncode != 0:
        failures.append(f"canonical valid report failed {section!r}: {result.stderr.strip()}")

for label, sections, report in positive_controls:
    for section in sections:
        result = run_check(section_blocks[section], report)
        if result.returncode != 0:
            failures.append(f"positive control {label!r} was rejected by {section!r}")

for label, section, report in negative_controls:
    result = run_check(section_blocks[section], report)
    if result.returncode == 0:
        failures.append(f"targeted invalid report passed {section!r}: {label}")
    elif result.returncode != 1:
        # jq -e exits 1 for a false result and 5 for a runtime error; only 1 is a real rejection.
        failures.append(f"targeted invalid report errored instead of failing {section!r}: {label}")

# Every section must have at least one negative control that targets it.
targeted = {section for _, section, _ in negative_controls}
for section in expected_sections:
    if section not in targeted:
        failures.append(f"no negative control targets {section!r}")

# The example in SKILL.md must be a report the checks accept.
example = re.search(r"```json\n(.*?)\n```", raw_skill_md, re.DOTALL)
if not example:
    failures.append("SKILL.md has no JSON example")
else:
    try:
        example_report = json.loads(example.group(1))
    except json.JSONDecodeError as error:
        failures.append(f"SKILL.md example is not valid JSON: {error}")
    else:
        for section, command in section_blocks.items():
            if run_check(command, example_report).returncode != 0:
                failures.append(f"SKILL.md example failed {section!r}")

if failures:
    print("FAIL: 04-accuracy-sampling-plan executable contract checks failed:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print(
    "PASS: 04-accuracy-sampling-plan contract and executable checks passed "
    f"({len(section_blocks)} gates, {len(negative_controls)} negative controls, "
    f"{len(positive_controls)} positive controls, statistics verified)."
)
