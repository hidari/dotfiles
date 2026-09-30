# Rust のビルドコストの一次実測

`~/.claude/rules/cargo-build-practices.md` の「ビルドの遅さも設定の効果も、観測しやすい量を証拠にしない」カテゴリと、`~/.claude/rules/rust-practices.md` の「ビルドのコストに手を入れる前に律速を測り、入れた後は効いていることを別の量で確かめる」カテゴリが持つ規範の、手当ての詳細と一次実測。

規範の遵守そのものには要らない。手当ての具体が要るとき、規範を疑うとき、似た失敗を踏んで「これは既知か」を確かめるときに読む。

数値は桁の目安で、ここで効く量の見積もりには使わない (下の「削減率を持ち込まない」節)。

## コンパイルキャッシュと incremental の取引

Cargo の dev 既定では workspace member と path 依存が incremental になり、sccache はその crate をキャッシュしない。

ヒット率0%でもビルドは緑になり、wall は他の要因で動く。

リンク・テスト実行・依存のインストール・toolchain の setup はキャッシュの対象外なので床が残る。ヒット率を0%から8割台まで上げても wall が4分の1ほどしか縮まず、残りをリンクと setup とテストが占めた例がある。ヒット率100%は「もうキャッシュでは縮まない」の意味であって「速い」の意味ではない。

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

release の `codegen-units = 1` のような素の設定も、依存が数百あれば数百すべてに降りる。無傷で残るのは `build-override` の既定へ落ちる proc macro と build script だけになる。

dev profile の3軸 (workspace は line-tables-only、依存と build script は debug を落とす) の効果は、`target/debug/deps` が4割強、target 全体が4割弱、user CPU が3割ほど減った。real は2割ほど縮んだが参考値に留める。

- 測定条件は arm64 の macOS 実機で、`cargo clean` 後のクリーンビルドを前後1回ずつ `/usr/bin/time -l` で測った
- 前後で実行されたテストの集合が一致していることを確かめてから比べた。「テストを実行しなくなったから速い」を排除するため
- real は同じ条件でも数倍ぶれた記録がある

`build-override` をフラグの有無で no-op と判定して一度削除し、隔離したプローブの出力バイト数 (1割弱の差) で誤りと分かって戻した。フラグの観測では差が出なかった。

`inherits` の退避先が片肺になる事故を、1つのブランチの中で2回踏んだ。1回目は依存の軸が戻らず、2回目は build script の軸だけが取り残された。

`incremental = true` が `[profile.dev]` にあると「検討済み」に見え続けるが、cargo の dev 既定の再掲で何も変えていない。

## CI キャッシュ

GitHub Actions の run が復元できるのは、自ブランチ・default branch・(pull_request で起動したときは) PR の base branch の scope に限られる。pull_request で起動した run が保存したキャッシュの scope は merge ref (`refs/pull/.../merge`) で、同じ PR の再実行からしか復元できない。

- default branch で一度も走らないジョブは、base が default branch の PR から見て復元できるキャッシュを持てず、構造的に cold になる
- PR の run から数分かけて GB 級のキャッシュを保存しても、マージ後は誰も復元できない。保存を止める (rust-cache なら `save-if`) ほうが時間を返す
- 同じ PR の再実行が保存済みのキャッシュを拾って1回だけ短くなることがあり、steady-state と取り違えやすい
