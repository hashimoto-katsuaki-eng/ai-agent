# ruvnet/agent-harness-generator (MetaHarness)

- **URL**: https://github.com/ruvnet/agent-harness-generator
- **調査日**: 2026-06-21
- **Star数**: 266
- **Fork数**: 25
- **ライセンス**: MIT
- **言語**: TypeScript / Rust (WASM + NAPI-RS)
- **作成日**: 2026-06-13（調査時点で8日目）
- **Linear issue**: AI-24

## 概要

MetaHarness は「任意の GitHub リポジトリから、そのリポジトリ専用の AI エージェントハーネスを生成するファクトリー」を標榜する CLI ツール兼ブラウザ Studio。`npx metaharness` で実行でき、生成物は npm パッケージとして publish 可能な `.zip`。Claude Code, OpenAI Codex, pi.dev, Hermes, OpenClaw, RVM, GitHub Copilot, OpenCode, GitHub Actions の9ホストに対応するアダプターを出力する。

エージェントフレームワークではなく「エージェントフレームワークのファクトリー」という位置づけ。モデルは交換可能で、ハーネス（設定・ポリシー・スキル・MCP サーバー・ガバナンス）がプロダクトであるという思想。

## リポジトリ構成

| ディレクトリ | 内容 |
|---|---|
| `packages/create-agent-harness` | メイン CLI (`metaharness` / `harness`) — 40+ ソースファイル |
| `crates/kernel` | Rust カーネル — MCP, hooks, memory, routing, witness 等 7 サブシステム (2,259 行) |
| `crates/kernel-wasm` / `kernel-napi` | WASM / NAPI-RS バインディング |
| `packages/darwin-mode` | 自己進化機構 — ハーネス設定をミューテーション＋サンドボックステスト＋選択 |
| `packages/router` | コスト最適モデルルーター (k-NN over embeddings) |
| `packages/bench/draco` | クロスドメイン深層リサーチベンチマーク |
| `packages/host-*` | 各ホスト向けアダプター (claude-code, codex, hermes, pi-dev, openclaw, rvm, copilot, opencode, github-actions) |
| `apps/web-ui` | ブラウザ Studio (Vite + Tailwind, GitHub Pages でホスト) |
| `examples-packages/` | 39 個の公開済み `@metaharness/*` ラッパーパッケージ |

総ファイル数: 約 1,534 ファイル / 22 MB（.git 除く）。TypeScript/JS 約 59,500 行、Rust 約 2,700 行、テスト 168 ファイル。

## セキュリティ評価

### 悪意のあるコードの兆候: なし

- **難読化コード**: `eval()`, `atob()`/`btoa()`, `fromCharCode` 等のパターンなし（`eval` は darwin-mode の安全層 `safety.ts` 内のサンドボックス用途のみで、外部入力を直接渡さない設計）
- **不審なインストール/ビルドスクリプト**: `postinstall` / `preinstall` フックなし。`package.json` の scripts は標準的なビルド・テストのみ
- **ネットワーク通信**: Rust カーネルにネットワーク依存なし（`reqwest`, `hyper`, `TcpStream` 等不使用）。TypeScript 側の `fetch` は GCP Secret Manager からの npm トークン取得（publish 時）と IPFS ピン（明示的な publish コマンド実行時）のみ
- **テレメトリ/フォンホーム**: なし。README にも「No telemetry」と明記
- **Rust `unsafe`**: カーネルで `#![forbid(unsafe_code)]` を宣言。違反なし

### サプライチェーン

- **依存関係**: 本体の npm 依存は `kolorist`, `prompts`, `@metaharness/darwin` の 3 つのみ（軽量）
- **Rust 依存**: `serde`, `serde_json`, `thiserror`, `anyhow`, `wasm-bindgen`, `ed25519-dalek`, `sha2` 等の標準的なクレート
- **`deny.toml`**: unknown-registry / unknown-git を deny、ライセンスホワイトリスト制、wildcard 依存を deny
- **CI セキュリティパイプライン**: `cargo-audit` + `cargo-deny` + `npm audit` + CodeQL + SBOM (SPDX-2.3) が毎 push + 週次 cron で実行
- **Renovate**: 週次で依存更新、パッチ/マイナーは自動マージ設定
- **npm publish**: GCP Workload Identity Federation 経由の短命トークン + npm provenance (SLSA L2)

### Star 数の急増について

- 266 ★ を 8 日間で獲得。1 日あたり約 33 ★ の増加ペース
- コミット数: 431 コミット / 8 日（1 日あたり 54 コミット平均）。特に 6/14 に 144 コミット、6/18 に 98 コミット
- コントリビューター: 実質 1 名（rUv / ruv）+ Claude による自動コミット 15 件
- npm ダウンロード数: 公開初週で約 30,700 DL（6/18 にピーク 11,849 DL/日）
- **判定**: 単独開発者による集中的な開発。コードに実体があり、テスト 568 件、CI マトリックス 16 ジョブ、npm に 11+ パッケージが公開済み。Star 数は急増しているが、コードの実体・npm ダウンロード数・ドキュメントの充実度を考慮すると、不自然な操作（Star 購入等）の明確な兆候は確認できなかった。ただし、8 日で 266 ★ は注視に値する

## 技術的特徴

### 強み

1. **Rust + WASM + NAPI-RS のハイブリッドカーネル**: ブラウザ（WASM）と Node.js（NAPI-RS）の両方で動作する共通カーネル。Ed25519 署名による witness manifest でリリース provenance を保証
2. **Darwin Mode**: SWE-bench Lite で実証済みの自己進化機構。安価なモデルでフロンティアモデル並の品質を目指す。安全層 (`safety.ts`) が 7 つの承認済みミューテーション面のみに制限
3. **マルチホスト対応**: 9 つのエージェントホストへの統一出力。MCP はデフォルト deny で監査付き
4. **DRACO ベンチマーク**: 独自のクロスドメインリサーチ品質ベンチマーク
5. **セキュリティへの配慮**: `#![forbid(unsafe_code)]`, cargo-deny, SBOM, SLSA L2 provenance

### 懸念・弱み

1. **8 日間で 431 コミット + 60K 行の TS**: 単独開発者による極めて高速な開発。AI 支援コーディング（Claude）を活用している形跡あり。コード品質の持続性は未知数
2. **v0.1.x beta**: プロダクション利用には早い段階。README の "credibility/doc reconciliation in progress" の記述あり
3. **実質 1 人プロジェクト**: bus factor = 1。コミュニティ形成はこれから
4. **対応ホストの一部は作者自身のプロジェクト**: RVM, OpenClaw は ruvnet 自身のリポジトリ。実際のユーザーベースは不明

## AI/LLM エージェント関連ツールとしての位置づけ

MetaHarness は既存のエージェントフレームワーク（LangChain, CrewAI, AutoGen 等）とは異なるレイヤーに位置する。フレームワーク自体を提供するのではなく、リポジトリの構造を静的解析してそのリポジトリに最適化されたエージェントハーネス（設定・スキル・コマンド・MCP サーバー）を生成する「メタレイヤー」ツール。

類似ツール:
- **claude-engineer / aider**: コーディングエージェント（MetaHarness はエージェントそのものではなくハーネスを生成）
- **create-react-app / Yeoman**: スキャフォールディングツール（最も近い比喩。ただし AI エージェント特化）

## 注目に値するか

**値する（条件付き）**。

- コードに実体があり、マーケティングだけのプロジェクトではない
- Rust + WASM カーネル、Ed25519 provenance、MCP default-deny、Darwin Mode（SWE-bench 実証）など技術的に興味深い要素がある
- 「リポジトリからエージェントハーネスを自動生成する」というコンセプト自体はユニークで、AI エージェント開発のメタツールとして新しい切り口
- ただし v0.1.x beta / 単独開発者 / 8 日のプロジェクト歴であり、継続性・コミュニティ形成は未知数。ウォッチリストに入れて 1-2 ヶ月後に再評価が妥当
