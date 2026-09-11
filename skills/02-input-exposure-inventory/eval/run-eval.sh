#!/usr/bin/env bash
set -euo pipefail

eval_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$eval_dir/../../.." && pwd)"

python3 "$eval_dir/contract_check.py"
python3 "$repo_root/scripts/validate-eval-fixtures.py" "$eval_dir/fixtures/held-out-scenarios.json"

echo "02-input-exposure-inventory eval: ALL CHECKS PASSED"
