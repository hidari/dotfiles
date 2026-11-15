# E2E の道具の一次実測

`~/.claude/references/testing-e2e.md` が名指しする、Playwright とブラウザの MCP の版に依存する道具の事実と手当て。

規範の遵守そのものには要らない。道具の挙動が想定と食い違ったとき、似た失敗を踏んで「これは既知か」を確かめるときに読む。各節に報告の日付と道具の版を添え、記録の無いものは「版は未記録」と書く。

## 実装の切り替えの前後で同じ意味を持つ assertion

disabled 属性から aria-disabled へ切り替える変更を Playwright で pin するときに読む。報告 2026-11-04、Playwright 1.62。

ライブラリの assertion が実装の切り替えの前後で同じ意味を持つと、既存のテストは切り替えを pin しない。Playwright 1.62の toBeDisabled / toBeEnabled と click の actionability は `aria-disabled="true"` も無効として数えるので、disabled から aria-disabled への切り替えで既存の assertion はすべて緑のまま通った。切り替えを pin できたのは toBeFocused だけで、変異を1つずつ入れて狙ったテストだけが赤になることで確かめた。

## 再実行の前に test-results/ を退避する

Playwright の実行を1つのシェルで連ねるとき、落ちたテストを単独で流し直すときに読む。Playwright の版は未記録。

- Playwright は実行のたびに outputDir (既定の test-results/) を消す。1つのシェルで順に連ねると先の実行の失敗の trace や screenshot が残らず、落ちたテストを単独で流し直した時点で直前の全件実行の trace・スクリーンショット・error-context が消えた (実測)。単独の再実行は再現性を見る最初の一手になりやすく、そのたびに一次の証拠が消える (実測)
- 手当て: 再実行の前に test-results/ (または outputDir) をリポジトリ内の書き捨ての場所へ複製するか、失敗しうる実行ごとに `--output` を分ける

## page.clock は performance も偽物にする

page.clock を入れた E2E で、読み込み方に依存する機構や短い余裕を確かめるときに読む。Playwright の版は未記録。

- page.clock.install は performance も偽物にするので Navigation Timing の記録が空になり、時計を入れた E2E では機構を外しても緑になった (実測)。読み込み方に依存する機構は、時計を入れずに確かめる
- page.clock.install() だけでは時計は実時間でも進み、止まるのは runFor の実行中だけなので、install のあと pauseAt で止めないと、短い余裕を測る検査が遅い環境で揺れる (playwright-core の実装を読んで確かめた)。page.clock を使う E2E は install のあと pauseAt で止める

## routeWebSocket の close code

Playwright の routeWebSocket で、code を指定した close を使って分岐を試すときに読む。Playwright の版は未記録。

サーバへ繋がずにハンドラの中ですぐ close すると、code を渡してもページが受ける close code は1006になった (chromium と webkit で実測)。close code で分岐する実装を、code を指定した close で試すテストは、指定が届いていない前提で読み直す。推測で「既定の close は1000」と書いた前提が誤っていた (実測)。

## context.route で本番のオリジンを横取りする

base_url が絶対 URL の静的サイトの E2E を、サーバを立てずに `context.route` で本番のオリジンを横取りして組むときに読む。Playwright と Chromium の版は未記録。

手元のビルドの出力に `_headers` のヘッダーを付けて返す形で組んだ (実測)。この形で見えたこと:

- Chromium の起動引数 `--host-resolver-rules=MAP * ~NOTFOUND` で名前解決を潰すと、横取りしたナビゲーションは200のまま、横取りから漏れたリクエストは即座に失敗する。横取りが外れて本番を開いて緑になる経路を塞げる (実測)
- `page.route` は登録の順番によらず `context.route` より優先される。対照のページを同じヘッダーの経路で差し込むのに使える (実測)
- `page.request` / `context.request` / `request` fixture (APIRequestContext) は `context.route` を通らず、実際の DNS とネットワークへ出る。横取りした本番のオリジンに使うと本番を叩いて本番の200で緑になるので、使わないことをテストで pin した (実測)
- `meta` の `content` 属性を全部 URL として解決すると、viewport や description の値が同じオリジンの相対パスに化けて404になる。ベース無しで URL として読めるものだけを取る (実測)

CSS が当たっていることの番兵は `~/.claude/references/testing-e2e.md` の「色とスタイルを E2E で測る」に、Test Agents の生成物の扱いは同じファイルの「Playwright Test Agents で生成するとき」にある。

## 滑り込むパネルの中の要素を force で押す

滑り込むパネルやドロワーの中の要素を `click({ force: true })` で押すときに読む。Playwright の版は未記録。

- スライドで開くドロワーの中の aria-disabled の要素を `click({ force: true })` すると、"Element is outside of the viewport" で落ちた。aria-hidden がスライドの始まりで外れるので「開いた」の確認が早く通り、force は静止を待たない。`toBeInViewport({ ratio: 1 })` を先に待つと直った (実測)。ただし `toBeInViewport({ ratio: 1 })` は、滑り込むパネル (CSS の transform の transition) の動きの終わりの印にならない。画面に入り切った後も要素は30〜130px 動いており、静止を待たない `click({ force: true })` が外れてフォーカスが移らないテストが10回に2回落ちた (実測)
- 手当て: パネルの要素の `getAnimations()` の `finished` を待つ。この形にすると40回とも通った。待ちが空振りしていない対照として、開くたびに animation が1つあることを測った (実測)

## 状態を変えた直後の computed style とスタイルの差し込み

状態を変えた直後の computed style で色や transform を測るとき、CSP のあるページへ実験用のスタイルを差し込むときに読む。ブラウザと Playwright の版は未記録。

- 色や transform を測るとき、reduced-motion で transition を0.01ms にしても状態を変えた直後の computed style は前の値を返すことがあり、負荷時は描画を2回待っても残った。前の値が合格する値だと測り損ねても緑になるので、`transition: none !important` を差し込み、状態ごとに値が変わったことも対照として見る (実測)
- CSP のあるページへ page.addStyleTag で実験用のスタイルを差し込むと CSP に拒まれる (実測)。style-src 'self' のページではインラインの style 要素として違反で弾かれる (Firefox で確認)。CSP の側は緩めず、構築可能なスタイルシートを document.adoptedStyleSheets へ足すと違反にならず、transition の停止も効いた (実測)。element.style (CSSOM) で当てても通った (実測)

## ブラウザの MCP の wait_for

ブラウザの MCP の wait_for で cross-origin の iframe や大きな画面を待つときに読む。MCP の版は未記録。

- Turnstile のような cross-origin の iframe の中の文字を wait_for で拾えず、タイムアウトした (実測。どの MCP の wait_for かは未記録)
- chrome-devtools-mcp の wait_for は、待ちが解けるとページ全体のスナップショットを返すので、大きな一覧のある画面では出力の上限を超えた。要るところだけを evaluate_script で抜き出すほうが確実だった (実測)

## playwright-test の MCP の相対パス

playwright-test の MCP の `browser_run_code_unsafe` でファイルのパスを書くときに読む。版は未記録。

`browser_run_code_unsafe` の中の相対パスは、MCP のサーバの cwd (Playwright の package) から解決され、screenshot が想定外の場所に落ちた。絶対パスで書く (実測)。
