# psinetron/echoes-vault-opencode

| 項目 | 値 |
|------|-----|
| URL | https://github.com/psinetron/echoes-vault-opencode |
| Star数 | 187 (検知時点) |
| 作成日 | 2026-06-16 |
| ライセンス | MIT |
| 作者 | psinetron (Fail) / npm: slybeaver |
| 調査日 | 2026-06-24 |
| Linear | AI-65 |

## 概要

EchoesVaultは、[OpenCode](https://opencode.ai)（sst/opencode、旧Serverless Stack チームが開発するオープンソースAIコーディングエージェント）向けの永続メモリプラグイン。AIコーディングセッション間でコンテキストを保持するため、プロジェクトリポジトリ内にObsidian互換のMarkdownベースのナレッジベース（`EchoesVault/`ディレクトリ）を作成・管理する。

主な機能:
- **セッション復元**: `/echoes-start`で直近3日分のデイリーログとインデックスを読み込み、前回の作業状態を復元
- **作業記録**: セッション中にAIが自律的に中間メモ・設計判断をデイリーログに記録
- **知識管理**: ADR（Architectural Decision Record）スタイルのページ作成・更新・検索
- **セッション終了処理**: `/echoes-end`でセッションの成果を要約・保存

## リポジトリ構成

- **単一ファイル構成**: ソースコードは `index.ts` 1ファイル（538行）のみ。
- **ファイル一覧**: `index.ts`, `package.json`, `tsconfig.json`, `LICENSE`, `README.md`, `.gitignore`, `.npmignore`, `images/EchoesVault.png`（ロゴ画像）
- **npmパッケージ公開**: `echoes-vault-opencode@1.0.4`。`files`フィールドで`index.ts`のみに限定（published fileCount: 4）。
- **コミット履歴**: 全6コミット、すべて同一著者（Fail <psinetron@mail.ru>）による同日（2026-06-16）のもの。npmも同日に9バージョン（0.0.1〜1.0.4）を公開。

## セキュリティ評価

### 悪意のあるコード: 検出なし

- 使用モジュールは `node:fs/promises` と `node:path` の標準ライブラリのみ。外部へのネットワーク通信なし。
- `eval`、`Function()`、`child_process`、`process.env` 等の危険なAPIの使用なし。
- すべてのファイル操作はローカルの `EchoesVault/` ディレクトリに限定。
- パストラバーサル対策あり: `sanitizeFilename()`で `..` と `/\` を除去。

### 依存関係

- ランタイム依存: `@opencode-ai/plugin` (`>=1.16.0`) — OpenCode公式プラグインSDK（npmでGitHub Actions OIDCから署名付き公開、maintainers: adamelmore, thdxr = sst/opencode チーム）。
- devDependencies: `typescript@^5.8.0`, `@types/node@^22.0.0`
- **`postinstall` / `preinstall` フック: 全バージョン(0.0.1〜1.0.4)になし。**
- サプライチェーンリスクは低い。

### 難読化: なし

- ソースコードはすべて平文TypeScript。ビルド済み`dist/`は `.npmignore` で除外されており、npm公開時もソースがそのまま含まれる。

### Star数の急増について

- 初回コミット 2026-06-16、検知時点で約8日間で187 star。
- 著者psinetronは同じnpmアカウント(slybeaver)で `psinetron-opencode-visualizer` も公開しており、OpenCodeエコシステムで複数のプラグインを開発している。
- GitHubの著者名 "Fail" とメール `psinetron@mail.ru`、npm側は `slybeaver` / `shahmayev@gmail.com` — 同一人物の別アカウントと推定。
- Hacker Newsや明確な外部メディアからのバズは確認できなかった。
- npm週間ダウンロード数: 初日1,193件（バージョン反復公開によるCI/テスト起因と推定）、以降は10〜36件/日に低下（直近1週間合計: 98件）。
- **187 starの伸びに対してnpmダウンロードが極端に少ない（週98件）**。OpenCodeプラグインとしてはニッチなため必ずしも不自然ではないが、star数とダウンロード数の乖離は留意すべき点。star購入等の明確な証拠はないが、GitHub API制限で詳細なstarタイムラインは確認できなかった。

## AI/LLMエージェント関連ツールとしての位置づけ

### 注目に値する理由

1. **エージェントの永続メモリ問題への解決策**: AIコーディングエージェントのセッション間コンテキスト喪失は実用上の大きな課題。ファイルベースのシンプルなアプローチでこれを解決する試み。
2. **OpenCodeエコシステム**: OpenCode（sst/opencode）はClaude Code・Codex等と並ぶオープンソースのAIコーディングエージェントとして成長中。そのプラグインエコシステムへの参加。
3. **Obsidian互換**: ナレッジベースがObsidianでそのまま閲覧・検索可能な設計は、AI生成ドキュメントの人間によるレビューを容易にする。
4. **軽量・安全**: 538行の単一ファイル、外部通信なし、ローカル完結。導入リスクが極めて低い。
5. **Google OKF準拠を謳う**: README上でGoogle Open Knowledge Format準拠と主張（ただしOKF自体の認知度は低く、実質的にはYAML frontmatter + Markdown）。

### 制約・注意点

- **OpenCode専用**: `@opencode-ai/plugin` APIに依存しており、Claude Code・Cursor・Codex等の他のAIコーディングツールでは使用不可。汎用メモリソリューションではない。
- **新規リポジトリ**: 作成から8日、全6コミット。まだ初期段階で実運用での検証事例は確認できない。
- **スケーラビリティ**: 200ページ超でRAG移行を推奨する `/echoes-status` コマンドを内蔵しているが、現状はインデックス全文読み込み方式で、大規模プロジェクトではコンテキストウィンドウを圧迫する可能性がある。
- **概念としては既知**: AIエージェントの永続メモリ（.claude, CLAUDE.md, Cursor rules等）は各ツールが独自に実装しており、EchoesVaultの新規性はObsidian互換のフォーマットと構造化されたワークフロー（init/start/end）にある。

## 自リポジトリ(ai-agent)との関連

- ai-agentの `CLAUDE.md` が果たしている「セッション間のコンテキスト引き継ぎ」と同じ課題領域。EchoesVaultはこれをより構造化・自動化したもの。
- OpenCode専用であるため直接の導入は不可だが、デイリーログ + インデックス + ADRスタイルのページという構成パターンは、ai-agentの知識管理拡張の参考になりうる。

## 結論

**やや注目に値する。** セキュリティ上の懸念なし。AIコーディングエージェントの永続メモリという実用的な課題に対するシンプルなソリューション。ただしOpenCode専用のニッチなプラグインであり、汎用性は低い。Star数（187）に対してnpmダウンロード（週98件）が少なく、コミュニティでの実際の採用度は限定的と推測される。概念としては既知の領域だが、Obsidian互換の構造化アプローチは一つの参考になる。
