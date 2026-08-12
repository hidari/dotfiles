# Issue #32 設計: symlink pair の列挙を張る側と数える側で共有する

## 解く問題

`bootstrap.sh` の symlink pair は 4 経路から供給される。配列 2 つ (`SYMLINK_PAIRS` /
`APM_SYMLINK_PAIRS`) と、追加の設定ディレクトリ向けに導出される生成 2 つ
(`claude_mirror_pairs` / `claude_home_symlink_pairs`) である。

この合併を、張る側 (`setup_dotfiles` / `setup_apm_symlinks`) と数える側
(`current_symlink_targets`) がそれぞれ独立に並べ直しており、両者の一致を守るものが無い。

壊れ方が破壊的である。供給カテゴリを 1 つ足して張る側だけを更新すると、新カテゴリの
target は集合に無いのに親ディレクトリは既存 target と共有されて走査対象に入る。`main` は
`setup_dotfiles` の直後に `prune_stale_symlinks` を呼ぶので、同じ bootstrap 実行の中で
張った直後のリンクが「リンク先が `$DOTFILES_DIR` 配下 かつ 集合に無い」を満たして backup へ
退避される。exit 0 で完走し、ログに Linked と Backed up が並ぶだけで終状態が壊れる。

## 現状の把握

読んで確認した事実を先に置く。設計はこの上に立つ。

共有は既に部分的に成立している。mirror の導出は `claude_mirror_pairs` が canonical で、
張る側も数える側も同じ関数を呼ぶ。`claude_home_symlink_pairs` も同様である。共有されて
いないのは「4 経路の合併をどう並べるか」だけである。

張る側は source の解決規則がカテゴリで違う。`setup_dotfiles` と `create_apm_symlink` は
`$DOTFILES_DIR` 起点、`setup_home_symlinks` は `$HOME` 起点で、後者は source が無ければ
自分で作る。`create_apm_symlink` だけが source 存在ガードを持つ。数える側は target しか
見ないのでこの違いに触れない。

順序の制約がある。`setup_dotfiles` は `install_apm_packages` より前かつ `--dotfiles-only`
でも走り、`setup_apm_symlinks` は apm install の後にしか走れない。カテゴリを畳んで
1 回で張ることはできない。

## 設計

### 1. pair の単一生成器

`symlink_pairs_for <category>` を置く。`repo` / `apm` / `home` / `all` を受け、1 行 1 pair で
出力する。pair のフォーマット (`source|target`) は変えない。

- `repo`: `SYMLINK_PAIRS` と、そこから導出した mirror
- `apm`: `APM_SYMLINK_PAIRS` と、そこから導出した mirror
- `home`: `claude_home_symlink_pairs`
- `all`: 上の 3 つを順に出力する

未知のカテゴリは `error` で報告して非 0 を返す (`error` は出力するだけで exit しないので、
呼び出し側が止まれるよう戻り値を返す)。黙って空を返すと、呼び出し側から見て「対象が 0 件」と
区別が付かず、健全に見えてしまう。

カテゴリと供給経路は 1 対 1 ではない。mirror の導出は `repo` と `apm` の両方に分かれて
入る。分け方の基準は source の性質で、`repo` の source は git 管理下で必ず実在し、`apm` の
source は apm install が配置するまで存在しない。張る側がこの違いで分岐するため、カテゴリも
そこへ合わせる。

消費側は 3 箇所になる。

- `setup_dotfiles`: `repo` と `home`
- `setup_apm_symlinks`: `apm`
- `current_symlink_targets`: `all` の target 列

カテゴリを足すときに編集するのは `symlink_pairs_for` の中の隣接する 2 箇所 (case の追加と
`all` への 1 行) だけになる。片方を忘れた状態は下の突き合わせテストが捕る。

`claude_mirror_pairs` と `claude_home_symlink_pairs` は canonical のまま触らない。生成器は
それらを呼ぶだけの薄い層である。

### 2. 判定述語の切り出し

`claude_extra_config_dirs` は現在、行の判定と却下行の警告を 1 つの関数に持つ。呼び出しが
プロセス置換なので、この関数は 1 回の bootstrap 実行で複数回走り、同じ警告が並ぶ。集約後は
呼び出しが 6 回になり悪化する。

メモ化は成立しない。呼び出しが全てプロセス置換 (`< <(f)`) なので、サブシェル内のグローバル
代入は親へ戻らない。実装しても効かないだけで例外は出ないため、静かに失敗する。

判定を `claude_config_dir_line_kind` へ切り出す。戻り値は 0 (有効) / 1 (無視: 空行・
コメント・既定ディレクトリ) / 2 (却下: 文法違反) の 3 状態とする。

- `claude_extra_config_dirs` は述語を使って黙ってフィルタする。何回呼ばれても静かになる
- `warn_invalid_claude_config_dir_lines` が却下行を verbatim で警告する。`main` が
  `setup_dotfiles` より前に 1 回だけ呼ぶ

述語が canonical なので文法が二重管理にならない。文法自体 (`.claude-` 接頭辞と `-dev`
接尾辞の予約) は変えない。`home/.zshrc` との一致を守る parity テストは既にあり、そのまま
生きる。

### 3. 突き合わせテスト

追加の設定ディレクトリを 1 件設定した `TEST_HOME` で `main --dry-run` を走らせ、出力の
`[DRY-RUN] ln -sf <source> <target>` 行から target を抽出して `$HOME` 相対へ戻し、
`current_symlink_targets` の集合に全件含まれることを検証する。

方向は「張った target ⊆ 数えた target」とする。逆向きは成立しない。テスト環境には apm が
配置する source が無いため apm 分は張られず、数える側だけが持つからである。破壊的なのは
「張ったのに数えていない」側だけなので、守る向きはこれで足りる。数える側の過剰は stale を
見逃すだけで、リンクを壊さない。

抽出では件数の一致も確認する。`[DRY-RUN] ln -sf` の行数と抽出できた target の数が合わ
なければ失敗させる。パスに空白が入ったときに一部が静かに落ちる経路を塞ぐためで、落ちた分は
エラーではなく「短い正常な結果」として返るので件数でしか捉えられない。

テストは `scripts/tests/bootstrap.bats` へ置く。`main` の dry-run 出力を検証する統合
テストが既にあり、その規約に合わせる。

### 4. 変異注入

検査機構を足すので 3 種を行う。

1. 検査対象を壊す: `symlink_pairs_for` へ新しいカテゴリを足して `all` には足さず、
   突き合わせテストが赤くなることを確認する
2. 検査機構を壊す: 突き合わせの assertion を無効化し、他のテストが緑のまま通ることを
   確認する。この機構が唯一の防御であることの確認になる
3. 取り付けを外す: テストから `main --dry-run` の実行を外し、テストが空回りで緑にならない
   ことを確認する

加えて範囲を数える。この機構が覆うのは「`main --dry-run` が通る経路で張られる target」で
あり、dry-run で分岐して張られない経路 (apm source 不在時の skip) は範囲外である。何が
範囲外かをテストのコメントに書く。

変異は 1 度に 1 箇所ずつ入れる。同時に入れると片方がもう片方の効果を隠して緑のままになり、
生きた pin を dead pin と誤読する。

## 検証

- `bats scripts/tests/` の TAP プランと `ok` 件数の一致
- `pre-commit run --all-files` の Passed / Failed 件数
- `bootstrap.sh --dry-run` を実 shell で 1 回通し、Linked と Backed up の並びが出ないこと
- 変異注入 3 種それぞれで期待どおり赤くなる (または緑のまま) ことの確認

## スコープ外

- Issue #33 (設定から外した設定ディレクトリの symlink が撤去されない) の走査範囲拡張。
  同じ関数群を触るが、あちらは破壊的機構の挙動変更で検証量が大きく違う
- pair フォーマットの変更。source の解決規則をデータへ持たせる案は、既存テストの多くが
  pair を直接扱うため影響が大きい割に、本 Issue の壊れ方は生成器だけで塞げる
- `prune_stale_symlinks` の所有判定 (リンク先が `$DOTFILES_DIR` 前置) の見直し
