---
name: 03-abstention-policy-design
description: Define when a customer-facing AI agent must abstain, how it gives a useful refusal and human handoff, who owns the answer threshold, and what coverage cost the coverage owner accepts. Use before launch, after source or scope changes, or when confident unsupported answers, evidence conflicts, stale sources, or unclear threshold ownership appear.
version: 1.0.0
last_reviewed: 2026-09-11
---

# Abstention Policy Design

Load and apply [`../00-agent-reliability-guardrails/SKILL.md`](../00-agent-reliability-guardrails/SKILL.md)
before this workflow. A hard-gate failure makes the result `BLOCK`. This skill designs, records
and recommends; it does not change a running agent, prompt, retrieval configuration, abstention
threshold or routing rule.

## Outcome

Treat abstention as an operating point between error and rejection, not as a defect to minimize in isolation [SRC-CHOW-REJECT-TRADEOFF].
When evaluating a candidate operating point, penalize confident errors more than abstentions; accuracy-only grading rewards guessing [SRC-OPENAI-HALLUCINATION-EVALS].

The deliverable is an enforceable decision rule, a customer-useful refusal and handoff, and an
explicitly owned tradeoff. The accuracy owner owns the threshold. A distinct coverage owner agrees
to its expected numeric coverage cost.

## Workflow

1. Consume the `source_registry` from `02-input-exposure-inventory` without re-deriving or renaming
   `source_id`, `owning_team`, `agent_speaks_from`, `owner_exposure`, `freshness_basis`, and `freshness_detail`.
   Do not infer missing freshness evidence.
2. Set all four unconditional `trigger_conditions`: `no_supporting_source`, `conflicting_sources`,
   `source_older_than_freshness_basis`, and `out_of_scope_question`. These triggers take precedence
   over the numeric operating point and always abstain.
3. Record the candidate `operating_point` as its metric, numeric answer threshold and
   `mandatory_abstention` trigger precedence. Name its `threshold_owner` with accountability
   `accuracy_owner`. The threshold owner must be a person or specific on-call function and cannot
   also be the coverage owner.
4. Set `customer_behaviour.disposition` to `refuse_and_handoff`. Provide a customer-ready message
   that explains the reliability limit, set both `explain_reason` and `offer_handoff` to true, and
   give `handoff` a named person or specific on-call function plus actionable instructions. Never
   terminate the interaction without that handoff.
5. Record `expected_coverage_impact` as a known number, a semantic unit and
   `coverage_decrease`. Name a distinct owner with accountability `coverage_owner`, record
   `agreement_status` as `agreed`, and record the agreement date. If the impact is unknown or the
   coverage owner has not agreed, return `BLOCK`; do not disguise uncertainty as zero. A measured
   or forecast zero is valid when the coverage owner has explicitly agreed to that known value.
6. Define `review_cadence.interval_days` and require all three evidence classes before changing the
   operating point: `system_of_record_error_measurement`, `abstention_rate_measurement`, and
   `coverage_impact_measurement`. A change based only on accuracy, only on coverage, or on model
   confidence is not supported.
7. Preserve the result of the global gates in `guardrail_status`. Every recommendation must carry
   `recommended_action`, an `automation_level` allowed by the guardrails, and `execution_status`
   set to `not_applied`. Set overall `status` to `BLOCK` when the guardrails block; otherwise set
   it to `CLEAR`. Never apply a recommended threshold or routing change autonomously.
8. Run every command in [`references/checks.md`](references/checks.md) against the delivered JSON.
   Any non-zero result makes the report invalid and `BLOCK`.

## Output contract

Emit JSON with this shape:

```json
{
  "source_registry": [
    {
      "source_id": "order-system",
      "owning_team": "Order operations",
      "agent_speaks_from": true,
      "owner_exposure": "acknowledged",
      "freshness_basis": "event_driven",
      "freshness_detail": "Order events appear within 60 seconds"
    }
  ],
  "abstention_policy": {
    "trigger_conditions": [
      "no_supporting_source",
      "conflicting_sources",
      "source_older_than_freshness_basis",
      "out_of_scope_question"
    ],
    "customer_behaviour": {
      "disposition": "refuse_and_handoff",
      "explain_reason": true,
      "offer_handoff": true,
      "message": "I cannot verify that reliably, so I will connect you with order support."
    },
    "handoff": {
      "type": "human",
      "target": {
        "type": "on_call_function",
        "name": "order-support-on-call"
      },
      "instructions": "Transfer the question and cited source IDs for human review."
    },
    "operating_point": {
      "metric": "qualified_answer_score",
      "answer_threshold": 0.85,
      "trigger_precedence": "mandatory_abstention"
    },
    "threshold_owner": {
      "accountability": "accuracy_owner",
      "type": "person",
      "name": "Amina Shah"
    },
    "review_cadence": {
      "interval_days": 30,
      "change_evidence": [
        "system_of_record_error_measurement",
        "abstention_rate_measurement",
        "coverage_impact_measurement"
      ]
    },
    "expected_coverage_impact": {
      "value": 8,
      "unit": "percentage_points",
      "direction": "coverage_decrease",
      "coverage_owner": {
        "accountability": "coverage_owner",
        "type": "person",
        "name": "Omar Khan"
      },
      "agreement_status": "agreed",
      "agreed_at": "2026-09-11"
    }
  },
  "recommendations": [
    {
      "recommended_action": "Have an operator apply the accepted abstention policy.",
      "automation_level": "2-HITL",
      "execution_status": "not_applied"
    }
  ],
  "guardrail_status": "CLEAR",
  "status": "CLEAR"
}
```

The `operating_point.metric` identifies the score being thresholded; this workflow does not
prescribe how that score is produced. The four evidence triggers remain unconditional regardless
of score.

## Completion criteria

- All four mandatory evidence triggers are present exactly once.
- The customer receives a useful refusal and a named, actionable human handoff.
- The named accuracy owner owns a numeric operating point and is distinct from the coverage owner.
- The coverage impact is numeric and explicitly agreed by the named coverage owner.
- The review cadence names the evidence required for any change.
- The report passes the global guardrails and every deterministic check.
