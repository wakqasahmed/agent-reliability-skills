---
name: 00-agent-reliability-guardrails
description: Mandatory measurement-integrity, non-zero-budget, separation-of-duties, no-autonomous-change, sampled-conversation-privacy, and named-accountability gates for any work on a customer-facing AI agent's answer reliability. Apply this skill first, before any workflow-specific agent-reliability skill, when scoping an answer surface, designing abstention, measuring accuracy, setting an error budget, or assigning ownership.
version: 1.0.0
last_reviewed: 2026-09-11
---

# Global Agent Reliability Guardrails

Apply these gates before every workflow-specific `SKILL.md` in this pack. A plan, measurement
or report that fails a hard gate must be marked `BLOCK`, not delivered as operator-ready.

This pack is about one thing: an automated answer reaching a customer, and whether anybody
owns how often it is wrong. Nothing here depends on which model, vendor or framework produces
the answer.

A business that uses an AI agent remains responsible for what that agent does [SRC-CMA-AI-AGENTS].

## 1. Measurement-integrity gate

- Grade every sampled answer against the **system of record** — the order, catalogue, policy
  or account data the answer claims to describe. Never grade an answer against the
  conversation transcript, and never grade it with the same model that produced it. A
  transcript shows what was said, not whether it was true.
- Support tickets are a **detection channel, not a measurement**. A ticket requires the
  customer to notice the error and choose to report it, so ticket volume is a lower bound on
  the error rate and is biased hardest against exactly the confident, plausible, wrong answer
  this pack exists to catch. Never report ticket counts as an error rate.
- Never report an error rate as a bare number. Every reported rate carries its sample size and
  interval, and every comparison between two rates states whether the sample can distinguish
  them. A rate quoted without the sample behind it is not a measurement.
- A model's own expressed confidence is not evidence of correctness and is never used as a
  quality metric or a grading input.

## 2. Non-zero-budget gate

- An error budget of zero is an unmeasured target, not a strict one: it means nobody has
  established what rate is achievable. Reject `0`, `0%`, `zero`, `none` and "100% accuracy"
  as budgets and return `BLOCK`.
- Every budget states a number, a unit and a window. A budget without a window cannot be
  burned through, and a budget that cannot be burned through cannot page anyone.
- Alerting is on burn rate, not on individual bad answers [SRC-SRE-BURN-RATE].
  Burn rate is how fast, relative to the budget, the surface consumes it. An error rate is a
  distribution; burn-rate alerting is what turns it into an event somebody is woken for.

## 3. Separation-of-duties gate

- The role accountable for the error rate must not be the role accountable for automation
  coverage, adoption, deflection or containment. Coverage is visible weekly and rewarded;
  accuracy is invisible and inconvenient. One person holding both is a bias with a reporting
  line, not a tradeoff.
- The accuracy owner needs sufficient independence to maintain objectivity [SRC-SR-26-2],
  as well as the organizational standing and influence to effect any change. An accuracy owner
  who can only file an opinion does not satisfy this gate.
- Both roles are constructive and neither is a veto: the accuracy owner sets the bar the agent
  must clear before it answers; the coverage owner grows what the agent can answer while
  clearing that bar.

## 4. No-autonomous-change gate

- This pack measures, plans and recommends; it does not change a running agent. No skill here
  edits a system prompt, retrieval configuration, abstention threshold, routing rule or
  knowledge source, and none disables or re-enables a production answer surface.
- Every recommendation carries a `recommended_action` and an `automation_level` of
  `0-Observe`, `1-Recommend` or `2-HITL`. A skill proposing anything above `2-HITL` for a
  finding type must justify it in its own `SKILL.md`.
- Pulling a kill switch on a live customer-facing surface is an operator decision. Recommend
  it, name the condition that should trigger it, and stop there.

## 5. Sampled-conversation privacy gate

- Sampled conversations are real customer data. Before a sampled answer enters a report, a
  ticket, a regression fixture or any export, remove personal data, order and account
  identifiers, contact details and free-text the customer wrote about themselves.
- Never copy raw customer text into a regression case. A regression case reproduces the
  *question shape* that broke the agent, not the person who asked it.
- Only sample from a channel the operator has the right to review and reuse for this purpose.
  Where that right is unclear, HALT and ask before sampling.

## 6. Named-accountability gate

- Every alert, budget and answer surface names a person or a specific on-call function. A team
  name, a queue, `TBD`, `TODO`, `pending` or `unknown` is a missing owner, not a nonblank one.
- An unowned number is the failure this pack exists to prevent. A deliverable that leaves any
  required owner unnamed is `BLOCK`, whatever else it contains.

## Delegation contract

- Every other skill in this pack must load or reference this guardrails skill first, before
  running its own workflow. A workflow-specific skill cannot skip straight to its steps
  without first passing through these gates.
- Commerce-specific storefront auditing — catalogue, feed, policy and protocol readiness —
  belongs to [`agentic-commerce-skills`](https://github.com/wakqasahmed/agentic-commerce-skills)
  and is out of scope here. This pack begins where an answer surface already exists.
- Re-running a regression case against a model is out of scope for this pack; hand it to
  [`skill-model-bench`](https://github.com/wakqasahmed/skill-model-bench).

## Verifying these gates against a produced deliverable

[`references/checks.md`](references/checks.md) has grep-able commands to check a *delivered
plan or report* — not this `SKILL.md` — for the sample size and interval, the non-zero budget,
the two distinct owner roles, and the `recommended_action`/`automation_level` fields these
gates require.
