#!/usr/bin/env bash
# PreToolUse guard for Write/Edit/NotebookEdit, user-wide (any directory under
# /workspaces). Denies until a Linear issue has been filed this session via
# linear-gate-mark.sh. See AI-7 / devcon CLAUDE.md for the pipeline this gates.
set -u

sid=$(jq -r '.session_id // ""' | tr -cd 'a-zA-Z0-9_-')
[ -n "$sid" ] && [ -f "/tmp/claude-linear-gate/$sid" ] && exit 0

jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"先にLinearにissueを起票してください(title=タスク名、description=完了条件/Definition of Doneのみで可)。mcp__linear__save_issue (team=\"Ai-agents-Teams\") で作成後に再実行してください。"}}'
