---
status: open
---

# refactor: Claude Code フックの共通基盤を集約する

## 背景

Issue #25 Phase 3a (PR #91) のレビューで、フック周りの共通部分が 3 箇所に分散していることが
分かった。いずれも単体では動くが、片方だけ変えたときに沈黙した失敗になる形の重複である。
Phase 3a のスコープを大きく超えるため別 Issue に分けた。

### 1. PreToolUse プロトコル層の重複

`home/.claude/hooks/tirith-check.py` と `home/.claude/hooks/apm-install-guard.py` で、
次の約 40 行が写経になっている。

- stdin から JSON を読む
- フィールドを snake_case と camelCase の両方で引くヘルパ
- deny の `hookSpecificOutput` JSON を組み立てる
- `PreToolUse` かつ `Bash` かを判定して抜けるゲート
- `tool_input.command` の型と空文字の検査

既に drift が発生している。`handoff-sentinel.py` だけが `ensure_ascii=False` で出力しており、
他 2 つは既定のままだった (`apm-install-guard.py` は PR #91 で揃えたが、揃えるという判断を
毎回 3 箇所で繰り返す構造は残っている)。

共通モジュールを `home/.claude/hooks/` に置けば symlink 経由の配布に乗る。ただし
`scripts/tirith-hook` と `scripts/apm-install-guard` という独立した uv プロジェクト 2 本の
lint / 型検査の対象と、`.pre-commit-config.yaml` の `files:` 正規表現の両方へ追加が要る。
この追加コストは項目 2 を先に片付けると消える。

### 2. uv ハーネスの分散

`scripts/tirith-hook` / `scripts/handoff-sentinel` / `scripts/apm-install-guard` の
`pyproject.toml` は、名前と説明を除いてほぼ同一である (ruff / mypy / pytest の設定、
zero runtime deps、`package = false` まで一致)。その結果:

- CI job が 3 本。1 本あたり実作業 2 秒に対して job セットアップが 100 秒以上
- lockfile が 3 本。`.venv` が 3 つで計 300MB
- `.pre-commit-config.yaml` のエントリが 12 個

しかも lockfile が食い違っている。`apm-install-guard` は ruff 0.16.1 / mypy 2.3.0、
`tirith-hook` と `handoff-sentinel` は ruff 0.15.20 / mypy 2.1.0。同じ
`home/.claude/hooks/` ディレクトリのファイルが別バージョンで lint されている状態。

`scripts/claude-hooks/` のような 1 プロジェクトへ集約し、`tests/test_<hook>.py` を並べる形に
すれば CI job 1 本 / lockfile 1 本 / venv 1 つ / pre-commit 4 エントリになる。

### 3. 必須フック検査がイベント固定

`scripts/config-guard/src/config_guard/settings_invariants.py` の
`_REQUIRED_PRETOOLUSE_HOOKS` と `_pretooluse_commands` は `PreToolUse` 1 イベントに
固定されている。`SessionStart` 系 (`handoff-sentinel.py` は session-handoff skill の
発動経路そのもので、配線が外れると skill が沈黙する) を pin したくなった時点で、
兄弟関数の複製を要求する形になっている。

データ形を `{イベント名: (フック名, ...)}` にしてコレクタをイベント引数付きの 1 関数へ
まとめれば、実装コストはほぼ変わらずに一般化できる。`handoff-sentinel` を必須に入れるかは
別判断 (個人ツールであり security guard ではない) として据え置いてよい。

## タスク

- [ ] 3 つの uv ハーネスを `scripts/claude-hooks/` へ集約する (CI job / lockfile / venv / pre-commit エントリを 1 系統にまとめ、ruff と mypy のバージョンを揃える)
- [ ] PreToolUse プロトコル層を共有モジュールへ切り出し、`tirith-check.py` と `apm-install-guard.py` から使う
- [ ] 共通化後に `tirith-check.py` の変異注入を再実施する (security guard なので、共通化で pin が死んでいないことを確かめる)
- [ ] `settings_invariants` の必須フック検査をイベント軸で一般化する
- [ ] 全フックの JSON 出力の `ensure_ascii` 方針を 1 箇所で決める

## 関連

- [Issue #25: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する](../25_skill%20と%20plugin%20を新規%20PUBLIC%20リポジトリへ集約し%20apm%20配布へ移行する/issue.md)
- PR #91 のレビューで検出 (Reuse / Efficiency / Altitude の 3 観点から独立に同じ箇所が挙がった)
