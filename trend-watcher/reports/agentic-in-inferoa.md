# agentic-in/inferoa

- **URL**: https://github.com/agentic-in/inferoa
- **Stars**: 224 (調査時点)
- **ライセンス**: Apache-2.0
- **言語**: TypeScript (Node.js 24+)
- **初回コミット**: 2026-06-08
- **最終コミット**: 2026-06-18
- **コミット数**: 132
- **主要コントリビュータ**: xunzhuo (128/132 commits, email: xunzhuo@vllm-semantic-router.ai)
- **npm パッケージ**: `inferoa` (v0.14.19, `@dev` dist-tag)
- **Linear チケット**: AI-26

## 概要

Inferoa は **"Inference-native Tokenmaxxing Agent Harness for Loop Engineering"** を名乗るターミナルベースのAIコーディングエージェント。vLLM エコシステムをベースに、LLM推論ループの長期実行・コスト最適化・prefix cache 管理に特化したTUIアプリケーション。

主な機能:
- **Loop Engineering**: `/loop` コマンドによる再帰的な長期タスク実行。目標・検証・エビデンス・リカバリを管理しながら自律的にコード修正を繰り返す
- **Tokenmaxxing**: prompt epoch の安定化、prefix cache 再利用の最大化、コンテキスト圧縮、bounded tool output によるトークンコスト削減
- **Intelligent Routing**: vLLM Semantic Router 経由でコスト・安全性・プライバシー・能力に応じたモデル選択
- **Self-hosted model serving**: vLLM Engine / vLLM Omni のローカル推論エンドポイント対応
- **CodeGraph / RTK 統合**: コードインテリジェンスとリポジトリコンテキスト最適化

## セキュリティ評価

### 悪意のあるコード・難読化: **問題なし**
- `src/` 配下は全て可読な TypeScript。minified / packed / obfuscated ファイルなし
- `eval()`, `new Function()` 等の動的コード実行パターンなし
- `Buffer.from(..., "base64")` の使用は全て正当な用途（API レスポンスのデコード、secret vault の AES-256-GCM 暗号化/復号、画像バイナリ処理）

### インストール/ビルドスクリプト: **問題なし**
- `package.json` に `postinstall` / `preinstall` フックなし
- `Makefile` は `npm run build`, `npm link`, `npm test` 等の標準操作のみ
- GitHub Actions (`npm-publish.yml`) も標準的な build → test → publish フロー

### 依存関係・サプライチェーン: **低リスク**
- runtime 依存は 4 パッケージのみ:
  - `commander` (^14.0.2): 著名な CLI フレームワーク、deps なし
  - `typescript` (^5.9.3): 標準
  - `yaml` (^2.8.1): 著名な YAML パーサー、deps なし
  - `@colbymchenry/codegraph` (0.9.9): コードインテリジェンスツール。npm上で32バージョン公開、MIT ライセンス、deps なし。小規模だが実体のあるパッケージ
- devDependencies は `@types/node` のみ
- 全体として依存ツリーが非常に浅く、サプライチェーンリスクは低い

### ネットワーク通信: **想定内**
- `fetch()` 呼び出しは全てユーザー設定の LLM エンドポイント（vLLM, OpenAI, Anthropic, Gemini 互換 API）への推論リクエストまたは web 検索機能
- 外部への意図しないデータ送信パターンは確認されず
- `child_process` の使用は `spawn`/`execFile` によるローカルコマンド実行（git, RTK, codegraph 等）で妥当

### Star数の急増: **やや不自然**
- 2026-06-08 に初回コミット → 約13日で 224 stars
- コントリビュータは実質1名 (xunzhuo, 97%)。メールドメインが `vllm-semantic-router.ai` で vLLM エコシステムとの関連を示唆
- 外部PRは1件のみ (#55, FAUST-BENCHOU)
- リポジトリの成熟度（132 commits, 62K行のソース, 28K行のテスト, Docusaurus サイト）に対して stars 成長が速い印象はあるが、vLLM コミュニティからの注目であれば説明可能

## 注目に値するか

### 注目ポイント
1. **vLLM エコシステムとの深い統合**: vLLM Engine / Semantic Router / Omni を前提にした設計は珍しい。セルフホスト LLM ユーザー向けのコーディングエージェントとして差別化されている
2. **Tokenmaxxing コンセプト**: prefix cache 再利用率・コンテキスト圧縮・モデルルーティングを「推論コスト最適化」として体系的に扱うアプローチは技術的に興味深い
3. **Loop Engineering**: 長期タスクの再帰実行・検証・エビデンス管理は、Claude Code の `/loop` や Devin の長期タスク実行と類似するが、推論コスト可視化と組み合わせている点が独自
4. **コード品質**: テストカバレッジが広く（80+ テストファイル）、内部設計ドキュメントも充実

### 懸念・限界
1. **実質1人プロジェクト**: 持続性リスクがある
2. **vLLM 依存**: vLLM を使わないユーザーには価値が限定的（ただし外部プロバイダー対応もあり）
3. **新規性が高すぎる**: 初回リリースから約2週間。実運用実績は不明
4. **「Tokenmaxxing」の造語**: マーケティング色が強く、実際の効果は検証が必要

### 総合判断: **注目に値する（ウォッチ推奨）**

vLLM エコシステムに特化したコーディングエージェントという位置づけは独自性がある。セルフホスト LLM のコスト最適化を体系的に扱う設計思想は、自前推論基盤を持つチームにとって参考になる。ただし新規プロジェクトのため、継続的な成長を見守る段階。
