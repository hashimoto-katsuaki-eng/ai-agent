#!/usr/bin/env bash
# PostToolUse marker for mcp__linear__save_issue, user-wide. Touches a
# per-session gate file that linear-gate-check.sh consults.
set -u

sid=$(jq -r '.session_id // ""' | tr -cd 'a-zA-Z0-9_-')
mkdir -p /tmp/claude-linear-gate
[ -n "$sid" ] && touch "/tmp/claude-linear-gate/$sid"
