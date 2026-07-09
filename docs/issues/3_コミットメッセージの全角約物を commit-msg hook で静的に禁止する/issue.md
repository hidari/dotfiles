---
status: open
---

# ci: コミットメッセージの全角約物を commit-msg hook で静的に禁止する

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
