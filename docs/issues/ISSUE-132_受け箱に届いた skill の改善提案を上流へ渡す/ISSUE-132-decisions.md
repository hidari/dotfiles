# ISSUE-132 の採否 (2026-11-16 に判断の保存先から写した)

この表は `knowledge_ledger.records` が台帳の判断の保存先から生成する。手で直さない。記号の意味は ISSUE-146-spec.md の判定表が持ち、理由の文面は判断の保存先が持つ。

| 件 | 箇条の冒頭 | 採否 | 判断した側 | 記号 | 反映先 |
| --- | --- | --- | --- | --- | --- |
| K132-001 | 2026-11-10の仕分けで、別のリポジトリから、`gh pr merge -… | 採らない | Claude | R5 |  |
| K132-002 | 報告 (実測): 同梱の `task-brief` は見出しの形を決め打ちしてい… | 保留 | Claude | H3 |  |
| K132-003 | 上の task-brief の件の報告者の提案は2つある。日本語で plan を… | 保留 | Claude | M | K132-002 に統合 |
| K132-004 | 報告 (実測): 見た目の案 (アイコン、表記、OG 画像のレイアウト) を並べ… | 採らない | Claude | R4 |  |
| K132-005 | justfile の `*args` を `{{ args }}` で展開すると… | 採る | 人 |  |  |
| K132-006 | 前回のゲートが CI や別のレビューと並行で走っていた場合、その指摘を直して積ん… | 採らない | Claude | R1 | ~/.claude/skills/pre-merge-quality-gate/SKILL.md |
| K132-007 | push の直後で新しい run が pending のとき、`gh pr ch… | 保留 | Claude | H3 |  |
| K132-008 | 2026-11-11の仕分けで、別のリポジトリから届いた。ゲートを当て直すときに… | 採らない | Claude | R4 |  |
| K132-009 | 2026-11-11の仕分けで、別のリポジトリから届いた。「ゲートが見た SHA… | 採らない | Claude | R1 | ~/.claude/skills/pre-merge-quality-gate/SKILL.md |
| K132-010 | pre-merge-quality-gate の Phase 3 の実ブラウザ確… | 採らない | Claude | R1 | ~/.claude/skills/pre-merge-quality-gate/SKILL.md |
| K132-011 | Workflow の script で、バッククォートのテンプレート文字列の中に… | 保留 | Claude | H3 |  |
| K132-012 | 報告 (実測): pre-merge-quality-gate の Boy Sc… | 保留 | Claude | M | K132-013 に統合 |
| K132-013 | 差分が約1.5万行・150ファイルの PR のマージ前ゲートで、コードレビューを… | 保留 | Claude | H3 |  |
| K132-014 | simplify の Reuse・Simplification・Altitude… | 保留 | Claude | H3 |  |
| K132-015 | 2026-11-13の仕分けで、別のリポジトリから届いた。同梱の `task-b… | 保留 | Claude | H3 |  |
| K132-016 | 2026-11-13の仕分けで、別のリポジトリから CSS の抑止の書き方の報告… | 保留 | Claude | H3 |  |
| K132-017 | 重点の画面を確実に探索させるため、committed の profile を編集… | 採らない | Claude | R4 |  |
| K132-018 | agent-browser の `set credentials` は HTTP… | 採らない | Claude | R1 | ~/.claude/skills/web-monkey-qa/agents/monkey-explorer-agent.md |
| K132-019 | explorer が `agent-browser network reques… | 採らない | Claude | R1 | ~/.claude/skills/web-monkey-qa/agents/monkey-explorer-agent.md |
| K132-020 | 並列の explorer が同じ scratchpad を共有し、同じファイル名… | 採らない | Claude | R1 | ~/.claude/skills/web-monkey-qa/commands/monkey-qa.md |
| K132-021 | agent-browser のブラウザが `press Escape` の直後な… | 保留 | Claude | H3 |  |
| K132-022 | 報告 (実測): in-repo Issue の起票の前の重複の検索で、skil… | 保留 | Claude | H3 |  |
| K132-023 | 報告者の提案 (実測): A.0 の検索のコマンドを、C.3 と同じく `fin… | 保留 | Claude | M | K132-022 に統合 |
| K132-024 | 長いゲート (20〜30分) の前に並列レビューを先に回し、修正を入れてから最終… | 保留 | Claude | H3 |  |
| K132-025 | 2026-11-15の仕分けで、別のリポジトリから届いた。報告者の提案: ast… | 保留 | Claude | H3 |  |
| K132-026 | 2026-11-15の仕分けで、別のリポジトリから届いた。web-monkey-… | 保留 | Claude | H3 |  |
| K132-027 | 2026-11-15の仕分けで、別のリポジトリから届いた。macos-vm-ve… | 保留 | Claude | H3 |  |
| K132-028 | 2026-11-15の仕分けで、別のリポジトリから届いた。報告者の提案: jus… | 保留 | Claude | H3 |  |
| K132-029 | 2026-11-15の仕分けで、別のリポジトリから同じテンプレート文字列の別の壊… | 保留 | Claude | H3 |  |
| K132-030 | 2026-11-16の仕分けで、別のリポジトリから届いた。差分の大半が機械生成の… | 保留 | Claude | H3 |  |
