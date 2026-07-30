---
status: open
---

# refactor: superpowers の成果物を Issue ディレクトリ配下へ寄せる

## 背景

作業の記録が 3 系統に分かれていて、互いに参照が無い。

| 置き場 | 中身 | 追跡 | 件数 (2026-07-31 時点) |
| --- | --- | --- | --- |
| `docs/issues/<NNN>_<title>/` | Issue 本体 | あり | 16 |
| `docs/superpowers/plans/` | writing-plans が書く実装計画 | あり | 6 |
| `docs/superpowers/specs/` | brainstorming が書く設計 | あり | 6 |
| `.superpowers/sdd/` | subagent-driven-development の ledger / brief / report / review | なし | 94 |

Issue から plans と specs への参照は 1 件も無い。逆に plans と specs のファイル名は日付と feature 名だけで、どの Issue に属するかを名前から辿れない。

さらに、両者のテーマがほとんど重なっていない。plans と specs が扱う 6 テーマは、既存の Issue のタイトルとおおむね対応が付かない。superpowers を回した作業には Issue が無く、Issue がある作業には plan も spec も無い。2 つのワークフローが並行して存在し、交わっていない状態である。

Issue を `closed/` へ移すときも、plans と specs は元の場所に残る。Issue 単位で作業の全体を追える状態になっていない。

## 検討すべきこと

### plans と specs を Issue ディレクトリ配下へ寄せるか

寄せる利点は、Issue を開いた人が設計と計画に直接辿り着けること、Issue を閉じたときに成果物も一緒に動くこと。

寄せない場合の代替として、Issue 本文の「関連」節から plans と specs へリンクを張る運用もある。ディレクトリ構造を変えずに参照だけ繋ぐ形になるが、リンクは人手なので張り忘れが検出できない。

### `.superpowers/sdd/` を含めるか

含めない方がよいと考える。理由は 2 つ。

`.superpowers/sdd/.gitignore` は `*` を持ち、配下は全て追跡外である。これは偶然ではなく、skill 定義が「plan が所有する git-ignored なディレクトリ」と規定し、`git clean -fdx` で消える scratch であると明記している。ledger と brief と report と review package はどれも作業中の中間生成物で、残す前提の成果物ではない。

これを追跡下の `docs/issues/<NNN>_<title>/` に置くと、追跡ディレクトリの中に `.gitignore` で `*` を書いた穴を空けることになる。Issue ディレクトリを丸ごと参照したり配布したりする意味が薄れる。

なお skill の最新版では sdd の置き場が plan ごとのサブディレクトリ (`<repo-root>/.superpowers/sdd/<plan-basename>/`) に変わっている。このリポジトリに残っているのは旧来のフラット配置で、`task-1-brief.md` のような plan 間で衝突する名前が並んでいる。上流も同じ問題を認識して直した形なので、追随するだけで衝突は解消する。

### 出力先をどう変えるか

plans と specs の出力先は skill 定義にハードコードされている。

- writing-plans: `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
- brainstorming: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`

superpowers は上流の marketplace プラグインなので、書き換えると更新のたびに fork の維持コストがかかる。取りうる形は次のいずれか。

- プロジェクトの `CLAUDE.md` で出力先を上書きする。skill より user instruction が優先される仕組みに乗る
- skill の指定どおりに書かせ、作業の区切りで Issue ディレクトリへ移す。移動を忘れると元の場所に残るので、検出手段が要る
- skill を fork して出力先を変える。更新追随のコストを引き受ける
- 現状維持とし、Issue 本文からのリンクで繋ぐ

### 既存の 12 ファイルをどうするか

対応する Issue が存在しないものが多い。移すには Issue を遡って起票することになるが、完了済みの作業に Issue を作る意味があるかは別の判断になる。`docs/superpowers/` に残したまま新規分から新方式にする案もある。

### Issue を先に起票する運用を強制するか

成果物を Issue ディレクトリ配下に置くなら、Issue が先に存在している必要がある。ブレインストーミングの途中で Issue 番号を決められるか、探索的な作業で Issue を先に切るのが自然かは、実際の進め方に照らして決めたい。

## タスク

- [ ] plans と specs を Issue ディレクトリ配下へ寄せるかを決める
- [ ] `.superpowers/sdd/` の扱いを決める (追跡外のまま据え置くか、Issue ディレクトリへ入れるか)
- [ ] 決めた場合、出力先の変更方法を選ぶ
- [ ] 既存の 12 ファイルの移行方針を決める
- [ ] Issue を先に起票する運用にするかを決める
- [ ] 決めた方針を `CLAUDE.md` か `dev-workflow:in-repo-issue` skill に落とす
- [ ] 置き場の規約から外れた成果物を検出する手段を用意する (人手のリンクや移動は忘れが検出できない)
- [ ] sdd の置き場を上流の最新形式 (plan ごとのサブディレクトリ) に追随させる

## 関連

[Issue #15: docs の相対リンクを pre-commit で検査する](../15_docs%20の相対リンクを%20pre-commit%20で検査する/issue.md) と隣接する。本 Issue で Issue ディレクトリ配下にファイルが増えると、相対リンクの本数も増えるため検査の価値が上がる。
