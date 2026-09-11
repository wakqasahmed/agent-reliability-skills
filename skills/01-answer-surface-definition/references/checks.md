# Answer-surface checks

Run these against a **delivered answer-surface report**, not against a `SKILL.md`. Set `$REPORT`
to the JSON deliverable produced by this skill.

Each command exits non-zero when the contract fails. A failing check makes the deliverable
`BLOCK`.

## The answer-surface fields are present

```bash
jq -e '
  (.answer_surface | type == "object") and
  (.answer_surface.scope_statement | type == "string" and test("\\S")) and
  (.answer_surface.never_inferred | type == "array") and
  (.answer_surface.scope_owner | type == "object") and
  (.answer_surface.last_reviewed | type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$"))
' "$REPORT"
```

## The refusal rule is explicit

Reject a missing, blank or placeholder `refusal_rule`:

```bash
jq -e '
  .answer_surface.refusal_rule
  | type == "string" and test("\\S") and
    (ascii_downcase
      | test("^(tbd|todo|pending|unknown|n/?a|none|placeholder|to be (defined|decided|confirmed))$" )
      | not)
' "$REPORT"
```

## Every excluded class has a handoff

An empty `out_of_scope` fails, as does an entry without both values:

```bash
jq -e '
  (.answer_surface.out_of_scope | type == "array" and length > 0) and
  all(.answer_surface.out_of_scope[];
    (.question_class | type == "string" and test("\\S")) and
    (.handoff | type == "string" and test("\\S")) and
    ((.handoff | ascii_downcase)
      | test("^(tbd|todo|pending|unknown|n/?a|none)$|\\b(team|department|group|queue)\\b")
      | not))
' "$REPORT"
```

## Safety-relevant classes are never inferred

Use the fixed enum values; free prose cannot reliably enforce this boundary:

```bash
jq -e '
  (.answer_surface.never_inferred | type == "array") and
  (["health", "legal", "financial_commitment", "safety_claims"]
    - .answer_surface.never_inferred
    | length == 0)
' "$REPORT"
```

## The scope owner is named and accountable

The enum rejects team ownership as a semantic category. The name check also rejects generic
teams, departments, groups and queues passed off as a person or on-call function:

```bash
jq -e '
  .answer_surface.scope_owner.type as $owner_type |
  (.answer_surface.scope_owner.name | type == "string" and test("\\S")) and
  (["person", "on_call_function"] | index($owner_type) != null) and
  (.answer_surface.scope_owner.name
    | ascii_downcase
    | test("^(tbd|todo|pending|unknown|n/?a|none|support|engineering|operations|product)$|\\b(team|department|group|queue)\\b")
    | not)
' "$REPORT"
```

## The review date is valid

```bash
jq -e '
  (.answer_surface.last_reviewed | type == "string") and
  (try (.answer_surface.last_reviewed | strptime("%Y-%m-%d") | type == "array") catch false)
' "$REPORT"
```
