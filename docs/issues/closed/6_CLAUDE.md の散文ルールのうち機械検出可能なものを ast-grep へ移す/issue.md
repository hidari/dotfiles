---
status: closed
---

# CLAUDE.md の散文ルールのうち機械検出可能なものを ast-grep へ移す

## 背景

CLAUDE.md に散文ルールを追記し続けると肥大化し、検索性と遵守率が下がる。
retrospective-codify の判定表は優先順位を ast-grep > CLAUDE.md > skill とし、
「静的に検出可能なものはプロンプトやドキュメントに書かず必ず ast-grep ルールにする」を第一原則とする。

CLAUDE.md (global / project) の散文ルールを棚卸しし、機械検出可能なものを ast-grep / lint へ移す。
移した分は CLAUDE.md から削除して肥大化を止める。

分別の基準:

- 移す対象: コードや設定の構文レベルで検出できるもの
  (例: 値の二重記述、特定 API の誤用、禁止パターン)。既に `rules/bats-no-bare-double-bracket.yml` などが前例。
- 残す対象: 手順・文脈判断・実機検証を伴うもの
  (例: live smoke を実行せよ、実機で確かめよ、push 後は専用クエリで確認せよ)。これらは静的検出できない。

## タスク

- [x] CLAUDE.md (global + project) の全ルールを機械検出可能 / 手順判断で分類する
- [x] 機械検出可能なものを移行候補としてリスト化する
- [x] 候補を実装する (下記メモの通り ast-grep でなく pre-commit hook + shellcheck へ移行)
- [x] 移したルールを CLAUDE.md から削除する
- [x] lint (ast-grep test / scan + 新 pre-commit hook) が緑であることを確認する

## 実装メモ

3 レンズの独立分類 (workflow) で全ルールを棚卸しした結論: 大半は手続き / 文脈判断 /
意味的検証で機械検出不能ゆえ正当に prose 維持。真の機械検出候補は少数で、しかも
ast-grep でなく pre-commit 標準 hook が適材だった (ast-grep 組込 markdown は inline
文法非対応で bold を表現できず、node --test はリポに使用面ゼロ)。

本 PR で実装した lint:
- end-of-file-fixer: global CLAUDE.md の末尾改行ルールを削除し委譲 (10 ファイル自動修正)
- trailing-whitespace: 行末空白の回帰防止
- shellcheck (.sh): 配線前に現違反 5 件を解消 (bootstrap.sh SC2295 の実バグ含む)

見送り (recommend=false): markdown 強調 / hr / 絵文字 (軟ルール・高 FP・ast-grep 表現不能)、
node --test (使用面ゼロ)、日本語コメント (高 FP)、commit prefix (enum 二重記述 drift)、
README ツリー禁止 (意図ギャップ)。secret / 全角約物は既存の gitleaks / tirith が担保。
警告0 原則は broad な傘のため prose 維持。

## 関連

improve/nvim-contrast-palette の retrospective で Hidari が提起。
ast-grep lint 基盤は sgconfig.yml + rules/ + rule-tests/ に既にあり pre-commit と CI に配線済み。
ast-grep-practice skill を参照。
