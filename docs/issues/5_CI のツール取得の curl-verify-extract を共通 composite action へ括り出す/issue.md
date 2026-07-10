---
status: open
---

# CI のツール取得の curl-verify-extract を共通 composite action へ括り出す

## 背景

CI がツールをリリースアーカイブから取得する手順が 3 箇所に手書きで重複している。

- `.github/actions/setup-ast-grep/action.yml`
- `.github/actions/setup-neovim/action.yml`
- `.github/workflows/test.yml` の gitleaks 導入ステップ

いずれも同じ流れ (バージョンを変数へ pin / curl でアーカイブをファイルへ取得 /
固定 sha256 を `sha256sum -c -` で検証 / 展開して PATH へ追加) を独立に書いている。
検証手順を変えるとき 3 ファイルを手で揃える必要があり drift のリスクがある。

url / sha256 / 展開方法を入力に取る共通 composite action (例: `verify-and-extract`) へ
括り出す候補。ただし展開方法が unzip + chmod (ast-grep) と tar (neovim / gitleaks) で異なるため、
入力で分岐するか展開だけ呼び出し側に残すかの設計判断が要る。単純な一行化ではない。

improve/nvim-contrast-palette の pre-merge quality gate で simplify の reuse / simplification 軸が
指摘した。ブランチのスコープを超える pre-existing 問題のため別タスクとして起票する。

## タスク

- [ ] 3 箇所の共通部分と差分 (展開方法 / PATH 追加先) を洗い出す
- [ ] `verify-and-extract` 相当の composite action を設計する (url / sha256 / 展開方法を入力に取る)
- [ ] 3 箇所を新 action の呼び出しへ置き換える
- [ ] CI が緑であることを確認する

## 関連

pre-merge quality gate (simplify reuse / simplification 軸) の指摘。
sha256 検証の導入自体は improve/nvim-contrast-palette で完了済み (setup-ast-grep 新設 + gitleaks への追加)。
