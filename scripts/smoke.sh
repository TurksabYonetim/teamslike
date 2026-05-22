#!/usr/bin/env bash
# Post-deploy smoke test.
# Exits 0 if everything passes, non-zero otherwise.
#
# Usage:
#   scripts/smoke.sh https://api.teamslike.com
#   scripts/smoke.sh http://localhost:8800

set -euo pipefail

BASE_URL="${1:-${API_BASE_URL:-}}"
if [ -z "$BASE_URL" ]; then
  echo "usage: $0 <base-url>" >&2
  exit 2
fi
BASE_URL="${BASE_URL%/}"

TIMEOUT="${SMOKE_TIMEOUT:-10}"
FAILED=0

probe() {
  local name="$1" path="$2" expected_status="$3"
  local url="$BASE_URL$path"
  local response status
  response=$(curl -sS -o /tmp/smoke_body.$$ -w "%{http_code}" \
    --max-time "$TIMEOUT" "$url" 2>&1) || {
    echo "  [FAIL] $name  -> curl error: $response"
    FAILED=$((FAILED + 1))
    return
  }
  status="$response"
  if [ "$status" = "$expected_status" ]; then
    echo "  [PASS] $name  $url -> $status"
  else
    echo "  [FAIL] $name  $url -> got $status, expected $expected_status"
    echo "         body: $(head -c 200 /tmp/smoke_body.$$)"
    FAILED=$((FAILED + 1))
  fi
  rm -f /tmp/smoke_body.$$
}

echo "Smoke test against: $BASE_URL"
probe "liveness"  "/health" "200"
probe "readiness" "/ready"  "200"

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "Smoke test FAILED ($FAILED check(s) failed)"
  exit 1
fi
echo ""
echo "Smoke test PASSED"
