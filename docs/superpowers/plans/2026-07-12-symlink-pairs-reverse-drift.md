# SYMLINK_PAIRS reverse-drift テスト Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `SYMLINK_PAIRS` の ghostty literal pin を、home/ 配下の全 config が pair でカバーされているか検証する reverse-drift テストへ一般化する。

**Architecture:** 純粋関数 `symlink_target_covered`（file が file pair か dir pair 配下かを transitive に判定）を追加し、それを composing する `uncovered_symlink_targets` で未カバーを列挙、明示 allowlist との集合一致を reverse テストでアサートする。既存 forward テストは残し、ghostty literal pin は削除する。全て `scripts/tests/bootstrap.bats` 内で完結する。

**Tech Stack:** Bats 1.13.0、bash、git ls-files。プロダクションコードは無く test 基盤のみ。

## Global Constraints

- @test 名は ASCII のみ（ast-grep rule `bats-test-name-ascii-only`）。
- bare `[[ ]]` 禁止（ast-grep rule `bats-no-bare-double-bracket`）。アサーションは単純コマンド（関数呼び出しをそのまま実行し 0 で継続・非0 で fail）か `[ ]`、negative は `run` + `[ "$status" -ne 0 ]` で書く。
- コミットメッセージは Conventional Commits プレフィックス。本文は全角約物（、。（））を使わず半角区切り。本プランのコミット subject は ASCII に統一し `-m` で渡す。
- 検査スコープは `home/` 配下のみ、git-tracked ファイルのみ（`git -C "$REPO_ROOT" ls-files 'home/'`）。
- allowlist の canonical 定義は bats の配列。spec の列挙は設計時点のスナップショット。
- ヘルパーは `scripts/tests/bootstrap.bats` の既存 `missing_symlink_sources`（現状 356 行目付近）の直後に置き、SYMLINK_PAIRS 系ヘルパーを 1 箇所へ集約する。
- 事前状態は bats 全 86 tests green。変更後の回帰ゼロを保つ。

---

### Task 1: symlink_target_covered 純粋ヘルパーとユニットテスト

home/ ファイルがいずれかの pair source にカバーされるかを判定する純粋関数を、両方向のユニットテスト付きで追加する。粒度混在（file pair と dir pair）の吸収をこの 1 関数に閉じ込める。

**Files:**
- Modify: `scripts/tests/bootstrap.bats`（`missing_symlink_sources` 関数定義の直後にヘルパーを追加し、`missing_symlink_sources` ユニットテストの後ろに @test を追加）

**Interfaces:**
- Produces: `symlink_target_covered <file> <source>...` — `file` が引数 source 群のいずれかにカバーされれば return 0、なければ return 1。covered = `file` が source と完全一致（file pair）、または `file` が `source/` の配下（dir pair の transitive）。純粋関数でファイル I/O を持たない。

- [ ] **Step 1: 失敗するユニットテストを書く**

`scripts/tests/bootstrap.bats` の `@test "missing_symlink_sources: passes existing and flags missing pairs"` ブロックの直後（現状 393 行目付近）に以下を追加する。

```bash
@test "symlink_target_covered: covers exact and dir-descendant, rejects uncovered and prefix collisions" {
    # 粒度混在の吸収を pin する。file pair は exact 一致、dir pair は配下 (transitive) でカバー。
    local -a srcs=("home/.config/nvim" "home/.config/ghostty/config")
    # 自身が source (file pair) → covered
    symlink_target_covered "home/.config/ghostty/config" "${srcs[@]}"
    # dir pair の配下 (transitive) → covered
    symlink_target_covered "home/.config/nvim/lua/init.lua" "${srcs[@]}"
    # どの source にも属さない → uncovered (false negative を防ぐ negative case)
    run symlink_target_covered "home/.config/herdr/resources/left-arrow.svg" "${srcs[@]}"
    [ "$status" -ne 0 ]
    # prefix 誤爆を防ぐ: config-backup は ghostty/config の配下ではない (末尾 / 境界)
    run symlink_target_covered "home/.config/ghostty/config-backup" "${srcs[@]}"
    [ "$status" -ne 0 ]
}
```

- [ ] **Step 2: テストが fail することを確認**

Run: `bats scripts/tests/bootstrap.bats -f "symlink_target_covered"`
Expected: FAIL（`symlink_target_covered: command not found` 相当で最初の呼び出しが非ゼロ）

- [ ] **Step 3: ヘルパーを実装**

`scripts/tests/bootstrap.bats` の `missing_symlink_sources()` 関数定義の閉じ `}` の直後（現状 362 行目付近）に以下を追加する。

```bash
# file が sources のいずれかにカバーされるか判定する純粋関数。
# covered = file 自身が source (file pair)、または file が source の配下 (dir pair の transitive)。
# 末尾 "/" 境界により prefix 誤爆 (ghostty/config が ghostty/config-backup を誤カバー) を防ぐ。
symlink_target_covered() {
    local file="$1"
    shift
    local source
    for source in "$@"; do
        [ "$file" = "$source" ] && return 0
        case "$file" in "$source"/*) return 0 ;; esac
    done
    return 1
}
```

- [ ] **Step 4: テストが pass することを確認**

Run: `bats scripts/tests/bootstrap.bats -f "symlink_target_covered"`
Expected: PASS（1 test, ok）

- [ ] **Step 5: 変異注入でユニットテストの有効性を確認**

`symlink_target_covered` の `case "$file" in "$source"/*)` の `/*` を一時的に `*` に変える（末尾 / 境界を壊す）。

Run: `bats scripts/tests/bootstrap.bats -f "symlink_target_covered"`
Expected: FAIL（prefix 誤爆の negative case が `config-backup` を covered と誤判定して赤くなる）

確認後、`*` を `/*` へ戻す（未コミット編集が同ファイルにあるため `git checkout` は使わず、この 1 箇所だけ手で戻す）。再実行して PASS を確認する。

- [ ] **Step 6: コミット**

```bash
git add scripts/tests/bootstrap.bats
git commit -m "test: add symlink_target_covered pure helper with unit test"
```

---

### Task 2: reverse-drift テストと ghostty literal pin の退役

未カバー列挙ヘルパーと reverse-drift テストを追加し、ghostty literal pin を削除する。変異注入で reverse テストが実際に drift を捕捉することを確認する。

**Files:**
- Modify: `scripts/tests/bootstrap.bats`（`symlink_target_covered` の直後に `uncovered_symlink_targets` を追加、`@test "SYMLINK_PAIRS: manages the Ghostty config"` を削除、reverse-drift の @test を追加）

**Interfaces:**
- Consumes: `symlink_target_covered`（Task 1）、`load_symlink_pairs` と `REPO_ROOT`（test_helper.bash 既存）。
- Produces: `uncovered_symlink_targets` — 呼び出し前に `load_symlink_pairs` で `SYMLINK_PAIRS` を読み込んだ状態で、`home/` 配下の tracked ファイルのうち未カバーのものを 1 行ずつ echo する。

- [ ] **Step 1: 失敗する reverse-drift テストを書く**

`scripts/tests/bootstrap.bats` の Task 1 で追加した `symlink_target_covered` の @test の直後に以下を追加する。

```bash
@test "SYMLINK_PAIRS: every managed home/ file is covered (reverse drift)" {
    # home/X は ~/X を mirror する規約で、home/ 配下は allowlist を除き全て symlink 対象。
    # 未カバー集合が allowlist と一致しない = 新 config の配線し忘れ (未カバー増) か
    # stale allowlist (pair 追加後の消し忘れ) を意味する drift。
    load_symlink_pairs
    # 空配列 (slice 破綻) での vacuous pass を防ぐ negative guard
    [ "${#SYMLINK_PAIRS[@]}" -gt 0 ]

    # home/ 配下だが意図的に symlink しないファイルの allowlist (canonical)。各行に理由を書く。
    local -a unmanaged=(
        "home/.gitignore"                              # home/ サブツリーの gitignore (apm 生成物を ignore)
        "home/.gitconfig.private.example"              # private gitconfig のテンプレ (実体は git-ignored)
        "home/apm.yml"                                 # apm install が bootstrap で読む manifest
        "home/apm.lock.yaml"                           # apm lockfile (deployed_files の真実源)
        "home/.config/herdr/resources/left-arrow.svg"  # cheatsheet .af のデザイン素材 (symlink 不要)
        "home/.config/herdr/resources/right-arrow.svg" # cheatsheet .af のデザイン素材 (symlink 不要)
    )

    local uncovered expected
    uncovered="$(uncovered_symlink_targets | sort)"
    expected="$(printf '%s\n' "${unmanaged[@]}" | sort)"
    [ "$uncovered" = "$expected" ] || {
        echo "reverse drift 検出。expected (allowlist) と actual (uncovered) の差分:" >&2
        diff <(echo "$expected") <(echo "$uncovered") >&2 || true
        return 1
    }
}
```

- [ ] **Step 2: テストが fail することを確認**

Run: `bats scripts/tests/bootstrap.bats -f "reverse drift"`
Expected: FAIL（`uncovered_symlink_targets: command not found` 相当）

- [ ] **Step 3: uncovered_symlink_targets ヘルパーを実装**

`scripts/tests/bootstrap.bats` の `symlink_target_covered()` 関数定義の閉じ `}` の直後に以下を追加する。

```bash
# home/ 配下の tracked ファイルのうち、どの SYMLINK_PAIR にもカバーされないものを列挙する。
# 呼び出し前に load_symlink_pairs で SYMLINK_PAIRS を読み込んでおくこと。
# git ls-files は tracked のみ返すため apm 生成物 (ignore 済み) は自動的に除外される。
uncovered_symlink_targets() {
    local -a sources=()
    local pair file
    for pair in "${SYMLINK_PAIRS[@]}"; do
        sources+=("${pair%%|*}")
    done
    while IFS= read -r file; do
        symlink_target_covered "$file" "${sources[@]}" || echo "$file"
    done < <(git -C "$REPO_ROOT" ls-files 'home/')
}
```

- [ ] **Step 4: テストが pass することを確認**

Run: `bats scripts/tests/bootstrap.bats -f "reverse drift"`
Expected: PASS（未カバー集合が allowlist の 6 件と完全一致）

- [ ] **Step 5: ghostty literal pin テストを削除**

`scripts/tests/bootstrap.bats` から以下のブロック全体（`@test "SYMLINK_PAIRS: manages the Ghostty config"` の 6 行と、その前後いずれかの空行 1 行）を削除する。

```bash
@test "SYMLINK_PAIRS: manages the Ghostty config" {
    # Ghostty config を管理下に置き HackGen font-family 等を fresh マシンで再現する。
    # all-sources-exist は pair 削除を許すため, 管理対象であること自体を pin する。
    load_symlink_pairs
    assert_contains "${SYMLINK_PAIRS[*]}" 'home/.config/ghostty/config|.config/ghostty/config'
}
```

- [ ] **Step 6: 全 bats を実行して回帰ゼロを確認**

Run: `bats scripts/tests/*.bats`
Expected: 全 PASS、0 failures（86 - 1 ghostty + 2 新規 = 87 tests）

- [ ] **Step 7: 実装をコミット**

```bash
git add scripts/tests/bootstrap.bats
git commit -m "test: add SYMLINK_PAIRS reverse-drift guard and retire ghostty pin"
```

- [ ] **Step 8: 変異注入 (a) — ghostty pair を外すと reverse が FAIL することを確認**

コミット済みで working tree は clean。`bootstrap.sh` の `SYMLINK_PAIRS` 配列から `"home/.config/ghostty/config|.config/ghostty/config"` の行を一時削除する。

Run: `bats scripts/tests/bootstrap.bats -f "reverse drift"`
Expected: FAIL（`home/.config/ghostty/config` が未カバーに現れ allowlist に無いため集合不一致。ghostty 保護が literal pin 無しでも効く証拠）

確認後 `git checkout -- bootstrap.sh` で復元（tree は clean なので安全）。

- [ ] **Step 9: 変異注入 (b) — 未配線の tracked ファイルで reverse が FAIL することを確認**

```bash
touch home/dummy-unwired.conf
git add home/dummy-unwired.conf
```

Run: `bats scripts/tests/bootstrap.bats -f "reverse drift"`
Expected: FAIL（`home/dummy-unwired.conf` が未カバーに現れる）

確認後に復元:

```bash
git rm -f home/dummy-unwired.conf
```

- [ ] **Step 10: 変異注入 (c) — allowlist から 1 件消すと reverse が FAIL することを確認**

`scripts/tests/bootstrap.bats` の `unmanaged` 配列から `"home/apm.yml"` の行を一時削除する。

Run: `bats scripts/tests/bootstrap.bats -f "reverse drift"`
Expected: FAIL（`home/apm.yml` が未カバーに現れるが allowlist に無く集合不一致）

確認後 `git checkout -- scripts/tests/bootstrap.bats` で復元（tree は clean なので安全）。再実行して PASS を確認する。

- [ ] **Step 11: pre-commit の静的検査を通す**

Run: `pre-commit run ast-grep-scan ast-grep-test --files scripts/tests/bootstrap.bats`
Expected: 全 Passed（@test 名 ASCII、bare `[[ ]]` 無しを確認）

---

## Self-Review

**1. Spec coverage:**
- 案A 集合一致テスト → Task 2 Step 1/3/4。
- 純粋関数 symlink_target_covered による粒度吸収 → Task 1。
- ghostty pin 削除 → Task 2 Step 5。
- allowlist 6 件 canonical → Task 2 Step 1。
- home/ scope・tracked のみ → Task 2 Step 3（git ls-files 'home/'）。
- 変異注入 3 種 → Task 2 Step 8/9/10。
- prefix 境界 negative → Task 1 Step 1/5。
全 spec 要件にタスクが対応する。

**2. Placeholder scan:** TBD/TODO/曖昧記述なし。全ステップに実コードとコマンドを記載。

**3. Type consistency:** `symlink_target_covered`（Task 1 Produces）を Task 2 の `uncovered_symlink_targets` が同名・同引数順で consume。`uncovered_symlink_targets`（引数なし、SYMLINK_PAIRS 依存）を reverse テストが consume。命名一貫。
