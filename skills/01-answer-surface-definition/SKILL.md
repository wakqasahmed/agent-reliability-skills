---
name: 01-answer-surface-definition
description: Define and validate exactly which customer questions an AI agent may answer, must refuse even when information is retrievable, or must hand off, including safety-relevant classes that cannot rely on inference. Use before launching or expanding an answer surface, or when its boundaries and accountable owner are unclear.
version: 1.0.0
last_reviewed: 2026-09-11
---

# Answer Surface Definition

Load and apply [`../00-agent-reliability-guardrails/SKILL.md`](../00-agent-reliability-guardrails/SKILL.md)
before this workflow. A result that fails a hard gate is `BLOCK`, not an operator-ready answer
surface.

Two guardrails are directly involved:

- **1. Measurement-integrity gate:** when candidate or held-out answers are evaluated, grade
  them against the system of record, never the transcript or the model that produced them.
- **6. Named-accountability gate:** the scope owner must be a person or a specific on-call
  function. A team, department, queue or placeholder is not an owner.

This skill defines and assesses a surface. It does not edit a running agent, prompt, retrieval
configuration or routing rule.

## Workflow

1. Write `scope_statement` as one sentence naming the complete class of questions the agent may
   answer. Describe the customer question, not the available documents or tools.
2. Write `refusal_rule` as one sentence naming what the agent must decline outright. State that
   the rule applies even when the agent can retrieve material or reason toward an answer.
3. Enumerate every known excluded question class in `out_of_scope`. Give each class one named
   human or operational handoff destination; never use a blank handoff, generic queue or `TBD`.
4. Put `health`, `legal`, `financial_commitment` and `safety_claims` in `never_inferred`. These
   represent health guidance, legal interpretation, financial commitment and safety claims.
   They may be answered only from a designated authoritative source when the scope permits;
   without direct support, the agent must refuse and use the relevant handoff.
5. Name one accountable scope owner as either a person or a specific on-call function, and record
   the date that owner last reviewed the surface.
6. Run every command in [`references/checks.md`](references/checks.md) against the delivered JSON.
   Return `BLOCK` if any command exits non-zero.

Do not infer omissions into scope. If the operator cannot state the answered class, refusal rule,
excluded classes, handoffs or owner, return `BLOCK` and list the missing decisions.

## Contract

Emit JSON with this shape:

```json
{
  "answer_surface": {
    "scope_statement": "The agent answers order-status questions for authenticated customers using the order management record.",
    "refusal_rule": "The agent declines every question outside order status even when related material can be retrieved.",
    "out_of_scope": [
      {
        "question_class": "Requests to change or cancel an order",
        "handoff": "Order changes on-call"
      }
    ],
    "never_inferred": [
      "health",
      "legal",
      "financial_commitment",
      "safety_claims"
    ],
    "scope_owner": {
      "type": "person",
      "name": "Amina Shah"
    },
    "last_reviewed": "2026-09-11"
  }
}
```

`scope_owner.type` is an enum: `person` or `on_call_function`. `scope_owner.name` is the person's
name or the exact on-call function, such as `support-quality-on-call`; it is never a team name.

## Completion criteria

- The scope and unconditional refusal rule are each stated and neither is a placeholder.
- Every out-of-scope question class has a handoff naming a person or specific on-call function.
- All four safety-relevant classes are declared never inferable.
- The scope owner is a person or specific on-call function and has a review date.
- The report passes every deterministic check.
