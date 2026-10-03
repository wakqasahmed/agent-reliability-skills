---
name: 04-accuracy-sampling-plan
description: Plan how a customer-facing AI agent's error rate is measured by sampling answers and grading them against the system of record, and state which comparisons the sample can and cannot support. Use before booking an accuracy review, when someone quotes an error rate or ticket count, or when a weekly number moves and nobody knows whether it is noise.
version: 1.0.0
last_reviewed: 2026-10-03
---

# Accuracy Sampling Plan

Load and apply [`../00-agent-reliability-guardrails/SKILL.md`](../00-agent-reliability-guardrails/SKILL.md)
before this workflow. A hard-gate failure makes the result `BLOCK`. This skill plans, records and
recommends; it does not sample, grade or change a running agent, prompt, threshold or routing rule.

## Outcome

A number that means something, and a statement of what it cannot tell you. Support tickets are a
detection channel, not a measurement: a ticket needs the customer to notice the error and choose
to report it, so ticket volume is a lower bound on the error rate, biased hardest against the
confident, plausible, wrong answer. The rate has to come from a graded sample, and the sample
size decides which questions that rate can answer.

## The arithmetic this skill forces

Take a true error rate near 3% and 200 graded answers per week (6 errors).

- Standard error: `sqrt(0.03 * 0.97 / 200)` is 1.2 percentage points (0.01206), so the 95%
  Wald interval is about +/-2.4 points (1.96 * 1.2).
- That symmetric figure is an approximation, and a poor one at 6 errors in 200. The Wilson
  interval for 6/200 is 1.4% to 6.4%: about 1.6 points below the estimate and 3.4 above it.
- Treat the Wald interval as having erratic coverage and report the Wilson interval instead [SRC-BROWN-CAI-DASGUPTA-BINOMIAL].
  Exact coverage of the nominal 95% interval at `n` = 200 is 93.3% (Wald) against 94.4% (Wilson)
  at a 3% rate, and 86.5% against 94.8% at a 1% rate. Quote the +/-2.4 only as the
  back-of-envelope version.
- Two independent weekly samples of 200 at a 3% baseline have 80% power to detect a rise of about
  6.8 points (to roughly 10%). A move from 3% to 8% is caught only about 6 times in 10. Telling
  3% from 4% needs about 5,300 graded answers per sample, so hundreds do not do it.

A weekly review that watches a number move by several points on noise alone will find
explanations for movement that is not there. The plan must say which of two questions it funds,
before the review is booked: `large_regression` (a real jump, visible within the week) or
`small_difference` (a change of one point or less, which needs thousands of graded answers).

## Workflow

1. Choose the sampling frame and cadence, and record `selection_method` as `uniform`,
   `stratified_by_question_class` or `oversampled_new_classes`. Report a stratified or
   oversampled sample per question class; do not pool strata into one overall rate unless the
   strata are reweighted to their population shares.
2. Name the grading source in `graded_against`: the system of record the answer claims to
   describe. Never the transcript, a conversation log, the agent's own output or the same model.
3. Record the grading `rubric` and the `grader` (a person or a specific on-call function). A
   grader who also built the answer surface breaks the separation-of-duties gate (gate 3);
   record `grader_built_surface` as `false` only when the grader did not build it.
4. For each `measurements[]` entry, give it a unique `id` (so later workflows can reference it)
   and record `error_rate` as a fraction (0.03, not 3), `sample_size`, and `interval` with its
   `interval_bounds` (Wilson, level 0.90, 0.95 or 0.99). A rate without both is a hard failure.
   Set `source` to `graded_sample`. A ticket count is never a rate.
5. Compute `detectable_difference` at the chosen `sample_size` with the formula in
   [`references/checks.md`](references/checks.md): the smallest difference two independent equal-size
   samples can separate at the stated confidence and power, the `funded_question`, and one
   `cannot_support` comparison with the sample size it would need. State the approximation and
   set `approximation_valid`; when it is `false`, record the `caveat`.
6. Record in `regression_intake` where a confirmed failure goes and who owns it. A failure
   becomes a regression case shaped like the question, never a copy of the customer's words
   (gate 5).
7. Preserve the global gate result in `guardrail_status`. Every recommendation carries
   `recommended_action`, an `automation_level` the guardrails allow, and `execution_status` set
   to `not_applied`. Set `status` to `BLOCK` when the guardrails block; otherwise `CLEAR`.
8. Run every command in [`references/checks.md`](references/checks.md) against the delivered JSON.
   Any non-zero result makes the report invalid and `BLOCK`.

## Output contract

Emit JSON with this shape:

```json
{
  "sampling_plan": {
    "frame": "Answers sent on the order-status surface, one calendar week",
    "grading": {
      "rubric": "Correct only if every stated order fact matches the order system",
      "grader": "Priya Nair",
      "grader_built_surface": false
    },
    "regression_intake": {
      "destination": "regression case backlog",
      "owner": "Priya Nair"
    }
  },
  "measurements": [
    {
      "id": "m-order-status-2026-w40",
      "source": "graded_sample",
      "error_rate": 0.03,
      "sample_size": 200,
      "interval": "95% Wilson interval 1.4% to 6.4%",
      "interval_bounds": { "method": "wilson", "level": 0.95, "lower": 0.0138, "upper": 0.0639 },
      "graded_against": "order management system",
      "cadence": "weekly",
      "selection_method": "uniform",
      "detectable_difference": {
        "design": "two_independent_samples_equal_size",
        "baseline_rate": 0.03,
        "confidence_level": 0.95,
        "power": 0.8,
        "minimum_difference": 0.0679,
        "approximation": "normal",
        "approximation_valid": true,
        "funded_question": "large_regression",
        "cannot_support": {
          "comparison_rate": 0.04,
          "required_sample_size": 5298
        }
      }
    }
  ],
  "recommendations": [
    {
      "recommended_action": "Book the weekly review as a large-regression check, not a trend review.",
      "automation_level": "1-Recommend",
      "execution_status": "not_applied"
    }
  ],
  "guardrail_status": "CLEAR",
  "status": "CLEAR"
}
```

`error_rate` is a fraction in `[0, 1]`. A rate of `0` is a sample result, not a target: 0 errors
in 200 still has a 95% Wilson upper bound of about 1.9%.

## Completion criteria

- Every rate carries `sample_size` and a Wilson `interval` that recomputes from them.
- Every `graded_against` names a system of record; none names a transcript, a log or the agent.
- No ticket count is presented as an error rate.
- The detectable difference recomputes, names the funded question, and states one comparison the
  sample cannot support.
- The grader did not build the surface, and confirmed failures have a named route into
  regression cases.
- The report passes the global guardrails and every deterministic check.
