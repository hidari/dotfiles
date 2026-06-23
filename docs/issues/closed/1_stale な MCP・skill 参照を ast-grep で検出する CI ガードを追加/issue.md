---
status: closed
---

# ci: stale な MCP・skill 参照を ast-grep で検出する CI ガードを追加

## 背景

PR #22 で chrome-devtools を公式 `chrome-devtools-mcp` plugin へハイブリッド移行した際、自作 skill 内に散在していた MCP ツール名・skill/plugin 参照を手作業で stale 修正した:

- `mcp__chrome-devtools__*` → `mcp__plugin_chrome-devtools-mcp_chrome-devtools__*`（plugin 由来の正式名）
- `claude-in-chrome` / `mcp__claude-in-chrome__*` → `superpowers-chrome:browsing`（`use_browser`）
- `git-branch-switcher` の allowed-tools `Git`（実在しないツール名）→ `Bash(git *)`

これらの literal は plugin 名・server 名・tool 名が変わるたびに silent に rot する。現状、変更を検出する仕組みが無い。皮肉にも品質ゲートである `pre-merge-quality-gate` 自身が legacy literal (`mcp__chrome-devtools__navigate_page`) を抱えていた。

CLAUDE.md MUST GLOBAL「静的検査可能なルールはプロンプトではなく、その環境の linter か ast-grep で記述する」に直接合致する課題。

## タスク

- [x] 検出ルールの対象を確定する（最低: (a) legacy un-prefixed `mcp__chrome-devtools__` 形、(b) `home/.claude/skills/*/SKILL.md` の `allowed-tools` にある非実在ツール名 = canonical built-in でも有効な `mcp__plugin_..._...__*` 形でもない bare word）
- [x] ast-grep（YAML 構造を見るなら）か grep（軽量正規表現で足りるなら）かを選定する。`ast-grep-practice` skill の指針に従う
- [x] ルールを実装し、既知の good/bad ケースでテストする（exact 検出 + false positive 抑制）
- [x] `.github/workflows/test.yml` に組み込む（bats / ruff / gitleaks と並ぶ check として）
- [x] 「実在ツール名」をどう判定するか（ソース・オブ・トゥルース）をルールに与える方法を決める

## 関連

- 起点 PR: #22（chrome-devtools 公式 plugin ハイブリッド採用 + stale 参照一掃）
- 関連 skill: `ast-grep-practice`, `pre-merge-quality-gate`
- 関連ルール: CLAUDE.md MUST GLOBAL「静的検査可能なルールは linter か ast-grep で記述する」
