# Issue #25 Phase 3 実装計画

> エージェント作業者へ: 本計画の実行には `superpowers:subagent-driven-development` を使う。
> 手順はチェックボックス (`- [ ]`) で追跡する。
> 本 Issue のドキュメントでは private リポジトリ名と追加の設定ディレクトリ名を伏字にする
> (issue.md 冒頭の方針)。実測を追記するときも literal を書かず `<追加の設定ディレクトリ>` の
> 形を使う。シェルのスニペットに置く場合はクォート内へ入れる (裸で置くと `<` がリダイレクトと
> 解釈されて構文エラーになる)。

目的: dotfiles が持つ skill と plugin の実体を追跡対象から外し、供給を apm 経由の単一経路へ移す。
併せて apm install の破壊性に対するガードを 2 層で機構化する。

方針: Phase 3 を 2 つの PR に分ける。spec は「分割しない」としていたが、その根拠だった供給の
依存関係は実測で存在しないことが分かった (追跡停止しても symlink は literal のまま生き、
`git rm -r --cached` は working tree を残すため供給は途切れない)。

- Phase 3a (PR A): 項目 11 → 15 → 13 → 10 の順。供給経路を apm へ切り替え、ガードを入れる
- Phase 3b (PR B): 項目 12 → 14 → 16 の順。設定ディレクトリ名を外部化し、stale symlink を撤去する

技術スタック: bash (bootstrap.sh) / zsh (.zshrc) / Python 3.12 標準ライブラリのみ (hook) /
bats-core (シェルのテスト) / pytest (hook のテスト) / apm 0.27.0 / Claude Code 2.1.223

## Global Constraints

- 検査機構を足したときの変異注入は 3 種行う。検査対象を壊す / 検査機構そのものを壊す /
  検査機構の取り付けを外す。1 種だけで完了としない
- 変異注入は一度に 1 箇所ずつ。復元は `git checkout -- <file>` ではなく cp のバックアップから戻す
- exit code で成否を判定するコマンドはパイプにも後続コマンドにも繋がない。出力を絞るときは
  `cmd > <file> 2>&1` だけを実行し、ファイルは次の呼び出しで読む
- コミット本文・PR 本文は Write でファイルに書き `-F` / `--body-file` で渡す
- ファイル一覧は NUL 区切り (`git ... -z` / `find -print0`) で受け取り、検査件数が対象件数と
  一致することを確かめる
- 「0 件」「緑」を健全の根拠にする前に、その検査が何を何件見たかを確認し、正常なら非空になる
  対照を並べる
- コード内のコメントは日本語。ログメッセージは内部ログなので日本語、絵文字なし
- 一時ファイルは `<repo>/.cache/` 配下に置く

## 実測で確定した事実 (本計画の前提)

apm 0.27.0 / Claude Code 2.1.223 で、隔離した `.cache/phase3-probe/home/` にて実測した。
実行前後で `~/.apm/apm.yml` と `~/.claude/settings.json` の md5 が不変、repo は clean のままで
あることを確認済み。

| 事実 | 実測値 |
|---|---|
| deploy 先ディレクトリ名 | パスの末尾セグメント。`skills/tooling/herdr` → `.claude/skills/herdr`、`plugins/dev-workflow` → `.claude/skills/dev-workflow` |
| フラット分解 | `.claude/agents/` 3 件、`.claude/commands/` 5 件 |
| フラット分解分の lockfile 記録 | 記録される (`deployed_files` に 6 件 + web-monkey-qa 分) |
| 依存 15 件の deploy 総数 | 88 ファイル、skills ディレクトリ 15 個 |
| 合成 `apm.yml` | 4 件 (plugin 3 + justfile)。パッケージ側に manifest は不要 |
| 現行 tracked 15 件との差 | 消える 1 件 (`ax/README.md`)、内容が変わる 2 件 (`ax/SKILL.md`・`markdown-to-pdf/SKILL.md`)、バイト一致 12 件 |
| `winvm.py` | 保たれる (`~/.local/bin/winvm` は無事) |
| apm の副作用 | cwd の `.gitignore` に `apm_modules/` を自動追記する |
| tirith の `apm install` 判定 | clean (無音 allow)。対照として `echo "hook。session"` は HIGH で block されるので検査は生きている |
| hook 入力の `cwd` | 存在する。「hook が起動された時点の作業ディレクトリ」 |

未確認のまま残すもの: 複数の PreToolUse hook が deny と allow を同時に返したときの合成規則。
公式ドキュメントは「All matching hooks run in parallel」までしか書いていない。本計画では
新 hook が allow を一切出さない設計にしてこの未確認事項を回避する。

## ファイル構成

### Phase 3a

作成:

- `home/.claude/hooks/apm-install-guard.py` — PreToolUse hook 本体。stdin の JSON を読み、
  Bash コマンドが apm の破壊的サブコマンドなら対象 repo の clean を検査して deny する
- `scripts/apm-install-guard/pyproject.toml` — テストハーネスの uv プロジェクト (package = false)
- `scripts/apm-install-guard/README.md` — hook の契約と env var の説明
- `scripts/apm-install-guard/tests/test_apm_install_guard.py` — hook の黒箱テスト

変更:

- `home/apm.yml` — 依存に自作 skill 5 + plugin 3 + ax を追加
- `home/apm.lock.yaml` — `apm install` で再生成
- `home/.gitignore` — per-skill 6 行を `.claude/skills/` `.claude/agents/` `.claude/commands/` へ畳む
- `bootstrap.sh` — `APM_SYMLINK_PAIRS` 新設 / `setup_apm_symlinks()` 追加 /
  `install_apm_skills()` に clean tree ガード / main の呼び出し順
- `home/.claude/settings.json` (committed 版) — PreToolUse に hook を配線
- `.pre-commit-config.yaml` — apm-install-guard の ruff / ruff format / mypy / pytest
- `.github/workflows/test.yml` — apm-install-guard の job
- `scripts/tests/bootstrap.bats` — 配列の分割に伴う検査の更新と新規テスト
- `docs/issues/25_*/issue.md` — Phase 3a のチェックを付ける
- `docs/issues/25_*/25-spec.md` — 実測と設計変更を反映

index から削除 (working tree は残す):

- `home/.claude/skills/**` の 15 ファイル

### Phase 3b

変更:

- `bootstrap.sh` — 設定ディレクトリ一覧の読み込み / pair の動的生成 / stale symlink 撤去
- `home/.zshrc` — ランチャ関数の動的生成
- `scripts/tests/test_helper.bash` — 配列読み込みヘルパの生成方式対応
- `scripts/tests/bootstrap.bats` — mirror 検査のパラメータ化
- `scripts/tests/zshrc-claude.bats` — ランチャ検査のパラメータ化
- `scripts/tests/statusline.bats` — フィクスチャのダミー名化

---

## Phase 3a

### Task 1: 供給経路を apm へ切り替える

`home/.claude/skills/` の追跡を止め、実体の供給元を apm に移す。gitignore の書き換えと
`git rm -r --cached` と `apm.yml` の更新は同一コミットにする (spec の必須事項)。

ガードはこの時点でまだ入っていない。ガードを先に入れると、`apm.yml` を編集した dirty な状態で
`apm install` を実行できず、ガードが自分の移行手順をブロックする。よって順序は 11 → 15 → 10。

**Files:**

- Modify: `home/apm.yml`
- Modify: `home/apm.lock.yaml` (apm install が再生成)
- Modify: `home/.gitignore:1-13`
- Delete from index: `home/.claude/skills/**` (15 ファイル)

**Interfaces:**

- Produces: `home/apm.lock.yaml` の `deployed_files` に `.claude/skills/*` `.claude/agents/*`
  `.claude/commands/*` が入る。Task 2 の `APM_SYMLINK_PAIRS` はこの 3 ディレクトリを source にする

- [ ] **Step 1: 適用前の実体を数えて記録する**

適用後にハッシュ単位で突き合わせるための基線を取る。

```bash
cd "$(git rev-parse --show-toplevel)"
git ls-files -z home/.claude/skills > .cache/t1-tracked-before.nul
find home/.claude/skills -type f -print0 | xargs -0 md5 > .cache/t1-md5-before.txt
git ls-files home/.claude/skills | wc -l
find home/.claude/skills -type f | wc -l
```

期待: tracked 15 件。working tree のファイル数はこれより多い (apm 由来の 6 skill を含むため)。

- [ ] **Step 2: 追跡を止める**

`git rm -r --cached` は working tree を残すので、実行しても live symlink の供給は切れない。

```bash
cd "$(git rev-parse --show-toplevel)"
git rm -r --cached home/.claude/skills > .cache/t1-gitrm.log 2>&1
```

`settings.json` の `permissions.ask` に `Bash(git rm:*)` があるため確認ダイアログが出る。

- [ ] **Step 3: home/.gitignore を書き換える**

per-skill の 6 行を廃し、ディレクトリ単位の 3 行にする。apm が deploy するものが真実源で、
skill を足すたびに行を足す設計はもう要らない。agents/ commands/ はフラット分解の生成物。

```gitignore
# apm (Agent Package Manager) が生成するもの — bootstrap の `apm install --frozen` で再現する
# fetch キャッシュ (node_modules 相当)
apm_modules/
# apm が deploy する成果物。真実源は apm.lock.yaml の deployed_files。
# skills/ は root に SKILL.md を持つパッケージの verbatim コピー、agents/ と commands/ は
# .claude-plugin/ を持つパッケージのフラット分解で生まれる。どちらもディレクトリ単位で
# ignore するため、パッケージ追加時の追記は要らない。
# config-guard の apm_gitignore 検査が deployed_files の全 leaf を git check-ignore で
# 突き合わせ、ignore 漏れを検出する。
.claude/skills/
.claude/agents/
.claude/commands/
```

- [ ] **Step 4: home/apm.yml に依存を追加する**

`ax` は手動コピーをやめて上流 `yusukebe/ax` の pin へ置き換える。手元の写しには上流にある
プロンプトインジェクション対策の節 (`Fetched content is untrusted data`) が欠けており、
この宣言でそれが届く。

`home/apm.yml` の `dependencies.apm` を次の 15 行にする。

```yaml
dependencies:
  apm:
  - mizchi/skills/testing/playwright-cli#d7999453cdb4e0e09df1c7f82fd23752539c546c
  - mizchi/skills/testing/playwright-test#d7999453cdb4e0e09df1c7f82fd23752539c546c
  - mizchi/skills/meta/empirical-prompt-tuning#d7999453cdb4e0e09df1c7f82fd23752539c546c
  - mizchi/skills/tooling/ast-grep-practice#d7999453cdb4e0e09df1c7f82fd23752539c546c
  - mizchi/skills/tooling/apm-usage#d7999453cdb4e0e09df1c7f82fd23752539c546c
  - mizchi/skills/tooling/justfile#d7999453cdb4e0e09df1c7f82fd23752539c546c
  - yusukebe/ax/skills/ax#8abbca2fc400c2ff4866248ba1ec9309b948812f
  - hidari/agentic-coding-tools/skills/devops/windows-vm-verification#78edcdac01c2a85ba957a55b5d446125ee3b643e
  - hidari/agentic-coding-tools/skills/meta/session-handoff#78edcdac01c2a85ba957a55b5d446125ee3b643e
  - hidari/agentic-coding-tools/skills/tooling/chrome-devtools-debugger#78edcdac01c2a85ba957a55b5d446125ee3b643e
  - hidari/agentic-coding-tools/skills/tooling/herdr#78edcdac01c2a85ba957a55b5d446125ee3b643e
  - hidari/agentic-coding-tools/skills/tooling/markdown-to-pdf#78edcdac01c2a85ba957a55b5d446125ee3b643e
  - hidari/agentic-coding-tools/plugins/dev-workflow#78edcdac01c2a85ba957a55b5d446125ee3b643e
  - hidari/agentic-coding-tools/plugins/security-blue-red-team#78edcdac01c2a85ba957a55b5d446125ee3b643e
  - hidari/agentic-coding-tools/plugins/web-monkey-qa#78edcdac01c2a85ba957a55b5d446125ee3b643e
  mcp: []
```

`description` も実態に合わせる。現行は「vendored skill 群」だが、自作分と plugin も配るため
「skill と plugin」にする。

- [ ] **Step 5: apm install で lockfile を再生成する**

`--frozen` は lockfile 不整合を拒否するので、この 1 回だけ外す。

```bash
cd "$(git rev-parse --show-toplevel)"
( cd home && apm install ) > .cache/t1-install.log 2>&1
```

- [ ] **Step 6: 適用後を基線と突き合わせる**

書き込み対象外のファイルがハッシュ単位で不変であることを確認する。probe の実測では
バイト一致 12 / 内容変更 2 / 削除 1 だった。ここから外れたら止まって原因を調べる。

```bash
cd "$(git rev-parse --show-toplevel)"
find home/.claude/skills -type f -print0 | xargs -0 md5 > .cache/t1-md5-after.txt
diff .cache/t1-md5-before.txt .cache/t1-md5-after.txt > .cache/t1-md5-diff.txt
wc -l .cache/t1-md5-diff.txt
```

期待する差分: `ax/README.md` の消失、`ax/SKILL.md` と `markdown-to-pdf/SKILL.md` の md5 変更、
apm 由来 6 skill の内容は不変、加えて新規に `home/.claude/agents/` と `home/.claude/commands/`
と plugin 3 個の skills ディレクトリが増える。

- [ ] **Step 7: ignore の網羅を config-guard で検査する**

lockfile の全 leaf が ignore されていることを、行の目視ではなく git 自身に判定させる。

```bash
cd "$(git rev-parse --show-toplevel)"
uv run --directory scripts/config-guard config-guard . > .cache/t1-guard.log 2>&1
```

期待: exit 0、findings 0 件。

- [ ] **Step 8: 0 件が「見ていない」でないことを対照で確かめる**

`home/.gitignore` の `.claude/agents/` を一時的に消して config-guard が赤くなることを見る。
これは検査対象を壊す変異注入 (1 種目)。

```bash
cd "$(git rev-parse --show-toplevel)"
cp home/.gitignore .cache/t1-gitignore.bak
# .claude/agents/ の行だけを削除して再実行
uv run --directory scripts/config-guard config-guard . > .cache/t1-guard-mutated.log 2>&1
# 赤を確認したら復元
cp .cache/t1-gitignore.bak home/.gitignore
```

期待: 変異時は exit 1 で `.claude/agents/...` が findings に出る。復元後は再び exit 0。

- [ ] **Step 9: live symlink の健全性を確認する**

```bash
extra_dir="$HOME/<追加の設定ディレクトリ>"
for p in ~/.claude/skills "$extra_dir/skills" ~/.local/bin/winvm; do
  printf '%s -> %s [%s]\n' "$p" "$(readlink "$p" 2>/dev/null || echo '(not a symlink)')" "$([ -e "$p" ] && echo alive || echo DANGLING)"
done
```

期待: 3 本とも alive。

- [ ] **Step 10: テストを回す**

```bash
bats scripts/tests/ > .cache/t1-bats.log 2>&1
```

この時点で `bootstrap.bats` の「all sources exist in repo」が赤になる可能性がある。
`SYMLINK_PAIRS` にはまだ `home/.claude/skills` が残っており、working tree には実体があるので
通るはずだが、赤なら Task 2 を先に進めてから再確認する。pass/fail の件数を両方読むこと。

- [ ] **Step 11: コミット**

```bash
cd "$(git rev-parse --show-toplevel)"
git add home/apm.yml home/apm.lock.yaml home/.gitignore
git status --short > .cache/t1-status.txt
```

`git status` で index から 15 件が削除され、追加が 3 ファイルであることを確認してからコミットする。
本文は Write でファイルに書き `-F` で渡す。

```bash
git commit -F .cache/t1-commit-msg.txt
```

コミットメッセージの型:

```
refactor: skill と plugin の供給を apm の単一経路へ移す

home/.claude/skills/ の追跡を止め、実体を apm が配置する形にする。自作 skill 5 個と
plugin 3 個は agentic-coding-tools から、ax は上流 yusukebe/ax から取得する。ax は
手元の写しが古く、プロンプトインジェクション対策の節が欠けていた。

gitignore は per-skill の列挙をやめてディレクトリ単位に畳んだ。apm がフラット分解する
agents/ と commands/ も deployed_files に記録されるため ignore 対象に含める。
```

---

### Task 2: apm 生成物を source とする symlink を分離する

`SYMLINK_PAIRS` の不変条件は「source は git 管理下で必ず実在する (欠けていればバグ)」で、
これは bootstrap.sh:56-59 のコメントが明文化している。Task 1 で `home/.claude/skills` は
git 管理下でなくなったため、この配列に置いたままにするとその不変条件が壊れ、fresh clone を
使う CI で `bootstrap.bats` の「all sources exist in repo」が構造的に赤くなる。

性質の違う source は配列を分ける。`HOME_SYMLINK_PAIRS` を分けた既存の判断と同じ理屈である。

**Files:**

- Modify: `bootstrap.sh:23-53` (SYMLINK_PAIRS から 3 エントリを外す)
- Modify: `bootstrap.sh` (APM_SYMLINK_PAIRS 新設 / setup_apm_symlinks 追加 / main の配線)
- Modify: `scripts/tests/bootstrap.bats`
- Test: `scripts/tests/bootstrap.bats`

**Interfaces:**

- Consumes: Task 1 が作った `home/.claude/{skills,agents,commands}` の実体
- Produces: `APM_SYMLINK_PAIRS` 配列と `setup_apm_symlinks()` 関数。Phase 3b の Task 9
  (stale 撤去) は両配列と `HOME_SYMLINK_PAIRS` を合わせた「現在の target 集合」を使う

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/bootstrap.bats` に追加する。既存の配列テストと同じく `load_pairs_array` で
実配列を source して検査する。

```bash
@test "APM_SYMLINK_PAIRS: every source is under home/.claude and is an apm deploy dir" {
  load_pairs_array APM_SYMLINK_PAIRS

  [ "${#APM_SYMLINK_PAIRS[@]}" -gt 0 ]

  local pair source
  for pair in "${APM_SYMLINK_PAIRS[@]}"; do
    source="${pair%%|*}"
    case "$source" in
      home/.claude/skills|home/.claude/agents|home/.claude/commands|home/.claude/skills/*) ;;
      *) fail "APM_SYMLINK_PAIRS source is not an apm deploy path: $source" ;;
    esac
  done
}

@test "APM_SYMLINK_PAIRS: sources are gitignored (they are apm output, not tracked)" {
  load_pairs_array APM_SYMLINK_PAIRS

  [ "${#APM_SYMLINK_PAIRS[@]}" -gt 0 ]

  local pair source checked=0
  for pair in "${APM_SYMLINK_PAIRS[@]}"; do
    source="${pair%%|*}"
    run git -C "$REPO_ROOT" check-ignore -q "$source"
    [ "$status" -eq 0 ] || fail "APM_SYMLINK_PAIRS source is not gitignored: $source"
    checked=$((checked + 1))
  done
  [ "$checked" -eq "${#APM_SYMLINK_PAIRS[@]}" ]
}

@test "SYMLINK_PAIRS: no longer carries apm-generated sources" {
  load_pairs_array SYMLINK_PAIRS

  [ "${#SYMLINK_PAIRS[@]}" -gt 0 ]

  local pair source
  for pair in "${SYMLINK_PAIRS[@]}"; do
    source="${pair%%|*}"
    case "$source" in
      home/.claude/skills|home/.claude/skills/*|home/.claude/agents|home/.claude/commands)
        fail "apm-generated source must live in APM_SYMLINK_PAIRS: $source" ;;
    esac
  done
}

@test "setup_apm_symlinks skips pairs whose source does not exist" {
  load_pairs_array APM_SYMLINK_PAIRS

  # source を 1 つも作らない状態で呼ぶ。dangling symlink を作らず警告するのが仕様
  run setup_apm_symlinks
  [ "$status" -eq 0 ]
  assert_contains "$output" "apm source not found"
  [ ! -e "$TEST_HOME/.claude/agents" ]
}

@test "setup_apm_symlinks links pairs whose source exists" {
  mkdir -p "$DOTFILES_DIR/home/.claude/agents"
  run setup_apm_symlinks
  [ "$status" -eq 0 ]
  [ -L "$TEST_HOME/.claude/agents" ]
  [ "$(readlink "$TEST_HOME/.claude/agents")" = "$DOTFILES_DIR/home/.claude/agents" ]
}
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
bats scripts/tests/bootstrap.bats > .cache/t2-red.log 2>&1
```

期待: `APM_SYMLINK_PAIRS` が未定義なので `load_pairs_array` が
`Error: array not found` で fail する。pass/fail 件数を両方読み、期待するテスト名が
出力に現れていることを確認する (件数だけでは 0 件実行と区別できない)。

- [ ] **Step 3: bootstrap.sh を実装する**

`SYMLINK_PAIRS` から次の 3 エントリを削除する。

```
    "home/.claude/skills|.claude/skills"
    "home/.claude/skills|<追加の設定ディレクトリ>/skills"
    "home/.claude/skills/windows-vm-verification/winvm.py|.local/bin/winvm"
```

`HOME_SYMLINK_PAIRS` の直後に新しい配列を置く。

```bash
# apm が deploy した成果物を source とするシンボリックリンク定義（ソース|ターゲット）。
# SYMLINK_PAIRS と分けているのは source の性質が違うため。あちらの source は git 管理下で
# 必ず実在する（欠けていればバグ）が、こちらは apm install が配置するまで存在しない。
# fresh clone や --dotfiles-only では実体が無いため、存在するときだけ張る。
# agents/ と commands/ は .claude-plugin/ を持つパッケージのフラット分解で生まれる。
APM_SYMLINK_PAIRS=(
    "home/.claude/skills|.claude/skills"
    "home/.claude/agents|.claude/agents"
    "home/.claude/commands|.claude/commands"
    "home/.claude/skills|<追加の設定ディレクトリ>/skills"
    "home/.claude/agents|<追加の設定ディレクトリ>/agents"
    "home/.claude/commands|<追加の設定ディレクトリ>/commands"
    "home/.claude/skills/windows-vm-verification/winvm.py|.local/bin/winvm"
)
```

`setup_home_symlinks` の直後に関数を置く。

```bash
# apm が deploy した成果物へのシンボリックリンクを作成する（冪等）。
# source が無いときは張らずに警告する。create_symlink の ln -sf は source の存在を見ないため
# リンク先の無い symlink を作れてしまい、参照した側が黙って失敗する。
setup_apm_symlinks() {
    local pair source target
    for pair in "${APM_SYMLINK_PAIRS[@]}"; do
        source="$DOTFILES_DIR/${pair%%|*}"
        target="$HOME/${pair##*|}"
        if [ ! -e "$source" ]; then
            warn "apm source not found; skipping symlink: $source"
            continue
        fi
        create_symlink "$source" "$target"
    done
}
```

main の呼び出しを `install_apm_skills` の直後にする。

```bash
        install_mise_tools
        install_apm_skills
        setup_apm_symlinks
        setup_claude_plugins
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
bats scripts/tests/bootstrap.bats > .cache/t2-green.log 2>&1
```

期待: 新規 5 件が pass。既存テストのうち mirror 検査 (`unmirrored_claude_targets`) の
allowlist が変わるため、そこが赤なら allowlist を更新する。`.claude/skills` は
`SYMLINK_PAIRS` から消えたので mirror 検査の対象外になる。

- [ ] **Step 5: 取り付けを外す変異で赤を確認する**

main から `setup_apm_symlinks` の呼び出しを消して、dry-run のサブプロセステストが赤くなることを
確認する。これは検査機構の取り付けを外す変異 (3 種目)。緑のままなら配線を pin するテストが
足りていない。

```bash
cd "$(git rev-parse --show-toplevel)"
cp bootstrap.sh .cache/t2-bootstrap.bak
# main から setup_apm_symlinks の行を削除して実行
bats scripts/tests/bootstrap.bats > .cache/t2-mutated.log 2>&1
cp .cache/t2-bootstrap.bak bootstrap.sh
```

配線を pin するテストが無い場合は、既存の dry-run テスト (`bootstrap.bats:748` 付近) と同型で
次を追加する。

```bash
@test "main wires setup_apm_symlinks after install_apm_skills" {
  mkdir -p "$DOTFILES_DIR/home/.claude/agents"
  run bash "$BOOTSTRAP_SCRIPT" --dry-run
  [ "$status" -eq 0 ]
  assert_contains "$output" "[DRY-RUN] apm install --frozen"
  assert_contains "$output" "$TEST_HOME/.claude/agents"
}
```

- [ ] **Step 6: 全テストを回してコミット**

```bash
bats scripts/tests/ > .cache/t2-all.log 2>&1
```

```bash
git add bootstrap.sh scripts/tests/bootstrap.bats
git commit -F .cache/t2-commit-msg.txt
```

---

### Task 3: install_apm_skills に clean tree ガードを置く (層 1)

自動実行経路を塞ぐ。目的は破壊の防止ではなく復旧可能性の確保である。ツリーが clean なら
apm が何を壊しても git から戻せるが、汚れていれば未コミットの作業が復旧不能に消える。
この整理から検査範囲は deploy 先ではなくリポジトリ全体になる。

`apm.yml` と `apm.lock.yaml` は apm install の入出力なので、これらだけが変更されている状態は
正常な中間状態として許可する。この例外が無いと、pin を更新するたびにガードが自分の手順を
ブロックする。

**Files:**

- Modify: `bootstrap.sh` (`apm_install_blockers()` 追加 / `install_apm_skills()` にガード)
- Test: `scripts/tests/bootstrap.bats`

**Interfaces:**

- Produces: `apm_install_blockers <repo>` — ブロック要因のパスを 1 行 1 件で stdout に出す
  純粋関数。ブロック要因が無ければ何も出さない。Task 4 の hook は同じ判定規則を Python 側で
  実装する (共有はしない。bash と Python でプロセスが別なため)

- [ ] **Step 1: 失敗するテストを書く**

```bash
@test "apm_install_blockers: clean tree yields no blockers" {
  local repo="$TEST_HOME/repo"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email t@example.com
  git -C "$repo" config user.name t
  echo hello > "$repo/a.txt"
  git -C "$repo" add a.txt
  git -C "$repo" commit -qm init

  run apm_install_blockers "$repo"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "apm_install_blockers: modified tracked file is a blocker" {
  local repo="$TEST_HOME/repo"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email t@example.com
  git -C "$repo" config user.name t
  echo hello > "$repo/a.txt"
  git -C "$repo" add a.txt
  git -C "$repo" commit -qm init
  echo changed > "$repo/a.txt"

  run apm_install_blockers "$repo"
  [ "$status" -eq 0 ]
  assert_contains "$output" "a.txt"
}

@test "apm_install_blockers: untracked file is a blocker" {
  local repo="$TEST_HOME/repo"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email t@example.com
  git -C "$repo" config user.name t
  echo hello > "$repo/a.txt"
  git -C "$repo" add a.txt
  git -C "$repo" commit -qm init
  echo new > "$repo/untracked.txt"

  run apm_install_blockers "$repo"
  [ "$status" -eq 0 ]
  assert_contains "$output" "untracked.txt"
}

@test "apm_install_blockers: apm manifest and lockfile are allowed" {
  local repo="$TEST_HOME/repo"
  mkdir -p "$repo/home"
  git -C "$repo" init -q
  git -C "$repo" config user.email t@example.com
  git -C "$repo" config user.name t
  echo name: x > "$repo/home/apm.yml"
  echo v: 1 > "$repo/home/apm.lock.yaml"
  git -C "$repo" add home/apm.yml home/apm.lock.yaml
  git -C "$repo" commit -qm init
  echo name: y > "$repo/home/apm.yml"
  echo v: 2 > "$repo/home/apm.lock.yaml"

  run apm_install_blockers "$repo"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "apm_install_blockers: a path containing spaces is not split" {
  local repo="$TEST_HOME/repo"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email t@example.com
  git -C "$repo" config user.name t
  echo hello > "$repo/a.txt"
  git -C "$repo" add a.txt
  git -C "$repo" commit -qm init
  echo x > "$repo/has space.txt"

  run apm_install_blockers "$repo"
  [ "$status" -eq 0 ]
  assert_contains "$output" "has space.txt"
  # 分断されて 2 件に数えられていないこと
  [ "$(printf '%s\n' "$output" | grep -c .)" -eq 1 ]
}

@test "install_apm_skills refuses to run when the tree is dirty" {
  # 実 repo を汚す代わりに DOTFILES_DIR を使い捨て repo に向ける
  local repo="$TEST_HOME/repo"
  mkdir -p "$repo/home"
  git -C "$repo" init -q
  git -C "$repo" config user.email t@example.com
  git -C "$repo" config user.name t
  echo hello > "$repo/a.txt"
  git -C "$repo" add a.txt
  git -C "$repo" commit -qm init
  echo changed > "$repo/a.txt"

  make_fake_apm   # PATH 先頭に呼び出しを記録する apm shim を置く
  DOTFILES_DIR="$repo" run install_apm_skills
  [ "$status" -ne 0 ]
  assert_contains "$output" "a.txt"
  [ ! -f "$TEST_HOME/fakebin/apm-called" ]
}
```

`make_fake_apm` は `scripts/tests/test_helper.bash` に既存の shim パターン (fakebin) と同型で
追加する。

```bash
# apm を呼び出し記録つきの shim に差し替える。呼ばれたら $TEST_HOME/fakebin/apm-called を作る
make_fake_apm() {
  mkdir -p "$TEST_HOME/fakebin"
  cat > "$TEST_HOME/fakebin/apm" <<'EOF'
#!/bin/sh
touch "$(dirname "$0")/apm-called"
exit 0
EOF
  chmod +x "$TEST_HOME/fakebin/apm"
  export PATH="$TEST_HOME/fakebin:$PATH"
}
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
bats scripts/tests/bootstrap.bats > .cache/t3-red.log 2>&1
```

期待: `apm_install_blockers: command not found`。

- [ ] **Step 3: bootstrap.sh に実装する**

`install_apm_skills` の直前に置く。

```bash
# apm install を阻む未コミットの変更を列挙する（1 行 1 パス。無ければ何も出さない）。
# apm install は deploy 先を rsync --delete 相当で書き換え、tracked file も黙って上書き・
# 削除する。ログには (files unchanged) と出るため差分に気づけない。ツリーが clean なら
# git から戻せるので、検査範囲は deploy 先ではなくリポジトリ全体になる。
# apm.yml と apm.lock.yaml は apm install の入出力であり、これらだけが変更された状態は
# 正常な中間状態なので許可する。
# パスは NUL 区切りで受け取る。空白や日本語を含むパスは空白分割すると分断され、落ちた分は
# 「エラー」ではなく「短い正常な結果」として返るため出力を見ても気づけない。
apm_install_blockers() {
    local repo="$1"
    local entry path

    while IFS= read -r -d '' entry; do
        # porcelain の各エントリは "XY <path>" 形式。先頭 3 文字が状態フィールド
        path="${entry:3}"
        case "${path##*/}" in
            apm.yml|apm.lock.yaml) continue ;;
        esac
        printf '%s\n' "$path"
    done < <(git -C "$repo" status --porcelain -z 2> /dev/null)
}
```

`install_apm_skills` にガードを差す。

```bash
install_apm_skills() {
    log "Installing apm-managed skills..."

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] apm install --frozen (in $DOTFILES_DIR/home)"
        return 0
    fi

    if ! command -v apm &> /dev/null; then
        warn "apm not found; skipping apm-managed skill installation"
        return 0
    fi

    local blockers
    blockers="$(apm_install_blockers "$DOTFILES_DIR")"
    if [ -n "$blockers" ]; then
        error "未コミットの変更があるため apm install を中止します。apm は deploy 先を上書き・削除します"
        printf '%s\n' "$blockers" >&2
        error "コミットまたは stash してから再実行してください"
        return 1
    fi

    # --frozen は lockfile 不在/不整合時に install を拒否し、pin されたスキルの再現性を担保する。
    # サブシェルで cd し、呼び出し元の cwd を汚さない。
    ( cd "$DOTFILES_DIR/home" && apm install --frozen )
}
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
bats scripts/tests/bootstrap.bats > .cache/t3-green.log 2>&1
```

- [ ] **Step 5: 検査機構そのものを壊す変異で赤を確認する**

`apm_install_blockers` の `printf` 行を消し (常に空を返す = 常に許可)、
`install_apm_skills refuses to run when the tree is dirty` が赤くなることを確認する。
これは 2 種目の変異。1 箇所ずつ隔離して行い、復元は cp から戻す。

```bash
cd "$(git rev-parse --show-toplevel)"
cp bootstrap.sh .cache/t3-bootstrap.bak
# printf 行を削除して実行
bats scripts/tests/bootstrap.bats > .cache/t3-mut2.log 2>&1
cp .cache/t3-bootstrap.bak bootstrap.sh
```

- [ ] **Step 6: 取り付けを外す変異で赤を確認する**

`install_apm_skills` からガードの if ブロックごと削除して、同じテストが赤くなることを確認する。
これが 3 種目。

- [ ] **Step 7: 全テストを回してコミット**

```bash
bats scripts/tests/ > .cache/t3-all.log 2>&1
```

```bash
git add bootstrap.sh scripts/tests/bootstrap.bats scripts/tests/test_helper.bash
git commit -F .cache/t3-commit-msg.txt
```

---

### Task 4: PreToolUse hook でエージェント経由の apm install を塞ぐ (層 2)

手打ちおよびエージェント経由の実行を塞ぐ。層 1 は bootstrap 経由しか守らない。

スコープは cwd の git repo とする。apm install が deploy 先を破壊するという性質は
どのリポジトリでも同じなので、dotfiles 限定にする理由がない。緊急回避のため
`APM_INSTALL_GUARD_DISABLE=1` で無効化できるようにする。

新 hook は deny のときだけ JSON を出し、それ以外は無音 exit 0 にする。複数の PreToolUse hook が
deny と allow を同時に返したときの合成規則は公式ドキュメントに書かれていないため、allow を
一切出さない設計でこの未確認事項を回避する。

**Files:**

- Create: `home/.claude/hooks/apm-install-guard.py`
- Create: `scripts/apm-install-guard/pyproject.toml`
- Create: `scripts/apm-install-guard/README.md`
- Create: `scripts/apm-install-guard/tests/test_apm_install_guard.py`

**Interfaces:**

- Consumes: PreToolUse の stdin JSON。`hook_event_name` / `tool_name` / `tool_input.command` /
  `cwd` を読む。既存 `tirith-check.py:44-49` と同じく snake_case と camelCase の両方に対応する
- Produces: deny 時に
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
  "permissionDecisionReason": <理由>}}` を stdout へ出し exit 0。それ以外は無出力 exit 0

- [ ] **Step 1: 失敗するテストを書く**

`scripts/apm-install-guard/tests/test_apm_install_guard.py` を作る。ハーネスは
`scripts/tirith-hook/tests/test_tirith_hook.py:52-73` と同型で、hook 本体を
`subprocess.run([sys.executable, HOOK])` で黒箱起動する。

```python
"""apm-install-guard hook の黒箱テスト。

hook 本体をサブプロセスで起動し、stdin に PreToolUse の JSON を流して stdout の
permissionDecision を検証する。モックは使わず、実 git リポジトリを tmp_path に作る。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[3] / "home" / ".claude" / "hooks" / "apm-install-guard.py"


def run_hook(payload: dict, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("APM_INSTALL_GUARD_")}
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def decision(proc: subprocess.CompletedProcess[str]) -> str | None:
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "a.txt").write_text("hello\n")
    subprocess.run(["git", "add", "a.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    return path


def payload(command: str, cwd: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": cwd,
    }


def test_clean_tree_allows_silently(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    proc = run_hook(payload("apm install --frozen", str(repo)))
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_dirty_tree_denies(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    proc = run_hook(payload("apm install --frozen", str(repo)))
    assert proc.returncode == 0
    assert decision(proc) == "deny"
    assert "a.txt" in proc.stdout


def test_untracked_file_denies(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "new.txt").write_text("x\n")
    proc = run_hook(payload("apm install", str(repo)))
    assert decision(proc) == "deny"


def test_apm_manifest_and_lockfile_are_allowed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "home").mkdir()
    (repo / "home" / "apm.yml").write_text("name: x\n")
    subprocess.run(["git", "add", "home/apm.yml"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "add manifest"], cwd=repo, check=True)
    (repo / "home" / "apm.yml").write_text("name: y\n")
    (repo / "home" / "apm.lock.yaml").write_text("v: 1\n")
    proc = run_hook(payload("cd home && apm install", str(repo)))
    assert proc.stdout.strip() == ""


def test_path_with_space_is_not_split(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "has space.txt").write_text("x\n")
    proc = run_hook(payload("apm install", str(repo)))
    assert decision(proc) == "deny"
    assert "has space.txt" in proc.stdout


def test_apm_update_and_uninstall_are_guarded(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    for sub in ("update", "uninstall"):
        proc = run_hook(payload(f"apm {sub}", str(repo)))
        assert decision(proc) == "deny", sub


def test_readonly_apm_subcommands_pass_through(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    for cmd in ("apm list", "apm --version", "apm audit"):
        proc = run_hook(payload(cmd, str(repo)))
        assert proc.stdout.strip() == "", cmd


def test_unrelated_command_passes_through(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    proc = run_hook(payload("echo apm install", str(repo)))
    assert proc.stdout.strip() == ""


def test_non_bash_tool_passes_through(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    body = payload("apm install", str(repo))
    body["tool_name"] = "Read"
    proc = run_hook(body)
    assert proc.stdout.strip() == ""


def test_non_pretooluse_event_passes_through(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    body = payload("apm install", str(repo))
    body["hook_event_name"] = "PostToolUse"
    proc = run_hook(body)
    assert proc.stdout.strip() == ""


def test_camel_case_fields_are_accepted(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    proc = run_hook(
        {
            "hookEventName": "PreToolUse",
            "toolName": "Bash",
            "toolInput": {"command": "apm install"},
            "cwd": str(repo),
        }
    )
    assert decision(proc) == "deny"


def test_disable_env_var_turns_the_guard_off(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "a.txt").write_text("changed\n")
    proc = run_hook(payload("apm install", str(repo)), {"APM_INSTALL_GUARD_DISABLE": "1"})
    assert proc.stdout.strip() == ""


def test_non_git_cwd_passes_through(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    proc = run_hook(payload("apm install", str(plain)))
    assert proc.stdout.strip() == ""


def test_malformed_json_denies(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("APM_INSTALL_GUARD_")}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input="{not json",
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0
    assert decision(proc) == "deny"


def test_missing_cwd_denies(tmp_path: Path) -> None:
    body = payload("apm install", "")
    del body["cwd"]
    proc = run_hook(body)
    assert decision(proc) == "deny"
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
cd "$(git rev-parse --show-toplevel)"
uv run --directory scripts/apm-install-guard pytest -q > .cache/t4-red.log 2>&1
```

期待: hook ファイルが無いので全件 fail。

- [ ] **Step 3: pyproject.toml を書く**

`scripts/tirith-hook/pyproject.toml` と同型にする。

```toml
[project]
name = "apm-install-guard"
version = "0.1.0"
description = "apm install がツリーを破壊する前に止める PreToolUse hook のテストハーネス"
requires-python = ">=3.12"
dependencies = []

[tool.uv]
package = false

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6", "mypy>=1.11"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "N", "SIM", "RUF"]

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: hook 本体を実装する**

```python
#!/usr/bin/env python3
"""apm の破壊的サブコマンドを、ツリーが汚れているときだけ止める PreToolUse hook。

apm install は deploy 先を rsync --delete 相当で書き換え、git tracked かつ手書きのファイルも
黙って上書きし、パッケージに含まれないファイルを削除する。ログには (files unchanged) と
表示されるため差分に気づけない。

目的は破壊の防止ではなく復旧可能性の確保である。ツリーが clean なら apm が何を壊しても git から
戻せるが、汚れていれば未コミットの作業が復旧不能に消える。この整理から検査範囲は deploy 先では
なくリポジトリ全体になる。

対象は cwd が属する git リポジトリ。apm install の破壊性はどのリポジトリでも同じなので
dotfiles 限定にはしない。緊急時は APM_INSTALL_GUARD_DISABLE=1 で無効化できる。

deny のときだけ JSON を出し、それ以外は無出力 exit 0 とする。複数の PreToolUse hook が deny と
allow を同時に返したときの合成規則は公式ドキュメントに記載が無いため、allow を出さないことで
既存 hook の判定を打ち消す経路を原理的に無くしている。
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from typing import Any

# deploy 先を書き換える apm のサブコマンド。読み取り専用のもの (list / audit 等) は対象外
DESTRUCTIVE_SUBCOMMANDS = frozenset({"install", "update", "uninstall", "add", "remove"})

# apm install の入出力なので、これらだけが変更された状態は正常な中間状態として許可する
ALLOWED_DIRTY_BASENAMES = frozenset({"apm.yml", "apm.lock.yaml"})


def get(data: dict[str, Any], *keys: str) -> Any:
    """snake_case と camelCase の両方でフィールドを引く。"""
    for key in keys:
        if key in data:
            return data[key]
    return None


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def allow_silently() -> None:
    sys.exit(0)


def destructive_subcommand(command: str) -> str | None:
    """コマンド文字列から apm の破壊的サブコマンドを取り出す。無ければ None。

    正規表現ではなく shlex でトークン化するのは、`echo apm install` のような引用された
    文字列を誤検出しないため。クォートが不整合でトークン化できないものは判定しない。
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None

    for index, token in enumerate(tokens):
        if token.rsplit("/", 1)[-1] != "apm":
            continue
        for following in tokens[index + 1 :]:
            if following.startswith("-"):
                continue
            return following if following in DESTRUCTIVE_SUBCOMMANDS else None
    return None


def repo_root(cwd: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def dirty_paths(root: str) -> list[str]:
    """未コミットの変更のうち、apm の入出力でないものを列挙する。

    パスは NUL 区切りで受け取る。空白や日本語を含むパスは空白分割すると分断され、落ちた分は
    「エラー」ではなく「短い正常な結果」として返るため出力を見ても気づけない。
    """
    proc = subprocess.run(
        ["git", "-C", root, "status", "--porcelain", "-z"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git status failed: {proc.stderr.strip()}")

    blockers: list[str] = []
    for entry in proc.stdout.split("\0"):
        if not entry:
            continue
        # porcelain の各エントリは "XY <path>" 形式。先頭 3 文字が状態フィールド
        path = entry[3:]
        if path.rsplit("/", 1)[-1] in ALLOWED_DIRTY_BASENAMES:
            continue
        blockers.append(path)
    return blockers


def main() -> None:
    if os.environ.get("APM_INSTALL_GUARD_DISABLE") == "1":
        allow_silently()

    raw = sys.stdin.read()
    if not raw.strip():
        deny("apm-install-guard: hook の入力が空でした")

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        deny("apm-install-guard: hook の入力を JSON として解釈できませんでした")

    if not isinstance(data, dict):
        deny("apm-install-guard: hook の入力が object ではありません")

    event = get(data, "hook_event_name", "hookEventName")
    tool = get(data, "tool_name", "toolName")
    if event != "PreToolUse" or tool != "Bash":
        allow_silently()

    tool_input = get(data, "tool_input", "toolInput") or {}
    if not isinstance(tool_input, dict):
        deny("apm-install-guard: tool_input が object ではありません")

    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        deny("apm-install-guard: Bash コマンドを読み取れませんでした")

    subcommand = destructive_subcommand(command)
    if subcommand is None:
        allow_silently()

    cwd = get(data, "cwd")
    if not isinstance(cwd, str) or not cwd:
        deny(f"apm-install-guard: cwd が取れないため apm {subcommand} を許可できません")

    root = repo_root(cwd)
    if root is None:
        # git リポジトリの外では git から戻す前提が成り立たないので、そもそも検査対象外
        allow_silently()

    try:
        blockers = dirty_paths(root)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        deny(f"apm-install-guard: git status を実行できませんでした: {exc}")

    if not blockers:
        allow_silently()

    listed = "\n".join(f"  {path}" for path in blockers[:20])
    more = f"\n  ... 他 {len(blockers) - 20} 件" if len(blockers) > 20 else ""
    deny(
        f"apm {subcommand} は deploy 先を上書き・削除します。{root} に未コミットの変更が "
        f"{len(blockers)} 件あるため中止しました。\n{listed}{more}\n"
        "コミットまたは stash してから再実行してください。"
        "緊急時は APM_INSTALL_GUARD_DISABLE=1 で無効化できます。"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        deny(f"apm-install-guard: 予期しない例外: {exc}")
```

- [ ] **Step 5: テストが通ることを確認する**

```bash
cd "$(git rev-parse --show-toplevel)"
uv run --directory scripts/apm-install-guard pytest -q > .cache/t4-green.log 2>&1
```

- [ ] **Step 6: lint と型検査を通す**

```bash
uv run --directory scripts/apm-install-guard ruff check --config pyproject.toml ../../home/.claude/hooks/apm-install-guard.py tests > .cache/t4-ruff.log 2>&1
```

```bash
uv run --directory scripts/apm-install-guard mypy --config-file pyproject.toml ../../home/.claude/hooks/apm-install-guard.py tests > .cache/t4-mypy.log 2>&1
```

- [ ] **Step 7: 検査機構を壊す変異で赤を確認する**

`dirty_paths` の `blockers.append(path)` を消して常に空を返す形にし、
`test_dirty_tree_denies` が赤くなることを確認する。1 箇所ずつ隔離し、cp のバックアップから戻す。

- [ ] **Step 8: README を書いてコミット**

`scripts/apm-install-guard/README.md` に hook の契約 (入力・出力・env var・スコープ) を書く。
値の二重管理を避けるため、サブコマンドの一覧や env var 名は本文へ literal で再掲せず
`home/.claude/hooks/apm-install-guard.py` を参照する形にする。

```bash
git add home/.claude/hooks/apm-install-guard.py scripts/apm-install-guard
git commit -F .cache/t4-commit-msg.txt
```

---

### Task 5: hook を配線する

本体があっても取り付けられていなければ何も守らない。config-guard の
`settings_invariants.py` は hooks セクションを一切見ておらず、既存の `tirith-check.py` ですら
配線を外しても全テストが緑のままである。この穴は本タスクでは広げないよう、配線を pin する
テストを併せて足す。

**Files:**

- Modify: `home/.claude/settings.json` (committed 版。skip-worktree の作法が要る)
- Modify: `.pre-commit-config.yaml`
- Modify: `.github/workflows/test.yml`
- Modify: `scripts/config-guard/src/config_guard/settings_invariants.py`
- Modify: `scripts/config-guard/tests/test_settings_invariants.py`

**Interfaces:**

- Consumes: Task 4 の `home/.claude/hooks/apm-install-guard.py`
- Produces: committed `settings.json` の `hooks.PreToolUse` に matcher `Bash` のグループが 2 つ
  (tirith-check と apm-install-guard)

- [ ] **Step 1: 配線を pin する検査を config-guard に足す (失敗するテストから)**

`scripts/config-guard/tests/test_settings_invariants.py` に追加する。

```python
def test_missing_required_hook_is_flagged() -> None:
    settings = {**GOOD, "hooks": {"PreToolUse": []}}
    findings = check_settings_invariants(settings)
    assert any("apm-install-guard" in f.detail for f in findings)


def test_required_hooks_present_is_clean() -> None:
    settings = {
        **GOOD,
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/tirith-check.py"'}],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/apm-install-guard.py"'}
                    ],
                },
            ]
        },
    }
    assert check_settings_invariants(settings) == []
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
cd "$(git rev-parse --show-toplevel)"
uv run --directory scripts/config-guard pytest -q > .cache/t5-red.log 2>&1
```

- [ ] **Step 3: settings_invariants.py に検査を実装する**

既存の検査と同じ形で `Finding` を返す。hook スクリプト名は 1 箇所にまとめ、散文へは再掲しない。

```python
# PreToolUse に必ず居るべき hook。本体が存在しても settings.json から外れれば何も守らないため、
# 取り付け自体を不変条件として pin する。
_REQUIRED_PRETOOLUSE_HOOKS = ("tirith-check.py", "apm-install-guard.py")


def _pretooluse_commands(settings: dict[str, Any]) -> list[str]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    groups = hooks.get("PreToolUse")
    if not isinstance(groups, list):
        return []
    commands: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        for entry in group.get("hooks") or []:
            if isinstance(entry, dict) and isinstance(entry.get("command"), str):
                commands.append(entry["command"])
    return commands
```

`check_settings_invariants` に次を足す。

```python
    commands = _pretooluse_commands(settings)
    for script in _REQUIRED_PRETOOLUSE_HOOKS:
        if not any(script in command for command in commands):
            findings.append(
                Finding(
                    source=SETTINGS_PATH,
                    detail=script,
                    message="PreToolUse に必須 hook が配線されていません",
                )
            )
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run --directory scripts/config-guard pytest -q > .cache/t5-green.log 2>&1
```

- [ ] **Step 5: committed settings.json に hook を配線する**

`home/.claude/settings.json` は skip-worktree で、working tree が live の superset になっている。
順序を誤ると live の変更が commit されないか、pre-commit が live 差分を stash して live 設定を
壊す。次の順で行う。

```bash
cd "$(git rev-parse --show-toplevel)"
cp home/.claude/settings.json .cache/t5-live-settings.json
git update-index --no-skip-worktree home/.claude/settings.json
git show HEAD:home/.claude/settings.json > home/.claude/settings.json
```

この時点で working tree は committed 版になっている。ここに hook グループを足す。
`hooks.PreToolUse` の配列へ 2 つ目のグループとして追加する (SessionStart が同じ matcher の
グループを複数持つ形が既存の前例)。

```json
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/apm-install-guard.py\""
          }
        ]
      }
```

編集後、index へ入れてから live を戻し、skip-worktree を再付与する。skip-worktree の再付与は
commit より前に行う (順序を逆にすると pre-commit が live 差分を stash する)。

```bash
git add home/.claude/settings.json
cp .cache/t5-live-settings.json home/.claude/settings.json
git update-index --skip-worktree home/.claude/settings.json
git ls-files -v home/.claude/settings.json
```

期待: `S home/.claude/settings.json`。

- [ ] **Step 6: live 側にも同じグループを足す**

committed に入れただけでは、この開発機の Claude Code は hook を読まない。live の
`home/.claude/settings.json` にも同じグループを足す (実体は symlink 先の同ファイルなので、
skip-worktree のまま直接編集する)。

- [ ] **Step 7: pre-commit と CI に配線する**

`.pre-commit-config.yaml` に `tirith-hook` 分 (`.pre-commit-config.yaml:150-176`) と同型の
4 hook を足す。`files` は `^(home/\.claude/hooks/apm-install-guard\.py|scripts/apm-install-guard/.*)$`。

`.github/workflows/test.yml` に `tirith-hook` の job (`:233-259`) と同型の job を足す。

- [ ] **Step 8: 取り付けを外す変異で赤を確認する**

committed の `settings.json` から apm-install-guard のグループを消し、config-guard が赤くなることを
確認する。これが検査機構の取り付けを外す変異。

```bash
cd "$(git rev-parse --show-toplevel)"
uv run --directory scripts/config-guard config-guard . > .cache/t5-mutated.log 2>&1
```

- [ ] **Step 9: 全検査を回してコミット**

```bash
bats scripts/tests/ > .cache/t5-bats.log 2>&1
```

```bash
uv run --directory scripts/config-guard config-guard . > .cache/t5-guard.log 2>&1
```

```bash
pre-commit run --all-files > .cache/t5-precommit.log 2>&1
```

```bash
git add .pre-commit-config.yaml .github/workflows/test.yml scripts/config-guard home/.claude/settings.json
git commit -F .cache/t5-commit-msg.txt
```

---

### Task 6: 実機で機能まで確認し、ドキュメントを更新する

ユニットテストが緑でも、シェル越しの連鎖・実際の Claude Code のロードは実機でしか確かめられない。
live smoke の合格条件は「skill が配置される」ではなく「代表 skill が実際に機能する」まで引き上げる。

ツールの自己申告で成否を判定しない。`claude plugin details` の Component inventory に Commands 行は
存在せず、`commands/` は Skills 行に畳み込まれて報告される。lockfile の `package_type` は P1 形でも
`marketplace_plugin` になる。どちらも誤読の元になることが実測済みである。

**Files:**

- Modify: `docs/issues/25_*/issue.md`
- Modify: `docs/issues/25_*/25-spec.md`

- [ ] **Step 1: bootstrap を dry-run して配線を確認する**

```bash
cd "$(git rev-parse --show-toplevel)"
bash bootstrap.sh --dry-run > .cache/t6-dryrun.log 2>&1
```

期待: `[DRY-RUN] apm install --frozen` の後に apm symlink の行が並ぶ。

- [ ] **Step 2: 実機で apm install --frozen が通ることを確認する**

ツリーが clean であることを先に確かめる (ガードが働くため)。

```bash
git status --porcelain > .cache/t6-status.txt
( cd home && apm install --frozen ) > .cache/t6-install.log 2>&1
```

- [ ] **Step 3: 配置されたファイル集合を直接見る**

```bash
find home/.claude/skills home/.claude/agents home/.claude/commands -type f | wc -l
find home/.claude/skills -maxdepth 1 -type d | sort
```

期待: 88 ファイル、skills ディレクトリ 15 個 (probe の実測値と一致)。

- [ ] **Step 4: 代表 skill が実際に機能することを確認する**

`markdown-to-pdf` は `${CLAUDE_SKILL_DIR}` を使う形に変わっているため、変数展開が効いて
`render.py` に届くかを実際に PDF を作って確かめる。

```bash
cd "$(git rev-parse --show-toplevel)"
printf '# smoke\n\n本文\n' > .cache/t6-smoke.md
uv run home/.claude/skills/markdown-to-pdf/scripts/render.py .cache/t6-smoke.md -o .cache/t6-smoke.pdf > .cache/t6-render.log 2>&1
```

```bash
ls -l .cache/t6-smoke.pdf
```

`~/.local/bin/winvm` が生きていることも確認する。

```bash
winvm --help > .cache/t6-winvm.log 2>&1
```

- [ ] **Step 5: plugin のロードを確認する**

marketplace 経由の版と apm 経由の版が同名で二重に載る期間になる (marketplace の削除は Phase 4)。
`claude plugin list --json` と、実際のスラッシュコマンド解決の両方を見る。自己申告 (Component
inventory) だけで判定しない。

```bash
claude plugin list --json > .cache/t6-plugins.json 2>&1
```

二重ロードで修飾名の解決が壊れている場合は、Phase 4 の項目 19 (marketplace 宣言の削除) を
Phase 3a へ前倒す。壊れていなければ spec の順序どおり Phase 4 に残す。

- [ ] **Step 6: issue.md のチェックを更新する**

Phase 3 の 7 項目を Phase 3a / Phase 3b に分け、3a の 4 項目にチェックを付ける。

- [ ] **Step 7: 25-spec.md を更新する**

次を反映する。

- 移行手順の Phase 3 を 3a / 3b に分割し、順序を 11 → 15 → 13 → 10 に直す。
  「分割しない」の根拠が実測で成立しないことと、その実測内容を書く
- 実測した事実に「deploy 先ディレクトリ名は末尾セグメント」「フラット分解分は deployed_files に
  記録される」「合成 apm.yml があるためパッケージ側 manifest は不要」を追加する
- ガードの設計に `apm.yml` / `apm.lock.yaml` の例外と、スコープを cwd の repo にした判断、
  `APM_INSTALL_GUARD_DISABLE` の逃げ道を書く
- 未確認事項の表に「複数 PreToolUse hook の deny/allow 合成規則」を追加し、allow を出さない
  設計で回避したことを書く

- [ ] **Step 8: PR を作る**

```bash
git push -u origin refactor/issue-25-phase3-apm-migration
```

```bash
git ls-remote --heads origin refactor/issue-25-phase3-apm-migration
```

```bash
git status -sb
```

PR 本文は Write でファイルに書き `--body-file` で渡す。

---

## Phase 3b

Phase 3a のマージ後に着手する。以下は設計の確定分であり、着手時に Phase 3a の結果
(特に `SYMLINK_PAIRS` の最終形とテストの構造) を読み直してから細部を詰める。

### 着手時の実測による補正

上の但し書きどおり着手時に実体と突き合わせた。Phase 3a が `APM_SYMLINK_PAIRS` を分離した結果、
本節が前提にしていた構造が動いている。以下は実測で確定した補正で、各 Task の本文はこれを
反映済みである。

生成先は 1 箇所ではなく 2 箇所に分ける。`SYMLINK_PAIRS` 由来 (`settings.json` / `CLAUDE.md`) は
`setup_dotfiles`、`APM_SYMLINK_PAIRS` 由来の 3 ディレクトリは `setup_apm_symlinks` へ生成する。
後者を `setup_dotfiles` に置くと `install_apm_packages` より前に走り、さらに `--dotfiles-only`
経路でも走るため、source が無い状態で symlink を張る。`setup_apm_symlinks` はこの順序を前提に
source 存在ガードを持っており、`setup_dotfiles` のループと `create_symlink` はどちらも持たない。
この回帰は dry-run では `create_symlink` が早期 return するため既存の統合テストで検出できず、
実機でだけ壊れる。

`HOME_SYMLINK_PAIRS` は該当 1 行が配列の全要素なので、空配列リテラルにはしない。bootstrap.sh は
`#!/bin/bash` + `set -euo pipefail` で /bin/bash 3.2 を踏み、空配列の `"${arr[@]}"` 展開が
`unbound variable` で exit 127 になる (実測)。配列ごと廃止し、`setup_home_symlinks` は生成した
pair を受け取る形にする。この pair は source が `$HOME` 相対で `ensure_directory` が実体を作る
規約なので、他 2 配列とは別の生成規則が要る。

mirror の allowlist は本節が書いていた向きと逆である。実在するのは
`scripts/tests/bootstrap.bats` の `unmirrored` (`.claude/hooks` / `.claude/statusline-command.sh` /
`.claude/.mcp.json`) で、これは「意図的に 2 本目を張らない target」の canonical である。生成対象は
その補集合であって allowlist そのものではない。読み違えると、`settings.json` が絶対パスで解決
させている hooks と statusline-command.sh に死んだ symlink を張る実装になる。

設定ファイルが無いときの挙動を決めた。`$HOME` 直下に該当ディレクトリが存在するのに設定ファイルが
無い場合は stderr へ警告し、ランチャは定義しない。現行の `.zshrc` は単体で自足しているため、
無言で消えると新規マシンや設定ファイル削除時に command not found になる。警告だけを出して名前は
リポジトリへ戻さない。

配列から mirror 行を消すと現在 green の pin が赤になる。`bootstrap.bats` の
`SYMLINK_PAIRS: shared Claude config is mirrored to the second account` と
`APM_SYMLINK_PAIRS:` の同名テスト、および `HOME_SYMLINK_PAIRS` の要素と件数を見る 2 件が対象で、
いずれも配列テキストを直接読む方式なので生成された mirror は原理的に見えない。生成後の形へ
書き換えることを各 Task の Files に含めた。

### Task 7: 設定ディレクトリ一覧を bootstrap.sh が読む

追加の設定ディレクトリ名を追跡外のローカル設定ファイルへ移す。
読み先は `${HOME}/.config/dotfiles/claude-config-dirs`、1 行 1 ディレクトリ名。

行の形式はドット付きにする。`$HOME` 直下のディレクトリ名そのものが
単一の真実になり、symlink の target (`$HOME/${pair##*|}`) へ無変換で使えるため。ドット無しに
すると bootstrap 側でドットを再付与する第 2 の規約が生まれて drift する。

行の内容は関数名の導出とパス組み立てに使われるため、charset を検証する。検証を通らない行は
警告して無視する。

**Files:**

- Modify: `bootstrap.sh` (`claude_config_dirs()` 追加 / `SYMLINK_PAIRS` と `APM_SYMLINK_PAIRS` から
  追加の設定ディレクトリ向けエントリを削除 / `HOME_SYMLINK_PAIRS` は配列ごと廃止 /
  mirror pair を `setup_dotfiles` と `setup_apm_symlinks` の 2 箇所へ分けて生成)
- Test: `scripts/tests/bootstrap.bats` (新規テストに加えて、配列テキストを直接読む既存の
  mirror pin を生成後の形へ書き換える。対象は `SYMLINK_PAIRS` と `APM_SYMLINK_PAIRS` の
  `mirrored to the second account` 2 件と、`HOME_SYMLINK_PAIRS` の要素と件数を見る 2 件)

`CLAUDE_CONFIG_DIRS_FILE` の代入は `# ヘルパー関数` マーカーより下へ置く。`load_bootstrap_functions`
はこのマーカーと `# メイン処理` の間だけを切り出して source するため、既存の設定変数と同じ位置
(配列の近く) へ置くとテストからは未定義になり、設定ファイルを置くテストが「常に既定だけ返る」形で
落ちる。

`run --separate-stderr` を使うので `bootstrap.bats` の冒頭に `bats_require_minimum_version 1.5.0`
が要る。無いと BW02 の警告が出る (実測)。`zshrc-claude.bats` が同じ宣言と同じフラグを既に使って
いるので、作法はそちらに揃える。

- [ ] **Step 1: 失敗するテストを書く**

```bash
@test "claude_config_dirs: returns only the default when the config file is absent" {
  run claude_config_dirs
  [ "$status" -eq 0 ]
  [ "$output" = ".claude" ]
}

@test "claude_config_dirs: returns the default plus each configured dir" {
  mkdir -p "$TEST_HOME/.config/dotfiles"
  printf '.claude-alpha\n.claude-beta\n' > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
  run claude_config_dirs
  [ "$status" -eq 0 ]
  [ "${#lines[@]}" -eq 3 ]
  [ "${lines[0]}" = ".claude" ]
  [ "${lines[1]}" = ".claude-alpha" ]
  [ "${lines[2]}" = ".claude-beta" ]
}

@test "claude_config_dirs: an empty config file yields only the default" {
  mkdir -p "$TEST_HOME/.config/dotfiles"
  : > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
  run claude_config_dirs
  [ "$status" -eq 0 ]
  [ "$output" = ".claude" ]
}

@test "claude_config_dirs: rejects entries that are not plain dot-prefixed names" {
  mkdir -p "$TEST_HOME/.config/dotfiles"
  printf '.claude-ok\n../escape\n.claude;rm -rf /\n' > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
  # 既定の run は stderr を $output へ併合する。warn が却下行を verbatim に出すため、
  # 併合したままでは「却下行が返り値に混ざっていない」ことを検査できない
  run --separate-stderr claude_config_dirs
  [ "$status" -eq 0 ]
  [ "${#lines[@]}" -eq 2 ]
  [ "${lines[0]}" = ".claude" ]
  [ "${lines[1]}" = ".claude-ok" ]
  # 却下したことが利用者へ届くことも検査する。黙って捨てると設定の typo に気づけない
  assert_contains "$stderr" "../escape"
  assert_contains "$stderr" ".claude;rm -rf /"
}

@test "claude_config_dirs: skips the default if it is also listed (no duplicates)" {
  mkdir -p "$TEST_HOME/.config/dotfiles"
  printf '.claude\n.claude-alpha\n' > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
  run claude_config_dirs
  [ "$(printf '%s\n' "$output" | grep -c '^\.claude$')" -eq 1 ]
}
```

- [ ] **Step 2: 実装する**

```bash
# 追加の Claude 設定ディレクトリ一覧を返す（1 行 1 ディレクトリ名。既定を必ず先頭に置く）。
# 一覧は追跡外の $HOME/.config/dotfiles/claude-config-dirs から読む。リポジトリに名前を
# 書かないための外部化であり、増えたら行を足すだけでリポジトリ側の変更は要らない。
# 各行は $HOME 直下のディレクトリ名そのものとして扱い、symlink の target へ無変換で使う。
# 行はパス組み立てと関数名の導出に流れるため、ドット始まりの英数字・ハイフン・ドット・
# アンダースコアだけを受け入れる。それ以外は警告して無視する（../ による脱出やコマンド
# 区切り文字の混入を防ぐ）。
CLAUDE_CONFIG_DIRS_FILE="${CLAUDE_CONFIG_DIRS_FILE:-$HOME/.config/dotfiles/claude-config-dirs}"

claude_config_dirs() {
    printf '%s\n' ".claude"

    [ -f "$CLAUDE_CONFIG_DIRS_FILE" ] || return 0

    local line
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|'#'*) continue ;;
            '.claude') continue ;;
        esac
        if ! printf '%s' "$line" | grep -Eq '^\.[A-Za-z0-9._-]+$'; then
            warn "設定ディレクトリ名として受け付けられない行を無視します: $line"
            continue
        fi
        printf '%s\n' "$line"
    done < "$CLAUDE_CONFIG_DIRS_FILE"
}
```

`SYMLINK_PAIRS` と `APM_SYMLINK_PAIRS` から追加の設定ディレクトリ向けのエントリを削除し、
`setup_dotfiles` で mirror pair を生成する。
生成対象は「既定の `.claude` へ張る pair のうち、2 アカウント側にも要るもの」。現行の
allowlist (`settings.json` / `CLAUDE.md`) と `APM_SYMLINK_PAIRS` の 3 ディレクトリが対象になる。

- [ ] **Step 3〜7**: テストの緑を確認、変異注入 3 種 (行の charset 検証を壊す / フォールバックを
  別名に変える / 生成の呼び出しを外す)、全テスト、コミット

---

### Task 8: ランチャ関数を .zshrc が生成する

`home/.zshrc:257` の追加アカウント用ランチャは関数名そのものがディレクトリ名を持つ。
設定ファイル駆動にするには関数を動的に定義する必要がある。

既定アカウントの `claude()` は `CLAUDE_CONFIG_DIR` を意図的に設定しない (Keychain の service 名
導出が変わって再ログインを誘発しうるため)。生成器はこの非対称を保存する。つまり生成するのは
「既定以外」のランチャだけで、`claude()` は現行の定義のまま残す。

生成コードは `# Claude Code 起動` マーカーブロック内に置く。bats が bash で source するため
bash 互換の構文で書く (eval による hyphen 名関数の動的定義は bash / zsh 双方で成立することを
実測済み)。定義は関数 `_claude_define_launchers` に包み、マーカーブロックの末尾で 1 度呼ぶ。
テストは `load_zshrc_claude_functions` が source した時点の定義を捨てて、`TEST_HOME` を
差し替えてからこの関数を呼び直す。

生成対象は設定ディレクトリ 1 件につき 2 関数である。素のランチャ (`<name>`) と、開発版
パッケージを読む派生 (`<name>-dev`) の両方が名前を持つ。派生は素のランチャを名前で呼ぶため、
片方だけ生成すると呼び先を失う。既定側の `claude` と `claude-dev` は現行の静的定義のまま残す。

設定ファイルが無いときは定義しない。ただし `$HOME` 直下に該当しうるディレクトリが存在するのに
設定ファイルだけが無い場合は stderr へ警告する。現行の `.zshrc` は単体で自足しているので、
無言で消えると新規マシンや設定ファイル削除時に command not found になり、原因がシェル設定側に
あることに気づけない。警告文には具体的なディレクトリ名を載せない (リポジトリへ名前を戻さない)。

**Files:**

- Modify: `home/.zshrc` の `# Claude Code 起動` マーカーブロック全体 (現行 193-326 行)。
  対象はランチャ 2 本 (`<name>` と `<name>-dev`) の静的定義の撤去と生成器の追加で、
  範囲は素のランチャだけでは足りない
- Test: `scripts/tests/zshrc-claude.bats` (新規テストに加えて、追加アカウントのランチャを
  名指しする既存テスト群の更新。いずれも設定ファイルを作らずに当該関数を呼ぶため、
  生成化すると一斉に赤くなる)

- [ ] **Step 1: 失敗するテストを書く**

```bash
@test "launcher generation defines a function per configured dir" {
  mkdir -p "$TEST_HOME/.config/dotfiles" "$TEST_HOME/.claude-alpha"
  printf '.claude-alpha\n' > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
  load_zshrc_claude_functions
  _claude_define_launchers

  run type claude-alpha
  [ "$status" -eq 0 ]
}

@test "launcher generation also defines the dev variant per configured dir" {
  mkdir -p "$TEST_HOME/.config/dotfiles" "$TEST_HOME/.claude-alpha"
  printf '.claude-alpha\n' > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
  load_zshrc_claude_functions
  _claude_define_launchers

  run type claude-alpha-dev
  [ "$status" -eq 0 ]
}

@test "generated launcher pins CLAUDE_CONFIG_DIR to its own directory" {
  mkdir -p "$TEST_HOME/.config/dotfiles" "$TEST_HOME/.claude-alpha"
  printf '.claude-alpha\n' > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
  setup_recording_claude
  load_zshrc_claude_functions
  _claude_define_launchers

  run claude-alpha
  [ "$status" -eq 0 ]
  local recorded
  recorded="$(cat "$RECORDED_LAUNCH")"
  assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-alpha"
}

@test "the default launcher still does not set CLAUDE_CONFIG_DIR" {
  setup_recording_claude
  load_zshrc_claude_functions
  _claude_define_launchers

  run claude
  [ "$status" -eq 0 ]
  local recorded
  recorded="$(cat "$RECORDED_LAUNCH")"
  refute_contains "$recorded" "CONFIG_DIR="
}

@test "no launcher is defined when the config file is absent" {
  load_zshrc_claude_functions
  _claude_define_launchers

  run type claude-alpha
  [ "$status" -ne 0 ]
}

@test "a warning is emitted when config dirs exist but the config file does not" {
  mkdir -p "$TEST_HOME/.claude-alpha"
  load_zshrc_claude_functions
  run _claude_define_launchers

  [ "$status" -eq 0 ]
  assert_contains "$output" "claude-config-dirs"
}

@test "no warning is emitted when neither the config file nor any config dir exists" {
  load_zshrc_claude_functions
  run _claude_define_launchers

  [ "$status" -eq 0 ]
  [ "$output" = "" ]
}

@test "bootstrap and zshrc agree on where the config dir list lives" {
  # 同じパスを 2 ファイルに書かざるを得ない (プロセスが別で共有できない) ため、
  # 値そのものを比較して drift を検出する。片方だけ変えると赤くなる。
  local from_bootstrap from_zshrc
  unset CLAUDE_CONFIG_DIRS_FILE
  load_bootstrap_functions
  from_bootstrap="$CLAUDE_CONFIG_DIRS_FILE"

  unset CLAUDE_CONFIG_DIRS_FILE
  load_zshrc_claude_functions
  from_zshrc="$CLAUDE_CONFIG_DIRS_FILE"

  [ -n "$from_bootstrap" ]
  [ "$from_bootstrap" = "$from_zshrc" ]
}
```

- [ ] **Step 2: 実装する**

```bash
# 追加の Claude 設定ディレクトリ一覧の置き場。bootstrap.sh の同名変数と同じ値でなければ
# ならないが、プロセスが別なので共有できない。両者が一致することはテストで pin する。
CLAUDE_CONFIG_DIRS_FILE="${CLAUDE_CONFIG_DIRS_FILE:-$HOME/.config/dotfiles/claude-config-dirs}"

# 追加アカウントのランチャを設定ファイルから生成する。
# 既定アカウントの claude() は CLAUDE_CONFIG_DIR を設定しない非対称を保つ必要があるため
# 生成対象に含めない（上の理由を参照）。
# 行の charset は bootstrap.sh と同じ規則で検証する。ここは eval に流れるため、検証を
# 通らない行は定義しない。
# 追加の設定ディレクトリが実在するかを調べる。グロブを裸で展開しないのは、zsh の nomatch が
# 既定で有効で、不一致のときエラーになるため (bats は bash で source し実シェルは zsh なので
# 両方で成立する必要がある)。find は不一致でも exit 0 を返すので出力の非空で判定する。
_claude_extra_config_dir_exists() {
  [ -n "$(find "$HOME" -maxdepth 1 -type d -name '.claude-*' -print -quit 2>/dev/null)" ]
}

_claude_define_launchers() {
  local file="$CLAUDE_CONFIG_DIRS_FILE"
  if [ ! -f "$file" ]; then
    # 設定ファイルだけが無い状態は、新規マシンや誤削除で起きる。現行の .zshrc は単体で
    # 自足していたので、無言で消えると command not found の原因がシェル設定側にあることに
    # 気づけない。名前はリポジトリへ戻さないので、警告に具体名は載せない
    if _claude_extra_config_dir_exists; then
      echo "追加の設定ディレクトリがありますが claude-config-dirs が見つかりません: $file" >&2
    fi
    return 0
  fi

  local line name
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*|'.claude') continue ;;
    esac
    printf '%s' "$line" | grep -Eq '^\.[A-Za-z0-9._-]+$' || continue
    name="${line#.}"
    # 素のランチャと開発版の派生を対で作る。派生は素のランチャを名前で呼ぶので、
    # 片方だけ生成すると呼び先を失う
    eval "
function ${name}() {
  local config_dir task_list
  config_dir=\"\$(_claude_config_dir \"\$HOME/${line}\")\" || return 1
  task_list=\"\${CLAUDE_CODE_TASK_LIST_ID:-\$(_claude_task_list_id)}\"
  _claude_task_list_notice \"\$config_dir\" \"\$task_list\"
  if [ -n \"\$task_list\" ]; then
    CLAUDE_CONFIG_DIR=\"\$config_dir\" CLAUDE_CODE_TASK_LIST_ID=\"\$task_list\" command claude \"\$@\"
  else
    CLAUDE_CONFIG_DIR=\"\$config_dir\" command claude \"\$@\"
  fi
}

function ${name}-dev() {
  local -a _CLAUDE_DEV_PLUGIN_ARGS
  _claude_dev_plugin_args || return 1
  ${name} \"\${_CLAUDE_DEV_PLUGIN_ARGS[@]}\" \"\$@\"
}
"
  done < "$file"
}

_claude_define_launchers
```

- [ ] **Step 3〜6**: 赤の確認、緑の確認、変異注入 (charset 検証を外す / 生成の呼び出しを外す)、コミット

---

### Task 9: stale symlink を撤去する

配列から消したペアの残骸は現状消えない。ただし bootstrap は過去に張った symlink の記録を
持たないため、検出は「リンク先が `$DOTFILES_DIR` 配下 かつ 現在の target 集合に無い」に
限定する。ユーザーが手で張った無関係な symlink を殺さないためである。

削除は `rm` ではなく既存の `backup_file` へ退避する。

設定ファイルが未作成のまま撤去を走らせると、生きている 2 アカウント側の symlink を stale と
誤認して撤去する経路がある。`$HOME` 直下に追加の設定ディレクトリが存在するのに設定ファイルが
無い場合は警告し、撤去だけを skip する。

存在検査はグロブを裸で展開せず `find` で行う。理由は Task 8 の同じ検査と同じで、zsh の nomatch が
既定で有効なため不一致時にエラーになる。bootstrap.sh は bash だけで動くのでここでは実害が無いが、
2 箇所で判定規則が割れると片方だけ直したときに挙動がずれるため揃える。

stale の判定は `readlink` が返すリテラルで行い、`[ -e ]` のような実体解決に依存する検査を使わない。
撤去対象は「参照先が `$DOTFILES_DIR` 配下で、かつ現在の target 集合に無い」リンクであり、
参照先が既に消えている dangling こそが典型例だからである。実体解決で判定すると、まさに撤去
すべきリンクが検査を素通りする。

**Files:**

- Modify: `bootstrap.sh`
- Test: `scripts/tests/bootstrap.bats`

- [ ] **Step 1: 失敗するテストを書く**

```bash
@test "prune_stale_symlinks removes a dotfiles-owned link that is no longer in the pair set" {
  mkdir -p "$TEST_HOME/.config"
  ln -s "$DOTFILES_DIR/home/.config/gone" "$TEST_HOME/.config/gone"
  run prune_stale_symlinks
  [ "$status" -eq 0 ]
  [ ! -L "$TEST_HOME/.config/gone" ]
}

@test "prune_stale_symlinks keeps links that are still in the pair set" {
  # setup は symlink を 1 本も張らないので、保持を検査するには自分で張る。
  # 張らずに [ -L ] を見ると「保持された」ではなく「元から無い」で必ず落ち、
  # 実装が何であっても赤になる (= 検査対象を見ていない)
  ln -s "$DOTFILES_DIR/home/.zshrc" "$TEST_HOME/.zshrc"
  run prune_stale_symlinks
  [ "$status" -eq 0 ]
  [ -L "$TEST_HOME/.zshrc" ]
}

@test "prune_stale_symlinks keeps links that point outside DOTFILES_DIR" {
  mkdir -p "$TEST_HOME/elsewhere" "$TEST_HOME/.config"
  ln -s "$TEST_HOME/elsewhere" "$TEST_HOME/.config/user-owned"
  run prune_stale_symlinks
  [ "$status" -eq 0 ]
  [ -L "$TEST_HOME/.config/user-owned" ]
}

@test "prune_stale_symlinks is skipped when config dirs exist but the config file does not" {
  mkdir -p "$TEST_HOME/.claude-alpha"
  ln -s "$DOTFILES_DIR/home/.config/gone" "$TEST_HOME/.config/gone"
  run prune_stale_symlinks
  [ "$status" -eq 0 ]
  assert_contains "$output" "claude-config-dirs"
  [ -L "$TEST_HOME/.config/gone" ]
}
```

- [ ] **Step 2〜6**: 実装、緑、変異注入 3 種、全テスト、コミット

---

### Task 10: テストをパラメータ化し Issue を閉じる

追加の設定ディレクトリ名を含むテストのうち、プロダクトコードと二重管理になっている
箇所をパラメータ化する。`statusline.bats` の 11 件はプロダクト側と結合していない任意の値なので
ダミー名 (`.claude-alpha` 等) に置き換えるだけでよい。

`@test` タイトルは静的文字列で runtime 変数を展開できず、`rules/bats-test-name-ascii-only.yml` が
文字種も制約する。タイトルからは具体名を外し、「configured dir」のような一般名にする。

**Files:**

- Modify: `scripts/tests/zshrc-claude.bats` (追加アカウントのランチャを名指しする節。
  Task 8 の生成器の形に従属するので、Task 8 の後に着手する)
- Modify: `scripts/tests/statusline.bats` (任意値なのでダミー名への置換のみ)
- Modify: `scripts/tests/bootstrap.bats` (テスト側が mirror の prefix をハードコードして
  プロダクトと二重管理になっている箇所)
- Modify: `docs/issues/11_*/issue.md` (open な Issue なので現行の規約に揃える)

`scripts/tests/test_helper.bash` は現時点で識別語を 1 件も持たない。パラメータの置き場として
新設する必要が出た場合にのみ触る。

Task 7 と Task 8 が消すのは `bootstrap.sh` と `home/.zshrc` の分で、Task 10 の担当ではない。
ただし Step 4 の残存確認は両者を含めた範囲で行う。

closed 配下の Issue は対象外とする。過去の記録を後から書き換えないため。

- [ ] **Step 1**: 識別語の出現を NUL 区切りで数え、役割別 (プロダクト / テスト / ドキュメント、
      テストは更にプロダクト結合と任意値) に分類し直す
- [ ] **Step 2**: プロダクト結合のある箇所をパラメータ化する
- [ ] **Step 3**: 任意値の箇所をダミー名に置き換える
- [ ] **Step 4**: 対象パス集合 (`bootstrap.sh` / `home/.zshrc` / `scripts/` / open な Issue) に
      スコープを絞って識別語の残存が 0 になったことを確認する。対照は同じスコープで作る。
      リポジトリ全体を引くと closed Issue の記録が必ず残って 0 にならず、ダミー名も本計画書に
      既に存在するため、スコープを揃えないと対照が「何も直さなくても通る」形になる
- [ ] **Step 5**: 全テストを回し、変異注入で pin が生きていることを確認する
- [ ] **Step 6**: issue.md の Phase 3b にチェックを付け、PR を作る
