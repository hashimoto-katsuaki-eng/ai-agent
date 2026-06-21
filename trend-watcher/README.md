# trend-watcher

GitHub Search APIとHacker News(Algolia)Search APIをポーリングし、AI/LLMエージェント開発ツール関連で注目度の高い項目(star数/ポイント数のしきい値+新しさ)を見つけたら、Linearチーム `Ai-agents-Teams` に自動でissueを起票するツール。LLM/Claudeトークンは一切使わない(bash+curl+jqのルールベース処理のみ)。詳細は `CLAUDE.md` の「自動issue起票ツール: trend-watcher」を参照(AI-15)。

## セットアップ

1. Linearで Personal API Key を発行する(Settings > API > Personal API keys)。**Read** と **Write** の両スコープが必要(Readはissueの重複チェック、Writeはissue作成用)。

## 本番運用: GitHub Actions(推奨)

`.github/workflows/trend-watcher.yml` が5時間おき(`cron: "23 */5 * * *"`)に `./trend-watcher-daemon.sh --once` を実行する。PC本体やdevcontainerの起動状態に依存せず、LLM/Claudeトークンも使わない。

セットアップはGitHubのリポジトリ設定でのみ行う(Claudeのチャット経由ではキーを設定しない):

1. GitHubリポジトリの Settings > Secrets and variables > Actions > New repository secret で `LINEAR_API_KEY` を追加する
2. `Actions` タブで `trend-watcher` ワークフローを選び、`Run workflow`(workflow_dispatch)で手動テスト実行できる
3. GitHubが自動提供する `GITHUB_TOKEN` をGitHub Search APIの認証に使うので追加設定は不要(レート制限緩和のみ)

## ローカル(devcontainer)での実行(動作確認・デバッグ用)

GitHub Actions本番運用とは別に、ローカルで単発/常駐実行することもできる。常駐実行はPCがスリープすると一緒に止まるため、本番用途には使わない。

`.env.local` を作成し、以下を記載する(gitignore済み):
```
LINEAR_API_KEY=lin_api_xxxxxxxxxxxx
```

単発実行(動作確認用):
```sh
set -a; source .env.local; set +a
./trend-watcher-daemon.sh --once
```

常駐起動(デバッグ用。PCがスリープすると停止する):
```sh
set -a; source .env.local; set +a
setsid nohup ./trend-watcher-daemon.sh > trend-watcher.log 2>&1 < /dev/null &
```
(`setsid`で端末/呼び出し元シェルのセッションから完全に切り離す。`nohup ... & disown`だと、呼び出し元のシェルがすぐ終了する環境ではバックグラウンドジョブ自体が始まる前に消えることがある)

ログ確認:
```sh
tail -f trend-watcher.log
```

停止:
```sh
pkill -f trend-watcher-daemon.sh
```

## 動作の要点

- 1回の実行で最大3件まで起票(`MAX_ISSUES_PER_RUN`)。ノイズ防止。
- 起票前にLinear上の直近30日分のissueタイトルと重複しないか確認し、重複していればスキップする(`LINEAR_DEDUP_LOOKBACK_DAYS`)。
- 起票したissueには label `auto-filed` が付き、assignee/delegateは設定しない。Devinへの委任を行うかどうかは人間が判断する。
- しきい値や対象トピック/キーワードはスクリプト先頭の変数(`GITHUB_TOPICS`、`NEWS_KEYWORDS`、`GITHUB_MIN_STARS`、`NEWS_MIN_POINTS`など)で調整できる。
