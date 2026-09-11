import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE_PLUGIN = Path("scripts/validate-plugin.py")
VALIDATE_SOURCES = Path("scripts/validate-sources.py")
VALIDATE_CITATIONS = Path("scripts/validate-citations.py")
GUARDRAILS = Path("skills/00-agent-reliability-guardrails/SKILL.md")
CHECKS = Path("skills/00-agent-reliability-guardrails/references/checks.md")


class RepositoryContractTest(unittest.TestCase):
    def run_script(self, script: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(ROOT / script)],
            capture_output=True,
            check=False,
            text=True,
        )

    def guardrails_text(self) -> str:
        return " ".join((ROOT / GUARDRAILS).read_text(encoding="utf-8").split())

    def checks_text(self) -> str:
        return " ".join((ROOT / CHECKS).read_text(encoding="utf-8").split())

    def test_plugin_registry_is_self_consistent(self) -> None:
        result = self.run_script(VALIDATE_PLUGIN)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_source_ledger_is_consistent(self) -> None:
        result = self.run_script(VALIDATE_SOURCES)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_citations_are_consistent(self) -> None:
        result = self.run_script(VALIDATE_CITATIONS)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_guardrails_skill_grades_against_the_system_of_record(self) -> None:
        text = self.guardrails_text()
        self.assertIn("Grade every sampled answer against the **system of record**", text)
        self.assertIn("Never grade an answer against the conversation transcript", text)

    def test_guardrails_skill_treats_tickets_as_a_lower_bound(self) -> None:
        text = self.guardrails_text()
        self.assertIn("detection channel, not a measurement", text)
        self.assertIn("lower bound on the error rate", text)

    def test_guardrails_skill_requires_sample_size_with_every_rate(self) -> None:
        text = self.guardrails_text()
        self.assertIn("Never report an error rate as a bare number", text)
        self.assertIn("carries its sample size and interval", text)

    def test_guardrails_skill_rejects_a_zero_error_budget(self) -> None:
        text = self.guardrails_text()
        self.assertIn("An error budget of zero is an unmeasured target", text)
        self.assertIn("number, a unit and a window", text)

    def test_guardrails_skill_separates_accuracy_from_coverage(self) -> None:
        text = self.guardrails_text()
        self.assertIn("must not be the role accountable for automation coverage", text)
        self.assertIn("sufficient independence to maintain objectivity", text)

    def test_guardrails_skill_forbids_autonomous_change(self) -> None:
        text = self.guardrails_text()
        self.assertIn("it does not change a running agent", text)
        for level in ("`0-Observe`, `1-Recommend` or `2-HITL`", "above `2-HITL`"):
            self.assertIn(level, text)

    def test_guardrails_skill_requires_conversation_sanitisation(self) -> None:
        text = self.guardrails_text()
        self.assertIn("Never copy raw customer text into a regression case", text)

    def test_guardrails_skill_requires_a_named_owner(self) -> None:
        text = self.guardrails_text()
        self.assertIn("names a person or a specific on-call function", text)
        self.assertIn("A team name, a queue", text)

    def test_guardrails_skill_defines_delegation_contract(self) -> None:
        text = self.guardrails_text()
        self.assertIn("Delegation contract", text)
        self.assertIn("load or reference this guardrails skill first", text)
        self.assertIn("agentic-commerce-skills", text)
        self.assertIn("skill-model-bench", text)

    def test_checks_verify_a_deliverable_not_the_skill(self) -> None:
        text = self.checks_text()
        self.assertIn("$REPORT", text)
        self.assertIn("not against a `SKILL.md`", text)

    def test_every_gate_header_is_covered_by_a_violating_fixture(self) -> None:
        import json
        import re

        gates = set(
            re.findall(
                r"^##[ \t]+(\d+\..+?)[ \t]*$",
                (ROOT / GUARDRAILS).read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )
        fixtures = json.loads(
            (
                ROOT
                / "skills/00-agent-reliability-guardrails/eval/fixtures/held-out-scenarios.json"
            ).read_text(encoding="utf-8")
        )
        covered = {
            entry["violates_gate"]
            for entry in fixtures
            if entry.get("expected") == "violates"
        }
        self.assertEqual(gates - covered, set(), "gates with no violating fixture")


if __name__ == "__main__":
    unittest.main()
