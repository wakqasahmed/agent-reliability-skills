# Readiness-review checks

Run these against a **delivered readiness report**, not against a `SKILL.md`. Set `$REPORT` to the
JSON deliverable produced by this skill. Each command exits non-zero when the contract fails. A
failing check makes the deliverable `HOLD`.

### Definitions used below

- Order of work by `surface_state`, as skill numbers: `no_surface_yet` is 01, 02, 03, 06, 04, 05,
  07; `about_to_ship` is 01, 02, 04, 05, 06, 03, 07; `live` is 04, 05, 06, 01, 02, 03, 07. `route`
  is a subsequence of that order with no repeats and contains the owning skill of every `missing`
  entry.
- Four retrieval items, each with the contract fields it points to: `scope_and_refusal`
  (`answer_surface.scope_statement`, `answer_surface.refusal_rule`),
  `input_list_with_acknowledgement_dates` (`source_registry`,
  `owner_acknowledgements.acknowledged_at`), `budget_with_sample_size` (`error_budget`,
  `measurements.sample_size`) and `alert_recipient_name` (`alerts.pages`). `points_to` may add other
  fields from the known list below and nothing else.
- Missing artefacts, each with its owning skill and retrieval item: `scope_statement` and
  `refusal_rule` (01, `scope_and_refusal`); `source_registry` and `owner_acknowledgements` (02,
  `input_list_with_acknowledgement_dates`); `error_budget` (05, `budget_with_sample_size`);
  `sample_size` (04, `budget_with_sample_size`); `alert_recipient` (05, `alert_recipient_name`);
  `accuracy_owner` (06, no retrieval item).
- A named role is a person or a specific on-call function. A team, department, queue, placeholder
  (`TBD`, `TBC`, `unassigned`, `nobody`, `-`) or blank is not (gate 6).

## The surface state is set and the route follows its order of work

```bash
jq -e '
  {"no_surface_yet": ["01-answer-surface-definition", "02-input-exposure-inventory", "03-abstention-policy-design", "06-accuracy-ownership-separation", "04-accuracy-sampling-plan", "05-error-budget-and-burn-alerting", "07-failure-to-regression-intake"],
   "about_to_ship": ["01-answer-surface-definition", "02-input-exposure-inventory", "04-accuracy-sampling-plan", "05-error-budget-and-burn-alerting", "06-accuracy-ownership-separation", "03-abstention-policy-design", "07-failure-to-regression-intake"],
   "live": ["04-accuracy-sampling-plan", "05-error-budget-and-burn-alerting", "06-accuracy-ownership-separation", "01-answer-surface-definition", "02-input-exposure-inventory", "03-abstention-policy-design", "07-failure-to-regression-intake"]} as $orders |
  .readiness as $r |
  if ($r.surface_state | type) == "string" and ($orders | has($r.surface_state)) and
     ($r.route | type) == "array" and ($r.missing | type) == "array"
  then
    $orders[$r.surface_state] as $order |
    [$r.route[] | . as $skill | $order | index($skill)] as $positions |
    all($positions[]; . != null) and
    ($positions == ($positions | sort)) and
    (($positions | length) == ($positions | unique | length)) and
    (([$r.missing[].owning_skill] | unique) - $r.route == [])
  else false end
' "$REPORT"
```

## The four retrieval items are listed once each, with evidence and real contract fields

A paragraph in place of the list fails, and so does an item that points at a field no skill in
`01` through `07` defines. Evidence is at least three words, so `yes`, `found` or `-` is not evidence.

```bash
jq -e '
  {"scope_and_refusal": ["answer_surface.scope_statement", "answer_surface.refusal_rule"],
   "input_list_with_acknowledgement_dates": ["source_registry", "owner_acknowledgements.acknowledged_at"],
   "budget_with_sample_size": ["error_budget", "measurements.sample_size"],
   "alert_recipient_name": ["alerts.pages"]} as $required |
  ["answer_surface.scope_statement", "answer_surface.refusal_rule", "source_registry", "source_registry.owning_team",
   "owner_acknowledgements.acknowledged_at", "error_budget", "error_budget.value", "error_budget.unit",
   "error_budget.window", "measurements.sample_size", "alerts.pages", "ownership.accuracy_owner"] as $known |
  (.readiness.retrieval_test | type == "array") and
  ([.readiness.retrieval_test[].id] | sort) == ($required | keys | sort) and
  all(.readiness.retrieval_test[];
    (.present | type == "boolean") and
    (.evidence | type == "string" and test("\\S") and ([scan("[A-Za-z0-9]+")] | length >= 3) and
      (ascii_downcase | gsub("^\\s+|\\s+$"; "") | test("^(tbd|todo|pending|unknown|n/?a|none|placeholder|later|yes|ok)$") | not)) and
    (.id as $id | .points_to as $points |
      ($points | type == "array") and
      all($required[$id][]; . as $field | $points | index($field) != null) and
      all($points[]; . as $field | $known | index($field) != null)))
' "$REPORT"
```

## A present item is backed by what was retrieved

`present: true` needs the value behind it: one sentence each for scope and refusal, an
acknowledgement date against every input, a budget above zero and below 100% with a unit, a window and a sample size,
and a named alert recipient. A zero target spelled in prose fails anywhere in the report (gates 1, 2
and 6).

```bash
jq -e '
  def nonblank: type == "string" and test("\\S");
  def named:
    type == "string" and test("[\\p{L}\\p{N}]") and
    (ascii_downcase | gsub("[^\\p{L}\\p{N}]+"; " ") | gsub("^ | $"; "") as $n
     | ($n | test("^(tbd|todo|pending|unknown|na|n a|none|name|owner|someone|somebody|person|support|engineering|operations|product|oncall|on call|open)$") | not) and
       ($n | test("(^| )(tbd|tbc|tba|todo|unknown|unassigned|unnamed|vacant|undefined|null|nobody|noone|none|someone|somebody|anyone|everyone|no one|no owner|not assigned|to be (decided|determined|confirmed|assigned|named))( |$)") | not)) and
    (ascii_downcase | test("\\b(team|teams|department|group|queue|committee|distribution list|mailing list|squad|pod|guild|tribe|division|organisation|organization|org)\\b") | not);
  def placeholder_free:
    type == "string" and test("[\\p{L}\\p{N}]") and
    (ascii_downcase | gsub("[^\\p{L}\\p{N}]+"; " ") | gsub("^ | $"; "")
     | test("(^| )(tbd|tbc|tba|todo|unknown|unassigned|unnamed|vacant|undefined|null|nobody|noone|none|na|n a|no one|not assigned)( |$)") | not);
  def budget_fraction:
    .value as $v | .unit as $u |
    if ($v | type) != "number" then null
    elif $u == "fraction_of_answers" then $v
    elif $u == "percent_of_answers" then $v / 100
    elif $u == "errors_per_1000_answers" then $v / 1000
    else null end;
  def one_sentence: nonblank and (test("[.!?]\\s+[A-Za-z0-9]") | not);
  def real_date:
    type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$") and
    (try ((strptime("%Y-%m-%d") | mktime | strftime("%Y-%m-%d")) == .) catch false);
  .readiness as $r |
  ($r.retrieval_test | map({key: .id, value: .present}) | from_entries) as $present |
  ($r.retrieved | type == "object") and
  (($r.retrieved | keys) - ["scope_statement", "refusal_rule", "inputs", "error_budget", "alert_recipient", "accuracy_owner"] == []) and
  (if $present.scope_and_refusal
   then ($r.retrieved.scope_statement | one_sentence) and ($r.retrieved.refusal_rule | one_sentence)
   else true end) and
  (if $present.input_list_with_acknowledgement_dates
   then ($r.retrieved.inputs | type == "array" and length > 0 and
         all(.[]; (.source_id | nonblank) and (.owning_team | placeholder_free) and
                  (.acknowledged_at | real_date) and (.acknowledged_at <= (now | strftime("%Y-%m-%d")))))
   else true end) and
  (if $present.budget_with_sample_size
   then ($r.retrieved.error_budget | type == "object" and
         (budget_fraction | . != null and . > 0 and . < 1) and
         (.unit as $u | ["fraction_of_answers", "percent_of_answers", "errors_per_1000_answers"] | index($u) != null) and
         (.window | type == "string" and test("^[1-9][0-9]*[hdw]$")) and
         (.sample_size | type == "number" and . > 0 and floor == .))
   else true end) and
  (if $present.alert_recipient_name then ($r.retrieved.alert_recipient | named) else true end) and
  ([.. | strings]
   | all(ascii_downcase
         | test("zero[ -](tolerance|error|defect|incident)|no (errors?|mistakes|wrong answers?|incorrect answers?) (are |is )?(allowed|permitted|acceptable|tolerated)|100 ?% ?(accura|correct|right)|perfect accuracy|error budget (of|is|=) ?(0|zero|none|nil)") | not))
' "$REPORT"
```

## Every item that is not present names the missing artefact and the skill that produces it

An entry outside the table above fails, so does the wrong owning skill, and so does an item that is
absent with nothing missing against it. Commerce artefacts are not in the table and cannot be added.

```bash
jq -e '
  {"scope_statement": ["01-answer-surface-definition", "scope_and_refusal"],
   "refusal_rule": ["01-answer-surface-definition", "scope_and_refusal"],
   "source_registry": ["02-input-exposure-inventory", "input_list_with_acknowledgement_dates"],
   "owner_acknowledgements": ["02-input-exposure-inventory", "input_list_with_acknowledgement_dates"],
   "error_budget": ["05-error-budget-and-burn-alerting", "budget_with_sample_size"],
   "sample_size": ["04-accuracy-sampling-plan", "budget_with_sample_size"],
   "alert_recipient": ["05-error-budget-and-burn-alerting", "alert_recipient_name"],
   "accuracy_owner": ["06-accuracy-ownership-separation", null]} as $catalogue |
  .readiness as $r |
  ($r.missing | type == "array") and
  all($r.missing[];
    type == "object" and
    (.artefact as $a | ($a | type == "string") and ($catalogue | has($a)) and
      (.owning_skill == $catalogue[$a][0]) and (.retrieval_item == $catalogue[$a][1]))) and
  (([$r.missing[].artefact] | length) == ([$r.missing[].artefact] | unique | length)) and
  ([$r.retrieval_test[] | select(.present | not) | .id] as $absent |
    all($absent[]; . as $id | any($r.missing[]; .retrieval_item == $id)) and
    all($r.missing[]; .retrieval_item == null or (.retrieval_item as $item | $absent | index($item) != null)))
' "$REPORT"
```

## READY is impossible with anything missing or an unnamed accuracy owner

`READY` needs every item present, nothing missing, a named accuracy owner and `guardrail_status` of
`CLEAR`. `HOLD` always names at least one missing artefact. An accuracy owner that is not a named
person or specific on-call function is a missing `accuracy_owner`, routed to
`06-accuracy-ownership-separation`.

```bash
jq -e '
  def named:
    type == "string" and test("[\\p{L}\\p{N}]") and
    (ascii_downcase | gsub("[^\\p{L}\\p{N}]+"; " ") | gsub("^ | $"; "") as $n
     | ($n | test("^(tbd|todo|pending|unknown|na|n a|none|name|owner|someone|somebody|person|support|engineering|operations|product|oncall|on call|open)$") | not) and
       ($n | test("(^| )(tbd|tbc|tba|todo|unknown|unassigned|unnamed|vacant|undefined|null|nobody|noone|none|someone|somebody|anyone|everyone|no one|no owner|not assigned|to be (decided|determined|confirmed|assigned|named))( |$)") | not)) and
    (ascii_downcase | test("\\b(team|teams|department|group|queue|committee|distribution list|mailing list|squad|pod|guild|tribe|division|organisation|organization|org)\\b") | not);
  .readiness as $r |
  .guardrail_status as $guardrails |
  (["READY", "HOLD"] | index($r.status) != null) and
  (["CLEAR", "BLOCK"] | index($guardrails) != null) and
  ($r.retrieved.accuracy_owner | named) as $owned |
  (any($r.missing[]; .artefact == "accuracy_owner")) as $owner_missing |
  ($owned == ($owner_missing | not)) and
  (if $r.status == "READY"
   then (($r.missing | length) == 0) and
        all($r.retrieval_test[]; .present == true) and
        $owned and ($guardrails == "CLEAR")
   else ($r.missing | length) > 0 end)
' "$REPORT"
```

## Commerce concerns are delegated, not answered here

For a storefront, catalogue, feed, policy and protocol readiness go to `agentic-commerce-skills`
with `answered_here` false. For anything else the delegation list is empty. Only the documented
keys are allowed in the report, in `readiness` and in `commerce_delegation`, so no key can carry an
assessment of a commerce concern.

```bash
jq -e '
  .readiness.commerce_delegation as $c |
  ($c | type == "object") and
  ($c.storefront | type == "boolean") and
  ($c.delegated_concerns | type == "array") and
  all($c.delegated_concerns[]; . as $d | ["catalogue", "feed", "policy", "protocol", "discoverability", "agent_actions"] | index($d) != null) and
  (if $c.storefront
   then ($c.delegate_to == "agentic-commerce-skills") and
        ($c.url == "https://github.com/wakqasahmed/agentic-commerce-skills") and
        (["catalogue", "feed", "policy", "protocol"] - $c.delegated_concerns == []) and
        ($c.answered_here == false)
   else ($c.delegated_concerns == []) and ($c | has("delegate_to") | not) and ($c | has("url") | not) end) and
  (($c | keys) - ["storefront", "delegate_to", "url", "delegated_concerns", "answered_here"] == []) and
  (($c.delegated_concerns | length) == ($c.delegated_concerns | unique | length)) and
  ((.readiness | keys) - ["surface_state", "route", "retrieval_test", "retrieved", "missing", "commerce_delegation", "status"] == []) and
  ((keys) - ["readiness", "recommendations", "guardrail_status"] == [])
' "$REPORT"
```

## Guardrail status is preserved and changes remain non-autonomous

```bash
jq -e '
  (.guardrail_status as $value | ["BLOCK", "CLEAR"] | index($value) != null) and
  (if .guardrail_status == "BLOCK" then .readiness.status == "HOLD" else true end) and
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
