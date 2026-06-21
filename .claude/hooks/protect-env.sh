#!/usr/bin/env bash
# Mode-independent guard for claude-limit-watcher/.env.local. Replaces the
# permissions.deny entries for this file, which bypassPermissions mode does
# not consult — hooks fire regardless of permission mode.
set -u

input="$(cat)"
tool="$(printf '%s' "$input" | jq -r '.tool_name // ""')"

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    },
    systemMessage: $reason
  }'
  exit 0
}

case "$tool" in
  Read)
    path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // ""')"
    [[ "$path" == *.env.local ]] && deny "claude-limit-watcher/.env.local の読み取りは禁止されています(秘密情報保護)。"
    ;;
  Grep)
    path="$(printf '%s' "$input" | jq -r '.tool_input.path // ""')"
    [[ "$path" == *.env.local ]] && deny "claude-limit-watcher/.env.local への grep は禁止されています(秘密情報保護)。"
    ;;
  Bash)
    cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"
    printf '%s' "$cmd" | grep -Fq ".env.local" && deny "claude-limit-watcher/.env.local を参照するコマンドは禁止されています(秘密情報保護): $cmd"
    ;;
esac
exit 0
