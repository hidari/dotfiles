# E2E テストの一次実測

`~/.claude/rules/testing-practices.md` の「テストが緑であることを、仕様を守れている証拠にしない」カテゴリと、`~/.claude/references/testing.md` の「E2E の生成」節が持つ規範と手順の、E2E での手当ての詳細と一次実測。

規範の遵守そのものには要らない。手当ての具体が要るとき、規範を疑うとき、似た失敗を踏んで「これは既知か」を確かめるときに読む。

例外が1つある。「Playwright Test Agents で生成するとき」節は、Test Agents で E2E を作る瞬間に引く手順の補足で、`~/.claude/references/testing.md` の「E2E の生成」節から開く。

Playwright とブラウザの MCP の、版に依存する道具の事実は `~/.claude/references/testing-e2e-tools.md` が持つ。disabled から aria-disabled への切り替えを pin するとき、落ちたテストを流し直す前、page.clock や routeWebSocket を使うとき、`context.route` で本番のオリジンを横取りするとき、滑り込むパネルの中の要素を force で押すとき、状態を変えた直後の computed style を測るときやスタイルを差し込むとき、ブラウザの MCP の wait_for や `browser_run_code_unsafe` を使うときに開く。

## 陰性の確認は陽性の合図を待ってから行う

E2E で、ある要素が0件であること、何も起きないこと、遷移しないことを確かめるときに読む。

- 「ある要素が0件」を自動再試行の assertion で確かめると、描画前の最初の判定で通るので何も確かめていない。先に陽性の要素が見えるまで待ってから0件を確かめる
- 「何も起きないこと」を確かめる E2E は、時間待ちではなくクライアント自身が上げる合図 (本文を読み終えた旗、遷移の回数) で判定すると決定的になった。「N ms 待って変化なし」は高負荷では処理の前に緑になり、変異でも緑のままでありうる。再読み込み中の evaluate の失敗を poll で NaN として読み流すと、変異の赤が数で出る
- 「Enter で遷移しない」を E2E で見るとき、Playwright の press は遷移を待たず toHaveURL は最初に一致した時点で通るので、直後の URL の検査は遷移の前に緑になりうる。テストの最後で URL をもう一度見ると、直後の検査を外した変異も末尾の検査だけで赤になった (実測。Playwright の版は未記録)

## 競合の再現は競合が起きた前提を assert する

要求や応答を遅らせて競合を再現する E2E を書くときに読む。

- 1/3回だけ落ちる E2E の競合を、片方の要求を `page.route` で遅らせて順番ごと固定し、毎回赤になる再現テストにした。このテストに「競合の片方が本当に起きたこと」の前提 (遅らせた要求が実際に送られ、遷移のクリックより後に応答したこと) を assert で入れておくと、何も確かめていない緑を防げた。最初の版はこの前提の assert で赤になり、前の画面がすぐアンマウントされると要求自体が出ないことが分かった。直す前3/3赤、直した後5/5緑、直した設定の行を外す変異で3/3赤。競合そのものの機序は React Router の lazy route discovery だった
- Playwright で応答を遅らせるときは、要求ではなく応答を握る (`route.fetch()` で取ってから待ち、`route.fulfill({ response })` で返す)。要求を握ると DB の問い合わせ自体が後ろへずれ、新しい値が返って競合が起きない (実測。Playwright の版は未記録)
- 競合を再現するために応答を握るときは、固定の時間で遅らせず、競合の相手の操作 (作成の RPC の応答) が返るまで握る。ホストが重いと固定の時間に操作が収まらず、製品が正しくてもテストが赤くなる (実測。Playwright の版は未記録)。「古い応答が届いた」の判定は時刻ではなく応答の本文で行う

## auto fixture で console と通信の失敗を断言する

E2E を作るとき、または取得の失敗や画像の描画を E2E で守りたいときに読む。Playwright の版は未記録。

- Playwright の auto fixture で外部オリジンを空の200で返し、console の error と warning、pageerror、4xx/5xx、requestfailed が0件であることをテストの終わりに検査すると、どの E2E も smoke を兼ねる (実測。abort を使うと失敗した要求として console に出る点は試していない)
- 4xx を数える fixture では、200で返ってきても描画できない画像 (XML として壊れた SVG) が見えない。画像を載せるページでは `naturalWidth > 0` を見る確認を並べる。壊した SVG を配信して、足した確認だけが赤くなった (実測)
- 取得の失敗に気づけることを固定するには、画面の文言ではなく、アプリが失敗のたびに出す `[scope] ... failed` の console の警告が0件であることを auto fixture で断言する。取得のフィルタの構文を壊す変異で、狙った断言 (`expect(warnings).toEqual([])`) が赤になった (実測)

## CSP の違反を検査する

E2E で CSP の違反を検査するときに読む。

- 収集は fixture の addInitScript で document の securitypolicyviolation を聞き、console.error として出し直す。インラインスクリプトのハッシュを1文字ずらす変異で、該当のテストが赤になった (実測)。`context.addInitScript` の `securitypolicyviolation` リスナーは script-src が厳しい CSP の下でも動き、インラインの style 属性の違反を拾えた。`route.fulfill` で返した応答のヘッダーの CSP は Chromium がそのまま適用する (どちらも実測)
- 違反を console の文言で数える E2E は、ブラウザごとに文言が違う (Chromium と WebKit で共通なのは Content Security Policy の語だけ)。WebKit を足すときは、対照を当てて空振りしないことを確かめる (実測)
- 第三者の iframe (bot 対策の widget など) を埋め込んだページでは、console の CSP の違反が iframe 自身の CSP であることがある。違反が名指しした指示の値を自分の CSP と突き合わせ、自分の文書の securitypolicyviolation をページのスクリプトより先に仕掛けた収集で数えると、取り違えずに判定できた (実測)

CSP のあるページへ実験用のスタイルを差し込むときの拒否と手当ては `~/.claude/references/testing-e2e-tools.md` の「状態を変えた直後の computed style とスタイルの差し込み」にある。

## 色とスタイルを E2E で測る

テーマや hover の色を E2E で検査するとき、CSS を外す変異で E2E が赤になることを確かめるときに読む。

- CSS の値は正規表現で読む代わりに E2E で getComputedStyle を測ると、カスケードやメディアクエリの解決をブラウザに任せられる。テーマは「属性 × OS の配色」の組で状態を作り、AA を満たすかの検査ではダークの色の取り違えを捕まえられず、状態どうしの色の一致の検査だけが捕まえた (実測、変異で確認)
- ホバーの合図を「計算済みの背景色が乗せる前と違う」で pin したら、明るいテーマで地との差が各チャンネル3しかなく、目では見えないまま緑だった。下地に重ねた画素の差の大きさ (12以上) を明暗の両方で測る形に変えた (実測)。「hover の前後で色が変わったこと」を測る helper の中で確かめるようにすると、平常時の色がたまたま基準を満たして通る形を、hover の対象を足すたびに書き忘れることがなくなった (実測)
- 「CSS を404にすれば崩れて赤になる」という変異は、スタイルが無くても折り返すサイトでは赤にならない。`nosniff` で捨てられた CSS は CSP の違反にも出ない。CSS が当たっていることは `:root` のカスタムプロパティが空でないことの番兵で見る必要があった (実測)

状態を変えた直後の computed style が前の値を返す件は `~/.claude/references/testing-e2e-tools.md` の「状態を変えた直後の computed style とスタイルの差し込み」にある。

## Playwright Test Agents で生成するとき

Playwright Test Agents を取り付けたとき、generator や healer にテストを書かせるとき、そのあとで `playwright test` を回すときに読む。生成の手順そのものは `~/.claude/references/testing.md` の「E2E の生成」節が持つ。Playwright Test Agents の版は未記録。

### 取り付けたあとの生成物

- `init-agents --loop=claude` が書き出す `.mcp.json` は `npx playwright run-test-mcp-server` で起動し、macOS では既定で headed、生成物は末尾の改行を持たない (実測)。npx を禁じている環境では pnpm exec に直す
- seed と specs/ はリポジトリのルートに置かれ、`testDir` がある状態で回すと seed はその中に作られる。generator の定義は seed のパスを `tests/seed.spec.ts` と決め打ちする。planner の計画ファイル (planner_save_plan) は既定でリポジトリ直下の specs/ に未追跡で置かれるので、コミットの前に移さないと混入する (実測)
- エージェント定義と MCP サーバはセッションの起動時にしか読まれないので、取り付けた後に再起動が要る (実測)
- 生成された healer の定義は、直せない頑固なテストに `test.fixme()` を付けて skip するよう指示する (実測)。失敗を緑に見せる経路なので、brief で禁止し、実行されたテストの ID の集合で skip が無いことを確かめる (この手当てはドキュメントのみ。生成された定義を読んだだけ)。件数ではなく ID の集合で見る理由は `~/.claude/references/observation.md` の「非 0 件も証明にならない」にある

### generator はテストを実行しない

- generator には shell が無く、書いたテストを1回も走らせずに返す。planner や generator などの Test Agents には Write の道具も無い。テストの実行と型エラーと赤の確認はコントローラ側が受け持ち、コントローラが毎回 `playwright test` を回して赤は healer に渡す流れにすると回った。結果は報告ファイルに書かせず、返事の本文で受け取る (実測)。Workflow の agentType として使ったときも、その環境ではテストを実行する道具を持たず、赤の確認は後続の agent に回した (実測)
- 実物のアプリを探索して locator を選ぶので役に立つが、探索した画面の構造のまま書くので、同じ文字列が画面に2か所ある箇所で strict mode の違反になりやすく、実行前のレビューで2件見つかった。生成物の待ち方 (正規表現の .+) が既存の作法より緩く、統合のときに直したこともある。古いビルドの画面を見て書くので、ブランチの HEAD で焼いたビルドで通すまで、仕様の変更との食い違いは見えない (いずれも実測)
- written=true は記録して書いたことを意味しないので、notes を読んで確かめる (実測)。Generator への brief に notes を確かめる手順を入れる
- Planner の観測 (ロケータ、想定外の挙動の列挙) は質が高い。planner / generator に実画面の文言を推測と区別して報告させると、UX の欠陥 (無効化されたユーザーに通信失敗の汎用画面が出る) を探索の段階で見つけられた。Generator は1ファイル1テストの制約があり、表で回すテストは手でまとめ直す前提になる (実測)

### MCP が webServer を残してポートを握る

- 機序: Test Agents の MCP サーバは、generator が雛形の spec を開いたときなどに playwright.config の webServer (アプリの dev サーバや vite preview) を立て、generator や agent が終わっても握ったまま残す (実測)
- 症状: 次の `playwright test` が「port is already used」で起動できない。`reuseExistingServer: false` と `--strictPort` の構成でも、`reuseExistingServer: false` だけの構成でも起きた (実測)。Generator を直列に回すと、2本目以降で setup がポートの使用中で失敗し、Generator は記録せず計画から静的にテストを書いて written=true を返した。このときポートを握っていたのは MCP サーバ自身が起動して残した preview だった (実測。原因は未特定で再現していない)
- 手当て: 同じ MCP の test_run で回すと既存の webServer を使って通せ、実行したテストの ID の集合も出力に出るので ID で pin できる。または /mcp で MCP を切ってから正規の入口で回す (実測)
- 手当て: generator や healer を使ったあとは、`playwright test` の前にテスト用のポートが残っていないか確かめる。止めるときは親のプロセスをたどって MCP の run-test の子だと確かめ、その preview の PID だけを止める (実測)。自分が起動したものだけに絞る判定は `~/.claude/references/host-environment.md` の「起動したものを使い終わったら落とす」にある
