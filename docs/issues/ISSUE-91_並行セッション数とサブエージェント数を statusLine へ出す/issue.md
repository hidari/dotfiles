---
status: open
---

# feat(statusline): 並行セッション数とサブエージェント数を statusLine へ出す

## 背景

並行して動いている同一アカウントのセッション数と、その配下で走っているエージェント数を、
ユーザーと Claude の両方が把握できるようにしたい。サブエージェントを多く動かすと現在の
監視方法では見逃し、週次リミットが尽きる。

実装先は statusLine 一択。レートリミットの実数値は statusLine の stdin にしか来ない
(メモリ reference-claude-code-rate-limits) ので、逼迫度と並行数を同じ場所に出さないと
判断材料が割れる。持ち場は `home/.claude/statusline-command.sh`。

`ListAgents` はローカルセッションとサブエージェントを列挙できるが Claude 側からしか叩けず、
しかも PID を返さない。ユーザーへ出す経路にはならない。

### 使える信号の実測 (2026-09-12)

どの信号も「エラー」にならず、もっともらしく違う数を返す。

| 信号 | 値 | 判定 |
| --- | --- | --- |
| `/tmp/cc-socks/*.sock` ∩ 生存 PID | 7 | **これが並行セッション数** |
| `ls /tmp/cc-socks/*.sock` (生存チェック無し) | 7 | 死んだセッションのソケットが残骸として残る形がある |
| `ps` の `claude` プロセス数 | 15 | node の補助プロセスを含むので過大 |
| `projects` 配下のディレクトリ数 | 859 | 過去の全セッション。現在数ではない |

**`find` で `projects` を数えると 0 件になる。** 両方の設定ディレクトリの `projects` は
`~/.claude-shared/projects` への symlink で、`find` は既定で symlink を辿らないため。
対照で確かめた結果は `-L` なし 0 件 / `-L` あり 859 件。同型の罠はメモリ
reference-memory-is-per-config-dir が `stat` の `-L` で記録している。

エージェント数の信号は未確定。`projects/*/subagents/` を見る経路が候補だが、上の symlink の
影響で走査が空を返していたため測り直しが要る。

### コストの制約

statusLine はプロンプトのたびに走る。`lsof` や広い `find` を毎回叩くと体感が落ちるので、
数える手段は「ソケットの数を数える」程度に抑えるか、キャッシュを挟む必要がある。
既存のキャッシュ置き場は `${XDG_CACHE_HOME:-$HOME/.cache}/claude/` で、
レートリミットとアカウントメールが既にアカウント別のファイルで入っている。

## タスク

- [ ] 並行セッション数を「ソケット ∩ 生存 PID」で数える実装を statusline へ入れる
- [ ] サブエージェント数の信号を決める。`projects/*/subagents/` を `-L` 付きで測り直して
      現在走っているものだけを切り出せるかを確かめる
- [ ] statusLine の実行コストを測る。毎回叩く経路と、キャッシュを挟む経路を比べる
- [ ] 死んだセッションのソケット残骸が数に入らないことをテストで pin する
- [ ] 表示形式を決める。レートリミットの逼迫度と並べたときに読み取れる形にする

## 未決

- **サブエージェント数をどこまで数えるか。** 自セッション配下だけか、全セッションの合計か。
  トークンが尽きる原因は後者だが、他セッションの配下を数える経路はまだ無い
- **更新頻度。** statusLine はプロンプトのたびに走るので、毎回数えると `lsof` のコストが乗る。
  キャッシュを挟むと表示が遅れる。どちらを取るか
- **表示の優先度。** statusLine の桁は限られている。レートリミット・アカウント・ブランチが既に
  出ている中で、並行数を常時出すか、閾値を超えたときだけ出すか
- **他アカウントのセッションを含めるか。** ソケットは `/tmp/cc-socks/` に全部集まるので
  アカウントを跨いで見える。リミットはアカウント別なので、混ぜると判断を誤る

## 関連

- ISSUE-46 — 両リポジトリの Issue をマイルストーンへ整理し着手順を決める。所属の canonical は
  あちらの表
- ISSUE-83 — セッション頭のプローブが逐次で走り待ち時間の上限が積み上がる。statusLine とは
  別経路だが「セッション頭のコスト」を扱う点で近い
- メモリ reference-claude-code-rate-limits (statusLine の stdin が唯一の取得元)、
  reference-memory-is-per-config-dir (`projects` の symlink と `-L` の罠)
- 調査 probe は `.cache/probe-session-visibility.sh` / `.cache/map-sessions.sh` /
  `.cache/probe-symlink-control.sh` / `.cache/who-burns-cpu.sh` (いずれも追跡外)
