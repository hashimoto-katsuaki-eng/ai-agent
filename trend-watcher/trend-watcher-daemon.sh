#!/usr/bin/env bash
# Polls public, unauthenticated/cheap APIs (GitHub Search, Hacker News Algolia
# search) for notable AI/LLM-agent-tooling activity and rule-base filters them
# (star/points thresholds + recency), then files a Linear issue for anything
# new. No LLM/Claude tokens are used anywhere in this script — filtering is
# pure threshold logic, not model judgment.
#
# Required env vars:
#   LINEAR_API_KEY   - Linear Personal API key (Settings > API > Personal API keys)
#
# Optional env vars:
#   GITHUB_TOKEN              - raises GitHub Search API rate limit (not required)
#   POLL_INTERVAL_SECONDS     - defaults to 18000 (5h, matches AI-14 cadence)
#   GITHUB_LOOKBACK_DAYS      - defaults to 14
#   GITHUB_MIN_STARS          - defaults to 150
#   NEWS_LOOKBACK_HOURS       - defaults to 24
#   NEWS_MIN_POINTS           - defaults to 30
#   LINEAR_DEDUP_LOOKBACK_DAYS - defaults to 30 (must be >= GITHUB_LOOKBACK_DAYS
#                                 so a repo never gets re-filed while it's still
#                                 inside its own discovery window)

set -u

LINEAR_TEAM_ID="0c81db18-a9dd-41bb-ab79-9d0819136cfe"
LINEAR_AUTO_FILED_LABEL_ID="80cc1631-1683-45d8-85bb-d458672ee673"
LINEAR_API_URL="https://api.linear.app/graphql"

POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-18000}"
GITHUB_LOOKBACK_DAYS="${GITHUB_LOOKBACK_DAYS:-14}"
GITHUB_MIN_STARS="${GITHUB_MIN_STARS:-150}"
NEWS_LOOKBACK_HOURS="${NEWS_LOOKBACK_HOURS:-24}"
NEWS_MIN_POINTS="${NEWS_MIN_POINTS:-30}"
LINEAR_DEDUP_LOOKBACK_DAYS="${LINEAR_DEDUP_LOOKBACK_DAYS:-30}"
MAX_ISSUES_PER_RUN="${MAX_ISSUES_PER_RUN:-3}"

GITHUB_TOPICS=(ai-agent llm-agent agent-framework coding-agent agentic-ai)
NEWS_KEYWORDS=("AI agent" "LLM agent" "Claude Code" "Devin AI" "coding agent")

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

require_env() {
  if [ -z "${LINEAR_API_KEY:-}" ]; then
    log "ERROR: LINEAR_API_KEY must be set"
    exit 1
  fi
}

linear_api() {
  # $1 = JSON payload (already serialized via jq -n)
  curl -s "$LINEAR_API_URL" \
    -H "Authorization: $LINEAR_API_KEY" \
    -H "Content-Type: application/json" \
    --data-binary "$1"
}

fetch_recent_linear_titles() {
  # Populates RECENT_TITLES_FILE with one lowercased issue title per line,
  # for issues created within LINEAR_DEDUP_LOOKBACK_DAYS. Returns non-zero on failure.
  local since payload response
  since=$(date -u -d "-${LINEAR_DEDUP_LOOKBACK_DAYS} days" +%Y-%m-%dT%H:%M:%SZ)
  payload=$(jq -n --arg teamId "$LINEAR_TEAM_ID" --arg since "$since" '{
    query: "query RecentIssues($teamId: ID!, $since: DateTimeOrDuration!) { issues(filter: { team: { id: { eq: $teamId } }, createdAt: { gte: $since } }, first: 250) { nodes { title } } }",
    variables: { teamId: $teamId, since: $since }
  }')
  response=$(linear_api "$payload")
  if [ "$(echo "$response" | jq -r '.errors // empty')" != "" ]; then
    log "ERROR: Linear recent-issues query failed: $(echo "$response" | jq -c '.errors')"
    return 1
  fi
  echo "$response" | jq -r '.data.issues.nodes[]?.title // empty' | tr '[:upper:]' '[:lower:]' > "$RECENT_TITLES_FILE"
  return 0
}

is_duplicate() {
  # $1 = match key (case-insensitive fixed-string search against recent Linear titles)
  local key_lower
  key_lower=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  grep -qF -- "$key_lower" "$RECENT_TITLES_FILE"
}

create_linear_issue() {
  # $1 = title, $2 = description
  local payload response success identifier url
  payload=$(jq -n \
    --arg teamId "$LINEAR_TEAM_ID" \
    --arg labelId "$LINEAR_AUTO_FILED_LABEL_ID" \
    --arg title "$1" \
    --arg description "$2" \
    '{
      query: "mutation IssueCreate($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { identifier url } } }",
      variables: { input: { teamId: $teamId, title: $title, description: $description, labelIds: [$labelId] } }
    }')
  response=$(linear_api "$payload")
  success=$(echo "$response" | jq -r '.data.issueCreate.success // false')
  if [ "$success" != "true" ]; then
    log "ERROR: issueCreate failed: $(echo "$response" | jq -c '.errors // .data')"
    return 1
  fi
  identifier=$(echo "$response" | jq -r '.data.issueCreate.issue.identifier')
  url=$(echo "$response" | jq -r '.data.issueCreate.issue.url')
  log "filed ${identifier}: ${1} (${url})"
  return 0
}

fetch_github_candidates() {
  # Appends score<TAB>source<TAB>match_key<TAB>display<TAB>url lines to CANDIDATES_FILE
  local since topic response auth_args=()
  since=$(date -u -d "-${GITHUB_LOOKBACK_DAYS} days" +%Y-%m-%d)
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    auth_args=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
  fi
  for topic in "${GITHUB_TOPICS[@]}"; do
    response=$(curl -s --get "${auth_args[@]}" \
      --data-urlencode "q=topic:${topic} created:>=${since}" \
      --data-urlencode "sort=stars" \
      --data-urlencode "order=desc" \
      --data-urlencode "per_page=5" \
      "https://api.github.com/search/repositories")
    echo "$response" | jq -r --arg minstars "$GITHUB_MIN_STARS" '
      .items[]? | select(.stargazers_count >= ($minstars | tonumber)) |
      [ .stargazers_count, "github", .full_name, ("GitHub: " + .full_name + " (★" + (.stargazers_count|tostring) + ")"), .html_url ] | @tsv
    ' >> "$CANDIDATES_FILE" 2>/dev/null
  done
}

fetch_news_candidates() {
  # Appends score<TAB>source<TAB>match_key<TAB>display<TAB>url lines to CANDIDATES_FILE
  local since_epoch keyword response
  since_epoch=$(date -u -d "-${NEWS_LOOKBACK_HOURS} hours" +%s)
  for keyword in "${NEWS_KEYWORDS[@]}"; do
    response=$(curl -s --get \
      --data-urlencode "query=${keyword}" \
      --data-urlencode "tags=story" \
      --data-urlencode "numericFilters=created_at_i>${since_epoch},points>=${NEWS_MIN_POINTS}" \
      "https://hn.algolia.com/api/v1/search_by_date")
    echo "$response" | jq -r --arg fallback_prefix "https://news.ycombinator.com/item?id=" '
      .hits[]? |
      [ .points, "hn", .title, ("News: " + .title), ((.url // ($fallback_prefix + .objectID))) ] | @tsv
    ' >> "$CANDIDATES_FILE" 2>/dev/null
  done
}

build_description() {
  # $1 = source (github|hn), $2 = url
  local source="$1" url="$2"
  case "$source" in
    github)
      printf 'GitHub上で、AI/LLMエージェント開発ツール関連で注目度の高いリポジトリを検知しました。\n\n- URL: %s\n\nこのissueはルールベースの非LLMスクリプト(trend-watcher/trend-watcher-daemon.sh)が、star数としきい値だけで自動起票したものです。要約や注目理由の評価は行っていません。\n\n次のアクション(読む・着手する・Devinに委任する)は人間が判断してください。' "$url"
      ;;
    hn)
      printf 'Hacker Newsで、AI/LLMエージェント開発ツール関連で注目度の高い記事を検知しました。\n\n- URL: %s\n\nこのissueはルールベースの非LLMスクリプト(trend-watcher/trend-watcher-daemon.sh)が、ポイント数としきい値だけで自動起票したものです。要約や注目理由の評価は行っていません。\n\n次のアクション(読む・着手する・Devinに委任する)は人間が判断してください。' "$url"
      ;;
  esac
}

run_once() {
  CANDIDATES_FILE=$(mktemp)
  RECENT_TITLES_FILE=$(mktemp)
  trap 'rm -f "$CANDIDATES_FILE" "$RECENT_TITLES_FILE"' RETURN

  if ! fetch_recent_linear_titles; then
    log "skipping this cycle: could not verify existing issues (avoiding duplicate risk)"
    return 1
  fi

  fetch_github_candidates
  fetch_news_candidates

  local total filed=0
  total=$(wc -l < "$CANDIDATES_FILE" | tr -d ' ')
  log "collected ${total} raw candidate(s)"

  while IFS=$'\t' read -r score source match_key display url; do
    [ "$filed" -ge "$MAX_ISSUES_PER_RUN" ] && break
    [ -z "${match_key:-}" ] && continue
    if is_duplicate "$match_key"; then
      log "skip (duplicate): ${display}"
      continue
    fi
    if create_linear_issue "[自動調査] ${display}" "$(build_description "$source" "$url")"; then
      filed=$((filed + 1))
      printf '%s\n' "$(printf '%s' "$match_key" | tr '[:upper:]' '[:lower:]')" >> "$RECENT_TITLES_FILE"
    fi
  done < <(awk -F'\t' '!seen[$3]++' "$CANDIDATES_FILE" | sort -t$'\t' -k1,1 -rn)

  if [ "$filed" -eq 0 ]; then
    log "no new issues filed this cycle"
  else
    log "filed ${filed} new issue(s) this cycle"
  fi
}

main() {
  require_env
  trap 'log "stopping"; exit 0' INT TERM
  log "starting trend-watcher-daemon (poll interval: ${POLL_INTERVAL_SECONDS}s)"
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
