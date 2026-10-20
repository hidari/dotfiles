---
status: open
---

# fix: feedbacks-outbox と hook_git で保留した端の扱いをまとめて片付ける

## 背景

ISSUE-126 で入れた送る側の hook (`home/.claude/hooks/feedbacks-outbox.py`) の最終レビューで、直さずに保留した小問題が5件あった。保留の判断はどれも「正しさへの影響が小さいか、この PR の範囲外」で、別の作業として残した。

保留を記録した台帳は実装の worktree の中にあり、worktree と一緒に消えた。下の各項目の判断の文面は消える前に会話へ写したものから取った。submodule の件だけは台帳に詳細があって写していなかったので、2026-10-20 に挙動を測り直して書いた。

### 本体の位置が linked worktree の位置にずれる

`hook_git.main_checkout_root` は、common dir が `.git` という名前でないとき (submodule の `.git/modules/<name>` と `--separate-git-dir`) に `None` を返す。この挙動はテストが pin している。feedbacks-outbox はそのとき作業ツリーのルートへ落とすので、こうした repo の linked worktree では、本体ではなく worktree の位置と名前を使う。

2026-10-20 に、使い捨てのリポジトリで `_active_roots` が返す本体の名前を測った。

- 対照の普通のリポジトリ: 本体からも linked worktree からも本体の名前になる
- `--separate-git-dir` のリポジトリ: 本体では本体の名前、linked worktree では worktree のディレクトリ名になる
- submodule: submodule の中では submodule の名前、submodule の linked worktree では worktree のディレクトリ名になる

影響を受けるのは、受け箱へ届けるファイル名の repo 名と、受け箱を持つ側かどうかの判定 (本体の `docs/.feedbacks-box/` を探す位置) の2つ。受け取る側の `feedbacks-box.py` も同じ関数で本体を探す。dotfiles 自身は普通のリポジトリなので、今は症状が無い。

### 保留した4件

- dotfiles 自身を除外する比較で両辺の `resolve()` を外しても、テストが赤にならない。比較そのものは正しく、symlink 越しのパスのテストが無いだけ。dotfiles を symlink 越しに開いたときに、自分を送る側と誤って判定しうる
- `recover_stale` が mtime を見る前に git (`_tracked_names`) を起動する。正しさには影響せず、回収の候補があるときの SessionStart のコストが1回増える
- 届け先へ link したあとで元のまとめの unlink に失敗すると、次の機会にもう一度届く。頻度が低く、受け取る側の重複検索で吸収される
- まとめの大きさを検査してから読むまでの間にファイルが育ちうる。書くのはセッション自身なので実害が小さい

## タスク

- [ ] 本体の位置のずれを直すか決める。直すなら `main_checkout_root` の `None` を、common dir を持つ repo の本体の作業ツリーへ解決する方法 (`core.worktree` や `git rev-parse --show-superproject-working-tree` 等) を測ってから選ぶ。同じ関数を使う `feedbacks-box.py` と `guard_probes.py` への影響も見る
- [ ] dotfiles 自身の除外を symlink 越しのパスで pin するテストを足し、`resolve()` を外す変異で赤になることを確かめる
- [ ] `recover_stale` で mtime の検査を git の起動より前へ移すか決める
- [ ] unlink の失敗による二重の配達と、大きさの検査と読み出しの間の競合を、今の判断 (直さない) のままにするか見直す。直さないなら、その理由を hook の docstring か Issue のクローズの理由に残す

## 関連

- ISSUE-126: feedbacks-outbox を入れた Issue。保留の判断はその最終レビューで行った
- ISSUE-129: in-repo-issue のクローズの理由の節の規約。この Issue を直さずに閉じるときの書き方もそちらで決まる
