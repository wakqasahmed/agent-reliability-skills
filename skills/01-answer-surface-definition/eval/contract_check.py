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

REQUIRED_SKILL_PHRASES = [
    "name: 01-answer-surface-definition",
    "version: 1.0.0",
    "last_reviewed: 2026-09-11",
    "../00-agent-reliability-guardrails/SKILL.md",
    "1. Measurement-integrity gate",
    "6. Named-accountability gate",
    "scope_statement",
    "refusal_rule",
    "out_of_scope",
    "question_class",
    "handoff",
    "never_inferred",
    "scope_owner",
    "last_reviewed",
    "health",
    "legal",
    "financial commitment",
    "safety claims",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    ".answer_surface",
    ".scope_statement",
    ".refusal_rule",
    ".out_of_scope",
    ".question_class",
    ".handoff",
    ".never_inferred",
    ".scope_owner.type",
    '"person", "on_call_function"',
    ".last_reviewed",
]

missing = []
for phrase in REQUIRED_SKILL_PHRASES:
    if phrase not in skill_md:
        missing.append(f"missing required skill phrase: {phrase!r}")

for phrase in REQUIRED_CHECK_PHRASES:
    if phrase not in checks_md:
        missing.append(f"missing required checks.md phrase: {phrase!r}")

if missing:
    print("FAIL: 01-answer-surface-definition contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

print(
    "PASS: 01-answer-surface-definition contract check passed "
    f"({len(REQUIRED_SKILL_PHRASES)} skill phrases and "
    f"{len(REQUIRED_CHECK_PHRASES)} check phrases verified)."
)
