---
status: open
---

# chore(config-guard): コードに残るタスク参照コメントを掃除する

## 背景

ISSUE-59 のマージ前レビュー (boy-scout-sweep) が、今回触っていない隣接ファイルにタスク参照
コメントが 3 箇所残っていると報告した。着手の根拠にする前に数え直したところ、**追跡下の
非 docs ファイル全体では 14 箇所 / 6 ファイル**だった。

| ファイル | 件数 |
| --- | --- |
| `scripts/config-guard/src/config_guard/rules_paths.py` | 5 |
| `scripts/config-guard/src/config_guard/instruction_budget.py` | 3 |
| `scripts/config-guard/tests/test_index_flags.py` | 2 |
| `scripts/config-guard/tests/test_related_refs.py` | 2 |
| `scripts/config-guard/src/config_guard/term_definitions.py` | 1 |
| `scripts/config-guard/tests/test_instruction_budget.py` | 1 |

レビューが報告した 3 箇所はテスト 2 ファイルのみで、production source の 3 ファイル 9 箇所は
入っていなかった。レビューの射程が「触ったファイルの隣接」に限られていたためで、報告の欠陥
ではない。**棚卸しの表は見つけた分だけが載るので必ず過小評価に外れる**、という規範どおりの形。

コードに書かれたタスク参照が問題なのは 2 つの理由による。1 つは PR の説明にあるべき情報が
コードへ入っていること。もう 1 つは参照先が動くことで、確認した範囲では `Issue #8` と
`Issue #36` はどちらも既に `docs/issues/closed/` 配下へ移っており、コメントが指す位置は
既に変わっている。

加えて `#<数字>` という記法自体が規約違反にあたる。この記法は GitHub の Issue / PR の
番号空間で、in-repo Issue は別の識別子を使う。同じ番号の GitHub オブジェクトと文脈でしか
区別できず、GitHub 側の autolink も発火する。`issue-id.py` の検査入口はこの混入を検出するが、
入口がコミットメッセージと一部の追跡ファイルに限られるため、既存のコメントは素通りしている。

## タスク

- [ ] 14 箇所から参照を外す。参照先が closed で復元できる情報でも、番号を振り直さず参照を
      伴わない記述へ書き換える (推測で番号や識別子を割り当て直さない)
- [ ] 参照を外すときに、そのコメントが持っていた WHY まで落とさないこと。番号は参照であって
      理由ではないので、理由が番号にしか無い箇所は先に理由を書き起こす
- [ ] 数え直した 14 という数自体を再検算する。上の集計は `Issue #<数字>` という 1 つの記法で
      引いたもので、`ISSUE-59` 形式や `PR #<数字>` 形式は別に数える必要がある
- [ ] `issue-id.py` の検査入口を広げてこの形を機械的に捕まえられるか判断する。広げないなら
      理由を残す。検査の射程を広げる判断は agentic-coding-tools 側の領分になる可能性がある

## 関連

ISSUE-59: この Issue の発端。マージ前レビューの boy-scout-sweep が隣接ファイルの候補として
報告したもので、触ったファイルではないため別 Issue へ切り出した

ISSUE-61: 言語規約が surface ごとに割れている。コメントの書き方に関する規約という点で
射程が隣接する
