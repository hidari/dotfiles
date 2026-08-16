---
status: open
parent: 35
---

# refactor: CLAUDE.md を rules と skill へ分割し常時ロード量を減らす

## 背景

`home/.claude/CLAUDE.md` は 1 枚しかないため、どの作業をしていても全文が常時ロードされる。
2026-08-17 時点で 314 行 / 45KB。セクション別の行数は次のとおり。

| セクション | 行数 | 直下項目 |
|---|---|---|
| あらゆる ”検証” 時に守ること | 121 | 26 |
| MUST GLOBAL 必ず守ること | 45 | 19 |
| テストコード | 48 | 8 |
| コミットメッセージ | 32 | - |
| セキュリティ | 16 | - |
| SubAgents、Plugins, Skills の活用 | 16 | 2 |
| 作業プロトコル | 12 | - |
| プロダクションコード | 11 | - |

言語別の内容はほぼ無い。Rust / TypeScript / Swift / Kotlin の出現数はいずれも 0 で、
実際の質量は git (17) / gh (9) / zsh・bash (5) と、言語非依存の検証・テスト方法論に寄っている。

## 実測で確定した機構 (2026-08-16、Claude Code 2.1.233)

バイナリの zod 定義と `HOOK_EVENT_REGISTRY` から直接読んだ。推測ではない。

`InstructionsLoaded` フックが実在する。ペイロードの schema は次のフィールドを持つ
(値の canonical はバイナリ側であり、ここでは再掲せずフィールド名のみ記す)。

- `file_path` / `memory_type` / `load_reason` は必須
- `globs` / `trigger_file_path` / `parent_file_path` は任意
- `matcher` は `load_reason` に対して効く
- observability-only と明記されており blocking は非対応

`~/.claude/rules/*.md` は User スコープで実在し、`paths` frontmatter によるスコープが効く。
プローブを置いて次のレコードを実測した。

    file_path: ~/.claude/rules/probe-user-scoped.md
    memory_type: User
    load_reason: path_glob_match
    globs: ["**/*.rulescope"]
    trigger_file_path: <repo>/.cache/probe.rulescope

副次的に確定したこと。

- フックの登録は settings.json を書いた瞬間に効く。セッション再起動は不要
  (PostToolUse へ同じロガーを仮付けした対照で確認)
- gitignore 対象の `.cache/` 配下のファイルでもトリガーになる

## 踏んだ罠 (運用上の注意)

rules ディレクトリの走査はセッション開始時にキャッシュされる。セッション途中で作った
`~/.claude/rules/` は自分のセッションからは見えず、同じファイルを読んでも発火しなかった。
subagent は毎回新鮮に走査するため、subagent 経由で読ませて初めて発火した。

rules を 1 枚足しても再起動するまで効かない。しかも「効かない」が無言なので、
書いて動かして反応が無いと `paths` の書き方の誤りと誤診する形をしている。
動作確認は subagent を 1 本投げるのが最短。

## 未確認

`paths` を持たない rules が session_start で常時ロードされるかは未測定。ログに出ていないが、
対照である `~/.claude/CLAUDE.md` 自身のレコードも出ていないため、これは subagent が
session_start のメモリロード経路を通っていないことを示している。未観測であって陰性ではない。

セッションを 1 回再起動し `~/.cache/claude/instructions-loaded.jsonl` を読めば確定する。
`CLAUDE.md` が `session_start` で出ていれば対照成立、そこに `probe-user-always.md` が
並んでいれば「paths 無しの rules は常時ロード」が確定する。

## 分割案の下書き

`paths` で絞れるかどうかで性質が分かれる。絞れない側を rules に置いても常時ロード量は減らない
ため、置き場所の判断はこの軸で行う。

スコープできる (触ったときだけロード):

| 移す先 | 内容 | paths |
|---|---|---|
| testing-practices | テストコード 48 行 (変異注入・dead pin・検査機構の 3 種変異) | テストファイル群 |
| frontend-practices | プロダクションコード 11 行 (semantic HTML・a11y・aspect-ratio) | tsx / jsx / html / css |
| shell-practices | 検証セクション内の zsh・bash 展開、exit code、パイプ、サブシェル境界 | sh / zsh / bats |

スコープできない (常時ロードのまま):

| 移す先 | 内容 | 理由 |
|---|---|---|
| verification-practices | 検証セクションの残り | 全作業に効く方法論でファイルに紐づかない |
| git-github-practices | push 後の確認、長時間コマンドの結論、ruleset 判定、コミット prefix | git 操作はファイル編集と無関係に起きる |
| subagent-practices | SubAgents の節 + 検証セクションの subagent 運用項 | 同上 |

skill 側への切り分けの軸を 1 本立てる。rules に置くのは「こう振る舞え」という規範、
skill に置くのは「こういう事実がある」という知識。現行ファイルは 1 項目の中でこの 2 つが
混ざっており、行数が膨らんでいる主因になっている。Node の `--test-name-pattern` の挙動、
zsh の `pipestatus`、BSD sed の `\b`、tirith の除外集合といった一次実測は
`verification-latest-techniques` skill へ寄せられる。

言語別 (rust / typescript / swift / kotlin) は現状ゼロ行のため、この Issue では作らない。
空ファイルを先に置くと、存在するのに参照価値が無い状態が続いて信用を落とす。

## タスク

- [ ] セッション再起動後に `~/.cache/claude/instructions-loaded.jsonl` を読み、未確認の 1 点を確定する
- [ ] 確定結果を踏まえて、常時ロード組と条件付きロード組の置き場所を決める
- [ ] 観測フック `home/.claude/hooks/instructions-loaded-log.py` を常設するか決め、常設するなら
      Issue #26 の集約方針に合わせてテストと lint の対象へ入れる
- [ ] 規範と知識の切り分け軸で各項目を仕分ける (rules 行きか skill 行きか)
- [ ] スコープできる 3 つを `paths` 付き rules として切り出し、subagent 経由で発火を確認する
- [ ] スコープできない 3 つの置き場所を決めて切り出す
- [ ] CLAUDE.md 本体に残す核を確定する (RFC2119 の定義、開発スタイル、個人情報、CI コスト、作業プロトコル)
- [ ] プローブ 3 点を撤去する (`~/.claude/rules/` の 2 枚と `.cache/probe.rulescope`)
- [ ] 分割後に位置参照が壊れていないことを確認する

## 関連

- [Issue #35: CLAUDE.md の指示量と読む単位を減らす](../35_CLAUDE.md%20の指示量と読む単位を減らす/issue.md) (親)
- [Issue #24: CLAUDE.md の MUST GLOBAL を族でまとめて読む単位を減らす](../24_CLAUDE.md%20の%20MUST%20GLOBAL%20を族でまとめて読む単位を減らす/issue.md)。
  #24 の「位置参照を族名参照へ張り替える」は本 Issue の前提条件。位置参照を残したまま分割すると
  参照先が別ファイルへ飛び、沈黙して壊れる
- [Issue #26: Claude Code フックの共通基盤を集約する](../26_Claude%20Code%20フックの共通基盤を集約する/issue.md)。
  本 Issue で足した観測フックが 4 本目のフックになる
