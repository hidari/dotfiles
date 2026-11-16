# gh と GitHub の API の一次実測

`~/.claude/references/tools.md` が名指しする、gh と GitHub の API の事実と手当て。

規範の遵守そのものには要らない。gh や GitHub の API の結果を完了や0件の根拠に使うとき、GitHub の側の設定 (Pages、移管) を変えるとき、道具の挙動が想定と食い違ったときに読む。版に依存する節には道具の版を添え、記録の無いものは「版は未記録」「報告日は未記録」と書く。

成否を持つ長時間コマンド (`gh run watch`・`gh pr checks --watch`・`gh pr merge`) の結論を専用のクエリで読む形は `~/.claude/references/observation.md` の「成否が隠れる」項が、PR のマージと squash の後の確かめ方は `~/.claude/references/git-workflow.md` が持つ。ここには書き直さない。

## run と job の状態は直後の1回で決めない

gh や jobs API で run や job の状態を読んで、完了や失敗を判断するときに踏む。報告日は未記録、gh の版は未記録。

- GitHub の jobs API が、needs で後続を持つ集約ジョブを in_progress / conclusion null と返したまま、その後続のジョブは completed / success になっていた。しばらく後に引き直すと completed / success に変わった。直後の1回の読みを「終わっていない」の根拠にしない (実測)
- 全 step が success でも job が queued や in_progress のまま返り、ランナーが拾っていないと読み違えて切り替えを一度外した。job を id で読み、steps の結果と runner_name を見る (実測)
- `gh run watch --exit-status` が途中のネットワークエラーで終了コード1を返し、直後に読んだ run は途中経過 (conclusion が空なのに集約の job だけ success) で、読み直すと success だった。終了コードが0以外のときはログの末尾のエラーを見てから、completed になった後の状態を読み直す (実測)

`--watch` の出力をファイルで読んで順序を誤読する形は `~/.claude/references/observation-shell.md` の「`--watch` の出力をファイルで読むと順序を誤読する」節にある。

## `gh run rerun --failed` の後の job id

`gh run rerun --failed` の後に、job のログや結果を読むときに踏む。報告日は未記録、gh の版は未記録。

- `gh run rerun <run> --failed` の後は、再実行していない成功の job も API 上で新しい job id が振られて見える。`started_at` が元の時刻のままなら再実行されていない。ログは新しい id で取り直さないと前回の失敗のログを読む (実測)
- 外部ミラーの不調で CI の1段だけが timeout した run を、翌日に `gh run rerun --failed` で落ちた job だけ再実行し、緑の job は同じ run の中で再利用させた (実測)。この例の記録は job id に触れていない

## ジョブのログの取得

`gh api` でジョブのログを取り出して grep するときに踏む。報告日は未記録、gh の版は未記録。

- `gh api .../actions/jobs/<id>/logs` は、ログが端末のエスケープシーケンスを含むと出力を拒んで rc 1になり、リダイレクト先は0行になる (実測)
- 拒んだときの出力が、本文の代わりに「--allow-escape-sequences を渡せ」という1行だったこともある。その出力に grep をかけると0件になり、「見ていない0件」が健全に見える (実測)
- 手当て: `--allow-escape-sequences` を付けると取れる。`gh run view <run> --job <id> --log` でも取れた (実測)

## 書き込みが失敗したときの再試行

`gh pr create` や push、merge が GraphQL のエラーなどで失敗し、再実行しようとするときに踏む。

- `gh pr create` が GraphQL の汎用エラーで失敗したとき、作り直す前に `gh pr list --head <branch> --state all` で存在を確かめると、1回目は作られず、2回目は作られたうえで assignee の設定だけが落ちていた。再実行の前に存在を、作られた後に title・body・assignee・head を個別に確かめる (実測)
- push が `fatal error in commit_refs_rules` で、同じ時間帯の squash merge が GraphQL のエラーと REST の空応答で、それぞれ続けて失敗した。githubstatus は正常だった。ブランチ名を変えた push は通り、merge は数分あけた再試行で通った。原因は特定できていない。ブランチ名が原因だと決めるには根拠が足りない (実測)
- GitHub の側の書き込みが続けて失敗したら、叩き続けずに状態 (PR が merge されていないこと、main が動いていないこと) を確かめてから、数分あけて1回だけ再試行する (提案)

## Pages の公開範囲

private のリポジトリで GitHub Pages を有効にするとき、Org やリポジトリを棚卸しするときに開く。

- Team プランの private のリポジトリで Pages を有効にすると、private のはずの中身が誰でも読める。Pages の閲覧範囲の制限は Enterprise Cloud の機能である。`keep_files: true` の deploy の action は gh-pages にある deploy の対象以外のファイルを消さないので、一度置かれたファイルは配信され続ける (実測。認証なしの読み出しが通った)
- 棚卸しの手順に、private のリポジトリで Pages が有効になっていないか (`GET repos/{owner}/{repo}/pages`) と、gh-pages に deploy の対象以外のファイルが残っていないかを入れる (提案)
- 一覧の側からは、`gh api 'user/repos?affiliation=owner,organization_member'` が返す `has_pages` を private と public に分けて数えられた。public の側が true を返すことを対照にした (2026-10-23に確かめた。gh-pages のブランチの中身は見ていない)

## リポジトリの移管

GitHub のリポジトリを REST の transfer API で organization へ移すときに開く。

- 完了の確かめ方と前後の diff: 個人アカウントの private のリポジトリを organization へ移し、前後で repo の設定 (ruleset、rules/branches、Environments と保護、secret と variable の名前、Actions の権限、webhook、deploy key、collaborator、autolink、repo 本体) を JSON に写し、id・URL・タイムスタンプ・owner など必ず変わるキーを jq の walk で落としてから diff すると、残った差分だけが読むべきものになった。transfer の POST の応答は旧い owner の full_name と null の visibility を返し、移管は非同期なので、新しい名前で GET し直してはじめて完了が分かる (実測。21ファイル中20が一致し、差分は repo 本体の4項目)
- 変わらなかったもの: ruleset の id と bypass_actors、Environment の保護とブランチの制限、secret と variable の名前は移管の前後で変わらず、rules/branches の ruleset_source は新しい owner の名前に変わるだけで、ruleset_source_type は Repository のままだった (実測)
- 変わったもの: allow_forking が true から false に変わった (org の private の fork の方針が効く)。security_and_analysis は null から6項目とも disabled を明示する形に変わり (実効は同じ)、custom_properties が空で増えたので、「設定は何も変わらない」と仮定しない (実測)
- 移す手順書には、上の確かめ方に加えて、release の一覧の API を引く action が移管の後に落ちうることを入れる (提案)

## 公開された攻撃の IOC を照合する

公開されたサプライチェーン攻撃や CI 乗っ取りの記事の IOC を、自分のリポジトリやアカウントや Org へ照合するとき、revert と run の削除で痕跡を消す攻撃の跡を探すときに開く。報告日は未記録、gh の版は未記録。

IOC (ブランチ名の形・PR のタイトル・コミットのメッセージ・workflow のファイル名と文字列・コールバックの IP・実行番号の欠け) は、gh の読み取りの API だけで、自分のリポジトリとアカウント、Org の全リポジトリへ照合できた (実測)。

### 対照を並べる

- どの検索にも、正常なら非空になる対照を並べた。緩い条件 (`chore/` で始まる) が自分の正規の PR を19件拾ったことで、検索がデータを見ていることを示せた (実測)
- IOC の0件を結論にする前に、同じパターンを合成した IOC の行に当てる陽性の対照を並べると、パターンの書き間違いによる空振りと区別できた (実測)
- 照合の手順には、自分が著者のプローブ PR の検索も入れる (提案)

対照を並べる判定そのものは `~/.claude/CLAUDE.md` の観測のカテゴリと `~/.claude/references/observation.md` の「何を何件見たか」項が持つ。

### run の番号の欠け

- 攻撃者は run とログを消すが番号は消せないので、workflow の run の番号の連番に欠けが無いことが、「見ていない」と区別できる正の証拠になる (実測)
- 欠けは workflow ごとの `run_number` で `最大 - 最小 + 1 - 件数` として数える。期間の直前の最後の run 番号とつながるかも見ないと、期間の最初の run の削除が見えない (実測)
- 実行番号の欠けは workflow の名前ではなく workflow_id で束ねないと、同じ動的ワークフローの番号を分け合う別名の run を欠けと誤読する (実測)

### 消された痕跡を追う

- revert と run の削除で痕跡を消す攻撃には、既定のブランチのコミット履歴 (revert しても残る) と、上の run の番号の欠けを見るのが効く (実測)
- 作って消されたブランチや PR は今のブランチの一覧には出ないので、`repos/{repo}/events` (90日、最大300件) の CreateEvent / DeleteEvent / PullRequestEvent の ref とタイトルで追う (実測)
- `orgs/{org}/audit-log` は Enterprise Cloud 以外の Org で404。盗まれた資格情報での操作は本人の操作として記録されるので、資格情報が無事かはアカウントの security log の画面でしか確かめられない (実測)
- 探す対象には、artifact と cache、既定のブランチの tree と workflow の中身も入れる (提案)
