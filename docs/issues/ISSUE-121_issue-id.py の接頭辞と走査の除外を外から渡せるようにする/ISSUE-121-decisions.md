# ISSUE-121 の採否 (2026-11-16 に判断の保存先から写した)

この表は `knowledge_ledger.records` が台帳の判断の保存先から生成する。手で直さない。記号の意味は ISSUE-146-spec.md の判定表が持ち、理由の文面は判断の保存先が持つ。

| 件 | 箇条の冒頭 | 採否 | 判断した側 | 記号 | 反映先 |
| --- | --- | --- | --- | --- | --- |
| K121-001 | 記法の検査 (識別子の数字記法の混入) は未追跡のファイルを見ず、新しい iss… | 保留 | Claude | H3 |  |
| K121-002 | `issue-id.py --check-diff` の2つの形の罠が届いた。`… | 保留 | Claude | H3 |  |
| K121-003 | 外部リポジトリの Issue 番号を `name#N` (owner の無い形)… | 採らない | Claude | R4 |  |
| K121-004 | Issue 識別子の検査 (`issue-id.py` の `GITHUB_RE… | 保留 | Claude | H3 |  |
| K121-005 | 色コードの取り違えは `.svg` だけではない。`--check` を全ツリー… | 保留 | Claude | H3 |  |
| K121-006 | in-repo-issue 同梱の issue-id.py (2026-11-1… | 採らない | Claude | R1 | ~/.claude/skills/in-repo-issue/scripts/issue-id.py |
| K121-007 | 配った issue-id.py の写しの docstring が、配った先のリポ… | 保留 | Claude | H3 |  |
