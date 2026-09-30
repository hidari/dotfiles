# Rust のビルドコストの一次実測

`~/.claude/rules/cargo-build-practices.md` と `~/.claude/rules/rust-practices.md` のビルドコストの見出しが持つ規範の、手当ての詳細と一次実測。
親が CLAUDE.md のカテゴリではなく rules なので、到達するのは `Cargo.toml` か `.cargo/config.toml` か `.rs` を Read したときだけになる。

規範の遵守そのものには要らない。手当ての具体が要るとき、規範を疑うとき、似た失敗を踏んで「これは既知か」を確かめるときに読む。

数値は別のリポジトリでの一次実測を桁に丸めたもので、ここで効く量の見積もりには使わない (下の「削減率を持ち込まない」節)。

## コンパイルキャッシュと incremental の取引

sccache は incremental でコンパイルされる crate をキャッシュしない。Cargo の dev 既定では workspace member と path 依存が incremental になるので、常に cold な CI では incremental を捨てて採り、反復編集が主なローカルでは採らない。

効いたかは機構自身のヒット統計で見る。ヒット率0%でもビルドは緑になり、wall は他の要因で動く。統計をログへ出す工程は機構と同じ変更で入れる。後から足すと、効いていなかった期間が観測できなくなる。

リンク・テスト実行・依存のインストール・toolchain の setup はキャッシュの対象外なので床が残る。ヒット率を0%から8割台まで上げても CI の wall は4分の1ほどしか縮まず、残りは MSVC のリンク (sccache の対象外) と setup とテストが占めていた。別の OS ではヒット率100%に達しており、「100%」は「もうキャッシュでは縮まない」の意味であって「速い」の意味ではない。

## 削減率を持ち込まない

効き幅は並列度・依存構成・OS ごとの既定 (debuginfo の分割方式など) で変わる。同じ手が別のリポジトリで効いたことは、ここで効くことの証拠にならない。

同じ対象 (同じ profile、同じ job の env) を触る施策を1つの変更にまとめない。効果の帰属が判別できなくなる。

## ホスト OS 由来の遅さ

「ローカルは CI の数倍遅い」という前提が実測で否定された。30分を超えていたテストの工程が2分台になり、同じ日の CI のゲートよりローカルのほうが速かった。

真因は2つともホスト OS 側にあった。

- Spotlight の索引。`~/Develop` をプライバシーの除外へ入れると、索引に載る `.rcgu.o` が10万件台から0件になった。`target/.metadata_never_index` は効かなかった
- Gatekeeper の検証。`syspolicyd` の CPU 使用率が1コアの数十%から1〜2%へ落ちた

TCC の権限はプロセスの起動時に決まるので、除外を入れた後に起動した系列でないと効かない。デーモンはセッションをまたいで生き残る。

対照にドットで始まるディレクトリを使わないこと。Spotlight はそもそも索引しないので対照にならない。

`target/` の `.o` が100万件規模に溜まっていても、それは数か月ぶん・複数の feature 構成の累積で、1回のビルドが作るのは1万件未満だった。残骸自体はビルドを遅くしていなかった。

## profile の射程

素の `[profile.<name>]` が依存グラフ全体へ降りることを、走行中の `ps` から rustc の実引数を採取して確かめた。変更前は自作も依存も `-C debuginfo=2`、変更後は自作が `-C debuginfo=line-tables-only`、依存が `-C strip=debuginfo` になった。

release の `codegen-units = 1` も、足場のコミットで実測も理由も無く置かれたまま、数百ある依存パッケージの全部に降りていた。proc macro と build script だけが `build-override` の既定へ落ちて無傷だった。

dev profile の3軸 (workspace は line-tables-only、依存と build script は debug を落とす) の効果は、`target/debug/deps` が4割強、target 全体が4割弱、user CPU が3割ほど減った。real は2割ほど縮んだが参考値に留める。

- 測定条件は arm64 の macOS 実機で、`cargo clean` 後のクリーンビルドを前後1回ずつ `/usr/bin/time -l` で測った
- 前後で実行されたテストの集合が一致していることを確かめてから比べた。「テストを実行しなくなったから速い」を排除するため
- real は同じ条件でも数倍ぶれた記録がある

`build-override` をフラグの有無で no-op と判定して一度削除し、隔離したプローブの出力バイト数 (1割弱の差) で誤りと分かって戻した。フラグの観測では差が出なかった。

`inherits` の退避先が片肺になる事故を、1つのブランチの中で2回踏んだ。1回目は依存の軸が戻らず、2回目は build script の軸だけが取り残された。

`incremental = true` がプロジェクトの初期から `[profile.dev]` にあり「検討済み」に見え続けていたが、cargo の dev 既定の再掲で何も変えていなかった。

## CI キャッシュ

GitHub Actions の cache は branch scope を持つ。PR ブランチが復元できるのは自ブランチの scope か default branch の scope だけなので、ラベルで起動する (default branch では走らない) ゲートは default branch の scope を持てず、全 PR が構造的に cold になる。

PR ブランチの scope へ数分かけて保存していた GB 級のキャッシュは、マージのたびに蒸発していた。死んだキャッシュを書いて捨てていただけなので、保存を止めた (rust-cache の `save-if: false`)。

一度だけ観測された短い wall は、保存を止める前に同じブランチの scope へ保存されたキャッシュを復元できた1回限りのもので、steady-state ではなかった。
