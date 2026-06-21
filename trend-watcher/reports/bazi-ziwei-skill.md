# dzcmemory-web/bazi-ziwei-skill

> 調査日: 2026-06-21 | Linear: AI-23 | Star: 456 | Fork: 56 | 作成日: 2026-06-13

## 概要

八字（四柱推命）と紫微斗数の排盤・分析を行う AI Agent 向け Skill。[SKILL.md 規格](https://code.claude.com/docs/en/skills)に準拠し、Claude Code / Codex / Cursor / Hermes / OpenClaw 等の Agent にプラグインできる。

排盤（命盤計算）は決定論的アルゴリズム（vendored [Yiqi](https://github.com/fdxuyq/Yiqi-BaZi-ZiWei) + 独自 enrichBazi 補層）で行い、LLM には分析・解釈のみを担当させる設計。LLM が自力で排盤すると日柱・格局が誤る問題を回避している。

## リポジトリ構成

```
calculator/
  run-chart.ts      生辰 → JSON（四柱+紫微+大運）
  dump-text.ts       JSON → 文墨天機風テキスト
  render.ts          JSON + 分析JSON + テンプレート → HTML ポスター
  yiqi-core/         排盤コアアルゴリズム（vendored, MIT）
  bazi-enrich/       格局・旺衰・調候・刑冲合害 補算
prompts/             4種の分析プロンプト（八字独立/紫微独立/綜合印証長文/海報版）
templates/           HTML 海報テンプレート（水墨風）
examples/            サンプル出力
```

- 言語: TypeScript
- 実行依存: `lunar-typescript` (MIT) のみ。Node.js >= 18
- npm install フック（preinstall/postinstall）: なし
- ライセンス: MIT

## セキュリティ評価

### コード安全性: 問題なし

- ネットワーク通信: なし。`fetch`, `http`, `https`, `net`, `XMLHttpRequest` 等の呼び出しゼロ
- `eval` / `exec` / `child_process`: 使用なし
- 難読化・エンコード: なし（`atob`, `btoa`, `Buffer.from`, `fromCharCode` 等ゼロ）
- `process.env` 参照: なし
- ファイル操作: `fs.writeFileSync` のみ（出力ファイル書き込み用、3箇所）
- HTML テンプレート: `<script>` タグなし。純粋な CSS + プレースホルダー置換
- npm install フック: なし
- サプライチェーン: 依存は `lunar-typescript`（MIT, 農暦変換ライブラリ）1つのみ。低リスク
- コミット履歴: 12コミット、すべて機能追加・バグ修正で一貫。不審なコミットなし

### Star 急増の自然性: 不自然（購入の疑い強い）

リポジトリ作成（6/13）からわずか8日で456 star。日別分布:

| 日付 | Star数 |
|------|--------|
| 6/13 | 2 |
| 6/14 | 1 |
| 6/15 | 30 |
| 6/17 | ~101 |
| 6/18 | ~250 |
| 6/19 | ~42 |
| 6/20 | ~19 |
| 6/21 | ~11 |

6/18 に1日で約250 star は極めて不自然。初期 stargazer のプロフィールを確認したところ:

- `susan-lee-ops`: リポジトリ作成と同日（6/13）にアカウント作成、リポ0件、フォロワー0
- `FaxmDolenk`, `AexztoSevenk`, `ZxoeHouay`, `NinaeJsean`, `ChloekjarMay`: すべて 2026-03-29〜30 に作成、ランダム風の命名、フォロワー0〜1

Star 購入サービスの利用が強く疑われる。

## AI/LLM エージェントツールとしての位置づけ

### 注目に値する点

1. **SKILL.md 規格の実用例**: Claude Code の SKILL.md 標準に準拠した完成度の高い Skill 実装。Agent に「生年月日を言うだけ」で命理分析が走るフローが設計されている
2. **LLM と決定論的計算の分離**: 排盤はアルゴリズム、分析は LLM という明確な責務分離。LLM 単体の命理計算精度問題への実践的解法
3. **3モード対応**: 八字独立/紫微独立/綜合印証（交差検証）の3分析モードと、Markdown 長文/HTML 海報の2出力形態
4. **プロンプトエンジニアリング**: 4種の専用プロンプト（合計443行）が同梱。LLM の分析品質を構造化するアプローチ

### 限界・留意点

1. **Star は購入の疑いが強い**: 実際の利用者コミュニティは不明
2. **ドメイン特化**: 中国伝統命理に特化しており、汎用的な AI/LLM ツールではない
3. **上流 Yiqi の Star は2件**: vendored 元の排盤ライブラリ自体は知名度が低い
4. **作者プロフィール**: public_repos=1, followers=3。実績が薄い
5. **占い・娯楽用途**: 免責事項にもある通り、実用的な意思決定ツールではない

## 総合判定

**技術的に面白いが、注目度は人工的。**

SKILL.md 規格に沿った Agent Skill の実装パターンとしては参考になるが、Star 数は購入されたものと見られ、実際のコミュニティ採用・有機的な注目は確認できない。AI/LLM エージェント開発ツールとしての直接的な有用性は低い（ドメイン特化の占い Skill）。

SKILL.md Skill の実装例として軽くウォッチする程度で十分。積極的な追従や導入は不要。
