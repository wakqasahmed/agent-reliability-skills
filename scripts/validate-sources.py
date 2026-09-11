#!/usr/bin/env python3
import argparse
import re
from datetime import date
from pathlib import Path


SOURCE_ID = re.compile(r"SRC-[A-Z0-9]+(?:-[A-Z0-9]+)*")
SOURCE_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
CITATION = re.compile(r"\[(SRC[^\]\n]*)\]", re.IGNORECASE)
REQUIRED_FIELDS = (
    "Publisher",
    "Official URL",
    "Supported claim",
    "Specification version",
    "Last verified",
)

# One entry per instruction line that must carry a specific citation. The anchor must match
# exactly one line in the file, so it fails loudly if the instruction is reworded away.
REQUIRED_CITATIONS: tuple[tuple[Path, str, tuple[str, ...]], ...] = (
    (
        Path("skills/00-agent-reliability-guardrails/SKILL.md"),
        "A business that uses an AI agent remains responsible for what that agent does",
        ("SRC-CMA-AI-AGENTS",),
    ),
    (
        Path("skills/00-agent-reliability-guardrails/SKILL.md"),
        "Alerting is on burn rate, not on individual bad answers",
        ("SRC-SRE-BURN-RATE",),
    ),
    (
        Path("skills/00-agent-reliability-guardrails/SKILL.md"),
        "sufficient independence to maintain objectivity",
        ("SRC-SR-26-2",),
    ),
    (
        Path("skills/03-abstention-policy-design/SKILL.md"),
        "Treat abstention as an operating point between error and rejection",
        ("SRC-CHOW-REJECT-TRADEOFF",),
    ),
    (
        Path("skills/03-abstention-policy-design/SKILL.md"),
        "penalize confident errors more than abstentions",
        ("SRC-OPENAI-HALLUCINATION-EVALS",),
    ),
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate registered source citations.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def parse_ledger(ledger: Path) -> tuple[dict[str, dict[str, str]], int, list[str]]:
    if not ledger.is_file():
        return {}, 0, ["missing SOURCES.md"]

    text = ledger.read_text()
    freshness_match = re.search(r"^Freshness window:[ \t]*(\d+)[ \t]*days\.[ \t]*$", text, re.MULTILINE)
    errors = [] if freshness_match else ["malformed or missing freshness window"]
    freshness_days = int(freshness_match.group(1)) if freshness_match else 0

    headings = list(SOURCE_HEADING.finditer(text))
    entries: dict[str, dict[str, str]] = {}

    for index, heading in enumerate(headings):
        source_id = heading.group(1).strip()
        if not SOURCE_ID.fullmatch(source_id):
            errors.append(f"malformed source heading {source_id}")
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        fields = {k.strip(): v.strip() for k, v in re.findall(r"^- ([A-Za-z ]+):\s*(.+)$", body, re.MULTILINE)}
        if source_id in entries:
            errors.append(f"duplicate source {source_id}")
        entries[source_id] = fields
        for field in REQUIRED_FIELDS:
            if not fields.get(field):
                errors.append(f"{source_id}: missing {field}")

        url = fields.get("Official URL", "")
        if url and not re.fullmatch(r"https://\S+", url):
            errors.append(f"{source_id}: malformed Official URL")

        verified = fields.get("Last verified", "")
        if verified:
            try:
                verified_date = date.fromisoformat(verified)
            except ValueError:
                errors.append(f"{source_id}: malformed Last verified date")
            else:
                if verified_date > date.today():
                    errors.append(f"{source_id}: Last verified date is in the future")

    if not entries:
        errors.append("SOURCES.md contains no source entries")
    return entries, freshness_days, errors


def markdown_citations(root: Path) -> tuple[set[str], list[str]]:
    citations: set[str] = set()
    malformed: set[str] = set()
    for markdown_file in root.rglob("*.md"):
        if markdown_file.name == "SOURCES.md" or ".git" in markdown_file.parts:
            continue
        for citation in CITATION.findall(markdown_file.read_text()):
            c_upper = citation.upper()
            if SOURCE_ID.fullmatch(c_upper):
                citations.add(c_upper)
            else:
                malformed.add(citation)
    return citations, [f"malformed citation {citation}" for citation in sorted(malformed)]


def required_citation_errors(root: Path) -> list[str]:
    errors = []
    for relative_path, anchor, source_ids in REQUIRED_CITATIONS:
        path = root / relative_path
        if not path.is_file():
            errors.append(f"{relative_path}: missing file required to carry {anchor!r}")
            continue

        matching_lines = [line for line in path.read_text().splitlines() if anchor in line]
        if len(matching_lines) != 1:
            errors.append(
                f"{relative_path}: expected one instruction anchored by '{anchor}', "
                f"found {len(matching_lines)}"
            )
            continue

        for source_id in source_ids:
            citation = f"[{source_id}]"
            if citation not in matching_lines[0]:
                errors.append(
                    f"{relative_path}: instruction '{anchor}' requires {citation}"
                )
    return errors


def main() -> int:
    root = parse_arguments().root.resolve()
    entries, freshness_days, errors = parse_ledger(root / "SOURCES.md")
    citations, citation_errors = markdown_citations(root)
    errors.extend(citation_errors)
    errors.extend(required_citation_errors(root))

    for source_id in sorted(citations - entries.keys()):
        errors.append(f"unregistered citation {source_id}")
    for source_id in sorted(entries.keys() - citations):
        errors.append(f"unused source {source_id}")

    today = date.today()
    for source_id, fields in sorted(entries.items()):
        verified = fields.get("Last verified")
        if not verified or not freshness_days:
            continue
        try:
            age = (today - date.fromisoformat(verified)).days
        except ValueError:
            continue
        if age > freshness_days:
            print(f"warning: {source_id} was last verified {age} days ago")

    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1

    print(f"validated {len(entries)} sources and {len(citations)} cited source IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
