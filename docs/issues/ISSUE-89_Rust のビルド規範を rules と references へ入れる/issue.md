---
status: open
---

# docs(rules): Rust のビルド規範を rules と references へ入れる

## 背景

2 つの委譲元から独立に届いた Rust のビルド規範を統合して取り込む。**別々に起票しない。**
両者は同じ規範へ収束しており (RUST-01 と BP-01、RUST-02 と BP-05)、分けると同じ規範を
2 箇所へ書くことになる。

材料は検証ワークフローで委譲元の追跡下 canonical と突き合わせてある。**委譲元の主張のうち
5 件が反証されているので、そのまま規範として書かないこと。**

### 反証された前提

- 「`[profile.*]` を workspace root へ集約する理由は rust-cache の lockfile ハッシュで
  正規化対象外だから」は委譲元の推論。委譲元の canonical が記録する理由は別の 2 点で、
  (1) `[profile.dev.package."*"]` には環境変数形が存在しない (2) 設定漏れのビルド経路が
  4 つあった。しかも canonical の実効的な半分「workflow や Dockerfile の `CARGO_PROFILE_*`
  環境変数で上書きしない」が材料から落ちている
- 「リンカを明示選択すると効く (aarch64 で lld にして 2.4 倍)」は汎用規範として成立しない。
  rustc 1.90 以降 `x86_64-unknown-linux-gnu` は self-contained rust-lld が既定で CI 側は既に
  lld で動く。効き目はローカル arm64 との非対称だけで、2.4 倍は集約前の構成での測定。
  委譲元が pin (`rust-toolchain.toml` の channel) で条件成立を再確認済み。**RUST-07 は取らない**
- 「まだ存在しない `.cargo/config.toml` も path-filter に先に含める」は成立しない。委譲元の
  canonical が「このリポジトリでは使えない」と結論しており、限界カバレッジが 0
- 「`references/` にビルド性能に触れる行は 0 件」は再現しない。同じ語で引くと hit する。
  実質的な主張 (ビルド性能の規範は無い) は成立するが、報告された 0 件は再現しない。委譲元は
  0 件を得た検査条件を書いていないので、どの版のどのパスで引いたかが辿れない
- 「`rules/rust-practices.md` の tests/ 集約項は『時間』と書いており誤り」は偽。既存本文は
  「時間が線形に増える」とは書かず、増える対象を「再コンパイルと再リンク」と書いている。
  BP-16 は事実の誤りの修正ではなく「量を名指ししていない曖昧さの解消」であり blocking ではない

### 取り込む規範

識別子は検証ワークフローの採番。材料は `.cache/` 配下に残してある (追跡外)。

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

**取らないもの**: RUST-06 / RUST-07 / RUST-08 / RUST-11 / BP-14 / BP-15。

### 予算

常時層 +0B / scoped +7,800B / references +5,130B。常時層に触らないので `BUDGET_RAISES` は
この Issue の範囲では要らない。ただし未決のいくつか (言語横断の置き場、ホスト OS 側の置き場) を
常時層へ倒すと要る。

## タスク

- [ ] RUST-01 / RUST-02 / RUST-03 / RUST-04 / RUST-05 を `rules/rust-practices.md` へ入れる
- [ ] BP-16 / BP-17 で `rules/rust-practices.md` の既存 2 項を締める
- [ ] `rules/cargo-build-practices.md` を新設し BP-01〜BP-07 を入れる
- [ ] `config_guard.rules_paths.EXPECTED_PATHS` へ新設 rules の pin を理由コメント付きで足す (BP-18)
- [ ] RUST-09 / RUST-10 を `references/observation.md` へ足す
- [ ] 新設 references を作り BP-08〜BP-13 を入れる
- [ ] 第三者 org の内部識別子と数値を落とす。機構と桁だけを残して抽象化する
- [ ] 新設 rules の `paths` が実マッチャで発火することを確かめる。pin だけでは沈黙する rules が
      できる (`rules_paths.py` は glob の意味論を検証しないと明記している)

## 未決

着手前に決める。

- **2 つ目の H1 を立てるか。** 既存見出し (コンパイルが通ったことを証拠にしない) の述語は
  正しさの側で、今回はコストの側なので射程が違う。H1 の本数を縛る機械検査は無いことを確認済みで、
  判断は読みやすさだけで決まる
- **RUST-01 / RUST-02 は Rust 固有ではない。** pnpm store・turbo・gradle・ccache でも同じ形。
  Rust の rules に置くと他言語では届かないが、常時層は余裕 0 なので CLAUDE.md へは置けない。
  言語横断の置き場 (paths 無し rules の新設 = 予算の引き上げ、または references への追記) を
  別途決めるか、今回は Rust 側に置いて実証が集まってから考えるか
- **新設 references の名前。** `rust-build.md` だとホスト OS の節と CI キャッシュの節が名前の
  射程から外れる。`build-performance.md` の方が中身に合うが、そうすると Rust 以外からも
  指されうる置き場になる
- **ホスト OS 側 (Spotlight / Gatekeeper) の置き場と到達性。** references へ置けば常時層 0B で
  済むが、到達契機が「Cargo.toml か .cargo/config.toml を Read したとき」に限られる。
  「ローカルのビルドが遅い」と感じた瞬間に Cargo.toml を開くとは限らないので、到達できない委譲に
  なる恐れがある。`references/host-environment.md` へ節を足す案は CLAUDE.md のカテゴリ見出しの
  射程を広げることになり `BUDGET_RAISES` が要る
- **`paths` の形。** `.cargo/config.toml` は `EXPECTED_PATHS` の既存パターンで唯一の非 `**/` 形に
  なる。`**/.cargo/config.toml` へ寄せるか、非 prefix 形が実マッチャで発火するかを live probe で
  測るか
- **`rust-practices.md` の `paths` を広げるか** (推奨: 今回は広げない)。広げるなら唯一の候補は
  `**/rust-toolchain*` だが、管理下のリポジトリでの限界カバレッジを測っていない (dotfiles には
  無い)。測るには dotfiles の外を走査する必要がある
- **第三者 org の内部データの扱い。** 委譲元は PUBLIC でない org のリポジトリで、dotfiles は
  PUBLIC。現行の指示層にはプロジェクト名が 1 件も無い。内部識別子・PR 番号・commit・パッケージ数・
  課金分・ヒット率をどこまで落とすか。メモリ no-private-project-data-in-repo は「PRIVATE リポ名
  そのものは前例あり、線が引かれているのはタスク内容の側」と記録しているが、指示層に限れば前例は 0 件
- **`references/observation.md` を伸ばし続けることの是非。** RUST-09 / RUST-10 を足すと予算には
  当たらないが、同ファイルは既に大きい。読まれる単位が大きくなることを許すか
- **ISSUE-48 との順序。** BP-01 は ISSUE-48 の軸A、BP-02 のプローブの節は軸C に対応する。
  ISSUE-48 の再構成を先に通すと Cargo 側の草案から一般形を落とせるが、着手が先送りになる。
  並行させると同じ規範を 2 箇所で書き直すことになる
- **references を 1 枚増やすことの是非。** ISSUE-48 の「採らない案」は references 全面移設の
  収支が合わないと結論している。あれは常時層からの移設の話で新規追加とは前提が違うが、新設が
  4,500B 規模になると同じ論点に当たる
- **委譲元への返信の粒度。** 材料に書かれた件数と実測が既に食い違っている (pin が 12 本と
  書かれていたが実測 41 件)。件数の訂正まで伝えるか、述語の採否だけ伝えるか

## 関連

- ISSUE-88 — 検査機構の作り方の知見。常時層の予算を共有するので配分をまとめて決める
- ISSUE-48 — 観測カテゴリの主語を観測へ引き上げ未被覆の軸を塞ぐ。BP-01 と BP-02 が軸A / 軸C に
  対応する。着手順は上の未決
- ISSUE-46 — 両リポジトリの Issue をマイルストーンへ整理し着手順を決める。所属の canonical は
  あちらの表
- 2 つの委譲元の原文と検証結果 (反証・配置提案・予算影響) は `.cache/` 配下に残してある (追跡外)
