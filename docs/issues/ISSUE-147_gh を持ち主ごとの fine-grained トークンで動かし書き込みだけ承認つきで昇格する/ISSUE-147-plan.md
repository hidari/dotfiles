# ISSUE-147 実装プラン: gh-token-shim

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- Goal: PATH の先頭に置く gh の shim が、持ち主と操作から fine-grained のトークンを選んで本物の gh へ渡す
- Architecture: apm-guard と同じ形。判定は `lib.sh` の純粋な関数に寄せ、入口の `gh` は設定の読み込み、トークンの取得、委譲だけを持つ。外部 (`security` / `op` / 本物の `gh` / `git`) は PATH 上の偽物で差し替えてテストする
- Tech Stack: bash (macOS の /bin/bash 3.2 でも動くこと)、bats、shellcheck
- Spec: 同じディレクトリの `ISSUE-147-spec.md`

## Global Constraints

- 実体は `scripts/gh-token-shim/gh` と `scripts/gh-token-shim/lib.sh`。配置先は `~/.local/libexec/gh-token-shim/`
- bash 3.2 で動くこと (連想配列、`${var,,}`、`mapfile` を使わない)。小文字化は `tr '[:upper:]' '[:lower:]'`
- stderr のメッセージは英語で、接頭辞は `gh-token-shim: `。トークンの値は、どの出力にも出さない
- キーチェーン: service `gh-token-shim`、account `<owner>:read`。owner は小文字
- 1Password の参照: `op://<vault>/gh-write-<owner>/credential`。owner は小文字
- 設定: `${GH_TOKEN_SHIM_CONFIG:-$HOME/.config/gh-token-shim/config}`。行の形は `vault=<名前>` / `default_owner=<owner>` / `owner=<owner>` (`owner` は複数行)。`#` で始まる行と空行は読み飛ばす。source しない
- 持ち主の名前の検証: `^[A-Za-z0-9]([A-Za-z0-9-]{0,38})$`
- コメントは日本語

## Review Focus

- 書き込みの判定から漏れた書き込みが、強いトークンへ倒れずに普段使いのトークンで走ること(安全側)。判定が強い側へ誤ることのほうが問題になる。Task 1 の表は「書き込みではない」側の行も同じ数だけ持つ
- トークンを持たない持ち主への書き込み。既定の持ち主の強いトークンへ流れると、意味のない承認になる。止める(Task 3 で pin)
- `-XPOST` / `--method=POST` / `-fkey=v` のような連結した形のフラグ(Task 1 で pin)
- `origin` が GitHub 以外の host を指すとき、その URL の持ち主を GitHub の持ち主と取り違えないこと(Task 2 で pin)
- 呼び手が `GH_TOKEN` を設定済みのときは、キーチェーンも op も呼ばないこと(Task 3 で、偽の `security` / `op` の起動記録が空であることを pin)

## ファイル

- Create `scripts/gh-token-shim/lib.sh`: 判定の純粋な関数(分類、持ち主、設定の解釈)
- Create `scripts/gh-token-shim/gh`: 入口。実行権限つき
- Create `scripts/gh-token-shim/config.example`: 設定の例。org と vault は架空の名前にする
- Create `scripts/tests/gh-token-shim.bats`
- Modify `bootstrap.sh` (`SYMLINK_PAIRS` に2行)、`home/.zshrc` (apm-guard の PATH の行の直後)、`.pre-commit-config.yaml` と `.github/workflows/test.yml` (shellcheck の対象に `scripts/gh-token-shim/gh`)、`scripts/tests/test_helper.bash` (`GH_TOKEN_SHIM_LIB` の既定値)

### Task 1: 操作の分類 `ghts_classify`

Files: `scripts/gh-token-shim/lib.sh`、`scripts/tests/gh-token-shim.bats`

Interfaces:
- Produces: `ghts_classify "$@"`。gh の引数をそのまま受け、標準出力に `none` / `read` / `write` / `admin` のどれか1語を出す。rc は常に 0

- [ ] Step 1: 失敗するテストを書く。分類の表を `@test "classify: <args> -> <class>"` の1行1件で並べる。最低限の行:
  - none: `--version`、`version`、`help`、`help pr`、`completion -s zsh`、`auth status`、`auth logout`、引数なし
  - read: `pr list`、`pr view 3`、`pr create --fill`、`pr comment 3 --body-file x`、`issue create`、`run view 1`、`run watch 1`、`co 3`(alias)、`api repos/a/b`、`api -X GET repos/a/b`、`api --method=HEAD repos/a/b`、`api graphql -f query='query { viewer { login } }'`、`release view v1`、`release list`、`repo view a/b`、`repo clone a/b`、`ruleset list`、`secret list`
  - write: `pr merge 3 --squash`、`release create v1`、`release upload v1 f`、`release delete-asset v1 f`、`repo sync`、`workflow run ci.yml`、`run rerun 1`、`run cancel 1`、`secret set X`、`variable delete X`、`cache delete 1`、`api -X POST repos/a/b/x`、`api -XPOST repos/a/b/x`、`api --method=patch repos/a/b`、`api repos/a/b/labels -f name=x`(-X なしで -f)、`api repos/a/b -Fx=1`、`api repos/a/b --input body.json`、`api graphql -f query='mutation { x }'`、`api graphql --input q.json`、`api graphql -F query=@q.graphql`(中身を読まないので書き込みとみなす)
  - admin: `repo create a/b --private`、`repo delete a/b --yes`、`repo edit --visibility public`、`repo rename x`、`repo archive`、`repo unarchive`、`repo fork a/b`、`repo deploy-key add k`、`repo autolink create p u`
- [ ] Step 2: `bats scripts/tests/gh-token-shim.bats -f classify` を走らせ、全件が FAIL することを確かめる(関数が未定義)
- [ ] Step 3: `ghts_classify` を実装する。サブコマンドは最初の非フラグの引数、動詞はその次の非フラグの引数。`api` だけは引数を走査し、`-X`/`--method` の値(連結形を含む)、フィールド系のフラグ(`-f` `-F` `--field` `--raw-field`、連結形を含む)、`--input` の有無、graphql の `query=` の値に `mutation` を含むかを見る。`-X GET`/`HEAD` が明示されていれば、フィールドがあっても read
- [ ] Step 4: テストが全件 PASS することを確かめる
- [ ] Step 5: 変異注入。(a) `-f` の判定を外す (b) 連結形の解釈を外す (c) admin の動詞を1つ write の一覧へ移す。それぞれ対応する行だけが赤くなることを、落ちたテストの名前で確かめる。変異前のコピーから戻し、ハッシュが一致することを確かめる
- [ ] Step 6: コミット

### Task 2: 持ち主の解決と設定の解釈

Files: `scripts/gh-token-shim/lib.sh`、`scripts/tests/gh-token-shim.bats`

Interfaces:
- Consumes: なし
- Produces:
  - `ghts_owner_from_args "$@"`: 標準出力に小文字の owner か空。仕様の表の順序 1 / 2 / 2' を見る
  - `ghts_owner_from_url <url>`: github.com の remote / Web の URL から小文字の owner、それ以外は空。対象は `git@github.com:O/R(.git)`、`ssh://git@github.com/O/R`、`https://github.com/O/R(.git|/...)`
  - `ghts_valid_owner <name>`: Global Constraints の正規表現に当たれば rc 0
  - `ghts_load_config <file>`: グローバル変数 `GHTS_VAULT` / `GHTS_DEFAULT_OWNER` / `GHTS_OWNERS`(空白区切りの小文字)を設定する。ファイルが無い、または `vault` か `default_owner` が欠けていれば rc 1。不正な owner の行があっても rc 1
  - `ghts_has_owner <owner>`: `GHTS_OWNERS` に含まれれば rc 0

- [ ] Step 1: 失敗するテストを書く
  - args: `pr view 3 -R Acme/Web` → `acme`、`--repo=acme/web` → `acme`、`-R github.com/acme/web` → `acme`、`-R https://github.com/acme/web` → `acme`、`api repos/Acme/web/rulesets` → `acme`、`api /repos/acme/web` → `acme`、`api orgs/acme/members` → `acme`、`api users/bob` → `bob`、`api user` → 空、`repo view acme/web` → `acme`、`pr merge https://github.com/acme/web/pull/3` → `acme`、`pr list` → 空、`search repos foo` → 空
  - url: 上の3形と `.git` の有無 → owner、`git@gitlab.com:acme/web.git` → 空、`https://github.example.com/acme/web` → 空
  - valid: `acme-1` は通る、`-acme`、`acme/x`、`a;b`、`../x`、40文字は通らない
  - config: 正常系(owner 2行、コメントと空行を含む)で3変数が期待どおり、`vault` 欠落で rc 1、`owner=a;b` で rc 1、ファイル不在で rc 1。`vault=$(touch pwned)` を書いた設定を読んでもファイル `pwned` が作られないこと(source していないことの pin)
- [ ] Step 2: FAIL を確かめる
- [ ] Step 3: 実装する
- [ ] Step 4: PASS を確かめる
- [ ] Step 5: 変異注入。(a) url の host の照合を外す (b) config を `.` で source する形に替える (c) owner の正規表現からアンカーを外す。それぞれ対応するテストが名前で赤くなることを確かめ、コピーから戻す
- [ ] Step 6: コミット

### Task 3: 入口の shim

Files: `scripts/gh-token-shim/gh`、`scripts/tests/gh-token-shim.bats`

Interfaces:
- Consumes: Task 1 と Task 2 の関数
- Produces: 実行ファイル `gh`。終了コード: 本物の gh の終了コード(exec)、shim が止めたときは 1、本物の gh が見つからなければ 127

処理の順序(この順序そのものを仕様として pin する):

1. `GH_TOKEN` か `GITHUB_TOKEN` が空でなければ、そのまま委譲する
2. 分類が `none` なら、そのまま委譲する
3. 設定を読む。失敗したら止める(`config.example` の場所を案内する)
4. 分類が `admin` なら止める(画面で操作するよう案内する)。トークンは読まない
5. 持ち主を決める: 引数 → `GH_REPO` → `git remote get-url origin` → `GHTS_DEFAULT_OWNER`。`GHTS_OWNERS` に無い持ち主は、read なら既定の持ち主へ置き換える。write なら止める
6. read: `security find-generic-password -s gh-token-shim -a <owner>:read -w`。失敗または空なら止め、`security add-generic-password -s gh-token-shim -a <owner>:read -w` を案内する
7. write: `op read -n op://<vault>/gh-write-<owner>/credential`。失敗または空なら止める。read のトークンでは続行しない
8. 自分のディレクトリを PATH から外し、本物の gh が自分自身でないことを `-ef` で確かめてから、`GH_TOKEN=<token>` を付けて exec する

- [ ] Step 1: 失敗するテストを書く。setup は apm-guard.bats の形に倣う(shim を symlink で置き、偽の `gh` / `security` / `op` を別のディレクトリに置く)。偽物は起動されたことと引数をファイルへ追記する。偽の gh は `GH_TOKEN` の値と引数を出す。偽の `security` は account に応じて `tok-read-<owner>` を返す。偽の `op` は参照に応じて `tok-write-<owner>` を返す。どちらも環境変数で失敗させられるようにする。テスト:
  - 既存の `GH_TOKEN` があれば、そのまま渡り、security と op の記録が空
  - `--version` は設定ファイルが無くても委譲され、security と op の記録が空
  - 設定が無いと `pr list` は rc 1 で止まり、偽の gh の記録が空
  - `pr list` を `origin` が acme のリポジトリで実行すると `tok-read-acme`
  - `-R bob/x` は cwd の origin より優先される
  - 設定に無い持ち主の `pr view -R stranger/x` は既定の持ち主の read トークン
  - 設定に無い持ち主の `pr merge 1 -R stranger/x` は rc 1 で止まり、op の記録が空
  - `pr merge 3` は `tok-write-acme` を渡し、security の記録が空
  - `repo create acme/x` は rc 1 で止まり、security と op の記録が空
  - op が失敗すると rc 1 で止まり、偽の gh の記録が空(read で続行しない)
  - security が失敗すると rc 1 で止まり、案内の文言に `security add-generic-password -s gh-token-shim -a acme:read -w` を含む
  - 引数は空白や引用符を含んでもそのまま本物へ渡る(`pr create --title "a b" --body "it's"`)
  - トークンの値が stderr に出ない(security / op の失敗時を含む)
  - shim の別名が PATH に残っていても、自分を再実行せずに止まる(apm-guard.bats と同じ守り)
- [ ] Step 2: FAIL を確かめる
- [ ] Step 3: 実装する
- [ ] Step 4: PASS を確かめる
- [ ] Step 5: 変異注入。(a) 手順 1 を外す (b) write の失敗時に read へ落とす (c) 手順 5 の「write で設定に無い持ち主なら止める」を外す (d) `-ef` の確認を外す。それぞれ狙ったテストが名前で赤くなることを確かめ、コピーから戻す
- [ ] Step 6: コミット

### Task 4: 配線

Files: `bootstrap.sh`、`home/.zshrc`、`.pre-commit-config.yaml`、`.github/workflows/test.yml`、`scripts/gh-token-shim/config.example`、`scripts/tests/test_helper.bash`、`scripts/tests/gh-token-shim.bats`

Interfaces:
- Consumes: Task 3 の `gh`
- Produces: 配置と PATH への差し込み

- [ ] Step 1: 失敗するテストを書く。apm-guard.bats の「取り付け」節と同じ4件(`SYMLINK_PAIRS` に `gh` と `lib.sh` がある、実体に実行権限がある、zshrc で `mise activate zsh` より後ろに PATH の行がある、PATH に入れる先と `SYMLINK_PAIRS` の配置先が一致する)。加えて、`config.example` を `ghts_load_config` に読ませると rc 0 になること
- [ ] Step 2: FAIL を確かめる
- [ ] Step 3: 配線を書く。shellcheck の対象は、pre-commit と CI の2か所に同じ形で足す
- [ ] Step 4: PASS を確かめる。`pre-commit run shellcheck --files scripts/gh-token-shim/gh scripts/gh-token-shim/lib.sh` で、gh が Skipped ではなく Passed になること(件数で確かめる)
- [ ] Step 5: 変異注入。`SYMLINK_PAIRS` の行を消す、zshrc の行を mise の前へ動かす。対応するテストが赤くなることを確かめる
- [ ] Step 6: コミット

### Task 5: 実物での通し確認と移行(コントローラが行う)

ユーザーの操作を含むので、subagent には渡さない。

- [ ] `bootstrap.sh` で配置する(live の作業ツリーがこのブランチを取り込んだあと)。新しいシェルで `command -v gh` が shim を指すこと
- [ ] ユーザーが持ち主ごとに2本ずつトークンを発行し、普段使いをキーチェーンに、強いトークンを 1Password に置き、設定ファイルを書く(権限は spec の「トークンの置き場所と権限」)
- [ ] 通し確認: 各持ち主のリポジトリで `gh pr list`、`gh api repos/<owner>/<repo>/rulesets`。昇格では、承認ダイアログが出ることを確かめてから拒否し、止まることを確かめる。承認して `gh api -X GET` 相当の無害な操作は昇格しないので、昇格を通す確認は、実際に merge が要る PR が出たときに行う
- [ ] gh を使う他の使い手を棚卸しする(launchd、Raycast、mise、apm の private の依存、`gh auth token` を読むもの)
- [ ] `gh auth logout` を打ち、GitHub の Authorized OAuth Apps から許可を取り消す
- [ ] 依頼元のセッションに構成検査を実物にかけてもらい、結果を受け取る
- [ ] 間接の書き込みの実測と、workflow の棚卸し(spec の移行の順序 6)。対話のターミナルでの承認の持続の計測(同 7)。結果を spec の「受け入れる残りのリスク」に書き足す
- [ ] メモリと Issue を実測に合わせて更新する
