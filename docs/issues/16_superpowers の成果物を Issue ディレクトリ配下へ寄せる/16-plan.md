# Issue 単位で成果物を束ねる置き場規約 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** superpowers の spec と plan を Issue ディレクトリ配下へ寄せ、その規約を再利用可能な opt-in skill として切り出す。

**Architecture:** 規約の実体を claude-plugins の新 skill `dev-workflow:issue-scoped-artifacts` に 1 箇所だけ置き、各プロジェクトの CLAUDE.md にはポインタ 1 行を置く 2 層構成。検出は移植可能な pre-commit の `language: fail` hook 1 本のみとし、上流 skill の既定パスに成果物が落ちた場合を捕捉する。

**Tech Stack:** Markdown (skill / spec / plan / Issue)、YAML (pre-commit 設定)、git (移行は `git mv`)。新しい実行時依存は追加しない。

## Global Constraints

- 設計の canonical は `docs/issues/16_superpowers の成果物を Issue ディレクトリ配下へ寄せる/16-spec.md`。判断が割れたら spec を読む。
- Issue ディレクトリ配下の成果物名は `<NNN>-spec.md` と `<NNN>-plan.md`。`<NNN>` はディレクトリ名先頭の番号と一致させる。
- git / gh へ渡す日本語の散文は Bash のコマンド文字列に載せない。`<repo>/.cache/` に Write ツールでファイルを書き `-F` / `--body-file` で渡す。手順の canonical は `dev-workflow:commit-and-pr-message`。
- コミットメッセージの prefix はグローバル CLAUDE.md の「[MUST] コミットメッセージ」節が canonical。
- `ls` はユーザーの zsh profile で `ls -aG` にエイリアスされている。件数を数えるときは `ls | wc -l` を使わず `find ... -type f | wc -l` か `/bin/ls` を使う。使うと `.` と `..` の 2 件が上乗せされる。
- git コマンドで日本語パスを扱うときは `-c core.quotepath=false` を付ける。付けないとパスが 8 進エスケープされ grep や件数が化ける。
- exit code で成否を判定するコマンドはパイプにも後続コマンドにも繋がず単独で実行する。出力を絞るときは `cmd > <file> 2>&1` だけを実行し、ファイルは次の呼び出しで読む。
- dotfiles の `home/.claude/settings.json` は `git update-index --skip-worktree` 下にある。ブランチ操作の後は `git ls-files -v home/.claude/settings.json` が `S` を返すことを確認する。
- 追跡下のファイルに `/Users/<name>` 形式の絶対パスを書かない。dotfiles は PUBLIC リポジトリで、`.gitleaks.toml` の `macos-user-path` ルール (`/Users/[a-z_][a-z0-9._-]*`) が pre-commit で弾く。ホームからの相対で `~/Develop/<repo>` と書く。本計画の初稿はこれを踏んで 35 件検出された。

## 前提ゲート

- [ ] **claude-plugins の PR #5 がマージ済みであること**

`gh pr merge 5 --squash` は Claude Code の auto mode classifier にブロックされるため、ユーザーが手動で実行する。実行後に次で確認する。

```bash
cd ~/Develop/claude-plugins && gh pr view 5 --json state,mergedAt
```

Expected: `"state":"MERGED"` と非 null の `mergedAt`。

未マージのまま Task 1 に進んではいけない。marketplace が directory ソースでこの作業ディレクトリを直接指すため、live な採番挙動が未マージブランチに乗っており、main を基点に新ブランチを切ると採番が退行した状態から始まる。

---

### Task 1: claude-plugins に issue-scoped-artifacts skill を新設する

**Files:**
- Create: `~/Develop/claude-plugins/plugins/dev-workflow/skills/issue-scoped-artifacts/SKILL.md`
- Test: スクラッチリポジトリでの live smoke (下記 Step 4)

**Interfaces:**
- Consumes: なし (最初のタスク)
- Produces: skill 名 `dev-workflow:issue-scoped-artifacts`。Task 4 の CLAUDE.md ポインタがこの名前を参照する。skill が提示する pre-commit スニペットの hook id は `issue-scoped-artifacts` で、Task 3 の `.pre-commit-config.yaml` がこの id を使う。

- [ ] **Step 1: ブランチを切る**

```bash
cd ~/Develop/claude-plugins && git checkout main && git pull --ff-only && git checkout -b feat/issue-scoped-artifacts-skill
```

- [ ] **Step 2: SKILL.md を書く**

frontmatter は次の literal をそのまま使う。`description` は opt-in の停止条件を含むこと。ポインタが無いプロジェクトで何もしないという判断は harness の機能ではなく、この description と本文の散文だけで実現される (`security-blue-red-team` と `web-monkey-qa` の profile 方式と同じ機構)。

```markdown
---
name: issue-scoped-artifacts
description: superpowers の brainstorming や writing-plans が spec / plan を書き出す直前に使う。成果物を docs/superpowers/ ではなく Issue ディレクトリ配下 (docs/issues/<NNN>_<title>/<NNN>-spec.md と <NNN>-plan.md) へ置く規約と、採用手順・移行手順を持つ。プロジェクトの CLAUDE.md にこの skill を指すポインタがある場合にのみ適用し、ポインタが無いプロジェクトでは何もせず既定の置き場に従う。
---
```

本文は次の節を持つ。各節の内容は指定のとおりにする。

`## 適用条件` — プロジェクトの CLAUDE.md に本 skill を指すポインタがあるときのみ適用する。無ければ何もせず上流 skill の既定パスに従い、その旨だけ伝えて終わる。副作用を一切残さない。

`## 規約` — Issue ディレクトリ配下に置くファイルを表で示す。`issue.md` (必須、`dev-workflow:in-repo-issue` が書く)、`<NNN>-spec.md` (任意、brainstorming)、`<NNN>-plan.md` (任意、writing-plans)、`notes/<name>.md` (任意、手動)。`<NNN>` はディレクトリ名先頭の番号と一致させる。

`## なぜ番号を前置するか` — subagent-driven-development の workspace 名が plan ファイルの basename から導出されるため (`sdd-workspace` の `basename "$plan" .md`)。`plan.md` にすると全 Issue の workspace が `.superpowers/sdd/plan/` へ集中し、上流が plan ごとのサブディレクトリ化で潰したばかりの衝突を再現する。番号前置で basename が大域一意になる。副次的に、期待されるファイル名がディレクトリ名の純粋関数になる。

`## 起票のタイミング` — spec を書き出す直前に起票する。対話フェーズは Issue を必要としない。その時点ではタイトルもスコープも未確定であり、探索の結果「作らない」と決まった場合に空の Issue が残る。既に Issue がある作業ではそれを使う。

`## 採用手順` — 3 つの手順を示す。(1) プロジェクトの CLAUDE.md に下記のポインタ 1 行を足す (2) `.pre-commit-config.yaml` に下記の hook を足す (3) `.gitignore` に `.superpowers/` を足す。(3) の理由は、subagent-driven-development の補助スクリプトが `.superpowers/sdd/.gitignore` を自動生成する一方、brainstorming の visual companion が書く `.superpowers/brainstorm/` は ignore されず `git status` に出るため。

ポインタの推奨文面は次の literal とする。

```markdown
- superpowers の spec / plan は `dev-workflow:issue-scoped-artifacts` skill の規約に従って Issue ディレクトリ配下へ置く
```

pre-commit スニペットは次の literal とする。既に `repo: local` エントリがあるプロジェクトでは、その `hooks:` 配下に `- id:` から下を足す。

```yaml
  - repo: local
    hooks:
      - id: issue-scoped-artifacts
        name: spec と plan は Issue ディレクトリ配下へ置く
        language: fail
        entry: "この成果物は docs/issues/<NNN>_<title>/<NNN>-spec.md または <NNN>-plan.md へ置く"
        files: '^docs/superpowers/(plans|specs)/'
```

`## 検出の範囲` — 捕捉するのは「CLAUDE.md の上書きが効かず成果物が上流 skill の既定パスへ落ちる」失敗モードのみ。既定パスは `docs/superpowers/plans/` と `docs/superpowers/specs/` の 2 つしか存在しないためこの失敗モードは漏れなく捕捉される。一方で Issue ディレクトリ配下のファイル名違反 (`spec.md` のような番号なし、`15_` 配下の `16-spec.md` のような番号不一致) は検出しない。ファイル名まで見るにはリポジトリ固有のロジックが要り、全プロジェクトで同一という性質を失うため意図的に見送っている。

`## language: fail を選ぶ理由` — 移植性。`ENVIRONMENT_DIR` が None で `install_environment` が no_install なので環境構築が発生せず、Python も Node も要らない。実行可能スクリプトを配って呼ばせる方式は、plugin の実体パスをシェルから解決する手段が無いこと (`CLAUDE_PLUGIN_ROOT` はシェルに export されない)、絶対パス直書きが gitleaks の macos-user-path ルールに抵触すること、pre-commit の外部 repo 参照が private リポジトリの clone 認証で詰まることの 3 点で塞がっている。

`## 既存プロジェクトの移行手順` — (1) 対応 Issue が 1 対 1 で明確な成果物だけを `git mv` で Issue ディレクトリ配下へ移す (2) 対応が曖昧なものは判断を要するので `docs/superpowers/archive/` へ退避する。判断を要する対応付けは、忘れが検出できない人手のリンクと同じ性質を持つ (3) `docs/superpowers/plans/` と `docs/superpowers/specs/` を空にする (4) 移行で切れる参照を探す。Markdown リンクでない参照 (コード内のコメントや文字列) はリンクチェッカーで守られないので `git grep` で旧パスの不在を確認する。

`## 関連` — `dev-workflow:in-repo-issue` (Issue の起票・更新・クローズ。補助資料をディレクトリ内に置いてよいという規定を持つ)、`superpowers:brainstorming` と `superpowers:writing-plans` (出力先を規定し、ユーザー設定による上書きを明示的に許可している)、`superpowers:subagent-driven-development` (workspace 名の導出元)。

- [ ] **Step 3: スクラッチリポジトリを作って hook スニペットを検証する**

skill が配るスニペットが実際に機能することを確かめる。ここで検証しないと、誤ったスニペットが全プロジェクトへ配られる。

```bash
mkdir -p ~/Develop/claude-plugins/.cache/snippet-smoke && cd ~/Develop/claude-plugins/.cache/snippet-smoke && git init -q . && git config user.email t@e && git config user.name t && mkdir -p docs/superpowers/specs 'docs/issues/16_テスト'
```

`.pre-commit-config.yaml` を Write ツールで作る。中身は Step 2 のスニペットに `repos:` を付けたもの。

```yaml
repos:
  - repo: local
    hooks:
      - id: issue-scoped-artifacts
        name: spec と plan は Issue ディレクトリ配下へ置く
        language: fail
        entry: "この成果物は docs/issues/<NNN>_<title>/<NNN>-spec.md または <NNN>-plan.md へ置く"
        files: '^docs/superpowers/(plans|specs)/'
```

規約に従うファイルと違反するファイルを 1 つずつ置いて stage する。

```bash
cd ~/Develop/claude-plugins/.cache/snippet-smoke && printf '# ok\n' > 'docs/issues/16_テスト/16-spec.md' && printf '# ng\n' > docs/superpowers/specs/2026-08-02-x-design.md && git add -A
```

- [ ] **Step 4: 違反ありで落ちることを確認する**

```bash
cd ~/Develop/claude-plugins/.cache/snippet-smoke && pre-commit run --all-files > run1.txt 2>&1
```

Expected: exit 1。`run1.txt` を読み、`Failed` と違反ファイル名 `docs/superpowers/specs/2026-08-02-x-design.md` の両方が出ていること。

- [ ] **Step 5: 違反なしで通ることを確認する**

この negative case を確認しなければ「何をしても落ちる hook」と区別できない。

```bash
cd ~/Develop/claude-plugins/.cache/snippet-smoke && git rm -q --cached docs/superpowers/specs/2026-08-02-x-design.md && rm -rf docs/superpowers && pre-commit run --all-files > run2.txt 2>&1
```

Expected: exit 0。`run2.txt` に `(no files to check)Skipped` が出ていること。日本語ディレクトリ名の `docs/issues/16_テスト/16-spec.md` が誤検出されていないこと。

- [ ] **Step 6: スクラッチを片付ける**

```bash
rm -rf ~/Develop/claude-plugins/.cache/snippet-smoke
```

- [ ] **Step 7: コミットして PR を出す**

コミット本文を `~/Develop/claude-plugins/.cache/commit-issue-scoped-artifacts.txt` に Write ツールで書き、prefix は `feat:` を使う。PR 本文は `~/Develop/claude-plugins/.cache/pr-issue-scoped-artifacts.md` に書き、dotfiles の Issue #16 を参照する。

```bash
cd ~/Develop/claude-plugins && git add plugins/dev-workflow/skills/issue-scoped-artifacts/SKILL.md && git commit -F .cache/commit-issue-scoped-artifacts.txt
```

push と PR 作成はグローバル CLAUDE.md の push ルールに従う。push 後は `git ls-remote --heads origin feat/issue-scoped-artifacts-skill` と `git status -sb` で成否を直接確認する。

---

### Task 2: dotfiles の既存成果物を移行し、切れる参照を直す

**Files:**
- Move: `docs/superpowers/plans/2026-07-31-markdown-link-check.md` → `docs/issues/closed/15_docs の相対リンクを pre-commit で検査する/15-plan.md`
- Move: `docs/superpowers/specs/2026-07-31-markdown-link-check-design.md` → `docs/issues/closed/15_docs の相対リンクを pre-commit で検査する/15-spec.md`
- Move: 残り 12 件を `docs/superpowers/archive/` へ
- Create: `docs/superpowers/archive/README.md`
- Modify: `home/.claude/hooks/handoff-sentinel.py:8`
- Modify: `scripts/handoff-sentinel/README.md:5`
- 書き換えない: 移行する 14 ファイルの中身 (旧パスへの平文参照 8 箇所を当時の記録として残す)

**Interfaces:**
- Consumes: なし
- Produces: `docs/superpowers/plans/` と `docs/superpowers/specs/` が存在しない状態。Task 3 の hook はこの状態を前提にする。

このタスクは Task 3 より必ず先に行う。順序が逆だと `pre-commit run --all-files` が 14 件の既存ファイルにマッチして即座に赤くなる。通常の `git commit` では staged ファイルしか hook に渡らないため気づかずに進み、後から `--all-files` を打った人が壊れたと誤診する窓ができる。

- [ ] **Step 1: dotfiles のブランチを確認する**

```bash
cd ~/Develop/dotfiles && git branch --show-current && git status --short
```

Expected: `refactor/issue-scoped-artifacts`、working tree は clean。異なる場合は `dev-workflow:git-branch-switcher` で切り替える。

- [ ] **Step 2: Issue #15 へ 2 件を移す**

```bash
cd ~/Develop/dotfiles && git mv docs/superpowers/plans/2026-07-31-markdown-link-check.md 'docs/issues/closed/15_docs の相対リンクを pre-commit で検査する/15-plan.md' && git mv docs/superpowers/specs/2026-07-31-markdown-link-check-design.md 'docs/issues/closed/15_docs の相対リンクを pre-commit で検査する/15-spec.md'
```

- [ ] **Step 3: 残り 12 件を archive へ退避する**

```bash
cd ~/Develop/dotfiles && mkdir -p docs/superpowers/archive && git mv docs/superpowers/plans/*.md docs/superpowers/archive/ && git mv docs/superpowers/specs/*.md docs/superpowers/archive/ && rmdir docs/superpowers/plans docs/superpowers/specs
```

- [ ] **Step 4: 移行結果を確認する**

```bash
cd ~/Develop/dotfiles && test ! -d docs/superpowers/plans && test ! -d docs/superpowers/specs && find docs/superpowers/archive -type f -name '*.md' | wc -l
```

Expected: exit 0 かつ `12`。

- [ ] **Step 5: 切れる参照 2 件を直す**

Edit ツールで置換する。どちらも Markdown リンク記法ではないため Issue #15 の相対リンク検査では守られない。

`home/.claude/hooks/handoff-sentinel.py:8`

```
仕様: docs/superpowers/specs/2026-07-03-session-handoff-design.md
```

を次に変える。

```
仕様: docs/superpowers/archive/2026-07-03-session-handoff-design.md
```

`scripts/handoff-sentinel/README.md:5`

```
仕様は `docs/superpowers/specs/2026-07-03-session-handoff-design.md` を参照。
```

を次に変える。

```
仕様は `docs/superpowers/archive/2026-07-03-session-handoff-design.md` を参照。
```

- [ ] **Step 6: 移行した文書には README を添え、中身は書き換えない**

移行する 14 ファイル自身が旧パスへの平文参照を 8 箇所持っている。これらは書き換えない。性質が 2 種類あり、`設計 spec: docs/superpowers/specs/...` のような生きたポインタと、`git add docs/superpowers/specs/...` のような当時のコマンド転記や当時のファイル内容の転記が混在している。後者を書き換えると「当時こう実行した」という記録が事実と食い違う。前者だけを選んで直すには 1 行ずつの人の判断が要り、判断を要する対応付けを避けるという本設計の方針に反する。

代わりに `docs/superpowers/archive/README.md` を Write ツールで新設し、次の内容を書く。

- ここにあるのは Issue との対応が 1 対 1 で確定しなかった過去の設計と計画であること
- 文書内のパス参照は移行前のディレクトリ構成 (`docs/superpowers/plans/` と `docs/superpowers/specs/`) を指したままであり、記録として当時のまま残していること
- 現行の置き場規約は `dev-workflow:issue-scoped-artifacts` skill が canonical であること

Issue #15 へ移した 2 件も同じ性質を持つが、Issue ディレクトリ配下にあることで「Issue #15 の作業記録」という文脈が明らかなので個別の断りは置かない。

- [ ] **Step 7: 生きた参照に旧パスが残っていないことを確認する**

```bash
cd ~/Develop/dotfiles && git -c core.quotepath=false grep -n -e 'docs/superpowers/plans' -e 'docs/superpowers/specs' -- ':!docs/issues/16_*' ':!docs/superpowers/archive' ':!docs/issues/closed/15_*'
```

Expected: exit 1 (ヒット 0 件)。除外する 3 つはいずれも意図的に旧パスを含む。Issue #16 の spec と plan は設計の記述として、archive と Issue #15 配下の移行済み文書は当時の記録として旧パスに言及する。ここでヒットが出たら、それは直すべき生きた参照である。

- [ ] **Step 8: config-guard で相対リンクの健全性を確認する**

```bash
cd ~/Develop/dotfiles && pre-commit run config-guard-scan --all-files > .cache/cg-after-move.txt 2>&1
```

Expected: exit 0。`.cache/cg-after-move.txt` を読み `Passed` であること (`Skipped` ではないこと)。

移動する 14 ファイルが持つ Markdown リンク記法はすべてコードフェンス内とインラインコード内にある (リンク検査そのもののテストデータと記法の例示)。`markdown_links` はコード領域を除外するため、移動で基準ディレクトリが変わっても判定は変わらない。ここが赤くなった場合は移行以外の原因を疑う。

- [ ] **Step 9: コミットする**

本文を `.cache/commit-migrate-artifacts.txt` に Write ツールで書く。prefix は `refactor:`。

```bash
cd ~/Develop/dotfiles && git add -A && git commit -F .cache/commit-migrate-artifacts.txt
```

---

### Task 3: pre-commit に検出 hook を足し live smoke で確かめる

**Files:**
- Modify: `.pre-commit-config.yaml` (`config-guard-scan` の定義の直後、`mise-update-notifier-ruff-check` の直前に挿入)

**Interfaces:**
- Consumes: Task 1 が確定させた hook id `issue-scoped-artifacts` とスニペットの literal。Task 2 が空にした `docs/superpowers/{plans,specs}/`。
- Produces: なし

- [ ] **Step 1: hook を挿入する**

Edit ツールで `config-guard-scan` の定義ブロックの直後に次を足す。既存の `repo: local` エントリの `hooks:` 配下なので `- id:` から書く。

```yaml
      # 上流 superpowers の brainstorming / writing-plans は既定でこの 2 パスへ書く。
      # プロジェクト CLAUDE.md による上書きが効かなかった場合ここに落ちるので、
      # そのときだけ落として置き場を知らせる。規約の canonical は
      # dev-workflow:issue-scoped-artifacts skill が持つ。
      - id: issue-scoped-artifacts
        name: spec と plan は Issue ディレクトリ配下へ置く
        language: fail
        entry: "この成果物は docs/issues/<NNN>_<title>/<NNN>-spec.md または <NNN>-plan.md へ置く"
        files: '^docs/superpowers/(plans|specs)/'
```

- [ ] **Step 2: 既存ファイルで誤発火しないことを確認する**

```bash
cd ~/Develop/dotfiles && pre-commit run issue-scoped-artifacts --all-files > .cache/hook-clean.txt 2>&1
```

Expected: exit 0。`.cache/hook-clean.txt` に `(no files to check)Skipped` が出ていること。Task 2 の移行が済んでいれば必ずこうなる。赤い場合は移行の取りこぼしなので Task 2 の Step 4 と Step 6 に戻る。

- [ ] **Step 3: 違反ファイルを置いて落ちることを確認する**

```bash
cd ~/Develop/dotfiles && mkdir -p docs/superpowers/specs && printf '# smoke\n' > docs/superpowers/specs/2026-08-02-smoke-design.md && git add docs/superpowers/specs/2026-08-02-smoke-design.md && pre-commit run issue-scoped-artifacts --all-files > .cache/hook-violation.txt 2>&1
```

Expected: exit 1。`.cache/hook-violation.txt` に `Failed` と `docs/superpowers/specs/2026-08-02-smoke-design.md` の両方が出ていること。落ちなければ hook が機能していないので `files:` のパターンを見直す。

- [ ] **Step 4: 違反ファイルを取り除いて緑に戻す**

```bash
cd ~/Develop/dotfiles && git rm -q --cached docs/superpowers/specs/2026-08-02-smoke-design.md && rm -rf docs/superpowers/specs && pre-commit run issue-scoped-artifacts --all-files > .cache/hook-restored.txt 2>&1
```

Expected: exit 0。`.cache/hook-restored.txt` が `Skipped` であること。`git status --short` で smoke 用ファイルが残っていないことも確認する。

- [ ] **Step 5: コミットする**

本文を `.cache/commit-artifact-hook.txt` に Write ツールで書く。prefix は `ci:`。

```bash
cd ~/Develop/dotfiles && git add .pre-commit-config.yaml && git commit -F .cache/commit-artifact-hook.txt
```

---

### Task 4: dotfiles の CLAUDE.md にポインタを置く

**Files:**
- Modify: `CLAUDE.md` (「[MUST] 必ず守らなければならないルール」節の箇条書きへ 1 行追加)

**Interfaces:**
- Consumes: Task 1 が確定させた skill 名 `dev-workflow:issue-scoped-artifacts` とポインタの推奨文面
- Produces: なし

規約の中身は書かない。skill 名だけを参照する。複数プロジェクトに同じ規約が散らばって drift するのを避けるためであり、これは spec の設計判断である。

- [ ] **Step 1: ポインタを足す**

Edit ツールで「[MUST] 必ず守らなければならないルール」節の箇条書きに次の 1 行を足す。挿入位置は `dev-workflow:git-branch-switcher` に言及する行の直後とする。作業開始前の手順に隣接させる。

```markdown
- superpowers の spec / plan は `dev-workflow:issue-scoped-artifacts` skill の規約に従って Issue ディレクトリ配下へ置く
```

- [ ] **Step 2: 記述が 1 行に収まり規約の中身を含んでいないことを確認する**

```bash
cd ~/Develop/dotfiles && grep -n 'issue-scoped-artifacts' CLAUDE.md
```

Expected: 1 行だけヒットする。ヒット行に `<NNN>-spec.md` のような規約の詳細が含まれていないこと。

- [ ] **Step 3: コミットする**

本文を `.cache/commit-claudemd-pointer.txt` に Write ツールで書く。prefix は `docs:`。

```bash
cd ~/Develop/dotfiles && git add CLAUDE.md && git commit -F .cache/commit-claudemd-pointer.txt
```

---

### Task 5: .superpowers/ を gitignore し sdd を掃除する

**Files:**
- Modify: `.gitignore`
- Delete: `.superpowers/sdd/` (追跡外。コミットには現れない)

**Interfaces:**
- Consumes: なし
- Produces: なし

この 2 つは因果で結ばれている。現在 `.superpowers/` が git から隠れているのは `.superpowers/sdd/.gitignore` の `*` だけによるもので、sdd を消すとその .gitignore も消えて `.superpowers/` が丸見えになる。brainstorming の visual companion が書く `.superpowers/brainstorm/` はそもそも ignore されていない。

- [ ] **Step 1: 削除前に対象を確認する**

```bash
cd ~/Develop/dotfiles && find .superpowers -mindepth 1 -type f | wc -l && du -sh .superpowers/sdd && git ls-files .superpowers | wc -l
```

Expected: `107`、`1.6M` 前後、そして追跡ファイルは `0`。追跡ファイルが 0 でない場合は削除せず停止して報告する。

- [ ] **Step 2: .gitignore に追記する**

Edit ツールで `.gitignore` に次の 2 行を足す。既存の `.cache/` の行の近くに置く。

```gitignore
# superpowers の作業領域 (sdd の workspace と brainstorming の visual companion)
.superpowers/
```

- [ ] **Step 3: ignore が効くことを確認する**

```bash
cd ~/Develop/dotfiles && git check-ignore -v .superpowers/brainstorm/x .superpowers/sdd/y
```

Expected: exit 0 かつ 2 行とも `.gitignore` 由来で報告される。sdd 側の `.gitignore` ではなくリポジトリの `.gitignore` が効いていること。

- [ ] **Step 4: sdd を削除する**

```bash
cd ~/Develop/dotfiles && rm -rf .superpowers/sdd && find .superpowers -mindepth 1 | wc -l
```

Expected: `0`。次回 plan 実行時に `sdd-workspace` が `<NNN>-plan/` 形式のサブディレクトリを新規生成するため、上流最新形式への追随もこれで完了する。

- [ ] **Step 5: 作業ツリーに余計な変更が出ていないことを確認する**

```bash
cd ~/Develop/dotfiles && git status --short
```

Expected: `.gitignore` の変更 1 件のみ。`.superpowers` 関連の未追跡ファイルが出ていないこと。

- [ ] **Step 6: コミットする**

本文を `.cache/commit-superpowers-gitignore.txt` に Write ツールで書く。prefix は `chore:`。

```bash
cd ~/Develop/dotfiles && git add .gitignore && git commit -F .cache/commit-superpowers-gitignore.txt
```

---

### Task 6: Issue #16 本文を実態に合わせタスクを消化する

**Files:**
- Modify: `docs/issues/16_superpowers の成果物を Issue ディレクトリ配下へ寄せる/issue.md`

**Interfaces:**
- Consumes: Task 2 から Task 5 までの完了
- Produces: なし

- [ ] **Step 1: 数値と主張を実態に合わせる**

Edit ツールで 4 箇所を直す。

16 行目の `.superpowers/sdd/` の件数 `94` を `107` にする。

20 行目の「plans と specs が扱う 6 テーマは、既存の Issue のタイトルとおおむね対応が付かない」を実測に合わせる。実際は 7 テーマのうち 2 テーマが 3 つの Issue に対応していた (config-drift-guard が Issue #1 と #2、markdown-link-check が Issue #15)。「ほとんど対応が付かない」という方向は正しいが「全く付かない」ではない旨を書く。

56 行目の見出し「既存の 12 ファイルをどうするか」を「既存の 14 ファイルをどうするか」にする。

69 行目のタスク「既存の 12 ファイルの移行方針を決める」を「既存の 14 ファイルの移行方針を決める」にする。

- [ ] **Step 2: タスクのチェックボックスを消化する**

8 件すべてを `- [x]` にする。最後の「sdd の置き場を上流の最新形式に追随させる」は Task 5 の削除により次回生成時に自動で満たされるので、その旨を 1 行添える。

- [ ] **Step 3: 相対リンクが健全であることを確認する**

```bash
cd ~/Develop/dotfiles && pre-commit run config-guard-scan --all-files > .cache/cg-issue-body.txt 2>&1
```

Expected: exit 0 かつ `.cache/cg-issue-body.txt` が `Passed`。

- [ ] **Step 4: コミットする**

本文を `.cache/commit-issue16-body.txt` に Write ツールで書く。prefix は `docs(issues):`。

```bash
cd ~/Develop/dotfiles && git add 'docs/issues/16_superpowers の成果物を Issue ディレクトリ配下へ寄せる/issue.md' && git commit -F .cache/commit-issue16-body.txt
```

---

### Task 7: マージ前ゲートを通して PR を出す

**Files:**
- なし (ゲートの指摘に応じて変更が入る場合はその都度)

**Interfaces:**
- Consumes: Task 1 から Task 6 までの完了
- Produces: なし

- [ ] **Step 1: 全 hook を通す**

```bash
cd ~/Develop/dotfiles && pre-commit run --all-files > .cache/precommit-all.txt 2>&1
```

Expected: exit 0。`.cache/precommit-all.txt` を読み、`Failed` が 1 件も無いこと。`issue-scoped-artifacts` が `Skipped` であること。

- [ ] **Step 2: マージ前ゲートを通す**

`dev-workflow:pre-merge-quality-gate` skill を使う。simplify / code-reviewer / boy-scout-sweep が並列で走る。指摘は confidence の高いものから対応する。

- [ ] **Step 3: push して PR を出す**

push はグローバル CLAUDE.md の push ルールに従う。push 後は `git ls-remote --heads origin refactor/issue-scoped-artifacts` と `git status -sb` で成否を直接確認する。

PR 本文を `.cache/pr-issue-scoped-artifacts.md` に Write ツールで書く。`Closes` リンクの書式は `dev-workflow:in-repo-issue` が canonical。claude-plugins 側の PR への参照も入れる。

```bash
cd ~/Develop/dotfiles && gh pr create --assignee @me --base main --body-file .cache/pr-issue-scoped-artifacts.md --title "refactor: superpowers の成果物を Issue ディレクトリ配下へ寄せる"
```

- [ ] **Step 4: PR が作られ本文が載ったことを確認する**

```bash
cd ~/Develop/dotfiles && gh pr view --json url,title,body
```

---

## 今回やらないこと

- CI ミラーの追加。このリポジトリの CI は pre-commit を実行せず hook を再実装してミラーする方式なので、ミラーを足すとパスの literal が 2 箇所に増えて drift する。加えて CLAUDE.md が CI コストを抑える方針を持つ。捕捉したい失敗モードはローカルの pre-commit で捕捉されるため、ミラー無しで足りると判断した。
- リポジトリルートの README の更新。`grep -in -e issue -e superpower -e spec -e plan README.md` がヒット 0 件で、更新すべき記述が存在しない (`docs/superpowers/archive/README.md` の新設は別で、Task 2 で行う)。
- 移行する 14 ファイルの中身の書き換え。旧パスへの平文参照 8 箇所は当時の記録として残す。
- Issue ディレクトリ配下のファイル名検査。spec の「今回やらないこと」に従う。
- `dev-workflow:in-repo-issue` の `SKILL.md:13` の書き換え。同行は補助資料を任意として汎用的に規定しており、本規約はその具体化にあたるため矛盾しない。
- 既存 12 ファイルへの遡及 Issue 起票。
