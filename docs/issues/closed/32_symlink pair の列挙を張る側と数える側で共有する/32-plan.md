# symlink pair の列挙共有 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** symlink pair の列挙を単一の生成器へ寄せ、張る側と数える側の不一致を突き合わせテストで検出できるようにする。

**Architecture:** `symlink_pairs_for <category>` を 1 つ置き、既存の 3 箇所 (`setup_dotfiles` / `setup_apm_symlinks` / `current_symlink_targets`) をその消費者にする。あわせて設定ファイルの行判定を述語へ切り出し、却下行の警告を `main` の 1 回に集約する。検出は `main --dry-run` の出力から「張った target」を抽出し、`current_symlink_targets` の部分集合であることを検証する統合テストで行う。

**Tech Stack:** bash 3.2 (macOS 標準)、bats-core、pre-commit、shellcheck

## Global Constraints

- 対象は `/bin/bash` 3.2。空配列の `"${arr[@]}"` は `set -u` 下で unbound variable になるため使わない (既存コードが `"$@"` を使っている理由がこれ)
- `bootstrap.sh` は `set -euo pipefail`。非 0 を返す関数を単独で呼ぶとスクリプトごと終了する。戻り値を読むときは `local kind=0; f "$x" || kind=$?` の形にする (`||` の文脈では `set -e` が発動しない)
- pair のフォーマットは `source|target` のまま変えない
- コード内のコメントは日本語で書く
- コミット本文は Write でファイルへ書き `git commit -F <file>` で渡す。Bash のコマンド文字列に日本語の散文を載せない
- テストの判定は exit code ではなく件数で行う。bats は TAP ヘッダ `1..N` と `^ok ` の件数一致、pre-commit は Passed / Failed の件数で見る
- 設定ディレクトリの実名を追跡ファイルへ書かない。テストはダミー名 (`.claude-alpha` 等) を使う
- 新しい関数は `bootstrap.sh` の `# ヘルパー関数` マーカーと `# メイン処理` マーカーの間へ置く。テストの `load_bootstrap_functions` はこの範囲だけを切り出して source するため、範囲外に置くとテストから見えず「関数が無い」で落ちる
- 配列 (`SYMLINK_PAIRS` / `APM_SYMLINK_PAIRS`) はこの範囲より前にあるので `load_bootstrap_functions` では読まれない。配列を使うテストは `load_pairs_array <name>` を別途呼ぶ
- `bootstrap.bats` の `setup()` が既に `load_bootstrap_functions` を呼ぶ。各テストで呼び直さない

---

### Task 1: 設定ファイル行の判定述語を切り出し、警告を 1 回にする

**Files:**
- Modify: `bootstrap.sh:471-486` (`claude_extra_config_dirs`)
- Modify: `bootstrap.sh:942` 付近 (`main` の `setup_dotfiles` 呼び出し直前)
- Test: `scripts/tests/bootstrap.bats`

**Interfaces:**
- Produces: `claude_config_dir_line_kind <line>` — 戻り値 0 (有効) / 1 (無視) / 2 (却下)。stdout へは何も出さない
- Produces: `warn_invalid_claude_config_dir_lines` — 引数なし。却下行を stderr へ verbatim で出す。常に 0 を返す
- Unchanged: `claude_extra_config_dirs` — 引数なし、有効なディレクトリ名を 1 行 1 件で stdout へ。Task 1 以降は警告を出さない

- [ ] **Step 1: 述語の失敗するテストを書く**

`scripts/tests/bootstrap.bats` の `claude_extra_config_dirs` 関連テストの隣に追加する。

```bash
@test "claude_config_dir_line_kind: separates valid, ignorable, and rejected lines" {
    # 有効
    run claude_config_dir_line_kind '.claude-alpha'
    [ "$status" -eq 0 ]
    [ -z "$output" ]

    # 無視 (空行・コメント・既定ディレクトリ)。却下ではないので警告の対象にしない
    run claude_config_dir_line_kind ''
    [ "$status" -eq 1 ]
    run claude_config_dir_line_kind '# comment'
    [ "$status" -eq 1 ]
    run claude_config_dir_line_kind '.claude'
    [ "$status" -eq 1 ]

    # 却下 (文法違反)。-dev 接尾辞は派生名の予約、接頭辞違いは名前空間の外
    run claude_config_dir_line_kind '.claude-alpha-dev'
    [ "$status" -eq 2 ]
    run claude_config_dir_line_kind '.git'
    [ "$status" -eq 2 ]
    run claude_config_dir_line_kind 'alpha'
    [ "$status" -eq 2 ]
    run claude_config_dir_line_kind '.claude-'
    [ "$status" -eq 2 ]
}
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `bats scripts/tests/bootstrap.bats --filter 'claude_config_dir_line_kind' > .cache/t1-red.log 2>&1`

次の呼び出しで `.cache/t1-red.log` を読み、TAP ヘッダが `1..0` でないこと (フィルタが 1 件も一致していない状態ではないこと) と、`not ok 1` が出ていることを確認する。`1..0` なら 0 件実行なので、フィルタ文字列を見直す。

Expected: `1..1` と `not ok 1 claude_config_dir_line_kind: ...` (command not found で落ちる)

- [ ] **Step 3: 述語を実装する**

`bootstrap.sh` の `claude_extra_config_dirs` の直前へ置く。

```bash
# 設定ファイルの 1 行を分類する。0 = 有効、1 = 無視 (空行・コメント・既定ディレクトリ)、
# 2 = 却下 (文法違反)。行を吐く側と警告する側が同じ述語を使うことで、文法が二重管理に
# ならない。文法の canonical はここ 1 箇所で、home/.zshrc 側との一致は parity テストが守る。
# 戻り値を読む側は set -e に注意すること。単独で呼ぶと 1 や 2 でスクリプトごと終了する。
claude_config_dir_line_kind() {
    case "$1" in
        '' | '#'* | '.claude') return 1 ;;
    esac
    if [ "$1" != "${1%-dev}" ] \
        || ! printf '%s' "$1" | grep -Eq '^\.claude-[A-Za-z0-9._-]+$'; then
        return 2
    fi
    return 0
}
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `bats scripts/tests/bootstrap.bats --filter 'claude_config_dir_line_kind' > .cache/t1-green.log 2>&1`

次の呼び出しでログを読み、`1..1` と `ok 1` を確認する。

- [ ] **Step 5: 警告が 1 回であることの失敗するテストを書く**

```bash
@test "main: reports a rejected config dir line exactly once" {
    # 却下行の警告は claude_extra_config_dirs が 1 回の実行で複数回呼ばれるぶんだけ
    # 並んでいた。設計意図 (却下行を verbatim で知らせる) がノイズに沈むため、
    # 警告を main の 1 回へ集約する。件数で pin するのは「出ている」だけでは
    # 回数の退行を捕まえられないため
    write_config_dirs_file '.claude-alpha' '.git'

    run bash "$BOOTSTRAP_SCRIPT" --dry-run --dotfiles-only

    [ "$status" -eq 0 ]
    local count
    count="$(printf '%s\n' "$output" | grep -c '受け付けられない行を無視します: \.git')"
    [ "$count" -eq 1 ]

    # 対照: 有効な行は警告されず、mirror は張られる (警告 0 件が「そもそも読んで
    # いない」ではないことの確認)
    assert_contains "$output" "$TEST_HOME/.claude-alpha/settings.json"
}
```

- [ ] **Step 6: テストが失敗することを確認する**

Run: `bats scripts/tests/bootstrap.bats --filter 'reports a rejected config dir line' > .cache/t1b-red.log 2>&1`

次の呼び出しでログを読む。Expected: `1..1` と `not ok`。現状は警告が複数回出るため件数が 1 を超えて落ちる。落ちた行の実測値もログで確認しておく (集約後にゼロへ落ちていないことの対照になる)。

- [ ] **Step 7: `claude_extra_config_dirs` を述語ベースへ書き換える**

既存の本体を次で置き換える。警告はここから除く。

```bash
claude_extra_config_dirs() {
    [ -f "$CLAUDE_CONFIG_DIRS_FILE" ] || return 0

    # 無視も却下もここでは黙って落とす。却下行の通知は
    # warn_invalid_claude_config_dir_lines が持ち main が 1 回だけ呼ぶ。
    # この関数はプロセス置換から何度も呼ばれるので、ここで警告すると同じ内容が並ぶ
    local line
    while IFS= read -r line || [ -n "$line" ]; do
        claude_config_dir_line_kind "$line" || continue
        printf '%s\n' "$line"
    done < "$CLAUDE_CONFIG_DIRS_FILE"
}
```

関数直前のコメントのうち「黙って捨てると設定の typo に気づけないため、却下行は verbatim で stderr へ出す。」の 1 文は、責務が移ったので `warn_invalid_claude_config_dir_lines` 側へ移す。

- [ ] **Step 8: 警告関数を追加する**

`claude_extra_config_dirs` の直後へ置く。

```bash
# 却下行を verbatim で stderr へ出す。黙って捨てると設定の typo に気づけない。
# main が 1 回だけ呼ぶ。判定は claude_config_dir_line_kind が canonical で、
# ここは通知だけを持つ。
# 戻り値の受け方に注意。set -e 下では述語を単独で呼ぶと 1 や 2 で即終了するため、
# || で受けて $? を読む
warn_invalid_claude_config_dir_lines() {
    [ -f "$CLAUDE_CONFIG_DIRS_FILE" ] || return 0

    local line kind
    while IFS= read -r line || [ -n "$line" ]; do
        kind=0
        claude_config_dir_line_kind "$line" || kind=$?
        if [ "$kind" -eq 2 ]; then
            warn "設定ディレクトリ名として受け付けられない行を無視します: $line"
        fi
    done < "$CLAUDE_CONFIG_DIRS_FILE"
    return 0
}
```

- [ ] **Step 9: `main` へ結線する**

`bootstrap.sh` の `main` 内、`# dotfiles セットアップ` コメントと `setup_dotfiles` の直前へ 2 行を挿入する。

```bash
    # 設定ファイルの却下行をここで 1 回だけ知らせる。以降の読み取りは黙ってフィルタする
    warn_invalid_claude_config_dir_lines

    # dotfiles セットアップ
    setup_dotfiles
```

`--dotfiles-only` でも走らせる (設定ファイルはどちらの経路でも読まれるため、gate の外へ置く)。

- [ ] **Step 10: テストが通ることを確認する**

Run: `bats scripts/tests/bootstrap.bats > .cache/t1-all.log 2>&1`

次の呼び出しでログを読み、TAP ヘッダの `1..N` と `^ok ` の件数が一致し `not ok` が 0 件であることを確認する。

- [ ] **Step 11: 変異注入で pin が生きていることを確認する**

1 度に 1 箇所ずつ入れる。同時に入れると片方がもう片方を隠す。

変異 A: `warn_invalid_claude_config_dir_lines` の `main` からの呼び出し行を削除する。Step 5 のテストが赤くなること (警告 0 件で `-eq 1` に落ちる) を確認し、元へ戻す。

変異 B: `claude_config_dir_line_kind` の `-dev` 判定を落とす (`[ "$1" != "${1%-dev}" ] ||` を削る)。Step 1 のテストが赤くなること (`.claude-alpha-dev` が 2 でなく 0 になる) を確認し、元へ戻す。

復元は `cp` で取ったバックアップから戻す。`git checkout -- bootstrap.sh` は使わない (このタスクの未コミット編集ごと巻き戻すため)。

```bash
cp bootstrap.sh .cache/bootstrap.sh.bak
# 変異を入れて bats を回す
cp .cache/bootstrap.sh.bak bootstrap.sh
```

- [ ] **Step 12: コミット**

```bash
git add bootstrap.sh scripts/tests/bootstrap.bats
git commit -F .cache/commit-t1.txt
```

`.cache/commit-t1.txt` の内容 (Write で作る):

```
refactor: 設定ファイル行の判定を述語へ切り出し却下行の警告を 1 回にする

claude_extra_config_dirs は 1 回の bootstrap 実行で複数回呼ばれるため、却下行の警告が
同じ内容で並んでいた。呼び出しが全てプロセス置換でメモ化が成立しない (サブシェル内の
グローバル代入は親へ戻らない) ので、判定を claude_config_dir_line_kind へ切り出し、
行を吐く側は黙ってフィルタ、警告は main が 1 回だけ鳴らす形にした。

述語が canonical なので文法は二重管理にならない。
```

---

### Task 2: pair の単一生成器を置き、3 箇所を消費者にする

**Files:**
- Modify: `bootstrap.sh` (`claude_home_symlink_pairs` の直後へ `symlink_pairs_for` を追加)
- Modify: `bootstrap.sh:580-591` (`setup_apm_symlinks`)
- Modify: `bootstrap.sh:593-631` (`setup_dotfiles`)
- Modify: `bootstrap.sh:637-654` (`current_symlink_targets`)
- Test: `scripts/tests/bootstrap.bats`

**Interfaces:**
- Consumes: `claude_mirror_pairs <dir> <pair>...`、`claude_home_symlink_pairs`、`claude_extra_config_dirs` (Task 1 で警告を外した版)
- Produces: `symlink_pairs_for <category>` — `repo` / `apm` / `home` / `all` を受け、`source|target` を 1 行 1 件で stdout へ。未知のカテゴリは `error` で報告して 1 を返す

- [ ] **Step 1: 生成器の失敗するテストを書く**

```bash
@test "symlink_pairs_for: yields each category and rejects an unknown one" {
    load_pairs_array SYMLINK_PAIRS
    load_pairs_array APM_SYMLINK_PAIRS
    write_config_dirs_file '.claude-alpha'

    # repo: 配列本体と、そこから導出した mirror の両方
    run symlink_pairs_for repo
    [ "$status" -eq 0 ]
    assert_array_contains 'home/.zshrc|.zshrc' "${lines[@]}"
    assert_array_contains 'home/.claude/settings.json|.claude-alpha/settings.json' "${lines[@]}"
    # apm 由来は repo に混ざらない
    refute_contains "$output" 'home/.claude/skills|'

    # apm: 配列本体と mirror
    run symlink_pairs_for apm
    [ "$status" -eq 0 ]
    assert_array_contains 'home/.claude/skills|.claude/skills' "${lines[@]}"
    assert_array_contains 'home/.claude/skills|.claude-alpha/skills' "${lines[@]}"
    refute_contains "$output" '|.zshrc'

    # home: ホーム内で完結する pair だけ
    run symlink_pairs_for home
    [ "$status" -eq 0 ]
    [ "$output" = '.claude/tasks|.claude-alpha/tasks' ]

    # all: 3 カテゴリの合併。件数で部分集合ではなく合併であることを見る
    run symlink_pairs_for all
    [ "$status" -eq 0 ]
    local repo_n apm_n home_n all_n
    repo_n="$(symlink_pairs_for repo | wc -l | tr -d ' ')"
    apm_n="$(symlink_pairs_for apm | wc -l | tr -d ' ')"
    home_n="$(symlink_pairs_for home | wc -l | tr -d ' ')"
    all_n="$(symlink_pairs_for all | wc -l | tr -d ' ')"
    [ "$all_n" -eq "$((repo_n + apm_n + home_n))" ]

    # 未知のカテゴリは黙って空を返さない。空だと「対象 0 件」と区別が付かない
    run symlink_pairs_for bogus
    [ "$status" -ne 0 ]
    assert_contains "$output" 'bogus'
}
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `bats scripts/tests/bootstrap.bats --filter 'symlink_pairs_for' > .cache/t2-red.log 2>&1`

次の呼び出しでログを読み、`1..0` でないことと `not ok 1` を確認する。

- [ ] **Step 3: 生成器を実装する**

`claude_home_symlink_pairs` の直後へ置く。

```bash
# カテゴリ別に symlink pair (source|target) を 1 行 1 件で出力する単一の生成器。
# 張る側 (setup_dotfiles / setup_apm_symlinks) と数える側 (current_symlink_targets) が
# ここから取ることで、供給カテゴリを足したときの編集箇所が 1 関数へ閉じる。
# カテゴリの分け方の基準は source の性質。repo の source は git 管理下で必ず実在し、
# apm の source は apm install が配置するまで存在せず、home の source は未追跡の
# ローカル状態で無ければ張る側が作る。張る側がこの違いで分岐するため境界をここに合わせた。
# 未知のカテゴリで空を返さないのは、呼び出し側から「対象が 0 件」と区別が付かないため。
symlink_pairs_for() {
    local category="$1"
    local dir

    case "$category" in
        repo)
            printf '%s\n' "${SYMLINK_PAIRS[@]}"
            while IFS= read -r dir; do
                claude_mirror_pairs "$dir" "${SYMLINK_PAIRS[@]}"
            done < <(claude_extra_config_dirs)
            ;;
        apm)
            printf '%s\n' "${APM_SYMLINK_PAIRS[@]}"
            while IFS= read -r dir; do
                claude_mirror_pairs "$dir" "${APM_SYMLINK_PAIRS[@]}"
            done < <(claude_extra_config_dirs)
            ;;
        home)
            claude_home_symlink_pairs
            ;;
        all)
            symlink_pairs_for repo
            symlink_pairs_for apm
            symlink_pairs_for home
            ;;
        *)
            error "Unknown symlink pair category: $category"
            return 1
            ;;
    esac
}
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `bats scripts/tests/bootstrap.bats --filter 'symlink_pairs_for' > .cache/t2-green.log 2>&1`

次の呼び出しでログを読み `ok` を確認する。

- [ ] **Step 5: `setup_apm_symlinks` を消費者にする**

本体を次で置き換える。

```bash
setup_apm_symlinks() {
    local pair
    while IFS= read -r pair; do
        create_apm_symlink "$pair"
    done < <(symlink_pairs_for apm)
}
```

関数直前のコメントのうち mirror の導出方法を説明した部分は、生成器へ移ったので「pair は symlink_pairs_for apm から取る」に置き換える。source 存在ガードを持つ理由と、`install_apm_packages` の後でなければならない理由の記述は残す。

- [ ] **Step 6: `setup_dotfiles` を消費者にする**

symlink 作成部分 (現在の `for pair in "${SYMLINK_PAIRS[@]}"` から `claude_home_symlink_pairs` のループまで) を次で置き換える。

```bash
    # リポジトリを source とする symlink (追加設定ディレクトリ向けの mirror を含む)
    local pair source target
    while IFS= read -r pair; do
        source="$DOTFILES_DIR/${pair%%|*}"
        target="$HOME/${pair##*|}"
        create_symlink "$source" "$target"
    done < <(symlink_pairs_for repo)

    # ホーム内で完結する共有リンク。source が無ければ setup_home_symlinks が作る
    while IFS= read -r pair; do
        setup_home_symlinks "$pair"
    done < <(symlink_pairs_for home)
```

- [ ] **Step 7: `current_symlink_targets` を消費者にする**

本体を次で置き換える。

```bash
current_symlink_targets() {
    local pair
    while IFS= read -r pair; do
        printf '%s\n' "${pair##*|}"
    done < <(symlink_pairs_for all)
}
```

関数直前のコメントは「集合を配列の直読みだけで組むと生成分が漏れる」という警句を残しつつ、供給元が `symlink_pairs_for all` になったことを書く。

- [ ] **Step 8: 全テストが通ることを確認する**

Run: `bats scripts/tests/bootstrap.bats > .cache/t2-all.log 2>&1`

次の呼び出しでログを読み、TAP プランと `ok` の件数一致、`not ok` 0 件を確認する。ここで既存テストが落ちた場合は生成器の出力順や重複が原因なので、落ちたテスト名を読んで対処する。

- [ ] **Step 9: 実 shell の live smoke**

Run: `bash bootstrap.sh --dry-run --dotfiles-only > .cache/t2-smoke.log 2>&1`

次の呼び出しでログを読み、`[DRY-RUN] ln -sf` が出ていること、`[ERROR]` が無いこと、`Backed up` が `Linked` の後に並んでいないことを確認する。実機の設定ファイルが存在する環境なので、追加設定ディレクトリ向けの行も出る。設定ディレクトリの実名はログにも報告にも転記しない。

- [ ] **Step 10: コミット**

```bash
git add bootstrap.sh scripts/tests/bootstrap.bats
git commit -F .cache/commit-t2.txt
```

`.cache/commit-t2.txt` の内容 (Write で作る):

```
refactor: symlink pair の列挙を単一の生成器へ寄せる

張る側 2 箇所と数える側 1 箇所が 4 つの供給経路をそれぞれ独立に並べ直していた。
symlink_pairs_for へ寄せ、カテゴリを足すときの編集が 1 関数へ閉じるようにした。

カテゴリの境界は source の性質で切っている。張る側が source の解決規則と存在ガードで
分岐するため、そこへ合わせないと消費側が再び分岐を持つことになる。
```

---

### Task 3: 張った target と数えた target を突き合わせるテストを足す

**Files:**
- Modify: `scripts/tests/bootstrap.bats`
- Test: 同上

**Interfaces:**
- Consumes: `symlink_pairs_for` (Task 2)、`current_symlink_targets` (Task 2 で消費者化済み)、`$BOOTSTRAP_SCRIPT` / `$TEST_HOME` / `$DOTFILES_DIR` (test_helper.bash)

- [ ] **Step 1: 突き合わせテストを書く**

`main` の dry-run 系テストの隣へ追加する。

```bash
@test "main: every target it links is inside the counted target set" {
    # 張る側と数える側が独立に列挙していると、供給カテゴリを片側だけ更新したときに
    # 新カテゴリの target が集合から漏れる。親ディレクトリは既存 target と共有される
    # ため走査対象には入るので、main が setup_dotfiles の直後に呼ぶ prune が
    # 張った直後のリンクを backup へ退避する。exit 0 で完走し、ログに Linked と
    # Backed up が並ぶだけで終状態が壊れるため、集合の包含をここで pin する。
    #
    # 方向は「張った ⊆ 数えた」だけを見る。逆向きは成立しない。フィクスチャには apm が
    # 配置する source が無く apm 分は張られないが、数える側は持つためである。
    # 破壊的なのは「張ったのに数えていない」側だけなので、守る向きはこれで足りる。
    #
    # この機構が覆うのは main --dry-run が通る経路で張られる target に限る。
    # dry-run で分岐して張られない経路 (apm source 不在時の skip) は範囲外。
    write_config_dirs_file '.claude-alpha'

    run bash "$BOOTSTRAP_SCRIPT" --dry-run --dotfiles-only
    [ "$status" -eq 0 ]

    # dry-run の行から target ($HOME 相対) を取り出す。行数と抽出数の一致を見るのは、
    # パスに空白が入ったときに一部が静かに落ちる経路を塞ぐため。落ちた分はエラーでは
    # なく「短い正常な結果」として返るので件数でしか捉えられない
    local link_lines linked_targets link_n target_n
    link_lines="$(printf '%s\n' "$output" | grep -c '^\[DRY-RUN\] ln -sf ')"
    linked_targets="$(printf '%s\n' "$output" \
        | sed -n "s|^\[DRY-RUN\] ln -sf [^ ]* $TEST_HOME/||p")"
    link_n="$link_lines"
    target_n="$(printf '%s\n' "$linked_targets" | grep -c .)"
    [ "$link_n" -gt 0 ]
    [ "$target_n" -eq "$link_n" ]

    # 数える側の集合を同じ条件 (同じ設定ファイル) で作る。関数は setup が読み済みだが
    # 配列はその範囲外にあるのでここで読む
    load_pairs_array SYMLINK_PAIRS
    load_pairs_array APM_SYMLINK_PAIRS
    local counted uncovered
    counted="$(current_symlink_targets)"

    # 張ったのに数えていない target を列挙する。0 件であること
    uncovered="$(printf '%s\n' "$linked_targets" \
        | while IFS= read -r t; do
              [ -n "$t" ] || continue
              printf '%s\n' "$counted" | grep -qxF "$t" || printf '%s\n' "$t"
          done)"
    [ -z "$uncovered" ]
}
```

- [ ] **Step 2: テストが通ることを確認する**

Run: `bats scripts/tests/bootstrap.bats --filter 'inside the counted target set' > .cache/t3-green.log 2>&1`

次の呼び出しでログを読み、`1..1` と `ok 1` を確認する。ここは新規追加した検査が現状の実装で成立することの確認なので、赤から入らない。実際に赤くなることは Step 3 の変異で確かめる。

- [ ] **Step 3: 変異 1 (検査対象を壊す)**

`bootstrap.sh` を `cp bootstrap.sh .cache/bootstrap.sh.bak` で退避してから、`symlink_pairs_for` へ新しいカテゴリを足し、`all` には足さない。

```bash
        probe)
            printf '%s\n' "home/.zshrc|.probe-target"
            ;;
```

さらに `setup_dotfiles` の末尾へ、そのカテゴリを張る 4 行を足す。

```bash
    while IFS= read -r pair; do
        source="$DOTFILES_DIR/${pair%%|*}"
        target="$HOME/${pair##*|}"
        create_symlink "$source" "$target"
    done < <(symlink_pairs_for probe)
```

Run: `bats scripts/tests/bootstrap.bats --filter 'inside the counted target set' > .cache/t3-mut1.log 2>&1`

次の呼び出しでログを読み `not ok` を確認する。確認できたら `cp .cache/bootstrap.sh.bak bootstrap.sh` で戻す。

- [ ] **Step 4: 変異 2 (検査機構そのものを壊す)**

`scripts/tests/bootstrap.bats` を `cp` で退避してから、Step 1 のテストの最後の行 `[ -z "$uncovered" ]` を `true` へ置き換える。

Run: `bats scripts/tests/bootstrap.bats > .cache/t3-mut2.log 2>&1`

次の呼び出しでログを読み、全テストが緑のままであることを確認する。これはこの assertion が唯一の防御であることの確認で、緑が正しい結果になる。確認できたら `cp` で戻す。

- [ ] **Step 5: 変異 3 (取り付けを外す)**

`scripts/tests/bootstrap.bats` を退避してから、Step 1 のテストの `run bash "$BOOTSTRAP_SCRIPT" --dry-run --dotfiles-only` を削除し `output=""` を置く。

Run: `bats scripts/tests/bootstrap.bats --filter 'inside the counted target set' > .cache/t3-mut3.log 2>&1`

次の呼び出しでログを読み `not ok` を確認する。`[ "$link_n" -gt 0 ]` が空回りを止めるので、ここが赤くなれば取り付けが検査されている。確認できたら `cp` で戻す。

- [ ] **Step 6: 全テストが通ることを確認する**

Run: `bats scripts/tests/bootstrap.bats > .cache/t3-all.log 2>&1`

次の呼び出しでログを読み、TAP プランと `ok` の件数一致、`not ok` 0 件を確認する。3 つの変異がすべて復元されていることを `git diff --stat` でも確認する (テストファイルと bootstrap.sh に意図しない残骸が無いこと)。

- [ ] **Step 7: コミット**

```bash
git add scripts/tests/bootstrap.bats
git commit -F .cache/commit-t3.txt
```

`.cache/commit-t3.txt` の内容 (Write で作る):

```
test: 張った target が数えた target の部分集合であることを pin する

供給カテゴリを片側だけ更新すると、張った直後のリンクを同じ実行内で backup へ退避する
破壊的な壊れ方をする。main --dry-run の出力から張った target を抽出し、
current_symlink_targets の集合に含まれることを検証する。

抽出は行数と件数の一致も見る。空白を含むパスで一部が静かに落ちる経路は、エラーではなく
短い正常な結果として返るため件数でしか捉えられない。

変異注入は 3 種で確認した。検査対象を壊すと赤くなり、assertion を無効化しても他の
テストは緑のまま (この検査が唯一の防御であること)、dry-run の実行を外すと空回りせず
赤くなる。
```

---

### Task 4: Issue を更新して PR を出す

**Files:**
- Modify: `docs/issues/32_symlink pair の列挙を張る側と数える側で共有する/issue.md`

- [ ] **Step 1: Issue のタスクを消化済みにする**

`issue.md` の `## タスク` の 4 項目を `- [x]` へ変える。決めた方式 (単一の生成器 + 突き合わせテスト) を 1 項目目の末尾へ括弧書きで残す。

- [ ] **Step 2: 事前状態と同じ検証をもう一度通す**

Run: `bats scripts/tests/ > .cache/t4-bats.log 2>&1`

Run: `pre-commit run --all-files > .cache/t4-precommit.log 2>&1`

次の呼び出しで両方のログを読み、bats は TAP プランと `ok` の件数一致・`not ok` 0 件、pre-commit は Passed の件数と Failed 0 件を確認する。

- [ ] **Step 3: コミットして push**

```bash
git add "docs/issues/32_symlink pair の列挙を張る側と数える側で共有する/issue.md"
git commit -F .cache/commit-t4.txt
git push -u origin refactor/symlink-pair-enumeration
```

push 後は `git ls-remote --heads origin refactor/symlink-pair-enumeration` と `git status -sb` で成否を直接確認する。パイプに繋がない。

- [ ] **Step 4: 品質ゲートを通して PR を作る**

`dev-workflow:pre-merge-quality-gate` を通してから `gh pr create --assignee @me --base main`。PR 本文は Write でファイルへ書き `--body-file` で渡す。本文に `Closes [Issue #32](...)` を入れる。

---

## 実装順序の理由

Task 1 を先に置くのは、Task 2 の集約で `claude_extra_config_dirs` の呼び出しが 5 回から 6 回へ増えるためである。先に警告を 1 回へ集約しておけば、Task 2 で呼び出しが増えても出力は静かなままになる。逆順だと Task 2 の途中で警告が 6 本並ぶ状態を経由する。

Task 3 を Task 2 の後に置くのは、突き合わせテストが `symlink_pairs_for` の存在を前提にするためではなく (前提にはしない。dry-run 出力と `current_symlink_targets` だけを見る)、Task 2 の変更が既存テストを壊していないことを先に確かめてから新しい検査を足すほうが、赤の原因を切り分けやすいためである。
