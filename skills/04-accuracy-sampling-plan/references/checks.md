# Accuracy-sampling-plan checks

Run these against a **delivered sampling plan**, not against a `SKILL.md`. Set `$REPORT` to the
JSON deliverable produced by this skill. Each command exits non-zero when the contract fails. A
failing check makes the deliverable `BLOCK`.

### Formulas used below

Let `p` be `error_rate`, `n` be `sample_size`, and `z` the two-sided normal quantile for the
confidence level (1.644854 at 0.90, 1.959964 at 0.95, 2.575829 at 0.99).

- Wilson interval: `(p + z^2/2n) / (1 + z^2/n)` plus or minus
  `z * sqrt(p(1-p)/n + z^2/4n^2) / (1 + z^2/n)`. Preferred over the Wald interval `p +/- z *
  sqrt(p(1-p)/n)`, whose coverage is erratic [SRC-BROWN-CAI-DASGUPTA-BINOMIAL]. At `p` = 0 the
  Wald interval collapses to a single point; the Wilson interval does not.
- Minimum detectable difference between two independent samples of size `n`, with baseline
  `p0`, confidence `1 - alpha` and power `1 - beta`: the `d` that solves
  `d = (z_{1-alpha/2} + z_{1-beta}) * sqrt((p0(1-p0) + p1(1-p1)) / n)` with `p1 = p0 + d`
  (power quantile 0.841621 at 0.80, 1.281552 at 0.90, 1.644854 at 0.95). The checks solve it by
  fixed-point iteration.
- Required sample size per sample to separate `p0` from `p1`:
  `ceil((z_{1-alpha/2} + z_{1-beta})^2 * (p0(1-p0) + p1(1-p1)) / (p1 - p0)^2)`.

These are normal approximations. They are least reliable when the expected error count in a
sample is small, so `approximation_valid` is `true` only when both `n * p0 >= 5` and
`n * (1 - p0) >= 5`. Below that, the z-test the formula assumes is unreliable, a sample can contain
zero errors, and the stated difference is indicative only; the plan must say so in `caveat` and
fund more samples or an exact test. The eval checks the formula against exact binomial power for a
grid of rates and sample sizes, including the 3%, n = 200 case.

## Every reported rate carries a sample and a Wilson interval that recomputes

An empty `measurements` array fails: this skill exists to produce a measurement. `interval` is the
human-readable string, and `interval_bounds` is its numeric form; both must be present and agree
(the string states the level and bounds within half a point of the numeric ones).

```bash
jq -e '
  def zfor($level): ({"0.9": 1.644854, "0.95": 1.959964, "0.99": 2.575829})[($level | tostring)];
  def absv: if . < 0 then -. else . end;
  def wilson($p; $n; $z):
    (1 + $z * $z / $n) as $d
    | (($p + $z * $z / (2 * $n)) / $d) as $c
    | ($z * (($p * (1 - $p) / $n) + ($z * $z / (4 * $n * $n)) | sqrt) / $d) as $h
    | {lower: ($c - $h), upper: ($c + $h)};
  def valid_measurement:
    (.id | type == "string" and test("\\S")) and
    (.error_rate | type == "number" and . >= 0 and . <= 1) and
    (.sample_size | type == "number" and . > 0 and floor == .) and
    (.interval | type == "string" and test("\\S") and test("wilson"; "i")) and
    (.interval_bounds as $b |
      ($b | type == "object") and
      ($b.method == "wilson") and
      (zfor($b.level) != null) and
      (.interval | contains(($b.level * 100 | round | tostring) + "%")) and
      ($b.lower | type == "number") and ($b.upper | type == "number") and
      ([.interval | scan("[0-9]+(?:\\.[0-9]+)?") | tonumber] as $nums |
        any($nums[]; (. - ($b.level * 100) | absv) < 0.01) and
        any($nums[]; (. - ($b.lower * 100) | absv) <= 0.5) and
        any($nums[]; (. - ($b.upper * 100) | absv) <= 0.5)) and
      (wilson(.error_rate; .sample_size; zfor($b.level)) as $w |
        (($b.lower - $w.lower) | absv) <= 0.001 and (($b.upper - $w.upper) | absv) <= 0.001));
  (.measurements? | type == "array" and length > 0) and
  all(.measurements[]; valid_measurement) and
  ([.measurements[].id] | length == (unique | length))
' "$REPORT"
```

## Graded against the system of record

`graded_against` must name the order, catalogue, policy or account data the answer describes.
Reject a transcript, a conversation or chat log, the agent's own output, the same model, ticket or
complaint counts, a survey or satisfaction score, or a placeholder.

```bash
jq -e '
  all(.measurements[]?;
    (.graded_against | type == "string" and test("\\S")) and
    (.graded_against | ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      (test("transcript|conversation|chat (log|history)|session log|the agent|agent.s (own )?(output|answer|response)|its own|own output|self[- ]?grad|same model|the model|model output|llm[- ]?(judge|grader)|(ticket|complaint|contact)s? (count|volume|total|rate)|complaints?|csat|\\bnps\\b|survey|customer feedback") or
       test("^(tbd|todo|pending|unknown|n/?a|none|placeholder|later)$")) | not))
' "$REPORT"
```

## Ticket counts are never an error rate

A rate must come from a graded sample. Support tickets, complaint counts and contact volume are a
lower bound on the error rate, not the rate.

```bash
jq -e '
  all(.measurements[]?;
    (.source == "graded_sample") and
    ((.source // "") | ascii_downcase | test("ticket|complaint|support volume|contact volume|escalation count") | not))
' "$REPORT"
```

## Selection, cadence and grading are recorded

`selection_method` is a fixed enum. The grader is a named person or specific on-call function and
did not build the answer surface (gate 3).

```bash
jq -e '
  def substantive:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(tbd|todo|pending|unknown|n/?a|none|placeholder|later)$") | not);
  def named:
    substantive and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(the )?(owner|someone|somebody|person|named person|grader|reviewer|support|engineering|operations|product|on[ _-]?call( function)?)$|\\b(team|department|group|queue|model|llm|bot)\\b") | not);
  (.sampling_plan.frame | substantive) and
  (.sampling_plan.grading.rubric | substantive) and
  (.sampling_plan.grading.grader | named) and
  (.sampling_plan.grading.grader_built_surface == false) and
  (.measurements | length > 0) and
  all(.measurements[];
    (.cadence | substantive) and
    (.selection_method as $m |
      ["uniform", "stratified_by_question_class", "oversampled_new_classes"] | index($m) != null))
' "$REPORT"
```

## The detectable difference is stated and recomputes

The difference the sample can detect, the question the plan funds, and one comparison the sample
cannot support, whose required sample size must genuinely exceed the sample taken. A plan with no
`detectable_difference` fails.

```bash
jq -e '
  def zconf: ({"0.9": 1.644854, "0.95": 1.959964, "0.99": 2.575829})[(. | tostring)];
  def zpow: ({"0.8": 0.841621, "0.9": 1.281552, "0.95": 1.644854})[(. | tostring)];
  def absv: if . < 0 then -. else . end;
  def mde($p0; $n; $za; $zb):
    reduce range(0; 200) as $i (0.05;
      (([$p0 + ., 0.9999] | min)) as $p1
      | ($za + $zb) * ((($p0 * (1 - $p0)) + ($p1 * (1 - $p1))) / $n | sqrt));
  def nreq($p0; $p1; $za; $zb):
    ((($za + $zb) * ($za + $zb) * (($p0 * (1 - $p0)) + ($p1 * (1 - $p1))) / (($p1 - $p0) * ($p1 - $p0))) | ceil);
  all(.measurements[]?;
    .sample_size as $n
    | .detectable_difference as $d
    | ($d | type == "object") and
      ($d.design == "two_independent_samples_equal_size") and
      ($d.approximation == "normal") and
      ($d.baseline_rate | type == "number" and . > 0 and . < 1) and
      (($d.confidence_level | zconf) != null) and
      (($d.power | zpow) != null) and
      (($d.confidence_level | zconf) as $za | ($d.power | zpow) as $zb |
        ($d.minimum_difference | type == "number" and . > 0) and
        ((($d.minimum_difference) - mde($d.baseline_rate; $n; $za; $zb)) | absv) <= 0.001 and
        ($d.cannot_support.comparison_rate | type == "number" and . > 0 and . < 1 and . != $d.baseline_rate) and
        (nreq($d.baseline_rate; $d.cannot_support.comparison_rate; $za; $zb) as $need |
          (($d.cannot_support.required_sample_size - $need) | absv) <= 1 and
          $need > $n)) and
      ($d.approximation_valid == (($n * $d.baseline_rate >= 5) and ($n * (1 - $d.baseline_rate) >= 5))) and
      (if $d.approximation_valid then true else ($d.caveat | type == "string" and test("\\S")) end) and
      ($d.funded_question as $q |
        (["large_regression", "small_difference"] | index($q) != null) and
        (if $q == "small_difference" then $d.minimum_difference <= 0.01 else $d.minimum_difference > 0.01 end)))
  and ((.measurements | length) > 0)
' "$REPORT"
```

## Confirmed failures have a route into regression cases

```bash
jq -e '
  def named:
    type == "string" and test("\\S") and
    (ascii_downcase | gsub("^\\s+|\\s+$"; "") |
      test("^(the )?(tbd|todo|pending|unknown|n/?a|none|owner|someone|somebody|person|named person|support|engineering|operations|product|on[ _-]?call( function)?)$|\\b(team|department|group|queue)\\b") | not);
  (.sampling_plan.regression_intake.destination | type == "string" and test("\\S")) and
  (.sampling_plan.regression_intake.owner | named)
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

## No raw customer identifiers enter the plan

A clean result is necessary, not sufficient; a human still confirms sanitisation.

```bash
jq -r '[.. | strings] | .[]' "$REPORT" \
  | grep -nEi '[[:alnum:]._%+-]+@[[:alnum:].-]+\.[a-z]{2,}|\+?([0-9][ ()-]*){8,}[0-9]|\border[ -]?#?[0-9]{4,}' \
  && echo "FAIL: unsanitised identifiers in deliverable" && exit 1 || exit 0
```
