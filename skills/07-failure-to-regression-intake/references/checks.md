# Regression-intake checks

Run these against a **delivered intake report**, not against a `SKILL.md`. Set `$REPORT` to the
JSON deliverable produced by this skill. Each command exits non-zero when the contract fails. A
failing check makes the deliverable `BLOCK`.

### Definitions used below

- Failure classes and the role that fixes each: `missing_input`, `stale_input` and
  `conflicting_inputs` go to `source_owner`; `out_of_scope_answered` goes to `scope_owner`;
  `wrong_from_correct_inputs` goes to `accuracy_owner`.
- Case text is every string in a case except identifiers and dates (`id`, `violates_gate`,
  measurement ids, `closed_on`). It is scanned for: email addresses (including `[at]`, `(at)` and
  "at ... dot ..." spellings), phone numbers (eight or more digits with up to two separator characters between digits, after
  ISO dates are removed), any run of six or more digits, order, account, customer, invoice, ticket,
  tracking, booking and reference numbers, `#` numbers, `ABC-123456` style codes, UUIDs, and a
  greeting or title followed by a name. Prose fields are also scanned for first-person wording,
  which means customer text was pasted rather than reduced to a shape. These are heuristics: a
  clean run does not prove a case is sanitised, and a bare number such as `ISO-27001` can be a
  false positive that a human clears by rewording.
- What `skill-model-bench` loads (read from its source, `main` at commit `2f22e81`): a non-empty
  JSON list in `eval/fixtures/held-out-scenarios.json`; `scenario` required on every entry;
  `id`, `expected` and `violates_gate` read; every other key ignored; `expected` scored only as
  `follow` or `violates`. `provenance` (`authored` or `production`) is proposed in that
  repository's issue #32 and is not read by the loader yet.

## Every case has a failure class, and the class decides who fixes it

A missing or unknown class fails, and so does a fixer from the wrong role. The fixer is a person
or a specific on-call function, never a team, queue or placeholder (gate 6).

```bash
jq -e '
  {"missing_input": "source_owner", "stale_input": "source_owner", "conflicting_inputs": "source_owner",
   "out_of_scope_answered": "scope_owner", "wrong_from_correct_inputs": "accuracy_owner"} as $roles |
  def named:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("[^a-z0-9 ]"; "") | gsub("\\s+"; " ") | gsub("^ | $"; "")
     | test("^(tbd|todo|pending|unknown|na|none|owner|someone|somebody|person|support|engineering|operations|product|oncall|on call)$") | not) and
    (ascii_downcase | test("\\b(team|teams|department|group|queue|committee|distribution list|mailing list)\\b") | not);
  (.regression_cases | type == "array" and length > 0) and
  all(.regression_cases[];
    type == "object" and
    (.failure_class as $class |
      ($class | type == "string") and ($roles | has($class)) and (.fix_owner_role == $roles[$class])) and
    (.fix_owner | named))
' "$REPORT"
```

## A production case is only valid once sanitisation and channel reuse are confirmed

`provenance` is `production` for every case this skill emits. `sanitisation_confirmed` and
`channel_reuse_confirmed` are the boolean `true`, not a string and not omitted (gate 5).

```bash
jq -e '
  (.regression_cases | type == "array" and length > 0) and
  all(.regression_cases[];
    (.provenance == "production") and
    (.sanitisation_confirmed == true) and
    (.channel_reuse_confirmed == true))
' "$REPORT"
```

## Case text carries no identifiers, no customer wording and no pasted transcript

A clean result is necessary, not sufficient; a person still reads the case before setting
`sanitisation_confirmed`.

```bash
jq -e '
  def sans_dates: gsub("[0-9]{4}-[0-9]{2}-[0-9]{2}"; "");
  def dirty:
    sans_dates |
    (test("[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)*\\.[A-Za-z]{2,}") or
     test("[A-Za-z0-9._-]+\\s*(\\[at\\]|\\(at\\))\\s*[A-Za-z0-9-]+") or
     test("\\bat\\s+[a-z0-9-]+\\s+dot\\s+[a-z]{2,}"; "i") or
     test("\\+?[0-9](?:[\\s().-]{0,2}[0-9]){7,}") or
     test("\\b[0-9]{6,}\\b") or
     test("\\b(order|ord|account|acct|customer|cust|invoice|ticket|tracking|booking|reference|ref)\\b[\\s#:._-]*(no\\.?|num(ber)?|id)?[\\s#:._-]*[a-z]{0,5}[_-]?[0-9]{4,}"; "i") or
     test("#[0-9]{4,}") or
     test("\\b[A-Z]{2,6}[-_][0-9]{4,}\\b") or
     test("\\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\b"; "i") or
     test("\\b(?i:dear|hi|hello|thanks|regards|mr|mrs|ms|miss|dr)\\.?\\s+[A-Z][a-z]+"));
  def first_person: test("\\b(i|my|me|mine|myself)\\b"; "i");
  def prose: [.question_shape, .scenario, .grading_evidence.system_of_record_finding?, .fix.description?]
             | map(select(type == "string"));
  (.regression_cases | type == "array" and length > 0) and
  all(.regression_cases[];
    ([del(.id, .violates_gate, .grading_evidence.measurement_id, .verification_measurement.planned_id, .fix.closed_on)
      | .. | strings | select(dirty)] | length == 0) and
    ([prose[] | select(first_person)] | length == 0) and
    (.question_shape | type == "string" and test("\\S") and length <= 300 and (test("[\\n\\r]") | not)) and
    (.scenario | type == "string" and length <= 800 and (test("[\\n\\r]") | not))) and
  ([.recommendations[]? | .recommended_action | strings | select(dirty)] | length == 0)
' "$REPORT"
```

## Each case loads in skill-model-bench unchanged

The array `regression_cases` can be written to `eval/fixtures/held-out-scenarios.json` as it is.
Every entry has a unique non-empty `id`, a non-empty `scenario`, `expected` of `follow` or
`violates`, and a non-empty `violates_gate` on `violates` cases only. `provenance` is `authored`
or `production`.

```bash
jq -e '
  (.regression_cases | type == "array" and length > 0) and
  all(.regression_cases[];
    type == "object" and
    (.id | type == "string" and test("\\S")) and
    (.scenario | type == "string" and test("\\S")) and
    (.expected as $e | ["follow", "violates"] | index($e) != null) and
    (if .expected == "violates"
     then (.violates_gate | type == "string" and test("\\S"))
     else (has("violates_gate") | not) end) and
    (.provenance as $p | ["authored", "production"] | index($p) != null)) and
  ([.regression_cases[].id] | length == (unique | length))
' "$REPORT"
```

## Each case cites graded evidence from 04-accuracy-sampling-plan

`grading_evidence.measurement_id` is the `id` of exactly one `measurements[]` entry, which is a
`graded_sample` with a rate, a sample size and a Wilson interval, graded against a system of
record and not a transcript, a log, the agent, a ticket count or the same model (gate 1). The case
repeats that `graded_against` and names the `grader` and the finding.

```bash
jq -e '
  def named:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("[^a-z0-9 ]"; "") | gsub("\\s+"; " ") | gsub("^ | $"; "")
     | test("^(tbd|todo|pending|unknown|na|none|owner|someone|somebody|person|support|engineering|operations|product|oncall|on call)$") | not) and
    (ascii_downcase | test("\\b(team|teams|department|group|queue|committee|distribution list|mailing list)\\b") | not);
  def system_of_record:
    type == "string" and test("\\S") and
    (ascii_downcase | test("transcript|conversation|chat log|the agent|its own output|self-grade|same model|ticket|complaint") | not);
  . as $report |
  (.measurements | type == "array" and length > 0 and ([.[].id] | length == (unique | length))) and
  all(.regression_cases[];
    .grading_evidence as $g |
    ($g | type == "object") and
    ($g.measurement_id | type == "string") and
    ([$report.measurements[] | select(.id == $g.measurement_id)] as $found |
      ($found | length == 1) and
      ($found[0] |
        (.source == "graded_sample") and
        (.error_rate | type == "number" and . >= 0 and . <= 1) and
        (.sample_size | type == "number" and . > 0) and
        (.interval_bounds.method == "wilson") and
        (.graded_against | system_of_record) and
        (.graded_against == $g.graded_against))) and
    ($g.graded_against | system_of_record) and
    ($g.grader | named) and
    ($g.system_of_record_finding | type == "string" and test("\\S")))
' "$REPORT"
```

## The fix and the measurement that shows it stayed closed are recorded

`fix` is `open` or `closed`; a closed fix names who closed it and a real date that is not in the
future. `verification_measurement` plans a later graded sample of the question class: a
`planned_id` that differs from the measurement that found the failure, a per-class
`selection_method`, the metric `error_rate`, a system of record, and a positive integer minimum
sample size. Re-running a case in skill-model-bench is not that measurement.

```bash
jq -e '
  def named:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("[^a-z0-9 ]"; "") | gsub("\\s+"; " ") | gsub("^ | $"; "")
     | test("^(tbd|todo|pending|unknown|na|none|owner|someone|somebody|person|support|engineering|operations|product|oncall|on call)$") | not) and
    (ascii_downcase | test("\\b(team|teams|department|group|queue|committee|distribution list|mailing list)\\b") | not);
  def real_date:
    type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$") and
    (try ((strptime("%Y-%m-%d") | mktime | strftime("%Y-%m-%d")) == .) catch false);
  (.regression_cases | type == "array" and length > 0) and
  all(.regression_cases[];
    (.fix | type == "object") and
    (.fix.description | type == "string" and test("\\S")) and
    (.fix.status as $s | ["open", "closed"] | index($s) != null) and
    (if .fix.status == "closed"
     then (.fix.closed_by | named) and (.fix.closed_on | real_date) and
          (.fix.closed_on <= (now | strftime("%Y-%m-%d")))
     else true end) and
    (.verification_measurement as $v |
      ($v | type == "object") and
      ($v.planned_id | type == "string" and test("\\S")) and
      ($v.planned_id != .grading_evidence.measurement_id) and
      (["stratified_by_question_class", "oversampled_new_classes"] | index($v.selection_method) != null) and
      ($v.metric == "error_rate") and
      ($v.graded_against | type == "string" and test("\\S") and
        (ascii_downcase | test("transcript|conversation|chat log|the agent|its own output|self-grade|same model|ticket|complaint") | not)) and
      ($v.minimum_sample_size | type == "number" and . >= 1 and floor == .)))
' "$REPORT"
```

## Guardrail status is preserved and changes remain non-autonomous

```bash
jq -e '
  (.guardrail_status as $value | ["BLOCK", "CLEAR"] | index($value) != null) and
  (.status as $value | ["BLOCK", "CLEAR"] | index($value) != null) and
  (if .guardrail_status == "BLOCK" then .status == "BLOCK" else .status == "CLEAR" end) and
  (.recommendations? | type == "array") and
  all(.recommendations[];
    (.recommended_action | type == "string" and test("\\S")) and
    (.automation_level as $level |
      ["0-Observe", "1-Recommend", "2-HITL"] | index($level) != null) and
    (.execution_status == "not_applied"))
' "$REPORT"
```
