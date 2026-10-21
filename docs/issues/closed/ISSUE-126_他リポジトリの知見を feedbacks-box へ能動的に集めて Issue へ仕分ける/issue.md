---
status: closed
parent: ISSUE-97
---

# feat: 他リポジトリの知見を feedbacks-box へ能動的に集めて Issue へ仕分ける

## 背景

ISSUE-97 の「集める側の経路が無い」を、受け箱の送る側と仕分ける側に絞って切り出したもの。

受け箱 (`docs/.feedbacks-box/`、ignore 済み) と、箱の中身を dotfiles の SessionStart で告げる hook は PR 253 で入った。送る側は非公開の運用指示の一文に頼っていて、他リポジトリのセッションが自分で思い出したときにしか届かない。2026-10-20 に transcript を数えたところ、箱へ実際に書き込んだのは数セッションだけで、指示が読み込まれたセッションの数に比べてごく一部だった。

集めたいのは、言語やビルドの性能チューニングの手法、新しく使った skill や plugin の使用感のように、リポジトリを越えて効く知見である。Memory はセッションごとに溜まって整理されないので、検証できる形で CLAUDE.md / rules / skill / plugin へ寄せたい。

設計は ISSUE-126-spec.md が持つ。

## タスク

- [x] spec を書いてレビューを通す
- [x] plan を書く
- [x] 実装前に、Stop の additionalContext の効き方と Workflow の子の見分け方を実測する
- [x] 送る側: 置き場を伝え、コミットのあとに案内し、セッションの終わりに箱へ届ける hook を作る
- [x] 送る側: まとめの書式を持つ skill を agentic-coding-tools に作り、pin を上げる
- [x] 受け取る側: 箱の中身を main の in-repo Issue へ仕分ける告知と手順に変える
- [x] 通しで確かめ、非公開の運用指示を書き換える

## 関連

- ISSUE-97: 親。受け箱と仕分けの工程の設計をこの Issue へ移した。刈り込みと公開範囲の一般化は親に残る
- ISSUE-88 と ISSUE-89: 委譲された知見の反証の実例。仕分けで実測を通過条件にする根拠
- ISSUE-67: handoff-sentinel の通知が 1 セッション 1 回で再武装しない件。Stop の割り込みの回数の設計と重なる
- ISSUE-71: SessionStart の告知が subagent へ届かない件
