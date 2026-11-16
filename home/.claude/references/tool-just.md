# just の一次実測

`~/.claude/references/tools.md` が名指しする、just と justfile の事実と手当て。

規範の遵守そのものには要らない。justfile の recipe を書くとき、recipe の構造をテストや検査で読むとき、just の挙動が想定と食い違ったときに読む。版に依存する節には just の版を添え、記録の無いものは「版は未記録」「報告日は未記録」と書く。

処理系の版を拒むガードを recipe の依存に置く形は `~/.claude/references/observation-checks.md` の「処理系の版は宣言だけでは拒まれない」節が持つ。ここには書き直さない。

## 引数の素通しは `{{args}}` で展開しない

justfile で `*args` を `{{args}}` で展開して、引数を recipe の中のコマンドへ素通しするときに踏む。

- `*args` を `{{ args }}` で展開すると、空白を含む引数が分割される。`just --dry-run` で `-t "a b"` が `-t a b` に割れ、`set positional-arguments` と `"$@"` で保たれた (実測)
- `{{args}}` を本文に書くと、レシピ本文を静的に読むテストの補助関数が式の展開を扱えず壊れることがある。`[positional-arguments]` と `"$@"` にすると本文に `{{...}}` が残らず、クォートも安全になる (実測)
- justfile skill の例も `{{args}}` の形なので同じ罠を踏む。例を写すときは上の形に直して書く。skill の例の側を直す (提案)

## justfile の構造を読む

justfile の recipe の依存や本文を、テストや検査で読むときに開く。

- 構造は `just --dump --dump-format json` で取れ、recipe ごとの依存 (priors 付き) と本体の行が返るので、regex で text-parse しなくて済む。CI に just が無いなら taiki-e/install-action で公式のリリースを入れる (実測)
- 続きの行: dump はレシピ本文の `\` で続けた行を別々の行として持つ。行単位で「この呼び出しの行が X を含む」と見る検査は、続きの行に置かれた X に届かず緑のまま通った。本文全体で見る形に変えると赤になった (実測)
- 後置の依存: dump の dependencies をそのまま辿る閉包は、`&&` の後置 (本体の後に走る依存) に置いたガードも「先に通る」と数える。本体より先に走るのは先頭の priors 件だけなので、`dependencies[:priors]` で切る必要がある (実測。後置に移しても全テストが緑のままだった)
- 解釈系の読み方: 本文からコメント行を除いて語を探す読み方では、shebang (`#!/usr/bin/env node`) のレシピを取りこぼす。dump は shebang を本文の1行目に `#!` のまま載せるため。`[script("...")]` 属性の解釈系は本文ではなく attributes に載る。どちらも本文の語とは別に、basename で解釈系を読む必要がある (実測)
- shebang のレシピの本文の検査: dump で名前と必須の引数の数を取り、`just --dry-run --no-deps <名前>` が stderr に出す本文を shellcheck にかけると検査できる。dry-run は実行せずに `{{ }}` を置き換える (just 1.59.0、macOS と Linux の runner で同じ件数) (実測)
- dry-run と backtick: dry-run は backtick で値を作る変数を評価せず backtick の式のまま出すので、取り出した本文が本物と食い違う。本文の `{{ }}` に backtick 由来の変数を使わない決まりにすると、破ったときは SC2006で赤になる (実測)

## dump から取り付けの検査を導く

just のゲートの集約から検査の手順が落ちていないか、ガードや recipe の取り付け忘れが無いかを検査するときに開く。報告日は未記録、just の版は未記録。

- 群から集約の依存を見る形: 手順のレシピに group 属性を付け、`just --dump --dump-format json` の attributes から群を読んで、「集約の直接の依存は群に在る」と「群は起点から届く」の2つを見る。集約から検査の手順が落ちたら赤くなり、群の一覧を別に持たないので drift しない (実測)
- 両方向の突き合わせ: gate のレシピ (`[group('gate')]`) と preflight の依存を dump の json で両方向に突き合わせる検査を足すと、足したばかりの検査自身の取り付け忘れを最初の実行で赤にできた。Claude Code の allow に名前で載せたレシピも同じ検査で突き合わせると、2か所に書いた一覧が drift しない (実測)
- 本文と呼び先から対象を導く形: 処理系の版のガードを付けるべきレシピを一覧で持たず、dump から導いて、テストで付け忘れを赤にした。本文が処理系を起動するものと、処理系を起動するスクリプトを呼ぶもの (import の兄弟まで辿る) を数える (実測)
- タスクランナーが解釈した構造から取り付けの検査を導くと、レシピを足したときの付け忘れがその場で赤くなる。今の定義に無い形は、合成した dump を導出の関数へ渡して陰陽の両方を固定できた (実測)

dump を読むときの罠 (続きの行、priors、shebang、script 属性) は上の「justfile の構造を読む」節にある。

## recipe と CI の workflow を突き合わせる

just の recipe と GitHub Actions の workflow が同じコマンドを同じ順に走らせていることを、テストで突き合わせるときに開く。報告日は未記録、just の版は未記録。

突き合わせるテストで、許す差 (CI だけのステップと if 条件) を1つの表に置き、差の相手のコマンドが just 側から消えたら表の適用が失敗する作りにすると、「差の表だけが残る」drift と取り付けを外す変異の両方が赤になった (実測)。

## Homebrew の just が canonical の版とずれたとき

Homebrew の just がリポジトリの canonical の版とずれ、版を照合する検査が入口で止まったときに開く。報告日は未記録、just の版は未記録。

- Homebrew の自動更新で手元の just がリポジトリの canonical の版 (CI は sha256 の照合つき) より新しくなり、版を照合する検査で preflight が入口で止まった。ホストを変えずに揃えるには、`cargo install just --version <版> --locked --root <repo>/.cache/<dir>` でソースから組んで PATH の先頭に置く。レシピの中から just を呼び直す検査があるので、PATH で差す (実測)
- brew には公開からの日数を待つ仕組みも版の pin も無く、just では GitHub Release の公開から formula の更新まで約1.5時間だった (実測)
