#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

GUARDRAILS_SKILL = "00-agent-reliability-guardrails"


def duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def normalize_plugin_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    names = []
    errors = []
    for raw_path in paths:
        if not isinstance(raw_path, str):
            errors.append(f"plugin skill path is not a string: {raw_path!r}")
            continue
        path = Path(raw_path)
        if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "skills":
            errors.append(f"invalid plugin skill path: {raw_path}")
            continue
        names.append(path.parts[1])
    return names, errors


def registry_errors(actual_names: list[str], plugin_paths: list[str]) -> list[str]:
    plugin_names, errors = normalize_plugin_paths(plugin_paths)
    expected = sorted(actual_names)

    duplicate_plugin_names = duplicates(plugin_names)
    if duplicate_plugin_names:
        errors.append("duplicate plugin skills: " + ", ".join(duplicate_plugin_names))

    if sorted(plugin_names) != expected:
        errors.append(f"plugin skills {plugin_names} do not match actual skills {expected}")
    return errors


root = Path(__file__).resolve().parents[1]
plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
skills = plugin.get("skills", [])
actual_skills = sorted(path.parent.name for path in root.glob("skills/*/SKILL.md"))

if GUARDRAILS_SKILL not in actual_skills:
    raise SystemExit(f"Mandatory guardrails skill missing: {GUARDRAILS_SKILL}")

errors = registry_errors(actual_skills, skills)
if errors:
    raise SystemExit("Skill registry mismatch: " + "; ".join(errors))

missing = [skill for skill in skills if not (root / skill / "SKILL.md").is_file()]
if missing:
    raise SystemExit("Missing plugin skill paths: " + ", ".join(missing))

for skill in skills:
    path = root / skill
    name_line = next(
        (line.strip() for line in (path / "SKILL.md").read_text().splitlines() if line.strip().startswith("name: ")),
        None,
    )
    if name_line != f"name: {path.name}":
        raise SystemExit(f"Skill name does not match its directory: {path}")

guardrail_ref = f"../{GUARDRAILS_SKILL}/SKILL.md"
missing_ref = [
    skill for skill in skills
    if Path(skill).name != GUARDRAILS_SKILL
    and guardrail_ref not in (root / skill / "SKILL.md").read_text()
]
if missing_ref:
    raise SystemExit("Skills missing the guardrails dependency: " + ", ".join(missing_ref))

print(f"validated {len(skills)} plugin skill paths")
