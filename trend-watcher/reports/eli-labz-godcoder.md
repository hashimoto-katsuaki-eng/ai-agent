# eli-labz/Godcoder

| 項目 | 値 |
|------|-----|
| URL | https://github.com/eli-labz/Godcoder |
| Star数 | 221 (検知時点) |
| 作成日 | 2026-06-26 |
| ライセンス | MIT |
| 作者 | e-l-i (dmesa@e-l-i.net) |
| 調査日 | 2026-06-27 |
| Linear | AI-75 |

## 概要

「Godcoder」は、**TransformerOptimus/SuperCoder（★971）のほぼ完全なコピーをリブランドしたリポジトリ**。SuperCoderはSuperAGI社が開発するローカルファーストのオープンソースAIコーディングエージェントで、Rust製のエージェントコアとTauri 2 + Reactデスクトップアプリから構成される。

Godcoderはこれを丸ごとコピーし、名前を「Godcoder」に変更して公開したもの。元リポジトリのGitHub fork機能は使用しておらず、全ファイルを1コミット目に一括投入している。

## リポジトリ構成

- **コミット数**: 4件（すべて2026-06-26の同日、単一著者）
- **ファイル数**: 1,167ファイル（.git除く、18MB）
- **構成**:
  - `crates/agent/` — Rust製エージェントコア（約20,000行）: ループ、ツール、Ask/Plan/Codingモード、サブエージェント、スキル、プロンプトキャッシュ
  - `crates/git-ops/` — ワーキングツリーのチェックポイント/diff/リストア
  - `crates/context-sync/` — コンテキストエンジンとの同期
  - `crates/bench-runner/` — ベンチマーク実行バイナリ
  - `apps/desktop/` — Tauri 2 + React デスクトップアプリ（フロントエンド約4,100行 TS/TSX）
  - `services/context-engine/` — Go製オプショナルインデックスサービス（約19,000行）: tree-sitter → Qdrant + FalkorDB + BM25
  - `v1/` — 2024年の旧パイプライン（凍結、SuperAGI社のロゴ・リンクがそのまま残存）

## オリジナルとの関係

| 項目 | TransformerOptimus/SuperCoder | eli-labz/Godcoder |
|------|------|------|
| Star数 | 971 | 221 |
| 作成日 | 2024-07-03 | 2026-06-26 |
| コミット数 | 多数（複数コントリビュータ、リリースv0.1.0あり） | 4（単一著者） |
| fork関係 | — | GitHub fork **ではない**（独立リポジトリとして作成） |
| go.mod | `module github.com/TransformerOptimus/SuperCoder` | 同左（変更されていない） |
| LICENSE | MIT, Copyright 2023 TransformerOptimus | MIT, Copyright 2023 TransformerOptimus + "Godcoder is a rebrand" 追記 |

### Godcoder独自の変更点（4コミットの差分）

1. **リブランド**: README、パッケージ名、アイコン等で「SuperCoder」→「Godcoder」に置換
2. **Voice API設定追加**: TTS/STT/Voice-to-Voice用のAPIキー保存UIとTauriコマンド（約230行追加）
3. **Windowsランチャー**: `launch-godcoder.bat`（35行）
4. **READMEの装飾強化**: バッジ、機能テーブル等

実質的な機能追加はVoice設定UI程度で、エージェントコアやコンテキストエンジンのロジックは一切変更されていない。

## セキュリティ評価

### 悪意のあるコード: 検出なし

- コードベースはSuperCoderと実質同一。外部への不審な通信、バックドア、データ窃取の痕跡なし。
- `package.json`に`postinstall`/`preinstall`フックなし。
- ネットワーク通信はすべてユーザーが明示的に設定したLLMプロバイダ（OpenAI/Anthropic）への正規APIコールのみ。
- Rust crateの依存関係はすべて広く使われている安定パッケージ（tokio, reqwest, serde等）。

### 難読化: なし

- ソースコードは平文のRust/Go/TypeScript。難読化やミニファイされたバイナリの同梱なし。

### サプライチェーンリスク: 低（SuperCoderと同等）

- 依存関係はSuperCoderから変更なし。Cargo.lockで固定。
- Context EngineのGoモジュール依存も既知の安定パッケージ群（gin, gorm, qdrant-client等）。

### Star数の急増について

- **強い不自然さの兆候あり。**
- リポジトリ作成から約1日で221 star。内容は既存OSS（SuperCoder）のリブランドに過ぎない。
- 同一org（eli-labz）の別リポジトリ「Third-Eye」も2026-06-13作成で831 starを獲得しGitHub Trendingに入った実績がある。
- eli-labzのリポジトリは短期間で複数プロジェクトが急速にstar数を伸ばしており、**star購入またはbotによる操作が疑われるパターン**。
- GitHub forkを使わず独立リポジトリとして作成しているのは、fork表示を避けてオリジナルに見せかける意図の可能性。

## AI/LLMエージェント関連ツールとしての位置づけ

### 元のSuperCoderとしての技術的評価

SuperCoder自体は技術的に興味深いプロジェクト:
- Rust製エージェントコアで、Ask/Plan/Codingの3モード
- ローカルファースト設計（コードがベンダーバックエンドを経由しない）
- オプショナルなグラフ対応コード検索（tree-sitter + Qdrant + FalkorDB + BM25）
- MCP Server対応、サブエージェント、スキルシステム
- Tauri 2によるクロスプラットフォームデスクトップアプリ

### Godcoderとしての注目価値

**注目に値しない。** 理由:

1. **オリジナリティ皆無**: SuperCoderの丸コピーにリブランドを施しただけ。独自の技術的貢献はVoice設定UIの230行のみ。
2. **Star操作の疑い**: 1日で221 starは、リブランドに対する自然な反応とは考えにくい。同orgの他リポジトリも同パターン。
3. **開発の継続性なし**: 4コミット・単一著者・1日で活動終了。継続的な開発の意思が見えない。
4. **fork表示の回避**: GitHub forkとせず独立リポジトリとして作成し、オリジナルへの貢献還元を行う意図が見えない。

### 注意点

- MITライセンスのためリブランド自体は法的に許容される。
- LICENSEファイルにオリジナルの帰属は記載されている。
- SuperCoderに興味がある場合は、オリジナル（TransformerOptimus/SuperCoder）を直接参照すべき。

## 結論

**注目に値しない。** セキュリティ上の直接的な懸念はないが、TransformerOptimus/SuperCoder（★971）のリブランドコピーであり、独自の技術的貢献はほぼない。Star数の急増はbotまたは購入による操作が強く疑われる。AI/LLMエージェントツールとしての評価はオリジナルのSuperCoderに対して行うべきであり、このリポジトリ自体を追跡する必要はない。
