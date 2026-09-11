# Security

## Reporting a vulnerability

Open a GitHub issue describing the problem and the affected skill. Do not include credentials, customer data, or a working exploit in the report.

## What the skills in this pack execute

These are instruction files for an agent, not runnable software. The pack ships no service, no daemon, and no installer. The only executable content is the deterministic contract checks under `scripts/` and `skills/*/eval/`, which read files inside this repository and make no network calls.

The following reference documents contain instructions directing an agent to execute commands:

1. `skills/00-agent-reliability-guardrails/references/checks.md` — runs local `jq` and `grep` commands against an operator-supplied deliverable file (`$REPORT`) to verify sample size, error-budget shape, owner separation, alert addressing, automation level, and residual identifiers. Outbound target: none; every command is local and read-only.

## Customer data

Skills in this pack sample real customer conversations. The sampled-conversation privacy gate in `skills/00-agent-reliability-guardrails/SKILL.md` requires personal data, order and account identifiers and customer-written free text to be removed before a sampled answer enters any report, ticket, fixture, or export, and forbids copying raw customer text into a regression case.

Never commit a sampled conversation, a real customer transcript, or an unsanitised deliverable to this repository. Fixtures in this repository are written scenarios, not captured production data.

## What the skills never do

No skill in this pack changes a running agent. None edits a system prompt, retrieval configuration, abstention threshold, routing rule, or knowledge source, and none disables or re-enables a production answer surface. Recommendations are capped at `2-HITL`.
