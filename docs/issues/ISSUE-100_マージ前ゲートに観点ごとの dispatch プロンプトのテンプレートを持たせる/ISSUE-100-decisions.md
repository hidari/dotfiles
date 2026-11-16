# ISSUE-100 の採否 (2026-11-16 に判断の保存先から写した)

この表は `knowledge_ledger.records` が台帳の判断の保存先から生成する。手で直さない。記号の意味は ISSUE-146-spec.md の判定表が持ち、理由の文面は判断の保存先が持つ。

| 件 | 箇条の冒頭 | 採否 | 判断した側 | 記号 | 反映先 |
| --- | --- | --- | --- | --- | --- |
| K100-001 | feature-dev:code-reviewer の subagent は B… | 保留 | 人 |  |  |
| K100-002 | 並列レビューの各席に、所見が0件でも「何を読んだか」(coverage) を必須… | 採る | 人 |  |  |
| K100-003 | ボーイスカウトの sweep を general-purpose に委ねたところ… | 採らない | Claude | R1 | ~/.claude/skills/pre-merge-quality-gate/SKILL.md |
| K100-004 | 振る舞いを変えないはずのリファクタ (simplify の指摘の反映) の後に、… | 採る | Claude | 14 | agentic-coding-tools の pre-merge-quality-gate/SKILL.md の「Phase 1: 並列でレビュー実行」 |
| K100-005 | 品質ゲートのレーンに「確かめた度合いを書いて返す」ことを求めていたので、1体が「… | 保留 | Claude | H3 |  |
