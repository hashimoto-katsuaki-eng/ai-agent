#!/usr/bin/env bash
# PreToolUse guard for the Bash tool. Deterministic, rule-based deny checks —
# does not rely on the model's own judgment. See AskUserQuestion decisions:
# scope=user-wide, supply-chain=hard block, rm -rf=dangerous paths only.
set -u

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"
[ -z "$cmd" ] && exit 0

deny() {
  local reason="$1"
  jq -n --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    },
    systemMessage: $reason
  }'
  exit 0
}

# ---------------------------------------------------------------------------
# 1. Secrets — check first, and never echo the matched value back out.
# ---------------------------------------------------------------------------
SECRET_RE='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|glpat-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk_live_[0-9a-zA-Z]{20,}|AIza[0-9A-Za-z_-]{35}|npm_[A-Za-z0-9]{30,}|-----BEGIN[[:space:]]?(RSA|EC|OPENSSH|DSA|PGP)?[[:space:]]?PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|(api[_-]?key|secret|token|password|passwd|pwd)[[:space:]]*[:=][[:space:]]*[\"\x27]?[A-Za-z0-9_/+=-]{16,})'
if printf '%s' "$cmd" | grep -Eiq "$SECRET_RE"; then
  deny "コマンドにシークレットらしき文字列(APIキー/トークン/秘密鍵パターン)が検出されたためブロックしました。"
fi

# ---------------------------------------------------------------------------
# 2. Irreversible git operations
# ---------------------------------------------------------------------------
if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+push' \
   && printf '%s' "$cmd" | grep -Eq '(--force\b|(^|[[:space:]])-f([[:space:]]|$))'; then
  deny "git push --force は不可逆操作のためブロックしました: $cmd"
fi

if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+reset[^|;&]*--hard\b'; then
  deny "git reset --hard は不可逆操作のためブロックしました: $cmd"
fi

if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+clean' \
   && printf '%s' "$cmd" | grep -Eq '(--force\b|[[:space:]]-[a-zA-Z]*f[a-zA-Z]*([[:space:]]|$))'; then
  deny "git clean -f は不可逆操作のためブロックしました: $cmd"
fi

if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+branch' \
   && printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])-D([[:space:]]|$)'; then
  deny "git branch -D は不可逆操作のためブロックしました: $cmd"
fi

# ---------------------------------------------------------------------------
# 3. rm -rf targeting a broad/dangerous path (root, system dirs, home,
#    cwd, parent traversal, or an unexpanded bare variable). Targeted
#    deletions like "rm -rf node_modules" are intentionally allowed.
# ---------------------------------------------------------------------------
DANGEROUS_EXACT=(
  "/" "/*"
  "/etc" "/etc/" "/etc/*"
  "/usr" "/usr/" "/usr/*"
  "/var" "/var/" "/var/*"
  "/home" "/home/" "/home/*"
  "/root" "/root/" "/root/*"
  "/bin" "/bin/" "/bin/*"
  "/sbin" "/sbin/" "/sbin/*"
  "/boot" "/boot/" "/boot/*"
  "/lib" "/lib/" "/lib/*"
  "/lib64" "/lib64/" "/lib64/*"
  "/opt" "/opt/" "/opt/*"
  "/sys" "/sys/" "/sys/*"
  "/proc" "/proc/" "/proc/*"
  "/dev" "/dev/" "/dev/*"
  "/workspaces" "/workspaces/" "/workspaces/*"
  "~" "~/" '$HOME' '${HOME}' "$HOME" "$HOME/"
  "." "./" ".."
)

is_dangerous_path() {
  local p="$1" d
  for d in "${DANGEROUS_EXACT[@]}"; do
    [[ "$p" == "$d" ]] && return 0
  done
  case "$p" in
    ../*|*/../*|*/..) return 0 ;;
  esac
  [[ "$p" =~ ^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/?$ ]] && return 0
  return 1
}

words=()
read -ra words <<< "$cmd"
n=${#words[@]}
for ((i = 0; i < n; i++)); do
  base="${words[$i]##*/}"
  [[ "$base" != "rm" ]] && continue
  seg=()
  j=$((i + 1))
  while ((j < n)); do
    tok="${words[$j]}"
    case "$tok" in
      ';' | '&&' | '||' | '|') break ;;
    esac
    seg+=("$tok")
    ((j++))
  done
  has_r=0
  has_f=0
  dangerous=""
  for tok in "${seg[@]}"; do
    case "$tok" in
      --recursive) has_r=1 ;;
      --force) has_f=1 ;;
      -*)
        [[ "$tok" == *[rR]* ]] && has_r=1
        [[ "$tok" == *f* ]] && has_f=1
        ;;
      *)
        is_dangerous_path "$tok" && dangerous="$tok"
        ;;
    esac
  done
  if ((has_r)) && ((has_f)) && [[ -n "$dangerous" ]]; then
    deny "rm -rf で広範囲/危険なパス『$dangerous』の削除を検知したためブロックしました: $cmd"
  fi
done

# ---------------------------------------------------------------------------
# 4. Supply chain — npm/pip installing directly from a URL or git ref
#    instead of the configured registry.
# ---------------------------------------------------------------------------
if printf '%s' "$cmd" | grep -Eq 'npm[[:space:]]+(install|i|add)\b' \
   && printf '%s' "$cmd" | grep -Eq '(https?://|git\+https?://|git\+ssh://|git://|github:)'; then
  deny "npm install が registry を介さずURL/gitから直接パッケージを取得しているためブロックしました: $cmd"
fi

if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])(pip3?|python[0-9.]*[[:space:]]+-m[[:space:]]+pip)[[:space:]]+install\b' \
   && printf '%s' "$cmd" | grep -Eq '(git\+|https?://)'; then
  deny "pip install が registry を介さずURL/gitから直接パッケージを取得しているためブロックしました: $cmd"
fi

exit 0
