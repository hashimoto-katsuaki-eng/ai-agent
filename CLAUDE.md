# ai-agent リポジトリでの運用ルール

このリポジトリは Linear チーム `Ai-agents-Teams` と GitHub 連携している。Devin がこのチームの delegate として登録されており、issue 起票 → Devin に委任 → PR 作成、という自律実行パイプラインが既に稼働している(参照: AI-7)。Claude Code もこのパイプラインに参加する。

## Linear-gate フック

`.claude/settings.json` の PreToolUse フックにより、**このセッションで `mcp__linear__save_issue`(team=`Ai-agents-Teams`)で issue を起票するまで Write/Edit/NotebookEdit はすべて拒否される**。title=タスク名、description=完了条件(Definition of Done)のみで起票してよい。最初のファイル変更の前に必ず起票すること。

## タスクの拾い方

- 通常は会話で直接指示されたタスクに取り組む。
- 「何かやることある?」のように明示的に聞かれた場合は、`mcp__linear__list_issues`(team=`Ai-agents-Teams`)で未着手バックログを確認し、Devin にすでに delegate 済みの issue は避けて拾う。

## 無人実行・監視の使い分け

- **非LLMの常駐スクリプト**: 単純な閾値ポーリングや通知(例: `claude-limit-watcher/claude-limit-daemon.sh`)はこの形のままにする。判断不要・コストをかけたくないものはここに置く。
- **`/loop`**: ログ/PR/状態の「解釈」が必要な巡回監視に使う。間隔を指定(`/loop 5m <prompt>`)、省略時は自動判断。裏でcronに変換され、Escで停止できる。
- **`/goal`(+ auto mode)**: 「終わりのある」長いタスク(移行作業の完遂、バックログ消化など)を複数ターンに渡って自走させたいときに使う。完了条件は観測可能な形で書く(test exit 0、lint cleanなど)。暴走防止に `or stop after N turns` のようなターン数キャップを必ず付ける。

## 並行ワークストリーム

複数の issue を同時に進める場合は、issue ごとに `EnterWorktree` で作業ツリーを分け、`Agent(..., run_in_background: true)` で並行実行し、`TaskCreate`/`TaskList` を共有ボードとして進捗を追う。

## Devin との役割分担

Devin は既にこのリポジトリの delegate。同じ issue に二重着手しない。着手前に delegate 欄を確認する。
