---
status: open
---

# fix(config-guard): git の toplevel でないルートを渡すと検査が空振りして rc 0 で通る

## 背景

jev-lint-curated の tests-cover-failure-paths が指した config-guard の `cli.main` を調べる途中 (2026-09-29) で見つかった。主目的 (jev-lint の指摘への対応) から外れるので、直さずにここへ切り出した。

`scan` と `main` は、受け取った repo_root が git の toplevel かどうかを確かめない。サブディレクトリを渡すと、追跡ファイルを列挙する検査はそのディレクトリの配下しか見ないので、ほとんどが空振りする。そのまま「問題は検出されませんでした」の rc 0 で終わる。一方で、settings.json を `git show :<path>` で読む検査は toplevel 基準で解決するので、実物を読む。検査ごとに見ている範囲が食い違ったまま、全体としては緑になる。

実測 (scripts/config-guard から `uv run config-guard <root>` を実行した):

- root に `.` (サブディレクトリ) を渡すと、「常時 0B / 予算 26480B、scoped 0 枚 0B」「関連 0 節 / 識別子 0 件 / 残リンク 0 件」「問題は検出されませんでした」で rc 0
- 対照として root に `../..` (toplevel) を渡すと、「常時 26016B」「関連 113 節 / 識別子 299 件」で rc 0

誤ったルートは、clean なリポジトリと見分けが付かない。見分ける手掛かりは、要約行の値を人が読むことだけになる。git 管理下でないディレクトリを渡した場合は、git の失敗が RuntimeError の traceback になって rc 1 で止まるので、黙っては通らない。

届く経路は、手で起動してルートを誤ったときだけ。pre-commit は `git rev-parse --show-toplevel` を、CI は `../..` を渡す。ただし、console script が sys.argv を読む分岐が壊れると、本番もこの状態へ落ちる。この分岐は、同じ変更で足したテスト (test_console_script_scans_the_root_given_on_the_command_line) が守っている。

## 決めること

- ルートが toplevel でないときに、拒否して非0で終えるか、toplevel へ解決し直して続けるか
- 非0で終えるなら、問題を検出した1と区別する終了コードを持つか
- どこで直すか。root を `resolve()` しているのは scan だけで、main は要約行を作る `budget_summary` と `related_refs_summary` へ受け取った値をそのまま渡している。上の証拠は要約行なので、scan だけを直すと要約行は直らない。main の入口で1回だけ検査する形が候補

## タスク

- [ ] 上の各点を決める
- [ ] 誤ったルートを渡したときの振る舞いを表すテストを先に書いてから直す

## 関連

なし
