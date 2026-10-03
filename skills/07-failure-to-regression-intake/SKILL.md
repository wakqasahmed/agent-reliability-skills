---
name: 07-failure-to-regression-intake
description: Turn a confirmed wrong answer from a customer-facing AI agent into a permanent, sanitised regression case that skill-model-bench loads unchanged, classify who has to fix it, and record the fix and the measurement that shows it stayed closed. Use when a graded sample or an escalation confirms a confident wrong answer, or when a fixed failure has no case locking it down.
version: 1.0.0
last_reviewed: 2026-10-03
---

# Failure To Regression Intake

Load and apply [`../00-agent-reliability-guardrails/SKILL.md`](../00-agent-reliability-guardrails/SKILL.md)
before this workflow. A hard-gate failure makes the result `BLOCK`. This skill classifies,
sanitises, records and recommends; it does not change a running agent, prompt, retrieval
configuration, abstention threshold or routing rule, and it does not re-run anything.

## Outcome

The highest-value test cases are not imagined by whoever wrote the skill. They are the specific
questions a real customer asked that the agent answered confidently and wrongly, the ones nobody
predicted. Without this step a confirmed failure gets fixed once and is free to come back. The
deliverable is a `regression_cases[]` list whose entries can be appended to a skill's
`eval/fixtures/held-out-scenarios.json` as they are, with no personal data in them and a named
person who owns the fix.

## Workflow

1. Take a confirmed wrong answer together with its grading evidence from
   `04-accuracy-sampling-plan`: the `measurements[].id` of the graded sample that found it, the
   `graded_against` system of record, and the `sampling_plan.grading.grader`. Consume those fields
   unchanged. A failure known only from a ticket or a transcript has no grading evidence yet; grade
   it first (gate 1).
2. Set `failure_class` to one of five values. The class decides who fixes it, and they are different
   people:

   | `failure_class` | What went wrong | `fix_owner_role` | Where that name comes from |
   |---|---|---|---|
   | `missing_input` | The source that should have held the answer did not | `source_owner` | `02-input-exposure-inventory`, the owner behind `source_registry.owning_team` |
   | `stale_input` | The source was older than its `freshness_basis` allows | `source_owner` | the same |
   | `conflicting_inputs` | Two reachable sources disagreed and the agent picked one | `source_owner` | the same |
   | `out_of_scope_answered` | The question was outside `answer_surface.scope_statement` and was answered anyway | `scope_owner` | `01-answer-surface-definition`, `answer_surface.scope_owner` |
   | `wrong_from_correct_inputs` | The inputs were right and the answer was still wrong | `accuracy_owner` | `06-accuracy-ownership-separation`, `ownership.accuracy_owner` |

   `fix_owner` is a person or a specific on-call function inside that role, never a team name,
   queue or placeholder (gate 6). A case with no `failure_class` has no one to fix it and fails.
3. Reduce the failure to the question shape that broke the agent, in `question_shape`: one
   third-person sentence naming the kind of question and the feature that made it hard. Reproduce
   the shape, not the person who asked it (gate 5). Then write `scenario`, the text
   `skill-model-bench` puts in front of a model: the same shape plus what the agent did, in the
   third person.
4. Sanitise (gate 5). Strip names, contact details, order and account identifiers and any free text
   the customer wrote about themselves. Set `channel_reuse_confirmed` to `true` only when the
   operator has the right to review and reuse the channel the conversation came from; where that is
   unclear, stop and ask. Set `sanitisation_confirmed` to `true` only after a person has read the
   case. The automated check in [`references/checks.md`](references/checks.md) finds the obvious
   identifier shapes and first-person wording; it cannot find a name or a rare detail, so it is
   necessary and not sufficient.
5. Emit the case with `provenance: production` so it can be told apart from an authored scenario.
   Set `expected` to `violates` (the scenario describes the failure, which a model must flag) or
   `follow` (it describes the corrected behaviour), and give a `violates_gate` label for every
   `violates` case. Re-running the case belongs to
   [`skill-model-bench`](https://github.com/wakqasahmed/skill-model-bench); see that repository's
   issue #32 for the intake path from its side.
6. Record the `fix` that closed it and the `verification_measurement` that will show it stayed
   closed: a later graded sample of that question class with its own `planned_id`, a different
   one from the sample that found the failure. Re-running a case in the bench checks a
   model's judgement of the written scenario. It does not show the live agent stopped making the
   mistake; only a new graded measurement does.
7. Preserve the global gate result in `guardrail_status`. Every recommendation carries
   `recommended_action`, an `automation_level` the guardrails allow, and `execution_status` set to
   `not_applied`. Set `status` to `BLOCK` when the guardrails block; otherwise `CLEAR`.
8. Run every command in [`references/checks.md`](references/checks.md) against the delivered JSON.
   Any non-zero result makes the report invalid and `BLOCK`.

## Bench compatibility

The shape below was read from the `skill-model-bench` source (`main` at commit `2f22e81`), not
assumed:

- It loads `eval/fixtures/held-out-scenarios.json` as a non-empty JSON list.
- It requires `scenario` on every entry and raises if it is missing. It reads `id`, `expected` and
  `violates_gate`, and ignores every other key.
- It scores `expected` as exactly `follow` or `violates`; any other value fails the scenario.
  For `violates` it looks for the words of `violates_gate` in the model's answer, so write the
  label in plain words.

`provenance` (`authored` or `production`, default `authored`) is proposed in that repository's open
issue #32 and is not read by the loader yet. It is emitted here because the issue names it and
because an ignored key does not break loading today. The remaining keys (`question_shape`,
`failure_class`, `sanitisation_confirmed`, `fix_owner`, and so on) are this pack's and are ignored by
the bench. To use a case, append the whole object to the target skill's fixture list.

## Output contract

Emit JSON with this shape:

```json
{
  "measurements": [
    {
      "id": "m-order-status-2026-w40",
      "source": "graded_sample",
      "error_rate": 0.03,
      "sample_size": 200,
      "interval_bounds": { "method": "wilson", "level": 0.95, "lower": 0.0138, "upper": 0.0639 },
      "graded_against": "order management system"
    }
  ],
  "regression_cases": [
    {
      "id": "rc-order-status-0001",
      "question_shape": "Asks for the delivery date of an order whose items shipped in two parcels with different carriers.",
      "scenario": "An order-status agent is asked for the delivery date of an order whose items shipped in two parcels with different carriers. It gives one date for the whole order with full confidence, although the order record holds a separate date for each parcel.",
      "failure_class": "wrong_from_correct_inputs",
      "expected": "violates",
      "violates_gate": "confident answer the order record does not support",
      "provenance": "production",
      "sanitisation_confirmed": true,
      "channel_reuse_confirmed": true,
      "fix_owner_role": "accuracy_owner",
      "fix_owner": "Priya Nair",
      "grading_evidence": {
        "measurement_id": "m-order-status-2026-w40",
        "graded_against": "order management system",
        "grader": "Priya Nair",
        "system_of_record_finding": "The order record lists two parcels with different delivery dates; the answer stated one."
      },
      "fix": {
        "description": "Answer split shipments parcel by parcel, or hand off when the parcels disagree.",
        "status": "closed",
        "closed_by": "Priya Nair",
        "closed_on": "2026-10-03"
      },
      "verification_measurement": {
        "planned_id": "m-order-status-split-shipments-2026-w44",
        "selection_method": "stratified_by_question_class",
        "metric": "error_rate",
        "graded_against": "order management system",
        "minimum_sample_size": 200
      }
    }
  ],
  "recommendations": [
    {
      "recommended_action": "Have an operator append rc-order-status-0001 to the target skill's held-out scenarios and book the follow-up graded sample.",
      "automation_level": "2-HITL",
      "execution_status": "not_applied"
    }
  ],
  "guardrail_status": "CLEAR",
  "status": "CLEAR"
}
```

`failure_class` is one of `missing_input`, `stale_input`, `conflicting_inputs`,
`out_of_scope_answered`, `wrong_from_correct_inputs`. `fix.status` is `open` or `closed`; a closed
fix names `closed_by` and a `closed_on` date that is not in the future. A `follow` case omits
`violates_gate`.

## Completion criteria

- Every case has a `failure_class`, and its `fix_owner_role` is the one that class requires.
- No case text holds an email address, phone number, order or account identifier, or customer
  first-person wording, and every case has `sanitisation_confirmed` and `channel_reuse_confirmed`
  true with `provenance: production`.
- Every case has exactly the keys and enums `skill-model-bench` loads, with a unique `id`.
- Every case cites a graded measurement from `04-accuracy-sampling-plan` that was graded against a
  system of record.
- Every case records the fix and a later, different, planned measurement that will show it held.
- The report passes the global guardrails and every deterministic check.
