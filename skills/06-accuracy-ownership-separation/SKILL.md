---
name: 06-accuracy-ownership-separation
description: Name two distinct owners for a customer-facing AI agent, one for accuracy and one for coverage, record what each can decide alone and how disagreement escalates, confirm the accuracy owner can require abstention, and produce a one-minute retrieval test. Use when one person holds both accuracy and coverage, when ownership is a team name, or before launch and at each ownership review.
version: 1.0.0
last_reviewed: 2026-10-03
---

# Accuracy Ownership Separation

Load and apply [`../00-agent-reliability-guardrails/SKILL.md`](../00-agent-reliability-guardrails/SKILL.md)
before this workflow. A hard-gate failure makes the result `BLOCK`. This skill records and
recommends ownership; it does not change a running agent, a threshold, a routing rule or anyone's
reporting line.

## Outcome

Coverage is visible weekly and gets applause. Accuracy is invisible and inconvenient. Give both to
one person and the result is not a tradeoff but a bias with a reporting line. The split is not a
veto and must not be built as one. The accuracy owner sets the bar the agent has to clear before
it answers. The coverage owner grows what the agent can answer while clearing that bar, which
mostly means fixing inputs, retrieval and scope rather than arguing about the threshold. Two
jobs, both constructive, one number between them.

## Workflow

1. Name `accuracy_owner` and `coverage_owner` as distinct roles, each a person or a specific
   on-call function, written as a string. Reconcile them with the `threshold_owner` and
   `expected_coverage_impact.coverage_owner` already recorded by `03-abstention-policy-design`.
   Two roles are the same role when their normalised strings match: punctuation stripped,
   parenthetical suffixes removed, whitespace collapsed, lowercased. `"Support quality lead"`,
   `"Support quality lead."` and `"Support quality lead (support)"` are one role. The checks also
   ignore whitespace entirely, so `"Amina-Shah"` and `"Amina Shah"` collide. A team name in either
   role is a missing owner (gate 6).
2. Record `accuracy_owner_authority` and `coverage_owner_authority`: what each may decide without
   the other's agreement. Use the fixed values in [`references/checks.md`](references/checks.md).
   Neither list may contain a veto over the other. Record the `escalation_path`: who decides when
   the two disagree, a deadline in days, and `interim_rule` set to `accuracy_requirement_stands`
   so that escalating cannot suspend an accuracy requirement.
3. Verify the accuracy owner has standing to act: `accuracy_owner_authority` includes `require_abstention_on_question_class`, the power to require the surface to abstain on a question class without the coverage owner's agreement [SRC-SR-26-2].
   An accuracy owner who can only file an opinion fails. That guidance covers bank model risk and
   excludes generative and agentic AI models from its scope, so it supports the principle here
   rather than imposing an obligation. Requiring abstention is a decision recorded for the
   operator to apply; this skill applies nothing (gate 4).
4. Record `review_cadence`: `interval_days`, a `reviewer` who is neither owner, and the
   `next_review` date, which must not be in the past.
5. Produce the one-minute retrieval test as `retrieval_test[]`, one checkable item for each of
   `scope_and_refusal`, `input_list_with_acknowledgement_dates`, `budget_with_sample_size` and
   `alert_recipient_name`. Each item gives the `location` a reader goes to, the contract fields it
   `points_to`, whether it was `found`, the `seconds_to_find` (60 or fewer) and the date it was
   `checked_on`. Anything that takes longer than a minute to find does not exist yet.
6. Preserve the global gate result in `guardrail_status`. Every recommendation carries
   `recommended_action`, an `automation_level` the guardrails allow, and `execution_status` set
   to `not_applied`. Set `status` to `BLOCK` when the guardrails block; otherwise `CLEAR`.
7. Run every command in [`references/checks.md`](references/checks.md) against the delivered JSON.
   Any non-zero result makes the report invalid and `BLOCK`.

## Output contract

Emit JSON with this shape (the dates shown are examples; use real ones):

```json
{
  "ownership": {
    "accuracy_owner": "Support quality lead",
    "coverage_owner": "Self-service product lead",
    "accuracy_owner_authority": [
      "require_abstention_on_question_class",
      "set_answer_bar",
      "require_regression_case"
    ],
    "coverage_owner_authority": [
      "prioritise_input_fixes",
      "expand_scope_within_the_bar",
      "propose_answer_bar_change"
    ],
    "escalation_path": {
      "escalates_to": "Head of customer operations",
      "trigger": "The owners disagree about a question class after one working session",
      "decision_within_days": 5,
      "interim_rule": "accuracy_requirement_stands"
    },
    "review_cadence": {
      "interval_days": 90,
      "reviewer": "Chief of staff, operations",
      "next_review": "2027-01-15"
    }
  },
  "retrieval_test": [
    {
      "id": "scope_and_refusal",
      "location": "Answer surface definition, section 1",
      "points_to": ["answer_surface.scope_statement", "answer_surface.refusal_rule"],
      "found": true,
      "seconds_to_find": 20,
      "checked_on": "2026-10-03"
    },
    {
      "id": "input_list_with_acknowledgement_dates",
      "location": "Input exposure inventory, source table",
      "points_to": ["source_registry", "owner_acknowledgements.acknowledged_at"],
      "found": true,
      "seconds_to_find": 35,
      "checked_on": "2026-10-03"
    },
    {
      "id": "budget_with_sample_size",
      "location": "Error budget page, first screen",
      "points_to": ["error_budget", "measurements.sample_size"],
      "found": true,
      "seconds_to_find": 25,
      "checked_on": "2026-10-03"
    },
    {
      "id": "alert_recipient_name",
      "location": "On-call rota, order support",
      "points_to": ["alerts.pages"],
      "found": true,
      "seconds_to_find": 15,
      "checked_on": "2026-10-03"
    }
  ],
  "recommendations": [
    {
      "recommended_action": "Have an operator record the accuracy owner's abstention requirement for the returns question class.",
      "automation_level": "2-HITL",
      "execution_status": "not_applied"
    }
  ],
  "guardrail_status": "CLEAR",
  "status": "CLEAR"
}
```

## Completion criteria

- The two owners are distinct under the normalisation above, and neither is a team name.
- The accuracy owner can require abstention on a question class without the coverage owner's
  agreement, and neither owner holds a veto.
- A named escalation path decides disagreements within a stated number of days, and the accuracy
  requirement stands while it does.
- A reviewer who is neither owner and a future review date are recorded.
- The one-minute retrieval test lists all four items, each found in 60 seconds or fewer.
- The report passes the global guardrails and every deterministic check.
