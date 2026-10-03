# Accuracy-ownership checks

Run these against a **delivered ownership record**, not against a `SKILL.md`. Set `$REPORT` to the
JSON deliverable produced by this skill. Each command exits non-zero when the contract fails. A
failing check makes the deliverable `BLOCK`.

### Normalisation and fixed values used below

- Normalised role: lowercase, parenthetical suffixes removed, punctuation stripped, whitespace
  collapsed. Roles are compared with whitespace removed as well, so `"Amina-Shah"` equals
  `"Amina Shah"`. Lowercasing is ASCII-only; non-ASCII letters are kept as written.
- `accuracy_owner_authority` values: `require_abstention_on_question_class` (the accuracy owner may
  require the surface to abstain on a question class without the coverage owner's agreement),
  `set_answer_bar`, `approve_answer_bar_change`, `require_regression_case`.
- `coverage_owner_authority` values: `prioritise_input_fixes`, `expand_scope_within_the_bar`,
  `propose_answer_bar_change`, `request_abstention_review`. A coverage veto such as overriding or
  blocking an abstention requirement is not a value, so it fails.
- Accuracy-owner standing: an accuracy owner who can only file an opinion lacks the standing to
  effect change [SRC-SR-26-2].

## Two distinct named roles

Equal owners fail under every normalisation: identical text, trailing punctuation, parenthetical
suffix, case and whitespace. A team, department, group, queue or committee is not a role.

```bash
jq -e '
  def normalized:
    ascii_downcase
    | gsub("\\([^)]*\\)"; "")
    | gsub("[^\\p{L}\\p{N}\\s]"; "")
    | gsub("\\s+"; " ")
    | gsub("^ | $"; "");
  def compact: normalized | gsub("\\s"; "");
  def named_role:
    type == "string" and (normalized | length > 0) and
    (normalized | test("^(the )?(tbd|todo|pending|unknown|na|none|owner|someone|somebody|person|named person|accuracy owner|coverage owner|support|engineering|operations|product|oncall|on call( function)?)$") | not) and
    (normalized | test("\\b(team|teams|department|group|queue|committee|board|council|everyone|distribution list|mailing list)\\b") | not);
  (.ownership.accuracy_owner | named_role) and
  (.ownership.coverage_owner | named_role) and
  ((.ownership.accuracy_owner | compact) != (.ownership.coverage_owner | compact))
' "$REPORT"
```

## The accuracy owner can require abstention without agreement, and neither owner holds a veto

```bash
jq -e '
  ["require_abstention_on_question_class", "set_answer_bar", "approve_answer_bar_change", "require_regression_case"] as $accuracy |
  ["prioritise_input_fixes", "expand_scope_within_the_bar", "propose_answer_bar_change", "request_abstention_review"] as $coverage |
  (.ownership.accuracy_owner_authority | type == "array" and length > 0 and length == (unique | length)) and
  (.ownership.coverage_owner_authority | type == "array" and length > 0 and length == (unique | length)) and
  (.ownership.accuracy_owner_authority | index("require_abstention_on_question_class") != null) and
  all(.ownership.accuracy_owner_authority[]; . as $value | $accuracy | index($value) != null) and
  all(.ownership.coverage_owner_authority[]; . as $value | $coverage | index($value) != null)
' "$REPORT"
```

## Disagreement has a named escalation path and the accuracy requirement stands meanwhile

The escalation target is neither owner, decides within a bounded number of days, and escalating
does not suspend an accuracy requirement.

```bash
jq -e '
  def normalized:
    ascii_downcase | gsub("\\([^)]*\\)"; "") | gsub("[^\\p{L}\\p{N}\\s]"; "") | gsub("\\s+"; " ") | gsub("^ | $"; "");
  def compact: normalized | gsub("\\s"; "");
  def named_role:
    type == "string" and (normalized | length > 0) and
    (normalized | test("^(the )?(tbd|todo|pending|unknown|na|none|owner|someone|somebody|person|named person|accuracy owner|coverage owner|support|engineering|operations|product|oncall|on call( function)?)$") | not) and
    (normalized | test("\\b(team|teams|department|group|queue|committee|board|council|everyone|distribution list|mailing list)\\b") | not);
  .ownership.escalation_path as $path |
  ($path | type == "object") and
  ($path.escalates_to | named_role) and
  (($path.escalates_to | compact) != (.ownership.accuracy_owner | compact)) and
  (($path.escalates_to | compact) != (.ownership.coverage_owner | compact)) and
  ($path.trigger | type == "string" and test("\\S")) and
  ($path.decision_within_days | type == "number" and . >= 1 and . <= 30 and floor == .) and
  ($path.interim_rule == "accuracy_requirement_stands")
' "$REPORT"
```

## The split has a reviewer who is neither owner and a review date

```bash
jq -e '
  def normalized:
    ascii_downcase | gsub("\\([^)]*\\)"; "") | gsub("[^\\p{L}\\p{N}\\s]"; "") | gsub("\\s+"; " ") | gsub("^ | $"; "");
  def compact: normalized | gsub("\\s"; "");
  def named_role:
    type == "string" and (normalized | length > 0) and
    (normalized | test("^(the )?(tbd|todo|pending|unknown|na|none|owner|someone|somebody|person|named person|accuracy owner|coverage owner|support|engineering|operations|product|oncall|on call( function)?)$") | not) and
    (normalized | test("\\b(team|teams|department|group|queue|committee|board|council|everyone|distribution list|mailing list)\\b") | not);
  def real_date:
    type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$") and
    (try ((strptime("%Y-%m-%d") | mktime | strftime("%Y-%m-%d")) == .) catch false);
  .ownership.review_cadence as $review |
  ($review | type == "object") and
  ($review.interval_days | type == "number" and . > 0 and . <= 366 and floor == .) and
  ($review.reviewer | named_role) and
  (($review.reviewer | compact) != (.ownership.accuracy_owner | compact)) and
  (($review.reviewer | compact) != (.ownership.coverage_owner | compact)) and
  ($review.next_review | real_date) and
  ($review.next_review >= (now | strftime("%Y-%m-%d")))
' "$REPORT"
```

## The one-minute retrieval test is a checkable list

Four items, each exactly once, each found in 60 seconds or fewer, each pointing at the contract
fields a reader should land on. A prose paragraph in place of the list fails.

```bash
jq -e '
  def real_date:
    type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$") and
    (try ((strptime("%Y-%m-%d") | mktime | strftime("%Y-%m-%d")) == .) catch false);
  {
    "scope_and_refusal": ["answer_surface.scope_statement", "answer_surface.refusal_rule"],
    "input_list_with_acknowledgement_dates": ["source_registry", "owner_acknowledgements.acknowledged_at"],
    "budget_with_sample_size": ["error_budget", "measurements.sample_size"],
    "alert_recipient_name": ["alerts.pages"]
  } as $required |
  (.retrieval_test | type == "array") and
  ([.retrieval_test[].id] | sort) == ($required | keys | sort) and
  all(.retrieval_test[];
    (.id as $id | $required | has($id)) and
    (.location | type == "string" and test("\\S") and
      (ascii_downcase | gsub("^\\s+|\\s+$"; "") | test("^(tbd|todo|pending|unknown|n/?a|none|placeholder|later)$") | not)) and
    (.points_to as $points | .id as $id | ($points | type == "array") and
      all($required[$id][]; . as $field | $points | index($field) != null)) and
    (.found == true) and
    (.seconds_to_find | type == "number" and . > 0 and . <= 60) and
    (.checked_on | real_date) and
    (.checked_on <= (now | strftime("%Y-%m-%d"))))
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

## No raw customer identifiers enter the record

A clean result is necessary, not sufficient; a human still confirms sanitisation.

```bash
jq -r '[.. | strings] | .[]' "$REPORT" \
  | grep -nEi '[[:alnum:]._%+-]+@[[:alnum:].-]+\.[a-z]{2,}|\+?([0-9][ ()-]*){8,}[0-9]|\border[ -]?#?[0-9]{4,}' \
  && echo "FAIL: unsanitised identifiers in deliverable" && exit 1 || exit 0
```
