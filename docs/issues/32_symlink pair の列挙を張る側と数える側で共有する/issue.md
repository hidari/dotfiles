---
status: open
---

# refactor: symlink pair の列挙を張る側と数える側で共有する

## 背景

Issue #25 Phase 3b のマージ前ゲートで、独立した 3 つのレビューが同じ構造を指摘した。

`bootstrap.sh` の symlink pair は 3 経路から供給される。配列 2 つ (`SYMLINK_PAIRS` /
`APM_SYMLINK_PAIRS`) と、追加の設定ディレクトリ向けに導出される生成 2 つ
(`claude_mirror_pairs` / `claude_home_symlink_pairs`) である。この合併を、張る側
(`setup_dotfiles` / `setup_apm_symlinks`) と数える側 (`current_symlink_targets`) が
それぞれ独立に列挙しており、両者の一致を pin するものが無い。

壊れ方が破壊的なのが問題である。供給カテゴリを 1 つ足して張る側だけを更新すると、
新カテゴリの target は集合に無いのに親ディレクトリは既存 target と共有されて走査
対象に入る。`main` は `setup_dotfiles` の直後に `prune_stale_symlinks` を呼ぶので、
同じ bootstrap 実行の中で張った直後のリンクが「リンク先が `$DOTFILES_DIR` 配下 かつ
集合に無い」を満たして backup へ退避される。exit 0 で完走し、ログに Linked と
Backed up が並ぶだけで終状態が壊れる。

Phase 3b 自身が「配列 2 + 生成 0」から「配列 2 + 生成 2」へカテゴリを増やした実績が
あるので、これは仮想の心配ではない。

あわせて、`claude_extra_config_dirs` が 1 回の bootstrap 実行で 5 回呼ばれるため、
却下行 1 行につき同じ警告が 5 回並ぶ。「却下行を verbatim で知らせる」設計意図が
ノイズに沈む。この 5 回はフルモードの値で、`--dotfiles-only` では
`setup_apm_symlinks` を通らないぶん 4 回になる。単純なメモ化では解けない: 呼び出しがプロセス置換なのでサブシェル内の
グローバル代入が親へ戻らず、成立させるには `main` での明示初期化と直接呼び出し用の
フォールバックが要る。呼び出し箇所そのものを減らす本 Issue の集約と合わせて解くのが
筋なのでここに含める。

## タスク

- [x] 列挙を 1 箇所へ寄せる方式を決める (単一の生成器へ集約する / 「張った target ⊆
      数えた target」を dry-run 出力から突き合わせるテストで塞ぐ / 両方)
      両方を採った。片方だけでは残る穴がそれぞれ別なので重ねる。生成器だけでは
      呼び出し側が生成器を通さず配列を直読みする経路を塞げず、テストだけでは
      カテゴリ追加時に 2 箇所を直す構造が残る
- [x] 決めた方式で実装し、カテゴリ追加が 1 箇所で済むことを確かめる
      供給カテゴリを引数で選ぶ生成器 `symlink_pairs_for` へ寄せ、張る側と数える側の
      双方をその出力から組む形にした
- [x] 供給カテゴリを 1 つ足す変異で、片側だけ更新した状態が赤くなることを確認する
      `main: every target it links is inside the counted target set` が pin する
- [x] 却下行の警告が 1 回になることを確認する (集約で呼び出し回数が減らない場合は
      明示初期化の是非をここで判断する)
      集約後も読み取り経路は複数残るため、警告を `warn_invalid_claude_config_dir_lines`
      へ分離して `main` が 1 回だけ呼ぶ形にし、読み取り側は黙ってフィルタする設計にした。
      `main: reports a rejected config dir line exactly once` が pin する。
      隔離ホームでの実測でも、却下行 1 行に対する警告はフルモード /
      `--dotfiles-only` とも 1 回で、却下行を持たない対照は 0 回だった

## 関連

- [Issue #25: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する](../closed/25_skill%20と%20plugin%20を新規%20PUBLIC%20リポジトリへ集約し%20apm%20配布へ移行する/issue.md)
  この構造を持ち込んだ Phase 3b の Issue。マージ前ゲートが検出したが、重要な設計判断を
  要するため別タスクとした
- [Issue #33: 設定から外した Claude 設定ディレクトリの symlink が撤去されない](../33_設定から外した%20Claude%20設定ディレクトリの%20symlink%20が撤去されない/issue.md)
  同じ `prune_stale_symlinks` の別の盲点。あちらは削除イベントを見られないという走査
  範囲の話で、こちらは集合の作り方の話
