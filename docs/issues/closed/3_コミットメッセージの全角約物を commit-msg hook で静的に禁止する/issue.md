---
status: closed
---

# ci: コミットメッセージの全角約物を commit-msg hook で静的に禁止する

## クローズ理由 (2026-07-23)

**前提が消滅したため実装しない。** 禁止対象としていた文字種のうち読点と全角括弧はそもそも tirith を発火させず、ルール自体に技術的根拠が無かった。CLAUDE.md の該当ルールは文字種の禁止から手順の指示 (本文をファイルに書いて `-F` / `--body-file` で渡す) に置き換え済みで、禁止すべき文字種が無くなった以上、機械検査する対象も無い。

tirith 0.3.3 の実測とソース (`terminal.rs` / `confusables.txt`) で確認したこと:

- confusable 集合に含まれるのは句点 `。` / 全角ピリオド `．` / 半角句点 `｡` / 全角ラテン / キリル・ギリシャの lookalike / 数学英数字で、**読点 `、` と全角括弧 `（）` は含まれない**
- 発火条件は文字種ではなく隣接。句点系は同一 word 内に ASCII 英字があるときだけ発火し、日本語に挟まれた句点や行末の句点は通る

本 Issue が挙げた PR #49 の実績 (6 コミットが違反のまま積まれた) は事実だが、それは無害な文字を禁じたルールへの違反だった。本 Issue が字義どおり実装されていた場合、置き換え後のルールに従うコミットが全件 reject される状態になっていた。

構図も反転している。本 Issue は「`git commit -F` は tirith の検査を逃れる抜け道であり穴だ」と論じているが、置き換え後の設計では **`-F` が正規の経路**である。

「静的検査可能なルールは linter に落とす」という原則自体は有効だが、**ルールが正しいことが先**である。間違ったルールを機械化すると間違いが強制力を持つ。

置き換え後の作法は skill `dev-workflow:commit-and-pr-message` が持つ。

以下は起票時の記述をそのまま残す。

## 背景

CLAUDE.md の MUST ルールでコミットメッセージ本文の全角句読点・全角括弧（。、（））を禁止しているが、現行の tirith PreToolUse hook（`home/.claude/hooks/tirith-check.py`）は Bash の argv しか scan しないため、`git commit -F <file>` 経由のメッセージは一切検査されない。日本語コミットの標準手順が -F である以上、このルールには機械検査の穴が常設されている。

実績（PR #49）: feature/nvim-markdown-highlight で 6 コミットが違反のまま積まれ、さらに「全角約物禁止」を明示指示された fixer subagent も 4 コミット中 3 コミットで 、を混入させた。どちらも subagent レビューまで発覚せず、未 push だったため `git filter-branch --msg-filter` で reword して回収できたが、push 後なら履歴書き換えのコストが跳ね上がっていた。

「静的検査可能なルールはプロンプトではなく linter で記述する」（CLAUDE.md MUST）の原則どおり、commit-msg stage の機械検査に落とす。

## タスク

- [ ] 実装方式を決める（pre-commit framework の commit-msg stage hook を第一候補に、素の `.git/hooks/commit-msg` / tirith 側の拡張と比較する）
- [ ] コミットメッセージに全角約物（。、（））が含まれる場合に reject する hook を実装する（対象はメッセージのみ。ファイル本文は tirith 同様に対象外）
- [ ] 違反メッセージで fail し準拠メッセージで pass する bats テストを追加する（negative case 必須）
- [ ] bootstrap の hook 導線に commit-msg stage の install を組み込む（`pre-commit install --hook-type commit-msg` 相当）

## 関連

- PR #49（すり抜け実績と filter-branch による reword 回収の経緯）
- `home/.claude/hooks/tirith-check.py`（argv scan のみで -F のメッセージ本文は見ない）
- `rules/bats-no-bare-double-bracket.yml`（同じ「プロンプトで守れなかったルールを静的ガード化した」前例）
