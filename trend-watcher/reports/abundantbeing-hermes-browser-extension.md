# abundantbeing/hermes-browser-extension

| 項目 | 値 |
|------|-----|
| URL | https://github.com/abundantbeing/hermes-browser-extension |
| Star数 | 194 (検知時点) |
| 作成日 | 2026-06-24 |
| ライセンス | MIT |
| 作者 | Jon Komet (@abundantbeing) |
| 調査日 | 2026-06-27 |
| Linear | AI-73 |

## 概要

Hermes Browser Extension は、Nous Research の [Hermes Agent](https://github.com/NousResearch/hermes-agent) ランタイムに接続するための Chrome/Edge/Chromium MV3 サイドパネル拡張機能。ブラウザのアクティブタブのコンテキスト（ページテキスト、メタデータ、選択テキスト、YouTube字幕など）を収集し、ローカルまたはリモートの Hermes Gateway/API サーバーに送信して、AI エージェントとの対話を可能にする。

公式の Chrome Web Store には未公開（`Load unpacked` で手動インストール）。公開アルファ版 v0.1.5。

## リポジトリ構成

- **全コード約7,674行**（JS/MJS）、21コミット、3日間の開発期間（2026-06-24〜27）。
- **拡張機能本体** (`extension/`):
  - `manifest.json`: MV3マニフェスト、Chrome 114+対応
  - `sidepanel.js` (3,920行): メインUI、Hermes API クライアント、チャット、設定、モデル/セッション管理
  - `content.js` (257行): ページコンテキスト収集（読み取り専用）
  - `background.js` (134行): サイドパネル制御、YouTube字幕取得
  - `lib/common.mjs` (1,072行): プロンプト構築、シークレット自動リダクション、Markdown レンダリング
  - `lib/gateway-ws.mjs` (202行): JSON-RPC 2.0 over WebSocket クライアント
  - `lib/dashboard-bridge.mjs` (114行): OAuth付きダッシュボード経由のWebSocketチケット取得
  - `lib/agent-discovery.mjs` (140行): ローカルHermesゲートウェイの自動検出
  - `lib/model-discovery.mjs` (197行): モデルレジストリ統合
  - `lib/transcript.mjs` (121行): YouTube字幕パーサー
  - `voice-dictation.js` (422行): 音声入力（Hermes STT / ブラウザ Speech API フォールバック）
- **レビュー自動化** (`scripts/`):
  - `hermes-review-watch.mjs`: ローカルポーラー、open PR/issueを巡回しHermesでレビュー
  - `hermes-review-github-event.mjs`: GitHub Actions/webhook用イベントランナー
- **ユーティリティ**: `build.mjs`（extension/ → dist/ コピー）、`check-manifest.mjs`、`package.mjs`、`windows-setup.mjs`（Windows用セットアップヘルパー）
- **テスト** (`tests/`): 6ファイル、Node.js組み込みテストランナー使用
- **ドキュメント**: SECURITY.md, PERMISSIONS.md, DATA-FLOW.md, PRIVACY.md, CONTRIBUTING.md, CHANGELOG.md

## セキュリティ評価

### 悪意のあるコード: 検出なし

- 拡張機能コード（extension/）はすべて平文の JavaScript/ESM。難読化・ミニファイなし。
- `eval()`, `new Function()`, 動的コード生成は一切使用していない。
- `package.json` に `postinstall` / `preinstall` フックなし。外部依存パッケージゼロ（devDependencies もなし）。
- `child_process` の使用は scripts/ とテストのみ（`gh auth token` 取得、`spawnSync` でのビルド/パッケージング）。拡張機能本体では使用なし。

### 権限モデル

- **要求する権限**: `activeTab`, `scripting`, `sidePanel`, `storage`, `tabs`
- **オプション権限**: `audioCapture`（マイク使用時のみ）
- **ホスト権限**: `http://*/*`, `https://*/*`, `http://127.0.0.1/*`, `http://localhost/*`
  - ホスト権限は広い（全HTTPページ）が、コンテンツスクリプトは読み取り専用で、ページ操作（クリック、フォーム送信等）は行わない。
- **要求しない権限**: `debugger`, `nativeMessaging`, `cookies`, `history`, `downloads`, `bookmarks`
- ブラウザ内部ページ（`chrome://`等）および銀行・暗号通貨・パスワード管理等のセンシティブURLは明示的にブロック。

### セキュリティ設計

- ページテキストは `UNTRUSTED_BROWSER_CONTEXT_START/END` で囲んでHermesに送信。プロンプトインジェクション対策。
- APIキーは `chrome.storage.local` に保存、UI上ではマスク表示。v0.1.5でトークンクリア機能追加。
- シークレット自動リダクション: Bearer トークン、OpenAI/Stripe/AWS/GitHub/Google/Slack のAPIキー、JWT、PEM秘密鍵、key=value形式のシークレットを送信前に `[REDACTED_SECRET]` に置換。
- ゲートウェイ接続時、`/health` プローブは非認証で実行し、Hermesと確認後にのみBearerトークンを送信（誤入力先へのトークン漏洩防止）。

### ネットワーク通信

- 拡張機能の通信先は3種のみ:
  1. ユーザー設定の Hermes Gateway URL（デフォルト `http://127.0.0.1:8642`）
  2. YouTube字幕取得（`video.google.com/timedtext`）
  3. GitHubバージョンチェック（`raw.githubusercontent.com` のpackage.json取得、`api.github.com` のコミット比較）
- 外部の分析サービス、テレメトリ、広告SDKへの通信なし。

### 依存関係

- ランタイム依存パッケージ: ゼロ（`node_modules` 不要で動作する純粋なブラウザ拡張機能）。
- Node.js依存: 標準ライブラリのみ（`node:fs`, `node:path`, `node:crypto`, `node:child_process`）。scripts/テスト用。
- サプライチェーンリスク: 極めて低い。

### 難読化: なし

- ソースコードはすべて平文。`build.mjs` は extension/ → dist/ への単純なファイルコピーのみ（バンドラー・トランスパイラ不使用）。

### Star数の急増について

- 初回コミット 2026-06-24、検知時点で約3日間で194 star。
- 著者 Jon Komet (@abundantbeing) は Hermes Agent エコシステムのコミュニティ貢献者。
- Nous Research の Hermes Agent（公式リポジトリ）のブラウザ拡張として位置づけられており、Hermes コミュニティからの自然な流入と推定。
- コミット履歴は自然（21コミット、2名のコントリビューター: abundantbeing 19件、Panat Taranat 2件）。
- 外部コントリビューターの Panat Taranat は remote-dashboard WebSocket モードの機能をPRで追加。
- **不自然なstar操作の兆候は確認されなかった。**

## AI/LLMエージェント関連ツールとしての位置づけ

### 注目に値する理由

1. **Hermes Agentの実用的なブラウザインターフェース**: Nous Research の Hermes Agent ランタイムにブラウザコンテキストを接続する初のサイドパネル拡張機能。「今見ているページについてAIに聞く」というユースケースを、Hermes のモデル・ツール・スキル・セッション・MCP サーバー機能と組み合わせて実現。
2. **セキュリティ意識の高い設計**: v0.1で読み取り専用に限定、プロンプトインジェクション対策、シークレット自動リダクション、センシティブURL ブロックなど、ブラウザ拡張機能の攻撃面を意識した保守的な設計。
3. **ゼロ依存**: 外部npmパッケージに依存せず、標準Web APIとChrome Extension APIのみで動作。サプライチェーンリスクが極めて低い。
4. **レビュー自動化の組み込み**: Hermes Agent を使ったPR/issueの自動レビュー機能をリポジトリ自体に組み込んでおり、AIエージェントの実用的な開発ワークフロー統合の一例。
5. **複数接続モード**: ローカルAPIサーバー、リモートAPIサーバー、リモートダッシュボードWebSocket の3モードをサポートし、セルフホスト型AIエージェントの柔軟な運用に対応。

### 制約・注意点

- **Hermes Agent依存**: 単独では動作せず、Hermes Agent のインストールとGateway/APIサーバーの起動が前提。汎用的なLLMブラウザ拡張機能ではない。
- **アルファ版**: Chrome Web Store未公開、Load unpacked必須。ユーザーベースはHermes Agentの利用者に限定される。
- **ホスト権限の広さ**: `http://*/*` と `https://*/*` の全サイトホスト権限は、読み取り専用とはいえ権限としては広い。Web Store公開時には narrower permissions（`activeTab` + on-demand host permissionsなど）への移行が望ましい。
- **開発期間の短さ**: 3日間で194 starは注目度としては高いが、リポジトリの成熟度はまだ低い。

## 自リポジトリ(ai-agent)との関連

- ai-agent の trend-watcher が検知した Hermes Agent エコシステムの拡張プロジェクト。Nous Research の Hermes Agent 自体は主要なオープンソース AI エージェントフレームワークの一つであり、そのブラウザ統合は AI エージェントの新たなインターフェース層として参考になる。
- レビュー自動化スクリプト（hermes-review-watch/hermes-review-github-event）のアーキテクチャは、ai-agent の trend-watcher のような非LLM自動化と LLM レビューの組み合わせの一例として参考になる。

## 結論

**注目に値する。** セキュリティ上の懸念なし。Nous Research の Hermes Agent ランタイムにブラウザコンテキストを接続するサイドパネル拡張機能として、ゼロ依存・読み取り専用・プロンプトインジェクション対策など保守的な設計が光る。Hermes Agent エコシステムの実用的なブラウザ統合の先駆けとして有用。Star数の急増はHermesコミュニティからの自然な流入と推定され、不自然な操作の兆候なし。
