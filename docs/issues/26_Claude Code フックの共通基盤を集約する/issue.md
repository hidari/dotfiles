---
status: in_progress
---

# refactor: Claude Code フックの共通基盤を集約する

## 背景

Issue #25 Phase 3a (PR #91) のレビューで、フック周りの共通部分が 3 箇所に分散していることが分かった。
いずれも単体では動くが、片方だけ変えたときに沈黙した失敗になる形の重複である。
Phase 3a のスコープを大きく超えるため別 Issue に分けた。

### 1. PreToolUse プロトコル層の重複

`home/.claude/hooks/tirith-check.py` と `home/.claude/hooks/apm-install-guard.py` で、次の約 40 行が写経になっている。

- stdin から JSON を読む
- フィールドを snake_case と camelCase の両方で引くヘルパ
- deny の `hookSpecificOutput` JSON を組み立てる
- `PreToolUse` かつ `Bash` かを判定して抜けるゲート
- `tool_input.command` の型と空文字の検査

既に drift が発生している。
`handoff-sentinel.py` だけが `ensure_ascii=False` で出力しており、他 2 つは既定のままだった (`apm-install-guard.py` は PR #91 で揃えたが、揃えるという判断を毎回 3 箇所で繰り返す構造は残っている)。

共通モジュールを `home/.claude/hooks/` に置けば symlink 経由の配布に乗る。
ただし `scripts/tirith-hook` と `scripts/apm-install-guard` という独立した uv プロジェクト 2 本の lint / 型検査の対象と `.pre-commit-config.yaml` の `files:` 正規表現の両方へ追加が要る。
この追加コストは項目 2 を先に片付けると消える。

### 2. uv ハーネスの分散

`scripts/tirith-hook` / `scripts/handoff-sentinel` / `scripts/apm-install-guard` の `pyproject.toml` は、名前と説明を除いてほぼ同一である (ruff / mypy / pytest の設定、zero runtime deps、`package = false` まで一致)。その結果:

- CI job が 3 本。1 本あたり実作業 2 秒に対して job セットアップが 100 秒以上
- lockfile が 3 本。`.venv` が 3 つで計 300MB
- `.pre-commit-config.yaml` のエントリが 12 個

しかも lockfile が食い違っている。
`apm-install-guard` は ruff 0.16.1 / mypy 2.3.0、`tirith-hook` と `handoff-sentinel` は ruff 0.15.20 / mypy 2.1.0。同じ `home/.claude/hooks/` ディレクトリのファイルが別バージョンで lint されている状態。

`scripts/claude-hooks/` のような 1 プロジェクトへ集約し、`tests/test_<hook>.py` を並べる形にすれば CI job 1 本 / lockfile 1 本 / venv 1 つ / pre-commit 4 エントリになる。

### 3. 必須フック検査がイベント固定

`scripts/config-guard/src/config_guard/settings_invariants.py` の `_REQUIRED_PRETOOLUSE_HOOKS` と `_pretooluse_commands` は `PreToolUse` 1 イベントに固定されている。
`SessionStart` 系 (`handoff-sentinel.py` は session-handoff skill の発動経路そのもので、配線が外れると skill が沈黙する) を pin したくなった時点で、兄弟関数の複製を要求する形になっている。

データ形を `{イベント名: (フック名, ...)}` にしてコレクタをイベント引数付きの 1 関数へまとめれば、実装コストはほぼ変わらずに一般化できる。
`handoff-sentinel` を必須に入れるかは別判断 (個人ツールであり security guard ではない) として据え置いてよい。

## タスク

- [x] 3 つの uv ハーネスを `scripts/claude-hooks/` へ集約する (CI job / lockfile / venv / pre-commit エントリを 1 系統にまとめ、ruff と mypy のバージョンを揃える)
      集約と同時に観測フックを 4 本目として入れた。検査対象は `home/.claude/hooks/` を
      ディレクトリごと渡す形にしたので、フック名の列挙は pre-commit にも CI にも残っていない。
      バージョンは新しい側 (ruff 0.16.3 / mypy 2.3.1) へ揃えた。古い側へ揃えると
      apm-install-guard が通っていた検査より緩くなるため
- [x] PreToolUse プロトコル層を共有モジュールへ切り出し、`tirith-check.py` と `apm-install-guard.py` から使う
      `home/.claude/hooks/pretooluse.py` へ純関数だけを置く形にした。fail ポリシーは共有しない。
      tirith は環境変数の逃げ道つき fail-closed、apm は無条件 deny で、同じ関数へ潰すと倒れ方が
      静かに変わるためである。異常は problem 付きの例外で返し、文面と倒し方は各フックが持つ。
      print と `sys.exit` も持たせていないので、共有層だけを直接テストできる
- [x] 共通化後に `tirith-check.py` の変異注入を再実施する (security guard なので、共通化で pin が死んでいないことを確かめる)
      共有層 8 件 + フック側 4 件の計 12 件を 1 件ずつ隔離して適用し、全件で期待したテストが
      赤くなることを確認した。この過程で「入力の壊れ方ごとの理由文」が dead pin だったことが
      分かった。どの problem でも結果は deny なので、判定だけを見る assert では区別できない。
      両フックの入力異常テストを理由文まで見る形へ強化して塞いだ。
      あわせて symlink 経由 + PATH の `python3` (3.14.6) で live smoke を通した。pytest は
      `sys.executable` (3.12) で実パス起動するため、本番の起動形を覆っていない
- [ ] `settings_invariants` の必須フック検査をイベント軸で一般化する
- [ ] 全フックの JSON 出力の `ensure_ascii` 方針を 1 箇所で決める
      値としては 4 フックすべてが `ensure_ascii=False` で揃った (PreToolUse の 2 本は共有層
      経由、`handoff-sentinel` と `instructions-loaded-log` は元から)。ただし canonical はまだ
      1 つではなく、PreToolUse 以外は各フックが独立に書いている。判定 JSON の形自体が違うので
      `pretooluse.py` への相乗りでは解けない
- [ ] 観測フックの allowlist を廃して除外集合だけにする。9 個のフィールド名を列挙しているが、
      載っていない値も `_unknown_fields` が拾うので選別を一つも行っていない。実際に効いているのは
      `transcript_path` / `prompt_id` の除外 2 件だけで、9 個の literal はバイナリ側の schema の
      再掲にあたる。JSONL の形が変わりテストの書き換えを伴うので独立させる
- [ ] pre-commit の同一 `files:` を YAML anchor へ畳む。claude-hooks の 4 エントリだけでなく
      backup-tool / config-guard / node-security-notifier にも同じ形があるので一斉に行う。
      anchor が既定値へ化けずに解決されることは実測済み (一致する正規表現なら発火し、
      非一致なら Skipped になる両方向を確認)

## 関連

- [Issue #25: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する](../closed/25_skill%20と%20plugin%20を新規%20PUBLIC%20リポジトリへ集約し%20apm%20配布へ移行する/issue.md)
- PR #91 のレビューで検出 (Reuse / Efficiency / Altitude の 3 観点から独立に同じ箇所が挙がった)
- [Issue #36: refactor: CLAUDE.md を rules と skill へ分割し常時ロード量を減らす](../closed/36_CLAUDE.md%20を%20rules%20と%20skill%20へ分割し常時ロード量を減らす/issue.md)。
  - 観測フック `home/.claude/hooks/instructions-loaded-log.py` は #36 で常設と決まり、集約と同時に
    `scripts/claude-hooks/` の 4 本目として取り込んだ
