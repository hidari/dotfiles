---
status: open
---

# fix: jev-lint の review が非 ASCII のパスを引用付きのまま ast-grep へ渡し黙って落とす

## 背景

別リポジトリで jev-lint-curated の `review --dry-run --base <ref>` を回したとき (2026-10-02)、日本語を含むパスの変更ファイルについて stderr に次の形の行が出た。rc は 0 だった。

```
ast-grep: ERROR: "b/docs/<日本語を含むパス>.md": No such file or directory (os error 2)
```

git が `core.quotePath` の既定 (true) で出す C 形式の引用 (二重引用符と 8 進のエスケープ) と、diff の `b/` 接頭辞が付いたままのパスが ast-grep に渡っている。

### 原因 (コードを読んで確認)

上流の jev-lint 0.7.0 の `dist/diff.js` にある。ラッパ (jev-lint-curated の `scripts/*.py`) は review の対象ファイルを作っておらず、関与しない。

- `changedRanges` (85〜95 行目) は `git diff --unified=0 --no-color --no-ext-diff --diff-filter=d --src-prefix=a/ --dst-prefix=b/ <base>...HEAD` を呼ぶ。`-c core.quotePath=false` も `-z` も付けていない
- `parseUnifiedDiff` (26〜31 行目) は `+++` 行から `line.slice(4).trim()` でパスを取り、`/^[abciw]\//` で接頭辞を外す。非 ASCII のパスでは行が `+++ "b/\346\227\245...py"` になり、先頭の `"` のせいで接頭辞の正規表現が一致しない。引用と 8 進のエスケープと `b/` が残ったまま次へ進む
- そのパスが `dist/cli/targets.js` (14、19 行目) を経て、`dist/scan.js` (375〜379 行目) から ast-grep に渡る。ast-grep はファイルが無いと stderr に出すが rc 0 で終わり、`dist/cli/cmd-check.js` (41〜42 行目) はそれをログに出すだけ
- 同じキャッシュにある 0.6.1 も `parseUnifiedDiff` が同一なので、0.7.0 での退行ではない

### 再現 (使い捨てのリポジトリで実測)

1 つのコミットで `ascii.py` と `日本語.py` (中身は同じ Python の関数 2 つ) を足し、`review --dry-run --base HEAD~1` を回した。

- `ascii.py` と `日本語.py`、既定の設定: rc 0、subject 2 件。`ascii.py` だけが対象になり、`日本語.py` は上の ERROR 行を出して落ちた
- 対照の `ascii.py` と `nihongo.py` (ASCII 名、同じ中身): rc 0、subject 4 件
- `core.quotePath=false` を書いた `.gitconfig` を持つ `HOME` で回すと、`ascii.py` と `日本語.py` で subject 4 件になった

非 ASCII 名のコードファイルは、rc 0 のまま検査から黙って外れる。stderr を読まない限り気づけない。

### 同じ形の箇所 (読んだだけで再現はしていない)

- `dist/diff.js` 104 行目の `git ls-files --others --exclude-standard` (`--base` も `--staged` も無いときの未追跡ファイル) も `-z` を使わず、同じ引用を受ける
- `dist/commits.js` 73、288、306 行目の `--name-only` も同様。ここはプロンプトの本文に入るだけで、ast-grep には渡らない

## タスク

- [ ] どこで直すかを決める
  - 上流 (jev-lint) で直すなら、`parseUnifiedDiff` が C 形式の引用を戻す (前後の `"` を外し、`\ooo` を UTF-8 のバイト列として、`\"` `\\` `\t` `\n` も戻してから接頭辞を外す) のが本筋。`changedRanges` に `-c core.quotePath=false` を付けるだけなら非 ASCII 名は直るが、`"` や `\` や制御文字を含むパスは git が引き続き引用する (未検証)
  - あわせて、diff から来たパスを ast-grep が見つけられなかったときは、ログだけでなく失敗として扱う
  - ラッパ (agentic-coding-tools の jev-lint-curated) で今すぐ塞ぐなら、`jevlint_host.py` の `_FIXED_GIT_SAFETY_ENV` に `GIT_CONFIG_COUNT=1` / `GIT_CONFIG_KEY_0=core.quotePath` / `GIT_CONFIG_VALUE_0=false` を足す。上の `.gitconfig` の実測と同じ仕組みだが、環境変数の経路そのものはまだ回していない。限界は `-c core.quotePath=false` と同じ
- [ ] 直したら、上の再現 (日本語名と ASCII 名の対照) で subject の件数が揃うことを確かめる

## 関連

- jev-lint-curated の canonical は agentic-coding-tools にある
