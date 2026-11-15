# ISSUE-88 の採否 (2026-11-15 に判断の保存先から写した)

この表は `knowledge_ledger.records` が台帳の判断の保存先から生成する。手で直さない。記号の意味は ISSUE-146-spec.md の判定表が持ち、理由の文面は判断の保存先が持つ。

| 件 | 箇条の冒頭 | 採否 | 判断した側 | 記号 | 反映先 |
| --- | --- | --- | --- | --- | --- |
| INS-1 | 検査機構を足したら「対象が何件あり、そのうち何件を実際に見たか」を突き合わせる検… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-1B | 件数の閾値で置いた陽性対照は総崩れしか検出しない | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| INS-2 | 検証手段の層の優先順位 (型システム > 構文木 > トークナイザ > 正規表現… | 採らない | Claude | R4 |  |
| INS-2C | 実装の確認や調査でコードを引くとき grep より ast-grep を優先する | 採らない | Claude | R4 |  |
| INS-3 | 使い捨ての検証ツールの誤りは検証対象の欠陥と同じ形で出る。決着はツールの出力どう… | 採る | 人 |  |  |
| INS-4 | 外部サービスとの契約を増やしたら Fake 側にも同じ契約を足す。テストの本数で… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| INS-5 | 変異の見逃しは pin が弱いとは限らない。到達不能な分岐は見逃しとして現れ、正… | 採る | 人 |  |  |
| INS-6 | fixture の深さが pin の射程を決める。実コードの構造の深さを fix… | 採る | 人 |  |  |
| INS-7 | 警告をエラーにするビルドで、変異が引数や変数を未使用にすると、テストより先にコン… | 採る | 人 |  |  |
| INS-8 | 変異が緑のとき、pin の弱さより先に (a) 変異が等価でないか (b) fi… | 採る | 人 |  |  |
| INS-9 | 変異の判定は rc だけでなく、狙った FAIL の行が出たかで行う。bash … | 採る | 人 |  |  |
| INS-10 | 変異が実際に入ったかを diff で確かめてから結果を読む。perl の置換パタ… | 採る | 人 |  |  |
| INS-11 | 変異の実行器が「変異前のファイルが写しと一致すること」を確かめる作りだと、コード… | 採らない | Claude | R5 |  |
| INS-12 | 成果物に残った綴りを数える検査 (Release に Debug 専用の型が残ら… | 採る | Claude | 14 | ~/.claude/references/tool-xcode.md (新規) |
| INS-13 | 包みの層を挟んだ契約は2段の変異で両側から示せる。利用側の述語を偽にすると利用側… | 採らない | Claude | R4 |  |
| INS-14 | 生成の直後に同じ生成物の整合を確かめる検査 (lock を書き換えた直後の `-… | 採る | Claude | 14 | ~/.claude/references/testing.md に生成物の検査の節を新設 |
| INS-15 | E2E で「ある要素が0件」を自動再試行の assertion で確かめると、描… | 採る | Claude | 14 | ~/.claude/references/testing.md に E2E の陰性の確認の節を新設 |
| INS-16 | 時間切れを確かめるテストの代役 CLI を `sleep` だけのシェルスクリプ… | 採る | Claude | 14 | ~/.claude/references/testing.md に時間切れのテストの節を新設 |
| INS-17 | `assertIs(x, os.environ)` や `assertEqual… | 採る | Claude | 14 | ~/.claude/references/tool-python.md (新規) |
| INS-18 | 発生率が数%の現象は30回程度では有無を言えない。再現ループで0/59、本番の手… | 採る | 人 |  |  |
| INS-19 | ライブラリの assertion が実装の切り替えの前後で同じ意味を持つと、既存… | 採る | Claude | 14 | ~/.claude/references/tool-playwright.md (新規)。報告 2026-11-04、Playwright 1.62 と添える |
| INS-20 | 経路を通ったことの確認には、計測の仕組みを外す変異を少なくとも2形当てる。E2E… | 採る | Claude | 14 | ~/.claude/references/testing.md の変異注入の節 |
| INS-21 | node:test の `test(name, { timeout }, fn)… | 採る | Claude | 14 | ~/.claude/references/tool-node.md (新規) |
| INS-22 | 綴りで行を数える検査は、同じ綴りを含むコメント行を拾う。workflow の Y… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-23 | 「この型を作るのは1ファイルだけ」を型名の出現で書いた ast-grep のルー… | 採る | Claude | 14 | ~/.claude/references/tool-ast-grep.md (新規)。報告 2026-11-04、ast-grep 0.45 と添える |
| INS-24 | テストの件数の突き合わせは、テストを1件消して別の1件を増やすと相殺されて緑のま… | 採らない | 人 |  |  |
| INS-25 | 検査器の取り付けを接頭辞の規約 (`verify_*.py` のような名前) で… | 採る | Claude | D | ~/.claude/references/testing.md の「検査機構を足したときの 3 種の変異と範囲」節 |
| INS-26 | 止め方を disabled に戻す変異で、止める関数の呼び出しを書き換えただけだ… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-27 | 緑の原因が守る対象とは別の層にあることがある。キーボードが起こした click … | 採る | Claude | 14 | ~/.claude/references/testing.md の「赤くなっても pin が有効とは限らない」節の隣 (緑の原因が別の層にある形) |
| INS-28 | 多層防御の片方の層を外す変異が緑でも dead pin とは限らない。もう片方の… | 採る | 人 |  |  |
| INS-29 | 同じ役目の処理を2か所に置くと (前のタイマーを消す処理、同じ役目のガード)、片… | 採る | Claude | M | INS-28 に統合 |
| INS-30 | 解釈器と reducer に同じ前提の判定が二重にあると、本番は解釈器の側で止ま… | 採る | Claude | M | INS-28 に統合 |
| INS-31 | 「A と B の数え先 (バケット) が分かれている」テストには「B 自身は使い… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| INS-32 | 変異の前に、変異を当てる経路と同じ経路で無変異の陽性対照を回す。実装役に回させな… | 採る | Claude | D | ~/.claude/rules/testing-practices.md の変異注入の項 |
| INS-33 | タイムゾーンで挙動が変わる日付処理の pin は、テスト内で `vi.stubE… | 採る | Claude | 14 | ~/.claude/references/testing.md にタイムゾーンに依存するテストの節を新設 |
| INS-34 | 変異の赤は、どのアサーションが何を見て落ちたかを読んでから証拠にする。行ロックを… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-35 | DB の例外を見る assert は SQLSTATE だけでなく理由のメッセー… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-36 | `playwright test --project chromium <fil… | 採らない | Claude | R6 |  |
| INS-37 | 変異に時間の遅れを加えると、タイミング次第で赤くなるだけの pin を見分けられ… | 採らない | Claude | R4 |  |
| INS-38 | 検査の射程を広げたときは、広げた分だけが赤くなる変異を計算で作る。コントラストの… | 採る | Claude | D | ~/.claude/references/testing.md の「範囲の穴は 3 種の変異では見えない」節 |
| INS-39 | 検査の射程を広げたら、広げた側の各ファイルに存在しない番号を書く変異を当て、その… | 採る | Claude | M | INS-38 に統合 |
| INS-40 | stderr を捨てる変異を1か所ずつ入れて、狙った assert だけが赤にな… | 採らない | Claude | R4 |  |
| INS-41 | witness (この経路を踏んだことを示す非0の数) は、数える条件を機構の発… | 採る | Claude | D | ~/.claude/references/observation.md の「非 0 件も証明にならない」節 |
| INS-42 | 簡素化の提案でテストの観測の仕組みを変えたら (Mutex のカウンタを Cel… | 採る | Claude | D | ~/.claude/rules/testing-practices.md の変異注入の項 |
| INS-43 | テストを別の関数へ付け替える機会に変異の網羅を見直したら、比較を `!=` へ変… | 採らない | Claude | R4 |  |
| INS-44 | pin と本体が同じ値を見ると守れない。呼び出し口が定数の base を使うこと… | 採る | Claude | 14 | ~/.claude/rules/testing-practices.md (詳細は references/testing.md) |
| INS-45 | E2E の Fake で「重ねて呼ばれていない」を pin するとき、記録を a… | 採る | Claude | 14 | ~/.claude/references/testing.md に Fake の作り方の節を新設 |
| INS-46 | 「上限を超えたら読みを止める」の pin は、結果だけでなく代役のストリームが引… | 採る | Claude | 14 | ~/.claude/references/testing.md に Fake の作り方の節を新設 |
| INS-47 | テストの Fake が2つの出力 (判断の値と、その副作用のカウンタ) を同じ条… | 採る | Claude | 14 | ~/.claude/references/testing.md に Fake の作り方の節を新設 |
| INS-48 | 「何も起きないこと」を確かめる E2E は、時間待ちではなくクライアント自身が上… | 採る | Claude | 14 | ~/.claude/references/testing.md に E2E の陰性の確認の節を新設 |
| INS-49 | 設定ファイル (TOML) の表を unittest の dict の exac… | 採る | Claude | 14 | ~/.claude/references/tool-python.md (新規) |
| INS-50 | シェルのテストハーネスで否定の assert が非0の終了をすべて PASS と… | 採る | Claude | 14 | ~/.claude/references/testing.md にシェルのテストハーネスの節を新設 |
| INS-51 | 外部 API の契約テストの fixture は、実 API の応答から鍵の集合… | 採る | Claude | D | ~/.claude/references/testing.md に契約テストの fixture の節を新設 |
| INS-52 | 写しが canonical と一致することを守る静的検査で、走査の母集団を ca… | 採る | Claude | D | ~/.claude/references/canonical.md に写しの一致を守る検査の節を新設 |
| INS-53 | 追跡ファイルを走査する検査を足すとき、検査のテストファイル自身が例の文字列を l… | 採らない | Claude | R5 |  |
| INS-54 | 検査の対象を参照や一覧で決め、見つからないものを黙って飛ばすと、足し忘れが検査さ… | 採る | 人 |  |  |
| INS-55 | 置いてはいけないものを名前で拒む denylist は、新しい経路が足されたとき… | 採る | Claude | 14 | ~/.claude/rules/testing-practices.md (詳細は references/testing.md) |
| INS-56 | ast-grep のルールを綴りの列挙で書くと、列挙に無い綴りを素通しする。証人… | 採る | Claude | 14 | ~/.claude/references/tool-ast-grep.md (新規)。版は未記録と添える |
| INS-57 | just のゲートの集約から検査の手順が落ちたら赤くするには、手順のレシピに g… | 採る | Claude | 14 | ~/.claude/references/tool-just.md (新規)。版は未記録と添える |
| INS-58 | just の recipe と GitHub Actions の workflo… | 採る | Claude | 14 | ~/.claude/references/tool-just.md (新規) |
| INS-59 | 判定ロジックの式を件数だけでなく md5 (コマンド・ロール・式の連結) でカタ… | 採らない | Claude | R4 |  |
| INS-60 | 製品側の未到達の集合を exact に pin するカバレッジの検知器が、配線を… | 採らない | Claude | R4 |  |
| INS-61 | 生成物をソースへ書き戻す仕組みは、「書き戻しても変わらない (不動点)」をテスト… | 採る | Claude | 14 | ~/.claude/references/testing.md に生成物の検査の節を新設 |
| INS-62 | コードを生成するスクリプトのユニットテストが緑でも、生成物はコンパイルで落ちた … | 採る | Claude | 14 | ~/.claude/references/testing.md に生成物の検査の節を新設 |
| INS-63 | smoke で応答ヘッダの付け忘れを見るとき、期待する値を写さず「付けない経路に… | 採る | Claude | D | ~/.claude/references/observation.md の「何を何件見たか」節 |
| INS-64 | 全列挙の件数の pin を、プロダクトの出力ではなくオラクルの側だけで決まる値で… | 採る | Claude | 14 | ~/.claude/references/testing.md に全列挙のテストの節を新設 |
| INS-65 | 判定ロジックを仕様の特徴づけから導いて作り直し、構造の違うオラクル (粗い格子の… | 採らない | Claude | R4 |  |
| INS-66 | 状態×遷移×期限 (前・ちょうど・後) のような小さな有限の定義域は、期待値をデ… | 採らない | Claude | R4 |  |
| INS-67 | 許容内の揺らしで答えが変わらないことを見るメタモルフィックテストが、揺らす向きを… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| INS-68 | 条件付きの文面を組み立てる生成器は、タグを1つずつ ON にしたテストだけでは条… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| INS-69 | 契約テストの golden が toolchain の更新で動いたときは、更新す… | 採らない | Claude | R4 |  |
| INS-70 | 形式手法とテスト技法の適用箇所を、領域ごとの調査役と前提を疑う役の Workfl… | 採らない | Claude | R4 |  |
| INS-71 | Makefile のガード (`@case ...`) の効き目を `make … | 採らない | Claude | R4 |  |
| INS-72 | pre-commit は hook を走らせる前に unstaged の変更を退… | 採る | Claude | D | ~/.claude/references/testing.md の「発火条件が tracked に依存する検査」節 |
| INS-73 | Python の変異では古い `__pycache__` の `.pyc` が読… | 採る | 人 |  |  |
| INS-74 | 作業ツリーをその場で書き換えて try/finally で戻す変異のハーネスは、… | 採る | 人 |  |  |
| INS-75 | Vite プラグインへの変異はテストランナーにも効く。vitest は `vit… | 採る | Claude | 14 | ~/.claude/references/tool-vitest.md (新規)。版は未記録と添える |
| INS-76 | 変異の実行役に「退避、置き換え、テスト、cp で復元、ハッシュ照合、失敗したテス… | 採る | 人 |  |  |
| INS-77 | 変異で狙ったテスト以外まで赤くなったときは、推測で「無関係」と片付けずに条件を切… | 採らない | Claude | R4 |  |
| INS-78 | 生成物を読み戻す `--check` が生成物を1項目1行の正規表現で読んでいた… | 採る | Claude | D | ~/.claude/references/testing.md に生成物の検査の節を新設 |
| INS-79 | 1/3回だけ落ちる E2E の競合を、片方の要求を `page.route` で… | 採る | Claude | 14 | ~/.claude/references/testing.md に E2E の競合の再現の節を新設 |
| INS-80 | fake の ResizeObserver を「最初の通知は新しく observ… | 採る | Claude | 14 | ~/.claude/references/testing.md に Fake の作り方の節を新設 |
| INS-81 | E2E で「諦めた後に1本だけ増えた」を示す前に、諦めていなければ次の試行が来る… | 採らない | Claude | R4 |  |
| INS-82 | 文書の「照合の射程」と、機械の照合が見ている範囲は黙ってずれる。生成物の中身 (… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-83 | 設定から読む「http を許すか」の印は、`YES` ちょうど以外 (キーの欠落… | 採らない | Claude | R4 |  |
| INS-84 | YAML の top-level にキーを足す変異を perl で注入したら、対… | 採る | Claude | 14 | ~/.claude/references/testing.md の変異注入の節 |
| INS-85 | 「特定の項目がこの位置にある」ことを pin するテストは、本体の配列の lit… | 採らない | Claude | R4 |  |
| INS-86 | 検査を足したら、比較の向きを変える変異 (NaN を失敗の側へ倒す否定の比較を、… | 採らない | Claude | R4 |  |
| INS-87 | エラー文の中の秘密を文字列置換で伏せるとき、テストの架空の値が周りの固定文字列の… | 採る | Claude | 14 | ~/.claude/references/testing.md の fixture の値の選び方の節 |
| INS-88 | 担当の subagent が赤を見ずに書いたテストは、コントローラが実装を1か所… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| INS-89 | ソースの grep 系の検査でコメントを落とすとき、文字列の中身まで落とすと補間… | 採る | Claude | 14 | ~/.claude/references/testing.md の fixture の値の選び方の節 |
| INS-90 | 拒否集合のテストを UCD の範囲表の全符号位置で回し、弾いた件数・通した件数・… | 採る | Claude | 14 | ~/.claude/references/testing.md に全列挙のテストの節を新設 |
| INS-91 | 写す・公開する系の操作の前の検査は、写す時点 (merge の後) だけでなく、… | 採らない | Claude | R4 |  |
| INS-92 | 「届かなかったときの既定値」を `\\|\\| code=000` のように置く行は… | 採る | Claude | 14 | ~/.claude/references/testing.md の変異注入の節 (既定値の盲点) |
| INS-93 | 「古い状態を読んで緑になるのでは」という静的レビューの指摘を、変異の赤で反証でき… | 採らない | Claude | R4 |  |
| INS-94 | 計画のファイル名や見出しを「計画への参照の語」として自動で集め、コードへの混入を… | 採らない | Claude | R5 |  |
| INS-95 | Quint の仕様の検査に、前提スイッチを倒した写しで inv が破れることと、… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| INS-96 | 「条件つき UPDATE で行を確保する」関数を「select で状態を読んでか… | 採る | Claude | 14 | ~/.claude/references/testing.md に並行性のテストの節を新設 |
| INS-97 | 静的な走査器 (Wiring テスト) を広げたときに、走査器の射程の穴を、直し… | 採る | Claude | D | ~/.claude/references/testing.md の「範囲の穴は 3 種の変異では見えない」節 |
| INS-98 | ディレクトリを歩いて作る走査の集合に「ファイル数の完全一致」の pin を置くの… | 採らない | Claude | R4 |  |
| INS-99 | 走査器の実ファイルの検査は、検査を緩める方向の変異 (sink の集合から1つ外… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-100 | 外部の公開一覧 (例: Node の dist/index.json) を「1項… | 採る | 人 |  |  |
| INS-101 | psql の ON_ERROR_STOP で走る SQL の回帰テストで、mig… | 採らない | Claude | R4 |  |
| INS-102 | 着手前の検査で、隔離した場所で実際に Playwright を動かすレンズが、計… | 採る | Claude | 14 | ~/.claude/references/testing.md の変異注入の節 |
| INS-103 | xtask などに YAML / ini のパーサが無いとき、2か所に書かざるを… | 採らない | Claude | R4 |  |
| K88-001 | 検査の緑を信じる前に、壊したら赤くなるかを1か所ずつ変異で確かめると、テストが足… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-104 | CLI を PATH の先頭の stub で差し替えるテストで、stub が `… | 採る | Claude | 14 | ~/.claude/references/testing.md に Fake の作り方の節を新設 |
| INS-105 | テストから待ちのスクリプトを呼ぶとき、待ちの上限を短く (5秒) 置き、テスト側… | 採らない | Claude | R4 |  |
| INS-106 | ast-grep (0.45.3) の CSS の規則で、抑止コメントを `# … | 採る | Claude | 14 | ~/.claude/references/tool-ast-grep.md (新規)。報告 2026-11-13、ast-grep 0.45.3 と添える |
| INS-107 | 負荷の高いときだけ落ちるテストが、前のテストの非同期処理の漏れ (完了を待たずに… | 採る | Claude | 14 | ~/.claude/references/testing.md に揺れるテストの再現の節を新設 |
| INS-108 | 変異注入のハーネスがログに `error: Tests failed` を並べる… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-109 | 描画を測る E2E の判定に「免除の一覧の各行が1件以上に当たる」assert … | 採る | Claude | D | ~/.claude/references/testing.md の「検査を緩める変更には緩めすぎる方向の変異を置く」節 |
| INS-110 | ast-grep 0.45.3 の `ast-grep test` は抑止コメン… | 採らない | Claude | R4 |  |
| INS-111 | 版の固定のような整合性の検査を足すとき、変異の3種目 (取り付けを外す) として… | 採る | Claude | D | ~/.claude/references/testing.md の「検査機構を足したときの 3 種の変異と範囲」節 |
| INS-112 | 設定ファイルの値の一致を固定するテストに変異を入れて赤くなるかを見るとき、pnp… | 採る | Claude | 14 | ~/.claude/references/tool-pnpm.md (新規)。版は未記録と添える |
| INS-113 | 包むレシピと呼び先のレシピが同じ入力の検査を持つとき、レビューの観点が「重複だか… | 採らない | Claude | R4 |  |
| INS-114 | 新しいレシピの pin を14本の変異で1か所ずつ壊し、それぞれ狙ったテストが狙… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-115 | 「並べ替えの最後の決め手を外す」変異は、DuckDB の並列の集計だと同じ件数の… | 採る | Claude | 14 | ~/.claude/references/testing.md の fixture の値の選び方の節 |
| INS-116 | 手元が日本時間のホストでは「端末のタイムゾーンで割り当てる」変異が見えない。テス… | 採る | Claude | 14 | ~/.claude/references/testing.md にタイムゾーンに依存するテストの節を新設 |
| INS-117 | TZ を切り替える道具が持つゾーンの一覧はただの配列なので、describe.e… | 採る | Claude | M | INS-116 に統合 |
| INS-118 | 記録して応答を返すだけの偽の DB では、クエリの絞り込み (not、limit… | 採らない | Claude | R4 |  |
| INS-119 | タスクのレビューが「手計算なら赤になる」とした断言を、古い実装へ戻す変異で実測し… | 採らない | Claude | R4 |  |
| INS-120 | 穴 (自クレートへの dev-dependency で有効にする test-su… | 採る | Claude | M | INS-111 に統合 |
| INS-121 | 確率で落ちる property-based test の反例を読むと、テストのオ… | 採る | Claude | 14 | ~/.claude/references/testing.md に property-based test の節を新設 |
| INS-122 | property-based test が CI で出した種 (proptest… | 採らない | Claude | R4 |  |
| K88-002 | グローバルの CLAUDE.md の委譲カテゴリにある「実験はリポジトリ本体では… | 採る | Claude | D | ~/.claude/references/delegation.md の「並列 subagent の実験場所」節 |
| INS-123 | E2E に「上限を広げる」変異を入れ、本物のバックエンドが400を返して赤くなる… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| INS-124 | テストのヘルパが成功のときに `undefined` を返し、`expect(e… | 採る | Claude | 14 | ~/.claude/rules/testing-practices.md の弱い assertion の項 (詳細は references/testing.md) |
| INS-125 | 既存のユニットテストが、バックエンドが拒む入力 (語の間のタブ) を「通す」と固… | 採らない | Claude | R4 |  |
| INS-126 | 処理系の名前を語の境界で探す正規表現で前の `/` を弾くと、パスで名指しした起… | 採らない | Claude | R2 |  |
| INS-127 | 「値を出さない」を assertNotIn だけで見るテストは、検出が壊れて空の… | 採る | Claude | D | ~/.claude/rules/testing-practices.md の弱い assertion の項 |
| INS-128 | 変異の一覧を当てる前に、ガード (入力の表の形の検査) にテストが1本も無いこと… | 採らない | Claude | R4 |  |
| INS-129 | 検査の docstring に理由つきで書いた免除 (「載っていないことは見ない… | 採る | Claude | D | ~/.claude/references/testing.md の「検査を緩める変更には緩めすぎる方向の変異を置く」節 |
| INS-130 | 検査が見た件数を、検査に渡す配列とは別の変数で数えていたら、渡し忘れの変異でも件… | 採る | Claude | D | ~/.claude/references/observation.md の「非 0 件も証明にならない」節 |
| INS-131 | permissions の allow の照合は、just に触れる項目をどの書… | 採らない | Claude | R4 |  |
| INS-132 | TOML の pin をテストから読むとき、正規表現ではなく tomllib (… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| INS-133 | ast-grep で Rust の enum の変種がどこで組まれているかを数え… | 採る | Claude | 14 | ~/.claude/references/tool-ast-grep.md (新規)。版は未記録と添える |
| INS-134 | ast-grep は項に付いた `#[cfg(...)]` の属性を読めるので、… | 採らない | Claude | R4 |  |
| INS-135 | 計画の文書に書いた性質 (「A の後に B が消えた ⇔ 関数が B を返す」の… | 採る | Claude | 14 | ~/.claude/references/testing.md に property-based test の節を新設 |
