# 道具ごとの参照の索引

`~/.claude/CLAUDE.md` が名指しする、道具の事実と手当てを持つ参照ファイル (`~/.claude/references/tool-<道具>.md`) の索引。

規範の遵守そのものには要らない。下の場面に入るとき、道具の結果 (0件、拒否、緑、終わらない待ち) が想定と食い違ったときに、該当するファイルの節を開く。各ファイルは版に依存する事実を含むので、節に添えた版と報告日を見てから使う。

## シェルとコマンドラインの道具

`~/.claude/references/tool-shell.md` が持つ。

- zsh で `=` から始まる語 (区切りの `echo ====` など) を引数に書くとき: 「zsh の `=` で始まる語」節
- zsh でクォートしないグロブ (`grep -r --include=*.ts`、grep の対象のファイル引数、git のコマンドのパスの引数) を書くとき: 「zsh のクォートしないグロブ」節
- zsh のスクリプトやループで `path` などの小文字の変数名を使うとき: 「zsh の小文字の `path`」節
- bash の `set -e` のスクリプトで、引数の中にコマンド置換を書くとき: 「bash の `set -e` は引数の中のコマンド置換を見ない」節
- macOS で bash のスクリプトを書くとき、とくに配列を作ってその配列を引数にコマンドを呼ぶとき: 「macOS の bash は3.2」節
- `&&` で連結するシェル片 (Makefile の変数に入れた片など) の中に `A || B` を書くとき: 「`&&` の連結の中の `A || B`」節
- background に待ちのループを置くとき、ポーリングのループの終了条件を書くとき: 「background の待ちのループ」節
- 子プロセスの終了を `kill(pid, 0)` で待つとき、プロセスグループをまとめて止めて消えるのを待つとき: 「`kill(pid, 0)` は zombie に成功を返す」節
- `make -n` で副作用の無い確認 (dry-run) をしようとするとき、`make -n` の出力で配線を pin するとき: 「`make -n` は `$(MAKE)` を含む行を実行する」節
- perl のワンライナーで日本語を含むパターンを照合・置換するとき: 「perl のワンライナーの日本語のパターン」節
- perl の `s` で、区切りと同じ文字を含むパターンや置換の文字列を書くとき、コードを差し込む置換を書くとき: 「perl の `s` の区切りと同じ文字」節

## git と gitleaks

`~/.claude/references/tool-git.md` が持つ。

- `git grep` で古い値の残りを数えるとき: 「`git grep` は未追跡のファイルを見ない」節
- `git grep -E` で `\b` や `\s` を含む正規表現を書くとき: 「`git grep -E` は単語境界と空白の略記を解さない」節
- `git ls-tree` に pathspec を渡して範囲を絞るとき、同じ範囲の文字列を複数の git のコマンドへ共通で渡すとき: 「`git ls-tree` の pathspec」節
- git hook を取り付けたとき、hook を配るレシピを書くとき: 「実行の権限が無い hook は飛ばされる」節
- コミットの後に gitleaks で確かめるとき、pre-commit の gitleaks が何を見ているかを読むとき: 「gitleaks の `--staged` の射程」節

## gh と GitHub の API

`~/.claude/references/tool-gh.md` が持つ。

- gh や jobs API で run や job の状態を読んで、完了や失敗を判断するとき: 「run と job の状態は直後の1回で決めない」節
- `gh run rerun --failed` の後に、job のログや結果を読むとき: 「`gh run rerun --failed` の後の job id」節
- `gh api` でジョブのログを取り出して grep するとき: 「ジョブのログの取得」節
- `gh pr create` や push、merge が GraphQL のエラーなどで失敗し、再実行しようとするとき: 「書き込みが失敗したときの再試行」節
- private のリポジトリで GitHub Pages を有効にするとき、Org やリポジトリを棚卸しするとき: 「Pages の公開範囲」節
- GitHub のリポジトリを REST の transfer API で organization へ移すとき: 「リポジトリの移管」節
- 公開されたサプライチェーン攻撃や CI 乗っ取りの記事の IOC を、自分のリポジトリやアカウントや Org へ照合するとき、revert と run の削除で痕跡を消す攻撃の跡を探すとき: 「公開された攻撃の IOC を照合する」節

## just

`~/.claude/references/tool-just.md` が持つ。

- justfile で `*args` を `{{args}}` で展開して、引数を recipe の中のコマンドへ素通しするとき: 「引数の素通しは `{{args}}` で展開しない」節
- justfile の recipe の依存や本文を、テストや検査で読むとき: 「justfile の構造を読む」節
- just のゲートの集約から検査の手順が落ちていないか、ガードや recipe の取り付け忘れが無いかを検査するとき: 「dump から取り付けの検査を導く」節
- just の recipe と GitHub Actions の workflow が同じコマンドを同じ順に走らせていることを、テストで突き合わせるとき: 「recipe と CI の workflow を突き合わせる」節
- Homebrew の just がリポジトリの canonical の版とずれ、版を照合する検査が入口で止まったとき: 「Homebrew の just が canonical の版とずれたとき」節

## Claude Code の harness

`~/.claude/references/tool-claude-code.md` が持つ。

- dev サーバなどの背景のプロセスを Bash で起動・停止・kill するとき、GUI のスパイクを起動するとき: 「背景のプロセスを起動して止める」節
- auto mode でリリース・本番のデプロイ・シークレットの書き込み・force push・CLI の拡張の導入・Claude Code の設定の編集を打つとき、それらを含む手順や skill を書くとき: 「auto mode の分類器が止める操作」節
- /goal に渡す DoD や「止まってよい条件」を書くとき、無人の実行に渡す spec を点検するとき: 「/goal に渡す DoD」節
- Workflow の結果ファイルや subagent の戻り値を JSON として parse するとき、subagent に JSON の結果を返させる指示を書くとき: 「Workflow と subagent の戻り値を JSON で読む」節
- Edit・Write・Bash のツールで、バックスラッシュと u と4桁の16進で書くエスケープを含むソースを書くとき、そのエスケープが残っているかを grep で確かめるとき: 「ツールが `\u` のエスケープを解いて書く」節
- プロジェクトの `.mcp.json` のサーバが `/mcp` や ToolSearch に出てこないとき、`.mcp.json` や settings.local.json のテンプレートを配るとき: 「プロジェクトの MCP サーバが一覧に出ない」節

## ブラウザの MCP

`~/.claude/references/testing-e2e-tools.md` が持つ。

- ブラウザの MCP の wait_for で cross-origin の iframe や大きな画面を待つとき: 「ブラウザの MCP の wait_for」節
- playwright-test の MCP の `browser_run_code_unsafe` でファイルのパスを書くとき: 「playwright-test の MCP の相対パス」節
