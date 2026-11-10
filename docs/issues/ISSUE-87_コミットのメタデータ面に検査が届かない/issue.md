---
status: open
---

# fix(security): コミットのメタデータ面に検査が届かない

## 背景

agentic-coding-tools のセッションから委譲された。あちらの ISSUE-15 (PUBLIC リポジトリの
漏洩ガード) を実装する過程で、どの層でも塞げない面が見つかっている。

グローバル CLAUDE.md は「個人情報 (実メールアドレスや実名…) はコミット、コミット
メッセージ/コードに載せないこと」を求めるが、コミットのメタデータにはどの検査も届かない。

gitleaks が走査するのはファイルの内容だけである。コミットメッセージ (subject / body /
trailer)、author / committer、注釈付きタグの tagger と message はいずれも面の外にある。
委譲元は走査バイト数がファイル内容の合計と一致し、メタデータ由来が 1 バイトも含まれない
ことを 8.30.1 で確認している。

## dotfiles での実測 (2026-09-11)

| 対象 | 結果 |
| --- | --- |
| ユニークな author / committer アドレス | 5 件 |
| うち予約形 (noreply / example / invalid / test / localhost) | 0 件 |
| annotated タグ | 0 件 |

値は取り出していない。ドメインが予約形かどうかの分類だけを出す形で判定した。PUBLIC な
場所へ値を書くと調査そのものが露出になるため、以後もこの形で見ること。

## 既知だった (2026-06-26 の監査)

`project-public-leak-audit` のメモリが「commit author 実メールは git 標準で公開範囲、
未対処」と記録している。history rewrite も同じ監査で見送りが決まっている
(低機微・既公開・open PR 巻き込みのため)。

**新しいのは「これから作る分は守れる」という視点である。**過去は変えられないが、
identity を予約形にすれば以後のコミットは守られる。

## 実施済み (2026-09-11)

`~/.gitconfig.private` の `user.email` を GitHub の noreply 形へ変えた。identity 単位の
設定なので、このマシンの全リポジトリに同時に効く。

`home/.gitconfig.private.example` のコメントも、noreply 形を使う理由と引きかたを持つ形へ
書き換えた。bootstrap は既存ファイルがあればコピーをスキップするので、既にセットアップ済みの
マシンへは届かない。

## 決めること

### 検査をどう足すか

今後 identity が予約形であることを何が保証するか。候補が 3 つある。

1. config-guard に足す。dotfiles の検査層に乗るが、見るのは追跡外のファイル
   (`~/.gitconfig.private`) になるので、検査の母集団の外にあるものを見ることになる
2. `guard-health.py` の probe に足す。セッション頭で告げる層で、既存の 5 probe と同じ扱い。
   追跡外のファイルを見ることに違和感が無い
3. pre-commit hook に足す。コミットの瞬間に見られるが、全リポジトリへ配る必要がある

2026-11-10の仕分けで、受け箱から、どの候補にも要る判定の仕方の報告が届いた。別のリポジトリのセッションの報告で、dotfiles では確かめていない。

- コミットの作者の縛りは `git config user.email` ではなく `git var GIT_AUTHOR_IDENT` と `git var GIT_COMMITTER_IDENT` で見ると、環境変数 GIT_AUTHOR_EMAIL / GIT_COMMITTER_EMAIL がアドレスを上書きする経路まで塞げる。設定だけを見る検査は、環境変数で個人のアドレスが入ったコミットを素通しする。使い捨てのリポジトリで環境変数を差し込むテストを書き、作者とコミッタを片方ずつ外す変異で両方が赤になることを確かめた (実測)
- 報告者の提案は、作者の縛りの検査は `git var GIT_*_IDENT` で見る、という形を、コミットを作るスクリプトの規範の候補にすること (実測)。上の3案のうち1つ目と2つ目は `~/.gitconfig.private` を見る形として書かれているので、そのままではこの経路は見えない (仕分けたセッションの解釈)

### gitleaks の allowlist に noreply 形を足すか

`home/.gitconfig.private.example` に noreply 形の実例を書こうとしたところ、
`.gitleaks.toml` の `email-address` ルールが検出することが分かった。allowlist は
文書用の例示ドメインと SSH clone URL の 2 軸だけで、noreply 形はどちらにも入らない
(集合の正本は `.gitleaks.toml` の `email-address` ルール自身)。

noreply 形は公開を前提に設計されたアドレスなので、allowlist に入れる方が筋は通る。ただし
`.gitleaks.toml` は canonical で、変更すると ISSUE-64 の 2 リポジトリの写しへも配り直しが要る。
今回はテンプレート側を placeholder のままにして回避した。

### 他マシンへの配りかた

`~/.gitconfig.private` は追跡外で、bootstrap は既存ファイルを上書きしない。他のマシンには
届かないので、手で直すのか、bootstrap に「予約形でなければ告げる」層を足すのかを決める。

## タスク

- [ ] 検査の置き場を決める (3 案の比較)
- [ ] 決めた形で実装し、変異注入で pin する。予約形でない identity を検出できることと、
      予約形で沈黙することの両方を見る
- [ ] gitleaks の allowlist に noreply 形を足すかを決める。足すなら 3 リポジトリへ配り直す
- [ ] 他マシンへの配りかたを決める
- [ ] コミットメッセージと tagger の面をどう扱うか決める。identity とは別の経路で、
      検査も手当ても違う

## 関連

agentic-coding-tools の ISSUE-15: PUBLIC リポジトリの漏洩ガード。この Issue の出所で、
あちらの「## タスク」にも同じ面が記録されている。層 1〜3 のどれを足しても塞げないことは
あちらが実測している

ISSUE-64: gitleaks の取り付けを扱う。あちらが入れる層はファイル内容の面で、この Issue は
その面の外を扱う。同じツールを使うが守る対象が違う

Issue 21: PUBLIC リポジトリに露出している個人情報と private リポジトリ情報を棚卸しする。
2026-06-26 の監査の続きで、この Issue が扱うメタデータ面はあちらの棚卸しの対象に入る
