# Agent Reliability Skills

Provider-agnostic agent skills for operating a **customer-facing AI agent** once it is live: scoping what it may answer and what it must refuse, measuring how often it is wrong, setting an error budget somebody is actually paged for, and naming who owns that number.

**The problem this pack exists for:** a scripted bot fails closed — no matching intent, no answer. An agent fails open. Asked something it does not have, it reasons its way to an answer from whatever it can reach and hands the result to the customer in the same fluent register it uses when it is right. The defect is rarely the model. It is inputs that were adequate internally and became customer-facing without their owners being told, and a steady percentage of confident wrong answers that nobody owns because an error rate is a distribution, and a distribution pages nobody.

Nothing here is model-, vendor- or framework-specific.

## Scope boundary

This pack begins where an answer surface already exists.

| Concern | Where it lives |
|---|---|
| Is the storefront discoverable, citable and safe for agents to act on? | [`agentic-commerce-skills`](https://github.com/wakqasahmed/agentic-commerce-skills) |
| Is this change ready to ship? | [`ai-engineering-workflow-skills`](https://github.com/wakqasahmed/ai-engineering-workflow-skills) |
| Does this model still pass a skill's fixtures? | [`skill-model-bench`](https://github.com/wakqasahmed/skill-model-bench) |
| Is the live answer surface wrong, how often, and who is paged? | **here** |

## Install

Pick whichever fits how you work. All three end up in the same place: the skill files sitting where your agent looks for them.

### 1. Everything, via npx (recommended)

```bash
npx skills@latest add wakqasahmed/agent-reliability-skills
```

This installs every skill in the pack for whichever agent you're using (Claude Code, Cursor, Codex, and 70+ others — see the [`skills` CLI](https://github.com/vercel-labs/skills)). Add `-g` to install once for every project instead of per-project, or `-a claude-code` to target one agent specifically.

### 2. Just one skill

```bash
npx skills@latest add wakqasahmed/agent-reliability-skills --skill 00-agent-reliability-guardrails
```

### 3. No Node/npx available — manual install

Download the repository as a ZIP from **Code → Download ZIP**, unzip it, and copy whichever `skills/<name>/` folder(s) you want into your agent's own skills directory. For Claude Code that is `.claude/skills/` in your project, or `~/.claude/skills/` for a global install; other agents use their own equivalent path.

## Use it

**Start with `00-agent-reliability-guardrails`.** Every other skill in this pack loads it first, and a deliverable that fails one of its hard gates is `BLOCK` rather than operator-ready.

| Skill | What it covers |
|---|---|
| [`00-agent-reliability-guardrails`](skills/00-agent-reliability-guardrails/SKILL.md) | Measurement integrity, non-zero budgets, separation of duties, no autonomous change, sampled-conversation privacy, named accountability. |
| [`01-answer-surface-definition`](skills/01-answer-surface-definition/SKILL.md) | Answered question class, unconditional refusal rule, out-of-scope handoffs, safety-relevant no-inference classes, and named scope ownership. |
| [`02-input-exposure-inventory`](skills/02-input-exposure-inventory/SKILL.md) | Reachable source inventory, customer-facing source-owner acknowledgement, freshness basis, and blocking exposure gaps. |

More skills are being added incrementally through tracked issues — abstention policy design, accuracy sampling plans, error budgets and burn-rate alerting, accuracy ownership, and failure-to-regression intake. See [Issues](https://github.com/wakqasahmed/agent-reliability-skills/issues) for current progress; this table is the source of truth for what actually ships today.

## The four things to have before an agent answers a customer

Anybody who did not build the agent should be able to retrieve all four in under a minute. If one takes longer than that to find, it does not exist yet.

1. The answer scope and the refusal rule, one sentence each.
2. The list of inputs, with an acknowledgement date against each owning team.
3. The error budget as a number with a unit and a window, and the sample size behind the measurement.
4. The name — a person, or a specific on-call function — that the burn-rate alert reaches.

## Evidence discipline

Every normative claim in this pack cites a registered source in [`SOURCES.md`](SOURCES.md), with a publisher, an official URL, the exact claim it supports, and a last-verified date inside a 180-day freshness window. CI fails on an unregistered citation and on a registered source nothing cites.

## Contributing

Deterministic contract checks run on every pull request: source ledger and citation validation, plugin and manifest consistency, the shared guardrail contract tests, and each skill's own eval. Run them locally with:

```bash
python3 scripts/validate-sources.py
python3 scripts/validate-citations.py
python3 scripts/validate-plugin.py
python3 -m unittest discover tests
for eval_script in skills/*/eval/run-eval.sh; do bash "$eval_script"; done
```

## License

MIT.
