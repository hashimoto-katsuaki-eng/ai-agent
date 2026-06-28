# LING71671/open-reverselab

| 項目 | 値 |
|------|-----|
| URL | https://github.com/LING71671/open-reverselab |
| Star数 | 227 (検知時点) → 34 (調査時点) |
| 作成日 | 2026-06-17 |
| ライセンス | GPL-3.0-only |
| 作者 | LING71671 |
| 調査日 | 2026-06-28 |
| Linear | AI-78 |

## 概要

「open-reverselab」は、逆向工程（リバースエンジニアリング）のための知識ベース＋MCPツールサーバーを統合したオープンソースプロジェクト。CTF/Web攻撃、APKリバース、PE/Windows解析、暗号・プロトコル解析の4分野を網羅し、AIエージェント（Claude Code、Codex等）が自律的に逆向作業を遂行するための「Agent-native」アーキテクチャを謳っている。

主な構成:
- **知識ベース(KB)**: 197篇のMarkdown技術文書（SQLi/XSS/SSRF/JWT/OAuth/CVE等のWeb攻撃面、APK/DEX解析、PE解析、暗号アルゴリズム識別等）
- **MCPツールサーバー**: FastMCPベースのPythonサーバー（100+ツール定義）。Ghidra無頭分析、DiE/rizin呼び出し、IOC抽出、YARA/Sigma生成等
- **インストールスクリプト**: PowerShellで各ツール（apktool, jadx, Ghidra, x64dbg, sqlmap等）を自動DL・展開
- **攻撃ネットワーク図**: 各分野のMermaid形式の攻撃パス全体図

## リポジトリ構成

- 全530ファイル（`.md` 301, `.py` 68, `.ps1`/`.bat` 16, `.json` 15, HTML/CSS等）
- コミット数: **1** (初回コミットのみ、2026-06-28)
- 著者: LING71671 のみ
- 容量: 約11MB（コード+ドキュメント、バイナリなし）
- CI: GitHub Actions (`release-check.yml`) でlint・healthcheck・pytest・PowerShell構文チェック

ディレクトリ構造:
```
kb/           → 197篇のリバース知識ベース（4ボード: ctf-website/apk-reverse/pe-reverse/general）
tools/        → MCPサーバー、proxy_pool、mitmproxy_capture
scripts/      → 自動化スクリプト（Python/PowerShell）
docs/         → GitHub Pages用静的サイト（llms.txt含む）
templates/    → 分析ノート・ルールテンプレート
tests/        → pytest（kb_router, public_release_check等）
```

## セキュリティ評価

### 悪意のあるコード: 検出なし

- `exec()` の使用: scripts/ 内に `exec()` 呼び出しなし。`subprocess` はローカルツール（Ghidra, rz-bin, diec等）の実行のみ。
- install_tools.ps1: 公式ソース（bitbucket.org/iBotPeaches, github.com/skylot/jadx, github.com/NationalSecurityAgency/ghidra等）からのダウンロードのみ。
- MCP サーバー: ファイルシステム操作とローカルツール呼び出しのみ。外部への情報送信なし。
- `postinstall` / `preinstall` フック: なし。

### 依存関係

- MCP サーバー (`pyproject.toml`): `mcp>=1.2.0,<2`, `pycryptodome>=3.20.0,<4` のみ。
- いずれも広く使われている安定パッケージ。

### 難読化: なし

- ソースコードはすべて平文のPython/PowerShell/Markdown。
- 圧縮・エンコード・難読化されたファイルは確認されなかった。

### プライバシー保護

- `public_release_check.py` が秘密鍵、GitHub token、AWS key、ユーザーパスのリークを自動検出するガードとして機能。
- `PUBLICATION.md` で私的データの公開禁止ルールを明文化。

### Star数の急減について（重要）

- **検知時点: 227 star → 調査時点: 34 star**（約85%減少）。
- リポジトリ作成から約11日で227 starは不自然に高い成長速度。
- その後の大幅減少は、**GitHubによるfake star除去**の可能性が高い。
- コミット履歴が1件のみであることも、オーガニックなコミュニティ成長とは矛盾。
- 同著者の `Open-ClaudeCode` (890 star, 1208 forks) も、Claude Codeのnpmパッケージからの「復元」を謳うリポジトリで、star/fork比率が不自然（通常forkはstarの10-30%程度だが、ここでは136%）。
- **star操作（star購入またはbot利用）の疑いあり。**

## AI/LLMエージェント関連ツールとしての位置づけ

### 技術的に注目できる点

1. **Agent-nativeアーキテクチャ**: `CLAUDE.md → AGENTS.md → AI-USAGE.md → boards/<board>/AI-USAGE.md` というコンテキストチェーンで、AIエージェントが自動的に適切なボードにルーティングされる設計。
2. **MCP統合**: 100+の逆向ツールをMCP (Model Context Protocol) で公開し、Claude CodeやCodexから直接呼び出し可能にする構想。
3. **知識ベースルーター**: 信号（SQLi, JWT, packer等）を検出すると対応する技術文書にルーティングし、攻撃チェーンとMCPツールのマッピングまで提供する設計。
4. **攻撃ネットワーク図**: 線形攻撃チェーンではなく、グラフ構造の攻撃パスをMermaidで可視化。

### 制約・注意点

1. **実質的にドキュメント集**: 197篇のKB記事は充実しているが、MCPツールの多くは外部ツール（Ghidra, x64dbg等）のラッパーであり、それらのツールが事前にインストールされていることが前提。Windows環境前提の記述が多い。
2. **単一コミット・単一著者**: 開発履歴がなく、一度にすべてが投入されている。他のコントリビューターもいない。プライベートリポジトリからの公開版移行と説明されている(`PUBLICATION.md`)。
3. **Star操作の疑い**: 上述の通り。技術的内容の質とは独立に、信頼性に疑問符が付く。
4. **攻撃ツール的側面**: proxy pool、mitmproxy capture、CTF攻撃スクリプト等、攻撃的セキュリティツールとしての側面がある。教育・CTF・合法的ペンテスト目的と明記されているが、悪用可能性はある。
5. **codex-session-patcher**: READMEで参照される[codex-session-patcher](https://github.com/ryfineZ/codex-session-patcher)は同エコシステムのツールで、Codexのプロジェクト設定を自動化するもの。

## 自リポジトリ(ai-agent)との関連

- MCPツールサーバーとしての設計パターン（FastMCP + ローカルツールラッパー）は参考になりうるが、直接的な技術的依存関係はない。
- 逆向・セキュリティ分析の知識ベースとしては内容が充実しているが、ai-agentの主目的（AI/LLMエージェント開発ツールのトレンド監視）とは領域が異なる。

## 結論

**注目度は限定的。Star操作の疑いあり。** 技術的内容（197篇のリバース知識ベース + MCP統合設計）自体は一定の実装努力が認められるが、(1) 検知→調査間でstar数が227→34へ85%急減しておりGitHubによるfake star除去が推定される、(2) 全コンテンツが単一コミットで投入され開発履歴がない、(3) 同著者の別リポジトリもstar/fork比が不自然、という点から、コミュニティの真正な関心によるものとは判断しにくい。セキュリティ上の直接的脅威（マルウェア、データ窃取等）は確認されなかったが、star操作による可視性の人為的増大が疑われるため、注目度の評価は割り引いて見るべき。
