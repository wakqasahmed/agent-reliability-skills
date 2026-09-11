# Input exposure inventory checks

Run these against the **delivered inventory report**, not against a `SKILL.md`. Set `$REPORT` to
the JSON deliverable. Each command exits non-zero when the contract fails.

## Source registry uses the interoperable contract

Reject an absent or empty registry, extra or missing source fields, invalid semantic values,
duplicate IDs, and freshness mechanisms without substantive detail.

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

## Blocking sources and status are derived exactly

A spoken source blocks independently when owner exposure is not acknowledged or freshness is
`none` or `unknown`. A non-spoken source does not enter `blocking_sources` under this rule. The
overall status also preserves a prior global guardrail block.

```bash
jq -e '
  (.source_registry? | type == "array") and
  (.blocking_sources? | type == "array") and
  (.guardrail_status as $value | ["BLOCK", "CLEAR"] | index($value) != null) and
  ([.source_registry[] |
    select(
      .agent_speaks_from == true and
      (.owner_exposure != "acknowledged" or
       .freshness_basis == "none" or
       .freshness_basis == "unknown")
    ) |
    .source_id
  ] | unique | sort) as $expected_blocking_sources |
  ([.blocking_sources[] | select(type == "string")] | unique | sort) as $reported_blocking_sources |
  ((.blocking_sources | length) == ($reported_blocking_sources | length)) and
  ($reported_blocking_sources == $expected_blocking_sources) and
  if ($expected_blocking_sources | length) > 0 or .guardrail_status == "BLOCK" then .status == "BLOCK"
  else .status == "CLEAR"
  end
' "$REPORT"
```

## Reachable but unscoped sources are findings

Require exactly one scope classification per registry source and exactly one
`reachable_but_unscoped` finding per source carrying that semantic state.

```bash
jq -e '
  def nonempty: type == "string" and test("\\S");
  (.answer_surface? | nonempty) and
  (.declared_answer_scope? | nonempty) and
  (.source_registry? | type == "array") and
  (.source_access? | type == "array") and
  (.findings? | type == "array") and
  ([.source_registry[].source_id] | unique | sort) as $source_ids |
  (all(.source_access[];
    type == "object" and
    (.source_id as $id | $source_ids | index($id) != null) and
    (.scope_state as $state |
      ["in_scope", "reachable_but_unscoped", "unknown"] | index($state) != null))) and
  ([.source_access[].source_id] | length == (unique | length)) and
  ([.source_access[].source_id] | unique | sort) == $source_ids and
  (all(.findings[];
    type == "object" and
    (.source_id as $id | $source_ids | index($id) != null) and
    (.finding_type | nonempty) and
    (.recommended_action | nonempty) and
    (.automation_level as $level |
      ["0-Observe", "1-Recommend", "2-HITL"] | index($level) != null))) and
  ([.source_access[] | select(.scope_state == "reachable_but_unscoped") | .source_id] | unique | sort) as $expected_findings |
  ([.findings[] | select(.finding_type == "reachable_but_unscoped") |
    select(
      (.source_id as $id | $source_ids | index($id) != null) and
      (.recommended_action | nonempty) and
      (.automation_level as $level |
        ["0-Observe", "1-Recommend", "2-HITL"] | index($level) != null)
    ) |
    .source_id
  ] | unique | sort) as $reported_findings |
  ([.findings[] | select(.finding_type == "reachable_but_unscoped")] | length == ($reported_findings | length)) and
  ($reported_findings == $expected_findings)
' "$REPORT"
```

## Acknowledgements are evidenced and outstanding requests are routed

Every acknowledged source has one dated acknowledgement naming who accepted the obligation. Every
`not_notified` or `unknown` source has one owner request with an enforceable obligation enum.

```bash
jq -e '
  def nonempty: type == "string" and test("\\S");
  def named:
    nonempty and
    (ascii_downcase | test("^(tbd|todo|pending|unknown|n/a|na|none|team|the team)$") | not);
  (.source_registry? | type == "array") and
  (.owner_acknowledgements? | type == "array") and
  (.owner_requests? | type == "array") and
  (.source_registry | map({key: .source_id, value: .}) | from_entries) as $sources |
  ([.source_registry[] | select(.owner_exposure == "acknowledged") | .source_id] | unique | sort) as $expected_acknowledged |
  ([.owner_acknowledgements[] |
    select(
      (.source_id as $id | $sources | has($id)) and
      (.acknowledged_by | named) and
      (.acknowledged_at | type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$")) and
      .obligation == "acknowledge_customer_facing_maintenance"
    ) |
    .source_id
  ] | unique | sort) as $reported_acknowledged |
  ([.owner_acknowledgements[]] | length == ($reported_acknowledged | length)) and
  ($reported_acknowledged == $expected_acknowledged) and
  ([.source_registry[] | select(.owner_exposure != "acknowledged") | .source_id] | unique | sort) as $expected_requests |
  ([.owner_requests[] |
    select(
      (.source_id as $id | $sources | has($id)) and
      (.routed_to == $sources[.source_id].owning_team) and
      .requested_obligation == "acknowledge_customer_facing_maintenance" and
      (.recommended_action | nonempty) and
      (.automation_level as $level |
        ["0-Observe", "1-Recommend", "2-HITL"] | index($level) != null)
    ) |
    .source_id
  ] | unique | sort) as $reported_requests |
  ([.owner_requests[]] | length == ($reported_requests | length)) and
  ($reported_requests == $expected_requests)
' "$REPORT"
```
