---
status: closed
---

# docs(rules): Rust のビルド規範を rules と references へ入れる

## 背景

2 つの委譲元から独立に届いた Rust のビルド規範を統合して取り込む。別々に起票しない。
両者は同じ規範へ収束しており (RUST-01 と BP-01、RUST-02 と BP-05)、分けると同じ規範を
2 箇所へ書くことになる。

材料は検証ワークフローで委譲元の追跡下 canonical と突き合わせてある。委譲元の主張のうち
5 件が反証されているので、そのまま規範として書かないこと。

### 反証された前提

- 「`[profile.*]` を workspace root へ集約する理由は rust-cache の lockfile ハッシュで
  正規化対象外だから」は委譲元の推論。委譲元の canonical が記録する理由は別の 2 点で、
  (1) `[profile.dev.package."*"]` には環境変数形が存在しない (2) 設定漏れのビルド経路が
  複数あった。しかも canonical の実効的な半分「workflow や Dockerfile の `CARGO_PROFILE_*`
  環境変数で上書きしない」が材料から落ちている
- 「リンカを明示選択すると効く (aarch64 で lld にすると数倍)」は汎用規範として成立しない。
  rustc 1.90 以降 `x86_64-unknown-linux-gnu` は self-contained rust-lld が既定で CI 側は既に
  lld で動く。効き目はローカル arm64 との非対称だけで、倍率は集約前の構成での測定。
  委譲元が pin (`rust-toolchain.toml` の channel) で条件成立を再確認済み。RUST-07 は取らない
- 「まだ存在しない `.cargo/config.toml` も path-filter に先に含める」は成立しない。委譲元の
  canonical が「このリポジトリでは使えない」と結論しており、限界カバレッジが 0
- 「`references/` にビルド性能に触れる行は 0 件」は再現しない。同じ語で引くと hit する。
  実質的な主張 (ビルド性能の規範は無い) は成立するが、報告された 0 件は再現しない。委譲元は
  0 件を得た検査条件を書いていないので、どの版のどのパスで引いたかが辿れない
- 「`rules/rust-practices.md` の tests/ 集約項は『時間』と書いており誤り」は偽。既存本文は
  「時間が線形に増える」とは書かず、増える対象を「再コンパイルと再リンク」と書いている。
  BP-16 は事実の誤りの修正ではなく「量を名指ししていない曖昧さの解消」であり blocking ではない

### 取り込む規範

識別子は検証ワークフローの採番。材料は追跡外の非公開の置き場に復元済み (2026-10-01)。

既存の `rules/rust-practices.md` へ入れるもの:

| ID | 内容 |
| --- | --- |
| RUST-01 | キャッシュを足す前にビルドの律速を実測する。キャッシュは 1 回あたりの作業量を減らさない |
| RUST-02 | ビルドを速くする配線は外れてもエラーではなく緑のまま効かないで返る。wall ではなく配線の生死を示す指標で判定し、観測手段が対象ビルドと同一プロセス・同一 RUN にあることまで確かめる |
| RUST-03 | 設定の canonical を workspace root の Cargo.toml へ置き、workflow や Dockerfile の環境変数で上書きしない |
| RUST-04 | ビルドの並列度に上限を置く。`CARGO_BUILD_JOBS` は上限ではなく絶対値なので `min(nproc, 上限)` を自前で算出する |
| RUST-05 | 計装・`CARGO_TARGET_DIR`・rustflags を変えるツールは fingerprint が別物になる。Cache hit と出ても再コンパイルする |
| BP-16 | tests/ 集約項で線形に増える量を「ディスクと user CPU」と名指しする (コア数ぶん並列にリンクされるので wall には出ない) |
| BP-17 | 「集約後の健全性は実行されたテストケース数で確認する」を CLAUDE.md の「件数ではなく実行されたテストの ID 集合を pin する」へ揃える |

新設する `rules/cargo-build-practices.md` へ入れるもの (BP-01 / BP-02 / BP-03 / BP-04 /
BP-05 / BP-06、枠は BP-07):

- 遅さの出所がビルドの中にあることを確かめるまで Cargo へ手を入れない
- profile のキーの射程は書いた場所ではなく rustc の実引数で確かめる
- デバッグ情報などを落としたら対称な退避先 profile を置く
- feature による除外が成立するのは 1 回の build invocation の中だけ
- 設定が効いたかをそのキーが動かすはずの量で判定する
- 時間を比べる前に両条件で実行された単位の集合が一致していることを確かめる

`references/observation.md` へ入れるもの (RUST-09 / RUST-10):

- サードパーティの action / ツールのどの入力が効くかを README ではなく使っている版のソースで確かめる
- 観測器そのものが対象の状態を作り替える形の実例

新設する `references/` へ入れるもの (BP-08 / BP-09 / BP-10 / BP-11 / BP-12、枠は BP-13):
コンパイルキャッシュと incremental の取引、削減率を他環境から持ち込まない、ホスト OS 由来の
遅さの一次実測、profile の射程の一次実測、CI キャッシュの一次実測。

取らないもの: RUST-06 / RUST-07 / RUST-08 / RUST-11 / BP-14 / BP-15。

### 予算

常時層 +0B / scoped +7,800B / references +5,130B。常時層に触らないので `BUDGET_RAISES` は
この Issue の範囲では要らない。言語横断の置き場とホスト OS 側の置き場も常時層へは倒さなかった (「決定」節)。

## タスク

- [x] RUST-01 / RUST-02 / RUST-03 / RUST-04 / RUST-05 を `rules/rust-practices.md` へ入れる
- [x] BP-16 / BP-17 で `rules/rust-practices.md` の既存 2 項を締める
- [x] `rules/cargo-build-practices.md` を新設し BP-01〜BP-07 を入れる
- [x] `config_guard.rules_paths.EXPECTED_PATHS` へ新設 rules の pin を理由コメント付きで足す (BP-18)
- [x] RUST-09 / RUST-10 を `references/observation.md` へ足す
- [x] 新設 references を作り BP-08〜BP-13 を入れる
- [x] 第三者 org の内部識別子と数値を落とす。機構と桁だけを残して抽象化する
- [x] 新設 rules の `paths` が実マッチャで発火することを確かめる。pin だけでは沈黙する rules が
      できる (`rules_paths.py` は glob の意味論を検証しないと明記している)

## 取り込みで分かったこと (2026-10-01)

- 検証ワークフローが unverifiable とした Cargo のセマンティクスを定義元で確かめた。上書きの優先順位は Cargo Book の Overrides 節と一致した。`package."*"` の射程は「workspace member 以外のすべて」で、これを本文に足した
- RUST-04 の「`CARGO_BUILD_JOBS` は上限ではなく絶対値」は、Cargo の config リファレンスが `build.jobs` を「並列に走らせるコンパイラプロセスの最大数」と書いており、そのままでは誤読を招く。実効的な述語は「固定値はコア数で頭打ちにならない」なので、そちらで書いた
- 「sccache は incremental と非互換」は、sccache の README の記述「incremental でコンパイルされる crate はキャッシュできない」へ寄せた。非互換なのは crate 単位で、Cargo の dev 既定では workspace member と path 依存が incremental になる

### paths の live probe

新しい headless の `claude -p` (2.1.286) を1セルにつき1プロセス起動し、リポジトリの外に `git init` した使い捨ての fixture の中で Read させた。注入は transcript の `nested_memory` の attachment に rule の本文が現れるかで判定した (stream-json の出力には現れない)。

| 宣言 | 直下の `Cargo.toml` (陽性の対照) | 直下の `.cargo/config.toml` | ネストした `.cargo/config.toml` | `cargo/config.toml` (陰性の対照) |
| --- | --- | --- | --- | --- |
| `**/.cargo/config.toml` | 発火 | 発火 | 発火 | 発火しない |
| `.cargo/config.toml` | 発火 | 発火 | 発火しない | 発火しない |

判定の規則は測る前に決めた (`**/` の形が両方で発火すればそれを採る)。管理下のリポジトリの `.cargo/config.toml` は直下よりネストした位置に多く、prefix の無い形では大半が沈黙するので `**/.cargo/config.toml` にした。

## 決定 (2026-10-01)

着手前に未決だったものを、ユーザーとの確認と上の probe で決めた。

- 射程は Rust に閉じる。RUST-01 / RUST-02 は Rust 固有ではないが、実証が集まるまでは `rules/rust-practices.md` に置く。常時層は +0B で、`BUDGET_RAISES` は要らない
  - 新設 references は `references/rust-build.md` とし、ホスト OS の節もここへ置く。到達の契機は `Cargo.toml` / `.cargo/config.toml` / `.rs` の Read に限られ、「ローカルのビルドが遅い」と感じた瞬間には届かないことがある。この穴は承知のうえで、`host-environment.md` の射程を広げる案 (`BUDGET_RAISES` が要る) は採らない
  - `references/observation.md` の伸びは許す。RUST-09 / RUST-10 は既存節の追記と2例目で、節は増やしていない
  - references を1枚増やすことは許す。ISSUE-48 の「採らない案」は常時層からの移設の収支の話で、新規の追加には当たらない
- `rules/rust-practices.md` には、コスト側の H1 を 2 本目として立てた。既存の見出しの述語は正しさの側で、射程が違う
- `.cargo/config.toml` の `paths` は `**/.cargo/config.toml` にした (上の probe)
- `rules/rust-practices.md` の `paths` は広げない
- ISSUE-48 より先にこの Issue を通した。BP-01 / BP-02 は Cargo の形のまま入れてある
- 委譲元の固有の情報は落とし、機構と桁だけを残した

## 未決

- 委譲元への返信の粒度。材料に書かれた件数と実測が食い違っている。件数の訂正まで伝えるか、述語の採否だけ伝えるか。dotfiles の外の作業なので、この Issue のタスクには含めない

## 関連

- ISSUE-88 — 検査機構の作り方の知見。常時層の予算を共有するので配分をまとめて決める
- ISSUE-48 — 観測カテゴリの主語を観測へ引き上げ未被覆の軸を塞ぐ。BP-01 と BP-02 が軸A / 軸C に対応する。この Issue を先に通したので、`rules/cargo-build-practices.md` の BP-01 と BP-02 は ISSUE-48 の再構成で一般形へ引き上げる候補になる (引き上げたら Cargo 側には具体だけを残す)
- ISSUE-46 — 両リポジトリの Issue をマイルストーンへ整理し着手順を決める。所属の canonical は
  あちらの表
- ISSUE-97 — 「試験」節に、この Issue の主張と候補を Jev で仕分けた記録がある
- 2 つの委譲元の原文と検証結果 (反証・配置提案・予算影響) は追跡外の非公開の置き場に復元済み (2026-10-01)
