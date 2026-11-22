# git と gitleaks の一次実測

`~/.claude/references/tools.md` が名指しする、git のコマンドと gitleaks の事実と手当て。

規範の遵守そのものには要らない。git の検索や一覧の結果を件数として読むとき、hook や gitleaks を取り付けたとき、道具の挙動が想定と食い違ったときに読む。版に依存する節には道具の版を添え、記録の無いものは「版は未記録」「報告日は未記録」と書く。

コミットと push と squash の後の確かめ方は `~/.claude/references/git-workflow.md` が、git の出力の日本語パスのクォートは `~/.claude/references/observation-shell.md` の「git の出力の日本語パスはクォートされる」節が持つ。ここには書き直さない。

## `git grep` は未追跡のファイルを見ない

`git grep` で古い値の残りを数えるときに踏む。

`git grep` は未追跡のファイルを見ないので、まだ add していない新しいファイルに残った古い値が0件に化けた。古い値の残りを数える手順では、`git ls-files --others --exclude-standard` の対象にも同じ検索を当てる (実測)。

## `git grep -E` は単語境界と空白の略記を解さない

`git grep -E` で `\b` や `\s` を含む正規表現を書くときに踏む。報告日は未記録、踏んだ側の git の版は未記録 (下の再現は git 2.56.0)。

- `git grep -E` は POSIX ERE なので `\b` を単語境界として解さず、該当があるのに警告なしで0件を返した (同じ照合が `-P` では18件) (実測)
- `\s` を使うと、エラーも警告も出さずに0件を返した (POSIX ERE は `\s` を持たない)。`[[:space:]]` に直すと同じ対象で21件出た (実測)
- Markdown のファイル群に `\bstatus\b` を当てると、`-E` は0ファイル、`-P` と境界なしの素の照合はどちらも153ファイルだった (2026-11-02に git 2.56.0 で再現した)
- 手当て: 単語境界が要る照合は `-P` を使い、正常なら非空になる対照 (総数など) を並べる (実測)
- `\s` `\d` `\w` は黙って解釈されないものとして、POSIX の文字クラスか `-P` で書く (提案。実測の記録があるのは `\b` と `\s`)

## `git ls-tree` の pathspec

`git ls-tree` に pathspec を渡して範囲を絞るとき、同じ範囲の文字列を複数の git のコマンドへ共通で渡すときに踏む。報告日は未記録、git の版は未記録。

`git ls-tree -r` の pathspec は、ファイル名の接頭辞にもグロブにも当たらず0件を返し、グロブに当たったのは `git ls-files` だけだった。同じ範囲の文字列を ls-tree・ls-files・status に共通で渡すと、ls-tree の側だけ空振りする。ディレクトリを列挙してから言語の側で述語で絞る (実測。サブエージェントが手元で確かめた)。

ls-tree の出力の非 ASCII のパスがクォートされる件は別の知見で、冒頭に挙げた `observation-shell.md` の節が持つ。

## 実行の権限が無い hook は飛ばされる

git hook を取り付けたとき、hook を配るレシピを書くときに踏む。

実行の権限が無い git hook は、git が hint を1行出すだけで飛ばし、コミットは検査なしで通る。`git hook run pre-commit` で起動すると気づける。取り付けのレシピで `-x` を確かめ、index のモード100755も検査するとよい (実測)。

hook が走らない別の経路 (cherry-pick、タグだけの push) は `~/.claude/references/git-workflow.md` の「hook が走らない経路」節が持つ。

## gitleaks の `--staged` の射程

コミットの後に gitleaks で確かめるとき、pre-commit の gitleaks が何を見ているかを読むときに踏む。報告日は未記録、gitleaks の版は未記録。

- コミットの後: pre-commit と同じ `--staged` をコミットの後に打つと、約0バイトを走査して緑になった。コミットの後に回すなら `gitleaks git --log-opts="main..HEAD"` にして scanned commits を出させる (実測)
- コミット済みの値: gitleaks の pre-commit (`gitleaks git --staged`) は stage した差分しか見ないので、前からコミット済みの秘密に見える値は、その行のキー名を直しただけで初めて止まる。直すときは検査を免除するより、そのファイルを追跡から外して雛形から作る形を先に考える (実測)

gitleaks の緑を安全の根拠にしない判定は `~/.claude/CLAUDE.md` の観測のカテゴリが持つ。発火の条件が stage や追跡の状態に依存する検査の例は `~/.claude/references/testing.md` の「発火条件が tracked に依存する検査」節にある。
