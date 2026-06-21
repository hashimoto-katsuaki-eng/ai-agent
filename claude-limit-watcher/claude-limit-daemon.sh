#!/usr/bin/env bash
# Polls Claude's undocumented "unified" rate-limit headers using the local
# Claude Code OAuth token, and pushes only the derived percentages to a
# Slack App Home tab. The raw OAuth token never leaves this process.
#
# Required env vars:
#   SLACK_BOT_TOKEN   - xoxb-... bot token with the views:write scope
#   SLACK_USER_ID      - target Slack user ID (e.g. U0123456789)
#
# Optional env vars:
#   CLAUDE_CREDENTIALS_PATH - defaults to ~/.claude/.credentials.json
#   POLL_INTERVAL_SECONDS   - defaults to 60

set -u

CREDENTIALS_PATH="${CLAUDE_CREDENTIALS_PATH:-$HOME/.claude/.credentials.json}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-60}"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

require_env() {
  if [ -z "${SLACK_BOT_TOKEN:-}" ] || [ -z "${SLACK_USER_ID:-}" ]; then
    log "ERROR: SLACK_BOT_TOKEN and SLACK_USER_ID must be set"
    exit 1
  fi
}

header_value() {
  # $1 = header name, $2 = headers file
  awk -F': ' -v k="$1" 'tolower($1)==tolower(k){print $2}' "$2" | tr -d '\r' | head -n1
}

fmt_relative() {
  # $1 = unix epoch seconds in the future
  local target now diff h m d
  target="$1"
  now=$(date +%s)
  diff=$((target - now))
  if [ "$diff" -le 0 ]; then
    echo "now"
    return
  fi
  d=$((diff / 86400))
  h=$(((diff % 86400) / 3600))
  m=$(((diff % 3600) / 60))
  if [ "$d" -gt 0 ]; then
    echo "${d}d ${h}h"
  elif [ "$h" -gt 0 ]; then
    echo "${h}h ${m}m"
  else
    echo "${m}m"
  fi
}

pct() {
  # $1 = utilization fraction (0.0-1.0) -> integer percent
  awk -v u="$1" 'BEGIN { printf "%d", (u == "" ? 0 : u * 100) }'
}

fetch_usage() {
  # Populates the SESSION_PCT, SESSION_RESET, WEEKLY_PCT, WEEKLY_RESET, STATUS globals.
  # Returns non-zero if usage could not be determined.
  local token hdrfile http_status
  token=$(jq -r '.accessToken // .claudeAiOauth.accessToken // empty' "$CREDENTIALS_PATH" 2>/dev/null)
  if [ -z "$token" ]; then
    log "ERROR: could not read accessToken from $CREDENTIALS_PATH"
    return 1
  fi

  hdrfile=$(mktemp)
  http_status=$(curl -s -o /dev/null -w '%{http_code}' -D "$hdrfile" \
    https://api.anthropic.com/v1/messages \
    -H "Authorization: Bearer $token" \
    -H "anthropic-version: 2023-06-01" \
    -H "anthropic-beta: oauth-2025-04-20" \
    -H "Content-Type: application/json" \
    -d '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}')
  token="" # drop the token from this shell's memory as soon as we're done with it

  if [ "$http_status" != "200" ]; then
    log "ERROR: unexpected HTTP status $http_status from Anthropic API"
    rm -f "$hdrfile"
    return 1
  fi

  local s5h_util s5h_reset s7d_util s7d_reset status
  s5h_util=$(header_value "anthropic-ratelimit-unified-5h-utilization" "$hdrfile")
  s5h_reset=$(header_value "anthropic-ratelimit-unified-5h-reset" "$hdrfile")
  s7d_util=$(header_value "anthropic-ratelimit-unified-7d-utilization" "$hdrfile")
  s7d_reset=$(header_value "anthropic-ratelimit-unified-7d-reset" "$hdrfile")
  status=$(header_value "anthropic-ratelimit-unified-5h-status" "$hdrfile")
  rm -f "$hdrfile"

  if [ -z "$s5h_util" ] || [ -z "$s7d_util" ]; then
    log "ERROR: unified rate-limit headers missing from response (Anthropic may have changed this undocumented behavior)"
    return 1
  fi

  SESSION_PCT=$(pct "$s5h_util")
  SESSION_RESET=$(fmt_relative "$s5h_reset")
  WEEKLY_PCT=$(pct "$s7d_util")
  WEEKLY_RESET=$(fmt_relative "$s7d_reset")
  STATUS="${status:-unknown}"
  return 0
}

publish_home() {
  local payload response ok
  payload=$(jq -n \
    --arg user_id "$SLACK_USER_ID" \
    --arg session "Session (5h): ${SESSION_PCT}% used, resets in ${SESSION_RESET}" \
    --arg weekly "Weekly (7d): ${WEEKLY_PCT}% used, resets in ${WEEKLY_RESET}" \
    --arg status "Status: ${STATUS}" \
    --arg updated "Last updated: $(date '+%Y-%m-%d %H:%M:%S %Z')" \
    '{
      user_id: $user_id,
      view: {
        type: "home",
        blocks: [
          { type: "header", text: { type: "plain_text", text: "Claude usage" } },
          { type: "section", text: { type: "mrkdwn", text: ("*" + $session + "*\n*" + $weekly + "*\n" + $status) } },
          { type: "context", elements: [ { type: "mrkdwn", text: $updated } ] }
        ]
      }
    }')

  response=$(curl -s -X POST https://slack.com/api/views.publish \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "$payload")
  ok=$(echo "$response" | jq -r '.ok')
  if [ "$ok" != "true" ]; then
    log "ERROR: Slack views.publish failed: $(echo "$response" | jq -r '.error // "unknown"')"
    return 1
  fi
  return 0
}

publish_unavailable() {
  curl -s -X POST https://slack.com/api/views.publish \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "$(jq -n --arg user_id "$SLACK_USER_ID" '{
      user_id: $user_id,
      view: { type: "home", blocks: [
        { type: "section", text: { type: "mrkdwn", text: "Claude usage is temporarily unavailable." } }
      ] }
    }')" >/dev/null
}

run_once() {
  if fetch_usage; then
    log "session=${SESSION_PCT}% weekly=${WEEKLY_PCT}% status=${STATUS}"
    publish_home
  else
    log "skipping Slack update this cycle (see error above)"
  fi
}

main() {
  require_env
  trap 'log "stopping"; exit 0' INT TERM
  log "starting claude-limit-daemon (poll interval: ${POLL_INTERVAL_SECONDS}s)"
  while true; do
    run_once
    sleep "$POLL_INTERVAL_SECONDS"
  done
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--once" ]; then
    require_env
    run_once
  else
    main
  fi
fi
