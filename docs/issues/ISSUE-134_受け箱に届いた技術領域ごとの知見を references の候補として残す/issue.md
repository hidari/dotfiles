---
status: open
---

# docs(references): 受け箱に届いた技術領域ごとの知見を references の候補として残す

## 背景

2026-10-21 に受け箱へ届いたまとめのうち、特定の技術領域に閉じた知見をここへ残す (ユーザー決定 2026-10-22: 技術領域に閉じた知見も捨てずに1本にまとめる)。どの領域にも閉じない知見は ISSUE-133 へ分けた。

どれも他のセッションの報告で、dotfiles では再現していない。根拠は報告者の申告 (実測 / 推測 / ドキュメントのみ) をそのまま書く。版や仕様は届いた時点 (2026-10-21か2026-10-22) のもので、古びる。2026-10-22に届いた7件から足した分は、各節の末尾と、新しく立てた節に置いた。2026-10-23に仕分けた5件から足した分も、各節の末尾と、新しく立てた GitHub の節に置いた。2026-10-31に仕分けた72件 (届いたのは2026-10-22〜2026-10-30) から足した分は、各節の末尾と、新しく立てた節に置いた。

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

2026-10-31に仕分けた分で届いた。

- Cloudflare のアカウント所有のトークンは `/user/tokens/verify` では401 (code 1000) になり、`/accounts/<id>/tokens/verify` で active が返る。401を見て無効と判断しない (実測)
- Workers Logs の telemetry/query は、アカウント単位の「Workers Observability Read」だけのトークンで読めた。公式の API リファレンスは Write を要求すると書くが、Read で足りた (実測)
- Worker 単位のロール (Individual Workers) のトークンでは telemetry の query / keys / values が読めず、Metadata Read-Only では403、Editor を付けても Authentication error (code 10000) だった。ロールの docs は Metadata Read-Only で logs を読めると書き、API の reference は query に Workers Observability Write を要求していて食い違う。Workers Observability はアカウント単位の権限グループで Worker 単位のポリシーには出てこず、逆に telemetry を読めるトークンでは Worker の settings が403で、1本のトークンで両方は読めなかった (実測)
- Cloudflare 側に実際に載っている Workers の observability の設定は `GET /accounts/{account_id}/workers/scripts/{name}/script-settings` の observability で読め、wrangler.toml の解決ではなく Cloudflare 側で有効になったかをこれで閉じられる (実測)
- telemetry の /keys と /values で鍵と値の実際の綴りを先に読むと、query の0件が「見ていない0」か「本当に0」かを切り分けられた。同じアカウントの別の Worker の値が写っていれば、トークンと鍵と取り込みの経路が生きている対照になる (実測)
- invocation logs を有効にした検証環境へダミーの値を送ると、Authorization と Cookie と名前に token を含む独自ヘッダは伏せられたが、発信元の IP (x-real-ip / cf-connecting-ip)、位置の項目 (緯度経度・郵便番号・都市)、クエリ文字列を含む URL 全体は残った。Access の service token のヘッダは Worker まで届かず、cf-access-jwt-assertion は伏せられた (実測)
- 報告者の提案: invocation logs を有効にする前に、記録されるものを確かめる手順を置く。位置や IP を守る対象にするプロダクトでは切る理由になる
- Workers Logs は Worker が console に書いた行のすべてに、その要求の URL をクエリごとメタデータで足す。起動ログを切ると IP・User-Agent・位置の項目は付かなくなるが URL は残るので、クエリの付いた要求ではログを書かない形で閉じた (実測)
- 報告者の提案: 利用者のデータを残さない方針では、「何を書くか」に加えて「どの要求で行を作るか」を決める
- workers-rs の Worker で fetch が Err を返すと crate がエラーのログにして500を返し、panic! は「runtime canceled ... hung」と、ファイルと行番号つきの Rust の panic の行と、関数名つきの wasm の stack trace として写る。Durable Object の alarm と hibernation の WebSocket ハンドラの Err は type=exception で trigger つきで写る (実測。呼び出しログが無効の構成は確かめている途中)

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

### Node と Web の API

- Node v24.18.0 の組み込み WebSocket (undici) は `new WebSocket(url, { headers: {...} })` で upgrade 要求にヘッダを載せる。`ws` パッケージを足さずに済む。ヘッダの値は ByteString で、日本語を入れると TypeError を投げるのでプローブの値は ASCII にする (実測)
- 複数のスクリプトに共通のヘッダを足すなら、全員が import する共有モジュールで `globalThis.fetch` と `globalThis.WebSocket` を包むと、呼び出し箇所を直さずに全経路へ載り、付け忘れも構造で無くなる。テストは子プロセスに通信させ、手元のサーバが経路ごとに受けたヘッダを数える。必要な値の片方だけ渡されたら exit で止める (黙って付けないと別の失敗と見分けがつかない) (実測。最後は設計判断)
- Node で先に AbortSignal.timeout つきの fetch を起こしてから spawnSync (承認待ちなど) でイベントループを止めると、応答が届いていても戻った直後に時間切れになる。同期の待ちは、すべての非同期の時計より前に済ませる (実測。委譲先が2回とも TimeoutError を再現した)
- URL のクエリへ入力を replaceState で書くページで、値がページ自身の書いたものか外から来たリンクかを見分けるには、replaceState の state に印を載せるのが合っていた。state はリロードを越えて残り新しい遷移で空になるので、Navigation Timing より層が正しく、補助の仕組みが全部要らなくなった (実測。E2E と変異注入で確かめた)
- 印を付けるかは、書く値が開いたときの値と同じかではなく、更新の出所 (起動時の正規化か利用者の操作か) で決める。値の比較だと正規化で値が変わり、共有リンクをリロードしただけで入力を失う (実測。レビューの指摘を E2E で再現して pin した)
- 報告者の提案: URL や履歴を状態の置き場にする機能のレビューの観点に、印の出所を足す
- ページ自身の location.reload() も、ブラウザは人のリロードと同じ reload と記録するので、Navigation Timing だけでは区別できない (実測)

### Web Share API

2026-10-31に仕分けた分で届いた。

- Playwright Test の headless Chromium には navigator.share が無いが、Playwright MCP が動かす macOS の本物の Chrome には有る。MCP の実ブラウザで共有シートの無い環境を想定すると前提が外れて誤ってバグに見えるので、Navigator.prototype から消す init script で無い環境を作る (実測)
- 報告者の提案: ブラウザの API の検証手順に、この差を注記する
- navigator.share の title は共有の中身にならない。WebKit は title をリンクのプレビューの見出しにだけ使って共有先には url だけを渡し、Android の Chrome は title を EXTRA_SUBJECT / EXTRA_TITLE にだけ入れて本文は text + url になるので、タイトルを届けたいなら text に入れる (両方のソースの該当行を読んだ。実機は未確認)
- iOS の共有シートの「コピー」は text があると text だけを取る (WebKit の未解決のバグ)。text にタイトル、url を別に渡すとコピーで URL が落ちるので、text に「タイトル + 改行 + URL」をまとめて url を渡さない形にすると、どの経路でも両方が残る (ドキュメントのみ。バグの記述と第三者の実測で、現行の iOS では未確認)
- Chromium の Web Share は url が空なら URL の検査を飛ばすので、url を渡さなくても拒否されない (ソースを読んだ。実行はしていない)

### Python

2026-10-31に仕分けた分で届いた。

- Python の送受信の失敗を URLError と TimeoutError の列挙で受けると、応答の読み取り中の切断 (ConnectionResetError や http.client の例外) が文脈なしで抜ける。OSError と http.client.HTTPException で受ける (推測)
- Python の str の正規表現では `\b` や `\w` が和文の文字も語の文字に数えるので、和文に挟まれた数や、和文が直に続く ISSUE-<数> を読み落とす。re.ASCII で数える (実測、変異で確認) か、bytes の正規表現で `(?<![0-9A-Za-z])` と `(?![0-9A-Za-z])` を明示する (ドキュメントのみ)

### iOS

- iOS の URLSession も既定では 302 を辿る (実測)
- iOS の URLSessionConfiguration の httpAdditionalHeaders は URLProtocol の stub に届く要求にも載る (作成と GET の2経路で確認)。組み立て役で構成を1つ作って各通信クラスへ渡せば通信クラスを触らずに済む。WebSocket の upgrade に載るかは未確認 (実測)
- シミュレータのアプリの通信の成否は、アプリにログを足さずに CFNetwork のログ (`Task ... received response, status 101` など) で読める (実測)
- Xcode 27 系には Simulator.app が無く、シミュレータの画面は Xcode の `Contents/Applications` にある DeviceHub.app で開く (実測)
- URLSession の task に `task.delegate` を据え、その delegate が `willPerformHTTPRedirection` を実装しなければ、redirect の判断は session の delegate へ回る。WebSocket の task でも、開いた・メッセージ・完了の出来事は task の delegate に届いた。session の delegate を状態の無い共有の1つに固定し、出来事を受けたい側を task の delegate に下げると、session を作る口を1つに閉じられる (実測、iOS 26のシミュレータ)。ただし redirect の判断は task の delegate でも上書きできるので、口を閉じても性質は閉じない (ISSUE-88 の INS-23)
- Apple のネットワークのログ (CFNetwork) は、WebSocket のプロトコルの ping の送信を記録しない。送ったことの証拠はクライアントのログからは取れないので、テストでの送信の確認と、対照付きの生存の組で主張するしかない (実測)

### React と E2E (Playwright)

- React Router の `navigate(..., { viewTransition: true })` では URL が先に変わり、新しい loader データの commit と、ref を effect で更新する「最新のコールバックを ref に持つ」hook の差し替えが後から来る。E2E で URL の変化だけを待って次のキーを押すと、古いデータのハンドラが走って空振りする。高負荷のホストでだけ表に出た (実測)
- hydration の完了の印 (html の data 属性) は full goto と reload にしか効かず、client 遷移の後は true のまま残る (実測)
- 冪等な操作は、`toPass` の中で「押す → 短い timeout で結果を待つ」を繰り返すと client 遷移の直後の取りこぼしを吸収できる。押しすぎても状態が壊れないことが条件 (実測)
- 報告者の提案: E2E のガイドに「client 遷移の後の操作は URL の変化を準備完了の印にしない。冪等なら toPass で押し直し、冪等でなければ遷移先の DOM の変化 (データに依存して出る要素) を待つ」を足す
- アプリが dispatch するカスタムイベントを `addInitScript` で DOM の data 属性へ写し、locator で待つと hydration の完了を待てた。tsconfig が DOM の型を持たない E2E では、`addInitScript` に content の文字列で渡すと型エラーを避けられる (実測)
- 開発サーバの React StrictMode では、捨てられる1回目の effect も localStorage に書く。cancelled フラグを書き込みの後でしか見ていない hydration は、イベントの発火回数と書き込み回数が一致しない (推測。コードを読んだだけ)
- UI の性能の上限を決めるとき、開発機の値に推測の倍率を掛けず、Playwright から CDP の `Emulation.setCPUThrottlingRate` (4倍と6倍) を掛けて独立プロセスで測った。長さの順を昇順と降順で入れ替えても中央値がほぼ動かないことで実行順の影響も確かめた (実測)
- Playwright で応答を遅らせるときは、要求ではなく応答を握る (`route.fetch()` で取ってから待ち、`route.fulfill({ response })` で返す)。要求を握ると DB の問い合わせ自体が後ろへずれ、新しい値が返って競合が起きない (実測)
- 競合を再現するために応答を握るときは、固定の時間で遅らせず、競合の相手の操作 (作成の RPC の応答) が返るまで握る。ホストが重いと固定の時間に操作が収まらず、製品が正しくてもテストが赤くなる (実測。レビューの指摘から採用)。「古い応答が届いた」の判定は時刻ではなく応答の本文で行う (ISSUE-88 の INS-20)
- 閉じた details の中身は、`getByRole` の既定 (隠れた要素を除く) から外れる。中に live region があると、ページ全体の role の数を数える検査が別の理由で赤くなる (実測)
- chromium では、disabled にしたボタンからフォーカスが body へ落ちた。送信中のボタンを aria-disabled とハンドラの先頭の早期リターンへ切り替えるとフォーカスが残る (実測、Playwright の chromium)。切り替えの pin については ISSUE-88 の INS-19
  - 続報 (2026-10-23の仕分け、実測): 原因は HTML の focus fixup rule で、enabled に戻してもフォーカスは返らず、止めるのが1 microtask だけ (同期のダウンロードの直後に戻す) でも落ちた。aria-disabled はクリックも Enter も止めないので早期リターンが要る。止める状態の書き込みと読み出しを1組の関数にまとめると、見た目と実際の止まり方が食い違わない
- 同期に済む処理を待つあいだ (async 関数が await 無しで返り、解決済みの Promise の then が戻すまで) は1 microtask しかなく、テストの側からは観測できない。その処理が同期に呼ぶ API (ダウンロードの a 要素の click など) を `addInitScript` で包み、その中で `queueMicrotask` を積むと、呼び出し側が止めたあと、then が戻す前に走る (FIFO の順)。そこで状態を記録し、もう一度の操作を送れる。変異3種で狙った行が赤になった (実測)。そこから送る2回目の操作の形は ISSUE-88 の INS-27
- Playwright の実行を1つのシェルで順に連ねると、後の実行が `test-results/` を消すので、先の実行の失敗の trace や screenshot が残らない。失敗しうる実行ごとに `test-results/` を別の場所へ写すか、`--output` を分ける (実測)
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
- E2E の中の page.evaluate で console.log してもテストランナーの標準出力には出ないので、判定の戻り値に診断の文字列を載せ、失敗メッセージの Received で読んだ (実測)
- 共有の E2E fixture で requestfailed を検査していると、幅を変えたときにブラウザが srcset の候補を選び直して画像を取り消し、負荷時だけ net::ERR_ABORTED で落ちる。取り消しは理由 (errorText) で免除して記録に理由を入れ、免除の範囲は route.abort で pin して fixture の値をテストで受けて直接見る (実測。約90回に3回の揺れが0回になった)
- 自動操作のブラウザ (CDP で操作中の Chrome) では Cloudflare Turnstile が検証を拒む。Turnstile を通る経路の確認は人の普段のブラウザで行い、結果はサーバのログで確かめる (実測)
- 本番でブラウザ自動化の smoke を回すとき、route でバックエンドの表への書き込みを abort して止めた件数をログに出し、前後で読み取り専用のスナップショット (件数と digest) を比べると、画面を開くだけで書き込む経路があっても書き込みが残らないことを機構と数で言えた (実測。止めた件数は0。他のリポジトリでの効果は推測)
- 報告者の提案: 本番の smoke の手順書の標準にする

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

### SVG と CSP の検査

2026-10-31に仕分けた分で届いた。

- 同一オリジンで配信する SVG を正規表現の文字列検査で守るときは、DOCTYPE の内部サブセットを ENTITY だけでなく ATTLIST・ELEMENT・NOTATION まで拒否する。ATTLIST の属性の既定値で要素に書かずに onload を付けられ、WebKit で実際に動いた (実測、Playwright の WebKit)
- `<!DOCTYPE[^>]*>` で DOCTYPE を読み飛ばすと、XML ではシステム識別子の引用符の中に > を書けるので、内部サブセットをコメントに見せかけられる。DOCTYPE は許可する形の許可リストで読み飛ばす (実測)
- SVG の href と CSS の url() は拒否リストではなく許可リスト (#id と特定の data:image だけ) で検査すると、符号化は自然に落ちる。そのうえで数値文字参照、CSS のエスケープ、url( を含まない外部読み込み (image-set) は別に拒否が要った (実測。段階ごとのレビューで見つけてテストで固定した)
- CSP が style-src 'self' のページでは、page.addStyleTag で差し込んだスタイルがインラインの style 要素として違反で弾かれる (Firefox で確認)。CSP の側は緩めず、構築可能なスタイルシートを document.adoptedStyleSheets へ足すと違反にならず、transition の停止も効いた (実測)
- Playwright の E2E で CSP の違反を検査するには、fixture の addInitScript で document の securitypolicyviolation を聞き、console.error として出し直すのが効いた。インラインスクリプトのハッシュを1文字ずらす変異で、該当のテストが赤になった (実測)
- CSP の違反を console の文言で数える E2E は、ブラウザごとに文言が違う (Chromium と WebKit で共通なのは Content Security Policy の語だけ)。WebKit を足すときは、対照を当てて空振りしないことを確かめる (実測)
- CSP を Report-Only で配信していると、Chromium は違反を console に info で出すだけで、error と warning を数える console の検査には入らない。ヘッダを付けただけでは、違反を見ているつもりで見ていない緑になる (実測)
- 第三者の iframe (bot 対策の widget など) を埋め込んだページでは、console の CSP の違反が iframe 自身の CSP であることがある。違反が名指しした指示の値を自分の CSP と突き合わせ、自分の文書の securitypolicyviolation をページのスクリプトより先に仕掛けた収集で数えると、取り違えずに判定できた (実測)
- CSP の report-uri / Reporting-Endpoints の宛先を相対のパスにすると、Chromium は応答の URL を基準に解決して https の宛先として登録し、本番で報告が届いた。ビルドした設定が本番の origin を持たずに済む (実測)
- 本番の CSP の違反の報告がブラウザから届くかは、Playwright の CDP セッションで Reporting API のイベント (Network.enableReportingApi、reportingApiReportAdded / Updated、reportingApiEndpointsChangedForOrigin) を受けて確かめられ、報告の本文、宛先の登録、送信の結果 (Queued → Pending → Success) が見える。報告の送信はページのネットワークの一覧に出ないので、DevTools の画面では確かめられない (実測)
- Reporting API の報告は数十秒まとめてから送られるので、違反を起こした直後にタブの context を閉じると、報告は送られずに消える (実測)

### SVG とデザインツールの書き出し

2026-10-31に仕分けた分で届いた。

- デザインツールが書き出した SVG は文字の位置を計算済みの座標で持つので、文言を変えるとずれる。`text-anchor="middle"` で書き、`qlmanage -t -s <px> -o <dir> <file.svg>` で PNG にして重なりを目で確かめた (実測)
- デザインツールの書き出しを受け取る検査器は、許可リストを決め打ちで広げず、実物の書き出しで止まってから広げる。新しい版の Affinity は SVG に旧版とは別の名前空間を書き、許可リストがそこで止めて初めて分かった (実測)
- Affinity の SVG の書き出しは、ドキュメントの DPI が72でないと viewBox が DPI/72倍になり、アートボードの位置が小数だと viewBox の幅が切り上がって1px ずれる。72DPI で整数の位置と寸法にすると、viewBox が設計どおりの整数になる (実測)
- maskable アイコンの安全域は SVG の getBBox では測れない (線幅の外側の半分が抜ける)。パスの上の点を getPointAtLength で刻み、線幅の半分を足して中心からの最大距離を測った (実測)

### Playwright Test Agents とブラウザの MCP

2026-10-31に仕分けた分で届いた。

- Playwright Test Agents の Generator を直列に回したとき、2本目以降で setup が webServer のポートの使用中で失敗し、Generator は記録せず計画から静的にテストを書いて written=true を返した。ポートを握っていたのは MCP サーバ自身が起動して残した preview だった (実測。原因は未特定で再現していない)
- Planner の観測 (ロケータ、想定外の挙動の列挙) は質が高い。Generator は1ファイル1テストの制約があって表で回すテストは手でまとめ直す前提になり、written=true は記録して書いたことを意味しないので notes を読んで確かめる (実測)
- 報告者の提案: Generator への brief に、notes を確かめる手順を入れる
- Planner / Generator / Healer は MCP サーバ1つ (ブラウザ1つ、webServer 1つ) を共有するので、並列に回すと setup が奪い合う。Workflow でも直列にする (直列で回した結果だけが実測。並列の奪い合いは推測)
- planner で browser_run_code_unsafe から新しい browser context を作ると、直後から全ツールが MCP backend is not initialized を返して止まった。同じページでログアウトしてログインし直すと最後まで探索でき、落ちたら setup_page を呼び直すと復帰する (実測)
- 報告者の提案: references/testing.md の E2E の生成の手順に追記する
- Test Agents の MCP サーバが起こした webServer がポートを握っているときは、同じ MCP の test_run で回すと既存の webServer を使って通せ、実行したテストの ID の集合も出力に出るので ID で pin できる。または /mcp で MCP を切ってから正規の入口で回す (実測)
- planner の計画ファイル (planner_save_plan) は既定でリポジトリ直下の specs/ に未追跡で置かれるので、コミットの前に移さないと混入する (実測)
- planner / generator に実画面の文言を推測と区別して報告させると、UX の欠陥 (無効化された利用者に通信失敗の汎用画面が出る) を探索の段階で見つけられた。generator は Bash を持たないので、テストの実行はコントローラ側が要る (実測)
- chrome-devtools の MCP は、同じプロファイルのブラウザが他で動いていると起動できない。別の MCP のブラウザへ切り替えて回避した (実測)
- セッションの途中で作った .mcp.json のサーバーは /mcp に出てこなかった (実測)。プロジェクトの MCP サーバーは起動時にしか読まれない様子で、Playwright Test Agents を使うにはセッションの再起動が要る (推測)。MCP の要らない配線を先に WIP コミットしてから再起動すると、待ちが無駄にならない。報告者の提案は、`references/testing.md` の「E2E の生成」に再起動の要否を足すこと
- `init-agents --loop=claude` が書き出す .mcp.json は `npx playwright run-test-mcp-server` で起動し、seed と specs/ もリポジトリのルートに置かれた (実測)。報告者の提案は、npx を禁じている環境では pnpm exec に直す手順を足すこと。specs/ の扱いは上の planner の計画ファイルの項と同じ
- 生成された Healer の定義に「直せなければ test.fixme() にして skip する」とある。失敗を緑に見せる経路なので、brief で禁止し、実行されたテストの ID の集合で skip が無いことを確かめる必要がある (ドキュメントのみ。生成された定義を読んだだけ)

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
- リリースをタグ駆動にして2種類の成果物をタグの接頭辞で分け、タグは任意のコミットに打てるので CI で `git merge-base --is-ancestor <tag>^{commit} origin/main` を検査し (fetch-depth: 0)、environment のデプロイの許可は tag のパターンだけにした。tag の ruleset は管理者が bypass できるので、immutable releases を足した (実測。タグの push だけでデプロイと Release の作成まで通った)
- tag の push で動く workflow は tag が指すコミットの workflow ファイルを使うので、main で直しても既存の tag の再実行では直らず、tag を打ち直す必要がある。immutable releases を ON にするとそれもできないので、正しく打ち直した後に ON にする (実測)
- strict な required check の下では、squash 後の main のツリーが、マージゲートが緑の PR の head のツリーとハッシュで一致した。main の push で CI を回さない構成でも、main が検証済みであることを確かめられる (実測)
- GitHub Actions を SHA でピン留めしている依存の更新の PR は、`git/ref/tags/<tag>` でタグが PR の SHA を指すことと、`compare/<旧>...<新>` で変わったファイルが自分の使う部分に触れていないことを確かめると、コメントの版ではなく実際に効く SHA を検証できる (実測)
- 長く放置したあと、Dependabot の Actions の更新3本を1本のブランチにまとめて取り込み、CI の実行を1回に抑えた (実測)
- ubuntu-latest の移行の告知は、移行がリポジトリに届く前から run に出続ける。実際の OS は Set up job のログの Image: の行で分かるので、直近の run を数えてから版を判断する (実測。告知の開始から9日後でも40本すべて旧イメージ)
- WarpBuild のランナーは、GitHub App の対象に repo を足し、ランナーのラベルを variable で切り替えれば使えた。job のログの「Runner name」と prehook の行で、どのランナーで走ったかを示せる (実測)

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
- gh pr create が GraphQL の汎用エラーで失敗したとき、作り直す前に `gh pr list --head <branch> --state all` で存在を確かめると、1回目は作られず、2回目は作られたうえで assignee の設定だけが落ちていた。再実行の前に存在を、作られた後に title・body・assignee・head を個別に確かめる (実測)
- `gh run download <id> -n <artifact>` で artifact を1つだけ落とすと、artifact の名前のサブディレクトリが作られず直下に置かれる (全部落とすときは作られる) (実測)
- Dependabot の版の更新の PR が届いていても、脆弱性の通知 (Dependabot alerts) は別のスイッチで無効のことがある。`gh api .../dependabot/alerts` が403 disabled なら無効で、`PUT .../vulnerability-alerts` で有効にし (GET が204で確認)、有効にした直後の0件は dependency-graph/sbom のパッケージ数が非空であることを対照に読む (実測)
- 報告者の提案: 管理しているリポジトリの定期点検に、Dependabot alerts の有効を入れる
- 個人アカウントの private のリポジトリを REST の transfer API で organization へ移し、前後で repo の設定 (ruleset、rules/branches、Environments と保護、secret と variable の名前、Actions の権限、webhook、deploy key、collaborator、autolink、repo 本体) を JSON に写し、id・URL・タイムスタンプ・owner など必ず変わるキーを jq の walk で落としてから diff すると、残った差分だけが読むべきものになった。transfer の POST の応答は旧い owner の full_name と null の visibility を返し、移管は非同期なので、新しい名前で GET し直してはじめて完了が分かる (実測。21ファイル中20が一致し、差分は repo 本体の4項目)
- 報告者の提案: org へ移す手順書に「POST の応答ではなく GET で完了を確かめる」「前後を JSON に写し、変わるキーを落として diff する」「org の方針に従って変わる値がある」「release の一覧の API を引く action は移管の後に落ちうる」の4点を入れる
- ruleset の id と bypass_actors、Environment の保護とブランチの制限、secret と variable の名前は移管の前後で変わらず、rules/branches の ruleset_source は新しい owner の名前に変わるだけで、ruleset_source_type は Repository のままだった (実測)
- org へ移すと allow_forking が true から false に変わった (org の private の fork の方針が効く)。security_and_analysis は null から6項目とも disabled を明示する形に変わり (実効は同じ)、custom_properties が空で増えたので、「設定は何も変わらない」と仮定しない (実測)

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
- pnpm 11以降の設定の移行は、公開1日未満の版を exact pin した依存を置き、workspace の設定に1440で ERR_PNPM_NO_MATURE_MATCHING_VERSION で落ち、0で入る、を並べて確かめる。組込の既定も1440なので、「設定を消しても落ちる」は設定が読まれている証拠にならない (実測)
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
- 脆弱性の対応で下限を上げた pnpm.overrides が、上流がさらに上の下限を宣言したあとも残り、上流の要求より古い版に固定し続けた。上限の無い override は、将来のメジャーを全依存へ強制する形でもある (実測)
- 依存の脆弱性のアラートが配信物に届くかは、`pnpm list --prod --depth Infinity --json` の木を名前で照合すると数えられる。本番の依存の既知の名前 (陽性の対照) と dev の木 (脆弱な名前が見える対照) を並べてから「0件」を読む (実測)
- `.cache/` の下に置いた隔離のディレクトリに専用の pnpm-workspace.yaml が無いと、pnpm (と corepack、`pnpm self-update`) は親の方向へ workspace を探してリポジトリの本体を操作の対象にし、本体の package.json の packageManager と lockfile を書き換えた。並列の調査エージェントで3回起きた。`.cache/` が ignore されていても、pnpm から見れば本体の一部である。git archive で作ったコピーのルートに専用の pnpm-workspace.yaml を置くと本体をルートと判定しなくなり、前後で本体の package.json と lockfile のハッシュを照合して確かめた (実測)。報告者の提案は、隔離コピーで pnpm を動かす手順 (調査エージェントへの指示を含む) に、この2点を必須として書くこと

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

### mise の lock

2026-10-31に仕分けた分で届いた。

- mise.toml を TOML として自前で解釈せず、`mise ls --local --json -C <repo>` で mise 自身のパーサの結果を読む。--local でグローバルの設定が混ざらない (実測)
- `mise lock --platform linux-x64,macos-arm64` は install せずに両方のプラットフォームの URL と sha256 を書くので、macOS で作った lock でも Linux の CI で照合できる (実測)
- 版を上げて mise install すると lock の全プラットフォームの行が新しい版に書き換わるので、手順は「mise.toml を直して mise install し、lock の差分も一緒にコミットする」で足りる (実測)
- 既定の locked=false の mise.lock は、版を上げて lock を作り直し忘れても rc=0で入れ、lock を黙って新しい hash で書き換える。--locked か MISE_LOCKED=1なら rc=1 (実測)
- lock の hash を1文字変えて新しくダウンロードさせると Checksum mismatch で rc=1になり何も入らないので、赤の対照に使える (実測)
- 入れ済みのツールは lock を照合し直さない。入れた後で lock を壊しても already installed で rc=0になり、cache から戻したツールは素通りする (実測)
- `locked = true` を mise.toml の settings に置くと、lock に無いツールの `mise exec tool@版` まで rc=1で止まるので、mise.toml の外のツールを mise exec で使うリポジトリでは置けない (実測)
- jdx/mise-action (v5.1.1) はリポジトリに mise.lock があると mise install に --locked を自動で足すが、その1回だけで MISE_LOCKED を後の step へ流さない。cache の key は mise.lock を含む (action のソースを読んだ。実行はしていない)
- 報告者の提案: CI の照合は自動の --locked に任せ、手元の作り直し忘れは lock の差分と CI の赤で捕まえる
- jdx/mise-action は version を指定すると mise の本体を埋め込みの minisign の公開鍵で検証し、cache から戻した mise も照合する。sha256 の入力を渡すと、minisign の検証が外れる (追加ではなく置き換え) (ドキュメントのみ。action のソースも読んだ)

### pre-commit と lefthook

2026-10-31に仕分けた分で届いた。

- pre-commit は hook がファイルを変えるとコミットを止め、lefthook の stage_fixed のように黙って stage し直さない。format の自動修正を確かめてから add し直す流れになる (実測)
- lefthook が置く git hook は、本体が見つからないと警告を出して exit 0で終わるので、依存から外すだけだと gitleaks などの検査が緑のまま消える。外す前に lefthook uninstall を打つ (実測)
- 報告者の提案: lefthook から移る手順に、これを入れる
- pre-commit install は既存の他のツールの hook を .legacy へ退避して連鎖で実行するので、本体の無い lefthook の hook が退避されると exit 0のまま残る。--overwrite で置き換えると避けられる (実測。移行モードが既定であることはドキュメントのみ)
- lefthook から移した後も、prepare-commit-msg が lefthook のものとして残ることがある。pre-commit install --overwrite は default_install_hook_types の種類しか置き換えないので、ソースの読解で「作られない」と結論したレビューより手元の実物を優先し、消す前に中身を確かめた (実測。古い版が置いたというのは推測)

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

### Rust と依存の脆弱性

- Rust の依存は Dependabot のアラートだけでは足りない。GitHub の Advisory DB が RustSec の項目を全部は取り込んでおらず、Dependabot が1件しか出していない lockfile に cargo audit は22件を出した。直した証拠は件数ではなく advisory ID の集合で取り、期待した残りの集合と comm で両方向の差0を確かめた (実測)
- 本番のバイナリに載るかを `cargo tree -i <crate> --edges normal` で見るときは、`--target <本番のトリプル>` を付けないと手元のホストのターゲットで解決される (実測)
- `cargo update -p A` が「available: 新しい版」と言いながら手前の版で止まることがある。A の新しい版が別の推移依存の新しい版を要求していると resolver が手前で止める。先に要求される側を上げてから A を当て直すと届いた。rc 0 は届いた証拠にならないので lock の版を読む (実測)
- 報告者の提案: Rust を持つリポジトリでは、依存の脆弱性の定期点検に cargo audit (か cargo deny の advisories) を入れる
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

### その他のツール

- 1Password CLI の `op read 'op://<vault>/<item>/<日付の欄>'` は、画面の表示ではなく UNIX 時刻の秒 (10桁の整数) と改行を返す。期限を判定するコードは秒の整数を読む前提で書く。値の形は実物を1回読んで `od -c` で確かめる (実測)
- 依存の柵 (特定のライブラリを import してよいのは1パッケージだけ) は、設定ファイルの文字列ではなくビルドツールが出す依存グラフの JSON (辺ごとに source / test の種類つき) で検査できる。標準ライブラリに同梱されたパッケージは依存グラフの JSON に現れないので、それへの直 import は柵で見えない (実測)
- mise の `github:` backend で入れた単体バイナリの CLI が npm パッケージを `deno compile` したもので、gRPC クライアントが Deno の node:http2 互換層の上で動いていた (実測。導入時の確かめ方は ISSUE-133)
- pnpm 10の「Ignored build scripts: <pkg>」の警告は、install に `--ignore-scripts` を付けると消え、lockfile も変わらない。設定ファイルの側 (package.json) で消す方法もあるが、その package.json をキャッシュの指紋に入れていると長い検査をやり直すことになるので、フラグの方を選んだ。消せることは、付けない対照で1件出て、付けた形で0件になることで確かめた (実測)
- 1Password CLI の読み出しが authorization timeout で2回続けて落ち、デスクトップアプリのアンロックをユーザーに頼むと通った (実測)
- 1Password でアーカイブしたアイテムは `op read op://...` では読めず、失効の確認にならない。`op item get <item-id> --vault <vault> --include-archive --fields <field> --reveal` なら読めるので、失効の確認は読めた長さと HTTP のコードだけを出す形にする (実測)
- 報告者の提案: 秘密を扱う手順書に、アーカイブしたアイテムの読み方を載せる
- 1Password のアイテムは vault をまたいで移すと ID が変わりうるので、`op://<vault-id>/<item-id>/<field>` の参照が「どこにも無い」になったら、まず別の vault でタイトルを引く (推測。ID が変わった経緯は確かめていない)
- `op item get` の失敗の出力を jq に渡すと、空入力で jq が rc 0を返し、`|| echo not found` の分岐に入らなかった (実測)
- S3 互換のストレージの DELETE が存在しない key に204を返すかは、curl の --aws-sigv4 で1本叩き、同じ認証での一覧の取得 (200) を対照に並べて確かめられる (実測)
- just はレシピの直前の最後のコメントの行を `just --list` の説明に使うので、理由のコメントを書くと説明の欄が崩れる。要約は `[doc("...")]` の属性に分け、コメントは理由だけにした (実測)
- justfile の構造は `just --dump --dump-format json` で取れ、recipe ごとの依存 (priors 付き) と本体の行が返るので、regex で text-parse しなくて済む。CI に just が無いなら taiki-e/install-action で公式のリリースを入れる (実測)。ISSUE-88 の INS-57 と同じ手法
- CJK の Markdown で閉じない太字を探すとき、正規表現ではなくリポジトリが使う CommonMark の実装で描画し、残った太字の記号を旧版と新版で数え比べた。壊れるのは、太字の内側の端が約物で外側に文字が続く形だけだった (実測。正規表現は誤検出だらけで、描画なら対照付きで判定できた)
- 報告者の提案: CJK の文書を扱うリポジトリ向けの検査の候補にする
- 有界の探索で状態の上限に達したときに precondition で process ごと落とすと、同じ実行の他のテストの結果と要約の行が消える。印を立てて探索を止め、Issue.record でそのテストだけを落とす (実測)

## タスク

- [ ] 項目ごとに、dotfiles の references へ入れる価値があるか (どのリポジトリの作業で読まれるか) を決める。入れないものは理由を書いて落とす
- [ ] 入れるものは references のどのファイルに置くかを決め、版や仕様に依存する記述には届いた日付を残す
- [ ] 技術領域ごとの references を dotfiles に持つか、各リポジトリの CLAUDE.md や skill に持たせるかを決める (ISSUE-97 の配る対象の棚卸しと重なる)
- [ ] private のリポジトリの Pages と gh-pages の残りを確かめる手順を、どこかの棚卸しに入れるかを決める

## 関連

- ISSUE-133: 同じ受け箱から届いた、技術領域に閉じない知見
- ISSUE-97: 集めた知見を磨いて配る工程
- ISSUE-88: 検査と変異注入の知見。今回足した項目のうち、pin の作り方にあたる部分を INS-19〜23 に置いた
- ISSUE-118: コンテナランタイムの移行。Supabase CLI のネイティブのランタイムの報告を置いた
- ISSUE-136: global の mise に `.node-version` を読ませるか
