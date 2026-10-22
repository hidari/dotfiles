---
status: closed
---

# depends: agentic-coding-tools の pin を v0.20.0 へ上げ、配布物からテストが消えたことを確かめる

## 背景

agentic-coding-tools が v0.20.0 をリリースし、そちらのセッションから pin の更新と、同リポジトリの ISSUE-76 のタスク4の確認を頼まれた (2026-10-22)。v0.20.0 は 2673c03c0ef620488ad3e285b1ec235d46796fa4 を指す annotated tag で、今の `home/apm.yml` の同リポジトリの pin は v0.19.0 (2ec9a1901a1708a238c888e637230a4d831e67df) である。pin は SHA で書き、行末に版を注記する。

変更の中身は、配布物にあったテスト13本 (Python 11本と `*.test.mjs` 2本) が配布物から消えること。security-blue-red-team と web-monkey-qa の plugin では `schemas/tests/` ごと無くなる。消費側の呼び出しが壊れる変更は無いと聞いている。

## 結果 (2026-10-23)

apm 0.34.0 で、`home/apm.yml` の同リポジトリの pin 10行を 2673c03 (v0.20.0) へ揃えて `apm install` し、rc 0 で終わった。続けて `apm install --frozen` も rc 0 で、展開先のハッシュは変わらなかった。`apm audit` は rc 0 で drift なしを返した。

- 2つのアカウントの設定ディレクトリの `skills/` は、どちらも `home/.claude/skills` への symlink で、実体は1か所だった。apm の展開先は lock の `deployed_files` から数えて `skills` / `agents` / `commands` の3つだけで、この3つを上げる前と後で sha256 の一覧に取って比べた
- テストのファイル (`test_*.py` と `*.test.mjs`) は、上げる前に16件、上げた後に0件だった。16件は上流で消えた13本と、dev-workflow の plugin の内側の skill を展開先の最上位へ写した flat の写しの3件 (`commit-and-pr-message` の2本と `in-repo-issue` の1本) にあたる。`schemas/tests/` のディレクトリも残っていない。展開済みの古いテストのファイルは apm が消し、配布物に入っていない `__pycache__` の `.pyc` も1件、同じく消えた
- 展開先のファイルは848件から831件になった。残った831件のうち829件は sha256 が変わらず、変わった2件は `check-leak-guard-denylist.py` の展開された2つの写し (flat の写しと dev-workflow の plugin の内側) だった。上流の v0.19.0 と v0.20.0 の配布物 (`plugins/` と `skills/`) の差分は、テストの13本の削除と、このファイルの docstring がテストの在り処を指す文の書き換えだけで、展開されたファイルは v0.20.0 の blob と sha256 が一致した
- lock の差分では、テストのファイルを指す行が48行から0行になった (1件につき deployed_files の一覧・ファイルごとのハッシュ・所有者のブロックの3か所)。`deployed_files` の一覧の行 (行頭が `  - .claude/skills/`) で数えると、SKILL.md は上げる前と後のどちらも30行、本体のスクリプト (`check-outgoing-text.py` / `check-leak-guard-denylist.py` / `issue-id.py` / `macvm.py` / `winvm.py` / `jevlint.py`) はどちらも9行で、展開先にも本体のファイルが揃っていた
- 依頼元のセッションは、この結果が出た時点の ListAgents に無かったので、この記録で返す

## タスク

- [x] `home/apm.yml` の agentic-coding-tools の pin をすべて v0.20.0 の SHA へ揃え、`apm install` する
- [x] 各アカウントの設定ディレクトリの skills/ で、テストのファイル (`test_*.py` と `*.test.mjs`) を探し、agentic-coding-tools 由来のものが0件であることを確かめる。対照として、同じ探し方で他の配布元のテストが非空であることも見る
  - 対照は差し替えた。展開先のテストのファイルは上げる前から全件が agentic-coding-tools 由来で、他の配布元のテストは0件だったので、この対照は取れない。代わりに、同じ探し方を上げる前に当てて16件が出ることを対照にした
- [x] lock の `deployed_files` から agentic-coding-tools 由来のテストのエントリが消え、本体 (SKILL.md やスクリプト) は載っていることを、lock の差分で確かめる
- [x] 既に展開済みの古いテストのファイルを apm が消すかを確かめ、残るならその旨を記録する
- [x] 結果を依頼元のセッションへ返す。先に終わっていたらこの Issue の記録で代える

## 関連

- agentic-coding-tools の ISSUE-76: 配布物からテストを外す。この Issue はそのタスク4 (消費側の確認) を持つ
- agentic-coding-tools の ISSUE-75: 同じ pin 上げに相乗りしてよい消費側の確認。2026-10-23に見た時点で closed で、何も references へ移さなかったので相乗りする確認は無かった
