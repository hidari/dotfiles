# 運用指示の注入を user スコープへ寄せる実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 各リポへ配っていた運用指示の配線を user スコープ 1 箇所へ寄せ、取り付けの欠落を検出する層とそれを埋めるスクリプトを用意する。

**Architecture:** 配線は `home/.claude/settings.json` の `SessionStart` へ 1 件足すだけで全リポへ効く (コマンドがリポ相対のため)。各リポの `settings.local.json` の `hooks` キーは冗長になるので消す。取り付けの欠落は 2 層で見る。実行時は `guard_probes` の述語 1 件が今いるリポだけを見て沈黙を告げ、棚卸しはセットアップスクリプトの `--check` が一覧の全件を突き合わせる。どちらも書き込まない。

**Tech Stack:** Python 3 (フック層、標準ライブラリのみ)、POSIX sh (セットアップスクリプト)、pytest (フック層のテスト)、bats (シェルのテスト)

**Spec:** [42-spec.md](./42-spec.md)

## Global Constraints

- ログとコード内コメントは日本語。フロント側など外部に見えるものだけ英語 (プロジェクト CLAUDE.md)
- bats のテスト名は ASCII のみ。`rules/bats-test-name-ascii-only` が ast-grep で pin している
- pytest のテスト名は日本語でよい (`scripts/claude-hooks/tests/` の既存に倣う)
- このリポジトリは PUBLIC。取引先のリポ名と `/Users/<ユーザー名>` の絶対パスを追跡下へ書かない。前者は運用ルール、後者は `.gitleaks.toml` の `macos-user-path` が検出する
- 検査の緑を根拠にしない。追跡下のファイルしか母集団に入らない検査があるので、新規ファイルは `git add` してから走らせ、件数の変化で「見た」ことを確かめる
- 日本語の散文を git / gh コマンドへ渡すときは Write でファイルに書き `-F` / `--body-file` で渡す。コマンド文字列に載せると tirith の `confusable_text` でブロックされる
- 新しく増やす機構は 2 つに収める。probe 1 件とスクリプト 1 本。config-guard には既存検査への追記以外で触らない

---

### Task 1: user スコープへ配線を移し、消えたら赤くなるようにする

**Files:**
- Modify: `home/.claude/settings.json` (`hooks.SessionStart` の配列へ 1 要素追加)
- Modify: `scripts/config-guard/src/config_guard/settings_invariants.py`
- Test: `scripts/config-guard/tests/test_settings_invariants.py`

**Interfaces:**
- Consumes: なし (最初のタスク)
- Produces: `settings.json` の `SessionStart` に運用指示を読むコマンドが 1 件存在する状態。Task 5 の各リポ側 `hooks` 削除がこれに依存する

`settings_invariants` は必須フックを**フック本体のファイル名**で宣言している (`_REQUIRED_HOOKS` の `"SessionStart": (("guard-health.py",), ...)`)。今回足すのはスクリプトではなく `cat` コマンドなので、ファイル名では pin できない。コマンド文字列に必ず現れる部分文字列で宣言する。

- [ ] **Step 1: 失敗するテストを書く**

`scripts/config-guard/tests/test_settings_invariants.py` の末尾へ追加する。

```python
def test_SessionStart_に運用指示の読み出しが無ければ検出する() -> None:
    settings = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/guard-health.py"'}
                    ],
                }
            ]
        },
        "claudeMdExcludes": ["**/home/.claude/CLAUDE.md"],
    }

    findings = check_settings_invariants(settings)

    assert any("PRIVATE_CLAUDE.md" in f.message for f in findings)


def test_SessionStart_に運用指示の読み出しがあれば通る() -> None:
    settings = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/guard-health.py"'},
                        {
                            "type": "command",
                            "command": (
                                'cat "$(git rev-parse --show-toplevel)'
                                '/.hidari/private-ops/PRIVATE_CLAUDE.md" 2>/dev/null'
                            ),
                        },
                    ],
                }
            ]
        },
        "claudeMdExcludes": ["**/home/.claude/CLAUDE.md"],
    }

    findings = check_settings_invariants(settings)

    assert not any("PRIVATE_CLAUDE.md" in f.message for f in findings)
```

- [ ] **Step 2: 落ちることを確かめる**

Run: `uv run --directory scripts/config-guard pytest tests/test_settings_invariants.py -k PRIVATE_CLAUDE -v`
Expected: 1 件目が FAIL (`assert any(...)` が False)。2 件目は PASS してしまうが、これは検査がまだ何も見ていないためで、1 件目だけが機構を測っている

- [ ] **Step 3: 最小の実装を書く**

`settings_invariants.py` の `_REQUIRED_HOOKS` の直後へ定数を足し、`check_settings_invariants` の末尾 (既存の `_REQUIRED_CLAUDE_MD_EXCLUDES` ループの後) へ検査を足す。

```python
# SessionStart に必ず載せるコマンドの目印。フック本体ではなく cat なのでファイル名では
# 宣言できず、コマンド文字列に必ず現れる部分文字列で見る。パスの綴りごと pin すると
# 参照の形を変えるたびにここが落ちるので、実体のファイル名だけを見る。
_REQUIRED_SESSION_START_SUBSTRING = "PRIVATE_CLAUDE.md"
```

```python
    session_start = settings.get("hooks", {}).get("SessionStart", [])
    commands = [
        hook.get("command", "")
        for group in session_start
        for hook in group.get("hooks", [])
    ]
    if not any(_REQUIRED_SESSION_START_SUBSTRING in c for c in commands):
        findings.append(
            Finding(
                _SRC,
                "hooks.SessionStart",
                f"SessionStart に {_REQUIRED_SESSION_START_SUBSTRING} を読むコマンドがありません。"
                "運用指示が全リポで載らなくなります",
            )
        )
```

`_SRC` はこのモジュールの既存定数を使う。名前が違う場合は既存の `Finding(...)` 呼び出しに合わせる。

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run --directory scripts/config-guard pytest tests/test_settings_invariants.py -v`
Expected: 全 PASS

- [ ] **Step 5: 実際の settings.json へ配線を足す**

`home/.claude/settings.json` の `hooks.SessionStart` 配列の `hooks` リストへ 1 要素追加する。既存 4 件の後ろへ置く。

```json
{
  "type": "command",
  "command": "cat \"$(git rev-parse --show-toplevel)/.hidari/private-ops/PRIVATE_CLAUDE.md\" 2>/dev/null"
}
```

`2>/dev/null` を付ける理由は 2 つある。git リポジトリでない作業ツリーでは `git rev-parse` が失敗する。`.hidari/private-ops` が無いリポでは `cat` が失敗する。どちらも対象外を意味するので無音で通す。

- [ ] **Step 6: 変異注入で pin が効くことを確かめる**

足した要素を一時的に消して config-guard を走らせ、赤くなることを見る。緑のままなら検査が届いていない。

Run: `uv run --project scripts/config-guard config-guard .` (要素を消した状態)
Expected: `SessionStart に PRIVATE_CLAUDE.md を読むコマンドがありません` が出る

確認したら要素を戻し、もう一度走らせて緑に戻ることを見る。

- [ ] **Step 7: コミット**

```bash
git add home/.claude/settings.json scripts/config-guard/src/config_guard/settings_invariants.py scripts/config-guard/tests/test_settings_invariants.py
git commit -F .cache/commit-msg.txt
```

コミット本文は Write でファイルに書いてから渡す (Global Constraints)。

---

### Task 2: 取り付けの欠落をセッション頭で告げる probe

**Files:**
- Modify: `home/.claude/hooks/guard_probes.py`
- Test: `scripts/claude-hooks/tests/test_guard_probes.py`

**Interfaces:**
- Consumes: Task 1 の配線 (probe はこの配線が届く前提を測る)
- Produces: `guard_probes.probe_private_ops() -> ProbeResult` と、`PROBES` に `("private-ops", probe_private_ops)` が加わった登録簿。Task 4 の `--check` はこの述語を使わず独立に実装する (シェルと Python で層が違うため)

probe が見るのは今いるリポ 1 件だけで、一覧は読まない。一覧は private-ops にあり到達経路が `.hidari/private-ops` なので、それが無いリポでは読めない (spec の「一覧と検出層の関係」)。

- [ ] **Step 1: 失敗するテストを書く**

`scripts/claude-hooks/tests/test_guard_probes.py` の末尾へ追加する。3 象限すべてを書く。

```python
def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """CLAUDE_PROJECT_DIR で指させる作業ツリーを 1 つ作る。

    git init しないのは、probe が git を呼ばずに環境変数だけで根を決める規約だからである。
    git を呼ぶ形にすると、フックの cwd がリポ外だったときの挙動がテストから見えなくなる。
    """
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    return root


def test_hidari_が無ければ対象外として健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo(tmp_path, monkeypatch)

    result = guard_probes.probe_private_ops()

    assert result.healthy is True
    assert result.detail == ""


def test_private_ops_が解決すれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    target = tmp_path / "cloud" / "private-ops"
    target.mkdir(parents=True)
    (root / ".hidari").mkdir()
    (root / ".hidari" / "private-ops").symlink_to(target)

    result = guard_probes.probe_private_ops()

    assert result.healthy is True


def test_hidari_はあるのに private_ops_が無ければ沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, monkeypatch)
    (root / ".hidari").mkdir()

    result = guard_probes.probe_private_ops()

    assert result.healthy is False
    assert "private-ops" in result.detail


def test_symlink_が切れていれば沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    (root / ".hidari").mkdir()
    (root / ".hidari" / "private-ops").symlink_to(tmp_path / "gone")

    result = guard_probes.probe_private_ops()

    assert result.healthy is False


def test_登録簿は名前の集合で pin する() -> None:
    """件数ではなく名前で見る。件数だけだと差し替えを見逃す。"""
    assert {name for name, _ in guard_probes.PROBES} == {"apm", "tirith", "private-ops"}
```

- [ ] **Step 2: 落ちることを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_guard_probes.py -k private_ops -v`
Expected: FAIL で `AttributeError: module 'guard_probes' has no attribute 'probe_private_ops'`

- [ ] **Step 3: 最小の実装を書く**

`guard_probes.py` の `probe_tirith` の後、`PROBES` の前へ追加する。

```python
def _project_root() -> Path | None:
    """フックから見た作業ツリーの根。決められなければ None。

    git を呼ばず環境変数だけで決める。フックの cwd はリポ外のこともあり、そこで
    git を呼ぶと「リポではない」と「指示が無い」が同じ失敗の形をとる。
    """
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(root) if root else None


def probe_private_ops() -> ProbeResult:
    """運用指示の実体へ到達できるか。

    .hidari/ の存在を opt-in マーカーとして使う。このディレクトリはユーザーが個人の
    メモを置く場所として全リポで運用しており、新しい状態を増やさずに「対象かどうか」を
    表せる。無いリポは対象外なので健全として通す。

    一覧は読まない。一覧は外部ストレージにあり到達経路がこの symlink なので、symlink が
    無いリポでは一覧そのものが読めない。読めない状態を沈黙として報告すると、対象外の
    リポで常に鳴ることになる。一覧との突き合わせは棚卸し側 (repo-wiring --check) が持つ。

    exists() は symlink を辿るので、切れたリンクは False になる。外部ストレージが
    未マウントで実体へ届かない状態もここで捕まる。
    """
    root = _project_root()
    if root is None:
        return ProbeResult(healthy=True)

    hidari = root / ".hidari"
    if not hidari.is_dir():
        return ProbeResult(healthy=True)

    link = hidari / "private-ops"
    if link.exists():
        return ProbeResult(healthy=True)

    return ProbeResult(
        healthy=False,
        detail=(
            f"{link} が解決しないため、このリポジトリの運用指示は読み込まれていない。"
            "外部ストレージが未マウントか、symlink が張られていない。"
            "repo-wiring を実行すると張り直せる。"
        ),
    )
```

`from pathlib import Path` を import 節へ追加する。`os` は既に import 済み。

- [ ] **Step 4: 登録簿へ足す**

```python
PROBES: tuple[tuple[str, Callable[[], ProbeResult]], ...] = (
    ("apm", probe_apm),
    ("tirith", probe_tirith),
    ("private-ops", probe_private_ops),
)
```

- [ ] **Step 5: テストが通ることを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_guard_probes.py -v`
Expected: 全 PASS

- [ ] **Step 6: 変異注入で登録が効くことを確かめる**

`PROBES` から `("private-ops", probe_private_ops)` を一時的に外し、`test_登録簿は名前の集合で pin する` が落ちることを見る。落ちなければ pin が効いていない。確認したら戻す。

- [ ] **Step 7: 実環境で鳴ることを対照付きで確かめる**

このリポジトリの `.hidari/private-ops` を一時的に別名へ退避し、新しいセッションで probe が鳴ることを見る。鳴ってから戻す。**先に鳴ることを見ないと、無言を健全と誤読する。**

```bash
mv .hidari/private-ops .hidari/private-ops.bak
# 新しいセッションを開いて告知が出ることを確認する
mv .hidari/private-ops.bak .hidari/private-ops
```

- [ ] **Step 8: コミット**

```bash
git add home/.claude/hooks/guard_probes.py scripts/claude-hooks/tests/test_guard_probes.py
git commit -F .cache/commit-msg.txt
```

---

### Task 3: 取り付けを冪等に張り直すセットアップスクリプト

**Files:**
- Create: `scripts/repo-wiring/repo-wiring`
- Create: `scripts/tests/repo-wiring.bats`
- Modify: `bootstrap.sh` (`SYMLINK_PAIRS` へ 1 行)

**Interfaces:**
- Consumes: なし (probe とは独立。probe は Python 層、こちらは sh 層で、同じ判定を共有しない)
- Produces: `repo-wiring <repo-path>` が 1 リポへ取り付ける。Task 4 が同じファイルへ `--check` を足す

拡張子を付けないのは `scripts/apm-guard/apm` と同じ理由で、`~/.local/bin/repo-wiring` として PATH から呼ぶため。`.pre-commit-config.yaml` の `shellcheck` フックは `files:` に拡張子無しのパスを個別列挙しているので、そこへ 1 行足す必要がある。

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/repo-wiring.bats` を作る。テスト名は ASCII のみ (Global Constraints)。

```bash
#!/usr/bin/env bats
# =============================================================================
# repo-wiring (運用指示の取り付け) のテスト
# =============================================================================

load test_helper

bats_require_minimum_version 1.5.0

WIRING="$REPO_ROOT/scripts/repo-wiring/repo-wiring"

setup() {
    setup_test_home
    TARGET="$TEST_HOME/repo"
    mkdir -p "$TARGET"
    git -C "$TARGET" init -q .
    OPS="$TEST_HOME/cloud/private-ops"
    mkdir -p "$OPS"
}

teardown() {
    teardown_test_home
}

@test "repo-wiring creates the hidari directory and the symlink" {
    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ -d "$TARGET/.hidari" ]
    [ -L "$TARGET/.hidari/private-ops" ]
    [ -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring writes the exclude entry before creating the symlink" {
    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    grep -q '^\.hidari/$' "$TARGET/.git/info/exclude"
}

@test "repo-wiring is idempotent" {
    run "$WIRING" --ops "$OPS" "$TARGET"
    [ "$status" -eq 0 ]

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ "$(grep -c '^\.hidari/$' "$TARGET/.git/info/exclude")" -eq 1 ]
}

@test "repo-wiring repairs a dangling symlink" {
    mkdir -p "$TARGET/.hidari"
    ln -s "$TEST_HOME/gone" "$TARGET/.hidari/private-ops"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring refuses when the path is still not ignored" {
    # .gitignore で明示的に再包含すると exclude を書いても ignore されない。
    # スクリプト自身が ignore を用意しても穴が残る経路がこれで、fail-closed を測る。
    printf '!.hidari/\n' > "$TARGET/.gitignore"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -ne 0 ]
    [ ! -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring refuses when the ops directory does not exist" {
    run "$WIRING" --ops "$TEST_HOME/missing" "$TARGET"

    [ "$status" -ne 0 ]
}
```

- [ ] **Step 2: 落ちることを確かめる**

Run: `bats scripts/tests/repo-wiring.bats`
Expected: 全件 FAIL (スクリプトが存在しない)

- [ ] **Step 3: 最小の実装を書く**

`scripts/repo-wiring/repo-wiring` を作り、実行ビットを立てる。

```sh
#!/usr/bin/env bash
# =============================================================================
# 運用指示の取り付け。1 リポジトリへ .hidari/ と private-ops の symlink を用意する。
#
# 追跡下のファイルは一切触らない。書くのは .git/info/exclude と追跡外の symlink だけで、
# コミットを要さない。並行して別のセッションが作業していても git 上で衝突しない。
# =============================================================================

set -euo pipefail

OPS_DEFAULT="$HOME/.hidari/private-ops"

usage() {
    echo "usage: repo-wiring [--ops <path>] <repo-path>" >&2
    exit 2
}

OPS="$OPS_DEFAULT"
TARGET=""
while [ $# -gt 0 ]; do
    case "$1" in
        --ops) [ $# -ge 2 ] || usage; OPS="$2"; shift 2 ;;
        -*) usage ;;
        *) [ -z "$TARGET" ] || usage; TARGET="$1"; shift ;;
    esac
done
[ -n "$TARGET" ] || usage

fail() {
    echo "repo-wiring: $*" >&2
    exit 1
}

[ -d "$OPS" ] || fail "運用指示の実体がありません: $OPS"
[ -d "$TARGET/.git" ] || fail "git リポジトリではありません: $TARGET"

# 1. exclude へ書く。symlink を作る前に置くことで、ignore されない瞬間を作らない。
exclude="$TARGET/.git/info/exclude"
mkdir -p "$(dirname "$exclude")"
if ! grep -qx '\.hidari/' "$exclude" 2>/dev/null; then
    printf '.hidari/\n' >> "$exclude"
fi

# 2. ignore を確かめる。配下パスで引くのは、末尾スラッシュ付きのパターンが
#    ディレクトリパスで問い合わせたときだけ実体を要求するためである。
if ! git -C "$TARGET" check-ignore -q .hidari/private-ops; then
    fail "$TARGET で .hidari/ が ignore されません。.gitignore の再包含を確認してください"
fi

# 3. 作る。ln -sfn は既存の symlink を張り直すので、切れたリンクの修復も同じ経路で済む。
mkdir -p "$TARGET/.hidari"
ln -sfn "$OPS" "$TARGET/.hidari/private-ops"

echo "repo-wiring: $TARGET を取り付けました"
```

- [ ] **Step 4: 実行ビットを立ててテストが通ることを確かめる**

```bash
chmod +x scripts/repo-wiring/repo-wiring
bats scripts/tests/repo-wiring.bats
```

Expected: 全 PASS

- [ ] **Step 5: shellcheck の対象へ入れる**

`.pre-commit-config.yaml` の `shellcheck` フックの `files:` は拡張子無しのスクリプトを個別に列挙している。`^scripts/repo-wiring/repo-wiring$` を追加する。

```yaml
        files: (\.sh$|\.bash$|^scripts/apm-guard/apm$|^scripts/repo-wiring/repo-wiring$)
```

Run: `pre-commit run shellcheck --all-files`
Expected: Passed

- [ ] **Step 6: bootstrap から PATH へ通す**

`bootstrap.sh` の `SYMLINK_PAIRS` へ 1 行足す。`scripts/util-tools/small-id-gen/small-id-gen.sh` と同じ形。

```bash
    "scripts/repo-wiring/repo-wiring|.local/bin/repo-wiring"
```

- [ ] **Step 7: symlink pair の件数テストを直す**

`scripts/tests/bootstrap.bats` は pair の件数を数えるテストを持つ。件数が 1 増えるので期待値を直す。

Run: `bats scripts/tests/bootstrap.bats`
Expected: 全 PASS (落ちたら期待値を実測に合わせる)

- [ ] **Step 8: コミット**

```bash
git add scripts/repo-wiring/repo-wiring scripts/tests/repo-wiring.bats .pre-commit-config.yaml bootstrap.sh scripts/tests/bootstrap.bats
git commit -F .cache/commit-msg.txt
```

---

### Task 4: 一覧と実態を突き合わせる `--check`

**Files:**
- Modify: `scripts/repo-wiring/repo-wiring`
- Modify: `scripts/tests/repo-wiring.bats`

**Interfaces:**
- Consumes: Task 3 の `repo-wiring` 本体
- Produces: `repo-wiring --check [--list <path>]` が一覧の全件を突き合わせて報告する。終了コードは問題があれば 1

一覧の既定の置き場は `$HOME/.hidari/private-ops/repos.txt` とし、`--list` で差し替えられるようにする (テストのため)。行の文法は有効・無視・却下の 3 分類にする。2 分類だと文法違反が「無視」へ吸われて静かに消える。

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/repo-wiring.bats` へ追加する。

```bash
@test "check reports a repo listed but not wired" {
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    [[ "$output" == *"$TARGET"* ]]
    [[ "$output" == *"missing"* ]]
}

@test "check stays silent for a wired repo" {
    "$WIRING" --ops "$OPS" "$TARGET"
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    [[ "$output" == *"ok"* ]]
}

@test "check always prints the population count" {
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    # 0 件と見ていないを区別するため、問題の有無にかかわらず母数を出す
    [[ "$output" == *"listed=1"* ]]
}

@test "check rejects a malformed line instead of ignoring it" {
    printf 'relative/path\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    [[ "$output" == *"rejected"* ]]
}

@test "check skips comments and blank lines" {
    printf '# comment\n\n%s\n' "$TARGET" > "$TEST_HOME/repos.txt"
    "$WIRING" --ops "$OPS" "$TARGET"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    [[ "$output" == *"listed=1"* ]]
}

@test "check reports a vanished repo" {
    printf '%s\n' "$TEST_HOME/gone" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    [[ "$output" == *"vanished"* ]]
}
```

- [ ] **Step 2: 落ちることを確かめる**

Run: `bats scripts/tests/repo-wiring.bats`
Expected: 追加した 6 件が FAIL

- [ ] **Step 3: 最小の実装を書く**

引数解析へ `--check` と `--list` を足し、`--check` のときは取り付けを行わず判定だけを出す分岐を書く。

```sh
LIST_DEFAULT="$OPS_DEFAULT/repos.txt"
CHECK=false
LIST=""

# 引数ループへ追加する分岐
        --check) CHECK=true; shift ;;
        --list) [ $# -ge 2 ] || usage; LIST="$2"; shift 2 ;;
```

`--check` の本体は引数の検証の後、取り付け処理の前へ置く。

```sh
if [ "$CHECK" = true ]; then
    list="${LIST:-$LIST_DEFAULT}"
    [ -f "$list" ] || fail "一覧がありません: $list"

    listed=0
    problems=0
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            '' | '#'*) continue ;;              # 無視
            /*) ;;                              # 有効 (絶対パスのみ)
            *) echo "rejected: $line (絶対パスではありません)"; problems=$((problems + 1)); continue ;;
        esac
        listed=$((listed + 1))
        if [ ! -d "$line/.git" ]; then
            echo "vanished: $line"
            problems=$((problems + 1))
        elif [ -e "$line/.hidari/private-ops" ]; then
            echo "ok: $line"
        else
            echo "missing: $line"
            problems=$((problems + 1))
        fi
    done < "$list"

    # 問題の有無にかかわらず母数を出す。0 件と「見ていない」を区別するため。
    echo "listed=$listed problems=$problems"
    [ "$problems" -eq 0 ] || exit 1
    exit 0
fi
```

`--check` は `$TARGET` を要らないので、引数検証の `[ -n "$TARGET" ] || usage` を `--check` のときは飛ばすよう条件を分ける。

```sh
if [ "$CHECK" = false ]; then
    [ -n "$TARGET" ] || usage
fi
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `bats scripts/tests/repo-wiring.bats`
Expected: 全 PASS

- [ ] **Step 5: 対照で「見ている」ことを確かめる**

一覧に実在する取り付け済みリポを 1 行だけ書いて `--check` を走らせ、`listed=1 problems=0` が出ることを見る。次にその行を消して空の一覧で走らせ、`listed=0` が出ることを見る。**同じ緑でも母数が違うことが読める**ようになっていれば正しい。

- [ ] **Step 6: shellcheck とテスト全体を通す**

```bash
pre-commit run shellcheck --all-files
bats scripts/tests/
```

Expected: どちらも Passed

- [ ] **Step 7: コミット**

```bash
git add scripts/repo-wiring/repo-wiring scripts/tests/repo-wiring.bats
git commit -F .cache/commit-msg.txt
```

---

### Task 5: 冗長な配線の撤去と実地検証

**Files:**
- Modify: 各リポの `.claude/settings.local.json` (追跡外。コミット不要)
- Create: `$HOME/.hidari/private-ops/repos.txt` (追跡外)
- Modify: 実地 1 件の `.pre-commit-config.yaml` (そのリポでコミット)

**Interfaces:**
- Consumes: Task 1 の配線、Task 2 の probe、Task 4 の `--check`
- Produces: なし (最終タスク)

このタスクだけ dotfiles の外側に出る。**先に二重に載ることを観測してから消す。** 観測せずに消すと、消えた後の無音が「1 回になった」なのか「0 回になった」なのか区別できない。

- [ ] **Step 1: 二重に載っていることを先に観測する**

Task 1 の配線を入れた状態で、project 側にも `cat` を持つリポで新しいセッションを開く。運用指示が **2 回** context に入ることを確かめる。

これが対照である。2 回入ることを見ずに 1 回を確認しても、それが「重複が消えた」結果なのか「元から 1 回だった」のかが分からない。

- [ ] **Step 2: 一覧を書く**

`$HOME/.hidari/private-ops/repos.txt` を作る。1 行 1 リポの絶対パスで、対象リポだけを書く。休眠・archive・Claude 未使用のリポは書かない。

種別の判断は `.cache/repo-inventory.md` の判断シートに基づく。**このファイルは追跡外に留め、リポ名を dotfiles へ持ち込まない。**

- [ ] **Step 3: `--check` で現状を測る**

Run: `repo-wiring --check`
Expected: `listed=N problems=M` が出る。`missing` の行が Task 3 で埋める対象になる

- [ ] **Step 4: 欠けている取り付けを埋める**

`--check` が `missing` と報告した各リポへ `repo-wiring <path>` を走らせる。走らせた後にもう一度 `--check` を回し、`problems=0` になることを確かめる。

- [ ] **Step 5: 各リポの冗長な hooks を消す**

`.claude/settings.local.json` を持つリポで `hooks` キーを削除する。`permissions` と他のキーは残す。**追跡外なのでコミットは不要。**

project 側に固有の hook を持つリポ (独自スクリプトを呼んでいるもの) は、その要素だけを残して user スコープと重複する 3 件を消す。全部消すと固有の挙動が失われる。

削除後、`jq` で残存を数える。**先に非 0 件が出ることを確認してから 0 件を確かめる。**

- [ ] **Step 6: 指示が 1 回だけ載ることを確かめる (V1)**

Step 1 で 2 回入ることを見たリポで、新しいセッションを開く。今度は 1 回だけ入ることを確かめる。

設定変更が実行中のセッションへ反映されるまでには数回のツール呼び出しぶんの遅れがある。1 回確認して空でも反映されないと決めないこと。

- [ ] **Step 7: probe が鳴ることを確かめる (V2)**

実地 1 件で `.hidari/private-ops` を一時退避し、新しいセッションで probe が鳴ることを見る。鳴ってから戻す。

- [ ] **Step 8: 実地 1 件へ pre-commit を入れる**

対象リポに `.pre-commit-config.yaml` を作る。汎用の hook だけを採る (ISSUE-64 の判断に従う)。

```yaml
repos:
  - repo: local
    hooks:
      - id: gitleaks
        name: gitleaks (leak guard)
        language: system
        entry: gitleaks git --staged --redact --no-banner -c .gitleaks.toml
        pass_filenames: false
        always_run: true

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: cef0300fd0fc4d2a87a85fa2093c6b283ea36f4b  # frozen: v5.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-json
      - id: check-yaml
```

`pre-commit install` をそのリポで 1 回実行する。**取り付けは clone に travel しない**ので、設定を commit しただけでは効かない。

- [ ] **Step 9: gitleaks が実際に止めることを対照で確かめる**

検出される文字列を含むファイルを作り、`git add` してからコミットを試みて**落ちること**を見る。

対象リポの `.gitleaks.toml` が `.cache/` を allowlist している場合、そこへ置いた対照は検出されない。**allowlist の外のパスへ置くこと。** `--staged` は index を見るので、`git add` しないと 0 件になる。

確認したら対照ファイルを消す。

- [ ] **Step 10: Issue を更新する**

ISSUE-42 の「タスク」4 件へチェックを入れ、ISSUE-53 のタスクのうち今回進んだものを記録する。ISSUE-53 の「実地で 1 件の配布先へ取り付けを通し、drift を検出できることを確かめる」は Step 3-4 と Step 7 が満たす。

---

## Self-Review

**spec のカバレッジ:** spec の「決めたこと」4 項目はそれぞれ Task 1 (配線)、Task 3 (ignore の保証)、判断のみで実装不要 (公開範囲は採らない)、Task 2 と Task 4 (検査の二層) が実装する。「検証」の V1/V2 は Task 5 の Step 6-7。「実地の 1 件」は Task 5 の Step 8-9。リスク表の R1 は Task 5 Step 1、R2 は Task 2 Step 7、R3 は Task 2 Step 6、R7 は Task 3 の fail-closed テストが対応する。R4 (一覧と実態のズレ) は Task 4、R5 と R6 は機構を持たない判断なので実装タスクを持たない。

**未確定として残すもの:** `settings_invariants.py` の `_SRC` 定数の実際の名前は、実装時にファイルを読んで確かめる。Task 1 Step 3 にその旨を書いた。`scripts/tests/bootstrap.bats` の pair 件数テストの期待値も実測に合わせる (Task 3 Step 7)。

**型の一貫性:** `ProbeResult(healthy, detail)` は既存の dataclass をそのまま使う。`probe_private_ops` の名前は Task 2 の実装・テスト・登録簿の 3 箇所で一致している。`repo-wiring` のオプション名は `--ops` / `--check` / `--list` で Task 3 と Task 4 を通じて一致している。
