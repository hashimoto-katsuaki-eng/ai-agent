# ai-agent リポジトリでの運用ルール

このリポジトリは Linear チーム `Ai-agents-Teams` と GitHub 連携している。Devin がこのチームの delegate として登録されており、issue 起票 → Devin に委任 → PR 作成、という自律実行パイプラインが既に稼働している(参照: AI-7)。Claude Code もこのパイプラインに参加する。

## Linear-gate フック

`.claude/settings.json` の PreToolUse フックにより、**このセッションで `mcp__linear__save_issue`(team=`Ai-agents-Teams`)で issue を起票するまで Write/Edit/NotebookEdit はすべて拒否される**。title=タスク名、description=完了条件(Definition of Done)のみで起票してよい。最初のファイル変更の前に必ず起票すること。

## タスクの拾い方

- 通常は会話で直接指示されたタスクに取り組む。
- 「何かやることある?」のように明示的に聞かれた場合は、`mcp__linear__list_issues`(team=`Ai-agents-Teams`)で未着手バックログを確認し、Devin にすでに delegate 済みの issue は避けて拾う。
- さらに、claude.ai のクラウドルーティン「`linearバックログ定期チェック`」(`trig_011EvNz9DiaBrnmbQLUStefC`, AI-14)が5時間おきに自動でバックログを確認し、候補を提示する。モデルは `claude-haiku-4-5`、`allowed_tools` は `Read/Glob/Grep` のみで、issueの更新やコード変更は一切行わない(提示のみ)。実際の着手判断は人間が行う。結果は claude.ai のルーティンページで確認する。

## 自動issue起票ツール: trend-watcher

- `trend-watcher/trend-watcher-daemon.sh`(AI-15)が、GitHub Search API と Hacker News(Algolia)Search APIをポーリングし、AI/LLMエージェント開発ツール関連で閾値(star数/ポイント数+作成・投稿の新しさ)を超えた項目を `Ai-agents-Teams` に自動起票する。
- **LLM/Claudeトークンは一切使わない**: 取得・閾値判定・重複チェック・issue作成まですべてbash+curl+jqのルールベース処理。`claude-limit-watcher/claude-limit-daemon.sh` と同じ構成(daemonループ、`--once`で単発実行)。
- **本番運用は GitHub Actions**(`.github/workflows/trend-watcher.yml`、5時間おき)。PC本体やdevcontainerの起動状態に依存しない。devcontainer内での常駐起動(README参照)はデバッグ用で、PCがスリープすると一緒に止まる。
- 起票前にLinear GraphQL APIで直近30日分のissueタイトルと重複しないか確認してからissueを作る(1回の実行で最大3件、ノイズ防止)。
- 自動起票されたissueには label `auto-filed` が付き、delegateは未設定。Devinへの委任を行うかどうかは人間が判断する。
- 必須環境変数 `LINEAR_API_KEY` は本番ではGitHub Actionsのrepository secretに置く。ローカル実行時のみ `trend-watcher/.env.local`(gitignore済み、Claude自身からの読み取りも `.claude/hooks/protect-env.sh` で禁止)を使う。
- 何かを定期的に調べて判断するだけの作業は、LLMで毎回賄うのではなく、まずこの形(非LLMスクリプト)で解決できないかを優先する。

## 無人実行・監視の使い分け

- **非LLMの常駐スクリプト**: 単純な閾値ポーリングや通知(例: `claude-limit-watcher/claude-limit-daemon.sh`)はこの形のままにする。判断不要・コストをかけたくないものはここに置く。
- **`/loop`**: ログ/PR/状態の「解釈」が必要な巡回監視に使う。間隔を指定(`/loop 5m <prompt>`)、省略時は自動判断。裏でcronに変換され、Escで停止できる。
- **`/goal`(+ auto mode)**: 「終わりのある」長いタスク(移行作業の完遂、バックログ消化など)を複数ターンに渡って自走させたいときに使う。完了条件は観測可能な形で書く(test exit 0、lint cleanなど)。暴走防止に `or stop after N turns` のようなターン数キャップを必ず付ける。

## 並行ワークストリーム

複数の issue を同時に進める場合は、issue ごとに `EnterWorktree` で作業ツリーを分け、`Agent(..., run_in_background: true)` で並行実行し、`TaskCreate`/`TaskList` を共有ボードとして進捗を追う。

## Devin との役割分担

Devin は既にこのリポジトリの delegate。同じ issue に二重着手しない。着手前に delegate 欄を確認する。
