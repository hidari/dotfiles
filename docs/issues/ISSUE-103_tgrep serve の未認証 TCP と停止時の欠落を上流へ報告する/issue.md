---
status: open
---

# docs: tgrep serve の未認証 TCP と停止時の欠落を上流へ報告する

## 背景

ISSUE-102 (tgrep serve の起動と停止をセッションの寿命へ合わせる作業) の設計段階と実装段階で、
上流 (`https://github.com/microsoft/tgrep`) への報告に値する実測が 3 件出た。dotfiles 側は
これらを踏まえた運用上の判断 (`--no-ignore` を渡さない、停止シグナルに SIGINT を使うなど) を
ISSUE-102 の spec に残しており、ここでは上流への報告という別の作業だけを切り出す。

切り分けの形は ISSUE-62 と同じにする。実測は元の Issue (ISSUE-102) が持ち続け、この Issue は
報告の工程 (報告時点の版の確認と、上流の反応の書き戻し) だけをタスクに持つ。

インストール済みのバージョンは Homebrew の `tgrep` 1.0.8 (`brew info tgrep` の homepage から
上流を確認した)。

### 報告する 3 件

1. **serve が公開する TCP に認証が無い。** `search` / `status` / `files` / `reload` の 4 メソッド
   が未認証で応答し、`search` は一致した行の内容をそのまま返す。HTTP のリクエスト行とヘッダを
   読み捨てて body 行の JSON-RPC だけを実行するため、ブラウザからの到達も起こりうる。待ち受けは
   `127.0.0.1` の IPv4 のみ。詳細は ISSUE-102 の spec (追加実測「serve が公開する TCP には認証が
   無い」節) が持つ。
2. **graceful な停止経路が SIGINT だけで、SIGTERM は SIGKILL と同じ残り方をする。** SIGTERM は
   graceful handler を通らず、`serve.json` が古い pid と port のまま残る。詳細は同じ spec の
   「停止はシグナルだけで、SIGINT が唯一の graceful 経路」節が持つ。
3. **SIGINT による graceful 停止でも、常駐が蓄積した索引の変更は保存されない。** 常駐が直前まで
   返していた語が、停止後の索引直読みでは 0 件になる。`tgrep serve --help` は `--auto-save-mutations`
   を「unsaved work if the process is killed」への備えとして説明しており、この書き方は graceful な
   shutdown を含意しない読み方ができる。実測の詳細は `home/.claude/references/observation.md` の
   tgrep 節が持つ (この Issue では数値を再掲しない)。

## タスク

- [ ] 報告先と作法を確認する (`https://github.com/microsoft/tgrep` の Issues か、別の窓口か)
- [ ] 報告に載せる最小の再現手順を作る。上の 3 件は dotfiles の運用 (ラッパーや hook) を通した
      実測なので、tgrep 単体で再現する形に直す
- [ ] 報告時点の tgrep のバージョンを確認する。上の実測は 1.0.8 で取ったが、報告までに上流が
      進んでいれば測り直す
- [ ] 報告する。3 件それぞれを独立した指摘として書く
- [ ] 上流の反応をこの Issue へ書き戻す。修正が入れば、ISSUE-102 側がこれらの挙動を前提にした
      運用判断を見直す契機になる

## 関連

- ISSUE-102: 実測の一次資料。spec の「追加実測」節と「上流への報告」節がこの Issue の材料を持つ
- ISSUE-62: 同じ形 (実測は元の Issue が持ち、報告の工程だけを独立させる) の先例
