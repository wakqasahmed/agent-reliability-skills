# Guardrail checks

Run these against a **delivered plan or report**, not against a `SKILL.md`. Set `$REPORT` to
the JSON deliverable produced by a skill in this pack.

Each command exits non-zero when a hard gate fails. A failing gate makes the deliverable
`BLOCK`.

## Every reported rate carries its sample

A rate without the sample behind it is not a measurement.

```bash
jq -e '
  all((.measurements // [])[];
    (.error_rate | type == "number") and
    (.sample_size | type == "number" and . > 0) and
    (.interval | type == "string" and test("\\S")) and
    (.graded_against | type == "string" and test("\\S")))
' "$REPORT"
```

`graded_against` names the system of record. Reject `transcript`, `conversation`, `the model`
or the agent's own output:

```bash
jq -e '
  all((.measurements // [])[];
    .graded_against
    | ascii_downcase
    | test("transcript|conversation log|the agent|its own output|self-grade|same model") | not)
' "$REPORT"
```

## Ticket counts are never presented as an error rate

```bash
jq -e '
  all((.measurements // [])[];
    (.source // "") | ascii_downcase | test("^ticket|support volume|complaint count") | not)
' "$REPORT"
```

## Error budget is non-zero and has a unit and a window

```bash
jq -e '
  (.error_budget.value | type == "number" and . > 0) and
  (.error_budget.unit | type == "string" and test("\\S")) and
  (.error_budget.window | type == "string" and test("\\S"))
' "$REPORT"
```

Catch a zero target spelled in prose anywhere in the deliverable:

```bash
jq -e '
  [.. | strings]
  | all(ascii_downcase
        | test("(zero|no) (tolerance|errors?) (for|allowed)|100% accura|error budget of (0|zero)") | not)
' "$REPORT"
```

## Accuracy owner and coverage owner are two different named roles

```bash
jq -e '
  def named: type == "string" and test("\\S") and
    (ascii_downcase | test("^(tbd|todo|pending|unknown|n/a|na|none|team|the team)$") | not);
  (.ownership.accuracy_owner | named) and
  (.ownership.coverage_owner | named) and
  ((.ownership.accuracy_owner | ascii_downcase | gsub("[^a-z0-9]"; "")) !=
   (.ownership.coverage_owner | ascii_downcase | gsub("[^a-z0-9]"; "")))
' "$REPORT"
```

## Every alert reaches a name, not a queue

```bash
jq -e '
  all((.alerts // [])[];
    .pages | type == "string" and test("\\S") and
    (ascii_downcase | test("^(tbd|todo|pending|unknown|n/a|na|none|team|support|engineering)$") | not))
' "$REPORT"
```

## Nothing recommends an autonomous change

```bash
jq -e '
  all((.recommendations // [])[];
    (.recommended_action | type == "string" and test("\\S")) and
    (["0-Observe", "1-Recommend", "2-HITL"] | index(.automation_level) != null))
' "$REPORT"
```

## Sampled conversations were sanitised

Flags the obvious identifier shapes surviving into a deliverable. A clean run is necessary,
not sufficient — a human still confirms sanitisation before anything leaves the operator.

```bash
jq -r '[.. | strings] | .[]' "$REPORT" \
  | grep -nEi '[[:alnum:]._%+-]+@[[:alnum:].-]+\.[a-z]{2,}|\+?[0-9][0-9 ()-]{8,}[0-9]|\border[ -]?#?[0-9]{4,}' \
  && echo "FAIL: unsanitised identifiers in deliverable" && exit 1 || exit 0
```
