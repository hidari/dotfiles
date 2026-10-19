---
status: open
---

# fix(hooks): apm-install-guard の起動失敗の扱いを決め、fd 番号をサブコマンドと読む誤検知を直す

## 背景

2026-10-19の棚卸しで、PreToolUse の `apm-install-guard.py` について2つ見つかった。

### 起動に失敗したときに素通りする

スクリプトは解釈できない入力を deny へ倒すが、スクリプト自体が起動できないとき (ファイルが無い、python3 が落ちる、タイムアウト、出力が JSON でない) は、hook の既定の `onFailure: continue` で Bash の呼び出しがそのまま通る。`home/.claude/settings.json` のこの hook は `onFailure` を持たない。インストール済みの 2.1.303 のバイナリは `continue` と `block` の2値を持つ。

`block` にすると、hook が直るまで Bash の呼び出しがすべて止まる。一方で、dirty な木での `apm install` は exec 時の shim (`scripts/apm-guard/`、ISSUE-55 で判定点を移した) も止めるので、hook が起動できなくても shim が PATH にあれば防御は残る。shim が PATH に居ないことは guard-health のプローブが告げる (ISSUE-59)。この hook が最後の1層ではないことを踏まえて決める。

### fd 番号をサブコマンドと読む

作業ツリーが dirty なとき、読むだけのコマンドが deny される。hook に JSON を直接渡して再現した。

| コマンド | 判定 |
| --- | --- |
| `apm --version` | 通る |
| `apm list` | 通る |
| `apm --version 2>/dev/null` | deny (「apm 2 は deploy 先を上書きし」) |
| `apm --version 2>&1` | deny |

リダイレクトの fd 番号 `2` を、`apm` に続く語として読んでいる。演算子を切る分割では `2>` が `2` と `>` に分かれ、`2` が普通の語として残るためと見ている (未確認)。deny に倒れる向きなので安全側ではあるが、作業中はツリーが dirty なことが多く、その間 apm の読み取りに出力の抑止を付けられない。

## タスク

- [ ] fd 番号の誤読の原因をコードで確かめ、直す。`2>` `2>&1` `>` `<` などのリダイレクトを表で pin し、`apm install 2>&1` が引き続き deny されることも対照に入れる
- [ ] `onFailure: block` を付けるかを決める (Hidari の判断)。付けるなら config-guard の必須フック検査で pin し、hook 登録の変更は headless の別プロセスで確かめる

## 関連

- ISSUE-55: apm ガードの判定点を exec 時の shim へ移した。コマンド位置の判定の前例
- ISSUE-59: 検査層が沈黙している状態をセッション頭で告げる層。shim の位置を見る
- 26: フックの共通基盤
