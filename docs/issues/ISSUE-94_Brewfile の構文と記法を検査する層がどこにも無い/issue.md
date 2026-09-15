---
status: open
---

# fix: Brewfile の構文と記法を検査する層がどこにも無い

## 背景

`home/.Brewfile` へシェルのコマンド形式の 3 行が追記され、Brewfile が構文エラーになった。
`brew bundle check` は exit 1 で `unexpected local variable or method` を返す状態で、
2026-09-16 に PR #220 で直すまで残っていた。

```
brew install mitmproxy
brew install wireshark
brew install --cask wireshark-chmodbpf
```

### この壊れはコミットを 1 度も通っていない

**壊れた 3 行はどの ref のどのコミットにも存在しない。**全 ref に対する `git log -S` のヒットは
この Issue 自身の文書だけで、`home/.Brewfile` の全履歴版に `^brew install` は 0 件である。
加えて 2026-09-13 から 2026-09-16 のあいだコミットが 1 本も無い。

つまり壊れは**未 stage の作業ツリーにだけ**存在していた。dotfiles は作業ツリーが live 設定の
実体 (`~/.Brewfile` がここを指す symlink) なので、追跡下へ入らないまま実環境で有効になる。

**この事実は「pre-commit へ配線する」という素朴な手当てを否定する。**`files:` で絞る hook は
stage されないので発火せず、`always_run` の hook もコミットが無いので走らない。コミット時
ゲートは、この窓を 1 秒も縮めない。

### 読んでいる層はあるが、検証していない

「どの層も Brewfile を見ていない」わけではない。`config_guard.tool_provisioning` の
`provided_commands()` は `home/.Brewfile` を**インデックスではなく作業ツリーから**読んでおり、
これを回す `config-guard-scan` hook は `always_run: true` である。

**読んでいるのに緑になるのは、その層が抽出器であって検証器ではないため。**壊れた行は
`BREW_ENTRY` の正規表現に一致しないので、供給側の集合から無音で落ちるだけで findings にならない。
隔離ルートで壊れた Brewfile を置いて `check_tool_provisioning()` を直接叩くと findings 0 件で、
`provided_commands` の要素数が静かに減る。

CI にも Brewfile を対象にする job は無い (`.github/` 全体で `Brewfile` は 0 件)。

壊れ方は 2 種類ある。**構文エラーで `brew bundle` が落ちる形**と、**構文は通るが種別が違う形**。
後者は `mitmproxy` が formula ではなく cask であることにあたる。CLI の `brew install` は
formula が無ければ cask を自動で探すので打った側は通るが、Brewfile の DSL は `brew` と `cask` を
区別する。シェルで打ったコマンドをそのまま貼ると、名前は正しいのに種別だけ壊れる。

## 検査の候補と、それぞれが届かない範囲

案が 3 つあり、覆う範囲がそれぞれ違う。

`brew bundle check` は正確だが外部 CLI とネットワークに依存する。これは
`config_guard.tool_provisioning` が Brewfile を行で読む判断と同じ理由で CI から外れる。加えて
exit code が「構文が壊れている」と「宣言どおりの版になっていない」を区別しない。実際、正しい
Brewfile でも exit 1 になる (2026-09-16 時点で 12 件。全て導入済みで outdated なものだが、
`needs to be installed or updated` という文面のとおり未導入も同じ側へ落ちる)。

**`ruby -c` は今回の壊れを実際に捕捉する。**3 行目の `brew install --cask wireshark-chmodbpf` で
`syntax error, unexpected tIDENTIFIER` を出して exit 1 になり、しかも `brew bundle check` が
報告するのと同じ行を指す。`--cask` が単項マイナス 2 つに解釈され、直後の識別子を続けられない
ためである。

ただし 1 行目と 2 行目は**通す**。`brew install mitmproxy` は Ruby として valid なメソッド
呼び出しで、壊れるのは評価時になる。つまり構文検査が捕まえるのは「オプション形式を含む行」
だけで、`brew install <name>` の形と種別の取り違えはすり抜ける。

`config_guard.tool_provisioning` の `BREW_ENTRY` は「供給側に数える行」を拾う正規表現で、
一致しない行を報告する形にはなっていない。一致しない行には `tap` と `go` とコメントと空行が
含まれるので、そのまま「違反」にはできない。

3 案の覆う範囲は次のとおり。

| 案 | `--cask` を含む行 | `brew install <name>` | 種別の取り違え | 外部依存 |
| --- | --- | --- | --- | --- |
| `brew bundle check` | 捕まえる | 捕まえる | 捕まえる | CLI + ネットワーク |
| `ruby -c` | 捕まえる | 素通し | 素通し | ruby のみ |
| 行の allowlist | 捕まえる | 捕まえる | 素通し | 無し |

種別の取り違えを捕まえたいなら `brew info` が要る。ただし ISSUE-95 が扱う「宣言と実機の
突き合わせ」は、`brew leaves` と `brew list --cask` の 2 回で同じ検出を副産物として得る
(`brew "mitmproxy"` と書けば「宣言 formula にあるが実機 formula に無い」と「実機 cask にあるが
宣言 cask に無い」の両方へ出る)。**この 2 つの Issue は独立に見えて、種別の検証だけは共有できる。**

## 決めること

- 許される行の形をどこに置くか。`BREW_ENTRY` と重複させると、同じ制約が 2 箇所へ散って drift する
- 種別 (formula / cask) の検証を射程に入れるか。入れるなら `brew info` が要り、外部 CLI への
  依存が戻ってくる
- CI ミラーを張るか。Brewfile の編集はローカルでしか起きないので、`issue-scoped-artifacts` や
  `issue-ref-notation` と同じく pre-commit 専用にする選択肢がある

## タスク

- [ ] 上の 3 点を決める。特に「許される行の形」の canonical をどこへ置くか
- [ ] **検出経路を決める。**commit 時ゲートは未 stage の作業ツリーを見ないので、実際に起きた
      窓には届かない。pre-commit だけを配線して「塞いだ」と結論しないこと。SessionStart の
      probe や、作業ツリーを直接見る経路を射程に入れるかを含めて決める
- [ ] 決めた経路へ検査を実装して配線する
- [ ] 変異注入で確かめる。検査対象を壊す / 検査機構そのものを壊す / 取り付けを外す の 3 種を
      それぞれ隔離して入れ、どれも赤くなることを見る
- [ ] 機構が覆う範囲を数える。行の形の allowlist は「形が合っているか」しか見ないので、
      種別の取り違えや存在しないパッケージ名が範囲外に残る。範囲外に残るものを明記する

## 関連

- Issue 45: 同じ「検査していないのに緑」の形。あちらは bats job が導入しないコマンドのテストが
  全 skip する件で、機構は別だが判定の誤り方は同型
- Issue 27: 同じく 0 件実行が緑になる形。Pester のラッパが持つ件数ガード
- ISSUE-86: pre-commit を残りのリポジトリへ展開する。取り付け先の話でこの Issue とは別だが、
  Brewfile を持つのは dotfiles だけなので射程は重ならない
- ISSUE-95: Brewfile の射程そのものを決める Issue。こちらが「書かれている内容が壊れていないか」を
  見るのに対し、あちらは「何を書くべきか」を決める。片方が他方を不要にしないが、**種別の検証
  だけは共有できる** (上の表の最終段落)。着手順はどちらが先でもよく、先に着手した側が
  `brew leaves` / `brew list --cask` の突き合わせを持つ
