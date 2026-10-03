---
name: 05-error-budget-and-burn-alerting
description: Turn a customer-facing AI agent's error rate into an error budget and burn-rate alerts that reach a named person, and define what is recommended to stop when the budget is gone. Use after a graded measurement exists, when an error rate has no owner or nobody is paged for it, or when a proposed budget is zero, has no window, or is stricter than the measured rate.
version: 1.0.0
last_reviewed: 2026-10-03
---

# Error Budget And Burn Alerting

Load and apply [`../00-agent-reliability-guardrails/SKILL.md`](../00-agent-reliability-guardrails/SKILL.md)
before this workflow. A hard-gate failure makes the result `BLOCK`. This skill designs, records
and recommends; it does not page anyone, change a running agent, or stop an answer surface.

## Outcome

An outage gets an owner because it is an event, and events page people. An error rate accrues no
owner because it is a distribution. This skill converts the distribution into something that
pages: an error budget, and an alert on how fast it is being consumed. Two percent a week burned
through in a day is an event, even though no single answer in it was bad enough to escalate.

## Workflow

1. Consume the `measurements[]` from `04-accuracy-sampling-plan` unchanged (`id`, `error_rate`,
   `sample_size`, `interval_bounds`). Do not re-derive or edit them.
2. Set the `error_budget` as a `value`, a `unit` (`fraction_of_answers`, `percent_of_answers` or
   `errors_per_1000_answers`) and a `window` such as `28d`. Reject zero in every spelling: a zero
   target is an unmeasured target, not a strict one, because nobody has established what rate is
   achievable. "100% accuracy" and "zero tolerance" are zero.
3. Set `derived_from` to the `id` of the measurement the budget is based on. The budget comes
   from the measured baseline, not aspiration. If the budget is below that measurement's Wilson
   lower bound (`interval_bounds.lower`), the surface is in breach on day one: set
   `baseline_status` to `already_in_breach`, give a `breach_response` (re-baseline, remediate, or
   accept with a named approver), and set `status` to `BLOCK`. Otherwise set `baseline_status` to
   `not_proven_in_breach`, which is not a clean bill: a budget below the point estimate is still a
   likely breach.
4. Define multiwindow, multi-burn-rate alerting with at least one `fast_burn` alert that pages now and at least one `slow_burn` alert that opens a ticket [SRC-SRE-BURN-RATE].
   Give each a `burn_rate`, a long `window` and a shorter `short_window` that confirms the burn is
   still happening, and its `budget_consumed` (`burn_rate * window / budget window`, at most 1).
   Fast burns have the higher rate and the shorter window. Set `action` to `page` for fast burns and
   `open_ticket` for slow burns.
5. Check each alert can actually be evaluated from graded answers. Record `graded_answers_in_window`
   and the `signal` that feeds it. The same chapter warns that the approach needs enough traffic to
   give a meaningful signal in each window. This pack's rule of thumb is at least 5 expected errors
   in the window when the burn is at its threshold (`graded_answers_in_window * burn_rate * budget
   >= 5`); fewer means one bad answer can trip the alert, and the guardrails require alerting on
   burn rate, not on individual answers. Grading latency matters as well: a sample graded once a
   week cannot page within a day, so a fast burn needs a graded signal that arrives inside its short
   window, such as an automated comparison of every answer to the system of record.
6. Name who each alert reaches in `pages`: a person or a specific on-call function. A team name,
   queue or distribution list is a missing owner (gate 6).
7. Define `exhaustion_policy`: the `trigger` condition, what is `recommended_stop`, and who
   `decided_by`. This is a recommendation, never an automated action (gate 4): its
   `automation_level` is `0-Observe`, `1-Recommend` or `2-HITL` and `execution_status` is
   `not_applied`.
8. Preserve the global gate result in `guardrail_status`. Set `status` to `BLOCK` when the
   guardrails block or when `baseline_status` is `already_in_breach`; otherwise `CLEAR`.
9. Run every command in [`references/checks.md`](references/checks.md) against the delivered JSON.
   Any non-zero result makes the report invalid and `BLOCK`.

## Output contract

Emit JSON with this shape:

```json
{
  "measurements": [
    {
      "id": "m-order-status-2026-w40",
      "error_rate": 0.03,
      "sample_size": 200,
      "interval": "95% Wilson interval 1.4% to 6.4%",
      "interval_bounds": { "method": "wilson", "level": 0.95, "lower": 0.0138, "upper": 0.0639 }
    }
  ],
  "error_budget": {
    "value": 0.04,
    "unit": "fraction_of_answers",
    "window": "28d",
    "derived_from": "m-order-status-2026-w40",
    "baseline_status": "not_proven_in_breach"
  },
  "alerts": [
    {
      "kind": "fast_burn",
      "burn_rate": 6,
      "window": "1d",
      "short_window": "2h",
      "budget_consumed": 0.2143,
      "graded_answers_in_window": 1500,
      "signal": "Automated comparison of every answer to the order management system",
      "pages": "order-support-on-call",
      "action": "page"
    },
    {
      "kind": "slow_burn",
      "burn_rate": 1,
      "window": "7d",
      "short_window": "2d",
      "budget_consumed": 0.25,
      "graded_answers_in_window": 200,
      "signal": "Weekly graded sample",
      "pages": "Priya Nair",
      "action": "open_ticket"
    }
  ],
  "exhaustion_policy": {
    "trigger": "Budget fully consumed inside the 28d window",
    "recommended_stop": "Recommend the operator restrict the surface to question classes still within budget and abstain on the rest",
    "decided_by": "Amina Shah",
    "automation_level": "2-HITL",
    "execution_status": "not_applied"
  },
  "recommendations": [
    {
      "recommended_action": "Route the fast-burn alert to the order-support on-call rota.",
      "automation_level": "1-Recommend",
      "execution_status": "not_applied"
    }
  ],
  "guardrail_status": "CLEAR",
  "status": "CLEAR"
}
```

## Completion criteria

- The budget is a non-zero number with a unit and a window, derived from a measurement `id` that
  exists in `measurements[]`.
- A budget below the measured lower bound is reported as `already_in_breach`, not accepted silently.
- At least one fast-burn and one slow-burn alert exist, their burn rate and consumed budget
  recompute, and each has enough graded answers to be evaluated.
- Every alert and the exhaustion decision name a person or a specific on-call function.
- The exhaustion policy is a recommendation with a named trigger and decider; nothing is applied.
- The report passes the global guardrails and every deterministic check.
