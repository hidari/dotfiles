---
status: open
---

# refactor: settings.json の live 専用パスを変数化して skip-worktree を解消する

## 背景

`home/.claude/settings.json` は skip-worktree が立っており、コミット済みの内容と live の
内容が異なる。live にはホーム配下の絶対パスが含まれ、gitleaks の `macos-user-path` ルールが
コミットを止めるため、この二重管理が必要になっている。

二重管理の代償は CI が捕捉できない drift。live 側だけに存在する設定（hook や marketplace）は
新しいマシンへ配布されず、bootstrap を回しても再現しない。実際 herdr の hook は live に
しか無く、他マシンでは静かに欠落する。

Issue #7（2 アカウント運用）の作業中に、この二重管理を無くせないか調べた。残っている
絶対パスはちょうど 2 箇所で、片方は確実に直せることが分かっている。

## 調査で分かっていること

### 1. herdr hook の command は変数化できる

```
"command": "bash '<ホーム配下の絶対パス>/.claude/hooks/herdr-agent-state.sh' session"
```

これはシェルコマンド文字列なので `$HOME` を書ける。同じファイルの兄弟 hook が既に
`python3 "$HOME/.claude/hooks/tirith-check.py"` と書いて動いている。この 1 行だけ書き方が
揃っていない。

しかもコミット済み版にはこの hook 自体が存在しない。パスを直せばコミット可能になり、
他マシンへも配布される。

### 2. marketplace の directory source の path は未確定

```
"extraKnownMarketplaces": { "<name>": { "source": { "source": "directory", "path": "<絶対パス>" } } }
```

`claude plugin marketplace add '~/...'` は成功するが、settings.json と
known_marketplaces.json の両方へ絶対パスに正規化して書き込む。つまり CLI は書き込み時に
チルダを展開する。

読み込み側が手書きのチルダや `$HOME` を展開するかは別問題で、そこが未確定。判別に使おうと
した `claude plugin marketplace list` と `claude plugin list` はどちらも settings.json を
同期しないため、チルダ版と絶対パス版の対照実験で差が出なかった（両方とも
「No marketplaces configured」）。対照を取らずにチルダ版だけを見ていたら「チルダは効かない」と
誤結論するところだった。

決着には対話セッションの起動が要る。同期は起動時に走るため。

## タスク

- [ ] marketplace の path でチルダまたは `$HOME` が展開されるかを対話セッションの起動で確かめる
  - [ ] スクラッチの `CLAUDE_CONFIG_DIR` を用意し、手書きの settings.json で起動して
        `plugins/known_marketplaces.json` に解決結果が落ちるかを見る
  - [ ] 絶対パス版を対照として同じ手順を踏み、検査に判別力があることを先に確かめる
- [ ] 展開される場合
  - [ ] herdr hook と marketplace path の両方を変数化する
  - [ ] skip-worktree を外し、live と committed を 1 本にする
  - [ ] gitleaks が通ることを確認する
  - [ ] 二重管理が復活していないことを検出するテストを追加する
- [ ] 展開されない場合
  - [ ] herdr hook だけ変数化してコミット済み版へ取り込む（他マシンへの配布漏れは解消できる）
  - [ ] marketplace を settings.json で宣言しない運用（`plugin marketplace add` を bootstrap
        から実行する等）が成立するかを検討する
  - [ ] どちらも成立しない場合は skip-worktree を維持し、理由を記録して本 Issue を閉じる

## 関連

- [Issue #7: feat: Claude Code の 2 アカウント運用で設定を共有する](../closed/7_Claude%20Code%20の%202%20アカウント運用で設定を共有する/issue.md)
  上記 Issue の作業中に判明した内容をこちらへ切り出した
- [Issue #2: docs: settings.json の live・committed 二重管理を文書化し curation を機械化](../closed/2_settings.json%20の%20live・committed%20二重管理を文書化し%20curation%20を機械化/issue.md)
  補完関係にある。#2 は二重管理を前提として契約を文書化し curation を機械化した。
  本 Issue はその前提自体を外せるかを問う。二重管理が解消できれば #2 が用意した
  curation 機構の役割も変わるため、config-guard の期待値を合わせて見直す必要がある。
