---
status: open
---

# feat: gh を持ち主ごとの fine-grained トークンで動かし書き込みだけ承認つきで昇格する

## 背景

別のリポジトリのセキュリティレビューで、開発機にある GitHub の認証情報の権限が広すぎ、1つ盗まれると人の承認なしに本番へ届く経路があると指摘された。入口として現実的なのは、手元で動く開発依存が悪性の版に入れ替わる場合。

2026-11-22 時点の開発機の状態(実測):

- gh は `gh auth login` で発行された OAuth のトークン(`gho_`)を keyring に持つ。スコープは `admin:org` / `admin:public_key` / `gist` / `repo` / `workflow`。同じユーザーのプロセスなら確認なしで push・タグの作成・ruleset や Environment の変更ができる
  - 2026-11-23の仕分けで、別のリポジトリから同じ型の再報告が届いた。`gh auth login` の OAuth のトークンは classic のスコープ (repo, workflow など) を持ち、持ち主の repo スコープで ruleset や Environment も変えられる。SSH の鍵だけを絞っても、タグの push の経路はこのトークンで残る (実測。ruleset を変えられることは推測)
- 開発機のリポジトリの持ち主は複数ある(個人アカウントと org)

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
  - 2026-11-23の仕分けで、別のリポジトリから同じ型の再報告が届いた。GitHub の ruleset の API がトークンの権限不足のときに bypass_actors を伏せるかを、迂回できる相手を1件持つ ruleset を使い捨てのリポジトリに作って確かめた (実測)。fine-grained のトークンに要る権限は応答ヘッダ `x-accepted-github-permissions` を見れば推測せずに分かり、`rulesets/{id}` の GET は metadata=read だけで通って、Administration が無くても bypass_actors を伏せずに返した (実測)
- Administration: none だと `GET actions/permissions` は 403 になる(要るのは `administration=read`)。ruleset の作成と Environment の作成も 403 になる
- 応答ヘッダの `x-accepted-github-permissions` で、その endpoint に要る fine-grained の権限が分かる

### 配置の前の棚卸しで分かったこと(2026-11-23)

- Claude Code (2.1.330) は PR の状態を `gh api graphql --hostname <host> --cache <ttl> -F query=@-` で取る。本文は stdin で、中身は読み取りの query だけ。shim は `query=@-` を中身を読めない write とみなしていたので、取得のたびに承認を求めるところだった。本文を読んで判定し直すように直した
- spec の「git の HTTPS の経路はすでに塞がっている」は誤りだった。開発機の追跡外の git 設定に、`gh auth git-credential` を絶対パスで呼ぶ github.com の credential helper があった。shim を素通りして、OAuth のトークンを HTTPS の git へ渡していた。HTTPS の origin を持つリポジトリは1つだけ
- `gh auth token` と `gh auth status` を読む使い手は、logout すると shim があってもトークンを受け取れない。shim は `auth` をトークン無しで委譲するため。次のものが該当する
  - Claude Code の auto mode のリポジトリの公開範囲の判定と `/web-setup`
  - apm と Homebrew の GitHub API の呼び出し。匿名に落ちる
- 持ち主の1つは自分が管理していない org で、fine-grained のトークンを発行できなかった。その org では外部コラボレーターで、GitHub のドキュメントは外部コラボレーターとしてのリポジトリへの貢献を fine-grained のトークンの未対応に挙げている。org の設定画面では fine-grained のトークンが承認制で許可されていたので、org のメンバーにしてもらえば使える見込み。設定からその持ち主を外した。開発機にはその org のリポジトリが1つある
  - 2026-11-23: そのあと org のメンバーになって2本を発行し、設定の `owner=` へ戻した。確かめた結果はタスクの項にある

### 決めたこと(2026-11-23、ユーザー)

- `query=@-` の誤判定は配置の前に shim で直す
- HTTPS の git の credential helper は消す。push は SSH だけにそろえる
- `gh auth token` の使い手が匿名に落ちるのは受け入れる。shim はトークンを `gh auth token` で配らない
- 1Password の強いトークンの項目名の形を、設定の `write_item=` で決められるようにする

### 配置して確かめたこと(2026-11-23)

- bootstrap.sh で配置し、新しいログインシェルの `command -v gh` が shim を指した
- 設定にある持ち主すべてで、shim 経由の読み取り(PR の一覧、rulesets の GET)が通った。応答ヘッダが fine-grained のトークンのもの(`github-authentication-token-expiration`)で、OAuth のトークンの `x-oauth-scopes` ではないことを、素の gh と並べて確かめた
- stdin で本文を渡す graphql の読み取りは、承認なしで通った
- 書き込みの承認ダイアログを拒否すると rc 1で止まり、普段使いのトークンで続行せず、対象は変わらなかった
- 承認を通した書き込みは成功した。一時的なブランチの ref を作って消せた。対照として、普段使いのトークンで同じ ref を作ると403になり、`x-accepted-github-permissions` は `contents=write` を求めた
- 強いトークンには Administration が無い。承認を通しても、リポジトリの設定の PATCH は403で止まり(`x-accepted-github-permissions` は `administration=write`)、対象は変わらなかった
- `gh auth logout` の後、素の gh は未ログインになり、shim の読み取りは通り続けた。GitHub の Authorized OAuth Apps から GitHub CLI の許可も取り消した
- logout の前に gh の使い手を棚卸しした。launchd のジョブ、hooks、statusline、Raycast のスクリプト、mise は gh もトークンも使っていなかった。影響があるのは上の棚卸しの `gh auth token` の使い手と、起動中のセッションだけだった
  - 起動中の Claude のセッションは shim の入る前の PATH を持つので、logout の後は gh が未ログインで落ちる。新しい zsh から起動し直すまで続く。起動し直さずに回すなら `zsh -i -c '<コマンド>'` で新しい対話の zsh を挟む
  - 2026-11-23の仕分けで、別のリポジトリのセッションから同じ型の報告が2件届いた。セッションの途中で gh の認証が PATH の先頭の shim に替わると、そのセッションは古い PATH のままなので素の gh が「未ログイン」で落ちる。セッションを起動し直すと /goal などの進行中の作業が切れるので、`zsh -i -c '<コマンド>'` で新しい対話の zsh から呼ぶと shim を通せた (実測)。もう1件も同じ形で、セッションの PATH が古くても shim を通せ、ユーザーが `!` で打つコマンドも同じ形で通った (実測)。仕分けたセッションの解釈: 上の起動中のセッションの項と同じ機構と手当てで、もう1件と同じまとめの apm のガードの側の報告は ISSUE-69 にある
- 上の棚卸しの HTTPS の git の credential helper を、開発機の git 設定から消した。github.com 向けに残る helper はシステムの osxkeychain だけで、キーチェーンに github.com の資格情報は無い
  - 2026-11-23の仕分けで、別のリポジトリから確かめ方の報告が届いた。git の HTTPS の資格情報が残っていないことは、`git credential fill` に `GIT_TERMINAL_PROMPT=0` を付けて password 行の件数だけを数え、同じ helper に一時の項目を入れて1件取れる対照と並べると確かめられる (実測)
- 設定から外した org のリポジトリは、shim 経由だと読み取りも書き込みも通らない。止まり方は読み取りと書き込みで違う(持ち主の決め方は `scripts/gh-token-shim/gh` の手順 5 が持つ)
  - 読み取りは既定の持ち主のトークンで黙って送られ、private のリポジトリは「Could not resolve to a Repository」で落ちた(そのリポジトリで作業するセッションの実測)。spec は、設定に無い持ち主を他人の公開リポジトリとしてしか想定していなかった
    - 2026-11-23の仕分けで、別のリポジトリから同じ型の再報告が届いた。gh を持ち主ごとのトークンの shim に替えた後、設定に無い持ち主の org のリポジトリは、読み取りが既定の持ち主のトークンに落ちて「Could not resolve to a Repository」になる。権限の不足ではなく「リポジトリが無い」に見えるので、原因を取り違えやすい。shim の前から動いていたセッションは「not logged into any GitHub hosts」になる (実測)。仕分けたセッションの解釈: 後半の未ログインの件は、同じ節の起動中のセッションの項 (logout の前の棚卸しの子) と同じ型。同じ報告の品質ゲートの手順の側は ISSUE-132 にある
  - 書き込みは「設定に無い持ち主」と名指しして止まる
  - 2026-11-23: この org はのちに設定へ戻したので、今はこの止まり方をしない (タスクの項)。止まり方そのものは、設定に無いほかの持ち主にも当てはまる
- 設定にある持ち主の1つでは、`gh repo list <owner>` が fine-grained のトークンで0件を返した(OAuth では数件)。同じトークンで REST の `orgs/<owner>/repos` は OAuth と同じ数を返す。原因は切り分けていない
- 別のリポジトリの作業で、権限の表の抜けが2つ見つかった
  - private のリポジトリの check run の読み取り(`commits/<sha>/check-runs`)は `checks=read` を要求し、403になった。fine-grained のトークンには Checks の権限が無い(GitHub のドキュメントが Checks API を未対応に挙げており、トークンの Edit の画面にも出ない)。CI の結果は Actions の run の API で読む。public のリポジトリでは権限なしで読めるので、ここまでの確認では見えなかった
    - 2026-11-23の仕分けで、別のリポジトリから同じ型の再報告が届いた。shim の読み取りトークンでは `gh pr checks` が commit の status を読めずに失敗した (Checks の権限が無いとみられる)。CI の結果は `gh run list --branch <b> --workflow <w>` なら読めた (実測)。報告者の提案: 読み取りトークンに Checks の read を足すか、`gh pr checks` が使えないことを shim の説明に書く。PR の CI の待ちに使う手順が読み取りのトークンで落ちる (実測にもとづく提案)。仕分けたセッションの解釈: 親の項のとおり fine-grained のトークンには Checks の権限が無いので、提案の前半 (Checks の read を足す) は取れない。後半は scripts/gh-token-shim/README.md の「分かっている制限」が Checks API を呼べないことと `gh run list` / `gh run view` で読むことを既に書いている (`gh pr checks` の名指しは無い)
  - `gh pr ready`(GraphQL の `markPullRequestReadyForReview`)は、普段使いのトークンの Pull requests の write では Resource not accessible になり、強いトークンでは通った。どの権限が効いたかは確かめていない。普段使いの権限は増やさず、shim で `pr ready` を書き込みに分類した
  - graphql の本文に持ち主を書いても shim は読まないので、cwd に origin が無いと既定の持ち主のトークンで送られる。`GH_REPO` で名指しすれば、その持ち主のトークンになる
- 依頼元のリポジトリの構成検査は、shim 経由の普段使いのトークンで21項目ずれ無し、終了0だった(依頼元のセッションの報告)
- 2026-11-23の仕分けで、別のリポジトリから届いた。対話シェルの設定ファイルで PATH の先頭に置く gh の shim (持ち主ごとの読み取りトークンと、書き込みだけ承認つきで昇格する仕組み) を、そのリポジトリのリリースの前段 (GitHub の設定を gh api で読む検査) と PR の作成で通した (実測)。shim を通した gh では、読み取りは fine-grained の読み取りトークンで、`gh pr create` は1Password の承認を経た強いトークンで通った。読み取りのトークンは `user/keys` を403で断り、最小権限として期待どおりだった (実測)
- 2026-11-23の仕分けで、別のリポジトリから届いた。1Password の SSH agent だけで github.com へ push する構成で、ブランチとリリースのタグの push が承認を経て通った。GitHub に登録された認証鍵の指紋と手元の公開鍵の指紋の一致で、古い鍵が残っていないことを確かめられた (実測)

## タスク

- [x] 設計書(`ISSUE-147-spec.md`)を書いて承認を得る
- [x] 実装プランを書く
- [x] shim と配線を実装する(テストつき)
- [x] bootstrap.sh で配置し、新しいシェルで `command -v gh` が shim を指すことを確かめる
- [x] 持ち主ごとの普段使いのトークンと強いトークンを発行して置く(ユーザーの操作。自分が管理していない org を除く)
- [x] 自分が管理していない org のメンバーにしてもらい、2本を発行して承認を受け、設定の `owner=` へ戻す(ユーザーの操作)
  - 2026-11-23: 発行の直後は、読み取りのトークンでもリポジトリの GET が404だった。org の承認を受けたと分かったあとは200になった (404の原因が承認待ちだったかは切り分けていない)。そのあと、その org のリポジトリで shim 経由の読み取り (リポジトリの GET、PR の一覧、コミットの CI の run の一覧) が通った。書き込みは、1Password の承認を拒否すると shim が止まり (rc 1。読み取りのトークンへは落ちない)、承認すると一時の ref の作成と削除が通った。削除のあとの GET は404で、対照の main の ref は取れた
- [x] gh の OAuth のトークンを外し、GitHub の Authorized OAuth Apps から許可を取り消す
- [x] 構成検査を実物にかけて読めることを確かめ、依頼元のセッションへ変えた内容を報告する
- [ ] 間接の書き込みを実測し、各リポジトリの workflow を棚卸しする。対話のターミナルで `op read` の承認がどのくらい続けて効くかを測る(spec の移行の順序 6 と 7)
- [ ] `gh api` で PR / Issue へ書き込む呼び出し(`-f body=...` のコメント、graphql の resolveReviewThread など)が毎回承認を求める頻度を測り、普段使いのトークンへ回すかを決める。普段使いの権限で足りるのに、spec の書き込みの判定では昇格する
- [ ] 手元のリポジトリの origin の持ち主のうち、設定の `owner=` に無いものを列挙する検査を作る。2026-11-23 に、1階層だけ走査して「その持ち主のリポジトリは0件」と誤って判断し、その前提で持ち主を設定から外した
- [ ] 設定に無い持ち主の読み取りを既定の持ち主のトークンへ落とすとき、「その持ち主のトークンが設定に無い」と stderr に一言出す。今は黙って落ちるので、private のリポジトリが「Could not resolve to a Repository」という紛らわしいエラーになる
- [ ] 普段使いのトークンで `gh pr` / `gh issue` / `gh label` の書き込みの動詞を一通り試し、通らないものを書き込みの表 (または管理の操作) へ足す。`pr ready` は表に無く read に落ちて Resource not accessible になった。同じ形の候補は `issue develop`、`pr update-branch`、`pr revert`、`issue delete` (推測)
- [ ] `gh repo list <owner>` が fine-grained のトークンで0件になる持ち主について、原因を切り分ける。REST では同じトークンで一覧が取れるので、急がない
- [ ] `.gitleaks.toml` の `git@` の allowlist を `ssh://git@<host>/` へ広げ、テストの literal を変数で組み立てずに書く形へ戻す。`.gitleaks.toml` は PUBLIC の各リポジトリへ配る canonical なので、別の PR にする。userinfo の URL(`https://<user>@github.com/...`)を解釈するかも、そこで決める

## 関連

なし(依頼元は非公開のリポジトリなので、名前を書かない)
