# omnigent-ai/omnigent

| 項目 | 値 |
|------|-----|
| URL | https://github.com/omnigent-ai/omnigent |
| Star数 | 4,253 (検知時点) |
| 作成日 | 2026-06-13 |
| ライセンス | Apache 2.0 |
| 作者 | Databricks, Inc. |
| 調査日 | 2026-06-21 |
| Linear | AI-19 |

## 概要

Omnigentは、Databricksが開発しApache 2.0でオープンソース化した**AIエージェントのメタハーネス（meta-harness）フレームワーク**。Claude Code、Codex、Cursor、Pi等の既存コーディングエージェントや、ユーザが自作したYAML定義エージェントを、共通のオーケストレーション層で統合的に扱えるようにするもの。

主な機能:
- **マルチエージェント協調**: 複数のエージェント（Claude Code, Codex, Pi等）を1セッション内で同時に使用し、タスク分担・クロスレビューが可能
- **デバイス横断セッション**: ターミナル、ブラウザ（localhost:6767）、macOSデスクトップアプリ、モバイルからの同一セッション操作
- **マルチモデル対応**: Anthropic, OpenAI, Databricks, OpenRouter, Ollama等、各種プロバイダのAPIキー/サブスクリプション/ゲートウェイに対応
- **ポリシーガバナンス**: 危険な操作の承認フロー、コスト上限、ツール制限等をサーバー/エージェント/チャット単位で宣言的に設定
- **クラウドサンドボックス**: Modal, Daytona, Islo, E2B等でリモートサンドボックス実行
- **リアルタイム共同作業**: セッション共有、ライブ共同操作、フォーク機能

## リポジトリ構成

- **Python (64.3万行, 1,355ファイル)**: メインのオーケストレーション・ランタイム・サーバー・CLI
  - `omnigent/inner/`: ハーネス実装（Claude, Codex, Pi, Cursor, Antigravity）、サンドボックス（bwrap/seatbelt）、エグレスプロキシ
  - `omnigent/server/`: FastAPIベースのWebサーバー、認証、ホスト管理、WebSocket
  - `omnigent/runtime/`: ハーネス抽象化、ポリシーエンジン、セッションライフサイクル
  - `omnigent/runner/`: エージェント実行、MCP管理、コストアドバイザー
  - `omnigent/policies/`: CELベースのポリシー評価エンジン
  - `omnigent/llms/`: マルチプロバイダLLMクライアント（OpenAI Responses API互換）
  - `omnigent/sandbox/`: OS分離（Linux: bubblewrap + seccomp, macOS: seatbelt）
- **TypeScript/React (12.6万行, 460ファイル)**: `ap-web/` にVite + Reactベースの管理WebUI
- **SDK**: `sdks/python-client/`（ヘッドレスHTTP/SSEクライアント）、`sdks/ui/`（ターミナルUI）
- **デプロイ**: `deploy/` に Modal, Docker, Fly, Railway, Render, Kubernetes, Cloudflare, E2B, Daytona 等の構成
- **テスト**: 883テストファイル（ユニット, インテグレーション, E2E, E2E UI）
- **CI**: 41ワークフロー（セキュリティスキャン、lint、テストマトリクス、E2E、コードカバレッジ等）
- **例示エージェント**:
  - `polly`: マルチエージェント・コーディングオーケストレーター（コードを書かないテックリード、Claude Code/Codex/Piに委任）
  - `debby`: 2ヘッド（Claude + GPT）のブレインストーミングパートナー

## セキュリティ評価

### 悪意のあるコード: 検出なし

- インストールスクリプト `scripts/install_oss.sh` (642行) は `uv tool install omnigent` を実行するラッパー。base64エンコード・難読化・外部への不審な通信なし。ネットワーク通信先はPyPIのみ。
- `package.json` に `postinstall` / `preinstall` フックなし。
- サンドボックス実装（bwrap, seatbelt, seccomp）は防御的セキュリティ機構であり、エージェント実行環境を隔離するもの。
- エグレスプロキシ (`omnigent/inner/egress/`) はL7レベルのHTTPS出力フィルタリングで、ホスト・パス単位のallow-listベース。デフォルト拒否。
- クレデンシャルプロキシ (`omnigent/inner/credential_proxy.py`) はサンドボックス内に実シークレットを渡さない「swap-on-access」モデル。

### 依存関係

- Pythonランタイム依存: pyyaml, openai, rich, prompt_toolkit, mcp, starlette, uvicorn, httpx, psutil, pydantic, sqlalchemy, tiktoken, fastapi, alembic 等。いずれも広く使われた安定パッケージ。
- オプショナル: databricks-sdk, boto3 (bedrock/s3), google-auth (vertex), modal, daytona 等。
- フロントエンド: React, Vite, Monaco Editor, Shiki, Radix UI 等の標準的なエコシステム。
- サプライチェーンリスクは低い。依存パッケージはすべてメジャーなOSSプロジェクト。

### 難読化: なし

- ソースコードはすべて平文のPython / TypeScript。`omnigent/server/static/web-ui/` にビルド済みのWeb UIバンドルがあるが、pre-commitで除外されており、`ap-web/` のソースから生成されたもの。

### Star数の急増について

- 初回コミット 2026-06-13、検知時点で約8日間で4,253 star。
- **Databricks公式ブログ** (2026-06-13) でオープンソース化を発表。heise online, MarkTechPost等の技術メディアも報道。
- コミット538件、コントリビューター20名以上（Pat Sukprasert 144, Tomu Hirata 112, Serena Ruan 78, Sabhya Chhabria 48等）。Databricks社員チームによる本格的な開発。
- コミット履歴は自然（PR番号 #12〜#894、CI修正、テスト改善、リファクタリング等の通常のOSS開発パターン）。
- **不自然なstar操作の兆候は確認されなかった。** Databricksブランドと公式ブログからの流入が主因。

### CI セキュリティゲート

- フォークPRに対する独自のセキュリティスキャン (`security-scan.yml`) を実装。信頼されないコードのビルド・実行前にdiffを静的解析し、シークレット漏洩・exfiltration・CI設定改竄等を検出。信頼レベル（OWNER/MEMBER/COLLABORATOR/CONTRIBUTOR/first-timer）ごとのゲート制御あり。

## AI/LLMエージェント関連ツールとしての位置づけ

### 注目に値する理由

1. **メタハーネスという新カテゴリ**: 個々のエージェント（Claude Code, Codex等）の上位に位置し、それらを統合・交換可能にするレイヤーを提案。「どのエージェントも入力はメッセージとファイル、出力はテキストストリームとツールコール」という洞察に基づく共通API。
2. **Databricks社の本格的OSS**: 20名以上のコントリビューター、538コミット、883テストファイル、41 CIワークフロー。企業としてのコミットメント。pyproject.toml の author は "Databricks, Inc."。
3. **セキュリティファースト設計**: OS-sandbox (bwrap/seatbelt + seccomp)、L7エグレスプロキシ（デフォルト拒否）、クレデンシャルプロキシ（sandbox内にシークレットなし）、CELベースのポリシーエンジン、フォークPRセキュリティスキャン。
4. **実用的なマルチエージェント協調**: Polly（テックリード兼オーケストレーター）やDebby（2モデル比較ブレインストーム）等の実例付き。異なるベンダーのエージェントにクロスレビューさせる運用パターン。
5. **幅広いデプロイオプション**: Docker, Modal, Daytona, Fly, Railway, Render, Kubernetes, Cloudflare, E2B等のサンドボックス/デプロイ構成を同梱。
6. **宣言的エージェント定義**: YAMLでエージェントを定義し、ハーネス（claude-sdk, codex, pi, openai-agents, cursor等）を指定。プロンプトとツール構成を分離。

### 制約・注意点

- **アルファ段階**: バージョン 0.2.0.dev0。APIの安定性は保証されていない。
- **新規リポジトリ**: 公開から8日と歴史が浅く、外部の運用実績は不明。
- **重厚な依存関係**: ランタイム依存だけで20以上のパッケージ。Python 3.12+、Node.js 22+、tmux、bubblewrap（Linux）等の前提条件あり。
- **Databricks色**: オプショナルだがDatabricksワークスペース統合が深く組み込まれている（`databricks-sdk`, `databricks-mcp`等）。

## 自リポジトリ(ai-agent)との関連

- ai-agentの `trend-watcher` による自動起票→Devin委任パイプラインは、Omnigentの「Polly」がタスク分割→サブエージェント委任する構造と概念的に類似。ただしai-agentは非LLMスクリプトベース、Omnigentは全面的にLLMオーケストレーション。
- Omnigentのポリシーガバナンス（承認フロー、コスト上限、ツール制限）の考え方は、ai-agentの自動化拡張において参考になりうる。
- Omnigentの宣言的エージェント定義（YAML）は、ai-agentでエージェント構成を管理する際のフォーマットとして検討材料になる。

## 結論

**注目に値する。** Databricksが本格的にオープンソース化したAIエージェントのメタハーネスフレームワーク。セキュリティ上の懸念なし（むしろOS-sandbox、エグレスプロキシ、クレデンシャル分離等の防御機構が充実）。複数のコーディングエージェントを統合管理し、ポリシーガバナンスを適用するという「メタハーネス」レイヤーは、エージェント運用の成熟に伴い重要性が増すカテゴリ。Star数の急増はDatabricks公式ブログ・技術メディア報道からの流入が主因で、不自然な操作の兆候なし。
