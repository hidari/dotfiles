---
status: open
---

# feat: gh を持ち主ごとの fine-grained トークンで動かし書き込みだけ承認つきで昇格する

## 背景

別のリポジトリのセキュリティレビュー(2026-11-15)で、開発機にある GitHub の認証情報が1つ盗まれると、タグを push してリリースの workflow を動かせる経路が指摘された。入口として現実的なのは、手元で動く開発依存が悪性の版に入れ替わる場合。

2026-11-22 時点の開発機の状態(実測):

- gh は `gh auth login` で発行された OAuth のトークン(`gho_`)を keyring に持つ。スコープは `admin:org` / `admin:public_key` / `gist` / `repo` / `workflow`。同じユーザーのプロセスなら確認なしで push・タグの作成・ruleset や Environment の変更ができる
- 開発機のリポジトリの持ち主は4つ(個人アカウント1つと org 3つ)

SSH の側は同じ日に済ませた(マシンローカルの設定で、追跡下には無い)。鍵は 1Password の SSH agent が持ち、使うたびに承認を挟む。古い鍵はディスクと GitHub から外した。この Issue は残る gh の層を扱う。

### 決めたこと(2026-11-22、ユーザー)

- 普段使いのトークンは読み取り中心にする。push とタグは承認つきの SSH だけで行う
- トークンは持ち主ごとに fine-grained で持つ
- 普段使いに足す読み取りの権限: Administration / Environments / Secrets / Actions / Dependabot alerts の read。別のリポジトリの構成検査が、gh の既定のトークンでこれらを GET する。検査用のトークンは分けない
- 書き込みが要る操作(`pr merge`、`release create`、`api` の書き込みのメソッドなど)では、shim が自動で強いトークンへ切り替え、1Password の承認を挟む(案 B)
- 強いトークンも持ち主ごとの fine-grained にし、Administration を付けない。承認を通したあとでも、ruleset と Environment は変えられない
- 承認待ちでバックグラウンドの Claude の push が止まるのは受け入れる

### 実測で確かめたこと(2026-11-22)

- `op read` は呼ぶたびに 1Password の承認ダイアログが出る。Claude の Bash から別々のコマンドで呼んだ場合の実測。普段使いのトークンを 1Password に置くと、gh を呼ぶたびに承認が要る
- fine-grained で Administration: read を付けると、`GET repos/{owner}/{repo}/rulesets/{id}` が `bypass_actors` を返す
- Administration: none でも、同じ endpoint は 200 を返し、中身の入った `bypass_actors` を伏せずに返す。この endpoint に要る権限は `x-accepted-github-permissions: metadata=read` だった。読み手はリポジトリの admin
- Administration: none だと `GET actions/permissions` は 403 になる(要るのは `administration=read`)。ruleset の作成と Environment の作成も 403 になる
- 応答ヘッダの `x-accepted-github-permissions` で、その endpoint に要る fine-grained の権限が分かる

## タスク

- [x] 設計書(`ISSUE-147-spec.md`)を書いて承認を得る
- [ ] 実装プランを書く
- [ ] shim と配線を実装する(テストつき)
- [ ] 持ち主ごとの普段使いのトークンと強いトークンを発行して置く(ユーザーの操作)
- [ ] gh の OAuth のトークンを外し、GitHub の Authorized OAuth Apps から許可を取り消す
- [ ] 構成検査を実物にかけて読めることを確かめ、依頼元のセッションへ変えた内容を報告する

## 関連

なし(依頼元は非公開のリポジトリなので、名前を書かない)
