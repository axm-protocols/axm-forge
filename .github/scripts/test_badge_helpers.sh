#!/usr/bin/env bash
# test_badge_helpers.sh — e2e shell test for badge-helpers.sh.
#
# Exercises the RESULT guard:
#   AC1 empty RESULT       -> error/red badge + non-zero exit
#   AC2 unparseable RESULT -> error badge, never a "%"/score badge, non-zero exit
#   AC3 valid numeric score -> normal score badge + zero exit
#
# Requires: bash, jq, python3 (all present in CI). Run: bash test_badge_helpers.sh
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=badge-helpers.sh
source "$HERE/badge-helpers.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail=0
check() { # $1 = 0 when the preceding test succeeded, $2 = description
  if [ "$1" -eq 0 ]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=1; fi
}

# ── AC1: empty RESULT -> error badge + non-zero exit ─────────────────────────
( require_valid_result "" "$TMP/a" "axm-audit" "axm-audit" ) 2>/dev/null
code=$?
[ "$code" -ne 0 ]; check $? "AC1: empty RESULT exits non-zero (got $code)"
[ "$(jq -r '.message' "$TMP/a/axm-audit.json" 2>/dev/null)" = "error" ]
check $? "AC1: empty RESULT writes an 'error' badge"
[ "$(jq -r '.color' "$TMP/a/axm-audit.json" 2>/dev/null)" = "red" ]
check $? "AC1: error badge colour is red"

# ── AC2: unparseable RESULT -> error badge, no % badge, non-zero exit ────────
( require_valid_result "not-json" "$TMP/b" "axm-audit" "axm-audit" ) 2>/dev/null
code=$?
[ "$code" -ne 0 ]; check $? "AC2: unparseable RESULT exits non-zero (got $code)"
msg_b="$(jq -r '.message' "$TMP/b/axm-audit.json" 2>/dev/null)"
[ "$msg_b" = "error" ]; check $? "AC2: unparseable RESULT writes an 'error' badge"
case "$msg_b" in *%*) false ;; *) true ;; esac
check $? "AC2: no '%'/score badge is written on failure"

# ── AC3: valid numeric score -> normal score badge + zero exit ──────────────
(
  require_valid_result '{"score": 87}' "$TMP/c" "axm-audit" "axm-audit"
  SCORE=$(printf '%s' '{"score": 87}' | jq '.score')
  write_badge "$TMP/c" "axm-audit" "axm-audit" "$SCORE"
)
code=$?
[ "$code" -eq 0 ]; check $? "AC3: valid RESULT exits zero (got $code)"
[ "$(jq -r '.message' "$TMP/c/axm-audit.json" 2>/dev/null)" = "87%" ]
check $? "AC3: valid RESULT writes the normal '87%' score badge"

if [ "$fail" -ne 0 ]; then echo "SOME TESTS FAILED"; exit 1; fi
echo "ALL TESTS PASSED"
