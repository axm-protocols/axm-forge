#!/usr/bin/env bash
# badge-helpers.sh — shieldsio badge writers for the axm-quality workflow.
#
# Sourced by the CI jobs (copied to /tmp/badge-helpers.sh) and by the
# sibling test_badge_helpers.sh. Pure function definitions only — no
# top-level side effects, so `source`-ing is safe.

# score_color SCORE_INT -> shields.io color for a 0-100 score.
score_color() {
  local SCORE=$1
  if [ "$SCORE" -ge 95 ]; then echo "brightgreen"
  elif [ "$SCORE" -ge 80 ]; then echo "green"
  elif [ "$SCORE" -ge 60 ]; then echo "yellow"
  else echo "red"; fi
}

# write_error_badge DIR NAME LABEL
# Emit an explicit red "error" badge (no percentage) signalling that the
# upstream payload was empty / malformed. Kept distinct from a real score
# badge so a broken audit run is never mistaken for a low-but-valid score.
write_error_badge() {
  local DIR=$1 NAME=$2 LABEL=$3
  mkdir -p "$DIR"
  jq -n --arg l "$LABEL" \
    '{schemaVersion:1, label:$l, message:"error", color:"red", style:"flat"}' \
    > "$DIR/$NAME.json"
}

# require_valid_result RESULT DIR NAME LABEL
# Guard invoked BEFORE extracting a score: RESULT must be non-empty, valid
# JSON, carrying a numeric `.score`. On any failure it writes an explicit
# error/red badge to DIR/NAME.json and `exit 1` (fails the CI job) — it must
# never fall through to a bogus "null%"/red score badge.
require_valid_result() {
  local RESULT=$1 DIR=$2 NAME=$3 LABEL=$4
  if [ -z "$RESULT" ] || ! printf '%s' "$RESULT" | jq -e . >/dev/null 2>&1; then
    echo "badge-helpers: RESULT is empty or not valid JSON — writing error badge" >&2
    write_error_badge "$DIR" "$NAME" "$LABEL"
    exit 1
  fi
  local SCORE
  SCORE=$(printf '%s' "$RESULT" | jq -r '.score')
  if ! printf '%s' "$SCORE" | grep -Eq '^-?[0-9]+(\.[0-9]+)?$'; then
    echo "badge-helpers: .score is not numeric ('$SCORE') — writing error badge" >&2
    write_error_badge "$DIR" "$NAME" "$LABEL"
    exit 1
  fi
}

# write_badge DIR NAME LABEL VALUE [LOGO_FILE]
# Nominal path: write a "<VALUE>%" score badge coloured by score_color.
write_badge() {
  local DIR=$1 NAME=$2 LABEL=$3 VALUE=$4 LOGO_FILE=${5:-}
  mkdir -p "$DIR"
  local SCORE_INT=$(python3 -c "print(int(float('${VALUE}')))")
  local COLOR=$(score_color "$SCORE_INT")
  if [ -n "$LOGO_FILE" ] && [ -f "$LOGO_FILE" ]; then
    local LOGO=$(cat "$LOGO_FILE")
    jq -n --arg l "$LABEL" --arg v "$VALUE" --arg c "$COLOR" --arg logo "$LOGO" \
      '{schemaVersion:1, label:$l, message:"\($v)%", color:$c, logoSvg:$logo, style:"flat"}' \
      > "$DIR/$NAME.json"
  else
    jq -n --arg l "$LABEL" --arg v "$VALUE" --arg c "$COLOR" \
      '{schemaVersion:1, label:$l, message:"\($v)%", color:$c, style:"flat"}' \
      > "$DIR/$NAME.json"
  fi
}
