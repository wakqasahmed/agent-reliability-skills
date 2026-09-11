#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDRAILS = ROOT / "skills/00-agent-reliability-guardrails/SKILL.md"
GATE_HEADING = re.compile(r"^##[ \t]+(\d+\..+?)[ \t]*$", re.MULTILINE)
EXPECTED_VALUES = ("follow", "violates")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate held-out eval fixtures.")
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("--min-entries", type=int, default=10)
    parser.add_argument("--min-per-class", type=int, default=5)
    return parser.parse_args()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"FAIL: fixtures file not found: {path}")
    except UnicodeDecodeError:
        sys.exit(f"FAIL: fixtures file is not valid UTF-8: {path}")
    except json.JSONDecodeError as error:
        sys.exit(f"FAIL: invalid JSON in {path}: {error}")


def known_gates() -> set[str]:
    try:
        text = GUARDRAILS.read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"FAIL: guardrails SKILL.md not found at {GUARDRAILS}")
    gates = set(GATE_HEADING.findall(text))
    if not gates:
        sys.exit(f"FAIL: no '## N. ...' gate headers found in {GUARDRAILS}")
    return gates


def main() -> int:
    args = parse_arguments()
    data = load_json(args.fixtures)
    gates = known_gates()

    if not isinstance(data, list) or len(data) < args.min_entries:
        count = len(data) if isinstance(data, list) else "non-list"
        sys.exit(
            f"FAIL: fixtures must be a JSON array with >={args.min_entries} entries, got {count}"
        )

    errors = []
    seen_ids = set()
    for entry in data:
        if not isinstance(entry, dict):
            errors.append(f"entry is not an object: {entry!r}")
            continue
        for field in ("id", "scenario", "expected"):
            if field not in entry:
                errors.append(f"entry missing required field {field!r}: {entry}")
        if entry.get("id") in seen_ids:
            errors.append(f"duplicate fixture id {entry.get('id')!r}")
        seen_ids.add(entry.get("id"))

        expected = entry.get("expected")
        if expected not in EXPECTED_VALUES:
            errors.append(f"entry has invalid 'expected' value {expected!r}: {entry}")
            continue
        if expected != "violates":
            continue
        gate = entry.get("violates_gate")
        if gate is None:
            errors.append(f"violates entry missing 'violates_gate': {entry}")
        elif gate not in gates:
            errors.append(
                f"violates_gate {gate!r} matches no '## N. ...' header in the guardrails SKILL.md"
            )

    follow = [d for d in data if isinstance(d, dict) and d.get("expected") == "follow"]
    violates = [d for d in data if isinstance(d, dict) and d.get("expected") == "violates"]
    if len(follow) < args.min_per_class:
        errors.append(f"need >={args.min_per_class} 'follow' entries, got {len(follow)}")
    if len(violates) < args.min_per_class:
        errors.append(f"need >={args.min_per_class} 'violates' entries, got {len(violates)}")

    if errors:
        print(f"FAIL: {args.fixtures}")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"PASS: {len(data)} fixtures ({len(follow)} follow, {len(violates)} violates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
