#!/usr/bin/env bash
# Provisions the user-wide Linear-gate hook into ~/.claude on container
# create. Run from devcontainer.json's postCreateCommand so any device that
# opens this devcontainer reproduces the hook — the ~/.claude volume itself
# is host-local and does not travel with the repo. Safe to re-run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS="$CLAUDE_DIR/settings.json"

mkdir -p "$HOOKS_DIR"
cp "$SCRIPT_DIR/hooks/linear-gate-check.sh" "$HOOKS_DIR/linear-gate-check.sh"
cp "$SCRIPT_DIR/hooks/linear-gate-mark.sh" "$HOOKS_DIR/linear-gate-mark.sh"
chmod +x "$HOOKS_DIR/linear-gate-check.sh" "$HOOKS_DIR/linear-gate-mark.sh"

[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

tmp="$(mktemp)"
jq \
  --arg check "$HOOKS_DIR/linear-gate-check.sh" \
  --arg mark "$HOOKS_DIR/linear-gate-mark.sh" \
  '
  .hooks //= {} |
  .hooks.PreToolUse //= [] |
  .hooks.PostToolUse //= [] |
  (if any(.hooks.PreToolUse[]?; .hooks[]?.command == $check) then .
   else .hooks.PreToolUse += [{"matcher":"Write|Edit|NotebookEdit","hooks":[{"type":"command","command":$check}]}]
   end) |
  (if any(.hooks.PostToolUse[]?; .hooks[]?.command == $mark) then .
   else .hooks.PostToolUse += [{"matcher":"mcp__linear__save_issue|mcp__claude_ai_Linear__save_issue","hooks":[{"type":"command","command":$mark}]}]
   end) |
  .skipDangerousModePermissionPrompt = true
  ' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"

echo "Linear-gate hooks + auto-approval provisioned into $SETTINGS"
