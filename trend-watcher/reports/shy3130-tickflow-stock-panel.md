# shy3130/tickflow-stock-panel

| 項目 | 値 |
|------|-----|
| URL | https://github.com/shy3130/tickflow-stock-panel |
| Star数 | 152 (検知時点) |
| 作成日 | 2026-06-18 |
| ライセンス | MIT |
| 作者 | shy3130 (wangshuai) |
| 調査日 | 2026-06-24 |
| Linear | AI-62 |

## 概要

A株（中国A株市場）向けの**株式スクリーニング + モニタリング + バックテスト**統合プラットフォーム。[TickFlow](https://tickflow.org/) SDKを主なデータソースとして、20種類の組み込み戦略によるスクリーニング、リアルタイム監視・アラート通知、vectorbtベースのバックテスト機能を提供する。オプションでOpenAI互換APIを使った自然言語→戦略コード自動生成機能を持つ。

バックエンドはFastAPI + Polars + DuckDB、フロントエンドはReact 18 + TailwindCSS + ECharts。Docker / デスクトップアプリ（PyWebView + PyInstaller）/ 開発モード（dev.sh）の3形態でデプロイ可能。

## リポジトリ構成

- **backend/** (Python, 約22,800行): FastAPI REST API、戦略エンジン、TickFlow SDK統合、バックテストエンジン、スケジューラ
  - `app/strategy/builtin/` — 20種の組み込み選股戦略（各ファイルがPolars式のfilter/scoring関数）
  - `app/strategy/ai_generator.py` — LLMによる戦略コード生成（AST安全検証付き、154行）
  - `app/tickflow/` — TickFlow SDK ラッパー（クライアント管理、能力探知、レート制限）
  - `app/backtest/` — vectorbt ベースのバックテストエンジン
  - `app/services/` — データ同期、監視、通知アダプタ等
- **frontend/** (TypeScript/React, 約31,400行): ダッシュボード、スクリーナー、バックテスト、モニター、設定等のSPA
- **packaging/** — PyInstaller / Inno Setup によるデスクトップアプリビルド
- **docs/** — 戦略開発ガイド、スクリーンショット
- **.github/workflows/release.yml** — 手動ディスパッチによるマルチプラットフォームデスクトップビルド

## セキュリティ評価

### 悪意のあるコード: 検出なし

- `package.json` に `postinstall` / `preinstall` フック一切なし。
- バックエンドPythonコードのネットワーク通信は以下に限定:
  - TickFlow SDK経由の株式データ取得（`tickflow` PyPIパッケージ）
  - OpenAI互換API呼び出し（AI戦略生成、オプション機能）
  - `tickflow.org/endpoints.json` のエンドポイント一覧取得
- `subprocess` の使用は2箇所のみ:
  - `scripts/bump_version.py` — `git add`（バージョンバンプ用、開発時のみ）
  - `app/services/notify_adapter.py` — OS通知送信（`osascript`/`notify-send`、デスクトップ版のみ）
- `eval()` の使用は1箇所: `ai_generator.py` でのMETA辞書抽出。AST解析済みノードに対して `{"__builtins__": {}}` で実行しており、任意コード実行リスクは低い。

### AI戦略生成のサンドボックス

`ai_generator.py` はLLM生成コードに対してAST解析による安全検証を実施:
- 禁止import: `os`, `sys`, `subprocess`, `socket`, `shutil`, `pathlib`, `http`, `urllib`, `requests`, `httpx`
- 禁止関数: `open`, `exec`, `eval`, `compile`, `__import__`, `globals`, `getattr` 等
- `import polars as pl` のみ許可

ただしホワイトリスト方式ではなくブラックリスト方式のため、未知のモジュール（例: `ctypes`, `importlib`）は通過する可能性がある。

### 依存関係

- **バックエンド**: `fastapi`, `uvicorn`, `polars`, `duckdb`, `pyarrow`, `pandas`, `openai`, `httpx`, `apscheduler`, `tickflow[all]>=0.1.23` 等。いずれもPyPI上の広く使われるパッケージ。
- **フロントエンド**: `react`, `react-dom`, `echarts`, `lightweight-charts`, `@tanstack/react-query`, `framer-motion`, `tailwind-merge` 等。npmの安定パッケージ群。
- **`tickflow` SDK** (PyPI): TickFlow Team公式。v0.1.17〜0.1.24（2026年リリース）。`tickflow.org` ドメインに紐づく。新興データプロバイダだが、SDKコードは公開されておりパッケージ自体に特段の不審点は確認されなかった。
- `package.json` にライフサイクルフックなし。サプライチェーンリスクは低い。

### 難読化: なし

- ソースコードはすべて平文のPython / TypeScript。`dist/` や `*.min.js` 等のバンドル成果物はリポジトリに含まれていない。
- シェルスクリプト（`dev.sh`, `dev.ps1`）も内容は明快。

### 注意点

- デフォルトAI APIエンドポイントが `https://api.alysc.top`（不明なドメイン）。`.env.example` では `https://api.deepseek.com/v1` を推奨しているが、`config.py` のハードコードデフォルトは `alysc.top`。ユーザーが意識せず使う可能性がある。悪意というよりは個人プロキシと推定されるが、注意は要する。

### Star数について

- 初回コミット 2026-06-18、検知時点で約6日間で152 star。
- 作者 shy3130 は QQ メールアドレス（415333856@qq.com）を使用。中国の個人開発者と推定。
- コミッターは主に shy3130 本人（47/54コミット）。他に wshy（同一人物の別名義と推定、メールアドレス一致）と Dallas、Aliang が少数コミット。
- コミット履歴は自然で、機能追加→バグ修正→バージョンバンプの一般的パターン。
- **急激なstar増加だが、6日で152は極端ではない。** TickFlowの公式推薦やSNS拡散の可能性がある（README内にTickFlowの招待コード `V3KDKGXPEA` が含まれている）。明らかな不自然さは確認されなかった。

## AI/LLMエージェント関連ツールとしての位置づけ

### 注目に値しない理由

1. **AI/LLMはオプション機能に過ぎない**: AI戦略生成機能は154行の単一ファイル（`ai_generator.py`）で、コアの株式分析エンジンとは独立。AI APIキー未設定でも全主要機能が動作する。
2. **エージェント自律性なし**: AIは「ユーザーが自然言語で指示 → コード生成」のワンショット呼び出しのみ。自律的なループ、ツール使用、計画・推論のエージェント的動作はない。
3. **本質は量化投資ツール**: Polarsベースの選股戦略エンジン、vectorbtバックテスト、APSchedulerによるデータ同期が中心。AI/LLMエージェント開発ツールやフレームワークではない。
4. **TickFlow SDKの宣伝的側面**: README全体にTickFlowの招待コードリンクが繰り返し登場。TickFlow社（データプロバイダ）のエコシステム拡大を目的とした公式/半公式サンプルアプリの可能性がある。

### 技術的に参考になる点

- Polars式の戦略DSL設計（`META` 辞書 + `filter()` 関数の規約）は、プラグイン可能な分析パイプラインの設計として興味深い。
- LLM生成コードのAST安全検証は、コード生成エージェントのサンドボックス実装の一例として参考になる。

## 自リポジトリ(ai-agent)との関連

- 直接的な関連は薄い。ai-agentの自動化パイプライン（trend-watcher、Claude Code連携）とは異なる領域。
- LLM生成コードのAST検証手法のみ、将来的にai-agentで動的コード生成を行う場合の参考になりうる。

## 結論

**注目に値しない。** セキュリティ上の重大な懸念はないが、これはA株市場向けの量化投資ツールであり、AI/LLMエージェント開発ツールではない。AIはオプションのコード生成機能として存在するのみで、エージェント的な自律性はない。TickFlow SDKのエコシステム宣伝の側面が見られる。trend-watcherの検知はstar数の閾値超過によるもので、AI/LLMエージェント関連としての実質的な注目理由はない。
