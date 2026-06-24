# Trend2Video-Pro

| 項目 | 値 |
|---|---|
| リポジトリ | [2417467487-hub/Trend2Video-Pro](https://github.com/2417467487-hub/Trend2Video-Pro) |
| Star数 | 211 |
| 作成日 | 2026-06-08 |
| ライセンス | MIT |
| 言語 | Python (3,168 行) |
| 調査日 | 2026-06-21 |
| Linear Issue | AI-27 |

## 概要

トレンド情報を入力すると、ショート動画の企画・脚本・映像・サムネイル・字幕・品質レポートをまとめた「パブリッシュパッケージ」を一括生成するエージェントフレームワーク。CLI / FastAPI / Streamlit UI の3つのインターフェースを持ち、LLM未設定時はモックモードで全パイプラインが動作する。

### エージェントパイプライン

```
Trend Scout → Trend Analyst → Creator Strategy → Script Writer
→ Fact Checker → Storyboard → Video Producer → Quality Reviewer
→ Publish Package
```

各エージェントは `src/agents/` 配下のラッパーで、コアロジック（スコアリング、LLMクライアント、MoviePy合成、edge-tts TTS等）を呼び出す薄い委譲層。オーケストレータ (`orchestrator.py`) が順次実行する。

### 主な技術スタック

- FastAPI (APIサーバ), Streamlit (実行コンソール)
- MoviePy (動画合成), Pillow (サムネイル/シーンカード生成)
- edge-tts (テキスト音声合成)
- Playwright (Webページスクリーンショット)
- SQLAlchemy + SQLite (トレンド・予測・生成履歴の永続化)
- LLMクライアント: OpenAI / DeepSeek / Qwen 対応、デフォルトはモック

### トレンドソース

- GitHub Trending (HTMLスクレイピング)
- Hacker News Algolia API
- Product Hunt GraphQL API (トークン要)

## セキュリティ調査結果

### 悪意のあるコード: 検出なし

- `eval`, `exec`, `subprocess`, `os.system`, `pickle`, `marshal`, `base64.b64decode` 等の危険なパターンは未使用
- 難読化されたコード・エンコード済みペイロードなし
- 外部通信先は既知の公開API (GitHub, HN Algolia, Product Hunt, OpenAI, DeepSeek, Qwen) のみ
- Chrome拡張は `localhost:8000` のみに通信、外部送信なし
- GitHub Actionsワークフローは `actions/checkout@v4` + `actions/setup-python@v5` + pytest のみ、安全

### サプライチェーンリスク: 低

`requirements.txt` は14パッケージ、すべて広く使われているもの (fastapi, streamlit, moviepy, pillow, requests, beautifulsoup4, playwright, edge-tts, numpy, pydantic, sqlalchemy, python-dotenv, uvicorn, pytest)。未知・マイナーなパッケージなし。バージョン指定は `>=` の下限のみで上限なし（ベストプラクティスではないが、悪意ではない）。

### インストール/ビルドスクリプト: 安全

`setup.py`, `Makefile`, シェルスクリプト等は存在しない。`pip install -r requirements.txt` のみ。

## Star数の急増: 不自然（購入の可能性が高い）

### 証拠

1. **アカウント作成日: 2026-06-02** — 調査時点で19日しか経過していない新規アカウント
2. **フォロワー1人 / フォロー0人** — 211 starに対して極端に少ない
3. **公開リポジトリ2つ** のみ、もう一方 (`WorldCupROI`) も287 star
4. **Stargazer分析**: 最初の30件中29件が **2026-06-11 07:13〜07:35 UTC の22分間** に集中。以降も同日07:35〜07:57に同ペース（約45秒間隔）で継続
5. **Starしたアカウント名**: `Wlkmrfmslk`, `ercdklewdweww`, `wejdpjkjewpjr`, `frehdhfhfjjy`, `dfgcxrgxdfrs` 等、ランダム文字列のボットアカウントが大半
6. コミット作者は単一人物 (`Jiayi LU <2417467487@qq.com>`)、外部コントリビューションなし

**結論: Star数は購入によるものとほぼ断定できる。**

## AI/LLMエージェントツールとしての評価

### 注目に値するか: いいえ

#### ポジティブな点

- マルチエージェントパイプラインの設計自体は教育的で、トレンド収集→分析→コンテンツ生成→品質管理→パッケージ出力という一気通貫のワークフロー思想は参考になる
- モックモードでAPI Key不要で動作する設計は、デモ/学習用途に適している
- コードは読みやすく、構造化されている

#### ネガティブな点

- **Star購入による注目度水増し**: 信頼性の根本的な問題
- **エージェント層が極めて薄い**: 各 `*_agent.py` は既存のスコアリング/生成関数を呼ぶだけの1関数ラッパー。実質的なエージェント的振る舞い（計画、自律判断、ツール選択、リトライ等）はない
- **LLM統合が最小限**: `LLMClient` はJSONを返すだけの薄いHTTPクライアント。プロンプト設計・構造化出力・エラーハンドリング等のエージェント的要素なし
- **スコアリングはすべてハードコード**: トレンドスコア、バイラル予測、クリエイターフィットすべてがルールベースの固定重み計算
- **動画生成は画像スライドショー**: MoviePyでテキストカード画像を連結しているだけで、実質的な動画生成AI機能はない
- **外部コミュニティ・コントリビューションなし**: issue 0件、PR 0件、フォーク5件（うち実質利用は不明）
- 類似の（より成熟した）OSSが存在する領域

### 位置づけ

「AIエージェントフレームワーク」と称しているが、実態はルールベースのパイプラインスクリプトにLLMのオプショナルな呼び出しを付けたもの。エージェント的な自律性・判断・ツール利用はほぼない。README/UIの体裁は整っているが、中身の技術的深さは浅い。Star購入の事実と合わせ、ポートフォリオ目的で見栄えを重視したプロジェクトの可能性が高い。

## 総合判断

**注目不要。** コード自体に悪意はないが、Star購入による信頼性毀損と、「エージェントフレームワーク」としての技術的実質の薄さから、追跡・参考にする価値は低い。
