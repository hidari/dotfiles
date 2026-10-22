---
status: open
---

# docs(references): 受け箱に届いた技術領域ごとの知見を references の候補として残す

## 背景

2026-10-21 に受け箱へ届いたまとめのうち、特定の技術領域に閉じた知見をここへ残す (ユーザー決定 2026-10-22: 技術領域に閉じた知見も捨てずに1本にまとめる)。どの領域にも閉じない知見は ISSUE-133 へ分けた。

どれも他のセッションの報告で、dotfiles では再現していない。根拠は報告者の申告 (実測 / 推測 / ドキュメントのみ) をそのまま書く。版や仕様は届いた時点 (2026-10-21か2026-10-22) のもので、古びる。2026-10-22に届いた7件から足した分は、各節の末尾と、新しく立てた節に置いた。

### Cloudflare Access の後ろの環境へ繋ぐ

- Access の Service Auth ポリシーは、作って保存しただけではアプリに効かない。対象のアプリの Access の設定で、既存のポリシーとして割り当てて保存して初めて service token で 200 になった。割り当て前は token の有無によらず 302 で見分けが付かないので、ポリシーを足す前に「token あり」の 302 を対照として取っておくと、変化の原因を1つに絞れる (実測)
- Node v24 の fetch で Access の後ろへ POST するときは `redirect: "manual"` にする。既定の follow だと Access のログインへの 302 を辿ってログイン画面の HTML を 200 で受け取り、`res.ok` が真になって JSON の解析エラーに化ける (実測)
- follow の既定で 302 を辿った呼び出しは行き先の応答を返すので、呼び出し側に残った最終 status が 403 や 302 なら辿っていないと読める。秘密が漏れたかを後から判定するときに使える (実測)
- Cloudflare の入口は、クライアントが送った CF-Connecting-IP を上書きせず要求ごと扱いを変える。service token だけなら 200、CF-Connecting-IP だけなら 403、両方なら 302 (token が効かなくなる) だった。ローカルの wrangler dev で鍵を分けるためにこのヘッダを名乗る smoke は、Cloudflare の後ろの環境へは向けられない (実測)
- 2026-08-26 以降に発行された Access の Client Secret は `cfast_` + 英数字40 + チェックサム8の形式で、16進64桁という古い知識で形を検査すると誤判定する (ドキュメントのみ。手元の値の形が一致することは実測)
- 報告者の提案: Cloudflare の後ろの環境へ向ける HTTP の検査では、Access の 302 を辿らない設定を既定にする規約を検討する

### Node と Web の API

- Node v24.18.0 の組み込み WebSocket (undici) は `new WebSocket(url, { headers: {...} })` で upgrade 要求にヘッダを載せる。`ws` パッケージを足さずに済む。ヘッダの値は ByteString で、日本語を入れると TypeError を投げるのでプローブの値は ASCII にする (実測)
- 複数のスクリプトに共通のヘッダを足すなら、全員が import する共有モジュールで `globalThis.fetch` と `globalThis.WebSocket` を包むと、呼び出し箇所を直さずに全経路へ載り、付け忘れも構造で無くなる。テストは子プロセスに通信させ、手元のサーバが経路ごとに受けたヘッダを数える。必要な値の片方だけ渡されたら exit で止める (黙って付けないと別の失敗と見分けがつかない) (実測。最後は設計判断)

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
- ESLint の prefer-const は、宣言のあとで1回だけ代入される `let` を、そのあいだにクロージャから読まれていても「const にできる」と報告する。クロージャへ渡す印を小さなオブジェクトのプロパティにすると通る (実測)

### GitHub Actions と Node の版

- `workflow_run` で起動した run の actions/checkout (ref 指定なし) は、トリガーした run の sha ではなく実行時点の default branch の先端を fetch する。workflow_dispatch はブランチを checkout する。checkout step のログの fetch 行と rev-parse 行で確かめられる (実測)
- actions/setup-node に `node-version-file` で範囲 (`24.x`) を渡し `check-latest` を付けないと、ランナーのツールキャッシュにある版で満たされ最新のパッチは入らない。同じ run の中でもジョブごとに 24.21.0 と 24.22.0 に分かれた。下限付きの範囲 (`>=24.22.1 <25`) なら check-latest 無しで修正版へ届き、全ジョブのログに `Attempting to download >=24.22.1 <25` と `node: v24.22.1` が出た (実測)
- 下限の検査は setup-node の直後に置き、「setup-node を持つ job ⇒ 直後のステップが検査」の含意と、ファイル全体の setup-node の出現数が列挙と一致することの2本でテストに pin すると、job の追加や書き方の揺れでも穴が空かない (実測。変異8種がすべて赤)
- setup-node 7.1.0 から `node-version-file` に mise.toml を渡せる (ドキュメントのみ)
- 手元の Node は、グローバルの mise 設定を変えずに `mise exec node@<版> -- <コマンド>` で切り替えて lint / test / build を回せる (実測)
- Vercel CLI の engines.node の解釈は `>=24.22.1 <25` でも `24.x` と同じく 24.x に解決され、警告もエラーも出ない (実測)
- pnpm (12系) は root の package.json の engines.node を満たさない Node でも、run / install とも警告なしに通る。手元での版の強制は効かず、CI 側の検査が唯一の強制になる (実測)
- 毎日の定期チェックの workflow では、前提のステップを checkout の直後に置き、その後ろの検査をすべて `if: always()` にそろえると、1つが落ちても残りの検知が止まらない。集約のステップは、内訳が空でも job が赤なら「正常」と言わずに1行残す (実測。変異16種がすべて赤)
- sparse-checkout で必要なファイルだけ取り出す workflow は、テストでもその一覧のファイルだけを一時ディレクトリへ写してステップを走らせると、取り出し漏れ (毎朝の偽の赤) をマージ前に捕まえられる (実測)
- 報告者の提案: setup-node にメジャーだけの範囲を渡しているリポジトリは、パッチが runner イメージ任せになっている。各リポジトリの CI ログで掴んだ版を数えてから、下限付きの範囲か check-latest を検討する (推測)
- node の版をリポジトリ直下の `.node-version` の1箇所に寄せ、CI は actions/setup-node の `node-version-file` で、手元は mise に同じファイルを読ませる形にした報告がある (実測)。mise の側の設定と、dotfiles の global の mise 設定で有効にするかの提案は ISSUE-136

### PostgreSQL

- 「他の表を読まない」の pin は `pg_stat_xact_user_tables` の seq_scan + idx_scan で数えると効いた。`pg_stat_get_xact_numscans` は表の seq_scan しか数えず索引経由の読みを見落とす (実測、変異で確認)
- 空の表を外側に置く hash join は内側の表を開かないので、「読む」変異を join の形で作ると読みが起きない。読む変異は相手の表を起点に読む形で作る (実測)
- 並列の2セッションの検査で、B 側の SQL に「返った結果の語が期待と違えば独自の SQLSTATE で raise する」do ブロックを置くと、B の成否だけで返り値まで判定できる。判定の順序を入れ替える変異で赤になり、「例外は出ないが間違った値を返す」退行を捕まえた (実測)
- 2つの周期ジョブが同じ状態を逆向きに書く設計では、altitude の観点のレビューが「列は同じでも意味が違う」と根本を指した。意味をそろえると、周期の調整と特別な分岐がまとめて消えた (実測)

### Rust と依存の脆弱性

- Rust の依存は Dependabot のアラートだけでは足りない。GitHub の Advisory DB が RustSec の項目を全部は取り込んでおらず、Dependabot が1件しか出していない lockfile に cargo audit は22件を出した。直した証拠は件数ではなく advisory ID の集合で取り、期待した残りの集合と comm で両方向の差0を確かめた (実測)
- 本番のバイナリに載るかを `cargo tree -i <crate> --edges normal` で見るときは、`--target <本番のトリプル>` を付けないと手元のホストのターゲットで解決される (実測)
- `cargo update -p A` が「available: 新しい版」と言いながら手前の版で止まることがある。A の新しい版が別の推移依存の新しい版を要求していると resolver が手前で止める。先に要求される側を上げてから A を当て直すと届いた。rc 0 は届いた証拠にならないので lock の版を読む (実測)
- 報告者の提案: Rust を持つリポジトリでは、依存の脆弱性の定期点検に cargo audit (か cargo deny の advisories) を入れる
- Rust の `std::time::Instant` は macOS ではスリープ中に進まない。同じ処理で、Instant で測った秒数と wall clock の差がスリープの区間と一致した。Instant を使うタイムアウトはスリープで誤発火しない代わりに、測った時間は wall clock より短く出る (実測)

### Supabase CLI と外部サービスの CLI

- Supabase CLI の stack モードのネイティブのランタイム (Docker なしのローカル実行) についての報告 (ドキュメントのみ) は、コンテナランタイムの移行の前提に触るので ISSUE-118 に置いた
- 報告者の提案: CI のために Supabase を立てる目的なら、Docker のランタイムの `supabase start` の費用を先に見積もる。ネイティブは費用を下げる手段で、CI で Supabase を立てる前提を新しく作るものではない (ドキュメントのみ)
- 一晩置いた開発環境で、Stripe CLI の `stripe listen` が OAuth トークンの期限切れで終了していた。E2E の前提チェックが待受の生存を見ていたので気づけた。再ログインにはブラウザでの承認が要るので利用者に頼む (実測)

### 正規表現の計算量

- `/\s*[\r\n]\s*/g` のような「空白の並び、区切り、空白の並び」の正規表現は、区切りを含まない長い空白で位置ごとに後戻りして、長さの2乗の時間になる (64,000文字で7秒台)。先頭に後読み `(?<!\s)` を足して照合の始まりを空白の並びの先頭に限ると線形になり、結果は変わらない (実測)。入力の検査より前に正規化を置く変更の観点は ISSUE-133、処理時間の上限の pin の形は ISSUE-88 の INS-21

### その他のツール

- 1Password CLI の `op read 'op://<vault>/<item>/<日付の欄>'` は、画面の表示ではなく UNIX 時刻の秒 (10桁の整数) と改行を返す。期限を判定するコードは秒の整数を読む前提で書く。値の形は実物を1回読んで `od -c` で確かめる (実測)
- 依存の柵 (特定のライブラリを import してよいのは1パッケージだけ) は、設定ファイルの文字列ではなくビルドツールが出す依存グラフの JSON (辺ごとに source / test の種類つき) で検査できる。標準ライブラリに同梱されたパッケージは依存グラフの JSON に現れないので、それへの直 import は柵で見えない (実測)
- mise の `github:` backend で入れた単体バイナリの CLI が npm パッケージを `deno compile` したもので、gRPC クライアントが Deno の node:http2 互換層の上で動いていた (実測。導入時の確かめ方は ISSUE-133)
- pnpm 10の「Ignored build scripts: <pkg>」の警告は、install に `--ignore-scripts` を付けると消え、lockfile も変わらない。設定ファイルの側 (package.json) で消す方法もあるが、その package.json をキャッシュの指紋に入れていると長い検査をやり直すことになるので、フラグの方を選んだ。消せることは、付けない対照で1件出て、付けた形で0件になることで確かめた (実測)

## タスク

- [ ] 項目ごとに、dotfiles の references へ入れる価値があるか (どのリポジトリの作業で読まれるか) を決める。入れないものは理由を書いて落とす
- [ ] 入れるものは references のどのファイルに置くかを決め、版や仕様に依存する記述には届いた日付を残す
- [ ] 技術領域ごとの references を dotfiles に持つか、各リポジトリの CLAUDE.md や skill に持たせるかを決める (ISSUE-97 の配る対象の棚卸しと重なる)

## 関連

- ISSUE-133: 同じ受け箱から届いた、技術領域に閉じない知見
- ISSUE-97: 集めた知見を磨いて配る工程
- ISSUE-88: 検査と変異注入の知見。今回足した項目のうち、pin の作り方にあたる部分を INS-19〜23 に置いた
- ISSUE-118: コンテナランタイムの移行。Supabase CLI のネイティブのランタイムの報告を置いた
- ISSUE-136: global の mise に `.node-version` を読ませるか
