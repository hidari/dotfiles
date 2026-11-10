---
status: open
---

# docs(references): 受け箱に届いた技術領域ごとの知見を references の候補として残す

## 背景

2026-10-21 に受け箱へ届いたまとめのうち、特定の技術領域に閉じた知見をここへ残す (ユーザー決定 2026-10-22: 技術領域に閉じた知見も捨てずに1本にまとめる)。どの領域にも閉じない知見は ISSUE-133 へ分けた。

どれも他のセッションの報告で、根拠は報告者の申告 (実測 / 推測 / ドキュメントのみ) をそのまま書く。dotfiles で確かめたものは項目の中で分けて書く。版や仕様は届いた時点のもので、古びる。2026-10-22に届いた7件から足した分は、各節の末尾と、新しく立てた節に置いた。2026-10-23に仕分けた5件から足した分も、各節の末尾と、新しく立てた GitHub の節に置いた。2026-10-31に仕分けた72件 (届いたのは2026-10-22〜2026-10-30) から足した分は、各節の末尾と、新しく立てた節に置いた。2026-11-01に仕分けた2件 (届いたのは2026-10-30) から足した分は、各節の末尾と、既存の項目の子に置いた。2026-11-02に仕分けた1件 (届いたのは2026-11-02) から足した分は、各節の末尾に置いた。2026-11-04に仕分けた5件 (届いたのは2026-11-02) から足した分は、各節の末尾と、新しく立てた CodeSandbox の節に置いた。2026-11-10に仕分けた受け箱の41件 (届いたのは2026-11-04〜2026-11-10) から足した分は、各節の末尾と、既存の項目の子と、新しく立てた節 (Cloudflare の2節、コンテナイメージ、GPUI、Vercel、Tauri、地理データ、Quint) に置いた。

### Cloudflare Access の後ろの環境へ繋ぐ

- Access の Service Auth ポリシーは、作って保存しただけではアプリに効かない。対象のアプリの Access の設定で、既存のポリシーとして割り当てて保存して初めて service token で 200 になった。割り当て前は token の有無によらず 302 で見分けが付かないので、ポリシーを足す前に「token あり」の 302 を対照として取っておくと、変化の原因を1つに絞れる (実測)
- Node v24 の fetch で Access の後ろへ POST するときは `redirect: "manual"` にする。既定の follow だと Access のログインへの 302 を辿ってログイン画面の HTML を 200 で受け取り、`res.ok` が真になって JSON の解析エラーに化ける (実測)
- follow の既定で 302 を辿った呼び出しは行き先の応答を返すので、呼び出し側に残った最終 status が 403 や 302 なら辿っていないと読める。秘密が漏れたかを後から判定するときに使える (実測)
- Cloudflare の入口は、クライアントが送った CF-Connecting-IP を上書きせず要求ごと扱いを変える。service token だけなら 200、CF-Connecting-IP だけなら 403、両方なら 302 (token が効かなくなる) だった。ローカルの wrangler dev で鍵を分けるためにこのヘッダを名乗る smoke は、Cloudflare の後ろの環境へは向けられない (実測)
- 2026-08-26 以降に発行された Access の Client Secret は `cfast_` + 英数字40 + チェックサム8の形式で、16進64桁という古い知識で形を検査すると誤判定する (ドキュメントのみ。手元の値の形が一致することは実測)
- 報告者の提案: Cloudflare の後ろの環境へ向ける HTTP の検査では、Access の 302 を辿らない設定を既定にする規約を検討する
- Cloudflare の Browser Integrity Check は、Python (urllib など) の既定の User-Agent を本文が `error code: 1010` の403で止め、User-Agent を明示すると200になる。smoke でこれをアプリの応答と数えると全件が偽の PASS になったので、本文が `error code: 1xxx` だけで Server が cloudflare なら edge の応答として FAIL にし、自分を名乗る UA を送る (実測。UA を変えた curl の陰性の対照を並べて初めて見えた)
- 報告者の提案: Cloudflare の手前にある API を呼ぶスクリプトは User-Agent を明示する規約にし、構文の確認だけの管理スクリプトは本番の操作の前に読み取り1本で疎通を確かめる

### Cloudflare Workers のログと API のトークン

2026-10-31と2026-11-01に仕分けた分で届いた。

- Cloudflare のアカウント所有のトークンは `/user/tokens/verify` では401 (code 1000) になり、`/accounts/<id>/tokens/verify` で active が返る。401を見て無効と判断しない (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。account-owned のトークンは `/accounts/{account_id}/tokens/verify` で status と expires_on が読め、`/user/tokens/verify` に当てると code 1000で失敗してトークンが無効に見える。verify の API で、読み取りだけでトークンの期限と状態を棚卸しできた (実測)
- Workers Logs の telemetry/query は、アカウント単位の「Workers Observability Read」だけのトークンで読めた。公式の API リファレンスは Write を要求すると書くが、Read で足りた (実測)
- Worker 単位のロール (Individual Workers) のトークンでは telemetry の query / keys / values が読めず、Metadata Read-Only では403、Editor を付けても Authentication error (code 10000) だった。ロールの docs は Metadata Read-Only で logs を読めると書き、API の reference は query に Workers Observability Write を要求していて食い違う。Workers Observability はアカウント単位の権限グループで Worker 単位のポリシーには出てこず、逆に telemetry を読めるトークンでは Worker の settings が403で、1本のトークンで両方は読めなかった (実測)
- Cloudflare 側に実際に載っている Workers の observability の設定は `GET /accounts/{account_id}/workers/scripts/{name}/script-settings` の observability で読め、wrangler.toml の解決ではなく Cloudflare 側で有効になったかをこれで閉じられる (実測)
- telemetry の /keys と /values で鍵と値の実際の綴りを先に読むと、query の0件が「見ていない0」か「本当に0」かを切り分けられた。同じアカウントの別の Worker の値が写っていれば、トークンと鍵と取り込みの経路が生きている対照になる (実測)
- invocation logs を有効にした検証環境へダミーの値を送ると、Authorization と Cookie と名前に token を含む独自ヘッダは伏せられたが、発信元の IP (x-real-ip / cf-connecting-ip)、位置の項目 (緯度経度・郵便番号・都市)、クエリ文字列を含む URL 全体は残った。Access の service token のヘッダは Worker まで届かず、cf-access-jwt-assertion は伏せられた (実測)
- 報告者の提案: invocation logs を有効にする前に、記録されるものを確かめる手順を置く。位置や IP を守る対象にするプロダクトでは切る理由になる
- Workers Logs は Worker が console に書いた行のすべてに、その要求の URL をクエリごとメタデータで足す。起動ログを切ると IP・User-Agent・位置の項目は付かなくなるが URL は残るので、クエリの付いた要求ではログを書かない形で閉じた (実測)
- 報告者の提案: 利用者のデータを残さない方針では、「何を書くか」に加えて「どの要求で行を作るか」を決める
- workers-rs の Worker で fetch が Err を返すと crate がエラーのログにして500を返し、panic! は「runtime canceled ... hung」と、ファイルと行番号つきの Rust の panic の行と、関数名つきの wasm の stack trace として写る。Durable Object の alarm と hibernation の WebSocket ハンドラの Err は type=exception で trigger つきで写る (実測。呼び出しログが無効の構成は確かめている途中)
- workers.dev が 404 と error code 1042 を返すことを「本番の Worker の workers.dev が閉じている」の確認に使っていたが、同じサブドメインで存在しない Worker の名前を叩いても同じ 404 / 1042 が返った。届かないことの証拠にはなるが、Worker が在ることや新しい版が載ったことの証拠にはならないので、版は deploy のログの Upload と Version ID で別に確かめる (実測)

### Cloudflare Logpush と DuckDB

2026-10-31に仕分けた分で届いた。

- Logpush の API でアカウント単位のデータセットを読むには、トークンの権限の行を Account にした Logs の権限が要る。Zone の Logs Write だと、トークンが active でも Authentication error (10000) になる (実測)
- Logpush の workers_trace_events の Logs は `STRUCT(Level, Message VARCHAR[], TimestampMs)[]` で届き、`console.log(JSON.stringify(...))` の1引数が Message[1] に JSON の文字列で入る。DuckDB では ::JSON から json_extract で読める (実測)
- Logpush は起動1回につき1行を書き、ログを出さなかった起動も Logs が空の行として届くので、件数の突き合わせはイベントの行で数える (実測)
- Logpush の job の GET では、絞り込みの無い job は filter の鍵そのものを持たない (実測。絞り込みのある job で返るかは公式の応答の schema に無く未確認)
- 宛先のフォルダを再帰の glob でまとめて読むと、Logpush が job の作成時に置く確認用のファイルを拾い、推論が別の形になって後の SELECT が Binder Error になる。日付のフォルダに絞って読む (実測)
- DuckDB の read_json で列の型を columns で明示すると、全行の Logs が空のファイルでも同じ型で読める。推論に任せると、空のファイルで JSON[] になり Binder Error になる (実測)
- DuckDB は外側の WHERE で json_valid を見ても SELECT 側の ::JSON を先に評価し、JSON でない文字列が1つあると問い合わせごと Conversion Error で失敗する。変換を `CASE WHEN json_valid(...)` の内側に置く (実測)
- DuckDB では `x ->> 'k' IN (...)` の IN が ->> より強く結び Conversion Error になるので、括弧で包む (実測)
- DuckDB の to_timestamp は TIMESTAMPTZ を返し、日付への変換がセッションの TimeZone に引っぱられる。UTC の日で切るなら epoch_ms から strftime し、テストで TimeZone を別の値にしてから流すと対照になる (実測)
- `duckdb -json` は文ごとに JSON の配列を出すので複数の文の出力は1つの JSON として読めず、CREATE MACRO と CREATE TABLE AS は結果を出さず CREATE SECRET は出す。1文に保つか、行頭の `[` で切って結果の数を流した文の数と突き合わせる (実測)

### Cloudflare のゾーンと Web Analytics の設定を API で読む

2026-11-10に仕分けた分で届いた。

- Web Analytics の `GET /accounts/{id}/rum/site_info/list` は、ドキュメントや推測が示す `rules[].host` を持たない。実物は「host (正規表現の文字列) と is_host_regex を持つホスト型」と「ruleset.zone_name と ruleset.enabled を持つゾーン型」の2種類で、Pages が作ったサイトはホスト型で auto_install が false だった。「Pages が管理」を示す項目は無い。API を読む前に形を決め打ちせず、実物で確かめること (実測)
- ダッシュボードで作ったシングルリダイレクトは、API では式が `(http.request.full_uri wildcard r"...")`、行き先が `wildcard_replace(...)` の形で保存されている。バルクリダイレクトのリストの source は末尾に `/` が付く。式は解析せず、実物の文字列をそのまま写して完全一致で比べるのが確実 (実測)
- あるべき設定を写す前に実物を照らすと、レジストラ移管の名残 (ゾーン内の古い NS レコード、ドメイン接続用の CNAME) がそのまま「あるべき設定」に固定されるのを防げた。公開されている NS は DoH (`cloudflare-dns.com/dns-query`) で引くと、サンドボックスで dig が届かない環境でも確かめられた (実測)

### Cloudflare Workers と Durable Objects の上限・料金・ダッシュボード

2026-11-10に仕分けた分で届いた。版と上限は届いた時点のもので古びる。

- 設計書に書き写した Workers の上限は古くなっていた。2026-11の docs では、Worker の大きさは非圧縮64MiB (Free も Paid も) で、圧縮後の上限は無い。代わりに起動時間1秒、isolate ごとに128MB のメモリ (wasm を含む)、Static Assets の1ファイル25MiB が効く。一次資料から写した数値は、日付を添えて置き、使う前に原文を読み直す (実測)
- Cloudflare の developers docs は URL の末尾に index.md を付けると Markdown の原文が取れる。WebFetch の要約に頼らず、curl と grep で上限の表を原文のまま確かめられた (実測)。Apple の docs を JSON で取る報告は iOS の節にある
- ネイティブで測った RSS は wasm の linear memory と一致しない。同じ表でネイティブの RSS が105MB、wasm の linear memory が79.5MiB だった。Workers の isolate の128MB と比べるなら、wasm 側で測った値を使う。同じデータを埋めた wasm を Node で読み、memory.buffer.byteLength を比べた (実測)。報告者の提案は、大きな地理データや静的データを Worker に埋める判断の前に、wasm の linear memory を Node で測る手順を、Workers を使うリポジトリ向けの参照に置くこと (実測)
- Durable Object の duration を「起きている時間 × 128MB」で見積もった。Hibernation API の接続しか持たない DO は、休眠の条件を満たして idle のあいだ課金されず、休眠に入る前の窓も課金されない (pricing の FAQ の明文)。この見積もりは hibernation が壊れたときの値で、攻撃の最悪値として出すと費用を桁で過大に見せる (ドキュメントのみ。検証環境の月の duration が小さいことと矛盾しないことは実測)
- ダッシュボードの Data Studio のクエリのエディタは、前に開いたインスタンスで打った文を残す。新しく打った文とつながって両方が実行された。消す文に `WHERE id = ...` を付けていたので、別のインスタンスでは0行で済んだ。回避は、毎回エディタを空にすることと、消す文に必ず主キーの条件を付けること (実測)。報告者の提案は、ダッシュボードの SQL エディタで本番のデータを消す手順を書くときは、この2つを手順の行として持たせること (実測)
- ダッシュボードの Workers の cron trigger の編集ダイアログは、「スケジュール」のタブで表せる式 (毎時N分・毎日N時) を開いて「Cron 式」のタブに切り替えると、実際の式ではなく既定値の `*/30 * * * *` を表示した。一覧の説明と次の発火時刻、API の GET .../schedules は正しい式を返した。確認に編集ダイアログを使わない (「更新」を押すと書き換わる) (実測)

### wrangler と Vite と Vitest

2026-10-31に仕分けた分で届いた。

- @cloudflare/vite-plugin の dev ではフックの throw が HTTP 200と汎用の文言になり、理由が本文にもターミナルにも出ない。preview と Worker 環境のビルドではフックが走らず、throw の前に console.error を置くと理由がターミナルに出る (実測)
- フレームワークのプラグインで mode (serve と build) によって hook の要否が変わるときは、hook の中の手書きの分岐ではなく apply のような仕組みでプラグインごと分けると、後から hook を足したときにガードの付け忘れが起きない (実測。付け忘れを防げるという効果は推測)
- vite.config.ts から src を拡張子なしで import すると、Vite 8の configLoader が警告を出す。連鎖に .ts の拡張子と allowImportingTsExtensions を付けると0件になり、Biome の useImportExtensions を override で連鎖に限って効かせると付け忘れが lint で赤になる (実測)
- vite の server.fs.deny に星2つで始めるパターンを書くと絶対パス全体に照合するので、.claude/worktrees/ や .cache/ の下の複製で dev サーバを起動すると全ファイルが403になる。プロジェクトのルートに固定したパターンにし、既定の拒否も含め直して resolveConfig の既定と突き合わせるテストを置いた (実測)
- @cloudflare/vitest-pool-workers は0.23.0で deprecated になり、@cloudflare/vitest-plugin へ改名された。旧 pool は vitest 5と組むと全テストファイルで worker の起動が SyntaxError になり、後継 (1.4.7) は vitest 4と5の両方に対応し、移行は import 元と tsconfig の types の差し替えだけだった (実測)
- 報告者の提案: 同じ構成の他のリポジトリを棚卸しする
- Workers 向けの Vitest で `*.module.css?raw` を import すると、文字列ではなく CSS Module の proxy が返る。vitest.config の `css.include` に対象を入れると文字列になった (実測)
- vitest 5が出す isolate: false を勧めるヒントは、isolate を明示的に設定すると出なくなる (実測。条件は vitest のソースで確かめた)
- vitest は既定で `.cache/` を除外しないので、`.cache/` にリポジトリの複製を置くとその中のテストまで収集し、テストの件数が303から4545に化けた。`test.exclude` に `.cache/` の配下を除くグロブを足して塞いだ (実測)。報告者の提案は、vitest を使うリポジトリでは `test.include` でテストの置き場を列挙すること。既定の全体探索のままだと、書き捨ての置き場や worktree に置いた複製の中のテストまで走る (実測)
- wrangler.toml で Durable Object の束ねを守るなら、各要素の鍵を {name, class_name} に exact で縛る。wrangler は script_name (別の Worker) とそれに付随する environment も受け付けるので class_name だけを見る検査は storage を別の場所へ向ける差分を素通しし、migration も legacy の deleted / renamed / transferred_classes は storage を消すか移すので、置ける鍵を {tag, new_sqlite_classes} に絞る (実測。鍵の意味は公式の頁で確かめた)
- wrangler dev では Content-Length を偽った要求が Worker に届かず、前段の ProxyWorker が待ち続ける。Worker 側で宣言を見て先に拒む門は手元では確かめられず、本番の経路で確かめるしかない (実測)
- wrangler dev の前段は、Worker が本文を読み残して返した直後の POST を1件落とすことがある (GET は再試行される)。後ろに別の smoke を並べるなら、捨ての POST を1件送る (実測。原因が keep-alive の使い回しというのは推測)
- 競合の探針を「繰り返しのたびに作成から始める」形で書いたら、作成のレート制限に加えて、ローカルの開発サーバの永続化された状態に残る日次の予算を使い切り、起動し直しても全部429になった。探針は作成を最小にし、状態は使い捨ての置き場 (wrangler なら --persist-to) に分けて、利用者の手元の状態を汚さない (実測)
- wrangler の pages deploy はコミットの情報を cwd の git から拾うので、作業ディレクトリを git の外に置くと Deployments にコミットが付かない。--commit-hash で渡せる (ソースとフラグの存在を確かめた)
- cloudflare/wrangler-action は lockfile を workingDirectory の中だけで探し、無ければ npm に落ちる。トークンを process.env に入れてから wrangler の有無を確かめ、無ければ install するので、install が走るとトークンのある環境で lockfile の外のコードが動く (ドキュメントのみ。pin した SHA のソースの読みで、実行はまだ)
- vitest の include の外 (無視されるキャッシュのディレクトリなど) に置いた使い捨てのテストは、何も走らず出力が空になる。空を「通った」と読まない。製品のテストの中で緑と変異の赤の両方を見て確かめ直した (実測)。上の `.cache/` の複製まで収集する項とは逆向きの事例
- rolldown (vite 8) の codeSplitting の group は、一致したモジュールを既定で1つの chunk にまとめるので、パッケージが自分で動的 import に分けたファイル (locale ごとのデータなど) まで1つに戻してしまう。group に `entriesAware: true` を付けると、読み込む側の組み合わせで分かれ、遅延ロードが戻った。付けるのはその性質のパッケージの group だけにする (実測)
- 自前の設定の型を、上流の型 (rolldown の CodeSplittingGroup) との交差型にすると、オプション名の綴りの誤りが excess property check で落ちる。自前の型にオプションを手で写す形では、型と値に同じ綴りの誤りを書くと黙って無視された (実測)
- `wrangler deploy` は cron の trigger を `PUT /schedules` で toml の一覧に置き換えるが、`wrangler rollback` は version を切り替えるだけで trigger を戻さない。rollback の後は code が古く trigger が新しい組になる (wrangler 4.127.1の dist を読んで確認、実走はしていない) (ドキュメントのみ)。報告者の提案は、Cloudflare Workers の cron を持つリポジトリの rollback の手順書に「`wrangler rollback` は trigger を戻さない。trigger まで戻すなら旧 checkout から `wrangler triggers deploy`」を書くこと。根拠は報告者が効かなかったことの2件目に挙げたもの (ドキュメントのみ)

### Node と Web の API

- Node v24.18.0 の組み込み WebSocket (undici) は `new WebSocket(url, { headers: {...} })` で upgrade 要求にヘッダを載せる。`ws` パッケージを足さずに済む。ヘッダの値は ByteString で、日本語を入れると TypeError を投げるのでプローブの値は ASCII にする (実測)
- 複数のスクリプトに共通のヘッダを足すなら、全員が import する共有モジュールで `globalThis.fetch` と `globalThis.WebSocket` を包むと、呼び出し箇所を直さずに全経路へ載り、付け忘れも構造で無くなる。テストは子プロセスに通信させ、手元のサーバが経路ごとに受けたヘッダを数える。必要な値の片方だけ渡されたら exit で止める (黙って付けないと別の失敗と見分けがつかない) (実測。最後は設計判断)
- Node で先に AbortSignal.timeout つきの fetch を起こしてから spawnSync (承認待ちなど) でイベントループを止めると、応答が届いていても戻った直後に時間切れになる。同期の待ちは、すべての非同期の時計より前に済ませる (実測。委譲先が2回とも TimeoutError を再現した)
- URL のクエリへ入力を replaceState で書くページで、値がページ自身の書いたものか外から来たリンクかを見分けるには、replaceState の state に印を載せるのが合っていた。state はリロードを越えて残り新しい遷移で空になるので、Navigation Timing より層が正しく、補助の仕組みが全部要らなくなった (実測。E2E と変異注入で確かめた)
- 印を付けるかは、書く値が開いたときの値と同じかではなく、更新の出所 (起動時の正規化か利用者の操作か) で決める。値の比較だと正規化で値が変わり、共有リンクをリロードしただけで入力を失う (実測。レビューの指摘を E2E で再現して pin した)
- 報告者の提案: URL や履歴を状態の置き場にする機能のレビューの観点に、印の出所を足す
- ページ自身の location.reload() も、ブラウザは人のリロードと同じ reload と記録するので、Navigation Timing だけでは区別できない (実測)
- `node -e '<コード>' a b` で外部スクリプトを import すると、`process.argv.slice(2)` が期待した引数にならず、全ケースが既定の分岐で走って全部同じ結果になった。引数を取るスクリプトはファイルを直接 `node script.mjs a b` で実行し、未知の引数で止まる検査を入れる (実測)
  - dotfiles で確かめたこと (2026-11-02、Node v24.22.1): `-e` ではスクリプトのパスが argv に入らず、`process.argv.slice(1)` が `["a","b"]` になる。import した側の `process.argv.slice(2)` は `["b"]` で、最初の引数が落ちる
- `document.fonts.check` は、該当する FontFace が無いと true を返すので、「フォントが読めたか」の検査にならない。document.fonts を列挙して status を見る必要があった (実測)
- CSS の `word-break: auto-phrase` は、要素の lang が ja でないと文節で区切らず、単語の途中で折り返した (実測)
- `readdirSync(..., { recursive: true, withFileTypes: true })` の `parentPath` から、ルートの長さぶんを slice してパスを組み立てると、OS の区切り文字に依存して脆くなった。`encoding: 'utf8'` で相対パスを受け取って、`split(sep).join('/')` で URL の形に直すほうが素直だった (推測: Windows では試してない。レビューの指摘を受けて直した)
- `node --test` の件数の行を `^# (tests|pass|fail)` で拾おうとしたら0行だった。今の既定の reporter は TAP ではなく、件数の行の頭が `ℹ` になっている。grep が空を返したのを「件数が出ない＝失敗」とも「緑」とも読まず、出力の末尾をそのまま見て確かめた (実測)

### Web Share API

2026-10-31に仕分けた分で届いた。

- Playwright Test の headless Chromium には navigator.share が無いが、Playwright MCP が動かす macOS の本物の Chrome には有る。MCP の実ブラウザで共有シートの無い環境を想定すると前提が外れて誤ってバグに見えるので、Navigator.prototype から消す init script で無い環境を作る (実測)
- 報告者の提案: ブラウザの API の検証手順に、この差を注記する
- navigator.share の title は共有の中身にならない。WebKit は title をリンクのプレビューの見出しにだけ使って共有先には url だけを渡し、Android の Chrome は title を EXTRA_SUBJECT / EXTRA_TITLE にだけ入れて本文は text + url になるので、タイトルを届けたいなら text に入れる (両方のソースの該当行を読んだ。実機は未確認)
- iOS の共有シートの「コピー」は text があると text だけを取る (WebKit の未解決のバグ)。text にタイトル、url を別に渡すとコピーで URL が落ちるので、text に「タイトル + 改行 + URL」をまとめて url を渡さない形にすると、どの経路でも両方が残る (ドキュメントのみ。バグの記述と第三者の実測で、現行の iOS では未確認)
- Chromium の Web Share は url が空なら URL の検査を飛ばすので、url を渡さなくても拒否されない (ソースを読んだ。実行はしていない)

### Python

2026-10-31と2026-11-01に仕分けた分で届いた。

- Python の送受信の失敗を URLError と TimeoutError の列挙で受けると、応答の読み取り中の切断 (ConnectionResetError や http.client の例外) が文脈なしで抜ける。OSError と http.client.HTTPException で受ける (推測)
- Python の str の正規表現では `\b` や `\w` が和文の文字も語の文字に数えるので、和文に挟まれた数や、和文が直に続く ISSUE-<数> を読み落とす。re.ASCII で数える (実測、変異で確認) か、bytes の正規表現で `(?<![0-9A-Za-z])` と `(?![0-9A-Za-z])` を明示する (ドキュメントのみ)
  - 2026-11-01の仕分けで、別のリポジトリから同じ型の報告が届いた。「ポート<数>番」を str の `\w` の境界で取りこぼし、bytes の `[0-9A-Za-z]` の境界で拾えた (実測)。同じ報告の、一括置換の前後のハッシュの突き合わせは ISSUE-133 の「作業の規範」節に置いた
  - dotfiles で確かめたこと (2026-11-01、Python 3.15): `ポート5432番` に対して、str の `\b5432\b` と `(?<!\w)5432(?!\w)` はどちらも0件、bytes の `(?<![0-9A-Za-z])5432(?![0-9A-Za-z])` は1件だった。上の項の bytes の手当ては、ここで実測になった
- Python の shlex は既定で語の途中の `#` からコメントとして捨てる。bash と zsh は語の頭の `#` だけをコメントにするので、コマンドの解析では `commenters = ""` にする (実測)。仕分けたセッションの解釈: dotfiles の apm-install-guard もコマンドを分割して判定するので、ISSUE-124 の誤検知の調査で当てはまるかを確かめるとよい

### iOS

- iOS の URLSession も既定では 302 を辿る (実測)
- iOS の URLSessionConfiguration の httpAdditionalHeaders は URLProtocol の stub に届く要求にも載る (作成と GET の2経路で確認)。組み立て役で構成を1つ作って各通信クラスへ渡せば通信クラスを触らずに済む。WebSocket の upgrade に載るかは未確認 (実測)
- シミュレータのアプリの通信の成否は、アプリにログを足さずに CFNetwork のログ (`Task ... received response, status 101` など) で読める (実測)
- Xcode 27 系には Simulator.app が無く、シミュレータの画面は Xcode の `Contents/Applications` にある DeviceHub.app で開く (実測)
- URLSession の task に `task.delegate` を据え、その delegate が `willPerformHTTPRedirection` を実装しなければ、redirect の判断は session の delegate へ回る。WebSocket の task でも、開いた・メッセージ・完了の出来事は task の delegate に届いた。session の delegate を状態の無い共有の1つに固定し、出来事を受けたい側を task の delegate に下げると、session を作る口を1つに閉じられる (実測、iOS 26のシミュレータ)。ただし redirect の判断は task の delegate でも上書きできるので、口を閉じても性質は閉じない (ISSUE-88 の INS-23)
- Apple のネットワークのログ (CFNetwork) は、WebSocket のプロトコルの ping の送信を記録しない。送ったことの証拠はクライアントのログからは取れないので、テストでの送信の確認と、対照付きの生存の組で主張するしかない (実測)
- iOS シミュレータの UI テストが1本落ちると、その直後に locationd へ位置のシミュレーションを止める要求が届き、実行の頭で1度だけ `simctl location set` した位置が消えた。全部が通る実行では、この要求は実行の最後にしか来ない。UI テストの setUp でテストごとに `XCUIDevice.shared.location` を置き直すと、変異で狙ったテストだけが赤になった (実測)。要求の送り手は xcodebuild と報告者は推定しており、ログは daemon-side としか言わない。巻き添えの赤の切り分けの手順は ISSUE-88 の INS-77
- 使い捨てのシミュレータ (実行のたびに作って消す) で原因を探るときは、テストを回すコマンドの直後に同じ端末で `simctl spawn ... log show` を取るラッパーを噛ませると、端末が消える前に locationd とアプリのログを残せた。通る組と落ちる組のログを並べると、provider の違い (wifi か simulated か) と停止の要求の時刻で差が一目で見えた (実測)
- 失敗の時点の画面は xcresult の添付 (App UI hierarchy のテキスト) から読めたが、xcodebuild のログ本体には階層が出ない。失敗の文言だけでは画面がどこで止まったかが分からず、添付を export して初めて開始の失敗の文言が見えた (実測)
- Privacy Manifest で理由が要る API の当て先は、ソースでも静的ライブラリでもなく、リンク済みの .app の実行ファイルの `nm -u`。リンカの dead strip の後に残る import だけが見え、静的にリンクした Rust の std が引く `fstat` もここで初めて見えた (実測)。報告者の提案は、iOS の Privacy Manifest を扱う手順があれば、棚卸しの当て先を「リンク済みの実行ファイルの import」と明記すること。Rust や C のライブラリを静的リンクするアプリでは、ソースの grep では必ず漏れる (実測)
- Rust の静的ライブラリをリンクした Swift アプリでは、Swift の `#available` が呼ぶ `__isPlatformVersionAtLeast` を Rust の std が弱い定義で提供し、compiler-rt の版に勝つ。その中で OS の版を読むために `fstat` まで届くので、panic の設定を変えても外れない (実測)
- 見つけた import の呼び出し元は、Rust のツールチェーン付属の `llvm-objdump -d` で逆アセンブルし、`otool -Iv` で得たスタブのアドレスへの `bl` を数えると辿れる。Release でも関数ラベルが残っていた (実測)
- 理由が要る API の突き合わせは、シミュレータ向けではなく実機向けの Release に当てる。Rust の std は target_abi でコード経路が分かれ、実機向けの実行ファイルにだけ import が1つ多かった。実機向けは `xcodebuild build -destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO` で署名なしに組める (実測)
- Apple の Bundle Resources の頁は `https://developer.apple.com/tutorials/data/documentation/<path>.json` で JSON が取れる。要約役のモデル越し (WebFetch) だと区分ごとの API と理由コードの一覧が落ちたが、JSON を自分でパースすると全部取れた (実測)。Cloudflare の docs の原文を index.md で取る報告は「Cloudflare Workers と Durable Objects の上限・料金・ダッシュボード」節にある
- `devicectl device process launch` は呼び手の環境の DEVICECTL_CHILD_ を前置した変数を起動したプロセスへ写す (simctl の SIMCTL_CHILD_ と同じ形)。`-e/--environment-variables` は値を引数の JSON に載せるので ps から見え、しかも DEVICECTL_CHILD_ 側を上書きする (実測 / ドキュメントのみ: 上書きは --help の記述)。起動時だけの secret をこの形で実機へ渡す手順を組んだ。報告者の提案は、実機へ secret を渡す手順の雛形を作るなら DEVICECTL_CHILD_ を既定にし、`-e` を使わないこと (実測)
- `xcodebuild -exportArchive` の行だけに `PATH="/usr/bin:$PATH"` を前置すると、Homebrew の rsync が入った Mac でも export が通った。Homebrew の rsync 3.5.1が先に見つかると「exportArchive Copy failed」で落ち、理由は .xcdistributionlogs の IDEDistributionPipeline.log の rsync の行にしか出ない。署名とプロファイルの作成はその前に済んでいるので、アカウント側の問題に見える (実測)。報告者の提案は、macOS で Xcode の export を回すレシピやスクリプトを持つリポでは、export の呼び出し行に PATH の前置を入れるか、少なくとも Copy failed のときに xcdistributionlogs の Pipeline を読む手順をコメントに残すこと (実測)
- strip は archive の段で起きる。archive の実行ファイルは定義済みの記号が2本で export の後も同じ、STRIP_INSTALLED_PRODUCT=NO で archive すると export を通っても数万本のまま残った。配布の形を検査するなら archive を通った成果物を見る (実測)
- App Store Connect にアプリのレコードが無い状態でも、自動署名の exportArchive (method app-store-connect, destination export) は通り、App Store 向けのプロファイルを作った (実測)
- 実機向けの署名を、xcconfig の SDK 条件付きの設定 (`CODE_SIGN_STYLE[sdk=iphoneos*] = Automatic` と `DEVELOPMENT_TEAM[sdk=iphoneos*]`) で自動署名にし、シミュレータの ad-hoc と共存させた。Xcode の画面でチームを選ぶと pbxproj に書かれて xcconfig を迂回するため (実測)
- Keychain のアクセスグループの解決は、書き込みの成否ではなく、保存した項目の `kSecAttrAccessGroup` を `kSecReturnAttributes` で読み戻して値で見ると確かめられた。entitlements のグループを別名へ変える変異では、値を見るテストだけが赤になり、書き込みと読み戻しの緑は証拠にならなかった。host を持つテストを実機で回して Team ID の解決を確かめた (実測)。報告者の提案は、iOS の entitlements (Keychain のアクセスグループ、App Groups など) を検証するテストは、書き込みの成否ではなく保存した項目の属性の値で見る形を推奨として残すこと (実測)。pin の作り方の面は ISSUE-88 の INS-19 と同じ族 (仕分けたセッションの解釈)
- 実機の UDID (xcodebuild の destination に渡す形) は `xcrun xctrace list devices` で引けた (実測)
- `xcodebuild -allowProvisioningUpdates` だけでは未登録の端末を登録せず、「Device isn't registered」で落ちる。`-allowProvisioningDeviceRegistration` を併せて渡すと登録とプロファイルの作成まで進んだ (実測)
- `-only-testing` は実行を絞るだけで、スキームの全テストのターゲットはビルドされる。自動署名では UI テストの runner の分まで署名が要る (実測)
- シミュレータ向けの `*-Simulated.xcent` は Xcode にアカウントがある手元では実際の Team ID を持ち、シミュレータで緑でも実機の署名の証拠にならない (実測)。上の実機向けの Release に当てる項と同じく、シミュレータは実機の代わりにならない

### React と E2E (Playwright)

- React Router の `navigate(..., { viewTransition: true })` では URL が先に変わり、新しい loader データの commit と、ref を effect で更新する「最新のコールバックを ref に持つ」hook の差し替えが後から来る。E2E で URL の変化だけを待って次のキーを押すと、古いデータのハンドラが走って空振りする。高負荷のホストでだけ表に出た (実測)
- hydration の完了の印 (html の data 属性) は full goto と reload にしか効かず、client 遷移の後は true のまま残る (実測)
- 冪等な操作は、`toPass` の中で「押す → 短い timeout で結果を待つ」を繰り返すと client 遷移の直後の取りこぼしを吸収できる。押しすぎても状態が壊れないことが条件 (実測)
- 報告者の提案: E2E のガイドに「client 遷移の後の操作は URL の変化を準備完了の印にしない。冪等なら toPass で押し直し、冪等でなければ遷移先の DOM の変化 (データに依存して出る要素) を待つ」を足す
- アプリが dispatch するカスタムイベントを `addInitScript` で DOM の data 属性へ写し、locator で待つと hydration の完了を待てた。tsconfig が DOM の型を持たない E2E では、`addInitScript` に content の文字列で渡すと型エラーを避けられる (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。e2e の tsconfig に DOM の lib が無いと、`page.evaluate` に渡した関数の中の `window` が型エラーになる。文字列の式で渡すと型の文脈のずれごと避けられた (実測)
- 開発サーバの React StrictMode では、捨てられる1回目の effect も localStorage に書く。cancelled フラグを書き込みの後でしか見ていない hydration は、イベントの発火回数と書き込み回数が一致しない (推測。コードを読んだだけ)
- UI の性能の上限を決めるとき、開発機の値に推測の倍率を掛けず、Playwright から CDP の `Emulation.setCPUThrottlingRate` (4倍と6倍) を掛けて独立プロセスで測った。長さの順を昇順と降順で入れ替えても中央値がほぼ動かないことで実行順の影響も確かめた (実測)
- Playwright で応答を遅らせるときは、要求ではなく応答を握る (`route.fetch()` で取ってから待ち、`route.fulfill({ response })` で返す)。要求を握ると DB の問い合わせ自体が後ろへずれ、新しい値が返って競合が起きない (実測)
- 競合を再現するために応答を握るときは、固定の時間で遅らせず、競合の相手の操作 (作成の RPC の応答) が返るまで握る。ホストが重いと固定の時間に操作が収まらず、製品が正しくてもテストが赤くなる (実測。レビューの指摘から採用)。「古い応答が届いた」の判定は時刻ではなく応答の本文で行う (ISSUE-88 の INS-20)
- 閉じた details の中身は、`getByRole` の既定 (隠れた要素を除く) から外れる。中に live region があると、ページ全体の role の数を数える検査が別の理由で赤くなる (実測)
- chromium では、disabled にしたボタンからフォーカスが body へ落ちた。送信中のボタンを aria-disabled とハンドラの先頭の早期リターンへ切り替えるとフォーカスが残る (実測、Playwright の chromium)。切り替えの pin については ISSUE-88 の INS-19
  - 続報 (2026-10-23の仕分け、実測): 原因は HTML の focus fixup rule で、enabled に戻してもフォーカスは返らず、止めるのが1 microtask だけ (同期のダウンロードの直後に戻す) でも落ちた。aria-disabled はクリックも Enter も止めないので早期リターンが要る。止める状態の書き込みと読み出しを1組の関数にまとめると、見た目と実際の止まり方が食い違わない
- 同期に済む処理を待つあいだ (async 関数が await 無しで返り、解決済みの Promise の then が戻すまで) は1 microtask しかなく、テストの側からは観測できない。その処理が同期に呼ぶ API (ダウンロードの a 要素の click など) を `addInitScript` で包み、その中で `queueMicrotask` を積むと、呼び出し側が止めたあと、then が戻す前に走る (FIFO の順)。そこで状態を記録し、もう一度の操作を送れる。変異3種で狙った行が赤になった (実測)。そこから送る2回目の操作の形は ISSUE-88 の INS-27
- Playwright の実行を1つのシェルで順に連ねると、後の実行が `test-results/` を消すので、先の実行の失敗の trace や screenshot が残らない。失敗しうる実行ごとに `test-results/` を別の場所へ写すか、`--output` を分ける (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。Playwright は実行のたびに outputDir (既定の test-results/) を消すので、落ちたテストを単独で流し直した時点で、直前の全件実行の trace・スクリーンショット・error-context が消えた。流し直す前に test-results/ をリポジトリ内の書き捨ての場所へ複製しておくべきだった (実測)。報告者の提案は、E2E の失敗を調べるときの手順に「再実行の前に test-results/ (または playwright の outputDir) を退避する」を入れること。単独の再実行は再現性を見る最初の一手になりやすく、そのたびに一次の証拠が消える (実測)
- ESLint の prefer-const は、宣言のあとで1回だけ代入される `let` を、そのあいだにクロージャから読まれていても「const にできる」と報告する。クロージャへ渡す印を小さなオブジェクトのプロパティにすると通る (実測)
- 画面に出ない失敗の種類を文言の表から型で除く (Exclude) と、表の死に項目、一致を縛るテスト、E2E の特例がまとめて消え、網羅はコンパイラが強制する (実測)
- 「Enter で遷移しない」を E2E で見るとき、press は遷移を待たず toHaveURL は最初に一致した時点で通るので、直後の URL の検査は遷移の前に緑になりうる。テストの最後で URL をもう一度見ると、直後の検査を外した変異も末尾の検査だけで赤になった (実測)
- 送信しない UI を form から search 要素へ移すと、要素の種類に結び付いた型ガード (HTMLFormElement) が Progressive Enhancement を黙って no-op にする。E2E を移行の前に足し、同じ spec を移行の前後の両方に当てて緑を確かめてから移す (実測)
- Playwright の reporter に json を常設して .cache/ へ出すと、実行されたテストの ID の集合をいつでも取れる。PLAYWRIGHT_JSON_OUTPUT_NAME は json の reporter が有効なときしか効かない (実測)
- test.use のスコープのために無名の test.describe を使うと、テストの ID とタイトルのパスに空の階層が入る。名前を付けると消える (実測)
- Playwright Test では `test.use({ hasTouch: true, isMobile: true })` だけで、matchMedia を差し替えずに本物の `(pointer: coarse)` が true になり、タッチ端末の分岐を実判定のまま踏める (実測)
- 着手の前に一時的な spec で環境の能力 (pointer の種類、navigator.share / canShare / clipboard の有無、secure context) を console に出して測り、消してから本実装に入ると、E2E のスタブに何を入れるかが先に決まる (実測)
- Playwright の page.clock.install() だけでは時計は実時間でも進み、止まるのは runFor の実行中だけなので、install のあと pauseAt で止めないと、短い余裕を測る検査が遅い環境で揺れる (playwright-core の実装を読んで確かめた)
- page.clock.install は performance も偽物にするので Navigation Timing の記録が空になり、時計を入れた E2E では機構を外しても緑になった。読み込み方に依存する機構は、時計を入れずに確かめる (実測)
- 報告者の提案: page.clock を使う E2E は pauseAt を既定にし、読み込み方に依存する機構は時計を入れずに確かめることを E2E の規約に足す
- E2E が spec どうしで状態を共有していないことは、db-reset を挟まずに全件を2回続けて流して確かめた。1回目の緑は spec の実行順に助けられていただけだった (実測)
- picture の source を prefers-color-scheme で切り替える E2E で、切り替えの途中は img.currentSrc が空になり、`new URL("")` が投げて poll ごと落ちた (固定コンテナの Chromium で1回だけ再現)。空のときは空を返して poll に待たせると、20回繰り返しても落ちなかった (実測)
- vite preview は既定で dist に無いパスにも index.html を200で返す (SPA fallback)。本番の静的ホスティングが404を返す構成では E2E が404の振り分けを検証していないことに気づきにくく、404ページの smoke はステータスでは判定できないので /404.html を直接開く (実測)
- Playwright の auto fixture で外部オリジンを空の200で返し、console の error と warning、pageerror、4xx/5xx、requestfailed が0件であることをテストの終わりに検査すると、どの E2E も smoke を兼ねる (実測。abort を使うと失敗した要求として console に出る点は試していない)
  - 2026-11-10の仕分けで、別のリポジトリから、4xx を数える fixture の穴を塞ぐ報告が届いた。fixture に加えて `naturalWidth > 0` を見る確認を足した。200で返ってきても描画できない画像 (XML として壊れた SVG) は fixture では見えなかったが、この確認で捕まえられた (実測: 壊した SVG を配信して、足した確認だけが赤くなった)。報告者の提案は、E2E の fixture が見ているのが4xx だけなら、画像を載せるページでは `naturalWidth` の確認を並べるのを既定にすること (実測)
  - 2026-11-10の仕分けで、さらに別のリポジトリから同じ型の報告が届いた。「サーバーへの取得が失敗したら気づける」を固定するには、画面の文言ではなく、アプリが失敗のたびに出す `[scope] ... failed` の console の警告が0件であることを auto fixture で断言する形が効いた。取得のフィルタの構文を壊す変異で、狙った断言 (`expect(warnings).toEqual([])`) が赤になることを確かめた (実測)。報告者の提案は、E2E を作る手順に「取得の失敗は console の警告0件の auto fixture で断言する」を足すこと (実測)。同じ提案の後半は Supabase CLI の節の Realtime の項に置いた
- E2E の中の page.evaluate で console.log してもテストランナーの標準出力には出ないので、判定の戻り値に診断の文字列を載せ、失敗メッセージの Received で読んだ (実測)
- 共有の E2E fixture で requestfailed を検査していると、幅を変えたときにブラウザが srcset の候補を選び直して画像を取り消し、負荷時だけ net::ERR_ABORTED で落ちる。取り消しは理由 (errorText) で免除して記録に理由を入れ、免除の範囲は route.abort で pin して fixture の値をテストで受けて直接見る (実測。約90回に3回の揺れが0回になった)
- 自動操作のブラウザ (CDP で操作中の Chrome) では Cloudflare Turnstile が検証を拒む。Turnstile を通る経路の確認は人の普段のブラウザで行い、結果はサーバのログで確かめる (実測)
- 本番でブラウザ自動化の smoke を回すとき、route でバックエンドの表への書き込みを abort して止めた件数をログに出し、前後で読み取り専用のスナップショット (件数と digest) を比べると、画面を開くだけで書き込む経路があっても書き込みが残らないことを機構と数で言えた (実測。止めた件数は0。他のリポジトリでの効果は推測)
- 報告者の提案: 本番の smoke の手順書の標準にする
- dev サーバ (vite の dev モード) に向けた E2E を全件・並列で流すと、毎回違うテストが1〜2本落ち、単独では緑だった。ログの時刻の突き合わせは、複数の実行が1本の backend ログに混ざって収束しなかった。失敗した回だけ trace を残す設定で流すのが筋 (実測)。その設定で原因まで辿れたかは報告に無い
- React Router v7 (7.18.2) のフレームワークモードで、lazy route discovery (既定) の窓に遷移の打ち消しがあった。未発見のルートへの遷移が navigation を loading にしてから manifest を待ち、その間に別の fetcher の action が終わると、revalidation が遷移を abort して古い matches のまま URL だけ遷移先で確定させる (中身は元のページか catch-all の404)。`routeDiscovery: { mode: 'initial' }` にすると消えた。ルート数が数十なら、最初に配る量の増加は数KB (gzip で約4.7KB) (実測)
  - 機序は、1/3回だけ落ちる E2E の失敗した回の trace (操作・コンソール・ネットワークを、コンソールの ISO 時刻で壁時計へ揃えて1本の時系列に並べたもの) と、ライブラリのソースの読解で追った (実測)
  - 再現テストの前提の pin は ISSUE-88 の INS-79
- 遅らせる `page.route` の応答をテストの中で待たないと、テストが早く終わったときに後片付けの後で要求が届き、次のテストの最初の SSR が30〜67秒止まった。遅延を入れる route は、応答をテストの終わりまでに必ず待つ (実測)
- 外部 CDN の script を読む経路のテストは、`addInitScript` でグローバルを先置きして読み込みを短絡させるのではなく、CDN への要求を `page.route` で受けて同じ stub を定義する JS 本文で fulfill すると、script の注入から load、グローバルの判定までの実経路を残したまま外部依存だけを外せた。stub の関数を `fn.toString()` と `JSON.stringify(token)` で即時実行の本文にすれば、`addInitScript` 版と中身を1か所に保てる (実測)
- 実ブラウザの閲覧者で「接続が開いてから閉じるまで」を測るため、ページに入る前の初期化スクリプトで WebSocket を包み、ページ自身の Date.now() で open と close を記録した。アプリのタイマー判定と同じ時計・同じイベントで測れる (実測)
- 境界の閾値 (N 秒続いたら成功と数える) を実測の切断時刻と比べると、切断がちょうど閾値の上に乗っていて両側に落ちていた。数回に1回だけ壊れる形で、閾値を切断の時刻から十分に離すのが直し方だった。閾値を決めるときは、経路が切る時刻を観測系の時計で測ってから置く (実測)。同じ報告の、再開の処理を pin する前提は ISSUE-88 の INS-81
- Playwright の routeWebSocket で、サーバへ繋がずにハンドラの中ですぐ close すると、code を渡してもページが受ける close code は1006になった (chromium と webkit で実測)。close code で分岐する実装を、code を指定した close で試すテストは、指定が届いていない前提で読み直す。推測で「既定の close は1000」と書いた前提が誤っていた (実測)
- 「取得中なら何もせず返る」ガードを持つ関数を、呼ぶ側が「取ってもらえた」前提で印を消しながら呼ぶと、要求が黙って消える。ガードに弾かれたときは「終わった後にもう1回」の印を立て、関数の finally で消費する形で塞いだ。取得を遅らせる route で並びを作る E2E で、修正の前は赤、後は緑を確かめた (実測)
- vite 8.0 → 8.1で、dev サーバーの hydration が load イベントより後にずれ込むようになった。Playwright の page.goto は load までしか待たないので、直後の fill が React のハンドラが付く前に届き、controlled input は DOM に値が入っても state が空のまま (送信ボタンが有効にならない)。8.0では間に合っていたので潜在していた競合が表に出た形。full goto のあとは hydration の印 (html の属性など) を待ってから操作する (実測)
- Playwright の page.evaluate に型引数つきのジェネリックな関数を渡すと、引数が Unboxed<A> に包まれて型が合わない。値は JSON の文字列1本で渡す形にした (実測)
- Playwright の版を上げたあと、手元のブラウザを入れ直さずに E2E を回すと、全件が「Executable doesn't exist」で落ちる。headless shell の revision が変わるため。ブラウザを入れるレシピを打ち直せば直る (実測)
- 依存の自動更新の PR で jsdom を30.1.1 → 30.1.3に上げたら、ダイアログの初期フォーカスのテストが1件落ち、原因をリリースノートと react-dom のソースと実ブラウザで切り分けた (実測)。React 19の autoFocus は DOM に autofocus 属性を出さず、commit の layout の段階で focus() を呼ぶ。`<dialog>` を useEffect の中で showModal() するコンポーネントでは、focus() がまだ閉じた (display: none の) dialog の中で呼ばれて捨てられ、showModal() が dialog の最初のフォーカスできる要素 (ヘッダの閉じるボタンなど) へフォーカスを置く。直し方は showModal() の直後に印 (data 属性) の要素へ focus() する helper を1か所に置き、直呼びを構文木の配線テストで禁じる形 (実測)。報告者の提案は、React と `<dialog>` を使うリポジトリでは、ダイアログを開く処理を1つの helper に寄せ、開いた直後のフォーカスを autoFocus ではなく showModal() の後の focus() で置く規約を持つこと (実測)
  - jsdom は30.1.2から display: none の要素への focus() を拒む (リリースノートに明記)。この更新で落ちたテストは、テストの環境が実ブラウザに寄ったことで既存の製品の不具合が見えた形だった。依存の更新でテストが落ちたら、テストを直す前に同じことが実ブラウザで起きるかを測る (実測)
  - jsdom の dialog の polyfill (開閉だけを再現するもの) は実ブラウザの showModal の初期フォーカスの処理を持たないので、ユニットテストでは仕組み (helper が印へ focus を呼ぶか) を見て、実ブラウザの初期フォーカスは E2E の toBeFocused で見る形に分けた。印を外す変異で E2E が赤になることを確かめた (実測)
  - 入れ子の dialog がある画面では、`dialog.querySelector('[data-autofocus]')` が内側の閉じた dialog の印を文書順で先に拾う。`closest('dialog') === dialog` で自分の直下の印に絞る (実測)
  - 破壊的な操作の確認ダイアログで、確定のボタンに autoFocus が付いていた。元々は効いていなかったので害が無かったが、初期フォーカスを直すと開いた直後の Enter 1回で実行されるようになる。直す前に、印の先が破壊的な操作でないかを1本ずつ見る必要があった (実測)
- React の hook で「親が hook を持ち、子の passive effect から要求の関数を呼ぶ」形では、世代 (中断の単位) を effect で作ると、子の effect が先に走って要求が黙って捨てられる。世代を要求の関数の中で遅延して作り、キーの記録を layout effect に置くと塞がった。タスクのレビュー役が React の effect の順序から推論で指摘し、子の effect から呼ぶテストで固定した (実測)
- React の Drawer のように閉じていても子を描く部品の中の useQuery は、開くボタンを無効にしても走り続ける。権限で拒まれる読み取りは useQuery の enabled で止める必要がある (ソースの読みのみ)
- base_url が絶対 URL の静的サイトの E2E を、サーバーを立てずに Playwright の `context.route` で本番のオリジンを横取りし、手元のビルドの出力に `_headers` のヘッダーを付けて返す形で組んだ (実測)。この形で見えたこと:
  - Chromium の起動引数 `--host-resolver-rules=MAP * ~NOTFOUND` で名前解決を潰すと、横取りしたナビゲーションは200のまま、横取りから漏れたリクエストは即座に失敗する。横取りが外れて本番を開いて緑になる経路を塞げる (実測)
  - `page.route` は登録の順番によらず `context.route` より優先される。対照のページを同じヘッダーの経路で差し込むのに使える (実測)
  - `page.request` / `context.request` / `request` fixture (APIRequestContext) は `context.route` を通らず、実際の DNS とネットワークへ出る。横取りした本番のオリジンに使うと本番を叩いて本番の200で緑になるので、使わないことをテストで pin した (実測)
  - `meta` の `content` 属性を全部 URL として解決すると、viewport や description の値が同じオリジンの相対パスに化けて404になる。ベース無しで URL として読めるものだけを取る (実測)
  - 応答の CSP の扱いは「SVG と CSP の検査」節、CSS が当たっていることの番兵は「Playwright でスタイルと配置を測る」節、Test Agents の生成物の扱いは「Playwright Test Agents とブラウザの MCP」節に置いた
- `package.json` に `"type": "module"` が無いと、Playwright のテストの TS は CommonJS として読まれ `import.meta` が SyntaxError になる (実測)

### Playwright でスタイルと配置を測る

2026-10-31に仕分けた分で届いた。

- 数百ms の CSS アニメーションの存在を E2E で確かめるときは、開く操作と getAnimations() の数え上げを1回の evaluate の同期処理に収める。終わったアニメーションは消えるので、別の呼び出しで poll すると負荷次第で0件になる (実測。Firefox で40回に1回の失敗が、4ブラウザ×40回で全件緑になった)
- 同期処理で閉じて開き直すときは、間に getComputedStyle(el).display などでスタイルの再計算を挟む。挟まないと再計算がまとまって開き直しにならず、前回のアニメーションの残りを数えるだけになる (実測。500ms 待つ変異で、挟んだ版はガードを外すと赤になった)
- E2E で CSS 変数の解決後の色と比べたいときは、対象と同じ親の中に `style.color = "var(--x)"` のプローブの要素を足して computed の色を読み、すぐ消す。ライトとダークに自動で追従する (実測)
- CSS の値は正規表現で読む代わりに E2E で getComputedStyle を測ると、カスケードやメディアクエリの解決をブラウザに任せられる。テーマは「属性 × OS の配色」の組で状態を作り、AA を満たすかの検査ではダークの色の取り違えを捕まえられず、状態どうしの色の一致の検査だけが捕まえた (実測、変異で確認)
- Chromium はサポートしない CSS プロパティ (-webkit-touch-callout など) をパースの時点で捨てるので、computed style にも CSSOM にも現れない。ブラウザで確かめられないものだけは、宣言を見るユニットテストに残す (実測)
- 色や transform を測るとき、reduced-motion で transition を0.01ms にしても状態を変えた直後の computed style は前の値を返すことがあり、負荷時は描画を2回待っても残った。前の値が合格する値だと測り損ねても緑になるので、`transition: none !important` を差し込み、状態ごとに値が変わったことも対照として見る (実測)
- E2E で hover の色を測るときは、「hover の前後で色が変わったこと」を測る helper の中で確かめるようにした。平常時の色を読み、それがたまたま基準を満たして通る形を、hover の対象を足すたびに書き忘れることがなくなった (実測)
- ホバーの合図を「計算済みの背景色が乗せる前と違う」で pin したら、明るいテーマで地との差が各チャンネル3しかなく、目では見えないまま緑だった。下地に重ねた画素の差の大きさ (12以上) を明暗の両方で測る形に変えた (実測)
- color-mix() の計算済みの値は rgb() ではなく `color(srgb 0〜1 / a)` の形で返る (Chromium)。数値を正規表現で抜いて0〜255とみなすと片方のテーマだけ偶然通るので、canvas に下地と色を重ねて塗り、getImageData の画素で比べると書式に依存しない (実測)
- インライン SVG の表示属性に `stroke="var(--x)"` のように CSS 変数を書くと、ライトとダークのトークンの切り替えに追従する。Chromium / Firefox / WebKit の E2E で、computed の値が両モードで違うことを確かめた (実測)
- ページの上の余白を各ページの最初のブロックに書くと、狭い幅で縮める指定が1つのブロックにだけ足されてほかが取り残される。余白は全ページ共通のコンテナに1回だけ持たせ、E2E は「上の余白の合計がページ間で同じ」「狭い幅では小さい」を値を書き写さずに見る (実測。変異5種で赤)
- 下端をそろえる UI の調整では、行の箱ではなく文字の baseline を基準にし、ink の下端を canvas の measureText (actualBoundingBoxDescent) と inline-block の probe の baseline から実測して px を合わせた。行の箱の下端は行間で字から離れるので、flex の end ぞろえでは数px ずれる (実測)
- 見えないラベル (position: absolute で視覚的に隠すクラス) と見える文字をボタンの中で隣り合わせると、absolute のラベルの computed display が block になり、Chromium のアクセシブルネームの計算が前後に空白を入れる。HTML に空白を書かなくても「ラベル 本文」になり、空白を消す変異を入れても toHaveAccessibleName の検査は緑のままだった (実測)
- 見出しの横に置く小さな操作部品は、absolute で重ねるのではなく見出しより前の DOM に置いて float にすると、幅のしきい値を持たずに「並べば同じ行、並ばなければ見出しが下の行へ」を実現できる (実測。幅320の重なりの E2E が赤から緑になった)
- document.elementFromPoint で「上に何があるか」を判定する E2E は、対象が画面の外にあると null を返し、「隠れている」と同じ失敗に見える。判定の前に scrollIntoViewIfNeeded で対象を画面へ出し、画面に入るかは別のテストに任せた (実測)
- 報告者の提案: helper は null (画面の外) と「別の要素が上にある」を別の値で返し、切り分けを一度で済ませる
- ブラウザで見せた見本が Web フォントを読まずシステムのフォントで描かれ、本番より太く見えた。見本の段階から本番と同じフォントを読ませないと、見た目の合意がずれる (実測)
- 画面を操作する道具が無いセッションで、デスクトップアプリの UI 部品の見た目を確かめるため、開発用の vite dev server が配る ignore 済みのディレクトリにハーネスの HTML と TSX を置き、Playwright MCP の Chromium で開いて撮った。dev server 経由なら本物の CSS (グローバルのトークンと CSS Modules) で部品を描けて、getComputedStyle と elementFromPoint でフェードの色・pointer-events・クリックの当たり先まで実測できた (実測)。同じ部品を jsdom 上の fake の ResizeObserver で検証した側の pin の作り方は ISSUE-88 の INS-80
- scrollHeight と clientHeight は整数に丸められるので、1px の差を許容しないと「ちょうど収まる」文が誤判定されうる (推測。許容の有無は変異注入で pin 済み)
- 「CSS を404にすれば崩れて赤になる」という変異は、スタイルが無くても折り返すサイトでは赤にならない。`nosniff` で捨てられた CSS は CSP の違反にも出ない。CSS が当たっていることは `:root` のカスタムプロパティが空でないことの番兵で見る必要があった (実測)。変異が赤にならない型は ISSUE-88 の INS-8 と同じ (仕分けたセッションの解釈)

### SVG と CSP の検査

2026-10-31に仕分けた分で届いた。

- 同一オリジンで配信する SVG を正規表現の文字列検査で守るときは、DOCTYPE の内部サブセットを ENTITY だけでなく ATTLIST・ELEMENT・NOTATION まで拒否する。ATTLIST の属性の既定値で要素に書かずに onload を付けられ、WebKit で実際に動いた (実測、Playwright の WebKit)
- `<!DOCTYPE[^>]*>` で DOCTYPE を読み飛ばすと、XML ではシステム識別子の引用符の中に > を書けるので、内部サブセットをコメントに見せかけられる。DOCTYPE は許可する形の許可リストで読み飛ばす (実測)
- SVG の href と CSS の url() は拒否リストではなく許可リスト (#id と特定の data:image だけ) で検査すると、符号化は自然に落ちる。そのうえで数値文字参照、CSS のエスケープ、url( を含まない外部読み込み (image-set) は別に拒否が要った (実測。段階ごとのレビューで見つけてテストで固定した)
- CSP が style-src 'self' のページでは、page.addStyleTag で差し込んだスタイルがインラインの style 要素として違反で弾かれる (Firefox で確認)。CSP の側は緩めず、構築可能なスタイルシートを document.adoptedStyleSheets へ足すと違反にならず、transition の停止も効いた (実測)
- Playwright の E2E で CSP の違反を検査するには、fixture の addInitScript で document の securitypolicyviolation を聞き、console.error として出し直すのが効いた。インラインスクリプトのハッシュを1文字ずらす変異で、該当のテストが赤になった (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。`route.fulfill` で返した応答のヘッダーの CSP を Chromium はそのまま適用し、`context.addInitScript` の `securitypolicyviolation` リスナーは script-src が厳しい CSP の下でも動く。インラインの style 属性の違反を拾えた (実測)
- CSP の違反を console の文言で数える E2E は、ブラウザごとに文言が違う (Chromium と WebKit で共通なのは Content Security Policy の語だけ)。WebKit を足すときは、対照を当てて空振りしないことを確かめる (実測)
- CSP を Report-Only で配信していると、Chromium は違反を console に info で出すだけで、error と warning を数える console の検査には入らない。ヘッダを付けただけでは、違反を見ているつもりで見ていない緑になる (実測)
- 第三者の iframe (bot 対策の widget など) を埋め込んだページでは、console の CSP の違反が iframe 自身の CSP であることがある。違反が名指しした指示の値を自分の CSP と突き合わせ、自分の文書の securitypolicyviolation をページのスクリプトより先に仕掛けた収集で数えると、取り違えずに判定できた (実測)
- CSP の report-uri / Reporting-Endpoints の宛先を相対のパスにすると、Chromium は応答の URL を基準に解決して https の宛先として登録し、本番で報告が届いた。ビルドした設定が本番の origin を持たずに済む (実測)
- 本番の CSP の違反の報告がブラウザから届くかは、Playwright の CDP セッションで Reporting API のイベント (Network.enableReportingApi、reportingApiReportAdded / Updated、reportingApiEndpointsChangedForOrigin) を受けて確かめられ、報告の本文、宛先の登録、送信の結果 (Queued → Pending → Success) が見える。報告の送信はページのネットワークの一覧に出ないので、DevTools の画面では確かめられない (実測)
- Reporting API の報告は数十秒まとめてから送られるので、違反を起こした直後にタブの context を閉じると、報告は送られずに消える (実測)
- インラインの `style="width:2000px"` で作ったはみ出しの対照は、厳しい CSP の下では style が消されてはみ出さない。属性で幅を出す `canvas` を使う (実測)

### SVG とデザインツールの書き出し

2026-10-31に仕分けた分で届いた。

- デザインツールが書き出した SVG は文字の位置を計算済みの座標で持つので、文言を変えるとずれる。`text-anchor="middle"` で書き、`qlmanage -t -s <px> -o <dir> <file.svg>` で PNG にして重なりを目で確かめた (実測)
- デザインツールの書き出しを受け取る検査器は、許可リストを決め打ちで広げず、実物の書き出しで止まってから広げる。新しい版の Affinity は SVG に旧版とは別の名前空間を書き、許可リストがそこで止めて初めて分かった (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ方向の報告者の提案が届いた。デザインツールの書き出しを入力にする機能では、仕様を固める前に実物の書き出しを1枚もらい、その特徴を持つ小さな見本で契約テストを作る、という手順をガイドに入れる。根拠は Affinity の新しい版の書き出しの項 (実測)
- Affinity の SVG の書き出しは、ドキュメントの DPI が72でないと viewBox が DPI/72倍になり、アートボードの位置が小数だと viewBox の幅が切り上がって1px ずれる。72DPI で整数の位置と寸法にすると、viewBox が設計どおりの整数になる (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。書類の DPI が72でないと座標は72DPI 換算の小数で出るのに viewBox だけが整数へ丸められ、縦横の比がずれる。HTML に埋め込んで大きさを固定すると、既定の preserveAspectRatio で縮んで中央に置かれ、縁に塗られない帯が出る。書類を72DPI にすると viewBox が整数のピクセルで出て、比のずれが起きない (実測)。報告者の提案は、デザインツールの書き出しを素材として取り込むリポジトリでは、アートボードの縦横の比 (viewBox) を撮る直前に検査すること。縁の帯はエラーにならず、目で見るまで気づけない (実測)
- maskable アイコンの安全域は SVG の getBBox では測れない (線幅の外側の半分が抜ける)。パスの上の点を getPointAtLength で刻み、線幅の半分を足して中心からの最大距離を測った (実測)
- 新しい版の Affinity (名前空間が https://www.affinity.studio/ のもの) の SVG の書き出しを平らな形だと仮定すると外れ、座標の読み取りを自前で書く前提は崩れる (実測)。実際は次のようになる
  - レイヤー名はグループの id になり、空白はハイフンに置き換わる。元の名前は affinity:id に残る
  - 変形は matrix の入れ子のまま残り、縦横の比の違う拡大もかかる
  - 文字は行ごとに別の text に分かれ、字間の調整で tspan にも割れる
  - フォントは PostScript 名と家族名の両方で指定される
- Affinity は font-family の先頭に太さ別の PostScript 名 (Geist-Bold など) を書く。可変フォントを同梱するなら、太さ別の名前を全部同じファイルの @font-face に結び付ければ、書き出しをそのまま使える (実測)
- Affinity は tspan ごとの letter-spacing でカーニングを焼き込む。ブラウザのカーニングは tspan の境目をまたいで効かないので二重には掛からず、tspan を外してブラウザのカーニングに任せても、文字の幅の差は1px 未満だった (実測)
- Affinity でシンボル化した図形を縮めると、線の太さは既定では縮まない。線の設定でオブジェクトと一緒に拡大縮小させると、比率どおりの太さで書き出される (書き出しの stroke-width が縮小率に一致した) (実測)
- テンプレートの座標は自前で解析せず、Chromium に描かせてから getBoundingClientRect と getScreenCTM で測る設計にした。入れ子の matrix をブラウザが解いた結果だけを使えば済む (推測。設計の段階で、実装はまだ)
- ビルドで画像を撮るとき、サブセットのフォントに無い文字が OS のフォントで黙って描かれるのを、Chromium の DevTools Protocol の CSS.getPlatformFontsForNode で捕まえた。isCustomFont が false で glyphCount が0より大きい項目があれば失敗にする。SVG の text と HTML の要素のどちらでも返る (実測)
- 書き出しの掃除が見た目を変えていないかは、元と掃除後を同じ条件で撮り、文字を隠した版と隠さない版の2通りで画素の差を数えると切り分けられる。図形の差が0なら、差は文字の組み方だけにあると言える (実測)
- ロゴを空の四角 (プレースホルダ) の範囲へビルドで描き込む構成では、ロゴの外側のタイルが置き先の背景と同じ色だと、見える形が四角より小さくなる (その報告では約78%)。デザインツールで四角に合わせて並べても、見た目はずれる。デザインツール側でロゴの見本を四角に重ねて配置し、コミットするテンプレートからは見本を外して四角だけを残すと、元のデータを1つに保ったまま見た目どおりに並ぶ。症状は、ビルドした画像で見えている画素の範囲を測ると切り分けられる (実測)
- `<img>` で読み込む SVG を、サイトのダークテーマに対応させたいとき、SVG の一番下にライトの surface と border の色で不透明な板を1枚敷くと、どちらのテーマでも読めた。`<img>` の中の SVG には、ページの `data-theme` も、CSS の変数も届かない。SVG の中に prefers-color-scheme を書く手もあるが、それは OS の設定に従うだけで、サイトのテーマ切り替えボタンとは食い違う (実測: ヘッドレス Chromium で描画して確かめた)。報告者の提案は、フロントエンドの規約に「`<img>` で読み込む SVG やアイコンはページのテーマを継承しないので、ダークテーマで読めるかを確かめる」という観点を足すこと (実測)

### Playwright Test Agents とブラウザの MCP

2026-10-31に仕分けた分で届いた。

- Playwright Test Agents の Generator を直列に回したとき、2本目以降で setup が webServer のポートの使用中で失敗し、Generator は記録せず計画から静的にテストを書いて written=true を返した。ポートを握っていたのは MCP サーバ自身が起動して残した preview だった (実測。原因は未特定で再現していない)
- Planner の観測 (ロケータ、想定外の挙動の列挙) は質が高い。Generator は1ファイル1テストの制約があって表で回すテストは手でまとめ直す前提になり、written=true は記録して書いたことを意味しないので notes を読んで確かめる (実測)
- 報告者の提案: Generator への brief に、notes を確かめる手順を入れる
- Planner / Generator / Healer は MCP サーバ1つ (ブラウザ1つ、webServer 1つ) を共有するので、並列に回すと setup が奪い合う。Workflow でも直列にする (直列で回した結果だけが実測。並列の奪い合いは推測)
- planner で browser_run_code_unsafe から新しい browser context を作ると、直後から全ツールが MCP backend is not initialized を返して止まった。同じページでログアウトしてログインし直すと最後まで探索でき、落ちたら setup_page を呼び直すと復帰する (実測)
- 報告者の提案: references/testing.md の E2E の生成の手順に追記する
- Test Agents の MCP サーバが起こした webServer がポートを握っているときは、同じ MCP の test_run で回すと既存の webServer を使って通せ、実行したテストの ID の集合も出力に出るので ID で pin できる。または /mcp で MCP を切ってから正規の入口で回す (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。Test Agents の MCP は generator の終了後も E2E 用の dev server を握ったまま残し、`reuseExistingServer: false` と `--strictPort` の構成では次の `playwright test` が起動できない。MCP の親プロセスとポートを確かめてから止める必要があった (実測)。報告者の提案は、Test Agents を使った後は `playwright test` の前にテスト用のポートを確かめる手順を足すこと (実測)
- planner の計画ファイル (planner_save_plan) は既定でリポジトリ直下の specs/ に未追跡で置かれるので、コミットの前に移さないと混入する (実測)
- planner / generator に実画面の文言を推測と区別して報告させると、UX の欠陥 (無効化された利用者に通信失敗の汎用画面が出る) を探索の段階で見つけられた。generator は Bash を持たないので、テストの実行はコントローラ側が要る (実測)
  - 2026-11-10の仕分けで、別のリポジトリから generator の報告が届いた。実物のアプリを探索して locator を選ぶので役に立つが、探索した画面の構造のまま書くので、同じ文字列が画面に2か所ある箇所で strict mode の違反になりやすく、実行前のレビューで2件見つかった。shell が無いので自分では実行できず、型エラーも実行もコントローラが確かめる必要がある (実測)
- chrome-devtools の MCP は、同じプロファイルのブラウザが他で動いていると起動できない。別の MCP のブラウザへ切り替えて回避した (実測)
- セッションの途中で作った .mcp.json のサーバーは /mcp に出てこなかった (実測)。プロジェクトの MCP サーバーは起動時にしか読まれない様子で、Playwright Test Agents を使うにはセッションの再起動が要る (推測)。MCP の要らない配線を先に WIP コミットしてから再起動すると、待ちが無駄にならない。報告者の提案は、`references/testing.md` の「E2E の生成」に再起動の要否を足すこと
- `init-agents --loop=claude` が書き出す .mcp.json は `npx playwright run-test-mcp-server` で起動し、seed と specs/ もリポジトリのルートに置かれた (実測)。報告者の提案は、npx を禁じている環境では pnpm exec に直す手順を足すこと。specs/ の扱いは上の planner の計画ファイルの項と同じ
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。`testDir` がある状態で回すと seed はその中に作られる。生成される `.mcp.json` は `npx` で起動し、macOS では既定で headed、生成物は末尾の改行を持たない。generator の定義は seed のパスを `tests/seed.spec.ts` と決め打ちし、healer の定義は頑固なテストに `test.fixme()` を付けろと指示する。エージェント定義と MCP サーバーはセッションの起動時にしか読まれないので、取り付けた後に再起動が要る (実測)。上の再起動の要否の項 (推測) と Healer の定義の項 (ドキュメントのみ) と同じ点について、こちらは実測の札で届いた。報告者の提案は、E2E の生成の手順に、`page.request` 系が route を迂回すること、横取りで返すときは `--host-resolver-rules` で名前解決を潰すこと、Test Agents の生成物の `npx` と headed と `test.fixme()` の扱いを書き足すこと (実測)。前の2点の中身は「React と E2E (Playwright)」節の本番のオリジンを横取りする項にある
- 生成された Healer の定義に「直せなければ test.fixme() にして skip する」とある。失敗を緑に見せる経路なので、brief で禁止し、実行されたテストの ID の集合で skip が無いことを確かめる必要がある (ドキュメントのみ。生成された定義を読んだだけ)
- Playwright MCP はカレントのリポジトリ直下に `.playwright-mcp/` (snapshot の yml と console のログ) を作り、多くのリポジトリの .gitignore には載っていない。放置すると誤コミットの種になるので、使い終わったら消すか ignore に足す (実測)。報告者の提案は、グローバルの gitignore に `.playwright-mcp/` を足すこと。仕分けたセッションの解釈: 上の planner の `specs/` と同じ型の混入
  - dotfiles で確かめたこと (2026-11-04): グローバルの gitignore (`home/.config/git/.gitignore_global`、15行) に `playwright` と `mcp` を含む行は0件だった
- claude-in-chrome は CodeSandbox の Preview の確認に使えた。初回は「proceed to preview」の確認画面が出るのでクリックが要る。コンソールの記録は呼んだ時点から始まるので、読む前に一度再読み込みしないと「0件」が「見ていない」と区別できない (実測)

### GitHub Actions と Node の版

- `workflow_run` で起動した run の actions/checkout (ref 指定なし) は、トリガーした run の sha ではなく実行時点の default branch の先端を fetch する。workflow_dispatch はブランチを checkout する。checkout step のログの fetch 行と rev-parse 行で確かめられる (実測)
  - 続報 (2026-10-31の仕分け、実測): この経路では配信中のタグとずれるので、本番の検査は checkout ではなく応答から期待値を導く。ハッシュの元を配信されるバイト列にすると、本番の値を本番の応答だけで検算できる
- actions/setup-node に `node-version-file` で範囲 (`24.x`) を渡し `check-latest` を付けないと、ランナーのツールキャッシュにある版で満たされ最新のパッチは入らない。同じ run の中でもジョブごとに 24.21.0 と 24.22.0 に分かれた。下限付きの範囲 (`>=24.22.1 <25`) なら check-latest 無しで修正版へ届き、全ジョブのログに `Attempting to download >=24.22.1 <25` と `node: v24.22.1` が出た (実測)
  - 続報 (2026-10-31の仕分け、実測): 別のリポジトリでは devEngines.runtime を範囲ではなく exact の版にし、CI の setup-node は `node-version-file: package.json` で読む形にして、Node の版の literal を1箇所にした。範囲だと、lockfile が固定した runtime とツールキャッシュの最新がずれる (範囲の扱いは実測とソースの読み)
- 下限の検査は setup-node の直後に置き、「setup-node を持つ job ⇒ 直後のステップが検査」の含意と、ファイル全体の setup-node の出現数が列挙と一致することの2本でテストに pin すると、job の追加や書き方の揺れでも穴が空かない (実測。変異8種がすべて赤)
- setup-node 7.1.0 から `node-version-file` に mise.toml を渡せる (ドキュメントのみ)
- 手元の Node は、グローバルの mise 設定を変えずに `mise exec node@<版> -- <コマンド>` で切り替えて lint / test / build を回せる (実測)
- Vercel CLI の engines.node の解釈は `>=24.22.1 <25` でも `24.x` と同じく 24.x に解決され、警告もエラーも出ない (実測)
- pnpm (12系) は root の package.json の engines.node を満たさない Node でも、run / install とも警告なしに通る。手元での版の強制は効かず、CI 側の検査が唯一の強制になる (実測)
- 毎日の定期チェックの workflow では、前提のステップを checkout の直後に置き、その後ろの検査をすべて `if: always()` にそろえると、1つが落ちても残りの検知が止まらない。集約のステップは、内訳が空でも job が赤なら「正常」と言わずに1行残す (実測。変異16種がすべて赤)
- sparse-checkout で必要なファイルだけ取り出す workflow は、テストでもその一覧のファイルだけを一時ディレクトリへ写してステップを走らせると、取り出し漏れ (毎朝の偽の赤) をマージ前に捕まえられる (実測)
- 報告者の提案: setup-node にメジャーだけの範囲を渡しているリポジトリは、パッチが runner イメージ任せになっている。各リポジトリの CI ログで掴んだ版を数えてから、下限付きの範囲か check-latest を検討する (推測)
- node の版を `.node-version` へ寄せて CI と mise で共有する報告と、その mise の設定は ISSUE-136 に置いた
- Draft PR を作った直後は、作成の run が立ったのを見てから Ready にすると、Ready の run が取り消されずに残った (実測)
- required check を Draft では意図的に failure にする設計 (skipped を満たされた扱いにしない安全弁) のまま Draft で作ってすぐ Ready にすると、CI の節約は起きず、赤の通知だけが PR ごとに鳴った。preflight が緑なら Draft を挟まず Ready で作る運用へ変えた (実測。直近60件の failure 21件の大半が設計上の赤)
- setup-node の自動キャッシュは packageManager が npm のときだけ有効で pnpm では無効だが、権限の強いジョブでは `package-manager-cache: false` の明示が README で推奨されている (ドキュメントのみ。README の記述)
- `on.push.branches: ["*"]` は glob の星が / を跨がないので、feat/... のようなブランチでは一度も走らない。全ブランチなら星2つの glob にする (実測。実行の記録が0件)
- 「デプロイは main からのみ」は workflow の if では守れない (workflow_dispatch は起動したブランチ側の YAML を走らせる)。environment のブランチのポリシーを main だけにし、シークレットを environment secrets へ移すと、別のブランチからの起動はステップ0で「Branch is not allowed to deploy」と拒否された (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ手当ての報告が届いた。CI が secret manager を読むトークンを、どのブランチの workflow からも読めるリポジトリの secret から、branch policy (main だけ) 付きの GitHub environment の secret へ移した。環境ごとに別のトークンにし、名前も環境ごとに変えた (実測)。名前を分ける理由と配線の pin は、この節の後ろの「secret の配線」の項にある
  - 2026-11-10の仕分けで、別のリポジトリから live の確認の報告が届いた。Environment のブランチ制限の live の確認は費用がほぼ掛からない。拒否された job は step が1つも走らず、job の check-run の annotation に「Branch ... is not allowed to deploy to ... due to environment protection rules」が出るので、それを読めば拒否の理由まで確かめられる。feature のブランチから拒否され、main から通ることを live で確かめた (実測)
  - 2026-11-10の仕分けで、別のリポジトリから移す順序の報告が届いた。デプロイ用の secret をリポジトリの secret から main に絞った Environment の secret へ移し、順序は Environment へ入れる → 配信元ブランチを絞る → リポジトリ側を消す → マージの deploy で実測、とした。同名の secret は Environment 側が勝つので、リポジトリ側を残したままの緑は Environment 側の正しさの証拠にならない (実測は deploy 待ち)。同じ報告で、ブランチ保護も ruleset も無いリポジトリで配信元ブランチを絞るときに `protected_branches: true` を選ぶと許可が0本になるので、`custom_branch_policies: true` と名前の policy で main を指す (ドキュメントのみ)
  - 2026-11-10の仕分けで、別のリポジトリからテストで縛る向きの報告が届いた。secret を Environment へ移すときは「secret を読む job ⇔ environment を持つ job」を両方向でテストに縛る。逆向き (読まない job に environment を付ける) も赤にするのは、environment を付けた job は OIDC token の sub が environment の形に変わり、クラウドの WIF の attribute condition から外れて配信などが黙って止まるため。読む job の集合は件数でなく job ID の集合で pin した。変異3種で赤、コメントにだけ名前がある対照で緑 (実測)
- リリースをタグ駆動にして2種類の成果物をタグの接頭辞で分け、タグは任意のコミットに打てるので CI で `git merge-base --is-ancestor <tag>^{commit} origin/main` を検査し (fetch-depth: 0)、environment のデプロイの許可は tag のパターンだけにした。tag の ruleset は管理者が bypass できるので、immutable releases を足した (実測。タグの push だけでデプロイと Release の作成まで通った)
- tag の push で動く workflow は tag が指すコミットの workflow ファイルを使うので、main で直しても既存の tag の再実行では直らず、tag を打ち直す必要がある。immutable releases を ON にするとそれもできないので、正しく打ち直した後に ON にする (実測)
- strict な required check の下では、squash 後の main のツリーが、マージゲートが緑の PR の head のツリーとハッシュで一致した。main の push で CI を回さない構成でも、main が検証済みであることを確かめられる (実測)
- GitHub Actions を SHA でピン留めしている依存の更新の PR は、`git/ref/tags/<tag>` でタグが PR の SHA を指すことと、`compare/<旧>...<新>` で変わったファイルが自分の使う部分に触れていないことを確かめると、コメントの版ではなく実際に効く SHA を検証できる (実測)
- 長く放置したあと、Dependabot の Actions の更新3本を1本のブランチにまとめて取り込み、CI の実行を1回に抑えた (実測)
- ubuntu-latest の移行の告知は、移行がリポジトリに届く前から run に出続ける。実際の OS は Set up job のログの Image: の行で分かるので、直近の run を数えてから版を判断する (実測。告知の開始から9日後でも40本すべて旧イメージ)
  - 2026-11-10の仕分けで、別のリポジトリから、`ubuntu-latest` は2026-10-19から Ubuntu 26へ順に移る (actions/runner-images#14748、deploy の run の notice で告知) という報告が届いた。報告者の提案は、`runs-on: ubuntu-latest` のリポジトリは、Playwright の `install-deps` のように OS のパッケージ名に依存する step が移行の日に落ちうるので、版を1か所で明示して先に26.04で確かめるのを棚卸しに入れること (ドキュメントのみ)。同じ報告で、Ubuntu 26.04には sudo (1.9.17、`/usr/bin/sudo.ws`) と sudo-rs が両方入り、コンテナの既定の `/usr/bin/sudo` は alternatives で sudo-rs を指す。GitHub の runner の readme の sudo の版はパッケージの版で、どちらが `/usr/bin/sudo` かまでは読めない (実測 / ドキュメント)
- WarpBuild のランナーは、GitHub App の対象に repo を足し、ランナーのラベルを variable で切り替えれば使えた。job のログの「Runner name」と prehook の行で、どのランナーで走ったかを示せる (実測)
- workflow_dispatch だけで動く workflow は、merge の前に誰も YAML を検証しない。存在しない job を `needs` に書くと dispatch の時点で workflow ごと拒否され、if や run に残った `needs.<消した job>.*` は空文字として黙って評価される。job を消す変更は、参照先の実在を pytest などで pin しないと merge の後まで見えない (推測。GitHub の挙動はレビューの subagent の読みで、実走はしていない)
- GitHub の runner の image は apt のミラー3段と `Acquire::http::Timeout 15` を2026-09から持つが、Timeout は無応答にしか効かず、遅いが進んでいる取得からは逃げない (ドキュメント / 実測のログ)
- `${{ vars.X }}` は未設定だと空文字列に展開される。値を env にそのまま渡すと、フロントの `import.meta.env.X ?? 既定値` は空文字列を「値あり」として通し、既定値に倒れない。以前の取得経路で「変数が存在しない」だった env の挙動が黙って変わる。ビルドの前に空の変数を unset する (コードの読みで確認、修正はこれから) (推測)。報告者の提案は、フロントのビルドに CI の変数を渡す手順の規約に「未設定の変数は空文字列になるので、渡す前に空を unset する」を足すこと (推測)
- secret の棚卸しは「名前が workflow に出るか」ではなく「`secrets.<名前>` の形で参照されるか」で数えると、1Password の load-secrets の出力名や Secret Manager の `--set-secrets` の変数名と同じ名前の GitHub secret を「使用中」と取り違えずに済む。間接の参照 (`toJSON(secrets)`、`secrets: inherit`) も別に数えて0件を確かめてから消す判断をした。結果として、リポジトリと environment の secret の大半が参照ゼロの名残だった (実測)。別の報告では、secret の参照を YAML の文字列から正規表現で拾うときは、`secrets.` の直前に `.` `-` 英数字が無いことを条件にする。`steps.x-secrets.outputs` や `needs.verify-secrets.result` を誤って拾う (実測)
- environment に branch policy を付ける前に `gh run list --workflow=<名前> -L 100 --json headBranch,event` で過去の run の ref を集計すると、制限で壊れる経路が無いことを先に確かめられる (実測)
- secret の配線: secret manager を読む job は environment を宣言する、その environment のトークンだけを読む、environment を持たない job は GITHUB_TOKEN 以外の secret を読まない、top-level の env と `secrets: inherit` を禁じる、の対応関係を、workflow の YAML を読む pytest で固定した (実測)
  - トークンの secret 名を環境ごとに変える (同じ名前を environment とリポジトリの両方に置かない)。environment の付け忘れやリポジトリの secret の再追加があっても、別の値へ黙って落ちずに空になって失敗する (ドキュメントのみ)
  - リポジトリの secret を消したり移したりするときは、org レベルに同じ名前の secret が無いかも名前だけで確かめる (`gh secret list --org <org>` と `gh api repos/<owner>/<repo>/actions/organization-secrets`)。実際に同じ名前の org secret が見つかった (対象リポは0件で無害だった)。後からそのリポを対象に加えるだけで、消したはずの名前が黙ってその値で解決されるので、環境ごとに名前を変える理由にもなる (実測)
  - PR でも走る job が本番の値を要るときは、計算する job (environment なし) と値を読む job (environment あり、artifact を受け取る) に分ける。job 全体に environment を付けると、PR の ref が branch policy に合わずに job ごと失敗する (ドキュメントのみ)
  - 報告者の提案は、secret を CI に渡すリポジトリの共通の規約として、「secret manager のトークンはリポジトリの secret に置かず、environment の secret に環境ごとの名前で置く」を検討すること (ドキュメントのみ)
- environment の保護規則で拒否される job の負のプローブで、1回目の dispatch が job0件・GitHub の Internal server error で終わり、「拒否」と「障害」の区別が付かなかった。re-run の2回目で job が作られ、step 0・runner なし・annotation に保護規則の拒否が出た。負のプローブの判定は conclusion ではなく、job の有無と annotation の本文で行う (実測)
- 1Password の load-secrets-action は、OP_ENV_FILE のパスが読めないと何も読み込まずに成功する。前の step で `test -f` する必要がある (ドキュメントのみ。action のソースを読んだ subagent の報告)
- GitHub Actions の workflow lockfile (`.github/workflows/actions.lock`、`gh actions-lock` 拡張 v0.4.0) へ、全 `uses:` を SHA で固定済みの workflow を移した (実測)。別の報告は、lockfile が2026-10-28に GA になったとしている (ドキュメントのみ)
  - `gh actions-lock --no-fix` を先に打つと、書き込まずに onboarding で何が変わるか (SHA の ref を tag の ref へ書き換えること) が分かる。生成後の lockfile の commit は元の SHA と一致し、`--verify` で検証できる (実測)
  - `gh actions-lock` は workflow の `uses:` に SHA を残すオプションを持たない。SHA の ref は「tag の ref が無い」として tag の ref へ書き換えられる (`--no-narrow` は部分の版を保つだけ)。workflow の SHA 固定を「固定の証拠」として読むテストやコメントは、移行で偽になる (実測)。別の報告も同じ事実 (SHA は lockfile だけが持つ形になる) を挙げ、`--verify-local` は uses: の版を変えると rc 1、戻すと rc 0で、pre-commit の hook として使える (実測)
  - v0.4.1は公開から3日未満だったので、待ち期間の方針に合わせて既存の v0.4.0を使った。pre-1.0で書式やフラグが変わりうるので、版を記録しておく (実測)
  - lockfile の強制 (Require lockfile) の policy は、REST の Actions policies の文書に rule の型が載っていない。UI (Settings > Actions > Policies) で作ったものを `GET repos/<owner>/<repo>/actions/policies/<id>` で読むと rule は `{"type":"require_lockfile"}`、対象は `workflow_path.include: ["~ALL"]` だった。一覧の GET は rules を返さないので詳細を引く (実測)。別の報告は、この policy は REST の作成と更新で弾かれるという報告があるので、画面でしか有効にできない前提で計画するとしている (ドキュメントのみ)
  - lockfile が古い PR では、workflow が `startup_failure` になって PR の check の一覧に出ないと報告されている。CI の結論は check の一覧ではなく run の一覧で見る必要がある (ドキュメントのみ。第三者の検証記事)
  - 報告者の提案は2つ。1つは、全 action を SHA で固定済みのリポジトリへ lockfile を入れるときの手順 (`--no-fix` で差分の形を見る、lockfile の commit が元の SHA と同じかを確かめる、SHA 固定の強制はそのまま有効にできる、Require lockfile は main に入ってから有効にする) を横断の手順として持っておくこと (実測とドキュメント)。もう1つは、Actions を使う全リポジトリで採用を検討すること。composite の action が内部で使う action まで commit を固定でき、SHA の固定だけでは届かなかった推移的な依存を塞げる。sha_pinning_required は API で入れられる安い下敷きとして併用する (ドキュメントのみ)。仕分けたセッションの解釈: dotfiles 自身も Actions を SHA で固定しているので採否の対象になる

### CI のコンテナと digest 固定

2026-10-31に仕分けた分で届いた。

- Actions の Playwright の E2E を公式のコンテナで動かして `install --with-deps` を外すと、apt の待ちで20分のタイムアウトになっていたジョブが pull 込み1分8秒になった。`--user 1001` で Firefox と WebKit も動いた (実測)
- 報告者の提案: CI で Playwright を回すリポジトリの既定の作法にする
- CI の全ジョブを runs-on の新しい ubuntu のラベルと digest 固定のコンテナ (node / playwright) で動かす形へ移し、CI、マージゲート、本番のデプロイ、デプロイ後の E2E が緑になった (実測)
- ランナーのラベルは OS の版の固定で、中身の固定ではない (イメージは毎週更新される)。実行環境を固定するなら digest 固定のコンテナで動かし、index の digest は Accept ヘッダ付きの HEAD の docker-content-digest で取れる (Docker Hub は token が要る) (実測)
- コンテナの tag は Dependabot が上げないので、イメージの版と lockfile の @playwright/test の版の一致をユニットテストで pin すると、npm 側の更新の PR で赤くなる。workerd では node:fs が無いので `?raw` で YAML を読み、正規表現はキーの行に固定してコメントの行を拾わない (実測、変異注入で確認)
- digest 固定の node のイメージを root のまま動かすと、checkout の後の git が dubious ownership で落ちる (ワークスペースは uid 1001で、checkout の safe.directory は後続に残らない)。`--user 1001` で揃えて解消し、テストで pin した (実測)
- CI と同じ digest 固定の Playwright 公式イメージをローカルの Docker で動かし、全ブラウザの E2E を回した。リポジトリを読み取り専用でマウントしてコンテナの中へコピーし、node_modules は中で入れ直し、webServer が呼ぶタスクランナーがイメージに無いときは使う recipe だけの使い捨ての shim を置いた (実測。ホストのブラウザが欠けていても全ブラウザで確かめられた)
- 報告者の提案: 「ローカルのコンテナで検証する」の具体例として参照ファイルに置く

### コンテナイメージの配信と trust store

2026-11-10に仕分けた分で届いた。

- `gcr.io/distroless/cc-debian12:nonroot` は2026-11-06の最新の digest でも ca-certificates 20250419~deb12u1のままで、emSign ECC Root CA - G3 と AAA Certificate Services を含んでいた。bookworm の apt の候補は deb12u2で両方を外しており、cc-debian13は2つとも含まない。distroless は Debian の standard support を追う方針で、Debian 12の通常のサポートは2026-07-12に LTS へ移ったので、debian12系は修正が入っても作り直されない前提で扱うのが安全 (実測 / ドキュメント)。報告者の提案は、distroless の debian12系を runtime に使うリポジトリは、debian13への移行と built image の CA バンドルの検査 (拒否の CN と対照の CN) を棚卸しの対象に入れること (実測)
- webpki-roots などの crate を上げても、reqwest 0.13の rustls-platform-verifier (rustls-native-certs) と native-tls / OpenSSL の経路はシステムの trust store を読むので、base image の CA バンドルが古いと取り下げた root を信頼し続ける。crate と image の両方を見る必要がある (実測)
- built image の CA バンドルの検査は「拒否の CN が0件」だけでは別のファイルを読んだ空振りと区別できないので、どの版にも入っている root (ISRG Root X1) を対照として必須にすると判定が締まる。`openssl x509 -noout -subject -nameopt sep_multiline,utf8,-esc_msb` は OpenSSL 3.0と4.0で同じく RDN を1行ずつ出す (実測)
  - 2026-11-10の仕分けで、別のリポジトリからも同じ形の報告が届いた。distroless イメージの `/etc/ssl/certs/ca-certificates.crt` を取り出して、信頼を外すべき root の有無を対照の root (ISRG Root X1) と一緒に数えた (実測)。その取り出しで踏んだ偽の0件は ISSUE-133 の観測の節に置いた
- deploy の `docker buildx build --push` は runner の daemon に image を残さないので、検査は push の後に `docker pull` してから Cloud Run 等へ出す前に置く (実測)
- trixie では `libssl3` は `libssl3t64` が Provides するだけの仮想パッケージ。apt に推測させず実名で入れる (実測)
- Cloud Run の revision の image は digest で記録されるので、タグの digest と比べると食い違って見える。buildx の provenance でタグは OCI の index を指し、revision はその中の linux/amd64 の manifest を指す。Artifact Registry の manifests API で index を読むと突き合わせられる (実測)。別の報告も同じ事実を挙げ、push の digest と serving の digest が食い違って見えても、`docker buildx imagetools inspect <index>` で親子を確かめれば同じ build だと言える。検査を serving の側に当てるときは revision の `status.imageDigest` を使う (実測)
- Cloud Run の「今の revision」を最新作成の revision で採る仕組みは、rollback の後だけでなく、失敗して traffic を持たない revision が残っていても誤検知する。traffic が100%向いている revision で採るのが正しい (実測)
- musl の sshd の認証バイパス (crypt() が失敗時に `*` を返し、ロック済みの印と一致する) は、「musl でビルドされ PAM を通さない sshd が動いているか」で影響を判定できる。Dockerfile・compose・IaC を `openssh|sshd` で grep し、alpine / musl を使う image の用途を並べれば足りた (実測)

### GitHub

2026-10-23に仕分けた分で届いた。

- 旧来の方式 (gh-pages ブランチから配信する legacy) の GitHub Pages は、`DELETE repos/{owner}/{repo}/pages` が 422「Deactivating GitHub pages for this repository is not allowed」で拒まれた。止められたのは次の順で、止めたあと元の URL は30秒ほどで 404 になった (実測)
  - gh-pages を作り直す workflow を先に無効にする
  - ブランチの名前を変える。配信元は自動で付いてきて、配信は続く
  - その後なら DELETE が通る
- Team プランの private のリポジトリで Pages を有効にすると、private のはずの中身が誰でも読める。Pages の閲覧範囲の制限は Enterprise Cloud の機能である。`keep_files: true` の deploy の action は gh-pages にある deploy の対象以外のファイルを消さないので、一度置かれたファイルは配信され続ける (実測。認証なしの読み出しが通った)
- 報告者の提案: org やリポジトリの棚卸しの手順に、「private のリポジトリで Pages が有効になっていないか (`GET repos/{owner}/{repo}/pages`)」と「gh-pages に deploy の対象以外のファイルが残っていないか」を入れる
  - dotfiles で確かめたこと (2026-10-23): `gh api 'user/repos?affiliation=owner,organization_member'` で見える87件のうち、private の36件で `has_pages` が true のものは0件だった。対照として、public の51件のうち4件は true を返した。gh-pages のブランチの中身は見ていない。棚卸しの手順を置く場所は決めていない

### GitHub の CLI とリポジトリの管理

2026-10-31に仕分けた分で届いた。

- `gh api .../actions/jobs/<id>/logs` は、ログが端末のエスケープシーケンスを含むと出力を拒んで rc 1になり、リダイレクト先は0行になる。`--allow-escape-sequences` を付けると取れる (実測)
  - 2026-11-10の仕分けで、2つのまとめから同じ型の報告が届いた。拒んだときの出力は本文の代わりに「--allow-escape-sequences を渡せ」という1行で rc=1になり、その出力に grep をかけると0件になり、「見ていない0件」が健全に見える。`gh run view <run> --job <id> --log` なら取れた (実測)
- gh pr create が GraphQL の汎用エラーで失敗したとき、作り直す前に `gh pr list --head <branch> --state all` で存在を確かめると、1回目は作られず、2回目は作られたうえで assignee の設定だけが落ちていた。再実行の前に存在を、作られた後に title・body・assignee・head を個別に確かめる (実測)
  - 2026-11-10の仕分けで、別のリポジトリから GitHub 側の書き込みが続けて失敗した報告が届いた。push が `fatal error in commit_refs_rules` で、同じ時間帯の squash merge が GraphQL のエラーと REST の空応答で、それぞれ続けて失敗した。githubstatus は正常だった。ブランチ名を変えた push は通り、merge は数分あけた再試行で通った。原因は特定できていない。ブランチ名が原因だと決めるには根拠が足りない (実測)。報告者の提案は、GitHub 側の書き込みが続けて失敗したら、叩き続けずに状態 (PR が merge されていないこと、main が動いていないこと) を確かめてから、数分あけて1回だけ再試行する手順を共通の運用に置くこと (実測)
- `gh run download <id> -n <artifact>` で artifact を1つだけ落とすと、artifact の名前のサブディレクトリが作られず直下に置かれる (全部落とすときは作られる) (実測)
- Dependabot の版の更新の PR が届いていても、脆弱性の通知 (Dependabot alerts) は別のスイッチで無効のことがある。`gh api .../dependabot/alerts` が403 disabled なら無効で、`PUT .../vulnerability-alerts` で有効にし (GET が204で確認)、有効にした直後の0件は dependency-graph/sbom のパッケージ数が非空であることを対照に読む (実測)
- 報告者の提案: 管理しているリポジトリの定期点検に、Dependabot alerts の有効を入れる
  - 2026-11-10の仕分けで、別のリポジトリから報告者の提案が届いた。dotfiles の監査の手順で、依存の脆弱性を lockfile の1件として挙げるときは、`dependabot/alerts?state=open` の件数も並べる。その報告では1件の指摘に対して実際の open alerts は92件だった (実測)。仕分けたセッションの解釈: どの監査の手順を指すかは原文から特定できない
- 個人アカウントの private のリポジトリを REST の transfer API で organization へ移し、前後で repo の設定 (ruleset、rules/branches、Environments と保護、secret と variable の名前、Actions の権限、webhook、deploy key、collaborator、autolink、repo 本体) を JSON に写し、id・URL・タイムスタンプ・owner など必ず変わるキーを jq の walk で落としてから diff すると、残った差分だけが読むべきものになった。transfer の POST の応答は旧い owner の full_name と null の visibility を返し、移管は非同期なので、新しい名前で GET し直してはじめて完了が分かる (実測。21ファイル中20が一致し、差分は repo 本体の4項目)
- 報告者の提案: org へ移す手順書に「POST の応答ではなく GET で完了を確かめる」「前後を JSON に写し、変わるキーを落として diff する」「org の方針に従って変わる値がある」「release の一覧の API を引く action は移管の後に落ちうる」の4点を入れる
- ruleset の id と bypass_actors、Environment の保護とブランチの制限、secret と variable の名前は移管の前後で変わらず、rules/branches の ruleset_source は新しい owner の名前に変わるだけで、ruleset_source_type は Repository のままだった (実測)
- org へ移すと allow_forking が true から false に変わった (org の private の fork の方針が効く)。security_and_analysis は null から6項目とも disabled を明示する形に変わり (実効は同じ)、custom_properties が空で増えたので、「設定は何も変わらない」と仮定しない (実測)
- Dependabot の件数は manifest と lockfile (`pyproject.toml` と `uv.lock`、`package.json` と `pnpm-lock.yaml`) に同じ advisory を2回立てるので、(ディレクトリ, GHSA, パッケージ) で重複を除いてから仕分ける。311件が229件になった (実測)
- Dependabot には既定で3日の cooldown があり (ドキュメントのみ)、pnpm の lockfile も ecosystem は npm で扱われ、pnpm 11まで対応している (ドキュメントのみ)。報告者の提案は、既定は変わりうるので cooldown を明示する運用をそろえること。github-actions の ecosystem で cooldown が使えない件は ISSUE-101 にある
- `gh run rerun <run> --failed` の後は、再実行していない成功の job も API 上で新しい job id が振られて見える。`started_at` が元の時刻のままなら再実行されていない。ログは新しい id で取り直さないと前回の失敗のログを読む (実測)
- `GET repos/{owner}/{repo}/rules/branches/{branch}` が `[]` なら、リポジトリと組織のどちらの ruleset もそのブランチに効いていない。「PR 必須のつもり」の private リポジトリで実際には何も強制されていなかったのを、この API で見つけた (実測)
- `gh pr merge --match-head-commit` は短縮の SHA を受け付けず、GraphQL の `Could not coerce value ... to GitObjectID` で落ちるので、40桁で渡す (実測)。別の報告では、Dependabot の PR を続けてマージすると、lockfile がぶつかる PR は Dependabot が rebase して head が変わり、`--match-head-commit` に前の sha を渡した実行は「Head branch was modified」で止まった。マージのコマンドは毎回 head を引き直してから組む (実測)
- `gh pr diff` にはパスで絞る引数が無い。パスを渡しても何も出ないので、差分をファイルに書いてから diff --git の区切りで切り出す (実測)

### pnpm

2026-10-31に仕分けた分で届いた。pnpm の版と engines の扱いは GitHub Actions と Node の版の節、build scripts の警告はその他のツールの節にもある。

- deprecated は `pnpm outdated` の Latest の列と `pnpm view <pkg>@<ver> deprecated` で拾える。peer の非対応を見てメジャーを据え置く前に、後継のパッケージの有無を確かめる (実測)
- pnpm 11以降は onlyBuiltDependencies と ignoredBuiltDependencies を読まず、allowBuilds (名前から真偽への map) が後継になった。pnpm 12は pnpm-workspace.yaml の未知のキーを pin した版で実行中ならエラーにし、未承認のビルドスクリプトも警告ではなく ERR_PNPM_IGNORED_BUILDS のエラーにするので、移行は必須 (実測。2つの設定を読まないことと未知のキーのエラーはドキュメントのみ)
- 報告者の提案: 全リポジトリで、pnpm の移行時のチェックリストにする
- allowBuilds は、書かないと ERR_PNPM_IGNORED_BUILDS で非0、false なら通って postinstall のログが出ない、true なら出る、の3つを並べて確かめた。ストアは場面ごとに分けて side effects cache の影響を外す (実測)
- pnpm 10系では minimumReleaseAge の既定が0で、未設定のリポジトリにはクールダウンが無い。11から既定は1440なので、既定に頼らず明示した方が版をまたいで意図が残る (ドキュメントのみ)
- pnpm 11以降は .npmrc の認証とレジストリ以外の設定と、package.json の pnpm の欄を読まない。.npmrc の minimum-release-age のまま上げると若い版で妥協して入り、pnpm-workspace.yaml を自分で作って例外まで書き足した (実測)
- 報告者の提案: 設定を移し、minimumReleaseAge と minimumReleaseAgeStrict を両方明示する手順を共通の規約に入れる
- minimumReleaseAgeStrict の既定は「minimumReleaseAge を明示したときだけ true」で分かりにくいので、strict も明示する (明示した側の振る舞いは実測。既定の規則はドキュメントのみ)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。`minimumReleaseAge` を明示して strict を既定にした (実測)。`pnpm config get minimumReleaseAgeStrict` は明示しなくても `undefined` を返す (値から導かれる既定なので config に出ない)。pin するなら導出の元の `minimumReleaseAge` を見る (実測)
  - 2026-11-10の仕分けで、さらに別のリポジトリから、pnpm 11の minimumReleaseAge と Dependabot の cooldown を同じ日数で入れ、依存の更新を範囲指定 (`pnpm add -D -E 'pkg@^X'`) で解決させた報告が届いた (実測)。minimumReleaseAge を明示すると strict になり、範囲指定の add は窓の内側で最新の版へ解決された。窓の外の新しい版は黙って外れる (実測)
- pnpm 11以降の設定の移行は、公開1日未満の版を exact pin した依存を置き、workspace の設定に1440で ERR_PNPM_NO_MATURE_MATCHING_VERSION で落ち、0で入る、を並べて確かめる。組込の既定も1440なので、「設定を消しても落ちる」は設定が読まれている証拠にならない (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ形の確かめ方が届いた。極端な値 (100年分) で解決が止まることと、本番の値で範囲内の最新版 (公開から1日) ではなく1つ古い版が選ばれることの両方で確かめた (実測)。範囲内に「待ち期間より新しい版」がちょうどある依存を update すると、選ばれた版そのものが minimumReleaseAge の効いている証拠になり、極端な値の変異と組み合わせると両方向の証拠になる (実測)
- minimumReleaseAge のあるリポジトリで「猶予を過ぎた最新へ上げる」とき、猶予期間の中にある新しい版の猶予明けを待つ必要はない。その時点で猶予を過ぎた最新の版に上げ、新しい版は猶予明けに Dependabot に任せると、作業が止まらなかった。待つ前提で計画すると作業が数時間止まる (実測)
- pnpm のメジャー更新を、猶予期間 (minimumReleaseAge) を過ぎた1つ前の版で隔離コピーにリハーサルし、猶予が明けた版を本番に適用する前にハマりどころを洗い出した (実測)
- pnpm 11以降は verifyDepsBeforeRun の既定が install で、package.json を変えたあとの pnpm run lint が lockfile を黙って書き換えた。error を明示すると、何も書き換えずに exit 1で止まる (実測)
- 報告者の提案: pnpm 11以降へ上げるリポジトリでは verifyDepsBeforeRun を明示する。lockfile の更新を明示的な install に限るなら error が合う
- verifyDepsBeforeRun は node_modules の同期の代わりにならない。workspace では package.json の mtime だけを見るので、lockfile だけが変わると古い node_modules のまま exit 0で走る。同期は frozen install を検査の先頭に置いて担保した (実測。委譲先が再現し、ソースで裏付けた)
- package.json の name を変えると、lockfile は変わらないのに verifyDepsBeforeRun が workspace structure has changed で pnpm run を止める。frozen のまま pnpm install で覚え直すと通り、lockfile の差分は0 (実測)
- workspace のリポジトリを別のディレクトリへ mv したあと、verifyDepsBeforeRun: error の設定で pnpm run が ERR_PNPM_VERIFY_DEPS_BEFORE_RUN (workspace structure has changed) で止まった。原因は node_modules/.pnpm-workspace-state-v1.json が各プロジェクトを絶対パスで持っていることで (node_modules の中で旧パスが残っていたのはこのファイルだけで、.bin を対照にした grep はヒットした)、rm -rf node_modules のあと frozen-lockfile の install で state が新しいパスで書き直されて通り、lockfile の差分は0だった (実測)
- `pnpm install --frozen-lockfile --workspace-root` (絞り込んだ install) は、lockfile が最新だと Already up to date で早く終わって state のファイルを書き直さず、state を消してからでも作り直さない (filteredInstall: true が残る)。移行スクリプトの最後に install を置くだけでは直らなかった (実測)
- 報告者の提案: ディレクトリを移す手順では、install の前に node_modules を消す
- pnpm 11以降の pnpm exec は、node_modules が無いか lockfile と合わないと、実行の前に黙って install する。pnpm deploy の出力先の pnpm-workspace.yaml は verifyDepsBeforeRun を引き継がないのでそこで install が走り、`pnpm --config.verify-deps-before-run=error exec ...` にすると、揃っていれば実行し、揃っていなければ止まる (実測)
- pnpm 12の --frozen-lockfile は install の対象に選んだプロジェクトの食い違いしか見ず、--filter / --workspace-root で絞ると他のパッケージがずれていても exit 0になり、pnpm deploy も package.json と lockfile の食い違いを見ずに lockfile の版を黙って入れる。lockfile 全体の食い違いは `pnpm install --frozen-lockfile --lockfile-only` で検査でき、node_modules を作らず数十ms で終わり、root でないパッケージのずれも ERR_PNPM_OUTDATED_LOCKFILE で止まる (実測)
- 報告者の提案: pnpm の workspace の CI と install のタスクは、絞った install の前に --frozen-lockfile --lockfile-only の検査を置く形をひな形にする
- `pnpm install --frozen-lockfile --workspace-root` で root だけを入れると、別のパッケージへ移した重い依存 (workerd など) が入らなくなる (実測)
- pnpm 12で `--filter <root でないパッケージ>` の install は root の依存も一緒に入れ、--no-include-workspace-root も効かなかった (実測)
- `pnpm --filter <pkg> deploy <dir>` は root の lockfile から対象のパッケージの依存だけを <dir> に入れ、<dir> に pnpm-lock.yaml を置く。トークンのあるジョブへビルドの依存を入れずに、デプロイ用の CLI だけを入れる用途に合う (実測。用途に合うという評価は推測)
- pnpm dedupe は devEngines.runtime の範囲も解決し直すので、Node の runtime の更新が無関係なコミットに混ざる。runtime を先に exact へ固定してから dedupe する (実測)
- package.json の devEngines.runtime に onFail: download を書くと、pnpm が lockfile に Node の版を固定して node_modules/.bin/node に置き、.bin の shim がそれを優先する。ホストの Node をセキュリティリリースへ上げても pnpm 経由は古いままで、audit も Dependabot も追わない (実測。pnpm exec node -v とホストの node -v が別の版だった)
- packageManager で固定した pnpm 自身は lockfile に入らず、pnpm audit の対象の外にある。固定版が古いと、pnpm 自身のアドバイザリが20件以上あっても気づかない (実測。件数は委譲先の照会による)
- pnpm audit の緑を疑って .modules.yaml と lockfile の日付と実際の版を突き合わせると、インストール済みの依存が lockfile より古いまま test と build が走っていた。audit は lockfile しか見ないので、検査の先頭に frozen install を置いて塞いだ (実測)
- 報告者の提案: Node のリポジトリのセキュリティ確認に、pnpm audit の外にある3つ (node_modules と lockfile の一致、devEngines.runtime が固定した Node、packageManager が固定した pnpm) を確かめる項目を入れる (根拠は直前の3項目)
- pnpm audit は依存を変えていなくても、advisory の追加で翌日に赤くなる。推移的な依存が子を exact pin していると親を上げても直らないので、overrides で `親>子: ^修正版` に寄せ、外す時機は検査できないので依存の更新を待つ Issue のタスクに持たせた (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ手当ての報告が届いた。上流の最新版でも推移依存の修正版に届かないときは、pnpm-workspace.yaml の overrides で下限を張る。直接依存と別系統の同名パッケージだけを持ち上げるには `'parent>child'` のセレクタを使う (直接依存の vite 8を縛らずに、vite-node が持つ vite 7だけを持ち上げた) (実測)
  - 2026-11-10の仕分けで、さらに別のリポジトリから、major の更新でも同じだった報告が届いた。依存の最新の major (exact pin を持つ CLI) に上げても、その CLI 自身が推移依存を exact pin しているので alert の大半が残った。major の更新で直るかは、写しで上げて同じ物差しで数えるまで分からない (実測)
- 脆弱性の対応で下限を上げた pnpm.overrides が、上流がさらに上の下限を宣言したあとも残り、上流の要求より古い版に固定し続けた。上限の無い override は、将来のメジャーを全依存へ強制する形でもある (実測)
- 依存の脆弱性のアラートが配信物に届くかは、`pnpm list --prod --depth Infinity --json` の木を名前で照合すると数えられる。本番の依存の既知の名前 (陽性の対照) と dev の木 (脆弱な名前が見える対照) を並べてから「0件」を読む (実測)
- `.cache/` の下に置いた隔離のディレクトリに専用の pnpm-workspace.yaml が無いと、pnpm (と corepack、`pnpm self-update`) は親の方向へ workspace を探してリポジトリの本体を操作の対象にし、本体の package.json の packageManager と lockfile を書き換えた。並列の調査エージェントで3回起きた。`.cache/` が ignore されていても、pnpm から見れば本体の一部である。git archive で作ったコピーのルートに専用の pnpm-workspace.yaml を置くと本体をルートと判定しなくなり、前後で本体の package.json と lockfile のハッシュを照合して確かめた (実測)。報告者の提案は、隔離コピーで pnpm を動かす手順 (調査エージェントへの指示を含む) に、この2点を必須として書くこと
  - 2026-11-10の仕分けで、別のリポジトリから同じ手順に要る別の注意が届いた。対照を作るために `.cache/` などリポの下の空のディレクトリへ package.json を置くと、`packageManager` が無いので corepack の固定ではなくホストの全体の pnpm (別のメジャー版) が走った。出力の末尾の「using pnpm vX」を読まないと、別の版の挙動を結論にしてしまう。写しには `packageManager` を揃える (実測)
- `pnpm audit --prod` は、lockfile の版を影響範囲内 (GHSA の vulnerable range の中) に書き換えた対照でも、その GHSA を報告しなかった。audit の0件を「抑止を外して安全」の根拠にする前に、検出できる対照が当たることを先に確かめる (実測1件、原因は未特定)
- pnpm audit の重大度ごとの件数は advisory と該当した版の組で数えるので、advisory の数と合わない。1つの advisory が2つの版に当たると2件になる。件数を突き合わせるときは `--json` の advisories と findings の版を数える (実測)。`pnpm audit` の表の出力は説明文が複数行に折り返すので行単位では集計できず、`--json` を使う (実測)
- `pnpm store prune` はどのプロジェクトからも参照されていないパッケージだけを消す。8.0G が6.8G になった (実測)
- pnpm 12で minimumReleaseAge を変えると、install の「Lockfile passes supply-chain policies (verified Nd ago)」のキャッシュが外れ、lockfile の全エントリを新しい値で検証し直す。変えたあとに frozen の install を1回打てば、新しい値で解決が止まらないかを確かめられる (実測。223件を10.7秒で検証し直した)
- `--frozen-lockfile` の install は解決を飛ばすので、minimumReleaseAge のような解決時の設定は評価されない。「install が止まらない」の緑は、陽性対照と並べて初めて設定が効いている証拠になる (実測)。pnpm 10.x で陽性と陰性の対照を並べて測った
- pnpm 12.9の frozen install は lockfile の各版を `minimumReleaseAge` で検査する。隔離コピーで値を1年にすると `ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION` で rc 1、元の値では通る。つまり CI の install でも、公開から日の浅い版 (Dependabot のセキュリティ更新など) は止まる (実測)。仕分けたセッションの解釈: 上の pnpm 10.x の項とは版が違い、frozen install が解決時の設定を見るかは版で変わったように読める
- Dependabot alerts の脆弱な range と pnpm-lock.yaml の版を semver で突き合わせ、「package.json の range の中の更新で消せる分」を測る物差しとして、HEAD の写しで引数なしの `pnpm update --lockfile-only` をかけた lockfile と alert の番号の集合を比べた (実測)。range 内の全更新をかけた写しの lockfile を物差しにすると、「range の中で直せるものが残っていない」を alert の番号の集合の一致で言える。件数だけでなく集合で比べ、変更前の lockfile で全件が当たる対照も並べた (実測)
- `pnpm why <name>@<version>` の出力で、ルートのパッケージの直下にある依存を数えると、残る脆弱な版がどの直接依存 (exact pin) から来ているかを件数で確定できる (実測)
- 別の lockfile を持つ pnpm の root (`--ignore-workspace` で動かすもの) では、pnpm-workspace.yaml の設定は読まれない。pnpm 10なら、その root の `.npmrc` の `minimum-release-age=` は読まれた (実測: 極端な値で止まり、外すと通る)
- Homebrew の pnpm が12系だと、`packageManager` で古い版へ切り替わる前に12の CLI が引数を読む。`pnpm update --depth Infinity` は12の側で「数でない」と拒まれる。`pnpm update` は既定で深さを限らないので、`--depth` を外せば推移的な依存も名前で解き直せた (実測)
- `packageManager` を持たない別の root (例: 仕様の道具だけを入れるサブディレクトリ) では、PATH の pnpm 12がそのまま動く。12は package.json の `pnpm.overrides` を読まないので、frozen でない install / update で lockfile から overrides が黙って消えた。frozen の install では表に出ない。node_modules が別の store の版 (v11) から入っていたことが証拠になった (実測)。報告者の提案は、「pnpm を使うリポジトリでは、別の lockfile を持つすべての root に packageManager を置く」を規約か検査に入れること (実測)

### Biome

2026-10-31に仕分けた分で届いた。

- biome 2.6は Markdown と YAML を既定で整形の対象にし、markdown.parser.frontmatter が既定で false なので、ハイフン3つで囲んだ frontmatter が区切り線と見出しに整形されて消える (status: open が見出しになる)。frontmatter を grep する仕組み (in-repo の Issue の status など) が黙って壊れ、lockfile も整形の対象に入って全体が書き換わった (実測)
- 報告者の提案: Markdown の整形を切るか frontmatter の解析を on にし、lockfile は files.includes から外す。これを biome を使うリポジトリの雛形や規約に入れる
- `biome check --write .` は git の ignore だけを除くので、未追跡のまま置いている文書も整形の対象に入る。整形の対象が広がる更新の前に、触ってはいけない未追跡のファイルのハッシュを取って前後で比べる (実測)
- Dependabot は biome の package.json だけを上げ、biome.jsonc の $schema の版を上げないので、biome の更新の PR は schema の不一致で赤くなる (実測)
- Biome の --config-path は設定のファイルではなく、設定を置いたディレクトリを受け取る。ファイルを渡すと設定エラーで止まる (実測)
- biome の correctness/noGlobalDirnameFilename は recommended に入っていないので、type: module のリポジトリでテストランナーが注入する __dirname に頼る書き方は、明示的に有効にしない限り lint を通る (実測。off で変異が素通りし、error で赤)
- E2E の spec が @playwright/test を直接 import することを Biome の overrides と noRestrictedImports で禁じ、includes を e2e の spec に絞ると、fixture の本体だけが import でき、違反する一時の spec は rc=1で止まる (実測)
- Biome (2.5.15) の GritQL プラグインで「as const と as unknown 以外の型アサーションを禁じる」規則を、コードの片 `$value as $type` だけで書くと、import / export の別名 (`{ a as b }`) も error にした。`$cast <: TsAsExpression()` でノードの種類に絞ると拾わなくなった (実測。契約テストの許す側に別名を置いて確かめた)
- biome 2.5.14から、HTML (Astro / Vue / Svelte も) で aria-label だけを持つアイコンのリンクを useAnchorContent のエラーにする (JSX と同じ判定)。リンクの中に視覚的に隠したテキストを置く形へ移すと通る (実測)。2.5.12からは noDescendingSpecificity の検出の範囲も広がり、別の要素どうしの比較が出る (changelog による)
- Biome の `// biome-ignore` をオブジェクトのプロパティの前に置いていたら、値の文字列が長くなって formatter が `key:` の次の行へ折り返したとき、抑制がプロパティ名の行に当たって空振りし、元の警告と `suppressions/unused` の2件が出た。抑制のコメントは、警告の出る式 (文字列そのもの) の直前の行に置く (実測)

### mise の lock

2026-10-31に仕分けた分で届いた。

- mise.toml を TOML として自前で解釈せず、`mise ls --local --json -C <repo>` で mise 自身のパーサの結果を読む。--local でグローバルの設定が混ざらない (実測)
- `mise lock --platform linux-x64,macos-arm64` は install せずに両方のプラットフォームの URL と sha256 を書くので、macOS で作った lock でも Linux の CI で照合できる (実測)
- 版を上げて mise install すると lock の全プラットフォームの行が新しい版に書き換わるので、手順は「mise.toml を直して mise install し、lock の差分も一緒にコミットする」で足りる (実測)
- 既定の locked=false の mise.lock は、版を上げて lock を作り直し忘れても rc=0で入れ、lock を黙って新しい hash で書き換える。--locked か MISE_LOCKED=1なら rc=1 (実測)
- lock の hash を1文字変えて新しくダウンロードさせると Checksum mismatch で rc=1になり何も入らないので、赤の対照に使える (実測)
- 入れ済みのツールは lock を照合し直さない。入れた後で lock を壊しても already installed で rc=0になり、cache から戻したツールは素通りする (実測)
- `locked = true` を mise.toml の settings に置くと、lock に無いツールの `mise exec tool@版` まで rc=1で止まるので、mise.toml の外のツールを mise exec で使うリポジトリでは置けない (実測)
  - 2026-11-10の仕分けで、別のリポジトリから射程の報告が届いた。`locked = true` は、プロジェクトの設定に書いてもグローバルの道具にまで効き、lock に無い道具で毎回警告が出る。範囲を絞る `locked_scopes` はプロジェクトの設定からは「セキュリティのため無視」される (実測)
- jdx/mise-action (v5.1.1) はリポジトリに mise.lock があると mise install に --locked を自動で足すが、その1回だけで MISE_LOCKED を後の step へ流さない。cache の key は mise.lock を含む (action のソースを読んだ。実行はしていない)
- 報告者の提案: CI の照合は自動の --locked に任せ、手元の作り直し忘れは lock の差分と CI の赤で捕まえる
- jdx/mise-action は version を指定すると mise の本体を埋め込みの minisign の公開鍵で検証し、cache から戻した mise も照合する。sha256 の入力を渡すと、minisign の検証が外れる (追加ではなく置き換え) (ドキュメントのみ。action のソースも読んだ)

### pre-commit と lefthook

2026-10-31に仕分けた分で届いた。

- pre-commit は hook がファイルを変えるとコミットを止め、lefthook の stage_fixed のように黙って stage し直さない。format の自動修正を確かめてから add し直す流れになる (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ挙動の別の面が届いた。整形の hook がファイルを直すとコミットが止まるのに、`git commit ... | tail -1` で結果を見ると止まったことに気づけない。コミットの後に git log で着地を確かめる (実測)
- lefthook が置く git hook は、本体が見つからないと警告を出して exit 0で終わるので、依存から外すだけだと gitleaks などの検査が緑のまま消える。外す前に lefthook uninstall を打つ (実測)
- 報告者の提案: lefthook から移る手順に、これを入れる
- pre-commit install は既存の他のツールの hook を .legacy へ退避して連鎖で実行するので、本体の無い lefthook の hook が退避されると exit 0のまま残る。--overwrite で置き換えると避けられる (実測。移行モードが既定であることはドキュメントのみ)
- lefthook から移した後も、prepare-commit-msg が lefthook のものとして残ることがある。pre-commit install --overwrite は default_install_hook_types の種類しか置き換えないので、ソースの読解で「作られない」と結論したレビューより手元の実物を優先し、消す前に中身を確かめた (実測。古い版が置いたというのは推測)
- `.pre-commit-config.yaml` に stage していない変更があると、pre-commit はコミットを拒否する。`-q` と出力の grep で絞っていたため気づかず、stage 済みのファイルが次のコミットへ混ざった。設定を変えるときは、設定の変更を stash してから他のコミットを作るか、設定のコミットを先にする。コミットの rc を必ず見る (実測)。unstaged の退避の挙動は ISSUE-88 の INS-72 にある

### PostgreSQL

- 「他の表を読まない」の pin は `pg_stat_xact_user_tables` の seq_scan + idx_scan で数えると効いた。`pg_stat_get_xact_numscans` は表の seq_scan しか数えず索引経由の読みを見落とす (実測、変異で確認)
- 空の表を外側に置く hash join は内側の表を開かないので、「読む」変異を join の形で作ると読みが起きない。読む変異は相手の表を起点に読む形で作る (実測)
- 並列の2セッションの検査で、B 側の SQL に「返った結果の語が期待と違えば独自の SQLSTATE で raise する」do ブロックを置くと、B の成否だけで返り値まで判定できる。判定の順序を入れ替える変異で赤になり、「例外は出ないが間違った値を返す」退行を捕まえた (実測)
- 2つの周期ジョブが同じ状態を逆向きに書く設計では、altitude の観点のレビューが「列は同じでも意味が違う」と根本を指した。意味をそろえると、周期の調整と特別な分岐がまとめて消えた (実測)
- PostgreSQL 16以降は lc_ctype と lc_collate が設定のパラメータではなく、current_setting('lc_ctype') はエラーになる。値は pg_database の datctype と datcollate から読む (実測)
- psql の \if と psql の変数で評価の切り替えを渡し、各切り替えの効き目を「その切り替えでだけ結果が変わるクエリ」で対照してから集計した (実測)
- RLS が有効でポリシーが0本の表は、GRANT を持つロールでも BYPASSRLS が無いと DELETE が例外なしに0行で終わる。前提の検査には GRANT と BYPASSRLS の両方を並べる (実測)
- RLS のポリシーで引数の無い stable の関数を (select f()) で包む書き換えの検査は、deparse の正規表現ではなく、pg_node_tree を括弧の深さで読み、FUNCEXPR の祖先に SUBLINK があるかで決めた。総数を pg_proc 側の集計と突き合わせ、節の数を2通りで数えて読み落としを例外にした (実測。式ごと包む形も数えられた)。別の報告では、RLS のポリシーの中の関数の呼び出しを、deparse した文ではなく pg_policy の式木 (pg_node_tree) の :funcid から数え、既知の2件を持つポリシーを対照にして数え方が死んでいないことを確かめた。式木に出るのは直接の呼び出しだけで、関数の本体からの間接の呼び出しは別に追う (実測)
- 報告者の提案: RLS を主な層にするリポジトリで、この検査をテストに固定する
- 書き換えの等価性は、後の deparse から包みを外すと前の deparse と一字一句同じになることで示せた。ロール・コマンド・permissive も前後でバイト比較した (実測)
- インデックスが選ばれる読み方では、stable の式は包む前から Index Cond として文ごとに1回だけ評価されるので、包んでも速くならない。効くのは Filter に落ちる読み方と、行ごとに呼ばれる関数の本体から届く呼び出しだけ (実測)
- migration の `ENABLE ROW LEVEL SECURITY` を grep して RLS 必須の表を導出する方法は、表の改名 (RENAME TO) を拾えず古い名前を残し続けた。RLS のポリシーの期待値を持つ検証スクリプトの表を canonical にする方がよい (実測)
- migration で関数を置き換えたときの照合として、migration の範囲の最後の create の本体の md5 と DB の md5(prosrc) を比べた。期待値の取り出しの正しさは、適用済みの環境で「後の側と一致し、前の側と不一致」を対照に確かめた (実測)
- HEAD の全 migration で状態を作るベンチは、後から入る migration のたびに状態の検査や fixture が壊れ、気づかれないまま止まっていた (無関係な FK の追加で止まっていた)。比べる版に固定すると壊れない (実測)
- 既存の migration を最終状態の DB へ流し直す冪等性のゲートを持つリポジトリで列を drop すると、その列を名指しする過去の migration (列の単位の grant など) の再適用が止まる。過去の文を「今ある列だけに与える」動的な形へ書き換えると順に流した結果を変えずに通せるが、適用済みの本文を変える判断は人に聞く (実測)
- seed が migration の後に表の権限を付け直す構成では、ローカルの DB で「拒否されない」は証拠にならない。migration の grant だけを当て直して測り、事後に relacl を事前と一致させる (実測)
- 書き手を問わず列を null にする BEFORE INSERT のトリガを足すと、テストの fixture でも「その列に値を持つ既存の行」を作れなくなり、既存の行を書き換える関数のテストが常に0件を返す。既存の行の書き換えは migration の述語つき UPDATE にして、テストはトリガの挙動だけを pin する形にした (推測。計画段階で advisor が指摘)
- テーブル単位の `pg_dump --schema-only` の diff は、列・制約・index・RLS の有効化・COMMENT・GRANT を1回でまとめて比べられ、手書きのカタログ問い合わせより取りこぼしが少ない。カタログ側の diff は作り直したオブジェクトの OID だけが変わるので、OID の列を伏せてから比べる (実測)
- pg_dump 18系の出力には `\restrict <鍵>` / `\unrestrict <鍵>` の行が入り、鍵が実行のたびにランダムに変わる。そのまま2回の dump を diff すると、スキーマが同じでも必ず差分が出る。`grep -v -E '^\\(un)?restrict '` で外してから比べる (実測。クライアント18.6、サーバ17.6)。報告者の提案は、DB のスキーマ比較の手順やスクリプトを持つリポジトリでは、pg_dump の `\restrict` 行を除く処理を最初から入れておくこと (実測)
- DROP の前に「対象に依存する repo の外のオブジェクト (view・外部キー・ポリシー) が0件」を pg_depend で確かめる SQL は、存在する表 (外部キーとポリシーが出る) と、rollback する transaction の中で作った view の2つを対照にして、拾えることを先に確かめてから本番相当の環境へ当てた (実測)
- 対象を `to_regclass(名前)` で引いて pg_depend と結合する検査は、対象がもう無い (NULL) と結合が空になり、依存0件と同じ形の空を返す。存在の有無と行数を同じ回で別に採ってから0件を読む (実測)
- 本番 DB へ Cloud SQL Proxy で入る手順で、proxy は `127.0.0.1:<port>` (IPv4) だけで待ち受け、同じポートをローカルのコンテナ (OrbStack) が `::1` (IPv6) で待ち受けていた。psql の `localhost` は IPv6 から試すので、本番ではなくローカルの DB へつながった。起動スクリプトは「ポート使用中」を警告したが、非対話モードで続行した。DB 名が違ったので落ちて気付けたが、名前が同じなら「本番を読んだつもりでローカルを読む」になる (実測)。報告者の提案は、DB へ proxy で入る起動スクリプトは、ポートの使用中を警告で続行せず止める側に倒し、接続先を `127.0.0.1` に固定すること (実測)。ポートの選び方は ISSUE-133 の「ホスト環境」節にある
- 実装役の「Postgres で default now() の列追加は表の書き換えを伴う」という主張を、同じ版の Postgres のコンテナで pg_relation_filenode の前後を比べて反証できた。now() (STABLE) では filenode が変わらず、対照の clock_timestamp() (volatile) では変わった。既定値の列追加の重さは、版と関数の volatility で決まるので、主張を見たら対照つきで測る (実測)

### Rust と依存の脆弱性

- Rust の依存は Dependabot のアラートだけでは足りない。GitHub の Advisory DB が RustSec の項目を全部は取り込んでおらず、Dependabot が1件しか出していない lockfile に cargo audit は22件を出した。直した証拠は件数ではなく advisory ID の集合で取り、期待した残りの集合と comm で両方向の差0を確かめた (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。Rust の依存は Dependabot と別に cargo audit で数え直す。Dependabot は GitHub がレビューしていない advisory には alert を立てず、RUSTSEC の多くはそこに入っていない。GHSA の alias を持つものでも `gh api /advisories/<GHSA>` が404を返した。あるリポジトリで Dependabot の open が0件の Cargo.lock に cargo audit が16件を出した (実測)
- 本番のバイナリに載るかを `cargo tree -i <crate> --edges normal` で見るときは、`--target <本番のトリプル>` を付けないと手元のホストのターゲットで解決される (実測)
  - 2026-11-10の仕分けで、別のリポジトリから同じ型の報告が届いた。実行時に載るかの判定は、Cargo なら `cargo tree --invert <crate> --edges normal --target <本番の triple>`。`--target all` だと本番では引かれないプラットフォーム固有の依存 (Linux 以外でだけ引かれるルート証明書の crate など) まで「載る」に見える (実測)
  - 2026-11-10の仕分けで、さらに別のリポジトリから、`cargo tree -e features` は辺の種類を置き換えず足すので normal・build・dev が混ざったまま出る、という報告が届いた。これだけを見て「dev-dependencies だけだから無害」と結論しかけた。本番で引くかは `-e normal` で別に見る (実測)。feature で API の有無が決まる脆弱性は、`-e normal` と `-e features -i` の2段で判定した
- `cargo update -p A` が「available: 新しい版」と言いながら手前の版で止まることがある。A の新しい版が別の推移依存の新しい版を要求していると resolver が手前で止める。先に要求される側を上げてから A を当て直すと届いた。rc 0 は届いた証拠にならないので lock の版を読む (実測)
- 報告者の提案: Rust を持つリポジトリでは、依存の脆弱性の定期点検に cargo audit (か cargo deny の advisories) を入れる
  - 2026-11-10の仕分けで、別のリポジトリから同じ提案が届いた。依存の脆弱性の棚卸しの手順に「Rust は Dependabot の件数を根拠にせず cargo audit で数え直す」と「Dependabot の件数は manifest と lock の重複を除く」の2点を入れる (実測)。重複の除き方は「GitHub の CLI とリポジトリの管理」節にある
- Rust の `std::time::Instant` は macOS ではスリープ中に進まない。同じ処理で、Instant で測った秒数と wall clock の差がスリープの区間と一致した。Instant を使うタイムアウトはスリープで誤発火しない代わりに、測った時間は wall clock より短く出る (実測)
- sqlx の query! を変える変異で、backend を権限の狭いロールの DATABASE_URL でオンラインビルドすると、他のクエリの describe が権限不足で落ちる。変異した SQL のキャッシュだけ owner のロールで prepare してオフラインでビルドすると、実行時のロールを変えずに回せる (実測)
- actix-web 4.x の Logger は、内側の middleware が Err を返すとアクセスログの行を出さないので、middleware が Err(ErrorUnauthorized) で返す401はアクセスログから消える。ログで数えたいなら req.error_response(..) などの応答として返す (ソースの LoggerResponse::poll を読んだ。実行はしていない)
- Cloud Logging では、Rust の tracing の JSON の行のメッセージが jsonPayload.fields.message に入り、textPayload の条件では一致せず0件になる。0件のとき、必ず当たるはずの過去の行 (時刻を絞った対照) も0件だったので、条件の誤りと分かった (実測)
- Rust で型がその trait を実装していないことを、impl の曖昧さで E0283 にして止められる。`const _: () = { ... };` の中で trait ごと作れば同じ型に何度呼んでもぶつからず、テストのモジュールに置くとカバレッジに未到達として数えられない (実測。仕組みの impl を外すと通ることまで確かめ、型の doc が実装しないと書いた trait を一覧に載せると載せ漏れの型が見つかった)
- rustdoc の警告を CI のゲートに入れるときは --document-private-items を付ける。付けないと非公開の項目の doc のリンク切れが -D warnings でも exit 0で通り、公開しない crate ではゲートが実質何も見ない (実測。付けると unresolved link で exit 101になり、壊したリンクの探針で赤を確かめた)
- private_intra_doc_links は [workspace.lints.rustdoc] に allow と書けば全 crate で1か所で黙る (各 crate が lints.workspace を継ぐ前提)。--document-private-items でも消えず、broken_intra_doc_links は warn のまま -D warnings で落ちる (実測)
- 報告者の提案: rustdoc のゲートの作り方を Rust の rules に足す
- Rust の std::env::VarError::NotUnicode(OsString) の Display は環境変数の生の値を出すので、thiserror の #[from] VarError や {0} で起動エラーへ埋め込むと、UTF-8 でないシークレットが値ごと起動ログに残る。変数名だけを持ち値を持たない独自のエラー型を返す読み取りの関数1か所に寄せて塞いだ (実測。修正前は単体テストの出力に値のバイト列がそのまま出た)
- 報告者の提案: Rust の規範 (panic 禁止、thiserror) に「VarError をそのまま通さない」を足す
- Rust の usize::from_str は先頭の + を受けるので、Content-Length のように数字だけを許す値は、解析の前に数字だけかを見る。テストに +1 が無いと、検査を外しても緑になる (実測)
- テストで expect() を使ったら、通常の test では通るのに、lint の段 (-D clippy::expect-used をコマンドラインで渡す) で初めて落ちた。unwrap_or_else(|e| panic!(..)) で文言を保った (実測)
- Result::unwrap_or_else の closure は Err を受けるので、Ok の値を panic に出す意図では型が合わずコンパイルが通らない。expect_err(&format!(..)) を使う (実測)
- エラーの判定を Display ではなく enum の payload で行った。ユーザー向けの文言にするため payload を Display に載せない variant があると、Display の部分一致は黙って外れる (実測)
- serde の #[serde(alias = "X")] で大文字と小文字の綴りを1つの欄に受ける形は、応答が両方の鍵を同時に持つと duplicate field で親ごと deserialize が落ち、1件でも両方を持つと配列全体が読めない。綴りごとに別の欄 (rename) で受けてから1つにまとめると直った (実測)
- Option<&dyn Trait> を await をまたいで持つと future が Send でなくなり、multi_thread の runtime で使う呼び出し側がコンパイルできない。dyn Trait + Sync の境界が要る (実測)
- embedded replica で「transaction の中の読みが primary に行くか」を、read-your-writes で毎文 pull する接続の上で判別した。毎文のあとにローカルへ pull する接続では件数の比べ方は判別力を失い、pull で消えない差 (ローカルにだけある TEMP 表、transaction の中の自分の未コミットの行、BEGIN の後に別の接続がコミットした行) を見ると経路が判別でき、対照を本命より先に assert した (実測)
- libsql の1本の Connection を RwLock の読みロックで共有して複数のスレッドから読むと、文の形によって毎回 SIGSEGV になった。下層が serialized を保証していても、ラッパの層で同じ接続を並行に使うのは安全ではない (実測。Mutex で直列にすると9/9緑、読みロックに戻す変異で3/3 SIGSEGV。正確な機序は未特定)
- 報告者の提案: 接続を直列にするか、分ける規約にする
- Windows ARM の検証 VM でしか見ていなかった非決定的なクラッシュが、Mac のストレステスト (32タスク×300回、1〜2秒) で決定的に再現した。再現テストは、そのまま回帰テストとして残せる (実測)
- 静的にリンクして配るアプリで、標準ライブラリが内部で取り込む crate を、rust-src の `library/` を同梱の `library/vendor/` へ向けた `cargo metadata --offline --locked --filter-platform <triple>` で列挙した。`library/` の Cargo.toml は nightly の cargo-features を宣言するので、stable の cargo では `RUSTC_BOOTSTRAP=1` が要る (実測)
- 標準ライブラリの依存の解決だけでは一覧が合わない。配布物は `backtrace` の feature 付きで組まれており、feature を付けないと addr2line・gimli・object・miniz_oxide などが解決から消える。逆に、ワークスペースの feature の統合で、rlib の無い crate (例: hashbrown の既定の hasher) が解決に出る。rustup が配った `lib/rustlib/<triple>/lib/*.rlib` の実物を正とし、解決と両側から突き合わせると決まる。rlib の側に在って解決にも既知の「リンクされない rlib」(test、getopts、proc_macro など) にも無いものが出たら止める (実測。feature を外す変異で、6 crate を名指しして止まった)
- ライセンスの一覧の照合 (`--check`) を、rust-src の無い CI でも回る形に保てた。標準ライブラリの一覧は toolchain の版の関数なので、生成物に版を pin し、版の一致を見るだけで済ませる (実測)
- cargo の古いライセンスの綴り `MIT/Apache-2.0` (斜線) は、SPDX の `OR` だけを読む選び方では扱えない式に化け、生成が止まる。標準ライブラリが取り込む crate の中に、今もこの綴りがある (実測)
- 報告者の提案: 静的にリンクする成果物のライセンス表示を生成するリポジトリでは、cargo の依存に加えて、標準ライブラリの vendor の crate を、配られた rlib との突き合わせで数える手順を共通の手当てにする。生成物の中身を守るテストの穴は ISSUE-88 の INS-82
- cargo-audit は `.cargo/audit.toml` の `[output] deny = ["warnings"]` で unmaintained / unsound でも止められる。ignore から1件外すと ID を名指しして exit 1になることで、設定が読まれていることを確かめられる (実測)。cargo-audit 0.22.0は `[output]` を置くと `quiet` を必須にし、無いと設定の parse で落ちる。上流の example の設定ファイルにはその注記が無い (実測)
- 依存の既知の脆弱性の検査 (cargo-audit と pnpm audit) を just のターゲットにし、上流を上げる前のツリーで赤を記録してから上げる順で陽性対照を作った (実測)
- cargo llvm-cov の JSON から未到達の region を拾うとき、関数の写しごとに拾うと数十件に見える。同じ (開始行, 開始列, 終了行, 終了列) を持つ region の実行回数を全ての関数の写しで合算してから0のものを拾うと、ゲートの報告と同じ件数 (1件) になった。region の種類 (配列の8番目) が0のものだけを数える (実測)。報告者の提案は、この手順を references に置くなら「region の座標ごとに全ての写しの回数を合算してから0を拾う」を前提として書くこと (実測)
- 依存先のリポジトリの [patch.crates-io] は依存する側に効かないので、必要な patch (zed なら async-task の fork) はルートの Cargo.toml に写し、Cargo.lock で fork の rev に解決されたことを確かめる (実測)。GPUI の取り込みは GPUI の節にある
- Cargo の feature を `--all-features` で回す check がある構成で、新しい feature の中で `env!` を使うと、その環境変数を設定しない check が全部コンパイルで落ちる。値はソースの定数に置き、外の道具はソースから読む形にした (推測。実装前)

### GPUI

2026-11-10に仕分けた分で届いた。

- GPUI は zed の公式リポジトリのリリースの rev を git 依存で固定し、toolchain をその rev の rust-toolchain.toml と同じ版にするとビルドが通った。crates.io の gpui は2025-10から止まっていて、gpui_platform は publish = false で crates.io に無い (実測)。crates.io・第三者の出し直し・公式の git rev の3つを比べた。patch が推移的に効かない件は Rust の節にある
- GPUI は前面にない窓を既定で33.3ms (30fps) に間引く (WindowOptions::inactive_frame_interval)。ターミナルから起動した窓は前面に来ないので、描く仕事が軽くても30fps しか出ない。測るときは inactive_frame_interval を None にするか、終了時に is_window_active を出して条件を記録する (実測)。報告者の提案は、GPUI を使うプロジェクトの測定の手順に「窓が前面か (is_window_active) と inactive_frame_interval を結果に書く」を入れること (実測)
- uniform_list の processor は、行の高さを測るために先頭の1行 (範囲 0..1) だけで呼ばれることがある。processor の range を「見えている範囲」と取ると毎フレーム揺れる。見えている範囲はスクロールの offset と viewport の高さから自分で計算する (実測)
- GPUI のアトラスは RenderImage の Arc を捨てても空かない。Window::drop_image を呼ばないとメモリが増え続ける (実測)

### Supabase CLI と外部サービスの CLI

- Supabase CLI の stack モードのネイティブのランタイム (Docker なしのローカル実行) についての報告 (ドキュメントのみ) は、コンテナランタイムの移行の前提に触るので ISSUE-118 に置いた
- 報告者の提案: CI のために Supabase を立てる目的なら、Docker のランタイムの `supabase start` の費用を先に見積もる。ネイティブは費用を下げる手段で、CI で Supabase を立てる前提を新しく作るものではない (ドキュメントのみ)
- 一晩置いた開発環境で、Stripe CLI の `stripe listen` が OAuth トークンの期限切れで終了していた。E2E の前提チェックが待受の生存を見ていたので気づけた。再ログインにはブラウザでの承認が要るので利用者に頼む (実測)
- Supabase CLI の config.toml の `port = "env(VAR)"` は整数として読まれ、整数でない値も未設定も CliConfigParseError で止まる (fail-closed)。supabase/.env も自動で読むが、範囲外の値は読み込みの段では止まらない (実測。隔離したコピーに supabase status --workdir を当てて読み込みの段だけを確かめた)
- Supabase で Data API を OFF にすると、PostgREST が番兵の schema 名で schema cache を読みに行き、postgres_logs に 3F000 の ERROR が毎時数件出続ける。害は無く、消すには schema の公開が要るので放置が妥当で、ログ監視の除外条件の候補になる (推測。ログの属性から読んだもので、周期の原因は未確認)
- Supabase の hosted で postgres は一部のシステム表の持ち主ではないが、supautils.policy_grants がそのポリシーの作り直しを許している。持ち主の判定だけで作り直せないと結論せず、この設定を読む (実測)
- Supabase の Management API の billing/addons で計算資源を変えた直後に PITR を選ぶと、400 Project is not in a healthy state で返る (再起動中)。変更と PITR の選択は分け、PITR は数分おきに再試行する。add-on の変種の識別子は .variant.id に入る (実測)
- Supabase の Management API の OpenAPI は各 operation に x-fga-permissions (fine-grained token の権限名) と x-oauth-scope を持つので、陰性の対照に使う GET がどの権限群に属するかを推測でなく引ける。Auth の設定の書き込みに project_admin_write が要るので、構築用の PAT は事実上プロジェクトの管理者になる (実測。内側のリストを AND と読むのは仮説で未確認)
- 報告者の提案: PAT を権限で絞る作業では、対応表を書く前に OpenAPI を引く
- テスト用のメール受信サービスで確認コードを取る処理が「待ち受けの起動の数秒前より後のメール」だけを見る形だと、人が先に送信すると永遠に拾えない。待ち受けを先に起動してから、合図して押してもらう順序に固定する (実測)
- ある認証サービスで、ユーザーを Backend API で削除したあと端末の資格情報でフロントの API を叩くと、client の取得は401ではなく200でセッションが空になり、所属の一覧は401になった。端末からは普通のサインアウトと区別できないので、「アカウントが消された」は secret を持つ backend で確かめる (実測。dev のインスタンスで1回ずつ)
- Resend の送信の一覧の API は full_access の鍵が要り、送信専用の鍵では401 restricted_api_key になる。読み取りだけの権限が無いので、人の目視に倒した (ドキュメントのみ)
- 報告者の提案: 道具を作る前に、API が要る鍵の権限をドキュメントで見る
- `supabase db push` は未適用の migration を全部流すので、1つの PR の中で「フロントを出してから revoke」のように配信の段を分けられない (実測)。計画の並列レビューで前提を疑う観点だけが出した穴で、レビューの形は ISSUE-133 の「Claude Code の hook と委譲」節に置いた
- ローカルの Supabase Realtime は、E2E の beforeAll で psql から入れた行を、ページの購読の後に配ることがある (届く件数は実行ごとに変わる)。届いた行がクライアントの状態に入り、画面の判定 (「データあり」) が変わって、取得の失敗を見るつもりの E2E が偽の緑になった。理由は報告者の推論で、共有のレプリケーションのスロットをポーリングしているためと見ている。行が届いたこと自体は実測 (実測)。報告者の提案は、E2E を作る手順に「DB へ直接入れた fixture は Realtime で後から画面に混ざりうる」を足すこと (実測)

### Vercel

2026-11-10に仕分けた分で届いた。Vercel CLI の engines の解釈は GitHub Actions と Node の版の節にある。

- Custom Environment に紐づく環境変数は、API 上 `target` が空で `customEnvironmentIds` だけを持つ。管理画面で見つけにくいのはこのためで、REST なら `target` が空かつ `customEnvironmentIds` が1つだけの行で絞れる (実測)
- 変数が複数の env にまたがっている行を対象から外す (target がちょうど1つの行だけを消す) と、消すことで別の env を巻き込む事故を構造的に避けられる (推測)
- team で Member の権限だと、アクセストークンの scope に team が出ず、project 単位でしか作れなかった。しかも1つのトークンに複数の project を載せられず、project ごとに1本ずつ要った。REST のスクリプトは project ごとにトークンを使い分ける形にする必要がある (実測)
- CLI の認証ファイルのトークンは数日で403になっていた。CLI を依存から外したリポジトリでは、REST を手元から叩くたびに短期のトークンを作り直す運用になる (実測)。原文は事業者名を書いていないが、同じ報告の文脈からここに置いた

### LLM を組み込む機能

2026-10-31に仕分けた分で届いた。

- LLM の生成機能の回帰評価に命令に見える入力のケースを足すと、乗っ取りは0件でも、偽の区切りで入力を取り落とす形と「出力は空でいい」に半分従う形が出た。乗っ取りの有無だけでなく、出力が壊れる形も数えると守りの穴が見える (実測)
- LLM の審査役は攻撃の文面も読むので欺かれうる。出力に system プロンプトの20文字以上の文が逐語で出たかの照合を別に持つと2層目になり、その照合の段が変異注入で pin されているかを確かめると、1つ目の書き方では抜けていた (実測)
- 入力を素の文字列ではなく JSON の文字列の値として user メッセージに載せ、system で値は全部対象と定めた (推測を含む。効果は再評価の結果待ち)
- 報告者の提案: LLM へ利用者の入力を渡す機能の規約に、「入力の側から閉じられない符号化で渡す」と「回帰評価に命令に見える入力を持つ」を足す

### 正規表現の計算量

- `/\s*[\r\n]\s*/g` のような「空白の並び、区切り、空白の並び」の正規表現は、区切りを含まない長い空白で位置ごとに後戻りして、長さの2乗の時間になる (64,000文字で7秒台)。先頭に後読み `(?<!\s)` を足して照合の始まりを空白の並びの先頭に限ると線形になり、結果は変わらない (実測)。入力の検査より前に正規化を置く変更の観点は ISSUE-133、処理時間の上限の pin の形は ISSUE-88 の INS-21
- JS の正規表現で Unicode の範囲を書くとき、`\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}` と `u` フラグで書くと、16進のエスケープを使わずに済み、Edit ツールでもそのまま残る。範囲の意図も読める (実測。書き換え後のファイルを grep して確かめた)。16進のエスケープが Edit ツールで生の文字に化ける件は ISSUE-133

### Windows と MSI

2026-10-31に仕分けた分で届いた。

- 同じ版数の MSI の上書きは、MajorUpgrade で ProductCode が毎回変わるので旧製品の削除から新しい ProductCode でのコピーになり、REINSTALLMODE=amus で同じ版でも置き換わる。証拠はインストール先の exe のハッシュが前のビルドと違うことで、1638は ProductCode が一致したときだけ出る (実測。exe のハッシュと詳細ログで確かめた)
- 操作の前に取ったクラッシュダンプとイベントの件数をベースラインにし、操作の後に増えていないことで異常終了しないと判定し、プロセスの起動時刻が変わらないことで途中の再起動を除いた (実測)
- オフラインの起動で「ある処理が走らない」ことの判定は、ネットワークを戻す前にゲストの中のスクリプトでログを数えると、まだ走っていないだけの場合と区別できる (実測)
- ssh の既定のシェルが cmd の Windows のホストに `pwsh -Command "... | ..."` を送ると、パイプを cmd が解釈して壊れる。スクリプトのファイルを送って `pwsh -File` で走らせると確実 (実測)
- PowerShell で `$home` を変数名に使うと、読み取り専用の自動変数 `$HOME` と大文字小文字を区別せずにぶつかる (実測)
- PDB の無いリリースビルドのクラッシュを、イベントログのフォールトのオフセットと exe の逆アセンブル (llvm-objdump、ImageBase + オフセット) で調べ、落ちた命令の並びの形から埋め込みの DB の割り当て関数を特定した。最寄りのシンボル名は無関係な名前が付くので信じない (実測)
- 報告者の提案: PDB を artifact に残さないリリースビルドでも、命令の形で特定できない場合に備えて、PDB を別の保管先 (CI の非公開の artifact など) に残す運用を検討する (推測)

### Tauri と WebView2

2026-11-10に仕分けた分で届いた。E2E で Tauri のアプリの WebView2 へ Playwright を CDP でつなぐ経路の報告で、後の報告が前の報告の結論を覆している。

- Tauri 2のアプリは WebView2 に自分の引数 (`--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection`) を渡すので、環境変数 `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=...` を付けて起動してもポートは開かない。WebView2 のブラウザのプロセスの引数を `Win32_Process.CommandLine` で読んで確かめた。CDP で E2E をつなぐなら、アプリ側の `additional_browser_args` に足すビルドの構成が要る (実測)。最後の結論は下の HKCU の policy の項が覆している
- Tauri v2 (wry 0.55) の WebviewWindowBuilder::additional_browser_args は、値を渡すと WebView2 の既定の引数に足すのではなく置き換える (wry の webview2/mod.rs の unwrap_or_else)。CDP のポートだけを渡すと既定の無効化が黙って外れる (ソースの読みのみ)
- 環境変数 WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS は、親のプロセスで設定して直接起動しても効かなかった (Microsoft の文書は環境変数とレジストリを並べて「追記される」と書いているが、環境変数の側は外れた)。HKCU の policy (`Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments` に、値の名前を実行ファイル名、値を `--remote-debugging-port=<N>`) は、Tauri の既定の引数の後ろに追記されて CDP が開いた (実測、Windows 11 ARM の WebView2 156)
- 報告者の提案: E2E の生成の手順の参照に、Tauri (WebView2) のアプリへ Playwright を CDP でつなぐ経路として「HKCU の WebView2 の policy で開く。環境変数は効かない。additional_browser_args は既定を置き換える」を足す。Tauri のアプリを持つリポジトリで同じ遠回りを踏みうる (原文に根拠の札は無い)

### その他のツール

- 1Password CLI の `op read 'op://<vault>/<item>/<日付の欄>'` は、画面の表示ではなく UNIX 時刻の秒 (10桁の整数) と改行を返す。期限を判定するコードは秒の整数を読む前提で書く。値の形は実物を1回読んで `od -c` で確かめる (実測)
  - 2026-11-10の仕分けで、別のリポジトリから、`op read` は末尾に改行を付けるので `gh secret set` へパイプで渡すときは `op read -n` を使う、という報告が届いた。改行が値に入るかは未確認で、安全側に倒した (推測)。`op read -n` を `gh secret set` へ渡して値を出さずに入れる形は ISSUE-133 の秘密の値を出さない箇条の子にある
- 依存の柵 (特定のライブラリを import してよいのは1パッケージだけ) は、設定ファイルの文字列ではなくビルドツールが出す依存グラフの JSON (辺ごとに source / test の種類つき) で検査できる。標準ライブラリに同梱されたパッケージは依存グラフの JSON に現れないので、それへの直 import は柵で見えない (実測)
- mise の `github:` backend で入れた単体バイナリの CLI が npm パッケージを `deno compile` したもので、gRPC クライアントが Deno の node:http2 互換層の上で動いていた (実測。導入時の確かめ方は ISSUE-133)
- pnpm 10の「Ignored build scripts: <pkg>」の警告は、install に `--ignore-scripts` を付けると消え、lockfile も変わらない。設定ファイルの側 (package.json) で消す方法もあるが、その package.json をキャッシュの指紋に入れていると長い検査をやり直すことになるので、フラグの方を選んだ。消せることは、付けない対照で1件出て、付けた形で0件になることで確かめた (実測)
- 1Password CLI の読み出しが authorization timeout で2回続けて落ち、デスクトップアプリのアンロックをユーザーに頼むと通った (実測)
- 1Password でアーカイブしたアイテムは `op read op://...` では読めず、失効の確認にならない。`op item get <item-id> --vault <vault> --include-archive --fields <field> --reveal` なら読めるので、失効の確認は読めた長さと HTTP のコードだけを出す形にする (実測)
- 報告者の提案: 秘密を扱う手順書に、アーカイブしたアイテムの読み方を載せる
- 1Password のアイテムは vault をまたいで移すと ID が変わりうるので、`op://<vault-id>/<item-id>/<field>` の参照が「どこにも無い」になったら、まず別の vault でタイトルを引く (推測。ID が変わった経緯は確かめていない)
  - 2026-11-10の仕分けで、別のリポジトリから公式ドキュメントによる裏付けが届いた。item を別の vault へ移すと item の ID が変わり、ID で書いた op:// 参照は全部切れる。service account の vault の権限は作成後に変えられず、後から読める vault を絞るには作り直しになる (ドキュメントのみ。1Password の公式ドキュメント)
- `op item get` の失敗の出力を jq に渡すと、空入力で jq が rc 0を返し、`|| echo not found` の分岐に入らなかった (実測)
- S3 互換のストレージの DELETE が存在しない key に204を返すかは、curl の --aws-sigv4 で1本叩き、同じ認証での一覧の取得 (200) を対照に並べて確かめられる (実測)
- just はレシピの直前の最後のコメントの行を `just --list` の説明に使うので、理由のコメントを書くと説明の欄が崩れる。要約は `[doc("...")]` の属性に分け、コメントは理由だけにした (実測)
- justfile の構造は `just --dump --dump-format json` で取れ、recipe ごとの依存 (priors 付き) と本体の行が返るので、regex で text-parse しなくて済む。CI に just が無いなら taiki-e/install-action で公式のリリースを入れる (実測)。ISSUE-88 の INS-57 と同じ手法
  - 2026-11-10の仕分けで、別のリポジトリからこの手法の落とし穴が届いた。`just --dump --dump-format json` はレシピ本文の `\` で続けた行を別々の行として持つ。行単位で「この呼び出しの行が X を含む」と見る検査は、続きの行に置かれた X に届かず緑のまま通った。本文全体で見る形に変えると赤になった (実測)
- CJK の Markdown で閉じない太字を探すとき、正規表現ではなくリポジトリが使う CommonMark の実装で描画し、残った太字の記号を旧版と新版で数え比べた。壊れるのは、太字の内側の端が約物で外側に文字が続く形だけだった (実測。正規表現は誤検出だらけで、描画なら対照付きで判定できた)
- 報告者の提案: CJK の文書を扱うリポジトリ向けの検査の候補にする
- 有界の探索で状態の上限に達したときに precondition で process ごと落とすと、同じ実行の他のテストの結果と要約の行が消える。印を立てて探索を止め、Issue.record でそのテストだけを落とす (実測)
- macOS の Parallels VM のアプリを人手なしに動かすには、ホストの `prlctl send-key-event` (PC のスキャンコード) が使えた。ホストの仮想キーボードとして届くのでゲストの TCC (アクセシビリティ) の許可は要らない。ゲスト内の osascript / System Events はこの許可が要る (実測)
- `prlctl send-key-event` にマウスのイベントは無い。WKWebView の Tab はテキスト欄と select にしか止まらず、Alt (0x38) を押しながらの Tab でもボタンへ移らなかった。ボタンを押す操作は人手が要った (実測。Option が届いていないのか WKWebView が見ないのかは未切り分け)
- 仕分けたセッションの解釈: 上の2件は agentic-coding-tools の macos-vm-verification の skill に関わる。報告者は skill への提案をしていない
- 1Password の API Credential 型の項目は、値のフィールド名が `credential` になる。参照は `op://<vault>/<item>/credential` で、`op read ... > /dev/null` の終了コードで値を出さずに存在を確かめられる (実測)
- fontTools (varLib.instancer と pyftsubset) の出力は書き出した時刻を含むので、SOURCE_DATE_EPOCH を固定すると作り直してもバイト列が一致する (実測)
- `ast-grep scan` は severity が error 以外のルールの違反を見つけても exit 0で終わる。`--error` を付けると全ルールを error として扱う (実測)
- `jq empty` は空のファイルと、値を2つ並べたファイルを通す。`jq -n '[inputs] | length'` が1であることを見る (実測)
- APM でサブディレクトリの skill を巨大なリポジトリから取ると、初回は190秒かかったが、残るのは124KB だった。2回目はキャッシュで0.2秒 (実測)

### 地理データの処理 (osmium)

2026-11-10に仕分けた分で届いた。

- osmium tags-filter で候補を先に切り出すと、2.5GB の国単位の pbf でも数十秒で31MB の pbf になり、その後の export と集計はホストを圧迫しない大きさになる (実測)。export と集計はメモリ上限付きのコンテナで回した
- osmium export の geojsonseq は、閉じた way を LineString と MultiPolygon の両方で出す。そのまま数えると面の件数が二重になる。LineString を落としてから数える (実測)

### Quint と仕様のモデル化を支援するツール

2026-11-10に仕分けた分で届いた。後半の項目は、仕様言語のモデル化を支援するツール (デスクトップのウィンドウと MCP サーバーの2経路を持つ) の、報告の時点の版の話。

- Quint 0.33の `--backend rust` は初回に評価器を checksum なしで GitHub から取ってくるが、`~/.quint/rust-evaluator-v<版>/quint_evaluator` に先に置けば取りに行かない (プロキシを壊した HOME で確かめた)。typescript の backend は25倍遅く、仕様4本で160秒かかった (実測)
- そのツールを初めてリポジトリに当て、ウィンドウからのスキャンと MCP からの run の開始の両方を通した (実測)
- ウィンドウで始めた run はダッシュボードに running と出るが、MCP の run の一覧には出ない。進み具合はツールのデータディレクトリにあるサーバーのログが唯一確かな観測点で、tail -F に grep をかけて Monitor で見張れる。ただし intent 段階は1ファイルごとに進行の行が1行出るので、それを除外しないと通知が溢れて抑制される (実測)
- MCP から始めた run は、ウィンドウの run が Anthropic のモデルで動いていても、データディレクトリのモデル割り当てが空だと別の提供元 (Codex) へのサインインを要求して即座に失敗する。決定的なので再試行は無意味。設定の画面で推奨のモデルを選び直しても、保存されるのは空の上書きで、MCP の経路は変わらず失敗した。画面に推奨と出るモデルは表示時に計算される既定値で、空の上書きをウィンドウの経路は Anthropic に、MCP の経路は Codex に解決している様子 (報告者はツール側の不具合の疑いと書いている)。回避はウィンドウから run を始めて、結果を MCP で読むこと (実測)。報告者の提案は、そのツールを他のリポジトリへ展開する前に、MCP の経路で run が1回通ることを確かめる手順を足すこと。Codex を使わない環境では、現状 run はウィンドウから始める運用になる (実測)
- 同じツールの CLI の status は、ウィンドウのサーバーが正常に動いている状態でも、サーバーの実行ファイルを見つけられずに No such file or directory のエラーで provider と usage の行を出せなかった。実行ファイルはデータディレクトリの bin/ にあり、CLI がそれを見つけられていない様子 (報告者はツール側の不具合の疑いと書いている) (実測)
- そのツール向けの skill は、手順 (setup → ランク付け → run の開始) と troubleshoot の表が丁寧で、エラー文言から該当行を引ける。一方で「ウィンドウの経路は動くが MCP の経路だけ provider で落ちる」状態は表に無く、自分で両経路を通すまで分からなかった (実測)
- コンポーネント1つのモデル化を始めても、最後のスキャンからツリーが変わっていれば、先にリポジトリ全体のスキャンと intent 抽出がやり直される (その報告では intent の reader が約450、agent のセッションが1秒で80超)。開発中の作業ツリーで裏で回すとそのたびに全体を読み直すので、ツリーが落ち着いた時点 (PR の前など) に回すのが向く (実測)
- スキャンが作るコンポーネントマップは、テストファイルを本体と別のコンポーネントへ割り当てることがある (例: backend のエンドポイントのテストが desktop 側のコマンドのコンポーネントに入った)。ランク付けに使う前に、変更の多いコンポーネントに割り当てられた本体とテストのパスの一覧を目視する (実測)

### CodeSandbox で上流への再現を作る

2026-11-04に仕分けた分で届いた。上流の OSS への Issue の Bug Report テンプレートが求める「動かせる最小再現へのリンク」を、CodeSandbox に API で作った報告。旧系統の define API と、SDK API の `POST https://api.codesandbox.io/sandbox` の両方を試している。

- SDK API の `POST /sandbox` に `{title, privacy, template, files: {path: {code}}}` を送ると、API トークンが紐付くチームのワークスペースにサンドボックスができる。define API で作ったものは匿名になり、チームの一覧に出なかった (実測)
- ブラウザで動かすだけの再現は `template: "static"` と import map で esm.sh の版を固定するのが確実だった。bundler に依存しないので、Preview を開いた瞬間に結果が出る。作る前に手元で `python -m http.server` で配信して、実ブラウザで同じ結果になるのを確かめてから1回で作った (実測)
- 再現の台本はバグの実行と、原因の手順だけを外した対照の実行の2本を並べて出す形にした。メンテナが一目で原因の手順を特定できる (実測)
- `POST /sandbox` で `template: "vanilla"` を渡すと500 (Internal Server Error) になった。Vanilla テンプレートの内部名は `parcel` (実測)
- API で作るときは `sandbox.config.json` の template が無視され、本文の `template` だけで決まる。未指定だと package.json の scripts から nodebox と推定され、台本が実行されない (実測)
- `parcel` テンプレートは CodeSandbox 側の babel-transpiler の worker が NetworkError で読めず、Preview が止まった。CodeSandbox 側の問題か閲覧側の問題かは切り分けていない (実測。原因は推測)
- define API で `"template": "node"` を指定しても Browser Sandbox になり、ターミナルが無い。Browser Sandbox から VM Sandbox へ変換する節は公式ドキュメントでコメントアウトされていた (実測 / ドキュメントのみ)
- CodeSandbox の API にはサンドボックスを消す手段が無く、試作のたびにダッシュボードで手で消す手間が出る (ドキュメントのみ。OpenAPI に DELETE が無い)
- codesandbox.io の UI と公開 API は WebFetch や curl だと Cloudflare の403になる。ドキュメントは GitHub の `codesandbox/docs` のソース、API の仕様は `codesandbox/codesandbox-sdk` の `openapi.json` から読める (実測)
- 報告者の提案: 上流への Issue の再現を作る手順 (チームに作る API、static + import map、手元で確かめてから1回で作る、バグと対照を並べる) を、OSS へのバグ報告を支援する skill の候補として検討する (実測)。skill を作るなら置き場は agentic-coding-tools になる (仕分けたセッションの解釈)
- Preview の確認に claude-in-chrome を使った報告は「Playwright Test Agents とブラウザの MCP」節に置いた

## タスク

- [ ] 項目ごとに、dotfiles の references へ入れる価値があるか (どのリポジトリの作業で読まれるか) を決める。入れないものは理由を書いて落とす
- [ ] 入れるものは references のどのファイルに置くかを決め、版や仕様に依存する記述には届いた日付を残す
- [ ] 技術領域ごとの references を dotfiles に持つか、各リポジトリの CLAUDE.md や skill に持たせるかを決める (ISSUE-97 の配る対象の棚卸しと重なる)
- [ ] private のリポジトリの Pages と gh-pages の残りを確かめる手順を、どこかの棚卸しに入れるかを決める
- [ ] グローバルの gitignore に `.playwright-mcp/` を足すかを決める

## 関連

- ISSUE-133: 同じ受け箱から届いた、技術領域に閉じない知見
- ISSUE-97: 集めた知見を磨いて配る工程
- ISSUE-88: 検査と変異注入の知見。このファイルの項目のうち pin の作り方にあたる部分は ISSUE-88 の INS-8 / INS-19〜21 / INS-23 / INS-27 / INS-57 / INS-72 / INS-77 / INS-79〜82 にあり、各項目の末尾から番号で参照している
- ISSUE-118: コンテナランタイムの移行。Supabase CLI のネイティブのランタイムの報告を置いた
- ISSUE-136: global の mise に `.node-version` を読ませるか
- ISSUE-101: apm の pin の遅れの告知。github-actions の ecosystem で Dependabot の cooldown が使えない件を参照した
- ISSUE-124: apm-install-guard の誤検知。Python の shlex の項から参照した
