---
status: open
---

# depends: agentic-coding-tools の pin を v0.20.0 へ上げ、配布物からテストが消えたことを確かめる

## 背景

agentic-coding-tools が v0.20.0 をリリースし、そちらのセッションから pin の更新と、同リポジトリの ISSUE-76 のタスク4の確認を頼まれた (2026-10-22)。v0.20.0 は 2673c03c0ef620488ad3e285b1ec235d46796fa4 を指す annotated tag で、今の `home/apm.yml` の同リポジトリの pin は v0.19.0 (2ec9a1901a1708a238c888e637230a4d831e67df) である。pin は SHA で書き、行末に版を注記する。

変更の中身は、配布物にあったテスト13本 (Python 11本と `*.test.mjs` 2本) が配布物から消えること。security-blue-red-team と web-monkey-qa の plugin では `schemas/tests/` ごと無くなる。消費側の呼び出しが壊れる変更は無いと聞いている。

## タスク

- [ ] `home/apm.yml` の agentic-coding-tools の pin をすべて v0.20.0 の SHA へ揃え、`apm install` する
- [ ] 各アカウントの設定ディレクトリの skills/ で、テストのファイル (`test_*.py` と `*.test.mjs`) を探し、agentic-coding-tools 由来のものが0件であることを確かめる。対照として、同じ探し方で他の配布元のテストが非空であることも見る
- [ ] lock の `deployed_files` から agentic-coding-tools 由来のテストのエントリが消え、本体 (SKILL.md やスクリプト) は載っていることを、lock の差分で確かめる
- [ ] 既に展開済みの古いテストのファイルを apm が消すかを確かめ、残るならその旨を記録する
- [ ] 結果を依頼元のセッションへ返す。先に終わっていたらこの Issue の記録で代える

## 関連

- agentic-coding-tools の ISSUE-76: 配布物からテストを外す。この Issue はそのタスク4 (消費側の確認) を持つ
- agentic-coding-tools の ISSUE-75: 同じ pin 上げに相乗りしてよい消費側の確認
