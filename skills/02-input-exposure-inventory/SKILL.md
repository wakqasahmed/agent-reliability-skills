---
name: 02-input-exposure-inventory
description: Inventory every source a customer-facing agent can retrieve, verify which sources it actually speaks from, and obtain source-owner acknowledgement of the customer-facing maintenance obligation. Use when exposing a new answer surface, changing retrieval access, or auditing whether reachable inputs have accountable owners and credible freshness.
version: 1.0.0
last_reviewed: 2026-09-11
---

# Input Exposure Inventory

Apply the [global agent reliability guardrails](../00-agent-reliability-guardrails/SKILL.md)
before this workflow. A hard-gate failure makes the result `BLOCK`. This skill inventories,
records and recommends; it does not change retrieval, prompts, routing, permissions or a running
answer surface.

## Outcome

The deliverable is recorded acknowledgement from every owner whose source the agent speaks from,
not merely a source list. `owner_exposure: acknowledged` means the owner explicitly accepted that
the source is customer-facing and agreed to maintain it at the recorded freshness basis. Current
data quality is not a substitute for that acknowledgement.

## Workflow

1. Name the answer surface and its declared answer scope. Enumerate every source the answer surface
   can retrieve through its tools, indexes, APIs, databases, files, prompt context, caches and
   inherited permissions, including sources it was not designed to use.
2. Consume an existing `source_registry` directly when another workflow already produced one with
   this contract. Do not re-derive or rename its fields. Deduplicate by `source_id`, then investigate
   only missing reachable sources and evidence needed by this workflow.
3. For every reachable source, record exactly `source_id`, `owning_team`, `agent_speaks_from`,
   `owner_exposure`, `freshness_basis`, and `freshness_detail` when required in `source_registry`.
   Determine `agent_speaks_from` from configuration, tool traces or sanitized observations; do not
   set it to `false` merely because no intended workflow names the source.
4. Record `owner_exposure` as `acknowledged`, `not_notified`, or `unknown`. Record
   `freshness_basis` as `scheduled`, `event_driven`, `none`, or `unknown`. Scheduled and
   event-driven sources require a substantive `freshness_detail`; omit it or use an empty string for
   `none` and `unknown`. Do not infer unestablished values. If the owning team is not established,
   use the literal `unknown`.
5. Add one `source_access` entry per registry source. Use `in_scope`,
   `reachable_but_unscoped`, or `unknown` for `scope_state`. Every
   `reachable_but_unscoped` source gets its own finding even when the agent does not currently speak
   from it.
6. Record explicit acknowledgement evidence in `owner_acknowledgements`. An acknowledgement names
   who gave it, when, and the obligation `acknowledge_customer_facing_maintenance`. Do not promote a
   source to `acknowledged` from silence, an inventory author's assumption or data that happens to
   be correct today.
7. Add one `owner_requests` entry for every source whose `owner_exposure` is `not_notified` or
   `unknown`. Route it to the recorded `owning_team` and request the specific obligation
   `acknowledge_customer_facing_maintenance`, with the requested decision and freshness commitment
   stated in `recommended_action`. Use only the guardrails' permitted automation levels.
8. Carry the result of the global gates in `guardrail_status`, exactly `BLOCK` or `CLEAR`, then
   derive `blocking_sources` and the overall status. A spoken source blocks when its
   `owner_exposure` is not `acknowledged` or its `freshness_basis` is `none` or `unknown`. A
   non-spoken source does not block under this rule, including when its exposure or freshness is
   `unknown`. Set status to `BLOCK` when any blocking source exists or `guardrail_status` is
   `BLOCK`; set it to `CLEAR` only when both checks clear.

## Output contract

Deliver JSON containing:

- `answer_surface` and `declared_answer_scope`;
- `source_registry` using the interoperable six-field contract;
- `source_access` with `source_id` and semantic `scope_state`;
- `owner_acknowledgements` containing acknowledgement evidence;
- `owner_requests` routing each unacknowledged source and its specific obligation;
- `findings`, including every `reachable_but_unscoped` source with `recommended_action` and
  `automation_level`;
- `guardrail_status`, preserving the result of the mandatory global gates;
- `blocking_sources`; and
- `status`, exactly `BLOCK` or `CLEAR`.

Run every gate in [`references/checks.md`](references/checks.md) against the delivered `$REPORT`.
Any non-zero result makes the report invalid; any valid report with status `BLOCK` is not ready for
customer-facing use.
