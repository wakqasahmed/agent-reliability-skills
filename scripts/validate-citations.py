#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors: list[str] = []
warnings: list[tuple[str, str]] = []

CITATION = re.compile(r"\[(SRC-[A-Z0-9]+(?:-[A-Z0-9]+)*)\]", re.IGNORECASE)
LAST_REVIEWED = re.compile(r"^[ \t]*(?:last_reviewed|Last reviewed):[ \t]*(\d{4}-\d{2}-\d{2})[ \t]*$", re.M)
LEDGER_HEADING = re.compile(r"^##[ \t]+(\S+)[ \t]*$", re.M)
LEDGER_URL = re.compile(r"^-[ \t]+Official URL:[ \t]*(\S+)[ \t]*$", re.M)
FRESHNESS = re.compile(r"^Freshness window:[ \t]*(\d+)[ \t]*days\.[ \t]*$", re.M)

actual_skills = sorted(p.parent.name for p in root.glob("skills/*/SKILL.md"))

manifest = None
manifest_path = root / "manifest.json"
if not manifest_path.is_file():
    errors.append("missing manifest.json")
else:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"malformed manifest.json: {error}")
    else:
        if manifest.get("skills") != actual_skills:
            errors.append(
                f"manifest.json skills {manifest.get('skills')} do not match actual skills {actual_skills}"
            )
        if manifest.get("skill_count") != len(actual_skills):
            errors.append(
                f"manifest.json skill_count {manifest.get('skill_count')} != {len(actual_skills)}"
            )

index: dict[str, str] = {}
index_path = root / "SOURCE_INDEX.json"
if not index_path.is_file():
    errors.append("missing SOURCE_INDEX.json")
else:
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"malformed SOURCE_INDEX.json: {error}")

for key in sorted(index):
    if key != key.upper():
        errors.append(f"SOURCE_INDEX.json key {key!r} must be upper case")

# The two ledgers are kept in parallel, so they must be checked against each other or they
# silently diverge: SOURCES.md is the human-readable record, SOURCE_INDEX.json the machine one.
ledger_path = root / "SOURCES.md"
freshness_days = 180
if not ledger_path.is_file():
    errors.append("missing SOURCES.md")
else:
    ledger_text = ledger_path.read_text(encoding="utf-8")
    freshness_match = FRESHNESS.search(ledger_text)
    if not freshness_match:
        errors.append("SOURCES.md has no parseable freshness window")
    else:
        freshness_days = int(freshness_match.group(1))

    ledger: dict[str, str] = {}
    headings = list(LEDGER_HEADING.finditer(ledger_text))
    for position, heading in enumerate(headings):
        end = headings[position + 1].start() if position + 1 < len(headings) else len(ledger_text)
        url_match = LEDGER_URL.search(ledger_text[heading.end():end])
        ledger[heading.group(1)] = url_match.group(1) if url_match else ""

    for source_id in sorted(set(ledger) - set(index)):
        errors.append(f"{source_id} is in SOURCES.md but not SOURCE_INDEX.json")
    for source_id in sorted(set(index) - set(ledger)):
        errors.append(f"{source_id} is in SOURCE_INDEX.json but not SOURCES.md")
    for source_id in sorted(set(ledger) & set(index)):
        if ledger[source_id] != index[source_id]:
            errors.append(
                f"{source_id}: SOURCES.md URL {ledger[source_id]!r} != SOURCE_INDEX.json {index[source_id]!r}"
            )

if manifest is not None and manifest.get("source_count") != len(index):
    errors.append(f"manifest.json source_count {manifest.get('source_count')} != {len(index)}")


def citations_in(path: Path, text: str, used: set[str]) -> None:
    unregistered = set()
    for citation in CITATION.findall(text):
        upper = citation.upper()
        if citation != upper:
            errors.append(f"{path.relative_to(root)} cites [{citation}]; source IDs are upper case")
        used.add(upper)
        if upper not in index:
            unregistered.add(upper)
    for citation in sorted(unregistered):
        errors.append(f"{path.relative_to(root)} cites unregistered ID [{citation}]")


used: set[str] = set()
today = date.today()
skill_files = sorted(root.glob("skills/*/SKILL.md"))

for path in skill_files:
    text = path.read_text(encoding="utf-8")
    citations_in(path, text, used)

    match = LAST_REVIEWED.search(text)
    if not match:
        errors.append(f"{path.relative_to(root)} has no last_reviewed date")
        continue
    try:
        age = (today - date.fromisoformat(match.group(1))).days
    except ValueError:
        errors.append(f"{path.relative_to(root)} has malformed last_reviewed date")
        continue
    if age > freshness_days:
        warnings.append((str(path.relative_to(root)), f"last reviewed {age} days ago"))

reference_files = sorted(root.glob("skills/*/references/checks.md"))
for path in reference_files:
    citations_in(path, path.read_text(encoding="utf-8"), used)

unused = sorted(set(index) - used)
if unused:
    errors.append(f"registered in SOURCE_INDEX.json but never cited: {unused}")

for path, message in warnings:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning file={path}::{message}")
    else:
        print(f"WARNING: {path} {message}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)

print(
    f"validated manifest.json, both source ledgers and {len(used)} cited source IDs "
    f"across {len(skill_files) + len(reference_files)} skill files"
)
