# Johell1NS/browser-search

| 項目 | 値 |
|------|-----|
| URL | https://github.com/Johell1NS/browser-search |
| Star数 | 174 (検知時点) |
| 作成日 | 2026-06-22 |
| ライセンス | MIT |
| 作者 | Alessio (Johell1NS) |
| 調査日 | 2026-06-26 |
| Linear | AI-71 |

## 概要

browser-searchは、AIコーディングエージェント（OpenCode, Claude Code, Cursor等）に「Web検索とブラウジング能力」を付与するための**SKILLファイル**（指示セット）。3つのオープンソースツールをオーケストレーションし、エージェントが自律的にWeb情報を取得できるようにする。

- **SearXNG**: メタ検索エンジン（Docker, localhost:8080）で複数ソースを同時検索
- **Camofox**: REST APIベースのFirefoxブラウザ（Docker, localhost:9377）で通常サイトを閲覧
- **CloakBrowser**: ステルスChromium（npm）でCloudflare/Akamai等のbot対策を回避

典型的なフロー: SearXNGで検索 → Camofoxで結果ページを閲覧 → ブロックされたらCloakBrowserにエスカレーション。

## リポジトリ構成

- **ファイル数**: 28ファイル（`.git`除く）
- **実行コード**: JavaScript 3ファイル（`cloak-fetch.mjs`, `cloak-script.mjs`, `challenges.mjs`）+ シェルスクリプト2本（`setup.sh`, `check.sh`）
- **ドキュメント**: `SKILL.md`（349行、エージェント向け完全指示書）、`README.md`（13.7KB）、i18n翻訳12言語
- **その他**: `Readability.js`（Mozilla製、Apacheライセンス、2,786行）、ロゴ画像3点、Docker設定ドキュメント

### 依存関係（package.json）

```json
{
  "cloakbrowser": "^0.3.31",
  "playwright-core": "^1.60.0"
}
```

ランタイム依存はこの2つのみ。devDependenciesなし。

## セキュリティ評価

### 悪意のあるコード: 検出なし

- `cloak-fetch.mjs`（約250行）: CloakBrowserの`launch()`を呼び出してURLを取得するだけ。ネットワーク通信はユーザーが指定したURLのみ。
- `cloak-script.mjs`（約130行）: ユーザーが渡したPlaywrightスクリプトを実行するラッパー。
- `challenges.mjs`（約180行）: Cloudflare/Akamai等のチャレンジページをRegExpで検出するロジック。純粋な文字列マッチング。
- `setup.sh`: `npm install` + CloakBrowserバイナリの確認のみ。
- `check.sh`: Docker/SearXNG/Camofox/CloakBrowserのヘルスチェック。読み取りのみ。
- `package.json`に`postinstall`/`preinstall`フックなし。

### 依存関係

- **cloakbrowser** (^0.3.31): CloakHQ/CloakBrowser（GitHub 27K stars, npm 週45.2Kダウンロード, MIT）。ステルスChromiumブラウザ。広く使われている正規パッケージ。
- **playwright-core** (^1.60.0): Microsoft公式のブラウザ自動化ライブラリ。
- **Readability.js**: Mozilla製のコンテンツ抽出ライブラリ（Apache 2.0）。ローカルファイルとして同梱。

サプライチェーンリスクは低い。

### 難読化: なし

ソースコードはすべて平文のJavaScript/シェルスクリプト。minifyや難読化なし。

### Star数の急増について

- 初回コミット 2026-06-22、検知時点（約4日後）で174 star。
- 著者Johell1NSはGitHubフォロワー0人、公開リポジトリ2つ（うち1つはStepMania関連で17 star）。
- **4日間で174 starは、フォロワーゼロの無名アカウントとしては不自然に急峻。** ただし以下の事情も考慮:
  - 参照先のCloakBrowser (27K stars) やCamofox (7.2K stars) はAI/スクレイピング界隈で注目度が高く、それらのコミュニティからの流入の可能性がある。
  - OpenCode/Claude Code等のAIエージェントツール向けSKILLという新しいカテゴリは関心を集めやすい。
  - 2日間で12言語の翻訳READMEを追加しており、国際的な露出を意図したマーケティング施策が見える（AI生成と推定）。
- **star操作の確証はないが、フォロワーゼロ→174 starの増加速度は通常より高い。注意を要する。**

## AI/LLMエージェント関連ツールとしての位置づけ

### 注目に値する点

1. **実用的なニッチ**: AIエージェントの「Web検索＋ブラウジング」を自己ホスト・無料・無制限で実現する構成をパッケージ化。API課金型サービス（Tavily, Perplexity API等）の代替として一定の需要がある。
2. **エスカレーション設計**: SearXNG → Camofox → CloakBrowserという段階的なツール選択ロジックをSKILLファイルに記述し、エージェントが自律判断する設計。
3. **軽量**: 実行コードは合計約560行（JS）+ シェルスクリプト約200行。主にドキュメントとオーケストレーション指示。
4. **安全**: スクリプト自体はローカル完結で、認証情報の収集やファイル書き込み（スクリーンショット以外）を行わない。

### 制約・注意点

1. **コードよりドキュメント**: 実質的にSKILLファイル（AIエージェントへの指示書）とCloakBrowserの薄いラッパースクリプトの集合体。独自のロジックやアルゴリズムは少ない。
2. **外部ツールへの完全依存**: SearXNG, Camofox, CloakBrowserの3つすべてが外部プロジェクト。browser-search自体の付加価値はオーケストレーション指示のみ。
3. **極めて新しい**: 作成から4日。実運用実績やコミュニティのフィードバックはまだない。
4. **Star数の信頼性に疑問**: フォロワーゼロの新規アカウントで急増しており、有機的な成長か判断しがたい。
5. **「Anti-hallucination by design」は誇大**: SKILL.mdに「検索してから回答せよ」と書いているだけで、技術的な幻覚防止メカニズムではない。

## 自リポジトリ(ai-agent)との関連

- ai-agentのDevinセッションではブラウザ機能が標準装備されているため、browser-searchのSKILL構成を直接採用する必要性は低い。
- ただし、SearXNG + Camofox + CloakBrowserというオープンソースのWeb検索スタックの組み合わせは、非Devin環境でのAIエージェント構築時の参考になりうる。

## 結論

**やや注目に値するが、注意を要する。** セキュリティ上の直接的な脅威は検出されなかった。AIエージェント向けのWeb検索+ブラウジングSKILLとしてのコンセプトは実用的だが、本体のコード量は少なく、外部ツールの組み合わせ指示書としての位置づけ。Star数の急増（フォロワー0人→4日で174 star）は有機的成長とは断定しがたく、star操作の可能性も排除できない。今後の成長パターンとコミュニティ形成の推移を見て再評価が望ましい。
