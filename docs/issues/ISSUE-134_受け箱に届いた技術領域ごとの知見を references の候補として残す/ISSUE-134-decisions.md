# ISSUE-134 の採否 (2026-11-16 に判断の保存先から写した)

この表は `knowledge_ledger.records` が台帳の判断の保存先から生成する。手で直さない。記号の意味は ISSUE-146-spec.md の判定表が持ち、理由の文面は判断の保存先が持つ。

| 件 | 箇条の冒頭 | 採否 | 判断した側 | 記号 | 反映先 |
| --- | --- | --- | --- | --- | --- |
| K134-001 | Access の Service Auth ポリシーは、作って保存しただけではア… | 採らない | Claude | R4 |  |
| K134-002 | Node v24 の fetch で Access の後ろへ POST するとき… | 採る | Claude | 14 | ~/.claude/rules/cloudflare-practices.md (新規) と ~/.claude/references/cloudflare.md (新規) の組 |
| K134-003 | follow の既定で 302 を辿った呼び出しは行き先の応答を返すので、呼び出… | 採らない | Claude | R4 |  |
| K134-004 | Cloudflare の入口は、クライアントが送った CF-Connecting… | 採らない | Claude | R4 |  |
| K134-005 | 2026-08-26 以降に発行された Access の Client Secr… | 採らない | Claude | R4 |  |
| K134-006 | Cloudflare の Browser Integrity Check は、P… | 採る | Claude | 14 | ~/.claude/rules/cloudflare-practices.md (新規) と ~/.claude/references/cloudflare.md (新規) の組 |
| K134-007 | Cloudflare のアカウント所有のトークンは `/user/tokens/… | 採る | Claude | 14 | ~/.claude/references/cloudflare.md (新規、rules と組) |
| K134-008 | Workers Logs の telemetry/query は、アカウント単位… | 採らない | Claude | R4 |  |
| K134-009 | Worker 単位のロール (Individual Workers) のトークン… | 採らない | Claude | R4 |  |
| K134-010 | Cloudflare 側に実際に載っている Workers の observab… | 採らない | Claude | R4 |  |
| K134-011 | telemetry の /keys と /values で鍵と値の実際の綴りを先… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-012 | invocation logs を有効にした検証環境へダミーの値を送ると、Aut… | 採る | Claude | 14 | ~/.claude/rules/cloudflare-practices.md (新規) と ~/.claude/references/cloudflare.md (新規) の組 |
| K134-013 | Workers Logs は Worker が console に書いた行のすべ… | 採る | Claude | M | K134-012 に統合 |
| K134-014 | workers-rs の Worker で fetch が Err を返すと c… | 採らない | Claude | R4 |  |
| K134-015 | workers.dev が 404 と error code 1042 を返すこ… | 採る | Claude | 14 | ~/.claude/rules/cloudflare-practices.md (新規) と ~/.claude/references/cloudflare.md (新規) の組 |
| K134-016 | Logpush の API でアカウント単位のデータセットを読むには、トークンの… | 採らない | Claude | R4 |  |
| K134-017 | Logpush の workers_trace_events の Logs は … | 採らない | Claude | R4 |  |
| K134-018 | Logpush は起動1回につき1行を書き、ログを出さなかった起動も Logs … | 採る | Claude | 14 | ~/.claude/references/cloudflare.md (新規、rules と組) |
| K134-019 | Logpush の job の GET では、絞り込みの無い job は fil… | 採らない | Claude | R4 |  |
| K134-020 | 宛先のフォルダを再帰の glob でまとめて読むと、Logpush が job … | 採らない | Claude | R4 |  |
| K134-021 | DuckDB の read_json で列の型を columns で明示すると、… | 採らない | Claude | R4 |  |
| K134-022 | DuckDB は外側の WHERE で json_valid を見ても SELE… | 採らない | Claude | R4 |  |
| K134-023 | DuckDB では `x ->> 'k' IN (...)` の IN が ->… | 採らない | Claude | R4 |  |
| K134-024 | DuckDB の to_timestamp は TIMESTAMPTZ を返し、… | 採る | Claude | 14 | ~/.claude/references/tool-duckdb.md (新規) |
| K134-025 | `duckdb -json` は文ごとに JSON の配列を出すので複数の文の出… | 採らない | Claude | R6 |  |
| K134-026 | @cloudflare/vite-plugin の dev ではフックの thr… | 採らない | Claude | R6 |  |
| K134-027 | フレームワークのプラグインで mode (serve と build) によって… | 採らない | Claude | R4 |  |
| K134-028 | vite.config.ts から src を拡張子なしで import すると… | 採らない | Claude | R4 |  |
| K134-029 | vite の server.fs.deny に星2つで始めるパターンを書くと絶対… | 採らない | Claude | R4 |  |
| K134-030 | @cloudflare/vitest-pool-workers は0.23.0で… | 採らない | Claude | R5 |  |
| K134-031 | Workers 向けの Vitest で `*.module.css?raw` … | 採らない | Claude | R6 |  |
| K134-032 | vitest 5が出す isolate: false を勧めるヒントは、isol… | 採らない | Claude | R4 |  |
| K134-033 | vitest は既定で `.cache/` を除外しないので、`.cache/`… | 採る | Claude | D | ~/.claude/references/host-environment.md に「.cache/ は ignore されてもツールからは本体の一部」の節を足す |
| K134-034 | wrangler.toml で Durable Object の束ねを守るなら、… | 採る | Claude | 14 | ~/.claude/references/cloudflare.md (新規、rules と組) |
| K134-035 | wrangler dev では Content-Length を偽った要求が W… | 採らない | Claude | R4 |  |
| K134-036 | wrangler dev の前段は、Worker が本文を読み残して返した直後の… | 採らない | Claude | R6 |  |
| K134-037 | 競合の探針を「繰り返しのたびに作成から始める」形で書いたら、作成のレート制限に加… | 採らない | Claude | R4 |  |
| K134-038 | wrangler の pages deploy はコミットの情報を cwd の … | 採らない | Claude | R6 |  |
| K134-039 | cloudflare/wrangler-action は lockfile を … | 採らない | Claude | R6 |  |
| K134-040 | Node v24.18.0 の組み込み WebSocket (undici) は… | 採らない | Claude | R4 |  |
| K134-041 | 複数のスクリプトに共通のヘッダを足すなら、全員が import する共有モジュー… | 採らない | Claude | R4 |  |
| K134-042 | Node で先に AbortSignal.timeout つきの fetch を… | 採らない | Claude | R4 |  |
| K134-043 | URL のクエリへ入力を replaceState で書くページで、値がページ自… | 採らない | Claude | R2 |  |
| K134-044 | 印を付けるかは、書く値が開いたときの値と同じかではなく、更新の出所 (起動時の正… | 採らない | Claude | R2 |  |
| K134-045 | ページ自身の location.reload() も、ブラウザは人のリロードと同… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-046 | `node -e '<コード>' a b` で外部スクリプトを import す… | 採る | Claude | 14 | ~/.claude/references/tool-node.md (新規) |
| K134-047 | Playwright Test の headless Chromium には n… | 採らない | Claude | R4 |  |
| K134-048 | navigator.share の title は共有の中身にならない。WebK… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-049 | iOS の共有シートの「コピー」は text があると text だけを取る (… | 採らない | Claude | R6 |  |
| K134-050 | Chromium の Web Share は url が空なら URL の検査を… | 採らない | Claude | R4 |  |
| K134-051 | Python の送受信の失敗を URLError と TimeoutError … | 採らない | Claude | R4 |  |
| K134-052 | Python の str の正規表現では `\b` や `\w` が和文の文字も… | 採る | 人 |  |  |
| K134-053 | iOS の URLSession も既定では 302 を辿る (実測) | 採らない | Claude | R4 |  |
| K134-054 | iOS の URLSessionConfiguration の httpAddi… | 採らない | Claude | R4 |  |
| K134-055 | シミュレータのアプリの通信の成否は、アプリにログを足さずに CFNetwork … | 採らない | Claude | R4 |  |
| K134-056 | Xcode 27 系には Simulator.app が無く、シミュレータの画面… | 採らない | Claude | R4 |  |
| K134-057 | URLSession の task に `task.delegate` を据え、… | 採らない | Claude | R4 |  |
| K134-058 | Apple のネットワークのログ (CFNetwork) は、WebSocket… | 採らない | Claude | R4 |  |
| K134-059 | iOS シミュレータの UI テストが1本落ちると、その直後に location… | 採らない | Claude | R4 |  |
| K134-060 | 使い捨てのシミュレータ (実行のたびに作って消す) で原因を探るときは、テストを… | 採らない | Claude | R4 |  |
| K134-061 | 失敗の時点の画面は xcresult の添付 (App UI hierarchy… | 採らない | Claude | R4 |  |
| K134-062 | React Router の `navigate(..., { viewTran… | 採らない | Claude | R4 |  |
| K134-063 | hydration の完了の印 (html の data 属性) は full … | 採らない | Claude | R2 |  |
| K134-064 | 冪等な操作は、`toPass` の中で「押す → 短い timeout で結果を… | 採らない | Claude | M | K134-062 に統合 |
| K134-065 | アプリが dispatch するカスタムイベントを `addInitScript… | 採らない | Claude | R5 |  |
| K134-066 | 開発サーバの React StrictMode では、捨てられる1回目の eff… | 採らない | Claude | R2 |  |
| K134-067 | UI の性能の上限を決めるとき、開発機の値に推測の倍率を掛けず、Playwrig… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-068 | Playwright で応答を遅らせるときは、要求ではなく応答を握る (`rou… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-069 | 競合を再現するために応答を握るときは、固定の時間で遅らせず、競合の相手の操作 (… | 採る | Claude | M | K134-068 に統合 |
| K134-070 | 閉じた details の中身は、`getByRole` の既定 (隠れた要素を… | 採らない | Claude | R4 |  |
| K134-071 | chromium では、disabled にしたボタンからフォーカスが body… | 採る | Claude | 14 | ~/.claude/rules/frontend-practices.md の「見た目ではなく意味で組み、色だけに情報を載せない」カテゴリ |
| K134-072 | 同期に済む処理を待つあいだ (async 関数が await 無しで返り、解決済… | 採らない | Claude | R4 |  |
| K134-073 | Playwright の実行を1つのシェルで順に連ねると、後の実行が `test… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-074 | ESLint の prefer-const は、宣言のあとで1回だけ代入される … | 採らない | Claude | R4 |  |
| K134-075 | 画面に出ない失敗の種類を文言の表から型で除く (Exclude) と、表の死に項… | 採らない | Claude | R2 |  |
| K134-076 | 「Enter で遷移しない」を E2E で見るとき、press は遷移を待たず … | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-077 | 送信しない UI を form から search 要素へ移すと、要素の種類に結… | 採らない | Claude | R4 |  |
| K134-078 | Playwright の reporter に json を常設して .cach… | 採る | Claude | D | ~/.claude/references/observation.md の「非 0 件も証明にならない」節 |
| K134-079 | test.use のスコープのために無名の test.describe を使うと… | 採らない | Claude | R4 |  |
| K134-080 | Playwright Test では `test.use({ hasTouch:… | 採らない | Claude | R4 |  |
| K134-081 | 着手の前に一時的な spec で環境の能力 (pointer の種類、navig… | 採らない | Claude | R4 |  |
| K134-082 | Playwright の page.clock.install() だけでは時計… | 採る | Claude | M | K134-083 に統合 |
| K134-083 | page.clock.install は performance も偽物にするの… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-084 | E2E が spec どうしで状態を共有していないことは、db-reset を挟… | 採る | Claude | 14 | ~/.claude/rules/testing-practices.md の「テストが緑であることを、仕様を守れている証拠にしない」カテゴリ |
| K134-085 | picture の source を prefers-color-scheme … | 採らない | Claude | R4 |  |
| K134-086 | vite preview は既定で dist に無いパスにも index.htm… | 採る | Claude | 14 | ~/.claude/references/tool-vite.md (新規) |
| K134-087 | Playwright の auto fixture で外部オリジンを空の200で… | 採る | Claude | 14 | ~/.claude/references/testing.md に E2E の auto fixture の節 (新規) |
| K134-088 | E2E の中の page.evaluate で console.log してもテ… | 採らない | Claude | R4 |  |
| K134-089 | 共有の E2E fixture で requestfailed を検査していると… | 採らない | Claude | R4 |  |
| K134-090 | 自動操作のブラウザ (CDP で操作中の Chrome) では Cloudfla… | 採らない | Claude | R4 |  |
| K134-091 | 本番でブラウザ自動化の smoke を回すとき、route でバックエンドの表へ… | 採らない | Claude | R4 |  |
| K134-092 | dev サーバ (vite の dev モード) に向けた E2E を全件・並列… | 採らない | Claude | R4 |  |
| K134-093 | React Router v7 (7.18.2) のフレームワークモードで、la… | 採る | Claude | 14 | ~/.claude/references/tool-react-router.md (新規) |
| K134-094 | 遅らせる `page.route` の応答をテストの中で待たないと、テストが早く… | 採らない | Claude | R4 |  |
| K134-095 | 外部 CDN の script を読む経路のテストは、`addInitScrip… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-096 | 実ブラウザの閲覧者で「接続が開いてから閉じるまで」を測るため、ページに入る前の初… | 採らない | Claude | R4 |  |
| K134-097 | 境界の閾値 (N 秒続いたら成功と数える) を実測の切断時刻と比べると、切断がち… | 採らない | Claude | R4 |  |
| K134-098 | Playwright の routeWebSocket で、サーバへ繋がずにハン… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-099 | 「取得中なら何もせず返る」ガードを持つ関数を、呼ぶ側が「取ってもらえた」前提で印… | 採らない | Claude | R2 |  |
| K134-100 | 数百ms の CSS アニメーションの存在を E2E で確かめるときは、開く操作… | 採らない | Claude | R4 |  |
| K134-101 | 同期処理で閉じて開き直すときは、間に getComputedStyle(el).… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-102 | E2E で CSS 変数の解決後の色と比べたいときは、対象と同じ親の中に `st… | 採らない | Claude | R4 |  |
| K134-103 | CSS の値は正規表現で読む代わりに E2E で getComputedStyl… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-104 | Chromium はサポートしない CSS プロパティ (-webkit-tou… | 採らない | Claude | R4 |  |
| K134-105 | 色や transform を測るとき、reduced-motion で tran… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-106 | E2E で hover の色を測るときは、「hover の前後で色が変わったこと… | 採る | Claude | M | K134-107 に統合 |
| K134-107 | ホバーの合図を「計算済みの背景色が乗せる前と違う」で pin したら、明るいテー… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-108 | color-mix() の計算済みの値は rgb() ではなく `color(s… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-109 | インライン SVG の表示属性に `stroke="var(--x)"` のよう… | 採らない | Claude | R4 |  |
| K134-110 | ページの上の余白を各ページの最初のブロックに書くと、狭い幅で縮める指定が1つのブ… | 採らない | Claude | R2 |  |
| K134-111 | 下端をそろえる UI の調整では、行の箱ではなく文字の baseline を基準… | 採らない | Claude | R4 |  |
| K134-112 | 見えないラベル (position: absolute で視覚的に隠すクラス) … | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-113 | 見出しの横に置く小さな操作部品は、absolute で重ねるのではなく見出しより… | 採らない | Claude | R4 |  |
| K134-114 | document.elementFromPoint で「上に何があるか」を判定す… | 採らない | Claude | R4 |  |
| K134-115 | ブラウザで見せた見本が Web フォントを読まずシステムのフォントで描かれ、本番… | 採らない | Claude | R4 |  |
| K134-116 | 画面を操作する道具が無いセッションで、デスクトップアプリの UI 部品の見た目を… | 採らない | Claude | R4 |  |
| K134-117 | scrollHeight と clientHeight は整数に丸められるので、… | 採らない | Claude | R4 |  |
| K134-118 | 同一オリジンで配信する SVG を正規表現の文字列検査で守るときは、DOCTYP… | 採る | Claude | 14 | ~/.claude/references/tool-svg.md (新規) |
| K134-119 | `<!DOCTYPE[^>]*>` で DOCTYPE を読み飛ばすと、XML … | 採る | Claude | M | K134-118 に統合 |
| K134-120 | SVG の href と CSS の url() は拒否リストではなく許可リスト… | 採る | Claude | M | K134-118 に統合 |
| K134-121 | CSP が style-src 'self' のページでは、page.addSt… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-122 | Playwright の E2E で CSP の違反を検査するには、fixtur… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-123 | CSP の違反を console の文言で数える E2E は、ブラウザごとに文言… | 採る | Claude | M | K134-122 に統合 |
| K134-124 | CSP を Report-Only で配信していると、Chromium は違反を… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-125 | 第三者の iframe (bot 対策の widget など) を埋め込んだペー… | 採る | Claude | M | K134-122 に統合 |
| K134-126 | CSP の report-uri / Reporting-Endpoints の… | 採らない | Claude | R4 |  |
| K134-127 | 本番の CSP の違反の報告がブラウザから届くかは、Playwright の C… | 採らない | Claude | R4 |  |
| K134-128 | Reporting API の報告は数十秒まとめてから送られるので、違反を起こし… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-129 | デザインツールが書き出した SVG は文字の位置を計算済みの座標で持つので、文言… | 採らない | Claude | R4 |  |
| K134-130 | デザインツールの書き出しを受け取る検査器は、許可リストを決め打ちで広げず、実物の… | 採る | Claude | 14 | ~/.claude/references/tool-affinity.md (新規) |
| K134-131 | Affinity の SVG の書き出しは、ドキュメントの DPI が72でない… | 採る | Claude | 14 | ~/.claude/references/tool-affinity.md (新規) |
| K134-132 | maskable アイコンの安全域は SVG の getBBox では測れない … | 採らない | Claude | R4 |  |
| K134-133 | Playwright Test Agents の Generator を直列に回… | 採る | Claude | M | K134-137 に統合 |
| K134-134 | Planner の観測 (ロケータ、想定外の挙動の列挙) は質が高い。Gener… | 採る | Claude | M | K134-137 に統合 |
| K134-135 | Planner / Generator / Healer は MCP サーバ1つ… | 採らない | Claude | R4 |  |
| K134-136 | planner で browser_run_code_unsafe から新しい … | 採らない | Claude | R4 |  |
| K134-137 | Test Agents の MCP サーバが起こした webServer がポー… | 採る | 人 |  |  |
| K134-138 | planner の計画ファイル (planner_save_plan) は既定で… | 採る | Claude | M | K134-142 に統合 |
| K134-139 | planner / generator に実画面の文言を推測と区別して報告させる… | 採る | 人 |  |  |
| K134-140 | chrome-devtools の MCP は、同じプロファイルのブラウザが他で… | 採らない | Claude | R4 |  |
| K134-141 | セッションの途中で作った .mcp.json のサーバーは /mcp に出てこな… | 採る | Claude | 14 | ~/.claude/references/tool-claude-code.md (新規) |
| K134-142 | `init-agents --loop=claude` が書き出す .mcp.j… | 採る | 人 |  |  |
| K134-143 | 生成された Healer の定義に「直せなければ test.fixme() にし… | 採る | Claude | M | K134-142 に統合 |
| K134-144 | Playwright MCP はカレントのリポジトリ直下に `.playwrig… | 保留 | Claude | H3 |  |
| K134-145 | claude-in-chrome は CodeSandbox の Preview… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-146 | `workflow_run` で起動した run の actions/check… | 採らない | Claude | R4 |  |
| K134-147 | actions/setup-node に `node-version-file`… | 採る | 人 |  |  |
| K134-148 | 下限の検査は setup-node の直後に置き、「setup-node を持つ… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| K134-149 | setup-node 7.1.0 から `node-version-file` … | 採らない | Claude | R4 |  |
| K134-150 | 手元の Node は、グローバルの mise 設定を変えずに `mise exe… | 採らない | Claude | R4 |  |
| K134-151 | Vercel CLI の engines.node の解釈は `>=24.22.… | 採らない | Claude | R6 |  |
| K134-152 | pnpm (12系) は root の package.json の engin… | 採る | Claude | 14 | ~/.claude/references/node-pnpm.md (新規、rules と組) の版に依存する節 |
| K134-153 | 毎日の定期チェックの workflow では、前提のステップを checkout… | 採らない | Claude | R4 |  |
| K134-154 | sparse-checkout で必要なファイルだけ取り出す workflow … | 採らない | Claude | R4 |  |
| K134-155 | node の版を `.node-version` へ寄せて CI と mise … | 保留 | Claude | H3 |  |
| K134-156 | Draft PR を作った直後は、作成の run が立ったのを見てから Read… | 採らない | Claude | R4 |  |
| K134-157 | required check を Draft では意図的に failure にす… | 採らない | Claude | R2 |  |
| K134-158 | setup-node の自動キャッシュは packageManager が np… | 採らない | Claude | R4 |  |
| K134-159 | `on.push.branches: ["*"]` は glob の星が / を… | 保留 | Claude | H6 |  |
| K134-160 | 「デプロイは main からのみ」は workflow の if では守れない … | 採る | 人 |  |  |
| K134-161 | リリースをタグ駆動にして2種類の成果物をタグの接頭辞で分け、タグは任意のコミット… | 採らない | Claude | R4 |  |
| K134-162 | tag の push で動く workflow は tag が指すコミットの w… | 採らない | Claude | R4 |  |
| K134-163 | strict な required check の下では、squash 後の m… | 採る | Claude | D | ~/.claude/references/git-workflow.md の「squash マージ後の取り込み確認」節 |
| K134-164 | GitHub Actions を SHA でピン留めしている依存の更新の PR … | 採る | Claude | 14 | ~/.claude/rules/github-actions-practices.md (新規) と ~/.claude/references/github-actions.md (新規) の組 |
| K134-165 | 長く放置したあと、Dependabot の Actions の更新3本を1本のブ… | 採らない | Claude | R4 |  |
| K134-166 | ubuntu-latest の移行の告知は、移行がリポジトリに届く前から run… | 採る | Claude | 14 | ~/.claude/references/github-actions.md (新規、rules と組) の版に依存する節 |
| K134-167 | WarpBuild のランナーは、GitHub App の対象に repo を足… | 採らない | Claude | R2 |  |
| K134-168 | Actions の Playwright の E2E を公式のコンテナで動かして… | 採らない | Claude | R4 |  |
| K134-169 | CI の全ジョブを runs-on の新しい ubuntu のラベルと dige… | 採らない | Claude | R2 |  |
| K134-170 | ランナーのラベルは OS の版の固定で、中身の固定ではない (イメージは毎週更新… | 採らない | Claude | R4 |  |
| K134-171 | コンテナの tag は Dependabot が上げないので、イメージの版と l… | 採らない | Claude | R4 |  |
| K134-172 | digest 固定の node のイメージを root のまま動かすと、chec… | 採らない | Claude | R4 |  |
| K134-173 | CI と同じ digest 固定の Playwright 公式イメージをローカル… | 採らない | Claude | R4 |  |
| K134-174 | 旧来の方式 (gh-pages ブランチから配信する legacy) の Git… | 採らない | Claude | R4 |  |
| K134-175 | Team プランの private のリポジトリで Pages を有効にすると、… | 採る | Claude | 14 | ~/.claude/references/tool-gh.md (新規) の「Pages の公開範囲」節 |
| K134-176 | `gh api .../actions/jobs/<id>/logs` は、ログ… | 採る | 人 |  |  |
| K134-177 | gh pr create が GraphQL の汎用エラーで失敗したとき、作り直… | 採る | 人 |  |  |
| K134-178 | `gh run download <id> -n <artifact>` で a… | 採らない | Claude | R6 |  |
| K134-179 | Dependabot の版の更新の PR が届いていても、脆弱性の通知 (Dep… | 採る | Claude | 14 | ~/.claude/references/tool-dependabot.md (新規) の「alerts の有効化と0件の読み方」節 |
| K134-180 | 個人アカウントの private のリポジトリを REST の transfer… | 採る | Claude | 14 | ~/.claude/references/tool-gh.md (新規) の「リポジトリの移管」節 |
| K134-181 | ruleset の id と bypass_actors、Environment… | 採る | Claude | M | K134-180 に統合 |
| K134-182 | org へ移すと allow_forking が true から false に… | 採る | Claude | M | K134-180 に統合 |
| K134-183 | deprecated は `pnpm outdated` の Latest の列… | 採らない | Claude | R4 |  |
| K134-184 | pnpm 11以降は onlyBuiltDependencies と ignor… | 採らない | Claude | R4 |  |
| K134-185 | allowBuilds は、書かないと ERR_PNPM_IGNORED_BUI… | 採らない | Claude | R4 |  |
| K134-186 | pnpm 10系では minimumReleaseAge の既定が0で、未設定の… | 採らない | Claude | R4 |  |
| K134-187 | pnpm 11以降は .npmrc の認証とレジストリ以外の設定と、packag… | 採る | Claude | 14 | ~/.claude/references/node-pnpm.md (新規、rules と組) の版に依存する節 |
| K134-188 | minimumReleaseAgeStrict の既定は「minimumRele… | 採る | 人 |  |  |
| K134-189 | pnpm 11以降の設定の移行は、公開1日未満の版を exact pin した依… | 採る | 人 |  |  |
| K134-190 | minimumReleaseAge のあるリポジトリで「猶予を過ぎた最新へ上げる… | 採らない | Claude | R4 |  |
| K134-191 | pnpm のメジャー更新を、猶予期間 (minimumReleaseAge) を… | 採らない | Claude | R4 |  |
| K134-192 | pnpm 11以降は verifyDepsBeforeRun の既定が inst… | 採る | Claude | 14 | ~/.claude/references/node-pnpm.md (新規、rules と組) の版に依存する節 |
| K134-193 | verifyDepsBeforeRun は node_modules の同期の代… | 採らない | Claude | R6 |  |
| K134-194 | package.json の name を変えると、lockfile は変わらな… | 採らない | Claude | R5 |  |
| K134-195 | workspace のリポジトリを別のディレクトリへ mv したあと、verif… | 採る | Claude | 14 | ~/.claude/references/tool-pnpm.md の verifyDepsBeforeRun の節 (版は未記録) |
| K134-196 | `pnpm install --frozen-lockfile --worksp… | 採る | Claude | M | K134-195 に統合 |
| K134-197 | pnpm 11以降の pnpm exec は、node_modules が無いか… | 採る | Claude | 14 | ~/.claude/references/tool-pnpm.md の verifyDepsBeforeRun の節 (報告 2026-11-04、pnpm 11以降) |
| K134-198 | pnpm 12の --frozen-lockfile は install の対象… | 採る | Claude | 14 | ~/.claude/references/node-pnpm.md (新規、rules と組) の版に依存する節 |
| K134-199 | `pnpm install --frozen-lockfile --worksp… | 採らない | Claude | R4 |  |
| K134-200 | pnpm 12で `--filter <root でないパッケージ>` の in… | 採らない | Claude | R4 |  |
| K134-201 | `pnpm --filter <pkg> deploy <dir>` は roo… | 採らない | Claude | R4 |  |
| K134-202 | pnpm dedupe は devEngines.runtime の範囲も解決し… | 採らない | Claude | R6 |  |
| K134-203 | package.json の devEngines.runtime に onFa… | 採る | Claude | 14 | ~/.claude/references/node-pnpm.md (新規、rules と組) の版に依存する節 |
| K134-204 | packageManager で固定した pnpm 自身は lockfile に… | 採る | Claude | 14 | ~/.claude/rules/node-pnpm-practices.md (新規) と ~/.claude/references/node-pnpm.md (新規) の組 |
| K134-205 | pnpm audit の緑を疑って .modules.yaml と lockfi… | 採る | Claude | 14 | ~/.claude/rules/node-pnpm-practices.md (新規) と ~/.claude/references/node-pnpm.md (新規) の組 |
| K134-206 | pnpm audit は依存を変えていなくても、advisory の追加で翌日に… | 採る | Claude | 14 | ~/.claude/rules/node-pnpm-practices.md (新規) と ~/.claude/references/node-pnpm.md (新規) の組 |
| K134-207 | 脆弱性の対応で下限を上げた pnpm.overrides が、上流がさらに上の下… | 採る | Claude | 14 | ~/.claude/rules/node-pnpm-practices.md (新規) と ~/.claude/references/node-pnpm.md (新規) の組 |
| K134-208 | 依存の脆弱性のアラートが配信物に届くかは、`pnpm list --prod -… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-209 | `.cache/` の下に置いた隔離のディレクトリに専用の pnpm-works… | 採る | 人 |  |  |
| K134-210 | `pnpm audit --prod` は、lockfile の版を影響範囲内 … | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-211 | biome 2.6は Markdown と YAML を既定で整形の対象にし、m… | 採る | Claude | 14 | ~/.claude/references/node-pnpm.md (新規、rules と組) の版に依存する節 |
| K134-212 | `biome check --write .` は git の ignore だ… | 採る | Claude | D | ~/.claude/references/observation.md の「記録されたメタデータ」節 |
| K134-213 | Dependabot は biome の package.json だけを上げ、… | 採らない | Claude | R5 |  |
| K134-214 | Biome の --config-path は設定のファイルではなく、設定を置い… | 採らない | Claude | R5 |  |
| K134-215 | biome の correctness/noGlobalDirnameFilen… | 採らない | Claude | R6 |  |
| K134-216 | E2E の spec が @playwright/test を直接 import… | 採らない | Claude | R4 |  |
| K134-217 | Biome (2.5.15) の GritQL プラグインで「as const … | 採らない | Claude | R4 |  |
| K134-218 | biome 2.5.14から、HTML (Astro / Vue / Svelt… | 採らない | Claude | R4 |  |
| K134-219 | mise.toml を TOML として自前で解釈せず、`mise ls --l… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| K134-220 | `mise lock --platform linux-x64,macos-ar… | 採らない | Claude | R4 |  |
| K134-221 | 版を上げて mise install すると lock の全プラットフォームの行… | 採らない | Claude | R4 |  |
| K134-222 | 既定の locked=false の mise.lock は、版を上げて loc… | 採らない | Claude | R6 |  |
| K134-223 | lock の hash を1文字変えて新しくダウンロードさせると Checksu… | 採らない | Claude | R4 |  |
| K134-224 | 入れ済みのツールは lock を照合し直さない。入れた後で lock を壊しても… | 採らない | Claude | R6 |  |
| K134-225 | `locked = true` を mise.toml の settings に… | 採る | Claude | 14 | ~/.claude/references/tool-mise.md (新規) |
| K134-226 | jdx/mise-action (v5.1.1) はリポジトリに mise.lo… | 採る | Claude | 14 | ~/.claude/references/tool-mise.md (新規) |
| K134-227 | jdx/mise-action は version を指定すると mise の本… | 採らない | Claude | R6 |  |
| K134-228 | pre-commit は hook がファイルを変えるとコミットを止め、left… | 採らない | Claude | R1 | ~/.claude/references/observation.md |
| K134-229 | lefthook が置く git hook は、本体が見つからないと警告を出して… | 採らない | Claude | R6 |  |
| K134-230 | pre-commit install は既存の他のツールの hook を .le… | 採る | Claude | 14 | ~/.claude/references/tool-pre-commit.md (新規) |
| K134-231 | lefthook から移した後も、prepare-commit-msg が le… | 採る | Claude | M | K134-230 に統合 |
| K134-232 | 「他の表を読まない」の pin は `pg_stat_xact_user_tab… | 採る | Claude | 14 | ~/.claude/references/postgresql.md (新規) の「読みの検査」節 (rules/postgresql-practices.md (新規、paths は **/*.sql) から症状で名指し) |
| K134-233 | 空の表を外側に置く hash join は内側の表を開かないので、「読む」変異を… | 採る | Claude | 14 | ~/.claude/references/postgresql.md (新規) の「読みの検査」節 |
| K134-234 | 並列の2セッションの検査で、B 側の SQL に「返った結果の語が期待と違えば独… | 採らない | Claude | R4 |  |
| K134-235 | 2つの周期ジョブが同じ状態を逆向きに書く設計では、altitude の観点のレビ… | 採らない | Claude | R4 |  |
| K134-236 | PostgreSQL 16以降は lc_ctype と lc_collate が… | 採らない | Claude | R5 |  |
| K134-237 | psql の \if と psql の変数で評価の切り替えを渡し、各切り替えの効… | 採らない | Claude | R4 |  |
| K134-238 | RLS が有効でポリシーが0本の表は、GRANT を持つロールでも BYPASS… | 採る | Claude | 14 | ~/.claude/references/postgresql.md (新規) の「RLS」節 |
| K134-239 | RLS のポリシーで引数の無い stable の関数を (select f())… | 採る | Claude | 14 | ~/.claude/references/postgresql.md (新規) の「RLS」節 |
| K134-240 | 書き換えの等価性は、後の deparse から包みを外すと前の deparse … | 採らない | Claude | R4 |  |
| K134-241 | インデックスが選ばれる読み方では、stable の式は包む前から Index C… | 採らない | Claude | R4 |  |
| K134-242 | migration の `ENABLE ROW LEVEL SECURITY` … | 採る | Claude | 14 | ~/.claude/references/postgresql.md (新規) の「RLS」節 |
| K134-243 | migration で関数を置き換えたときの照合として、migration の範… | 採らない | Claude | R4 |  |
| K134-244 | HEAD の全 migration で状態を作るベンチは、後から入る migra… | 採らない | Claude | R4 |  |
| K134-245 | 既存の migration を最終状態の DB へ流し直す冪等性のゲートを持つリ… | 採らない | Claude | R4 |  |
| K134-246 | seed が migration の後に表の権限を付け直す構成では、ローカルの … | 採る | Claude | 14 | ~/.claude/references/postgresql.md (新規) の「権限の検査」節 |
| K134-247 | 書き手を問わず列を null にする BEFORE INSERT のトリガを足す… | 採らない | Claude | R4 |  |
| K134-248 | Rust の依存は Dependabot のアラートだけでは足りない。GitHu… | 採る | 人 |  |  |
| K134-249 | 本番のバイナリに載るかを `cargo tree -i <crate> --ed… | 採る | Claude | 14 | ~/.claude/rules/rust-practices.md の新しい「依存の脆弱性」節 |
| K134-250 | `cargo update -p A` が「available: 新しい版」と言… | 採る | Claude | 14 | ~/.claude/references/tool-cargo.md (新規) の「cargo update が届かない」節 |
| K134-251 | Rust の `std::time::Instant` は macOS ではスリ… | 採る | Claude | 14 | ~/.claude/references/tool-rust.md (新規) の「時間の計測」節 |
| K134-252 | sqlx の query! を変える変異で、backend を権限の狭いロールの… | 採らない | Claude | R4 |  |
| K134-253 | actix-web 4.x の Logger は、内側の middleware … | 採る | Claude | 14 | ~/.claude/references/tool-rust.md (新規) の「actix-web のログ」節 |
| K134-254 | Cloud Logging では、Rust の tracing の JSON の… | 採る | Claude | 14 | ~/.claude/references/tool-gcloud.md (新規) の「Cloud Logging の検索」節 |
| K134-255 | Rust で型がその trait を実装していないことを、impl の曖昧さで … | 採らない | Claude | R4 |  |
| K134-256 | rustdoc の警告を CI のゲートに入れるときは --document-p… | 採る | Claude | 14 | ~/.claude/rules/rust-practices.md の新しい「rustdoc のゲート」節 |
| K134-257 | private_intra_doc_links は [workspace.lin… | 採る | Claude | M | K134-256 に統合 |
| K134-258 | Rust の std::env::VarError::NotUnicode(Os… | 採る | Claude | 14 | ~/.claude/rules/rust-practices.md の「コンパイルが通ったことを…」節の thiserror の項 |
| K134-259 | Rust の usize::from_str は先頭の + を受けるので、Con… | 採る | Claude | 14 | ~/.claude/rules/rust-practices.md の新しい「数値の解析」節 |
| K134-260 | テストで expect() を使ったら、通常の test では通るのに、lint… | 採らない | Claude | R5 |  |
| K134-261 | Result::unwrap_or_else の closure は Err を… | 採らない | Claude | R5 |  |
| K134-262 | エラーの判定を Display ではなく enum の payload で行った… | 採らない | Claude | R4 |  |
| K134-263 | serde の #[serde(alias = "X")] で大文字と小文字の綴… | 採らない | Claude | R4 |  |
| K134-264 | Option<&dyn Trait> を await をまたいで持つと futu… | 採らない | Claude | R5 |  |
| K134-265 | embedded replica で「transaction の中の読みが pr… | 採らない | Claude | R4 |  |
| K134-266 | libsql の1本の Connection を RwLock の読みロックで共… | 採らない | Claude | R4 |  |
| K134-267 | Windows ARM の検証 VM でしか見ていなかった非決定的なクラッシュが… | 採らない | Claude | R4 |  |
| K134-268 | 静的にリンクして配るアプリで、標準ライブラリが内部で取り込む crate を、r… | 採らない | Claude | R4 |  |
| K134-269 | 標準ライブラリの依存の解決だけでは一覧が合わない。配布物は `backtrace… | 採る | Claude | 14 | ~/.claude/references/tool-cargo.md (新規) の「静的リンクの成果物のライセンス表示」節 |
| K134-270 | ライセンスの一覧の照合 (`--check`) を、rust-src の無い C… | 採らない | Claude | R4 |  |
| K134-271 | cargo の古いライセンスの綴り `MIT/Apache-2.0` (斜線) … | 採らない | Claude | R4 |  |
| K134-272 | Supabase CLI の stack モードのネイティブのランタイム (Do… | 保留 | Claude | H3 |  |
| K134-273 | 一晩置いた開発環境で、Stripe CLI の `stripe listen` … | 採らない | Claude | R4 |  |
| K134-274 | Supabase CLI の config.toml の `port = "en… | 採らない | Claude | R4 |  |
| K134-275 | Supabase で Data API を OFF にすると、PostgREST… | 採らない | Claude | R4 |  |
| K134-276 | Supabase の hosted で postgres は一部のシステム表の持… | 採らない | Claude | R4 |  |
| K134-277 | Supabase の Management API の billing/addo… | 採らない | Claude | R5 |  |
| K134-278 | Supabase の Management API の OpenAPI は各 o… | 採らない | Claude | R4 |  |
| K134-279 | テスト用のメール受信サービスで確認コードを取る処理が「待ち受けの起動の数秒前より… | 採らない | Claude | R4 |  |
| K134-280 | ある認証サービスで、ユーザーを Backend API で削除したあと端末の資格… | 採らない | Claude | R4 |  |
| K134-281 | Resend の送信の一覧の API は full_access の鍵が要り、送… | 採らない | Claude | R5 |  |
| K134-282 | `supabase db push` は未適用の migration を全部流す… | 採らない | Claude | R4 |  |
| K134-283 | LLM の生成機能の回帰評価に命令に見える入力のケースを足すと、乗っ取りは0件で… | 採らない | Claude | R4 |  |
| K134-284 | LLM の審査役は攻撃の文面も読むので欺かれうる。出力に system プロンプ… | 採らない | Claude | R4 |  |
| K134-285 | 入力を素の文字列ではなく JSON の文字列の値として user メッセージに載… | 保留 | Claude | H5 |  |
| K134-286 | `/\s*[\r\n]\s*/g` のような「空白の並び、区切り、空白の並び」の… | 保留 | Claude | H6 |  |
| K134-287 | JS の正規表現で Unicode の範囲を書くとき、`\p{Script=Hi… | 採らない | Claude | R4 |  |
| K134-288 | 同じ版数の MSI の上書きは、MajorUpgrade で ProductCo… | 採らない | Claude | R4 |  |
| K134-289 | 操作の前に取ったクラッシュダンプとイベントの件数をベースラインにし、操作の後に増… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-290 | オフラインの起動で「ある処理が走らない」ことの判定は、ネットワークを戻す前にゲス… | 採らない | Claude | R4 |  |
| K134-291 | ssh の既定のシェルが cmd の Windows のホストに `pwsh -… | 採らない | Claude | R1 | ~/.claude/skills/windows-vm-verification/SKILL.md |
| K134-292 | PowerShell で `$home` を変数名に使うと、読み取り専用の自動変… | 採らない | Claude | R5 |  |
| K134-293 | PDB の無いリリースビルドのクラッシュを、イベントログのフォールトのオフセット… | 採らない | Claude | R4 |  |
| K134-294 | 1Password CLI の `op read 'op://<vault>/<… | 採る | Claude | 14 | ~/.claude/references/tool-1password.md (新規) の「op read の値の形」節 |
| K134-295 | 依存の柵 (特定のライブラリを import してよいのは1パッケージだけ) は… | 採らない | Claude | R4 |  |
| K134-296 | mise の `github:` backend で入れた単体バイナリの CLI… | 採らない | Claude | R4 |  |
| K134-297 | pnpm 10の「Ignored build scripts: <pkg>」の警… | 採らない | Claude | R4 |  |
| K134-298 | 1Password CLI の読み出しが authorization timeo… | 採らない | Claude | R5 |  |
| K134-299 | 1Password でアーカイブしたアイテムは `op read op://..… | 採らない | Claude | R4 |  |
| K134-300 | 1Password のアイテムは vault をまたいで移すと ID が変わりう… | 採る | Claude | 14 | ~/.claude/references/tool-1password.md (新規) の「参照が切れたとき」節 |
| K134-301 | `op item get` の失敗の出力を jq に渡すと、空入力で jq が … | 採らない | Claude | R6 |  |
| K134-302 | S3 互換のストレージの DELETE が存在しない key に204を返すかは… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-303 | just はレシピの直前の最後のコメントの行を `just --list` の説… | 採らない | Claude | R4 |  |
| K134-304 | justfile の構造は `just --dump --dump-format… | 採る | Claude | 14 | ~/.claude/references/tool-just.md (新規) の「justfile の構造を読む」節 |
| K134-305 | CJK の Markdown で閉じない太字を探すとき、正規表現ではなくリポジト… | 保留 | Claude | H6 |  |
| K134-306 | 有界の探索で状態の上限に達したときに precondition で proces… | 採らない | Claude | R4 |  |
| K134-307 | macOS の Parallels VM のアプリを人手なしに動かすには、ホスト… | 採らない | Claude | R4 |  |
| K134-308 | `prlctl send-key-event` にマウスのイベントは無い。WKW… | 採らない | Claude | R4 |  |
| K134-309 | SDK API の `POST /sandbox` に `{title, pri… | 採らない | Claude | R4 |  |
| K134-310 | ブラウザで動かすだけの再現は `template: "static"` と im… | 採らない | Claude | R4 |  |
| K134-311 | 再現の台本はバグの実行と、原因の手順だけを外した対照の実行の2本を並べて出す形に… | 採らない | Claude | R4 |  |
| K134-312 | `POST /sandbox` で `template: "vanilla"` … | 採らない | Claude | R4 |  |
| K134-313 | API で作るときは `sandbox.config.json` の templ… | 採らない | Claude | R6 |  |
| K134-314 | `parcel` テンプレートは CodeSandbox 側の babel-tr… | 採らない | Claude | R4 |  |
| K134-315 | define API で `"template": "node"` を指定しても… | 採らない | Claude | R4 |  |
| K134-316 | CodeSandbox の API にはサンドボックスを消す手段が無く、試作のた… | 採らない | Claude | R4 |  |
| K134-317 | codesandbox.io の UI と公開 API は WebFetch や… | 採らない | Claude | R4 |  |
| K134-318 | Preview の確認に claude-in-chrome を使った報告は「Pl… | 採らない | Claude | R4 |  |
| K134-319 | `wrangler deploy` は cron の trigger を `PU… | 採る | Claude | 14 | ~/.claude/references/cloudflare.md (新規、rules と組) の版に依存する節 |
| K134-320 | ダッシュボードの Workers の cron trigger の編集ダイアログ… | 採る | Claude | 14 | ~/.claude/references/cloudflare.md (新規、rules と組) |
| K134-321 | Web Analytics の `GET /accounts/{id}/rum/… | 採らない | Claude | R4 |  |
| K134-322 | ダッシュボードで作ったシングルリダイレクトは、API では式が `(http.r… | 採らない | Claude | R4 |  |
| K134-323 | あるべき設定を写す前に実物を照らすと、レジストラ移管の名残 (ゾーン内の古い N… | 採らない | Claude | R4 |  |
| K134-324 | 設計書に書き写した Workers の上限は古くなっていた。2026-11の d… | 採らない | Claude | R4 |  |
| K134-325 | Cloudflare の developers docs は URL の末尾に … | 採らない | Claude | R4 |  |
| K134-326 | ネイティブで測った RSS は wasm の linear memory と一致… | 採らない | Claude | R4 |  |
| K134-327 | Durable Object の duration を「起きている時間 × 12… | 採らない | Claude | R4 |  |
| K134-328 | ダッシュボードの Data Studio のクエリのエディタは、前に開いたインス… | 採る | Claude | 14 | ~/.claude/rules/cloudflare-practices.md (新規) と ~/.claude/references/cloudflare.md (新規) の組 |
| K134-329 | vitest の include の外 (無視されるキャッシュのディレクトリなど… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-330 | rolldown (vite 8) の codeSplitting の grou… | 採る | Claude | 14 | ~/.claude/references/node-pnpm.md (新規、rules と組) の版に依存する節 |
| K134-331 | 自前の設定の型を、上流の型 (rolldown の CodeSplittingG… | 採る | Claude | 14 | ~/.claude/references/tool-typescript.md (新規) |
| K134-332 | `document.fonts.check` は、該当する FontFace が… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-333 | CSS の `word-break: auto-phrase` は、要素の la… | 採らない | Claude | R4 |  |
| K134-334 | `readdirSync(..., { recursive: true, wit… | 採らない | Claude | R4 |  |
| K134-335 | `node --test` の件数の行を `^# (tests\|pass\|fai… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-336 | Python の shlex は既定で語の途中の `#` からコメントとして捨て… | 採る | Claude | 14 | ~/.claude/references/tool-python.md (新規) の「shlex」節 |
| K134-337 | Privacy Manifest で理由が要る API の当て先は、ソースでも静… | 採る | Claude | 14 | ~/.claude/references/tool-xcode.md (新規) の「Privacy Manifest の棚卸し」節 |
| K134-338 | Rust の静的ライブラリをリンクした Swift アプリでは、Swift の … | 採る | Claude | M | K134-337 に統合 |
| K134-339 | 見つけた import の呼び出し元は、Rust のツールチェーン付属の `ll… | 採る | Claude | M | K134-337 に統合 |
| K134-340 | 理由が要る API の突き合わせは、シミュレータ向けではなく実機向けの Rele… | 採る | Claude | 14 | ~/.claude/references/tool-xcode.md (新規) の「シミュレータは実機の代わりにならない」節 |
| K134-341 | Apple の Bundle Resources の頁は `https://de… | 採らない | Claude | R6 |  |
| K134-342 | `devicectl device process launch` は呼び手の環… | 採らない | Claude | R6 |  |
| K134-343 | `xcodebuild -exportArchive` の行だけに `PATH=… | 採らない | Claude | R4 |  |
| K134-344 | strip は archive の段で起きる。archive の実行ファイルは定… | 採らない | Claude | R4 |  |
| K134-345 | App Store Connect にアプリのレコードが無い状態でも、自動署名の… | 採らない | Claude | R4 |  |
| K134-346 | 実機向けの署名を、xcconfig の SDK 条件付きの設定 (`CODE_S… | 採らない | Claude | R4 |  |
| K134-347 | Keychain のアクセスグループの解決は、書き込みの成否ではなく、保存した項… | 採る | Claude | 14 | ~/.claude/references/tool-xcode.md (新規) の「entitlements の検証」節 |
| K134-348 | 実機の UDID (xcodebuild の destination に渡す形)… | 採らない | Claude | R4 |  |
| K134-349 | `xcodebuild -allowProvisioningUpdates` だ… | 採らない | Claude | R4 |  |
| K134-350 | `-only-testing` は実行を絞るだけで、スキームの全テストのターゲッ… | 採らない | Claude | R4 |  |
| K134-351 | シミュレータ向けの `*-Simulated.xcent` は Xcode にア… | 採る | Claude | M | K134-340 に統合 |
| K134-352 | vite 8.0 → 8.1で、dev サーバーの hydration が lo… | 採らない | Claude | R4 |  |
| K134-353 | Playwright の page.evaluate に型引数つきのジェネリック… | 採らない | Claude | R4 |  |
| K134-354 | Playwright の版を上げたあと、手元のブラウザを入れ直さずに E2E を… | 採らない | Claude | R5 |  |
| K134-355 | 依存の自動更新の PR で jsdom を30.1.1 → 30.1.3に上げた… | 採る | Claude | 14 | ~/.claude/references/tool-react.md (新規) |
| K134-356 | React の hook で「親が hook を持ち、子の passive ef… | 採らない | Claude | R4 |  |
| K134-357 | React の Drawer のように閉じていても子を描く部品の中の useQu… | 採らない | Claude | R4 |  |
| K134-358 | base_url が絶対 URL の静的サイトの E2E を、サーバーを立てずに… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-359 | `package.json` に `"type": "module"` が無いと… | 採らない | Claude | R5 |  |
| K134-360 | 「CSS を404にすれば崩れて赤になる」という変異は、スタイルが無くても折り返… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-361 | インラインの `style="width:2000px"` で作ったはみ出しの対… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-362 | 新しい版の Affinity (名前空間が https://www.affini… | 採らない | Claude | R6 |  |
| K134-363 | Affinity は font-family の先頭に太さ別の PostScri… | 採らない | Claude | R4 |  |
| K134-364 | Affinity は tspan ごとの letter-spacing でカーニ… | 採らない | Claude | R4 |  |
| K134-365 | Affinity でシンボル化した図形を縮めると、線の太さは既定では縮まない。線… | 採らない | Claude | R4 |  |
| K134-366 | テンプレートの座標は自前で解析せず、Chromium に描かせてから getBo… | 採らない | Claude | R4 |  |
| K134-367 | ビルドで画像を撮るとき、サブセットのフォントに無い文字が OS のフォントで黙っ… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-368 | 書き出しの掃除が見た目を変えていないかは、元と掃除後を同じ条件で撮り、文字を隠し… | 採らない | Claude | R4 |  |
| K134-369 | ロゴを空の四角 (プレースホルダ) の範囲へビルドで描き込む構成では、ロゴの外側… | 採らない | Claude | R2 |  |
| K134-370 | `<img>` で読み込む SVG を、サイトのダークテーマに対応させたいとき、… | 採る | Claude | 14 | ~/.claude/rules/frontend-practices.md の「見た目ではなく意味で組み、色だけに情報を載せない」カテゴリ |
| K134-371 | workflow_dispatch だけで動く workflow は、merge… | 保留 | Claude | H5 |  |
| K134-372 | GitHub の runner の image は apt のミラー3段と `A… | 採らない | Claude | R4 |  |
| K134-373 | `${{ vars.X }}` は未設定だと空文字列に展開される。値を env … | 採る | Claude | 14 | ~/.claude/rules/github-actions-practices.md (新規) と ~/.claude/references/github-actions.md (新規) の組 |
| K134-374 | secret の棚卸しは「名前が workflow に出るか」ではなく「`sec… | 採る | 人 |  |  |
| K134-375 | environment に branch policy を付ける前に `gh r… | 採らない | Claude | R4 |  |
| K134-376 | secret の配線: secret manager を読む job は env… | 採る | Claude | 14 | ~/.claude/rules/github-actions-practices.md (新規) と ~/.claude/references/github-actions.md (新規) の組 |
| K134-377 | environment の保護規則で拒否される job の負のプローブで、1回目… | 採る | Claude | M | K134-160 に統合 |
| K134-378 | 1Password の load-secrets-action は、OP_ENV… | 採らない | Claude | R6 |  |
| K134-379 | GitHub Actions の workflow lockfile (`.gi… | 採る | Claude | 14 | ~/.claude/references/github-actions.md (新規、rules と組) の版に依存する節 |
| K134-380 | Dependabot には既定で3日の cooldown があり (ドキュメント… | 採る | Claude | 14 | ~/.claude/references/tool-dependabot.md (新規) の「cooldown と minimumReleaseAge」節 |
| K134-381 | `gcr.io/distroless/cc-debian12:nonroot` … | 採る | Claude | 14 | ~/.claude/references/tool-container-image.md (新規) |
| K134-382 | webpki-roots などの crate を上げても、reqwest 0.1… | 採る | Claude | M | K134-381 に統合 |
| K134-383 | built image の CA バンドルの検査は「拒否の CN が0件」だけで… | 採る | 人 |  |  |
| K134-384 | deploy の `docker buildx build --push` は … | 採らない | Claude | R4 |  |
| K134-385 | trixie では `libssl3` は `libssl3t64` が Pro… | 採らない | Claude | R5 |  |
| K134-386 | Cloud Run の revision の image は digest で記… | 採る | Claude | 14 | ~/.claude/references/tool-cloud-run.md (新規) |
| K134-387 | Cloud Run の「今の revision」を最新作成の revision … | 採る | Claude | 14 | ~/.claude/references/tool-cloud-run.md (新規) |
| K134-388 | musl の sshd の認証バイパス (crypt() が失敗時に `*` を… | 採らない | Claude | R4 |  |
| K134-389 | 報告者の提案: 管理しているリポジトリの定期点検に、Dependabot ale… | 採る | 人 |  |  |
| K134-390 | Dependabot の件数は manifest と lockfile (`py… | 採る | Claude | 14 | ~/.claude/references/tool-dependabot.md (新規) の「件数の重複」節 |
| K134-391 | `gh run rerun <run> --failed` の後は、再実行してい… | 採る | Claude | 14 | ~/.claude/references/tool-gh.md (新規) の「run の再実行」節 |
| K134-392 | `GET repos/{owner}/{repo}/rules/branches… | 採らない | Claude | R1 | ~/.claude/references/git-workflow.md |
| K134-393 | `gh pr merge --match-head-commit` は短縮の S… | 採らない | Claude | R5 |  |
| K134-394 | `gh pr diff` にはパスで絞る引数が無い。パスを渡しても何も出ないので… | 採らない | Claude | R6 |  |
| K134-395 | pnpm audit の重大度ごとの件数は advisory と該当した版の組で… | 採らない | Claude | R4 |  |
| K134-396 | `pnpm store prune` はどのプロジェクトからも参照されていないパ… | 採る | Claude | 14 | ~/.claude/references/tool-pnpm.md の store の節 (版は未記録) |
| K134-397 | pnpm 12で minimumReleaseAge を変えると、install… | 採らない | Claude | R4 |  |
| K134-398 | `--frozen-lockfile` の install は解決を飛ばすので、… | 採る | Claude | 14 | ~/.claude/references/tool-pnpm.md の minimumReleaseAge の節 (報告 2026-11-10、pnpm 10.x。12 系の frozen 検査の件と並べて版差として書く) |
| K134-399 | pnpm 12.9の frozen install は lockfile の各版… | 採らない | Claude | R4 |  |
| K134-400 | Dependabot alerts の脆弱な range と pnpm-lock… | 採らない | Claude | R4 |  |
| K134-401 | `pnpm why <name>@<version>` の出力で、ルートのパッケ… | 採らない | Claude | R4 |  |
| K134-402 | 別の lockfile を持つ pnpm の root (`--ignore-w… | 採る | Claude | 14 | ~/.claude/references/tool-pnpm.md の minimumReleaseAge の節 (報告 2026-11-10、pnpm 10) |
| K134-403 | Homebrew の pnpm が12系だと、`packageManager` … | 採らない | Claude | R4 |  |
| K134-404 | `packageManager` を持たない別の root (例: 仕様の道具だ… | 採る | Claude | 14 | ~/.claude/rules/node-pnpm-practices.md (新規) と ~/.claude/references/node-pnpm.md (新規) の組 |
| K134-405 | Biome の `// biome-ignore` をオブジェクトのプロパティの… | 採らない | Claude | R4 |  |
| K134-406 | `.pre-commit-config.yaml` に stage していない変… | 採らない | Claude | R1 | ~/.claude/references/observation.md |
| K134-407 | テーブル単位の `pg_dump --schema-only` の diff は… | 採らない | Claude | R4 |  |
| K134-408 | pg_dump 18系の出力には `\restrict <鍵>` / `\unr… | 採らない | Claude | R4 |  |
| K134-409 | DROP の前に「対象に依存する repo の外のオブジェクト (view・外部… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-410 | 対象を `to_regclass(名前)` で引いて pg_depend と結合… | 採る | Claude | 14 | ~/.claude/references/postgresql.md (新規) の「依存の検査」節 |
| K134-411 | 本番 DB へ Cloud SQL Proxy で入る手順で、proxy は `… | 採る | Claude | 14 | ~/.claude/references/postgresql.md (新規) の「接続先の取り違え」節 |
| K134-412 | 実装役の「Postgres で default now() の列追加は表の書き換… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-413 | 報告者の提案: Rust を持つリポジトリでは、依存の脆弱性の定期点検に car… | 採る | 人 |  |  |
| K134-414 | cargo-audit は `.cargo/audit.toml` の `[ou… | 採らない | Claude | R4 |  |
| K134-415 | 依存の既知の脆弱性の検査 (cargo-audit と pnpm audit) … | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-416 | cargo llvm-cov の JSON から未到達の region を拾うと… | 採る | Claude | 14 | ~/.claude/references/tool-cargo.md (新規) の「llvm-cov の JSON から未到達を拾う」節 |
| K134-417 | 依存先のリポジトリの [patch.crates-io] は依存する側に効かない… | 採らない | Claude | R4 |  |
| K134-418 | Cargo の feature を `--all-features` で回す c… | 採らない | Claude | R4 |  |
| K134-419 | GPUI は zed の公式リポジトリのリリースの rev を git 依存で固… | 採る | Claude | 14 | ~/.claude/references/tool-gpui.md (新規) の「依存の固定」節 |
| K134-420 | GPUI は前面にない窓を既定で33.3ms (30fps) に間引く (Win… | 採らない | Claude | R6 |  |
| K134-421 | uniform_list の processor は、行の高さを測るために先頭の… | 採らない | Claude | R6 |  |
| K134-422 | GPUI のアトラスは RenderImage の Arc を捨てても空かない。… | 採らない | Claude | R6 |  |
| K134-423 | ローカルの Supabase Realtime は、E2E の beforeAl… | 採らない | Claude | R6 |  |
| K134-424 | Custom Environment に紐づく環境変数は、API 上 `targ… | 採らない | Claude | R4 |  |
| K134-425 | 変数が複数の env にまたがっている行を対象から外す (target がちょう… | 採らない | Claude | R4 |  |
| K134-426 | team で Member の権限だと、アクセストークンの scope に te… | 採らない | Claude | R4 |  |
| K134-427 | CLI の認証ファイルのトークンは数日で403になっていた。CLI を依存から外… | 採らない | Claude | R4 |  |
| K134-428 | Tauri 2のアプリは WebView2 に自分の引数 (`--disable… | 採る | Claude | M | K134-430 に統合 |
| K134-429 | Tauri v2 (wry 0.55) の WebviewWindowBuild… | 採る | Claude | 14 | ~/.claude/references/tool-tauri.md (新規) の「WebView2 へ引数を渡す」節 |
| K134-430 | 環境変数 WEBVIEW2_ADDITIONAL_BROWSER_ARGUMEN… | 採る | Claude | 14 | ~/.claude/references/tool-tauri.md (新規) の「E2E を CDP でつなぐ」節 |
| K134-431 | 報告者の提案: E2E の生成の手順の参照に、Tauri (WebView2) … | 採る | Claude | M | K134-430 に統合 |
| K134-432 | 1Password の API Credential 型の項目は、値のフィールド… | 採らない | Claude | R4 |  |
| K134-433 | fontTools (varLib.instancer と pyftsubset… | 採らない | Claude | R4 |  |
| K134-434 | `ast-grep scan` は severity が error 以外のルー… | 採らない | Claude | R1 | ~/.claude/skills/ast-grep-practice/SKILL.md |
| K134-435 | `jq empty` は空のファイルと、値を2つ並べたファイルを通す。`jq -… | 採らない | Claude | M | K134-301 に統合 |
| K134-436 | APM でサブディレクトリの skill を巨大なリポジトリから取ると、初回は1… | 採らない | Claude | R4 |  |
| K134-437 | osmium tags-filter で候補を先に切り出すと、2.5GB の国単… | 採らない | Claude | R4 |  |
| K134-438 | osmium export の geojsonseq は、閉じた way を L… | 採らない | Claude | R6 |  |
| K134-439 | Quint 0.33の `--backend rust` は初回に評価器を ch… | 採らない | Claude | R4 |  |
| K134-440 | そのツールを初めてリポジトリに当て、ウィンドウからのスキャンと MCP からの … | 採らない | Claude | R4 |  |
| K134-441 | ウィンドウで始めた run はダッシュボードに running と出るが、MCP… | 採らない | Claude | R4 |  |
| K134-442 | MCP から始めた run は、ウィンドウの run が Anthropic の… | 採らない | Claude | R4 |  |
| K134-443 | 同じツールの CLI の status は、ウィンドウのサーバーが正常に動いてい… | 保留 | Claude | H4 |  |
| K134-444 | そのツール向けの skill は、手順 (setup → ランク付け → run… | 保留 | Claude | H4 |  |
| K134-445 | コンポーネント1つのモデル化を始めても、最後のスキャンからツリーが変わっていれば… | 採らない | Claude | R4 |  |
| K134-446 | スキャンが作るコンポーネントマップは、テストファイルを本体と別のコンポーネントへ… | 採らない | Claude | R4 |  |
| K134-447 | Playwright で、スライドで開くドロワーの中の aria-disable… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規) |
| K134-448 | CSS grid の列を既定の auto のままにすると、子に `word-br… | 採る | Claude | 14 | ~/.claude/rules/frontend-practices.md の「見た目ではなく意味で組み、色だけに情報を載せない」カテゴリ |
| K134-449 | レスポンシブの棚卸しで、同じオリジンの iframe をビューポートと同じ大きさ… | 採らない | Claude | R4 |  |
| K134-450 | ブラウザの文字サイズ設定の再現に、html の font-size を % で上… | 採らない | Claude | R4 |  |
| K134-451 | 「見えているか」の判定に display / visibility を使わず E… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-452 | 文字のあふれは要素の枠の座標では見えない。button / a の scroll… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-453 | モバイルの emulation で fixed のボトムナビが切れて見えたとき、… | 採る | Claude | 14 | ~/.claude/references/tool-browser.md (新規) |
| K134-454 | 中のスクロール領域を持つ画面 (管理画面に多い) では window.scrol… | 採らない | Claude | R4 |  |
| K134-455 | coarse pointer の baseline (`:where(a){mi… | 採らない | Claude | R4 |  |
| K134-456 | 同じ class を button と a に付けると、baseline で44… | 採らない | Claude | R4 |  |
| K134-457 | iframe の中ではモバイルの「横にあふれると layout viewport… | 採る | Claude | M | K134-453 に統合 |
| K134-458 | 報告者の提案は、上の計測の手順 (checkVisibility、scrollW… | 採る | Claude | M | K134-451 に統合 |
| K134-459 | ブラウザの MCP の wait_for について2つの報告が届いた。1つは (… | 採る | Claude | 14 | ~/.claude/references/tool-browser-mcp.md (新規) |
| K134-460 | chrome-devtools-mcp の evaluate_script の … | 採らない | Claude | R4 |  |
| K134-461 | chrome-devtools-mcp の emulate の networkC… | 採らない | Claude | R4 |  |
| K134-462 | playwright-test の MCP の `browser_run_cod… | 採る | Claude | 14 | ~/.claude/references/tool-browser-mcp.md (新規) |
| K134-463 | 公式 Playwright Test Agents の planner を CD… | 採らない | Claude | R4 |  |
| K134-464 | deploy の workflow で、リリースタグの作成を smoke テスト… | 保留 | Claude | H6 |  |
| K134-465 | GitHub の environment を削除すると、その中の secret … | 採る | Claude | 14 | ~/.claude/references/github-actions.md (新規、rules と組) |
| K134-466 | GitHub の environment の名前は大文字小文字を区別しない。`S… | 採らない | Claude | R4 |  |
| K134-467 | workflow の `run:` を正規表現で探すとき、`${{ github… | 採らない | Claude | R4 |  |
| K134-468 | `gh` の `--jq` は jq のオプション (`-c` など) を受け付… | 採らない | Claude | R5 |  |
| K134-469 | `gh pr checks --watch` の出力をファイルへ書いて tail… | 採る | Claude | D | ~/.claude/references/observation.md の「成否が隠れる」節 |
| K134-470 | `pnpm install --offline --frozen-lockfil… | 採らない | Claude | R5 |  |
| K134-471 | pg_trgm の類似度を使う検索のテストで、乱数の短い16進の語を fixtu… | 採らない | Claude | R4 |  |
| K134-472 | 依存の監査 (cargo audit と pnpm audit) の exit … | 採らない | Claude | R4 |  |
| K134-473 | Supabase CLI (2.122.0) の supabase start … | 採らない | Claude | R4 |  |
| K134-474 | Cloudflare の Workers の静的資産で配るサイトは、HSTS を… | 採る | Claude | 14 | ~/.claude/rules/cloudflare-practices.md (新規) と ~/.claude/references/cloudflare.md (新規) の組 |
| K134-475 | Vite の dev サーバーで CSS Modules の `composes… | 採らない | Claude | R6 |  |
| K134-476 | Vite は入口の JS チャンクのハッシュに、そのチャンクが import す… | 採らない | Claude | R6 |  |
| K134-477 | uv の `uv lock --upgrade` を回す recipe は、ex… | 採らない | Claude | R4 |  |
| K134-478 | `xcrun devicectl device process launch` … | 採らない | Claude | R5 |  |
| K134-479 | Cloudflare Turnstile の `appearance: 'int… | 採る | Claude | 14 | ~/.claude/references/tool-cloudflare.md (新規) |
| K134-480 | CSP の違反の報告で disposition が欠けていたら WebKit (… | 採らない | Claude | R4 |  |
| K134-481 | mise は `.tool-versions` を trust なしで読み、ac… | 保留 | Claude | H3 |  |
| K134-482 | GitHub の資格情報を盗んで workflow を注入し、すぐ revert… | 採る | Claude | 14 | ~/.claude/references/tool-gh.md (新規) の「消された痕跡を探す」節 |
| K134-483 | Dependabot の版の更新を見るときに、到達先の版が上流の securit… | 採る | Claude | 14 | ~/.claude/references/tool-dependabot.md (新規) の「グローバルの Advisory Database の外」節 |
| K134-484 | `gh search commits "\"<メッセージ>\""` は引用符で囲… | 採らない | Claude | R6 |  |
| K134-485 | pnpm 12の minimumReleaseAge が何に掛かるかを、同じ手順… | 保留 | Claude | H5 |  |
| K134-486 | ソースを走査する検査のテストで、テンプレートリテラルの差し込みの例を普通の文字列… | 採らない | Claude | R4 |  |
| K134-487 | Rust の workspace で、テスト専用の構築子を自クレートへの dev… | 採る | Claude | D | ~/.claude/rules/cargo-build-practices.md の「feature による除外が成立するのは…」項 |
| K134-488 | tracing-actix-web 0.7は既定の feature `emit_… | 採る | Claude | 14 | ~/.claude/references/tool-rust.md (新規) の「エラーの型とログ」節 |
| K134-489 | MoonBit 0.10.19で String / StringView の `… | 採らない | Claude | R4 |  |
| K134-490 | vitest の `it.each` の名前では `%c` が書式の目印として消… | 採らない | Claude | R6 |  |
| K134-491 | バックエンド (Rust) の入力検査をフロント (JS) に写すとき、JS の… | 採る | Claude | 14 | ~/.claude/references/tool-javascript.md (新規) |
| K134-492 | 決済サービス (Stripe) のホスト型の Checkout の画面が ifr… | 採らない | Claude | R6 |  |
| K134-493 | 2026-11に Stripe の hosted Checkout が刷新され、… | 採らない | Claude | M | K134-492 に統合 |
| K134-494 | Stripe の Checkout の URL の path が `/c/pay… | 採らない | Claude | R6 |  |
| K134-495 | 検索の UI で、「debounce した入力値」と「URL の検索パラメータ」… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K134-496 | deploy の workflow が secret を外部の保管庫から Wor… | 採らない | Claude | R4 |  |
| K134-497 | 資格情報の入れ替えの前に、その資格情報を `${{ }}` で run の本文へ… | 採らない | Claude | R4 |  |
| K134-498 | lockfile の差は、`packages:` 節の見出しのキーの集合を前後で… | 採らない | Claude | R4 |  |
| K134-499 | 2026-11-15の仕分けで、別のリポジトリから届いた。gitleaks の … | 採らない | Claude | R4 |  |
| K134-500 | 2026-11-15の仕分けで、別のリポジトリから toolchain を上げた… | 採らない | Claude | R4 |  |
| K134-501 | 2026-11-15の仕分けで、上の項と同じまとめから届いた。Rust 1.98… | 採らない | Claude | M | K134-504 に統合 |
| K134-502 | 2026-11-15の仕分けで、上の項と同じまとめから届いた。Rust 1.99… | 採らない | Claude | M | K134-504 に統合 |
| K134-503 | 2026-11-15の仕分けで、上の項と同じまとめから届いた。Rust 1.10… | 採らない | Claude | M | K134-504 に統合 |
| K134-504 | 報告者の提案: Rust の規範へ、版つきで次の3つを足す候補にする。どれも c… | 採らない | Claude | R4 |  |
| K134-505 | 2026-11-15の仕分けで、上の項と同じまとめから届いた。Rust 1.98… | 採らない | Claude | R4 |  |
| K134-506 | 2026-11-15の仕分けで、同じリポジトリの2つのまとめから届いた。Rust… | 採る | Claude | 14 | ~/.claude/references/tool-cargo.md (新規) の「公開からの待ち期間」節 |
| K134-507 | 2026-11-15の仕分けで、別のリポジトリから届いた。Rust 1.98 の… | 採らない | Claude | R4 |  |
| K134-508 | 2026-11-15の仕分けで、別のリポジトリから届いた。Rust 1.100.… | 採らない | Claude | R4 |  |
| K134-509 | 2026-11-15の仕分けで、別のリポジトリから届いた。Rust 1.97.1… | 採らない | Claude | R4 |  |
| K134-510 | 2026-11-15の仕分けで、別のリポジトリから届いた。サブディレクトリだけが… | 採らない | Claude | R4 |  |
| K134-511 | 2026-11-15の仕分けで、別のリポジトリから届いた。Parallels の… | 保留 | Claude | H3 |  |
| K134-512 | Stripe CLI の転送 (`stripe listen` 系) はグローバ… | 採らない | Claude | R6 |  |
| K134-513 | Stripe CLI の転送は、グローバルな login のアカウントではなく、… | 採らない | Claude | M | K134-512 に統合 |
| K134-514 | Stripe CLI を API 鍵で固定すると、webhook の署名鍵が l… | 採らない | Claude | R4 |  |
| K134-515 | Stripe CLI の転送ログを tail で読むと、起動時の行に webho… | 採らない | Claude | R6 |  |
| K134-516 | 2026-11-15の仕分けで、別のリポジトリから届いた。Supabase CL… | 採らない | Claude | R4 |  |
| K134-517 | 1Password CLI の `op run --env-file` は、外か… | 採らない | Claude | R6 |  |
| K134-518 | 2026-11-15の仕分けで、別のリポジトリから届いた。just のレシピの中… | 採らない | Claude | R4 |  |
| K134-519 | 2026-11-15の仕分けで、別のリポジトリから届いた。quint-conne… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| K134-520 | 2026-11-15の仕分けで、別のリポジトリから届いた。外付けディスク (AP… | 採る | Claude | 14 | ~/.claude/references/tool-macos.md (新規) の「ディスクイメージで外付けを代える」節 |
| K134-521 | exFAT のディスクイメージは `hdiutil create -size 1… | 採らない | Claude | R4 |  |
| K134-522 | macOS 26 では exFAT は FSKit のドライバでマウントされ、m… | 採らない | Claude | R4 |  |
| K134-523 | exFAT のディスクイメージでは SQLite の synchronous=N… | 採る | Claude | M | K134-520 に統合 |
| K134-524 | exFAT は拡張属性を持てないので、macOS がファイルごとに4KBの `.… | 採る | Claude | 14 | ~/.claude/references/tool-macos.md (新規) の「exFAT の AppleDouble」節 |
| K134-525 | SD カードでは SQLite の synchronous=FULL と FUL… | 採らない | Claude | R4 |  |
| K134-526 | ディスクイメージを外すときは `hdiutil info` の image-pa… | 採らない | Claude | R4 |  |
| K134-527 | 2026-11-15の仕分けで、別のリポジトリから届いた。ICC の無い sRG… | 採らない | Claude | M | K134-529 に統合 |
| K134-528 | macOS で同じ写真の sRGB 版と Display P3 版を Color… | 採らない | Claude | R4 |  |
| K134-529 | macOS の `sips --embedProfile` と `sips -m… | 採らない | Claude | R6 |  |
| K134-530 | macOS のプレビュー.app は ICC の無い JPEG を sRGB と… | 採らない | Claude | R4 |  |
| K134-531 | 2026-11-15の仕分けで、別のリポジトリから届いた。Finder から窓へ… | 採る | Claude | 14 | ~/.claude/references/tool-macos.md (新規) の「ファイル名の Unicode 正規化」節 |
| K134-532 | 2026-11-16の仕分けで、別のリポジトリから届いた。GitHub の Fr… | 採らない | Claude | R5 |  |
