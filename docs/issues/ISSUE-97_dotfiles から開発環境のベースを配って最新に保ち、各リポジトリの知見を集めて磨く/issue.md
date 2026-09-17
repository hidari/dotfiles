---
status: open
---

# feat: dotfiles から開発環境のベースを配って最新に保ち、各リポジトリの知見を集めて磨く

## 背景

ユーザーの構想。dotfiles がローカル開発環境のベース (skill / plugin / rules / CLAUDE.md / hooks /
検査の設定) を各リポジトリへ配り、最新に保つ。逆向きに、各リポジトリで得たプラクティスを集めて
一般化し、ベースを磨く。

### 今の配布の経路

| 経路 | 配るもの | 届き方 |
| --- | --- | --- |
| apm (agentic-coding-tools から) | skill / plugin | deploy 先はホーム直下の 1 箇所で、全リポジトリへ同時に届く (上流 ISSUE-22) |
| symlink (dotfiles から) | hooks / settings / CLAUDE.md / rules | 同じく全リポジトリ共通 |
| リポジトリごとの写し | `.gitleaks.toml` と pre-commit の設定 (ISSUE-86)、in-repo Issue の template と採番スクリプト、issue-scoped-artifacts の hook block | 写した時点で止まる |
| GitHub の設定 (計画中) | ruleset (ISSUE-50) | dotfiles の汎用定義を API で各リポジトリへ適用する |

### 鮮度が落ちても誰も告げない

apm の pin が上流から遅れた実例 (2026-09-17) は ISSUE-101 へ切り出した。写しの側の drift は
ISSUE-53 の実測がある (旧版のまま残る写しと、宣言そのものが無い配布先)。

### 集める側の経路が無い

- 今の収集は、別リポジトリのセッションからの委譲 (ISSUE-88 / ISSUE-89 のような起票) だけである。
  委譲元が思い立ったときにしか届かない
- retrospective-codify は、学びを CLAUDE.md / rules / skill へ直接書き出す手順を持つ。リポジトリを
  またぐ受け箱や、後でまとめて仕分ける工程は持たない
- 書き出し先の `~/.claude/CLAUDE.md` は dotfiles の作業ツリーが実体なので、他リポジトリの
  セッションから書くと dotfiles の作業ツリーが変わる

## 方向性 (会話で出したもの。未決)

- 配布は push ではなく pull にする。各リポジトリのセッションが SessionStart で drift を告げる
  (guard-health のプローブが近い形)
- 写しを減らし、apm の pin か symlink で参照させる。写しが無ければ drift も起きない
- 収集は、retrospective-codify の候補を非公開側の受け箱へ落とし、週 1 の仕分けで一般化してから
  起票する。採否とマージはユーザーが決める

## 壁

- **公開範囲。**非公開リポジトリで得た知見は、一般化しないと PUBLIC な dotfiles へ入れられない。
  語単位の検査では落としきれない形がある (上流 ISSUE-57 の記録: 列挙の組み合わせが対象を特定する形と、
  解釈を反転させるメタ記述)
- **質。**委譲された主張は、そのままでは規範にできないものが少なくない (ISSUE-88 と ISSUE-89 に
  反証の記録がある)。実測の裏付けを通過条件にする
- **量。**常時ロード層の予算は余裕が 0 (予算値の canonical は config-guard の `instruction_budget`。
  2026-09-17 時点で CLAUDE.md の実バイト数が予算値と同じ)。週次のレートリミットも実際の制約になる。
  集める工程には、刈り込む工程をセットで置く

## 決めること

- 配る対象と単位。上の経路 (計画中の GitHub の設定を含む) のどれを「ベース」に含めるか
- **写しか参照か。**CI と pre-commit が読むものは追跡下に要る。apm が deploy したものは git hook
  からも CI runner からも存在が保証されない (ISSUE-46 の「検査を取り付ける土台が大半のリポジトリに
  無い」節)。symlink の先も開発機のホーム直下にしか無く、CI runner には無い。上流 ISSUE-32 の spec
  も、供給連鎖を理由に追跡下の写しを採っている。追跡下に残す写しと参照へ移せる写しを切り分け、
  写しを採る判断を開け直すかを決める。採番スクリプトを写す理由は in-repo-issue skill の
  「初期化」節が持つ
- 写しの告知の置き場。SessionStart のプローブに足すなら、ISSUE-83 (プローブが逐次に走り、待ち時間の
  上限が積み上がる) と ISSUE-71 (SessionStart の告知が subagent へ届かない) が先に効く。Issue 42 が
  SessionStart の注入で同じ形を先に作っている (前例の中身は ISSUE-53 の「Issue 42 が作った前例」節)。
  pin の鮮度の経路は ISSUE-101 が決めるので、先に決まった方をもう一方が使えるかを見る
- 受け箱の置き場と形式。PUBLIC なリポジトリには置けない。Issue 42 の外部ストレージが候補になる
- 仕分けの工程。重複の統合 (ISSUE-89 の例)、反証 (ISSUE-88 の例)、マイルストーンへの所属
  (ISSUE-46 の未決タスク。委譲元には表を読む理由が無い)
- 刈り込みの工程と、その基準

## タスク

- [ ] 配る対象を経路ごとに棚卸しする (apm / symlink / 写し / GitHub の設定)。上流 ISSUE-36 の
      型 3 と型 6 を出発点にし、見つけた分だけが載る表なので数え直す。数え直した結果は、同じ
      タスクを持つ上流 ISSUE-36 へ渡す
- [ ] 写しを、追跡下に残すものと参照へ移せるものに切り分ける。上流が扱っている写しは除く。
      採番スクリプトの写しは上流 ISSUE-32 の spec の層 2 が配り方を決め、template の写しは
      同じく層 4 がやめると決めている (どちらも未実装)。issue-scoped-artifacts の hook block は、
      上流 ISSUE-35 が写しをやめられるかを検討している (未決)
- [ ] 写しの drift を告げる経路を決める
- [ ] 受け箱と仕分けの工程を設計する
- [ ] 刈り込みの工程と基準を決める
- [ ] 公開範囲の一般化の手順を決める。語単位の検査で落ちない形の扱いを含める

## 関連

- ISSUE-53: 配布先の加入状況と写しの drift を見る層。写しの drift の判定はあちらが持ち、
  この Issue の写しの告知はあちらの判定の形が決まってから着手する
- ISSUE-101: apm の pin の鮮度を告げる。この Issue から切り出した
- ISSUE-72: 開発機にある全リポジトリの母集団。この Issue はあちらと ISSUE-53 の決定に従う
- ISSUE-86: `.gitleaks.toml` の写しを各リポジトリへ置く作業。写しか参照かの切り分けで方針が
  変わりうる (変わるのは内容で、着手順ではない)
- ISSUE-50: ruleset の汎用定義を dotfiles に置き、各リポジトリへ適用する計画を持つ。対象の
  リポジトリは実行時に取得するので、母集団の決定とも重なる
- ISSUE-83 と ISSUE-71: SessionStart へ告知を足すときの前提
- ISSUE-88 と ISSUE-89: 今の収集経路 (委譲) の実例
- ISSUE-77: 配布済みの skill と dotfiles のフック実装が食い違う件。同種の drift にあたる
- ISSUE-90: 配布物の形が変わったことに気づく層
- Issue 42 (closed): 外部ストレージと SessionStart の注入の前例
- agentic-coding-tools の ISSUE-32: 層 2 (採番スクリプトの写しと、in-repo-issue の hook block の
  固定テンプレート)、層 3 (横断スイープ)、層 4 (template の写しをやめる) の spec を持つ
- agentic-coding-tools の ISSUE-35: issue-scoped-artifacts の hook block の写しをやめられるかを
  検討している
- agentic-coding-tools の ISSUE-36: 消費側へ要求する取り付けの棚卸し。型 3 (写しの drift) が重なる。
  型 6 (配布層自体) の鮮度は ISSUE-101 が持つ
- agentic-coding-tools の ISSUE-22: deploy 先がホーム直下の 1 箇所しかない
- agentic-coding-tools の ISSUE-57: 収集時の一般化で、語単位の検査が落とす形の記録を持つ
