# E2E の道具の一次実測

`~/.claude/references/testing-e2e.md` が名指しする、Playwright とブラウザの MCP の版に依存する道具の事実と手当て。

規範の遵守そのものには要らない。道具の挙動が想定と食い違ったとき、似た失敗を踏んで「これは既知か」を確かめるときに読む。各節に道具の版を添え、記録の無いものは「版は未記録」と書く。

## 実装の切り替えの前後で同じ意味を持つ assertion

disabled 属性から aria-disabled へ切り替える変更を Playwright で pin するときに読む。報告 2026-11-04、Playwright 1.62。

Playwright 1.62の toBeDisabled / toBeEnabled と click の actionability は `aria-disabled="true"` も無効として数えるので、disabled から aria-disabled への切り替えで既存の assertion はすべて緑のまま通った。切り替えを pin できたのは toBeFocused だけで、変異を1つずつ入れて狙ったテストだけが赤になることで確かめた。

## 再実行の前に test-results/ を退避する

Playwright の実行を1つのシェルで連ねるとき、落ちたテストを単独で流し直すときに読む。Playwright の版は未記録。

- Playwright は実行のたびに outputDir (既定の test-results/) を消すので、落ちたテストを単独で流し直した時点で直前の全件実行の trace・screenshot・error-context が消えた (実測)。単独の再実行は再現性を見る最初の一手になりやすく、そのたびに一次の証拠が消える (実測)
- 手当て: 再実行の前に test-results/ (または outputDir) をリポジトリ内の書き捨ての場所へ複製するか、失敗しうる実行ごとに `--output` を分ける

## page.clock は performance も偽物にする

page.clock を入れた E2E で、読み込み方に依存する機構や短い余裕を確かめるときに読む。Playwright の版は未記録。

- page.clock.install は performance も偽物にするので Navigation Timing の記録が空になり、時計を入れた E2E では機構を外しても緑になった (実測)。読み込み方に依存する機構は、時計を入れずに確かめる
- page.clock.install() だけでは時計は実時間でも進み、止まるのは runFor の実行中だけなので、install のあと pauseAt で止めないと、短い余裕を測る検査が遅い環境で揺れる (playwright-core の実装を読んで確かめた)。page.clock を使う E2E は install のあと pauseAt で止める

## routeWebSocket の close code

Playwright の routeWebSocket で、code を指定した close を使って分岐を試すときに読む。Playwright の版は未記録。

サーバへ繋がずにハンドラの中ですぐ close すると、code を渡してもページが受ける close code は1006になり、既定と推測しがちな1000でもなかった (Chromium と WebKit で実測)。close code で分岐する実装を、code を指定した close で試すテストは、指定が届いていない前提で読み直す。

## context.route で本番のオリジンを横取りする

base_url が絶対 URL の静的サイトの E2E を、サーバを立てずに `context.route` で本番のオリジンを横取りして組むときに読む。Playwright と Chromium の版は未記録。

手元のビルドの出力に `_headers` のヘッダーを付けて返す形で組んだ (実測)。この形で見えたこと:

- Chromium の起動引数 `--host-resolver-rules=MAP * ~NOTFOUND` で名前解決を潰すと、横取りしたナビゲーションは200のまま、横取りから漏れたリクエストは即座に失敗する。横取りが外れて本番を開いて緑になる経路を塞げる (実測)
- `page.route` は登録の順番によらず `context.route` より優先される。対照のページを同じヘッダーの経路で差し込むのに使える (実測)
- `page.request` / `context.request` / `request` fixture (APIRequestContext) は `context.route` を通らず、実際の DNS とネットワークへ出る。横取りした本番のオリジンに使うと本番を叩いて本番の200で緑になるので、使わないことをテストで pin した (実測)
- `meta` の `content` 属性を全部 URL として解決すると、viewport や description の値が同じオリジンの相対パスに化けて404になる。ベース無しで URL として読めるものだけを取る (実測)

CSS が当たっていることの番兵は `~/.claude/references/testing-e2e.md` の「色とスタイルを E2E で測る」にある。

## 滑り込むパネルの中の要素を force で押す

滑り込むパネルやドロワーの中の要素を `click({ force: true })` で押すときに読む。Playwright の版は未記録。

- スライドで開くドロワーの中の aria-disabled の要素を `click({ force: true })` すると、"Element is outside of the viewport" で落ちた。aria-hidden がスライドの始まりで外れるので「開いた」の確認が早く通り、force は静止を待たない (実測)。`toBeInViewport({ ratio: 1 })` を先に待つと直った (実測)。ただし `toBeInViewport({ ratio: 1 })` は動きの終わりの印にならず、画面に入り切った後も要素は30〜130px 動いていて、静止を待たない click が外れるテストが10回に2回落ちた (実測)
- 手当ては `~/.claude/references/testing-e2e.md` の「動きの終わりを待つ」にある

## 状態を変えた直後の computed style とスタイルの差し込み

状態を変えた直後の computed style で色や transform を測るとき、CSP のあるページへ実験用のスタイルを差し込むときに読む。ブラウザと Playwright の版は未記録。

- reduced-motion で transition を0.01ms にしても状態を変えた直後の computed style は前の値を返すことがあり、負荷時は描画を2回待っても残った。`transition: none !important` を差し込んで止める (実測)
- CSP のあるページへ page.addStyleTag で実験用のスタイルを差し込むと、インラインの style 要素として CSP の違反で弾かれる (実測。style-src 'self' のページを Firefox で確認)。CSP の側は緩めず、構築可能なスタイルシートを document.adoptedStyleSheets へ足すと違反にならず、transition の停止も効いた (実測)。element.style (CSSOM) で当てても通った (実測)

## ブラウザの MCP の wait_for

ブラウザの MCP の wait_for で cross-origin の iframe や大きな画面を待つときに読む。MCP の版は未記録。

- Turnstile のような cross-origin の iframe の中の文字を wait_for で拾えず、タイムアウトした (実測。どの MCP の wait_for かは未記録)
- chrome-devtools-mcp の wait_for は、待ちが解けるとページ全体のスナップショットを返すので、大きな一覧のある画面では出力の上限を超えた。要るところだけを evaluate_script で抜き出すほうが確実だった (実測)

## playwright-test の MCP の相対パス

playwright-test の MCP の `browser_run_code_unsafe` でファイルのパスを書くときに読む。版は未記録。

`browser_run_code_unsafe` の中の相対パスは、MCP サーバの cwd (Playwright の package) から解決され、screenshot が想定外の場所に落ちた。絶対パスで書く (実測)。

## Playwright Test Agents の挙動

Playwright Test Agents を取り付けたとき、generator や healer にテストを書かせるとき、そのあとで `playwright test` を回すときに読む。Playwright Test Agents の版は未記録。判定は `~/.claude/references/testing-e2e.md` の「Playwright Test Agents で生成するとき」にある。

### 取り付けたあとの生成物

- `init-agents --loop=claude` が書き出す `.mcp.json` は `npx playwright run-test-mcp-server` で起動し、macOS では既定で headed、生成物は末尾の改行を持たない (実測)。pnpm で起動し直す方針は `~/.claude/CLAUDE.md` の「テストを書き始める前に順序と方式を決める」カテゴリにある
- seed と specs/ はリポジトリのルートに置かれ、`testDir` がある状態で回すと seed はその中に作られる。generator の定義は seed のパスを `tests/seed.spec.ts` と決め打ちする。planner の計画ファイル (planner_save_plan) は既定でリポジトリ直下の specs/ に未追跡で置かれるので、コミットの前に移さないと混入する (実測)
- エージェント定義と MCP サーバはセッションの起動時にしか読まれないので、取り付けた後に再起動が要る (実測)
- 生成された healer の定義は、直せない頑固なテストに `test.fixme()` を付けて skip するよう指示する (実測)

### generator が書くテスト

- generator には shell が無く、書いたテストを1回も走らせずに返す。planner や generator などの Test Agents には Write の道具も無いので、結果は報告ファイルに書かせず、返事の本文で受け取る (実測)。Workflow の agentType として使ったときも、その環境ではテストを実行する道具を持たず、赤の確認は後続の agent に回した (実測)
- 実物のアプリを探索して locator を選ぶので役に立つが、探索した画面の構造のまま書くので、同じ文字列が画面に2か所ある箇所で strict mode の違反になりやすく、実行前のレビューで2件見つかった。生成物の待ち方 (正規表現の .+) が既存の作法より緩く、統合のときに直したこともある。古いビルドの画面を見て書くので、ブランチの HEAD で焼いたビルドで通すまで、仕様の変更との食い違いは見えない (いずれも実測)
- planner の観測 (locator、想定外の挙動の列挙) は質が高い。planner / generator に実画面の文言を推測と区別して報告させると、UX の欠陥 (無効化されたユーザーに通信失敗の汎用画面が出る) を探索の段階で見つけられた。generator は1ファイル1テストの制約があり、表で回すテストは手でまとめ直す前提になる (実測)

### MCP が webServer を残してポートを握る

- 機序: Test Agents の MCP サーバは playwright.config の webServer (アプリの dev サーバや vite preview) を立て、generator が終わっても握ったまま残す (実測)。立てる契機として記録があるのは、generator が雛形の spec を開いたときだけ
- 症状: 次の `playwright test` が「port is already used」で起動できない。`reuseExistingServer: false` と `--strictPort` の構成でも、`reuseExistingServer: false` だけの構成でも起きた (実測)。generator を直列に回すと、2本目以降で setup がポートの使用中で失敗し、generator は記録せず計画から静的にテストを書いて written=true を返した。このときポートを握っていたのは MCP サーバ自身が起動して残した preview だった (実測。原因は未特定で再現していない)
- 手当て: 同じ MCP の test_run で回すと既存の webServer を使って通せ、実行したテストの ID の集合も出力に出るので ID で pin できる。または /mcp で MCP を切ってから正規の入口で回す (実測)
- 止めるとき: 残っていた preview は MCP の run-test の子で、止める対象はその PID だった (実測)。止めるものを絞る判定は `~/.claude/references/host-environment.md` の「起動したものを使い終わったら落とす」にある
