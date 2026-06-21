# cobusgreyling/loop-engineering

| 項目 | 値 |
|------|-----|
| URL | https://github.com/cobusgreyling/loop-engineering |
| Star数 | 542 (検知時点) |
| 作成日 | 2026-06-09 |
| ライセンス | MIT |
| 作者 | Cobus Greyling |
| 調査日 | 2026-06-21 |
| Linear | AI-22 |

## 概要

「Loop Engineering」は、AIコーディングエージェント(Claude Code, Grok, Codex, Cursor等)を人間が都度プロンプトするのではなく、**エージェントを自律的にプロンプトし続ける"ループ"を設計する**という概念を体系化したリファレンスリポジトリ。

コンセプトの発端はAddy Osmani(Google Chrome DevRel)のエッセイおよびBoris Cherny(Anthropic, Head of Claude Code)の発言で、Cobus Greylingがそれをパターン集・CLIツール・スターターキットとしてまとめたもの。

## リポジトリ構成

- **ドキュメント中心**: 全236ファイル中131個が `.md`。パターン定義、設計チェックリスト、障害モードカタログ、安全ガイド等。
- **CLIツール3種** (TypeScript, 合計約2,064行):
  - `loop-audit`: プロジェクトの"ループ準備度"をスコアリング(L0-L3)。ファイルシステムの読み取りとgit log確認のみ。
  - `loop-init`: パターンに応じたスターターファイルをスキャフォールド。ローカルファイルコピーのみ。
  - `loop-cost`: パターン・ケイデンスからトークン消費を見積もるエスティメータ。純粋計算のみ。
- **パターン7種**: Daily Triage, PR Babysitter, CI Sweeper, Dependency Sweeper, Changelog Drafter, Post-Merge Cleanup, Issue Triage
- **スターター**: Grok / Claude Code / Codex 向けのクローン即実行キット
- **GitHub Actions**: daily-triage, audit, validate-patterns, changelog-drafter等を自リポジトリでdogfooding

## セキュリティ評価

### 悪意のあるコード: 検出なし

- CLIツール3種はすべて `node:fs/promises`, `node:path`, `node:child_process`(git logのみ) の標準ライブラリのみ使用。外部へのネットワーク通信なし。
- `package.json` に `postinstall` / `preinstall` フック一切なし（ルート・各ツールとも）。
- npmパッケージの `files` フィールドで公開範囲を `dist` + `README.md` に限定。

### 依存関係

- ルート: `ajv@^8.17.1`, `yaml@^2.8.0` (devDependencies)
- loop-audit: `typescript`, `@types/node` (devDependencies のみ、ランタイム依存なし)
- loop-init: 同上
- loop-cost: `yaml@^2.8.0` (唯一のランタイム依存)
- いずれも広く使われている安定パッケージ。サプライチェーンリスクは低い。

### 難読化: なし

- ソースコードはすべて平文の TypeScript/JavaScript。`dist/` にはtscの出力のみ。
- シェルスクリプト(`scripts/`)も全4本合計約140行で、内容は明快。

### Star数の急増について

- 初回コミット 2026-06-09、検知時点で約12日間で542 star。
- 著者Cobus Greylingは AI/LLM分野でSubstackブログを持つ既知のコンテンツクリエイター。
- Addy Osmani（Google）のブログ記事からの参照リンクがあり、そこからの流入と推定される。
- コミット履歴は自然（56コミット、dependabotの自動更新、daily-triageの自動コミット含む）。
- **不自然なstar操作の兆候は確認されなかった。**

## AI/LLMエージェント関連ツールとしての位置づけ

### 注目に値する理由

1. **概念の体系化**: AIエージェントの自律ループ設計という新しい領域を、パターン・チェックリスト・障害モード・コスト見積もりまで包括的にまとめた初の実用リファレンス。
2. **ツール横断**: 特定エージェント(Claude Code等)に依存せず、Grok/Claude Code/Codexの3ツールに対応したスターターを提供。
3. **Dogfooding**: リポジトリ自体がdaily-triage, audit, validate-patterns等のループをGitHub Actionsで運用中（STATE.mdに最終実行タイムスタンプあり）。
4. **安全設計の重視**: 段階的ロールアウト(L1報告→L2補助→L3無人)、denylist、予算上限、kill switch等の運用安全策を文書化。
5. **低リスクCLI**: ツールはすべてローカル完結で、認証情報の取得やネットワーク通信は行わない。

### 制約・注意点

- **実行コードではなくリファレンス**: 実際のAIエージェントの実行ランタイムやフレームワークではない。パターンとテンプレートの集合体。
- **新規リポジトリ**: 作成から12日と歴史が浅く、実運用での検証事例はまだ少ない。
- **トークンコスト見積もりの精度**: `loop-cost`の見積もりはパターンごとの固定値ベースで、実測値ではない。

## 自リポジトリ(ai-agent)との関連

- ai-agentの `trend-watcher` や `CLAUDE.md` で実践している「非LLMの定期ポーリング→自動起票」は、loop-engineeringの「Daily Triage (L1)」パターンに概念的に近い。
- loop-engineeringの段階的ロールアウト(L1→L2→L3)の考え方は、ai-agentの今後の自動化拡張の参考になりうる。

## 結論

**注目に値する。** セキュリティ上の懸念なし。AIエージェントの自律ループ設計パターンを体系化した実用リファレンスとして有用。ツール自体は軽量・ローカル完結で安全。Star数の急増はAddy Osmaniブログからの流入が主因と推定され、不自然な操作の兆候なし。
