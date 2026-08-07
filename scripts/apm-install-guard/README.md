# apm-install-guard

`home/.claude/hooks/apm-install-guard.py`（Claude Code の PreToolUse/Bash フック）の単体/統合テスト。

フック本体は `~/.claude/hooks` への symlink 対象なので `home/.claude/hooks/` に置く必要があり、
このディレクトリにはテストだけを置く（本体ソースは持たない）。テストはフックを subprocess 起動し、
実 git リポジトリを一時ディレクトリに作って clean / dirty の各分岐を実環境同等で検証する
(モック不使用)。

対象コマンド・許可する例外・無効化の環境変数はいずれも本体
`home/.claude/hooks/apm-install-guard.py` の定数が真実源なので、ここには再掲しない
(散文と定義の二重管理は CI が捕捉できない形で drift する)。設計の背景は本体の docstring にある。

ガードは 2 層で、こちらは手打ちとエージェント経由を塞ぐ。bootstrap 経由の自動実行は
`bootstrap.sh` の `apm_install_blockers` が塞ぐ。プロセスが別なので実装は共有していない。

```bash
# テスト
uv run --directory scripts/apm-install-guard pytest -q

# lint / format / 型 (本体ソースは repo ルート相対で対象に含める。config は明示する)
uv run --directory scripts/apm-install-guard ruff check --config pyproject.toml ../../home/.claude/hooks/apm-install-guard.py tests
uv run --directory scripts/apm-install-guard ruff format --check --config pyproject.toml ../../home/.claude/hooks/apm-install-guard.py tests
uv run --directory scripts/apm-install-guard mypy --config-file pyproject.toml ../../home/.claude/hooks/apm-install-guard.py tests
```
