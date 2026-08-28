# ISSUE-55 実装プラン: 判定点を exec 時へ移す

方式は ISSUE-55 の issue.md「方式」節が canonical。ここでは実装の分割と各タスクの要件を持つ。

## Global Constraints

- コード内のコメントは日本語。ログはシステム内部が日本語、外部に見えるものが英語
- 同じ制約を 2 箇所に literal で書かない。二重にせざるを得ない箇所は cross-pin テストで
  一致を検査する
- フックのパース (`tokenize` / `is_operator` / `is_command_position`) は拡張しない。
  方式の決定として、判定の網は shim が持ち、フックは shim が迂回される 2 形と
  shim の配置検出だけを担う
- 単独 CR を区切りとして扱わない。実シェル 5 種で apm は exec されないため、
  区切りとして pin すると実体と違う模型をテストへ焼き付ける
- 新しい検査を足したら変異注入 3 種を当てる (検査対象を壊す / 検査機構を壊す / 取り付けを外す)
- テストは仕様として読める形にする。docstring は「そこが外れたときどう静かに壊れるか」を書く
- 既存テストの慣習に合わせる。`scripts/tests/*.bats` は bats、
  `scripts/claude-hooks/tests/*.py` は subprocess 黒箱で pytest、モックは使わない

## Task 1: 判定ロジックの共有層と shim 本体

### 目的

`apm install` の可否判定は現在 `bootstrap.sh` (bash) と `apm-install-guard.py` (Python) に
二重実装されている。shim を足すと三重になるので、シェル側を 1 つのファイルへ寄せる。

### 新規: `scripts/apm-guard/lib.sh`

`bootstrap.sh` から次の 2 関数をそのまま移す。コメントも一緒に移し、`bootstrap.sh` 側には
残さない (コピーではなく移動)。

- `apm_io_path()` — パスが apm install の入出力 (`apm.yml` / `apm.lock.yaml`) なら真
- `apm_install_blockers()` — 未コミット変更のうち apm 入出力でないものを 1 行 1 件で stdout へ。
  検査できなかったときは 1 を返す

加えて 1 関数を新設する。

- `apm_is_readonly_invocation()` — 引数列 (`"$@"` 相当) を受け取り、読み取り専用の
  サブコマンド呼び出しなら真。判定は `apm-install-guard.py` の `READONLY_COMMANDS` と
  同じ集合で行い、フラグ (`-` で始まる語) は読み飛ばす。サブコマンドを伴わない呼び出し
  (`apm` 単独 / `apm --version`) も真 (help を出すだけなので対象外)

`lib.sh` は source されるだけで副作用を持たないこと。実行フラグは付けない。

### 変更: `bootstrap.sh`

関数定義を消し、同じ位置で `lib.sh` を source する。`bootstrap.sh` は
リポジトリルートにあるので、自身の位置から相対で解決すること。
`install_apm_packages()` の呼び出し側は変えない。

### 新規: `scripts/apm-guard/apm`

PATH の先頭に置かれる shim。実行フラグを付ける。POSIX sh で書く (`#!/bin/sh`)。

処理:

1. `APM_INSTALL_GUARD_DISABLE=1` なら何もせず実物へ委譲する
   (環境変数名はフックと同じものを使う。canonical を 1 つに保つため)
2. 自分のディレクトリを `$0` から求め、同じディレクトリの `lib.sh` を source する
3. `apm_is_readonly_invocation "$@"` が真なら実物へ委譲する
4. `apm_install_blockers "$PWD"` を呼ぶ。失敗 (exit 1) なら「検査できなかった」として
   拒否する。空でない出力があれば拒否する
5. 拒否のメッセージは stderr へ。フックの `format_reason` と同じ趣旨の内容にする
   (何が起きるか / どのリポジトリに何件あるか / どうすれば進めるか / 無効化の方法)。
   一覧は先頭 20 件までとし、残りは件数で示す
6. 通す場合は PATH から自分のディレクトリを取り除いてから `exec apm "$@"` する

注意点:

- PATH の除去に `sed` を使わない。パスに正規表現のメタ文字が入ると壊れる。
  `IFS=:` でループして一致するエントリを飛ばす形にする
- `$0` がパスを含まない形で起動される可能性を確認し、その場合の挙動を決めること。
  実際にどうなるかを測ってから決めること (推測で分岐を足さない)
- 無限再帰を防ぐこと。PATH の除去が効かないと shim が自分を再実行し続ける。
  除去後に解決される `apm` が自分自身でないことを確かめる手立てを持たせる

### テスト: `scripts/tests/apm-guard.bats` (新規)

`scripts/tests/test_helper.bash` の慣習に従い、検査対象のパスを環境変数で上書き可能にする
(変異注入で実ファイルを壊さずコピーへ当てられるようにするため)。

pin する仕様:

- `apm_is_readonly_invocation`: readonly な全サブコマンド (`apm-install-guard.py` の
  `READONLY_COMMANDS` と同じ集合) で真、`install` で偽、フラグ付き、サブコマンド無し
- shim が clean なツリーで実物へ委譲すること (実物は fake を PATH に置いて確認する)
- shim が dirty なツリーで非 0 終了し、実物を起動しないこと
- shim が readonly サブコマンドは dirty でも通すこと
- shim が `APM_INSTALL_GUARD_DISABLE=1` で素通りすること
- shim が自分を無限再帰しないこと
- 既存の `bootstrap.bats` の `apm_install_blockers` 7 件が緑のままであること

### 完了条件

`bats scripts/tests/` が緑。移動した関数の既存テストが 1 件も落ちないこと。

## Task 2: 配布と PATH への差し込み

### 変更: `bootstrap.sh` の `SYMLINK_PAIRS`

2 行足す。

```
"scripts/apm-guard/apm|.local/libexec/apm-guard/apm"
"scripts/apm-guard/lib.sh|.local/libexec/apm-guard/lib.sh"
```

target がネストしたディレクトリなので、親ディレクトリが無い場合に作られるかを確認すること。
既存の pair (`.config/git/.gitignore_global` など) が同じ深さを持つので、そこを見れば分かる。

### 変更: `home/.zshrc`

`eval "$(mise activate zsh)"` の直後に PATH の prepend を足す。

```sh
export PATH="$HOME/.local/libexec/apm-guard:$PATH"
```

`path` 配列の側へ足してはならない。`mise activate` が後で PATH を再構成するため、
配列へ足すと実物より後ろへ落ちる (実測で 31 番目)。なぜこの位置なのかをコメントに残すこと。

### テスト

- `scripts/tests/bootstrap.bats`: `SYMLINK_PAIRS` に 2 本が含まれること。
  既存の pair 検査の形に合わせる
- `.zshrc` の PATH 行が `mise activate` より後にあること。行の順序が仕様なので pin する
  (既存の zshrc テストの置き場と形式に合わせる)

### 完了条件

`bats scripts/tests/` が緑。`--dry-run` の bootstrap が新しい pair を出力に含むこと。

## Task 3: フックの役割変更と docstring の訂正

### 変更: `home/.claude/hooks/apm-install-guard.py`

パース関連 (`tokenize` / `is_operator` / `is_command_position` / `_PUNCTUATION_CHARS`) は
一切変更しない。

足すもの:

- shim の解決可能性の検査。`apm` を PATH から解決し、解決先が配布した shim でなければ
  「shim が配置されていない」ことを理由に deny する。判定は `guarded_command` が
  非 None を返した後、dirty 判定の前に置く
- shim のパスは `~/.local/libexec/apm-guard/apm` を HOME 相対で組み立てる。
  `SYMLINK_PAIRS` の target と同じ値になるので、一致を検査するテストを置く

直すもの:

- モジュール docstring の cross-pin テストの所在。現在 `scripts/tests/bootstrap.bats` の
  cross-pin テストが両層の一致を見ると書いてあるが、bats に両層の一致を見るテストは無い。
  実体は `scripts/claude-hooks/tests/test_apm_install_guard.py`
- モジュール docstring に射程を書く。この層が見るのはトップレベルのトークンとして
  現れる形までで、包み込みと変数展開の網は shim が持つこと。
  ISSUE-55 の issue.md にある「両層をすり抜ける形」は受容であることも書く
- モジュール docstring の「複数の PreToolUse フックが deny と allow を同時に返したときの
  合成規則は公式ドキュメントに記載が無い」という記述。公式ドキュメントの hooks の
  リファレンスに precedence (`deny` > `defer` > `ask` > `allow`) の記載がある。
  記述を実態に合わせること。allow を出さない設計自体は変えない

### テスト: `scripts/claude-hooks/tests/test_apm_install_guard.py`

- shim が解決できないときに deny すること。理由文に shim の配置方法が含まれること
- shim が解決できるときは従来どおり dirty 判定へ進むこと
- shim のパスが `bootstrap.sh` の `SYMLINK_PAIRS` の target と一致すること (cross-pin)
- 既存 33 件が緑のままであること

### 完了条件

`uv run --directory scripts/claude-hooks pytest -q` が緑。`bats scripts/tests/` が緑。

## Task 4: 変異注入

Task 1 から 3 で足した検査それぞれに 3 種の変異を 1 件ずつ隔離して当て、期待した
テストが赤くなることを確かめる。復元は `git checkout --` を使わず、`cp` で
`.cache/` へ退避してから戻す。新規ファイルは `git add` して追跡下へ入れてから変異させる
(untracked のままだと pre-commit の `files:` と bats の `git ls-files` が Skipped にする)。

当てる変異:

- 検査対象を壊す: dirty なツリーを clean と誤認させる、readonly allowlist に `install` を足す
- 検査機構を壊す: shim の拒否を素通りへ変える、フックの shim 検査を常に真にする
- 取り付けを外す: `SYMLINK_PAIRS` から shim を落とす、`.zshrc` の PATH 行を消す、
  `bootstrap.sh` の `lib.sh` source を消す

結果を件数と kill/survive で issue.md へ記録する。survive したものは理由を書く。
