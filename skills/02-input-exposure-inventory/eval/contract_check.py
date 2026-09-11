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
    "name: 02-input-exposure-inventory",
    "version: 1.0.0",
    "last_reviewed: 2026-09-11",
    "../00-agent-reliability-guardrails/SKILL.md",
    "every source the answer surface can retrieve",
    "Consume an existing `source_registry` directly",
    "`source_id`, `owning_team`, `agent_speaks_from`, `owner_exposure`, `freshness_basis`, and `freshness_detail`",
    "`acknowledged`, `not_notified`, or `unknown`",
    "`scheduled`, `event_driven`, `none`, or `unknown`",
    "reachable_but_unscoped",
    "A non-spoken source does not block",
    "Do not infer unestablished values",
    "acknowledge_customer_facing_maintenance",
    "Set status to `BLOCK` when any blocking source exists or `guardrail_status` is `BLOCK`",
    "does not change retrieval",
]

REQUIRED_CHECK_PHRASES = [
    "$REPORT",
    "source_registry",
    "source_access",
    "owner_acknowledgements",
    "owner_requests",
    "blocking_sources",
    ".guardrail_status == \"BLOCK\"",
    "reachable_but_unscoped",
    "acknowledge_customer_facing_maintenance",
    'if ($expected_blocking_sources | length) > 0 or .guardrail_status == "BLOCK" then .status == "BLOCK"',
]

missing = []
for phrase in REQUIRED_SKILL_PHRASES:
    if phrase not in skill_md:
        missing.append(f"missing required skill phrase: {phrase!r}")

for phrase in REQUIRED_CHECK_PHRASES:
    if phrase not in checks_md:
        missing.append(f"missing required checks.md phrase: {phrase!r}")

for forbidden in ("BLOCKED", "PASS", "not notified", "event driven"):
    if f'"{forbidden}"' in checks_md:
        missing.append(f"checks.md must use contract enums, not {forbidden!r}")

if missing:
    print("FAIL: 02-input-exposure-inventory contract check found missing items:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

print(
    "PASS: 02-input-exposure-inventory contract check passed "
    f"({len(REQUIRED_SKILL_PHRASES)} skill phrases and "
    f"{len(REQUIRED_CHECK_PHRASES)} check phrases verified)."
)
