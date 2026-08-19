# claude-hooks

`home/.claude/hooks/` 配下の Claude Code フックのテストハーネス。

フック本体は `~/.claude/hooks` への symlink 対象なので `home/.claude/hooks/` に置く必要があり、
このディレクトリにはテストだけを置く（本体ソースは持たない）。Python フックのテストは `tests/` の
ファイル名が示す（`.sh` フックは shellcheck が見るので pytest の対象外）。各フックの設計・契約・
環境変数はいずれも本体の docstring が真実源なので、ここには再掲しない（散文と定義の二重管理は
CI が捕捉できない形で drift する）。

Python フックのテストはいずれも本体を subprocess 起動する黒箱テストで、モックは使わない。偽の
外部コマンドや実 git リポジトリを一時ディレクトリに作り、各分岐を実環境同等で再現する。

lint と型検査は `home/.claude/hooks/` をディレクトリごと渡す。フックを増やしても検査対象は自動で
広がるため、フック名を列挙する場所を持たない。

## apm-install-guard のガードは 2 層ある

フックが塞ぐのは手打ちとエージェント経由で、bootstrap 経由の自動実行は `bootstrap.sh` の
`apm_install_blockers` が塞ぐ。プロセスが別なので実装は共有していない。

## コマンド

```bash
# テスト
uv run --directory scripts/claude-hooks pytest -q

# lint / format / 型 (本体は repo ルート相対で対象に含める。config は明示する)
uv run --directory scripts/claude-hooks ruff check --config pyproject.toml ../../home/.claude/hooks tests
uv run --directory scripts/claude-hooks ruff format --check --config pyproject.toml ../../home/.claude/hooks tests
uv run --directory scripts/claude-hooks mypy --config-file pyproject.toml ../../home/.claude/hooks tests
```
