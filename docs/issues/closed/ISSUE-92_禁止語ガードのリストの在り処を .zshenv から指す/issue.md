---
status: closed
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
- symlink あり + 実体が引けない → checker が rc=2 で loud に止まる
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

- [x] `home/.zshenv` を追加し、`-L` ガード付きで `LEAK_GUARD_DENYLIST` を export する
- [x] `bootstrap.sh` の `SYMLINK_PAIRS` へ `home/.zshenv|.zshenv` を足す
- [x] 配線を pin するテストを足す。3 状態の分岐・無出力・`SYMLINK_PAIRS` への登録の 3 面を見る
- [x] ISSUE-46 のマイルストーン表での扱いを決める (M4 へ入れたうえで、同じ PR でクローズする
      ため腐りになる。表は active のみを載せる規約なので外し、経緯を検算節へ残した)
- [x] 実マシンへ `~/.zshenv` を張り、変更後に起動したシェルから checker が status=skipped を
      返すことを確かめる (symlink を張る前の正しい結果は skipped。checked の確認は
      ユーザーがリストの symlink を張ったあと)

## 実測 (2026-09-12、配線後)

`~/.zshenv` を張った状態で full chain を 3 枝とも通した。値はコマンドの前に置いて注入せず、
ライブの `~/.zshenv` が中立パスの symlink を見て決めた値を使っている (注入する形では必ず
checked になり、見たい失敗を原理的に出せない)。

| 中立パスの状態 | checker の出力 | rc |
| --- | --- | --- |
| 生きた symlink | `status=checked tracked=143 scanned=143 entries=1 findings=0` | 0 |
| 壊れた symlink | `[x] LEAK_GUARD_DENYLIST の指す先を stat できない (errno=2)` | 2 |
| symlink なし | `status=skipped reason=env-unset` | 0 |

`unset` を「ガードが効いた」の根拠にする前に、ライブのファイルが実際に読まれていることを
`zsh -xc true` のトレースで確かめた (`/Users/<user>/.zshenv:22> [ -L ... ]` の行が出る)。
トレースに出ない場合の `unset` は「読まれていない」を意味するので、両者は区別が要る。

変異注入は 16 件で、最終的に全件 kill された。検体は隔離コピーへ作り、`ZSHENV_FILE` の
上書きで対象を差し替えるので、リポジトリ本体は一度も壊していない。

うち 2 件が設計上の穴を出した。

**`export` を落として代入だけにする変異は、当初 9 テスト全件が緑のまま生存した。**
観測を `.zshenv` を読んだシェル自身から行っていたためで、そのシェルからは export されて
いない変数も同じ値に見える。実際の消費者は pre-commit hook が起動する別プロセスなので、
export が無ければ届かない。この Issue が塞ごうとしている当のもの (変数が届かないまま
緑になる) を、テストが再現していた。観測に子プロセスを 1 枚挟んで kill した。

**pair を削って reverse drift の allowlist へ逃がす変異**は `bootstrap.bats` 側を緑に
戻すが、`zshenv.bats` の個別 pin だけが赤くなる。個別 pin を別に持つ理由がこれにあたる。

「壊れた symlink のときだけ警告する」という将来ありうる改変も検体に入れた。無出力の 3 行目
(broken symlink) を削ってよいかの判断に使い、削らないことにした。この変異は値のテストでも
赤くなるが、そちらは `run` が stderr を stdout へ混ぜている副作用による偶然の検出で、
`--separate-stderr` へ変えた瞬間に消える。無出力の 3 行目だけが直接の検出になっている。

## 射程 (塞げていない起動元)

この配線が覆うのは zsh が起動する経路だけで、全経路ではない。checker の docstring が
「届かない起動元は実在する」として記録している 2 つのうち、`.zshenv` が塞ぐのは片方だけ。

| 起動元 | .zshrc に置いた場合 | .zshenv に置いた場合 |
| --- | --- | --- |
| 対話シェル | 届く | 届く |
| 非対話 zsh (`zsh -c`)、その子プロセス | 届かない | 届く |
| GUI の git クライアント / IDE の VCS 機能 | 届かない | 届かない |

3 行目が残る穴。GUI アプリが継承するのは launchd の環境で、zsh の設定ファイルを一度も
読まない。2026-09-12 の実測で `launchctl getenv LEAK_GUARD_DENYLIST` は空を返す。
このリポジトリには `.idea/vcs.xml` があるので、JetBrains の VCS UI からコミットした場合は
現在も静かに skip される。

塞ぐなら `launchctl setenv` を打つ層が要るが、それは値を launchd の環境へ置くことなので、
中立パスを指すだけとはいえ配線の置き場と再起動時の再実行を別に決める必要がある。本 Issue の
射程外とし、必要になったら別 Issue で扱う。

## 採らなかった案と、残る論点

### この層ごと不要にする案 (向こうのリポジトリの判断)

checker が中立パスを既定値として自分で持てば、この配線は丸ごと要らなくなる。
環境変数が設定されていればそれを使い、未設定なら中立パスを lstat して symlink なら採用し、
それも無ければ skip する。現在の 3 分岐がそのまま再現され、シェルは介在しない。

成立するのは、checker の docstring が「リストの置き場所をここへ書かない」と決めている対象が
リストの実体のパスであって、中立パスではないため。中立パスは固有名詞を含まないので、この
PUBLIC リポジトリへ書けている以上あちらへも書ける。

そちらが優れている点は射程で、上の表の 3 行目 (GUI / IDE) も同時に埋まる。シェルの起動形態に
一切依存しなくなるため。dotfiles 側は `home/.zshenv` と `zshenv.bats` と `SYMLINK_PAIRS` の
1 行が不要になる。

**2026-09-12 に採らないことが決まった。** 判断は checker の持ち主である
agentic-coding-tools 側で、理由は 2 つ。

1. あちらの canonical な分岐表は入力が環境変数 1 つという前提で組まれていて、緑のまま何も
   見ていない形を 30 通り数えた末のものなので、入力を増やすと数え直しが要る
2. `.zshenv` と既定値は同じことを 2 箇所で実現するので、canonical を 1 つ決める原則に反する

結果として `.zshenv` が単一の機構として残る。上の表の 3 行目 (GUI / IDE) は**閉じないまま
残すという選択**であり、見落としではない。閉じるかどうかは「それらが本当にこの hook を
走らせるか」を実測してから別件で判断する。採らなかった案とその理由は agentic-coding-tools の
ISSUE-15 にも残る (自然に再提案される種類の案であるため)。

### 中立パスの名前空間

このリポジトリには「追跡下へ書けない値を中立な固定パスへ置き、無ければ黙って無効」という
同型の機構が既に 3 つある (`$HOME/.config/dotfiles/claude-config-dirs`、`~/.gitconfig.private`、
`<repo>/.hidari/private-ops`)。今回の `$HOME/.config/leak-guard/` は 4 つ目で、特に 1 つ目とは
「追跡下へ書けない固有名詞のリスト」という点まで同型である。

それでも `$HOME/.config/dotfiles/` へ寄せないのは、あちらが dotfiles 自身の設定を置く
名前空間で `bootstrap.sh` が読む側だからである。禁止語リストを消費するのは別リポジトリの
ツールなので、dotfiles の名前空間へ置くと所有者を偽ることになる。寄せる判断もありうるので、
理由をここに残す。

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
`scripts/check-leak-guard-denylist.py` の docstring。checker に中立パスの既定値を持たせて
この配線ごと不要にする案を採らなかった記録も、本 Issue の「採らなかった案」節と対で
あちらに残る
