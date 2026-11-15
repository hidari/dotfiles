# Bash コマンドの沈黙経路の続き

`~/.claude/references/observation.md` の「Bash コマンドの沈黙経路」節の続き。容量の都合で分けた。

あちらと同じく、コマンドを組む前に開く。

## 文字列の中のコマンド置換が `$?` を上書きする

終了コードを、同じ文字列の中のコマンド置換と並べて書くときに踏む。

zsh で `echo "$(basename $f) rc=$?"` と書くと、文字列の中の `$(...)` が先に走って `$?` を上書きし、直前のコマンドの終了コードが常に0に見えた。検査が全件緑に見え、まとめて回すと赤という矛盾で気づいた。`rc=$?` をコマンドの直後で変数に取ってから echo する (実測)。

`zsh -f -c 'f=/a/b; false; echo "$(basename $f) rc=$?"'` は `b rc=0` を出し、`bash -c` で同じ文字列を回しても `b rc=0` だった (2026-11-15に zsh 5.9 で再現した。bash の版は未記録)。

後ろのコマンドが `$?` を上書きする同じ型は `~/.claude/references/observation.md` の「成否が隠れる」節が持つ。

## `grep -c` は出現数ではなく行数を数える

`grep -c` で出現数を数えるときに踏む。minify されたファイルや1行の表・カタログで差が消える。

minify されたファイルや1行のカタログに `grep -c` を使うと、新旧とも1になって差が見えなかった。出現数は `grep -oF ... | wc -l` で数えた (実測)。

## git の出力の日本語パスはクォートされる

日本語のパスを含む git の出力 (`--name-only`・`ls-tree`・`--stat`・diff のヘッダ・`ls-files`) を、grep や Read や別の git コマンドへ渡すときに踏む。受け方の canonical は `~/.claude/references/observation.md` の「パースが静かに欠ける」節 (NUL 区切りで受ける) で、ここはクォートの出方と、設定でクォートを外す形を足す。

- 機序: git の `--name-only`、`ls-tree --name-only`、`--stat`、diff のヘッダは、既定 (core.quotepath=true) で ASCII 以外を含むパスを8進のエスケープで出す。`ls-files` も日本語のファイル名を引用符と8進数で出す (どちらも実測)
- 症状: 出力を grep や Read に渡すと、エラーにならずに0件になったり開けなかったりした。`ls-tree --name-only` から取ったパスを `git show` に渡すと、クォート付きのまま does not exist になった。ls-files の一覧と subagent が返したパスを突き合わせると、読んだはずのファイルが未読に数えられた (どれも実測)
- 手当て: `git -c core.quotepath=off ...` か `-z` で取る (実測)。監査で読み漏れを数えるときも、一覧をこの形で作る

## `--watch` の出力をファイルで読むと順序を誤読する

`gh pr checks --watch` の出力をファイルに書いて tail で読むときに踏む。

`gh pr checks --watch` の出力をファイルへ書いて tail で読むと、書き直しのたびの一覧が縦につながる。そのため「test が pending なのに集約のジョブが pass」に見える行の並びができ、集約のジョブが待たずに緑になったと誤読しかけた。順序は actions の jobs API の started_at / completed_at で確かめる (実測。報告日は未記録、gh の版は未記録)。

結論そのものの確かめ方は `~/.claude/references/observation.md` の「成否が隠れる」節が持つ。
