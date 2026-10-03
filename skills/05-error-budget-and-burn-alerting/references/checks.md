# Error-budget and burn-alerting checks

Run these against a **delivered budget and alerting plan**, not against a `SKILL.md`. Set
`$REPORT` to the JSON deliverable produced by this skill. Each command exits non-zero when the
contract fails. A failing check makes the deliverable `BLOCK`.

### Definitions used below

- Budget as a fraction `b`: `value` for `fraction_of_answers`, `value / 100` for
  `percent_of_answers`, `value / 1000` for `errors_per_1000_answers`. It must be above 0 and below 1.
- Windows are a positive integer plus `h`, `d` or `w` (hours, days, weeks) and are compared in hours.
- Burn rate is how fast the budget is consumed relative to the budget: a burn rate of 1 consumes
  exactly the budget over the budget window. `budget_consumed` is
  `burn_rate * window / budget window`, the share of the budget spent if the burn is sustained for
  the alert's long window [SRC-SRE-BURN-RATE].
- Sampled-signal floor: `graded_answers_in_window * burn_rate * b >= 5`. This is this pack's rule
  of thumb, not a published threshold. Below it a single bad answer can trip the alert.

## The budget is non-zero, with a unit and a window

A string, `null`, `0`, a negative number or a value of 100% or more fails, and so does a zero
target spelled in prose anywhere in the deliverable.

```bash
jq -e '
  def budget_fraction:
    .value as $v | .unit as $u |
    if ($v | type) != "number" then null
    elif $u == "fraction_of_answers" then $v
    elif $u == "percent_of_answers" then $v / 100
    elif $u == "errors_per_1000_answers" then $v / 1000
    else null end;
  (.error_budget | type == "object") and
  (.error_budget | budget_fraction) as $b |
  ($b != null and $b > 0 and $b < 1) and
  (.error_budget.window | type == "string" and test("^[1-9][0-9]*[hdw]$")) and
  ([.. | strings]
   | all(ascii_downcase
         | test("zero[ -](tolerance|error|defect|incident)|no (errors?|mistakes|wrong answers?|incorrect answers?|bad answers?) (are |is )?(allowed|permitted|acceptable|tolerated)|100 ?% ?(accura|correct|right)|perfect accuracy|never (be )?wrong|error budget (of|is|=) ?(0|zero|none|nil)|(^|[^0-9.])0 ?% ?(error|failure|wrong|budget)") | not))
' "$REPORT"
```

## The budget derives from a measurement and breach is reported

`derived_from` must name exactly one measurement `id` in `measurements[]` (the output of
`04-accuracy-sampling-plan`). When the budget is below that measurement's Wilson lower bound the
report must say `already_in_breach`; otherwise `not_proven_in_breach`. A breach reported as
within range is accepted silently, which this check rejects.

```bash
jq -e '
  def budget_fraction:
    .value as $v | .unit as $u |
    if ($v | type) != "number" then null
    elif $u == "fraction_of_answers" then $v
    elif $u == "percent_of_answers" then $v / 100
    elif $u == "errors_per_1000_answers" then $v / 1000
    else null end;
  .error_budget.derived_from as $id |
  (.error_budget | budget_fraction) as $b |
  ($b != null) and
  (.measurements? | type == "array") and
  ([.measurements[] | select(.id == $id)] | length == 1) and
  ([.measurements[] | select(.id == $id)][0] as $m |
    ($m.sample_size | type == "number" and . > 0) and
    ($m.interval_bounds.lower | type == "number") and
    (($b < $m.interval_bounds.lower) as $breach |
      (.error_budget.baseline_status ==
        (if $breach then "already_in_breach" else "not_proven_in_breach" end)) and
      (if $breach then (.error_budget.breach_response | type == "string" and test("\\S")) else true end)))
' "$REPORT"
```

## Fast-burn and slow-burn alerts recompute and can be evaluated

At least one `fast_burn` and one `slow_burn` alert. Fast burns page and have the higher burn rate
and shorter window; slow burns open a ticket. Each alert has a shorter confirming window,
consumes no more than the whole budget, and carries enough graded answers to be evaluated.

```bash
jq -e '
  def budget_fraction:
    .value as $v | .unit as $u |
    if ($v | type) != "number" then null
    elif $u == "fraction_of_answers" then $v
    elif $u == "percent_of_answers" then $v / 100
    elif $u == "errors_per_1000_answers" then $v / 1000
    else null end;
  def hours:
    if type == "string" and test("^[1-9][0-9]*[hdw]$")
    then ((.[0:-1] | tonumber) * ({"h": 1, "d": 24, "w": 168}[.[-1:]]))
    else null end;
  def absv: if . < 0 then -. else . end;
  (.error_budget | budget_fraction) as $b |
  (.error_budget.window | hours) as $bw |
  ($b != null and $bw != null) and
  (.alerts? | type == "array" and length > 0) and
  ([.alerts[].kind] as $kinds |
    ($kinds | index("fast_burn")) != null and
    ($kinds | index("slow_burn")) != null and
    all($kinds[]; . == "fast_burn" or . == "slow_burn")) and
  all(.alerts[];
    (.window | hours) as $w | (.short_window | hours) as $s |
    ($w != null and $s != null and $s < $w and $w <= $bw) and
    (.burn_rate | type == "number" and . > 0) and
    (.budget_consumed | type == "number" and . > 0 and . <= 1) and
    ((.budget_consumed - (.burn_rate * $w / $bw)) | absv) <= 0.005 and
    (.graded_answers_in_window | type == "number" and . > 0 and floor == .) and
    (.graded_answers_in_window * .burn_rate * $b >= 5) and
    (.signal | type == "string" and test("\\S")) and
    (if .kind == "fast_burn" then .action == "page" else .action == "open_ticket" end)) and
  ([.alerts[] | select(.kind == "fast_burn") | .burn_rate] | min) >
    ([.alerts[] | select(.kind == "slow_burn") | .burn_rate] | max) and
  ([.alerts[] | select(.kind == "fast_burn") | .window | hours] | max) <
    ([.alerts[] | select(.kind == "slow_burn") | .window | hours] | min)
' "$REPORT"
```

## Every alert reaches a named person or on-call function

A team name, queue, channel or distribution list is a missing owner, not a nonblank one.

```bash
jq -e '
  def named:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(the )?(tbd|todo|pending|unknown|n/?a|none|owner|someone|somebody|person|named person|everyone|support|engineering|operations|product|oncall|on[ _-]?call( function)?)$|^#|\\b(team|teams|department|group|queue|distribution|dl|mailing list|inbox|alias|channel|everyone)\\b") | not);
  (.alerts? | type == "array" and length > 0) and
  all(.alerts[]; .pages | named)
' "$REPORT"
```

## The exhaustion policy is a recommendation with a named trigger and decider

`recommended_stop` is what the operator is advised to stop; `decided_by` is the person or
on-call function who decides. Nothing is applied, and no wording describes an automatic action.

```bash
jq -e '
  def substantive:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(tbd|todo|pending|unknown|n/?a|none|placeholder|later)$") | not);
  def named:
    substantive and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(the )?(owner|someone|somebody|person|named person|everyone|support|engineering|operations|product|oncall|on[ _-]?call( function)?)$|^#|\\b(team|teams|department|group|queue|distribution|dl|mailing list|inbox|alias|channel|everyone)\\b") | not);
  .exhaustion_policy as $p |
  ($p | type == "object") and
  ($p.trigger | substantive) and
  ($p.recommended_stop | substantive) and
  ($p.decided_by | named) and
  ($p.automation_level as $level | ["0-Observe", "1-Recommend", "2-HITL"] | index($level) != null) and
  ($p.execution_status == "not_applied") and
  ([$p.trigger, $p.recommended_stop] | all(ascii_downcase |
     test("automatic(ally)?|auto[- ]?(disable|stop|pause|shut|kill|revert|block)|without (human|operator|approval)|kill switch (is )?(pulled|triggered|flipped)") | not))
' "$REPORT"
```

## Guardrail status is preserved and changes remain non-autonomous

`status` is `BLOCK` when the guardrails block or when the budget is already in breach.

```bash
jq -e '
  (.guardrail_status as $value | ["BLOCK", "CLEAR"] | index($value) != null) and
  (.status as $value | ["BLOCK", "CLEAR"] | index($value) != null) and
  (if (.guardrail_status == "BLOCK" or .error_budget.baseline_status == "already_in_breach")
   then .status == "BLOCK" else .status == "CLEAR" end) and
  (.recommendations? | type == "array") and
  all(.recommendations[];
    (.recommended_action | type == "string" and test("\\S")) and
    (.automation_level as $level |
      ["0-Observe", "1-Recommend", "2-HITL"] | index($level) != null) and
    (.execution_status == "not_applied"))
' "$REPORT"
```

## No raw customer identifiers enter the plan

A clean result is necessary, not sufficient; a human still confirms sanitisation.

```bash
jq -r '[.. | strings] | .[]' "$REPORT" \
  | grep -nEi '[[:alnum:]._%+-]+@[[:alnum:].-]+\.[a-z]{2,}|\+?([0-9][ ()-]*){8,}[0-9]|\border[ -]?#?[0-9]{4,}' \
  && echo "FAIL: unsanitised identifiers in deliverable" && exit 1 || exit 0
```
