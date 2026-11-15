# E2E テストの一次実測

`~/.claude/rules/testing-practices.md` の「テストが緑であることを、仕様を守れている証拠にしない」カテゴリと、`~/.claude/references/testing.md` の「E2E の生成」節が持つ規範と手順の、E2E での手当ての詳細と一次実測。

規範の遵守そのものには要らない。手当ての具体が要るとき、規範を疑うとき、似た失敗を踏んで「これは既知か」を確かめるときに読む。

E2E の assertion が空振りしていないことを、陽性の合図か前提の assert で先に示す。陰性の確認、動きの終わりを待つ、競合の再現の節はその実例。

Playwright とブラウザの MCP の、版に依存する道具の事実は `~/.claude/references/testing-e2e-tools.md` が持つ。Playwright やブラウザの MCP の API を使う E2E を書くとき、落ちたテストを流し直す前、挙動が想定と食い違ったときに開く。

## 陰性の確認は陽性の合図を待ってから行う

E2E で、ある要素が0件であること、何も起きないこと、遷移しないことを確かめるときに読む。

- 「ある要素が0件」を自動再試行の assertion で確かめると、描画前の最初の判定で通るので何も確かめていない。先に陽性の要素が見えるまで待ってから0件を確かめる
- 「何も起きないこと」を確かめる E2E は、時間待ちではなくクライアント自身が上げる合図 (本文を読み終えた旗、遷移の回数) で判定すると決定的になった。「N ms 待って変化なし」は高負荷では処理の前に緑になり、変異でも緑のままでありうる。再読み込み中の evaluate の失敗を poll で NaN として読み流すと、変異の赤が数で出る
- 「Enter で遷移しない」を E2E で見るとき、Playwright の press は遷移を待たず toHaveURL は最初に一致した時点で通るので、直後の URL の検査は遷移の前に緑になりうる。テストの最後で URL をもう一度見ると、直後の検査を外した変異も末尾の検査だけで赤になった (実測。Playwright の版は未記録)

## 動きの終わりを待つ

CSS の transition や animation で動いて現れる要素を押す前や測る前に、静止を待つときに読む。

- 画面に入り切った・aria-hidden が外れた、は静止の印ではない。動きの終わりは要素の `getAnimations()` の `finished` で待ち、待ちが空振りしていない対照 (開くたびに animation が1つある) を並べる。CSS の transform の transition で滑り込むパネルの中の要素をこの形で待つと40回とも通った (実測)。JS で動かす要素では getAnimations が空になりうる (推測。確かめていない)。事例は `~/.claude/references/testing-e2e-tools.md` の「滑り込むパネルの中の要素を force で押す」にある

## 競合の再現は競合が起きた前提を assert する

要求や応答を遅らせて競合を再現する E2E を書くときに読む。

- 再現テストには「競合の片方が本当に起きたこと」の前提 (遅らせた要求が実際に送られ、遷移のクリックより後に応答したこと) を assert で入れる。1/3回だけ落ちる E2E の競合を、片方の要求を `page.route` で遅らせて順番ごと固定し、毎回赤になる再現テストにしたとき、この前提の assert が何も確かめていない緑を防いだ。最初の版はこの前提の assert で赤になり、前の画面がすぐアンマウントされると要求自体が出ないことが分かった。直す前3/3赤、直した後5/5緑、直した設定の行を外す変異で3/3赤。競合そのものの機序は React Router の lazy route discovery だった
- Playwright で応答を遅らせるときは、要求ではなく応答を握る (`route.fetch()` で取ってから待ち、`route.fulfill({ response })` で返す)。要求を握ると DB の問い合わせ自体が後ろへずれ、新しい値が返って競合が起きない (実測。Playwright の版は未記録)
- 競合を再現するために応答を握るときは、固定の時間で遅らせず、競合の相手の操作 (作成の RPC の応答) が返るまで握る。ホストが重いと固定の時間に操作が収まらず、製品が正しくてもテストが赤くなる (実測。Playwright の版は未記録)。「古い応答が届いた」の判定は時刻ではなく応答の本文で行う

## auto fixture で console と通信の失敗を断言する

E2E を作るとき、または取得の失敗や画像の描画を E2E で守りたいときに読む。Playwright の版は未記録。

- Playwright の auto fixture で外部オリジンを空の200で返し、console の error と warning、pageerror、4xx/5xx、requestfailed が0件であることをテストの終わりに検査すると、どの E2E も smoke を兼ねる (実測。abort を使うと失敗した要求として console に出る点は試していない)
- 4xx を数える fixture では、200で返ってきても描画できない画像 (XML として壊れた SVG) が見えない。画像を載せるページでは `naturalWidth > 0` を見る確認を並べる。壊した SVG を配信して、足した確認だけが赤くなった (実測)
- 取得の失敗に気づけることは、画面の文言ではなく、アプリが失敗のたびに出す `[scope] ... failed` の console の警告を上の fixture で0件と断言して固定する。取得のフィルタの構文を壊す変異で `expect(warnings).toEqual([])` が赤になった (実測)

## CSP の違反を検査する

E2E で CSP の違反を検査するときに読む。

- 収集は fixture の addInitScript で document の securitypolicyviolation を聞き、console.error として出し直す。インラインスクリプトのハッシュを1文字ずらす変異で、該当のテストが赤になった (実測)。`context.addInitScript` の `securitypolicyviolation` リスナーは script-src が厳しい CSP の下でも動き、インラインの style 属性の違反を拾えた。`route.fulfill` で返した応答のヘッダーの CSP は Chromium がそのまま適用する (どちらも実測)
- 違反を console の文言で数える E2E は、ブラウザごとに文言が違う (Chromium と WebKit で共通なのは Content Security Policy の語だけ)。WebKit を足すときは、対照を当てて空振りしないことを確かめる (実測)
- 第三者の iframe (bot 対策の widget など) を埋め込んだページでは、console の CSP の違反が iframe 自身の CSP であることがある。違反が名指しした指示の値を自分の CSP と突き合わせ、自分の文書の securitypolicyviolation をページのスクリプトより先に仕掛けた収集で数えると、取り違えずに判定できた (実測)

CSP のあるページへ実験用のスタイルを差し込むときの拒否と手当ては `~/.claude/references/testing-e2e-tools.md` の「状態を変えた直後の computed style とスタイルの差し込み」にある。

## 色とスタイルを E2E で測る

テーマや hover の色を E2E で検査するとき、CSS を外す変異で E2E が赤になることを確かめるときに読む。

- CSS の値は正規表現で読む代わりに E2E で getComputedStyle を測ると、カスケードやメディアクエリの解決をブラウザに任せられる。テーマは「属性 × OS の配色」の組で状態を作り、AA を満たすかの検査ではダークの色の取り違えを捕まえられず、状態どうしの色の一致の検査だけが捕まえた (実測、変異で確認)
- 状態を変えた直後の computed style は前の値を返すことがあるので、前の値が合格する値だと測り損ねても緑になる。状態ごとに値が変わったことも対照として見る (実測)
- ホバーの合図を「計算済みの背景色が乗せる前と違う」で pin したら、明るいテーマで地との差が各チャンネル3しかなく、目では見えないまま緑だった。下地に重ねた画素の差の大きさ (12以上) を明暗の両方で測る形に変えた (実測)。「hover の前後で色が変わったこと」を測る helper の中で確かめるようにすると、平常時の色がたまたま基準を満たして通る形を、hover の対象を足すたびに書き忘れることがなくなった (実測)
- 「CSS を404にすれば崩れて赤になる」という変異は、スタイルが無くても折り返すサイトでは赤にならない。`nosniff` で捨てられた CSS は CSP の違反にも出ない。CSS が当たっていることは `:root` のカスタムプロパティが空でないことの番兵で見る必要があった (実測)

前の値が残る条件と transition の止め方は `~/.claude/references/testing-e2e-tools.md` の「状態を変えた直後の computed style とスタイルの差し込み」にある。

## Playwright Test Agents で生成するとき

Playwright Test Agents を取り付けたとき、generator や healer にテストを書かせるとき、そのあとで `playwright test` を回すときに読む。生成の手順そのものは `~/.claude/references/testing.md` の「E2E の生成」節が持つ。版に依存する Test Agents の挙動は `~/.claude/references/testing-e2e-tools.md` の「Playwright Test Agents の挙動」にある。

- healer の定義は直せないテストを `test.fixme()` で skip させる経路を持ち、失敗を緑に見せる。brief で禁止し、実行されたテストの ID の集合で skip が無いことを確かめる (healer が実際に fixme を付けるところも、この手当てが効くことも確かめていない。定義を読んだだけ)。件数ではなく ID の集合で見る理由は `~/.claude/references/observation.md` の「非 0 件も証明にならない」にある
- generator は書いたテストを実行しないので、テストの実行と型エラーと赤の確認はコントローラが持つ。コントローラが毎回 `playwright test` を回して赤は healer に渡す流れにすると回った (実測)
- generator が返す written=true は記録して書いたことを意味しないので、notes を読んで確かめる (実測)。generator への brief にその手順を入れる (提案)
- generator や healer を使ったあとは、`playwright test` の前にテスト用のポートが残っていないか確かめる (提案)
