---
status: open
---

# feat: 禁止語ガードのリストの在り処を .zshenv から指す

## 背景

agentic-coding-tools 側に禁止語リスト検査 (同リポジトリの ISSUE-15 の層 2) が入った。リストの
置き場は環境変数 `LEAK_GUARD_DENYLIST` で外から指す設計で、リスト自体は PUBLIC リポジトリへ
置けないため追跡外にある。検査の canonical は同リポジトリの
`scripts/check-leak-guard-denylist.py` の docstring。

その環境変数がどのマシンにも設定されていない。委譲元の実測は次のとおりで、rc=0 なので
コミットは通り、層 2 は緑のまま何も見ない。

    status=skipped reason=env-unset
    禁止語ガードを skip した (LEAK_GUARD_DENYLIST が未設定)
    rc=0

この Issue は dotfiles 側の配線だけを持つ。検査の実装と挙動は向こうの持ち場で、こちらが決める
のは「どこに export を置くか」と「いつ export するか」の 2 点にとどまる。

## 決定 (委譲元で確定済み、実測はこちらで再現)

### 置き場は .zshenv

`.zshrc` ではなく `.zshenv` に置く。`.zshrc` の export は非対話 zsh へ届かないため。
2026-09-12 に偽の HOME を使って再現した (`ZDOTDIR` は環境から落とす。残っていると HOME より
優先される)。

| 起動形態 | .zshenv の export | .zshrc の export |
| --- | --- | --- |
| `zsh -c` (非対話・非ログイン) | 届く | 届かない |
| `zsh -i -c` (対話) | 届く | 届く |
| `zsh -c` が起動した子プロセス (pre-commit hook 相当) | 届く | 届かない |

### 値は中立な固定パス

`$HOME/.config/leak-guard/denylist.gitignore` を指す。そこをリスト実体への symlink にすることで、
dotfiles (PUBLIC) 側に実体のパスを書かずに済む。checker は stat() で symlink を辿るため
symlink で問題ない (委譲元の実測: 生きた symlink で status=checked / rc=0)。

### ガードは -L で symlink の存在を見る

2026-09-12 に 3 状態を再現した。

| 状態 | `-L` | `-r` | `-e` |
| --- | --- | --- | --- |
| 壊れた symlink | true | false | false |
| 生きた symlink | true | true | true |
| 何も無い | false | false | false |

`-L` だけが「symlink を意図して張ったマシン」と「何も無いマシン」を分ける。結果として:

- symlink あり + 実体が引ける → checker が rc=0 で checked
- symlink あり + 実体が引けない (同期待ち等) → checker が rc=2 で loud に止まる
- symlink なし (fresh clone / 第三者) → export されず rc=0 で skip

`-r` や `-e` にすると壊れた symlink が不在と同じ扱いになり、loud な失敗が silent skip に化ける。
無条件 export にすると、リストを持たないマシンと第三者の clone で全コミットが rc=2 で止まり、
未設定を skip にした docstring の判断を壊す。

## 制約

- リスト実体のパスを追跡下のどのファイルにも書かない。`.zshenv` にも `bootstrap.sh` にも
  ドキュメントにも書かない。探索も推測もしない。必要なのは中立な側の固定パスだけで、
  symlink の張り先はユーザーが手元で決める
- `bootstrap.sh` に `$HOME/.config/leak-guard/` の symlink を作る処理を足さない。足すと `-L`
  ガードが全マシンで true になり、リストを持たないマシンで rc=2 になる。このガードが意図の
  宣言として働くのは、その symlink を人が明示的に張ったときだけ
- `.zshenv` の中で一切出力しない (echo / printf / ログ)。`.zshenv` は scp / sftp / rsync over
  ssh の非対話セッションでも読まれるため、出力するとプロトコルが壊れる

## タスク

- [ ] `home/.zshenv` を追加し、`-L` ガード付きで `LEAK_GUARD_DENYLIST` を export する
- [ ] `bootstrap.sh` の `SYMLINK_PAIRS` へ `home/.zshenv|.zshenv` を足す
- [ ] 配線を pin するテストを足す。3 状態の分岐・無出力・`SYMLINK_PAIRS` への登録の 3 面を見る
- [ ] ISSUE-46 のマイルストーン表 (M4) へ ISSUE-92 を入れる
- [ ] 実マシンへ `~/.zshenv` を張り、変更後に起動したシェルから checker が status=skipped を
      返すことを確かめる (symlink を張る前の正しい結果は skipped。checked の確認は
      ユーザーがリストの symlink を張ったあと)

## 関連

Issue 29: PUBLIC リポジトリに残る private リポジトリ名の露出を棚卸しする Issue。
そちらは「private リポジトリ名の denylist は PUBLIC リポジトリでは自己矛盾するので、名前を
列挙して弾く方向は採れない」と記録し、代わりに allowlist 方式の候補を 2 つ挙げている。
本 Issue が配線する層 2 は、リストを追跡外へ置いて環境変数で指すことで列挙方式を成立させる
第 3 の候補にあたる。**変わったのは着手順序ではなく内容**で、あちらの「採れない」は
「追跡下へ列挙する形は採れない」と読み替わる。あちらの検査手段の選定は本 Issue では閉じない

ISSUE-69: apm ガードの到達が起動元シェルの鮮度に依存する Issue。そちらは「`.zshenv` へ PATH 行を
移す案は成立しない」と結論しているが、**射程は PATH に限る**。Claude Code のシェルスナップ
ショットは最終行で PATH だけを起動元シェルの値へ上書きするためで、PATH 以外の export は
`.zshrc` 由来のものが現に届いている (2026-09-12 に `LANG` / `GOPATH` / `HOMEBREW_NO_ENV_HINTS` /
`LSCOLORS` で確認)。本 Issue が置くのは PATH ではないので、あちらの結論とは衝突しない

Issue 44: `.zshrc` が非対話シェルへ運ぶ設定をエイリアス以外にも絞る Issue。本 Issue は非対話へ
意図して運ぶ側を増やすので、あちらが絞る対象を決めるときに突き合わせが要る

agentic-coding-tools の ISSUE-15: 検査本体の持ち場。層 2 の canonical は同リポジトリの
`scripts/check-leak-guard-denylist.py` の docstring
