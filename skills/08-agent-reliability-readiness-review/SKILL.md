---
name: 08-agent-reliability-readiness-review
description: Entry point for this pack. Given a customer-facing AI agent that is live or about to ship, run the four-item retrieval test, route each missing item to the skill that produces it, and return READY or HOLD naming every missing artefact and its owning skill. Use first when you do not know which skill you need, before launch, or when asked whether an answer surface is safe to leave running.
version: 1.0.0
last_reviewed: 2026-10-03
---

# Agent Reliability Readiness Review

Load and apply [`../00-agent-reliability-guardrails/SKILL.md`](../00-agent-reliability-guardrails/SKILL.md)
before this workflow. A hard-gate failure makes the result `HOLD`. This skill reviews, routes and
recommends; it does not change a running agent, prompt, retrieval configuration, abstention
threshold or routing rule, and it does not produce the artefacts it asks for. Each of those belongs to
one of skills `01` through `07`.

## Outcome

The operator should not have to know which skill they need. The result is one decision, `READY` or
`HOLD`, and when it is `HOLD` the specific missing artefact and the skill that produces it, for every
gap. This is the pack's counterpart to `readiness-audit` in `agentic-commerce-skills`: that pack asks
whether a storefront can be found and acted on by agents; this one asks whether an answer surface
that already exists is measured, owned and paged for.

## Workflow

1. Set `surface_state` to `no_surface_yet`, `about_to_ship` or `live`. The order of work differs,
   because a live surface is answering customers now and a missing number costs more than a missing
   plan:

   | `surface_state` | Order of work (`route` is a subsequence of this) |
   |---|---|
   | `no_surface_yet` | `01`, `02`, `03`, `06`, `04`, `05`, `07` |
   | `about_to_ship` | `01`, `02`, `04`, `05`, `06`, `03`, `07` |
   | `live` | `04`, `05`, `06`, `01`, `02`, `03`, `07` |

   Before anything is built there is nothing to sample, so the route starts with what the surface
   will be and who owns each input. Before launch, run a graded shadow sample so the budget is derived
   from a measured baseline and abstention tuning in `03` has an error measurement to work from. Once
   live, measure and alert first, then close structural gaps.
2. Run the four-item retrieval test, one entry per item in `readiness.retrieval_test[]`. Where
   `06-accuracy-ownership-separation` already recorded its `retrieval_test[]`, an item is `present`
   only if that record has it `found` in 60 seconds or fewer; otherwise ask someone who did not build
   the agent to find it. Each item carries `present` (true or false), `evidence` (what was found, or
   where it was looked for and not found) and `points_to`, the contract fields that hold it:

   | Item `id` | Holds | `points_to` includes | Produced by |
   |---|---|---|---|
   | `scope_and_refusal` | The answer scope and the refusal rule, one sentence each | `answer_surface.scope_statement`, `answer_surface.refusal_rule` | `01-answer-surface-definition` |
   | `input_list_with_acknowledgement_dates` | The input list, with an acknowledgement date against each owning team | `source_registry`, `owner_acknowledgements.acknowledged_at` | `02-input-exposure-inventory` |
   | `budget_with_sample_size` | The error budget as a number with a unit and a window, and the sample size behind the measurement | `error_budget`, `measurements.sample_size` | `05-error-budget-and-burn-alerting` and `04-accuracy-sampling-plan` |
   | `alert_recipient_name` | The name a burn-rate alert reaches | `alerts.pages` | `05-error-budget-and-burn-alerting` |

3. Record what was found in `readiness.retrieved`, so that `present` is backed by values and not by a
   yes: `scope_statement` and `refusal_rule` (one sentence each), `inputs[]` with `source_id`,
   `owning_team` and `acknowledged_at`, `error_budget` with `value`, `unit`, `window` and
   `sample_size`, `alert_recipient`, and `accuracy_owner`. A budget of zero, or of 100% or more, is not a budget (gate 2),
   an alert reaching a team or a queue is not a name (gate 6), and a rate with no sample size is not a
   measurement (gate 1), so none of those makes an item `present`.
4. Route each missing item to the skill that produces it. For every item that is not `present`, add
   an entry to `missing[]` with the `artefact`, its `owning_skill` and the `retrieval_item` it
   belongs to, from this fixed table. The accuracy owner is not one of the four items but is required
   for `READY`, so it is a fifth artefact with no retrieval item:

   | `artefact` | `owning_skill` | `retrieval_item` |
   |---|---|---|
   | `scope_statement` | `01-answer-surface-definition` | `scope_and_refusal` |
   | `refusal_rule` | `01-answer-surface-definition` | `scope_and_refusal` |
   | `source_registry` | `02-input-exposure-inventory` | `input_list_with_acknowledgement_dates` |
   | `owner_acknowledgements` | `02-input-exposure-inventory` | `input_list_with_acknowledgement_dates` |
   | `error_budget` | `05-error-budget-and-burn-alerting` | `budget_with_sample_size` |
   | `sample_size` | `04-accuracy-sampling-plan` | `budget_with_sample_size` |
   | `alert_recipient` | `05-error-budget-and-burn-alerting` | `alert_recipient_name` |
   | `accuracy_owner` | `06-accuracy-ownership-separation` | none |

   `route` lists the owning skills of every `missing[]` entry in the order for the `surface_state`.
   `03-abstention-policy-design` and `07-failure-to-regression-intake` produce no retrieval item, so
   they appear in `route` only when an operator adds them as follow-on work; they never block
   `READY`.
5. Return `readiness.status`. It is `READY` only when every item is `present`, `missing[]` is empty,
   `accuracy_owner` is a named person or a specific on-call function, and `guardrail_status` is
   `CLEAR`. Anything else is `HOLD`, and a `HOLD` always names at least one `missing[]` entry. An
   unnamed accuracy owner (a team, a queue, `TBD`, blank) is itself a missing `accuracy_owner`
   artefact routed to `06-accuracy-ownership-separation`, so `READY` is impossible without one.
6. For a commerce storefront, set `readiness.commerce_delegation.storefront` to `true` and delegate
   catalogue, feed, policy and protocol readiness to
   [`agentic-commerce-skills`](https://github.com/wakqasahmed/agentic-commerce-skills) by listing
   them in `delegated_concerns` with `answered_here` set to `false`. Do not assess, score or answer
   those concerns here, and do not add them to `missing[]`. A `READY` for a storefront covers answer
   reliability only.
7. Preserve the global gate result in `guardrail_status`. Every recommendation carries
   `recommended_action`, an `automation_level` the guardrails allow, and `execution_status` set to
   `not_applied` (gate 4). A `guardrail_status` of `BLOCK` forces `HOLD`.
8. Run every command in [`references/checks.md`](references/checks.md) against the delivered JSON.
   Any non-zero result makes the report invalid, and an invalid report is `HOLD`.

## How `READY` and `HOLD` relate to `CLEAR` and `BLOCK`

Skills `00` through `07` report `guardrail_status` as `CLEAR` or `BLOCK`: whether their own deliverable
passes the global gates. This skill keeps that field unchanged and adds a decision on top of it,
`readiness.status` of `READY` or `HOLD`, which says whether the surface as a whole can be left
answering customers. `READY` implies `CLEAR`; `BLOCK` implies `HOLD`; `HOLD` can also occur with
`CLEAR`, when a deliverable is sound but one is missing.

## Output contract

Emit JSON with this shape:

```json
{
  "readiness": {
    "surface_state": "live",
    "route": ["04-accuracy-sampling-plan", "05-error-budget-and-burn-alerting"],
    "retrieval_test": [
      {
        "id": "scope_and_refusal",
        "present": true,
        "evidence": "Answer surface definition, section 1, found in 20 seconds",
        "points_to": ["answer_surface.scope_statement", "answer_surface.refusal_rule"]
      },
      {
        "id": "input_list_with_acknowledgement_dates",
        "present": true,
        "evidence": "Input exposure inventory source table lists each source with its acknowledgement date",
        "points_to": ["source_registry", "owner_acknowledgements.acknowledged_at"]
      },
      {
        "id": "budget_with_sample_size",
        "present": false,
        "evidence": "Searched the error budget page and the measurement log: no budget with a window, and the only error rate quotes no sample size",
        "points_to": ["error_budget", "measurements.sample_size"]
      },
      {
        "id": "alert_recipient_name",
        "present": false,
        "evidence": "On-call rota has no burn-rate alert for the order-status surface",
        "points_to": ["alerts.pages"]
      }
    ],
    "retrieved": {
      "scope_statement": "The agent answers order-status questions for authenticated customers using the order management record.",
      "refusal_rule": "The agent declines every question outside order status even when related material can be retrieved.",
      "inputs": [
        { "source_id": "order-system", "owning_team": "Order operations", "acknowledged_at": "2026-09-11" }
      ],
      "error_budget": null,
      "alert_recipient": null,
      "accuracy_owner": "Priya Nair"
    },
    "missing": [
      {
        "artefact": "error_budget",
        "owning_skill": "05-error-budget-and-burn-alerting",
        "retrieval_item": "budget_with_sample_size"
      },
      {
        "artefact": "sample_size",
        "owning_skill": "04-accuracy-sampling-plan",
        "retrieval_item": "budget_with_sample_size"
      },
      {
        "artefact": "alert_recipient",
        "owning_skill": "05-error-budget-and-burn-alerting",
        "retrieval_item": "alert_recipient_name"
      }
    ],
    "commerce_delegation": {
      "storefront": true,
      "delegate_to": "agentic-commerce-skills",
      "url": "https://github.com/wakqasahmed/agentic-commerce-skills",
      "delegated_concerns": ["catalogue", "feed", "policy", "protocol"],
      "answered_here": false
    },
    "status": "HOLD"
  },
  "recommendations": [
    {
      "recommended_action": "Have an operator run 04-accuracy-sampling-plan, then 05-error-budget-and-burn-alerting, for the order-status surface.",
      "automation_level": "1-Recommend",
      "execution_status": "not_applied"
    }
  ],
  "guardrail_status": "CLEAR"
}
```

When `commerce_delegation.storefront` is `false`, `delegate_to` and `url` are omitted and
`delegated_concerns` is `[]`. A `READY` report has an empty `missing`, every item
`present` and every `retrieved` value filled. `retrieved` holds `null` for anything not found.

## Completion criteria

- `surface_state` is set and `route` follows the order of work for that state.
- All four retrieval items are present in the list exactly once, each `present` true or false with
  evidence and the real contract fields in `points_to`.
- Every `present` item is backed by retrieved values; none rests on a zero budget, a team or queue as
  a recipient, or a rate with no sample size.
- Every item that is not `present` has a `missing[]` entry naming the artefact and the skill, `01`
  through `07`, that produces it.
- `READY` is returned only with nothing missing, a named accuracy owner and `guardrail_status` `CLEAR`;
  otherwise `HOLD` names every missing artefact.
- For a storefront, catalogue, feed, policy and protocol readiness is delegated to
  `agentic-commerce-skills`, not answered.
- The report passes the global guardrails and every deterministic check.
