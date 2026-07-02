# tirith-hook

`home/.claude/hooks/tirith-check.py`（Claude Code の PreToolUse/Bash フック）の単体/統合テスト。

フック本体は `~/.claude/hooks` への symlink 対象なので `home/.claude/hooks/` に置く必要があり、
このディレクトリにはテストだけを置く（本体ソースは持たない）。テストはフックを subprocess 起動し、
`TIRITH_BIN` に偽 tirith スクリプトを差し替えて exit code 0/1/2 の各分岐を実環境同等で検証する
(モック不使用)。

```bash
# テスト
uv run --directory scripts/tirith-hook pytest -q

# lint / format / 型 (本体ソースは repo ルート相対で対象に含める。config は明示する)
uv run --directory scripts/tirith-hook ruff check --config pyproject.toml ../../home/.claude/hooks/tirith-check.py tests
uv run --directory scripts/tirith-hook ruff format --check --config pyproject.toml ../../home/.claude/hooks/tirith-check.py tests
uv run --directory scripts/tirith-hook mypy --config-file pyproject.toml ../../home/.claude/hooks/tirith-check.py tests
```
