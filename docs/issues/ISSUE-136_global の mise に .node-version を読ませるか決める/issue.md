---
status: open
---

# feat(mise): global の mise に .node-version を読ませるか決める

## 背景

他のリポジトリのセッションから受け箱経由で届いた提案 (2026-10-22)。報告元は node の版をリポジトリ直下の `.node-version` の1箇所に寄せ、CI は actions/setup-node の `node-version-file` で、手元は mise に同じファイルを読ませる形にした。

- 報告 (実測、mise 2026.9.4): mise は既定で `.node-version` のような idiomatic な版のファイルを読まない。`idiomatic_version_file_enable_tools` の既定は空で、ファイルを置いただけでは global の版のまま黙って動く
- 報告 (実測、mise 2026.9.4): リポジトリの `mise.toml` に `[settings] idiomatic_version_file_enable_tools = ["node"]` だけを書くと、版の literal を2箇所目に増やさずに mise が `.node-version` を読む。`mise trust` のあと、`mise.toml` を外すと global の版を、戻すとファイルの版を `mise current node` が返した
- 報告者の提案 (推測): dotfiles の global の mise 設定でこれを有効にすれば、リポジトリごとに `mise.toml` を置かなくても、`.node-version` を持つリポジトリで CI と手元の版が揃う。副作用として `.node-version` を持つ他のリポジトリでも手元の版が切り替わるが、その影響は確かめていない

これは各リポジトリの pin を外す話ではない。版の canonical はリポジトリの `.node-version` のままで、変わるのは global の mise がそれを読むかどうかだけである。

dotfiles で確かめたこと (2026-10-22):

- この開発機の mise は 2026.9.4 で、`mise settings get idiomatic_version_file_enable_tools` は `[]` を返した。global の設定 (`home/.config/mise/config.toml`) はこの設定を持たない
- 開発用のディレクトリの直下にある27のリポジトリのうち、`.node-version` を持つのは1つだけで、`.tool-versions` と `.nvmrc` は0件だった。その1つは自前の `mise.toml` で既にこの設定を `["node"]` にしていて、`mise current node` は `.node-version` と同じ版を返した。今の時点で global を有効にしても、新しく版が切り替わるリポジトリは0件になる

## 決める前に見ること

- `probe_node_security` (ISSUE-131) は global の `[tools]` にある node の pin だけを security リリースと比べる。`.node-version` で手元の版が切り替わるリポジトリでは、その版が古くてもプローブは告げない。これは global を有効にするかどうかに関わらず、自前の `mise.toml` で有効にしているリポジトリでも既に同じである
- config-guard の tool_provisioning は、検査とテストに要るコマンドが Brewfile か mise の `[tools]` に宣言されているかだけを見て、版は見ない。`.node-version` で版が切り替わってもこの検査の結果は変わらない

## タスク

- [ ] global で有効にするか、`.node-version` を持つリポジトリの `mise.toml` に任せたままにするかを決める
- [ ] `.node-version` で版が切り替わるリポジトリの版を、security リリースと比べる対象に入れるかを決める

## 関連

- ISSUE-131: node の pin が security リリースより古いことをセッション開始時に告げる
- ISSUE-134: actions/setup-node の `node-version-file` と版の範囲についての報告
