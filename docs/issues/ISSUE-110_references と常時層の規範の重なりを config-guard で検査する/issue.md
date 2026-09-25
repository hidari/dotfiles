---
status: open
---

# feat(config-guard): references と常時層の規範の重なりを config-guard で検査する

## 背景

ISSUE-106 の L10 で、`home/.claude/references/` の各節が `home/.claude/CLAUDE.md` や `home/.claude/rules/*.md` の規範文を再掲していた箇所を手で消した。監査が挙げたのは4本だったが、数え直すと8本すべてにあった。規範側だけを直すと references の写しが取り残される形で、実際に食い違っていた。

「references は規範の文面を再掲しない」は、ISSUE-106 のマージ前ゲートで CLAUDE.md の5行目 (カテゴリと references の分担を定義する文) へ書いた。散文なので、次の再掲は次の監査まで見つからない。

ISSUE-106 の作業では、文字 bigram の包含率で「references の文が規範側のどの文にどれだけ含まれるか」を測って突き合わせた。マージ前ゲートの altitude のレビューが同じ方式で向きを逆にして測ると、main (作り替え前) は0.9以上が32件・0.85以上が42件で8本すべてに出た。作り替え後は0.85以上が0件で、最大は意図して残した過去形の事例の0.82だった。

## 決めること

- 検査の形。references/*.md の各文について、CLAUDE.md と rules/*.md の文に対する包含率の最大値を出し、しきい値以上を報告する案がある。しきい値は上の実測から0.85か0.9
- 母集団は既存の定義 (`instruction_budget` の CLAUDE.md と rules の指定、`instruction_refs` の references の指定) から import して再宣言しない
- 意図して残す文の免除を、`term_definitions` の `ACKNOWLEDGED` と同じく理由付きで持つか
- 文の切り出しは段落の行を結合してから行う。文の途中の改行が残っていると件数が少なく出るので、ISSUE-108 の改行の扱いと関係する
- 限界として、写しは捕まるが言い換えは捕まらない。どこまでを検査に任せるか

## タスク

- [ ] 上の各点を決める
- [ ] 検査を実装し、変異注入 (再掲の文を1つ戻すと赤くなる、免除を外すと赤くなる) で pin を確かめる

## 関連

ISSUE-106: references の作り替えを手で行った作業

ISSUE-108: 文中の改行の扱いが、この検査の文の切り出しに関係する
