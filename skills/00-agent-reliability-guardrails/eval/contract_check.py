#!/usr/bin/env python3
import sys
from pathlib import Path

skill_dir = Path(__file__).resolve().parents[1]
skill_path = skill_dir / "SKILL.md"
checks_path = skill_dir / "references" / "checks.md"

try:
    raw_skill_md = skill_path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as error:
    sys.exit(f"FAIL: unable to read {skill_path}: {error}")
try:
    raw_checks_md = checks_path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as error:
    sys.exit(f"FAIL: unable to read {checks_path}: {error}")

skill_md = " ".join(raw_skill_md.split())
checks_md = " ".join(raw_checks_md.split())

REQUIRED_GATES = [
    "1. Measurement-integrity gate",
    "2. Non-zero-budget gate",
    "3. Separation-of-duties gate",
    "4. No-autonomous-change gate",
    "5. Sampled-conversation privacy gate",
    "6. Named-accountability gate",
]

REQUIRED_PHRASES = [
    "Grade every sampled answer against the **system of record**",
    "Support tickets are a **detection channel, not a measurement**",
    "Never report an error rate as a bare number",
    "An error budget of zero is an unmeasured target",
    "Alerting is on burn rate, not on individual bad answers",
    "must not be the role accountable for automation coverage",
    "sufficient independence to maintain objectivity",
    "it does not change a running agent",
    "Never copy raw customer text into a regression case",
    "names a person or a specific on-call function",
    "Delegation contract",
    "load or reference this guardrails skill first",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    "sample_size",
    "graded_against",
    "error_budget",
    "accuracy_owner",
    "coverage_owner",
    "automation_level",
]

missing = []
for gate in REQUIRED_GATES:
    if gate not in skill_md:
        missing.append(f"missing gate header: {gate}")

for phrase in REQUIRED_PHRASES:
    if phrase not in skill_md:
        missing.append(f"missing required phrase: {phrase!r}")

for phrase in REQUIRED_CHECK_PHRASES:
    if phrase not in checks_md:
        missing.append(f"missing required checks.md phrase: {phrase!r}")

for level in ("3-Safe-Autonomous", "4-Emergency-Autonomous"):
    if level in checks_md:
        missing.append(f"checks.md must not accept automation level {level!r}")

if missing:
    print("FAIL: 00-agent-reliability-guardrails contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

print(
    "PASS: 00-agent-reliability-guardrails contract check passed "
    f"({len(REQUIRED_GATES)} gates, {len(REQUIRED_PHRASES)} phrases, "
    f"{len(REQUIRED_CHECK_PHRASES)} check fields verified)."
)
