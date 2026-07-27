# タスクリスト ID 自動導出 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 作業ディレクトリからタスクリスト ID を自動導出し、既存リストを導出名へ寄せる。

**Architecture:** `home/.zshrc` の Claude 起動セクションに純粋な導出関数を 1 つ追加し、既存の 2 つのランチャから使う。通知関数は ID をグローバル参照から引数受け取りへ変える。既存リストの移行は `.cache/` の使い捨てスクリプトで行い、リポジトリには成果物を残さない。

**Tech Stack:** zsh (実行時) / bash (テスト時) / bats-core 1.13 / jq

## Global Constraints

- 関数は POSIX 互換の展開のみを使う。zsh 専用 modifier (`${dir:t}` 等) は使わない。テストは bats が bash で関数ブロックを source して実行するため
- `home/.zshrc` は `~/.zshrc` の symlink 実体。変異注入は `ZSHRC_FILE` を上書きしてコピーに対して行う
- コード内のコメントは日本語
- リポジトリの追跡ファイル・コミット本文に実プロジェクト名と絶対パスを書かない
- 日本語の散文を git / gh に渡すときは Write でファイルに書いて `-F` / `--body-file` を使う
- 一時ファイルは `<repo>/.cache/` に置く

---

## File Structure

| ファイル | 責務 |
| --- | --- |
| `home/.zshrc` (Claude Code 起動セクション) | 導出・検査・通知・起動。今回 `_claude_task_list_id()` を追加し、`_claude_task_list_notice()` の引数を変え、2 つのランチャを更新する |
| `scripts/tests/zshrc-claude.bats` | 上記の仕様をテストで表現する |
| `scripts/tests/test_helper.bash` | cwd を移して関数を実行するヘルパを追加する |
| `.cache/migrate-task-lists.sh` | 1 回きりの移行。リポジトリには入れない |

---

### Task 1: cwd を移して実行するテストヘルパ

導出関数のテストは cwd に依存する。cwd を戻さないと `teardown_test_home` が現在の作業ディレクトリごと削除し、後続テストが存在しない cwd を引きずって `git rev-parse` の結果が揺れる。復元を各テストに任せると忘れた 1 件が他を壊すため、ヘルパに閉じる。

**Files:**
- Modify: `scripts/tests/test_helper.bash`

**Interfaces:**
- Produces: `run_in_dir <dir> <command...>` — cwd を `<dir>` にして `run` を実行し、元の cwd へ戻す。`status` / `output` は `run` と同じくグローバルに残る

- [ ] **Step 1: ヘルパを追加する**

`scripts/tests/test_helper.bash` のアサーションヘルパ節の直前 (`load_zshrc_claude_functions` の定義の後) に追加する。

```bash
# 指定ディレクトリを cwd にして run を実行し、元の cwd へ戻す。
# cwd を戻さないと teardown_test_home が作業中のディレクトリごと削除し、後続テストが
# 存在しない cwd を引きずって git 探索の結果が揺れる。復元忘れを 1 件でも作らないよう
# ヘルパ側に閉じる。run と同じく status / output はグローバルに残る。
run_in_dir() {
    local dir="$1"
    shift
    local saved="$PWD"
    cd "$dir" || return 1
    run "$@"
    cd "$saved" || return 1
}
```

- [ ] **Step 2: 既存テストが壊れていないことを確認する**

Run: `bats scripts/tests/*.bats`
Expected: 142 ok / 0 not ok / 0 warnings (ヘルパ追加のみなので件数は変わらない)

- [ ] **Step 3: コミット**

本文は Write で `.cache/commit-t1.txt` に書き、`git commit -F` で渡す。

```bash
git add scripts/tests/test_helper.bash
git commit -F .cache/commit-t1.txt
```

---

### Task 2: `_claude_task_list_id()` を追加する

**Files:**
- Modify: `home/.zshrc` (Claude Code 起動セクション、`_claude_config_dir()` の後)
- Test: `scripts/tests/zshrc-claude.bats`

**Interfaces:**
- Consumes: `run_in_dir` (Task 1)
- Produces: `_claude_task_list_id()` — 引数なし。cwd から ID を導出して stdout へ出す。git リポジトリ内ならリポジトリルートの basename、そうでなければ cwd の basename。導出できないときは空文字を出す

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/zshrc-claude.bats` の `_claude_config_dir` 節と `claude (個人アカウント)` 節の間に追加する。

```bash
# =============================================================================
# _claude_task_list_id
# =============================================================================
#
# ID を手で打つ限り typo は避けられない。作業ディレクトリから導出すれば
# 打ち間違えようがなく、指定を忘れることもない。

@test "_claude_task_list_id: derives from the git repository root" {
    setup_test_repo "$TEST_HOME/myrepo"
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" _claude_task_list_id

    [ "$status" -eq 0 ]
    [ "$output" = "myrepo" ]
}

@test "_claude_task_list_id: resolves to the root even from a subdirectory" {
    # サブディレクトリごとに別 ID になると、同じプロジェクトの進捗が割れる。
    # これが導出元を cwd ではなくリポジトリルートにしている理由
    setup_test_repo "$TEST_HOME/myrepo"
    mkdir -p "$TEST_HOME/myrepo/frontend/src"
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo/frontend/src" _claude_task_list_id

    [ "$status" -eq 0 ]
    [ "$output" = "myrepo" ]
}

@test "_claude_task_list_id: falls back to the cwd name outside a repository" {
    mkdir -p "$TEST_HOME/plain-dir"
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/plain-dir" _claude_task_list_id

    [ "$status" -eq 0 ]
    [ "$output" = "plain-dir" ]
}

@test "_claude_task_list_id: resolves symlinked directories to the same id" {
    # 同じ実ディレクトリへ 2 つの経路で入っても ID が一致すること。$PWD はリンク名を
    # 返すため、揃えないと同じ場所なのにタスクリストが 2 つに割れる。
    # git 側は --show-toplevel が常に実体パスを返すので、フォールバックだけ経路依存に
    # なる非対称を作らない
    mkdir -p "$TEST_HOME/real-dir"
    ln -s "$TEST_HOME/real-dir" "$TEST_HOME/link-dir"
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/link-dir" _claude_task_list_id

    [ "$status" -eq 0 ]
    [ "$output" = "real-dir" ]
}

@test "_claude_task_list_id: yields nothing at the filesystem root" {
    # basename が空になる唯一の場所。空の ID を渡したときの Claude Code の挙動は
    # 未確認なので、呼び出し側が変数を設定しない判断をするための signal にする
    load_zshrc_claude_functions

    run_in_dir / _claude_task_list_id

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}
```

- [ ] **Step 2: 赤を確認する**

Run: `bats scripts/tests/zshrc-claude.bats --filter "_claude_task_list_id"`
Expected: 5 件すべて not ok。理由は `_claude_task_list_id: command not found` (関数未定義)

- [ ] **Step 3: 最小の実装を書く**

`home/.zshrc` の `_claude_config_dir()` 定義の直後に追加する。

```zsh
# タスクリスト ID を作業ディレクトリから導出する。git リポジトリならルートの名前、
# そうでなければ cwd の名前。サブディレクトリでもルートに寄せるのは、同じプロジェクトの
# 進捗が割れないため。
# リポジトリ外では pwd -P で実体パスに寄せる。$PWD は symlink 経由で入ったときに
# リンク名を返すため、同じディレクトリなのに経路によって ID が割れる。git 側は
# --show-toplevel が常に実体パスを返すので、揃えないと 2 つの分岐が非対称になる。
# zsh の modifier (${dir:t}) は bats が bash で source すると壊れるので使わない。
function _claude_task_list_id() {
  local dir
  dir="$(git rev-parse --show-toplevel 2>/dev/null)" || dir="$(pwd -P)"
  printf '%s' "${dir##*/}"
}
```

- [ ] **Step 4: 緑を確認する**

Run: `bats scripts/tests/zshrc-claude.bats`
Expected: 25 ok / 0 not ok

- [ ] **Step 5: 変異注入で pin が生きていることを確認する**

一度に 1 箇所ずつ、`.cache/mutation/zshrc` のコピーに対して行う。`ZSHRC_FILE` を上書きして実行する。復元は `cp home/.zshrc .cache/mutation/zshrc` で行い、`git checkout` は使わない (未コミットの編集ごと巻き戻すため)。

| 変異 | 赤くなるべきテスト |
| --- | --- |
| `git rev-parse --show-toplevel` を `--show-prefix` に変える | derives from the git repository root |
| `\|\| dir="$(pwd -P)"` を削る | falls back to the cwd name |
| `pwd -P` を `pwd` に戻す | resolves symlinked directories to the same id |
| `${dir##*/}` を `${dir}` に変える | 全件 |

```bash
mkdir -p .cache/mutation && cp home/.zshrc .cache/mutation/zshrc
# 1 箇所だけ書き換えてから
ZSHRC_FILE="$PWD/.cache/mutation/zshrc" bats scripts/tests/zshrc-claude.bats --filter "_claude_task_list_id"
```

Expected: 各変異で対応するテストが not ok になる。緑のままなら dead pin なのでテストを強化する

- [ ] **Step 6: コミット**

```bash
rm -rf .cache/mutation
git add home/.zshrc scripts/tests/zshrc-claude.bats
git commit -F .cache/commit-t2.txt
```

---

### Task 3: `_claude_task_list_notice()` を引数受け取りに変える

導出した ID を通知に渡すには、グローバル参照をやめて引数で受ける必要がある。挙動は変えないリファクタだが、既存 4 件のテストが触るため独立したタスクにする。

**Files:**
- Modify: `home/.zshrc` (`_claude_task_list_notice`)
- Modify: `scripts/tests/zshrc-claude.bats` (既存 4 件)

**Interfaces:**
- Produces: `_claude_task_list_notice <config_dir> <task_list_id>` — 第 2 引数が空なら何もしない。`<config_dir>/tasks/<task_list_id>` が無ければ stderr へ知らせる。戻り値は常に 0

- [ ] **Step 1: 既存テストを新しい呼び出し形へ書き換える**

`scripts/tests/zshrc-claude.bats` の `_claude_task_list_notice` 節を差し替える。環境変数の前置をやめ、第 2 引数で渡す。

```bash
@test "_claude_task_list_notice: warns when the task list id is unknown" {
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude" nonexistent

    # 新規作成は正当な操作なので、知らせるだけでブロックはしない
    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: nonexistent"
}

@test "_claude_task_list_notice: stays silent when the task list already exists" {
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude" dotfiles

    [ "$status" -eq 0 ]
    # 既知の ID で警告が出ると常時ノイズになり、本当の typo を見落とす
    [ -z "$output" ]
}

@test "_claude_task_list_notice: stays silent when no task list id is given" {
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude" ""

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "_claude_task_list_notice: distinguishes the config dir it inspects" {
    # タスクリストはアカウントごとに別なので、探索先が config dir 依存であることを pin する。
    # 個人側にだけ存在する ID を仕事側の config dir で問い合わせたら未知として扱う。
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude-hamiltonian" dotfiles

    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: dotfiles"
}

@test "_claude_task_list_notice: ignores the ambient environment variable" {
    # グローバル参照が残っていると、呼び出し側が渡した ID ではなく前置の値を見てしまう。
    # 導出した ID と手打ちの ID が食い違ったときに誤った判定をする
    mkdir -p "$TEST_HOME/.claude/tasks/derived"
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=nonexistent run _claude_task_list_notice "$TEST_HOME/.claude" derived

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}
```

- [ ] **Step 2: 赤を確認する**

Run: `bats scripts/tests/zshrc-claude.bats --filter "_claude_task_list_notice"`
Expected: 少なくとも `ignores the ambient environment variable` が not ok。現行実装はグローバルの `CLAUDE_CODE_TASK_LIST_ID` を読むため、`nonexistent` が未知と判定されて警告が出る

- [ ] **Step 3: 実装を変える**

`home/.zshrc` の `_claude_task_list_notice()` を差し替える。

```zsh
# タスクリスト ID が未知なら知らせる。Claude Code は未知の ID でも黙って新しいリストを
# 作るため、typo は「履歴が分裂している」形でしか後から気づけない。
# 新規作成そのものは正当な操作なのでブロックはしない。
# ID は呼び出し側が解決した値を受け取る。グローバルを直接読むと、導出した ID ではなく
# 前置の値を見てしまい判定がずれる。
function _claude_task_list_notice() {
  local config_dir="$1"
  local task_list_id="$2"
  [ -n "$task_list_id" ] || return 0
  [ -d "$config_dir/tasks/$task_list_id" ] && return 0
  echo "新しいタスクリストを作成します: $task_list_id" >&2
}
```

- [ ] **Step 4: 呼び出し側を新しい形へ揃える**

引数が 1 つのままだと第 2 引数が未設定になり、ランチャ経由のテストが落ちる。同じコミット内で揃える。この時点では導出をまだ入れず、これまでどおりグローバルの値を明示的に渡すだけにする。挙動は変わらない。

```zsh
  _claude_task_list_notice "$config_dir" "$CLAUDE_CODE_TASK_LIST_ID"
```

`claude()` と `claude-hamiltonian()` の両方を書き換える。

- [ ] **Step 5: 緑を確認する**

Run: `bats scripts/tests/*.bats`
Expected: 全件 ok / 0 not ok / 0 warnings。挙動を変えないリファクタなので、既存テストは 1 件も落ちない

- [ ] **Step 6: 変異注入で pin を確認する**

| 変異 | 赤くなるべきテスト |
| --- | --- |
| `local task_list_id="$2"` を `local task_list_id="$CLAUDE_CODE_TASK_LIST_ID"` に戻す | ignores the ambient environment variable |
| `[ -n "$task_list_id" ] \|\| return 0` を削る | stays silent when no task list id is given |

- [ ] **Step 7: コミット**

```bash
rm -rf .cache/mutation
git add home/.zshrc scripts/tests/zshrc-claude.bats
git commit -F .cache/commit-t3.txt
```

---

### Task 4: ランチャから導出を使う

**Files:**
- Modify: `home/.zshrc` (`claude()` と `claude-hamiltonian()`)
- Test: `scripts/tests/zshrc-claude.bats`

**Interfaces:**
- Consumes: `_claude_task_list_id()` (Task 2)、`_claude_task_list_notice <dir> <id>` (Task 3)
- Produces: 起動時に `CLAUDE_CODE_TASK_LIST_ID` を子プロセスへ渡す。前置で指定された値があればそちらを使う

- [ ] **Step 1: 失敗するテストを書く**

`claude (個人アカウント)` 節と `claude-hamiltonian (仕事アカウント)` 節にそれぞれ追加する。

```bash
@test "claude: passes the derived task list id to the binary" {
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" claude

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "TASK_LIST=myrepo"
}

@test "claude: lets an explicit task list id win over derivation" {
    # 導出は既定であって強制ではない。別のリストを指定して起動する余地を残す
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=explicit run_in_dir "$TEST_HOME/myrepo" claude

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "TASK_LIST=explicit"
    refute_contains "$recorded" "TASK_LIST=myrepo"
}

@test "claude: leaves the variable unset when nothing can be derived" {
    # 空文字を渡したときの Claude Code の挙動は未確認。未確認の前提に賭けず、
    # 導出できないときは既定のセッション ID リストに任せる
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir / claude

    [ "$status" -eq 0 ]
    refute_contains "$(cat "$RECORDED_LAUNCH")" "TASK_LIST="
}

@test "claude: warns about a derived task list that does not exist yet" {
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" claude

    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: myrepo"
}

@test "claude-hamiltonian: passes the derived task list id to the binary" {
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" claude-hamiltonian

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-hamiltonian"
    assert_contains "$recorded" "TASK_LIST=myrepo"
}

@test "claude-hamiltonian: leaves the variable unset when nothing can be derived" {
    # 空ガードは 2 つのランチャに重複して存在する。片方だけを pin すると
    # もう片方は変異させても緑のままになり、仕事アカウントだけが退行できてしまう
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir / claude-hamiltonian

    [ "$status" -eq 0 ]
    refute_contains "$(cat "$RECORDED_LAUNCH")" "TASK_LIST="
}
```

既存の `claude-hamiltonian: passes the task list id through to the binary` は前置指定の経路を pin する意図だが、前置値 `dotfiles` がこのリポジトリ自身の名前と一致する。bats はリポジトリルートで走るので導出値も `dotfiles` になり、前置が効いたのか導出が効いたのかを区別できない。前置を完全に無視する変異を入れても緑のままになる。衝突しない値へ変え negative case を足す。

```bash
@test "claude-hamiltonian: passes the task list id through to the binary" {
    mkdir -p "$TEST_HOME/.claude-hamiltonian/tasks/explicit"
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    # アカウント (関数) とタスクリスト (前置) が直交して合成できることを pin する。
    # 前置値は導出値と衝突しない名前にする
    CLAUDE_CODE_TASK_LIST_ID=explicit run_in_dir "$TEST_HOME/myrepo" claude-hamiltonian

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-hamiltonian"
    assert_contains "$recorded" "TASK_LIST=explicit"
    refute_contains "$recorded" "TASK_LIST=myrepo"
}
```

- [ ] **Step 2: 赤を確認する**

Run: `bats scripts/tests/zshrc-claude.bats`
Expected: 新規 6 件のうち 3 件 (`claude` / `claude-hamiltonian` の derived id と警告) が not ok。残り 3 件と強化した既存 1 件は緑のまま。変更前のランチャは前置値を素通しするだけなので、前置ありのテストは素通しで満たされ、前置なしのテストは「何もセットしない」ことで満たされてしまう。加えて Task 3 の変更でランチャ経由の警告テストも not ok になっている

赤が想定より少ないこと自体は dead pin の証拠ではない。pin が生きているかは Step 5 の変異注入だけが答える

- [ ] **Step 3: ランチャを更新する**

`home/.zshrc` の 2 つの関数を差し替える。

```zsh
function claude() {
  local config_dir task_list
  config_dir="$(_claude_config_dir)" || return 1
  task_list="${CLAUDE_CODE_TASK_LIST_ID:-$(_claude_task_list_id)}"
  _claude_task_list_notice "$config_dir" "$task_list"
  # 空文字を渡したときの挙動は未確認。導出できないときは変数ごと渡さず既定に任せる
  if [ -n "$task_list" ]; then
    CLAUDE_CODE_TASK_LIST_ID="$task_list" command claude "$@"
  else
    command claude "$@"
  fi
}

# 仕事アカウント。アカウントを固定するのが存在理由なので、外から前置で
# CLAUDE_CONFIG_DIR が渡されていても自分のディレクトリを引数で名指しする。
function claude-hamiltonian() {
  local config_dir task_list
  config_dir="$(_claude_config_dir "$HOME/.claude-hamiltonian")" || return 1
  task_list="${CLAUDE_CODE_TASK_LIST_ID:-$(_claude_task_list_id)}"
  _claude_task_list_notice "$config_dir" "$task_list"
  # 空文字を渡したときの挙動は未確認。導出できないときは変数ごと渡さず既定に任せる
  if [ -n "$task_list" ]; then
    CLAUDE_CONFIG_DIR="$config_dir" CLAUDE_CODE_TASK_LIST_ID="$task_list" command claude "$@"
  else
    CLAUDE_CONFIG_DIR="$config_dir" command claude "$@"
  fi
}
```

`claude()` の既存コメントは保つ。空ガードを入れる理由はコード側のコメントに置く。テストファイルにしか書かないと `.zshrc` を読む人には伝わらない。

- [ ] **Step 4: 緑を確認する**

Run: `bats scripts/tests/*.bats`
Expected: 全件 ok / 0 not ok / 0 warnings

- [ ] **Step 5: 変異注入で pin を確認する**

空ガードと優先順位は 2 つのランチャに重複して存在する。片方で測って済ませず、両方に同じ変異を入れる。

| 変異 | 対象 | 赤くなるべきテスト |
| --- | --- | --- |
| `${CLAUDE_CODE_TASK_LIST_ID:-$(_claude_task_list_id)}` を `$(_claude_task_list_id)` に変える | `claude` | lets an explicit task list id win over derivation |
| 同上 | `claude-hamiltonian` | claude-hamiltonian: passes the task list id through to the binary |
| `${CLAUDE_CODE_TASK_LIST_ID:-...}` を `${CLAUDE_CODE_TASK_LIST_ID}` に変える | 両方 | passes the derived task list id (claude / claude-hamiltonian) |
| `if [ -n "$task_list" ]` を `if true` に変える | `claude` | claude: leaves the variable unset when nothing can be derived |
| 同上 | `claude-hamiltonian` | claude-hamiltonian: leaves the variable unset when nothing can be derived |
| `_claude_task_list_notice "$config_dir" "$task_list"` の第 2 引数を落とす | `claude` | warns about a derived task list that does not exist yet |

変異は 1 つずつ隔離して入れる。同時に入れると片方がもう片方の効果を隠し、生きた pin を dead と誤読する。表は最低限赤くなるべきテストで、付随して他のテストも赤くなることはある。

- [ ] **Step 6: 実機の zsh で full chain を確認する**

環境の継承を落として実行する。このセッションは `claude-hamiltonian` 起動なので `CLAUDE_CONFIG_DIR` と `CLAUDE_CODE_TASK_LIST_ID` が環境に載っており、落とさないと導出経路を測れない。

```bash
E () { env -u CLAUDE_CONFIG_DIR -u CLAUDE_CODE_TASK_LIST_ID zsh -ic "$1" 2>&1; }
E 'cd ~/Develop/dotfiles && claude --version'
E 'cd ~/Develop/dotfiles/scripts && claude --version'
E 'cd ~/Develop/dotfiles && CLAUDE_CODE_TASK_LIST_ID=explicit claude --version'
E 'cd ~/Develop/dotfiles && claude-hamiltonian --version'
```

Expected:
- リポジトリルートとサブディレクトリのどちらでも警告が出ない (`dotfiles` は既存のため)
- 明示指定では `新しいタスクリストを作成します: explicit`
- `--version` はセッションを開かないのでリストの実体は作られない。`ls ~/.claude/tasks` で `explicit` が無いことを確認する

- [ ] **Step 7: コミット**

```bash
rm -rf .cache/mutation
git add home/.zshrc scripts/tests/zshrc-claude.bats
git commit -F .cache/commit-t4.txt
```

---

### Task 5: 移行スクリプトを書き dry-run で計画を出す

**Files:**
- Create: `.cache/migrate-task-lists.sh` (リポジトリには入れない)

**Interfaces:**
- Consumes: Task 2 と同じ導出ロジック (`git rev-parse --show-toplevel` → basename、失敗したら cwd の basename)
- Produces: `DRY_RUN=true bash .cache/migrate-task-lists.sh` が移行計画を表示する。`DRY_RUN=false` で適用する

- [ ] **Step 1: バックアップを取る**

移行の前に必ず実行する。以降のどの手順で失敗しても戻せる状態を先に作る。

```bash
mkdir -p ~/.claude/backups
tar -czf ~/.claude/backups/tasks-before-migration.tar.gz -C ~/.claude tasks
tar -tzf ~/.claude/backups/tasks-before-migration.tar.gz | head -3
```

Expected: アーカイブの中身が一覧できる。`tasks/` 配下が入っていること

- [ ] **Step 2: スクリプトを Write で書く**

日本語コメントを含むため heredoc は使わない (Bash コマンド文字列を通ると confusable_text で弾かれる)。Write ツールでファイルを作る。

```bash
#!/usr/bin/env bash
# タスクリストを導出名へ寄せる 1 回きりの移行。
# 移行先は実行時の導出ロジックと同じ手順で求める。projects/ のディレクトリ名は
# パス区切りと名前中のハイフンを区別できない非可逆エンコードなので、デコードせず
# セッション jsonl に記録された cwd を読む。
set -uo pipefail

CLAUDE_HOME="$HOME/.claude"
TASKS="$CLAUDE_HOME/tasks"
DRY_RUN="${DRY_RUN:-true}"

derive() {  # $1 = cwd
  local dir
  dir="$(git -C "$1" rev-parse --show-toplevel 2>/dev/null)" || dir="$1"
  printf '%s' "${dir##*/}"
}

open_count() {  # $1 = リストのディレクトリ
  find "$1" -name '[0-9]*.json' -exec jq -r 'select(.status != "completed") | .id' {} \; 2>/dev/null | wc -l | tr -d ' '
}

# src の全タスクを dst へ移す。src の id は 1..highwatermark なので、dst の
# highwatermark を足すだけで衝突しない写像になる。blocks / blockedBy も同じ量だけずらす。
merge_list() {  # $1 = src, $2 = dst
  local src="$1" dst="$2" offset newid f maxid src_hw
  mkdir -p "$dst"
  offset=$(cat "$dst/.highwatermark" 2>/dev/null || echo 0)
  maxid=$offset
  for f in "$src"/[0-9]*.json; do
    [ -e "$f" ] || continue
    newid=$(( $(basename "$f" .json) + offset ))
    [ "$newid" -gt "$maxid" ] && maxid=$newid
    jq --argjson off "$offset" '
      .id = ((.id | tonumber) + $off | tostring)
      | .blocks = [.blocks[] | ((. | tonumber) + $off | tostring)]
      | .blockedBy = [.blockedBy[] | ((. | tonumber) + $off | tostring)]
    ' "$f" > "$dst/$newid.json"
  done
  # 実際に書いた最大 id と、移送元の highwatermark をずらした値の大きい方を採る。
  # 前者だけだと移送元の完了済みが一括削除された後で採番が巻き戻り、後者だけだと
  # 移送元に highwatermark が無いときに書き込んだ id より小さい値になる
  src_hw=$(cat "$src/.highwatermark" 2>/dev/null || echo 0)
  [ $(( offset + src_hw )) -gt "$maxid" ] && maxid=$(( offset + src_hw ))
  echo "$maxid" > "$dst/.highwatermark"
  rm -rf "$src"
}

cd "$TASKS" || exit 1
for d in */; do
  id="${d%/}"
  open=$(open_count "$d")
  [ "$open" -eq 0 ] && continue

  hit=$(find "$CLAUDE_HOME/projects" -maxdepth 2 -name "${id}.jsonl" 2>/dev/null | head -1)
  if [ -z "$hit" ]; then
    printf 'SKIP      %-38s open=%-3s (not a session id)\n' "$id" "$open"
    continue
  fi
  cwd=$(jq -r 'select(.cwd != null) | .cwd' "$hit" 2>/dev/null | sort -u | head -1)
  if [ -z "$cwd" ] || [ ! -d "$cwd" ]; then
    printf 'TRIAGE    %-38s open=%-3s (cwd gone)\n' "$id" "$open"
    continue
  fi

  dest="$(derive "$cwd")"
  if [ "$dest" = "$id" ]; then
    printf 'NOOP      %-38s open=%-3s\n' "$id" "$open"
  elif [ ! -d "$dest" ]; then
    printf 'RENAME    %-38s -> %s\n' "$id" "$dest"
    [ "$DRY_RUN" = false ] && mv "$id" "$dest"
  else
    printf 'MERGE     %-38s -> %s\n' "$id" "$dest"
    [ "$DRY_RUN" = false ] && merge_list "$id" "$dest"
  fi
done
```

- [ ] **Step 3: dry-run で計画を確認する**

Run: `DRY_RUN=true bash .cache/migrate-task-lists.sh | awk '{print $1}' | sort | uniq -c`
Expected: 実測済みの内訳と一致すること。

| ラベル | 件数 | 意味 |
| --- | --- | --- |
| MERGE | 4 | 移行先が既に存在する。採番をずらして統合する |
| RENAME | 1 | 移行先が未作成。ディレクトリ名を変えるだけ |
| TRIAGE | 3 | 記録された cwd が現存しない。内容で仕分ける |
| MANUAL | 4 | セッション ID ではない (手で名付けたリスト)。移行先を機械的に決められない |

一致しなければ実行に進まない。導出ロジックか棚卸しのどちらかが間違っている。

`NOOP` は移行先が自分自身になった場合の分岐で、現状のデータでは発生しない。出た場合は
セッション ID リストが既に導出名を名乗っていることを意味し、そのまま何もしなくてよい

- [ ] **Step 4: 移行前の未完了 subject 集合を記録する**

```bash
find ~/.claude/tasks -name '[0-9]*.json' -exec jq -r 'select(.status != "completed") | .subject' {} \; | sort > .cache/open-before.txt
wc -l < .cache/open-before.txt
```

Expected: 未完了の件数が出る (dotfiles のぶんを含む)

---

### Task 6: 移行を適用して検証する

**Files:**
- Modify: `~/.claude/tasks/` (ローカルデータ。リポジトリ外)

**Interfaces:**
- Consumes: Task 5 のスクリプトとバックアップ

- [ ] **Step 1: MANUAL 対象が既に導出名と一致しているか確認する**

手で名付けたリストは移行先を機械的に決められない。それぞれが指すリポジトリで導出名を出し、
リスト名と一致するか目で確かめる。一致しないものは RENAME 相当の手当てが要る。

```bash
DRY_RUN=true bash .cache/migrate-task-lists.sh | awk '$1=="MANUAL"{print $2}'
# 出た各 ID について、対応するリポジトリの場所を思い出して
env -u CLAUDE_CONFIG_DIR zsh -ic 'cd <そのリポジトリ> && _claude_task_list_id; echo'
```

Expected: 導出名がリスト名と一致すること。一致しないリストは `mv` で名前を合わせる。
検証用に作られただけで対応するリポジトリが無いものは、Step 2 の仕分けに回す

- [ ] **Step 2: TRIAGE 対象の未完了を一覧で出す**

cwd が現存しない 3 本は移行先が機械的に決まらない。中身を見て移送先を決める。

```bash
for u in $(DRY_RUN=true bash .cache/migrate-task-lists.sh | awk '$1=="TRIAGE"{print $2}'); do
  echo "--- $u ---"
  find ~/.claude/tasks/"$u" -name '[0-9]*.json' -exec jq -r 'select(.status != "completed") | "[\(.status)] \(.subject)"' {} \;
done
```

- [ ] **Step 3: 仕分けの結果をユーザーに確認する**

AskUserQuestion で、生きている項目とその移送先を確認する。判断はユーザーのもので、エージェントが代わりに決めない

- [ ] **Step 4: 仕分けの結果を適用する**

生かす項目は移送先リストへ `merge_list` と同じ採番規則で移す。捨てる項目を含むリストは `rm -rf` する。バックアップがあるので取り返しはつく

- [ ] **Step 5: 自動移行を適用する**

Run: `DRY_RUN=false bash .cache/migrate-task-lists.sh`
Expected: RENAME と MERGE が実行され、dry-run と同じ行が出る

- [ ] **Step 6: 未完了 subject 集合が保たれたことを確認する**

```bash
find ~/.claude/tasks -name '[0-9]*.json' -exec jq -r 'select(.status != "completed") | .subject' {} \; | sort > .cache/open-after.txt
diff .cache/open-before.txt .cache/open-after.txt
```

Expected: 差分は Step 3 で意図的に捨てた項目のみ。それ以外の差分があれば移行に欠落がある

- [ ] **Step 7: 採番の衝突が無いことを確認する**

```bash
for d in ~/.claude/tasks/*/; do
  n=$(ls "$d" | grep -c '^[0-9]*\.json$')
  u=$(ls "$d" | grep '^[0-9]*\.json$' | sort -u | wc -l | tr -d ' ')
  [ "$n" != "$u" ] && echo "duplicate ids in $d"
done
echo "checked"
```

Expected: `duplicate ids` の行が出ないこと

- [ ] **Step 8: 依存の張り替えが壊れていないことを確認する**

```bash
for d in ~/.claude/tasks/*/; do
  ids=$(ls "$d" | grep '^[0-9]*\.json$' | sed 's/\.json$//' | sort)
  refs=$(find "$d" -name '[0-9]*.json' -exec jq -r '.blocks[], .blockedBy[]' {} \; 2>/dev/null | sort -u)
  for r in $refs; do
    echo "$ids" | grep -qx "$r" || echo "dangling ref $r in $d"
  done
done
echo "checked"
```

Expected: `dangling ref` が出ないこと。出た場合は完了済みが一括削除された後のリストである可能性があるので、そのリストの中身を確認してから判断する

- [ ] **Step 9: 実機で起動して読めることを確認する**

```bash
env -u CLAUDE_CONFIG_DIR -u CLAUDE_CODE_TASK_LIST_ID zsh -ic 'cd ~/Develop/dotfiles && claude --version'
```

Expected: 警告が出ない (dotfiles リストは存在するため)

- [ ] **Step 10: Issue のタスクを更新してコミットする**

`.cache/` の一時ファイルは移行完了後に削除する。リポジトリに残すのは Issue とプランの更新のみ

---

## 検証の締め

- [ ] `bats scripts/tests/*.bats` が全件 ok / 0 not ok / 0 warnings
- [ ] `shellcheck` を含む pre-commit フックが全て Passed
- [ ] 変異注入で追加した pin が全て赤くなる
- [ ] 実機の zsh で導出・前置優先・非リポジトリ・空の 4 経路を確認
- [ ] 移行前後で未完了 subject 集合の差分が意図した分だけ
