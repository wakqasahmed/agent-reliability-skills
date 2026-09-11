# Abstention-policy checks

Run these against a **delivered abstention-policy report**, not against a `SKILL.md`. Set `$REPORT`
to the JSON deliverable produced by this skill. Each command exits non-zero when the contract
fails. A failing check makes the deliverable `BLOCK`.

## Source registry preserves the interoperable contract

Reject an absent or empty registry, renamed or extra fields, invalid semantic values, duplicate
IDs, and freshness mechanisms without substantive detail.

```bash
jq -e '
  def nonempty: type == "string" and test("\\S");
  def substantive:
    nonempty and
    (test("\\b(tbd|todo|not applicable|to be determined)\\b|(^|[^[:alnum:]_])n/a([^[:alnum:]_]|$)|^[[:space:]]*(pending|unknown|none|later)[.!]?[[:space:]]*$"; "i") | not);
  def valid_keys:
    (keys | sort) as $keys |
    $keys == ["agent_speaks_from", "freshness_basis", "owner_exposure", "owning_team", "source_id"] or
    $keys == ["agent_speaks_from", "freshness_basis", "freshness_detail", "owner_exposure", "owning_team", "source_id"];
  def valid_source:
    type == "object" and
    valid_keys and
    (.source_id | nonempty) and
    (.owning_team | nonempty) and
    (.agent_speaks_from | type == "boolean") and
    (.owner_exposure as $value |
      ["acknowledged", "not_notified", "unknown"] | index($value) != null) and
    (.freshness_basis as $basis |
      (["scheduled", "event_driven", "none", "unknown"] | index($basis) != null) and
      if $basis == "scheduled" or $basis == "event_driven" then
        (.freshness_detail | substantive)
      else
        ((has("freshness_detail") | not) or .freshness_detail == "")
      end);
  (.source_registry? | type == "array") and
  (.source_registry | length > 0) and
  (all(.source_registry[]; valid_source)) and
  ([.source_registry[].source_id] | length == (unique | length))
' "$REPORT"
```

## Every mandatory evidence trigger is present

Use the fixed enum set. This rejects a policy with no `conflicting_sources` trigger even when a
free-text note mentions conflicting evidence.

```bash
jq -e '
  [
    "no_supporting_source",
    "conflicting_sources",
    "source_older_than_freshness_basis",
    "out_of_scope_question"
  ] as $required |
  (.abstention_policy.trigger_conditions? | type == "array") and
  (.abstention_policy.trigger_conditions | length == (unique | length)) and
  (all(.abstention_policy.trigger_conditions[]; . as $value | $required | index($value) != null)) and
  ($required - .abstention_policy.trigger_conditions | length == 0)
' "$REPORT"
```

## Customer behaviour is a useful refusal with handoff

The disposition enum rejects termination without handoff. The required booleans, customer-ready
message, named human target and instructions make the handoff actionable.

```bash
jq -e '
  def substantive:
    type == "string" and test("\\S") and
    (ascii_downcase | test("^(tbd|todo|pending|unknown|n/?a|none|placeholder|later)$") | not);
  def named:
    substantive and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(the )?(owner|someone|somebody|person|named person|on[ _-]?call( function)?|support|engineering|operations|product)$|\\b(team|department|group|queue)\\b") | not);
  (.abstention_policy.customer_behaviour.disposition == "refuse_and_handoff") and
  (.abstention_policy.customer_behaviour.explain_reason == true) and
  (.abstention_policy.customer_behaviour.offer_handoff == true) and
  (.abstention_policy.customer_behaviour.message | substantive) and
  (.abstention_policy.handoff.type == "human") and
  (.abstention_policy.handoff.target.type as $target_type |
    ["person", "on_call_function"] | index($target_type) != null) and
  (.abstention_policy.handoff.target.name | named) and
  (.abstention_policy.handoff.instructions | substantive)
' "$REPORT"
```

## The operating point has a distinct accuracy owner

Owner accountability and type are semantic enums. Normalized names must differ, so punctuation,
spacing and case cannot disguise one person or function holding both roles.

```bash
jq -e '
  def named:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(the )?(tbd|todo|pending|unknown|n/?a|none|owner|someone|somebody|person|named person|on[ _-]?call( function)?|support|engineering|operations|product|accuracy owner|coverage owner)$|\\b(team|department|group|queue)\\b") | not);
  def normalized: ascii_downcase | gsub("[^a-z0-9]"; "");
  (.abstention_policy.operating_point.metric | named) and
  (.abstention_policy.operating_point.answer_threshold | type == "number" and . > 0 and . <= 1) and
  (.abstention_policy.operating_point.trigger_precedence == "mandatory_abstention") and
  (.abstention_policy.threshold_owner.accountability == "accuracy_owner") and
  (.abstention_policy.threshold_owner.type as $owner_type |
    ["person", "on_call_function"] | index($owner_type) != null) and
  (.abstention_policy.threshold_owner.name | named) and
  (.abstention_policy.expected_coverage_impact.coverage_owner.name | named) and
  ((.abstention_policy.threshold_owner.name | normalized) !=
   (.abstention_policy.expected_coverage_impact.coverage_owner.name | normalized))
' "$REPORT"
```

## Review cadence requires evidence for change

```bash
jq -e '
  [
    "system_of_record_error_measurement",
    "abstention_rate_measurement",
    "coverage_impact_measurement"
  ] as $required |
  (.abstention_policy.review_cadence.interval_days | type == "number" and . > 0 and floor == .) and
  (.abstention_policy.review_cadence.change_evidence? | type == "array") and
  (.abstention_policy.review_cadence.change_evidence | length == (unique | length)) and
  (all(.abstention_policy.review_cadence.change_evidence[];
    . as $value | $required | index($value) != null)) and
  ($required - .abstention_policy.review_cadence.change_evidence | length == 0)
' "$REPORT"
```

## The coverage owner agrees a known numeric impact

Percentage units are bounded from 0 through 100; `answers_per_1000` is an integer from 0 through
1000. Zero is valid only as a known, explicitly agreed value, never as a stand-in for unknown. The
agreement date must be a real, nonfuture calendar date.

```bash
jq -e '
  def named:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(the )?(tbd|todo|pending|unknown|n/?a|none|owner|someone|somebody|person|named person|on[ _-]?call( function)?|support|engineering|operations|product|accuracy owner|coverage owner)$|\\b(team|department|group|queue)\\b") | not);
  (.abstention_policy.expected_coverage_impact as $impact |
    ($impact.value | type == "number" and . >= 0) and
    ($impact.unit as $unit |
      ["percentage_points", "percent_relative", "answers_per_1000"] | index($unit) != null) and
    (if $impact.unit == "answers_per_1000" then
       ($impact.value <= 1000 and ($impact.value | floor) == $impact.value)
     else
       $impact.value <= 100
     end)) and
  (.abstention_policy.expected_coverage_impact.direction == "coverage_decrease") and
  (.abstention_policy.expected_coverage_impact.coverage_owner.accountability == "coverage_owner") and
  (.abstention_policy.expected_coverage_impact.coverage_owner.type as $owner_type |
    ["person", "on_call_function"] | index($owner_type) != null) and
  (.abstention_policy.expected_coverage_impact.coverage_owner.name | named) and
  (.abstention_policy.expected_coverage_impact.agreement_status == "agreed") and
  (.abstention_policy.expected_coverage_impact.agreed_at as $agreed_at |
    ($agreed_at | type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$")) and
    (try (($agreed_at | strptime("%Y-%m-%d") | mktime | strftime("%Y-%m-%d")) == $agreed_at) catch false) and
    ($agreed_at <= (now | strftime("%Y-%m-%d"))))
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

## No raw customer identifiers enter the policy report

A clean result is necessary, not sufficient; a human still confirms sanitisation.

```bash
jq -r '[.. | strings] | .[]' "$REPORT" \
  | grep -nEi '[[:alnum:]._%+-]+@[[:alnum:].-]+\.[a-z]{2,}|\+?([0-9][ ()-]*){8,}[0-9]|\border[ -]?#?[0-9]{4,}' \
  && echo "FAIL: unsanitised identifiers in deliverable" && exit 1 || exit 0
```
