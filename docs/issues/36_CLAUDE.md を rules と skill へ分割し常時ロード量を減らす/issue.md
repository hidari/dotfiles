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

言語別の内容はほぼ無い。Rust / TypeScript / Swift / Kotlin の出現数はいずれも 0 で、実際の質量は git (17) / gh (9) / zsh・bash (5) と、言語非依存の検証・テスト方法論に寄っている。

## 実測で確定した機構 (2026-08-16、Claude Code 2.1.233)

バイナリの zod 定義と `HOOK_EVENT_REGISTRY` から直接読んだ。推測ではない。

`InstructionsLoaded` フックが実在する。ペイロードの schema は次のフィールドを持つ(値の canonical はバイナリ側であり、ここでは再掲せずフィールド名のみ記す)。

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

- フックの登録は settings.json を書いた瞬間に効く。セッション再起動は不要(PostToolUse へ同じロガーを仮付けした対照で確認)
- gitignore 対象の `.cache/` 配下のファイルでもトリガーになる

## 踏んだ罠 (運用上の注意)

rules ディレクトリの走査はセッション開始時にキャッシュされる。セッション途中で作った `~/.claude/rules/` は自分のセッションからは見えず、同じファイルを読んでも発火しなかった。
subagent は毎回新鮮に走査するため、subagent 経由で読ませて初めて発火した。

rules を 1 枚足しても再起動するまで効かない。しかも「効かない」が無言なので、書いて動かして反応が無いと `paths` の書き方の誤りと誤診する形をしている。
動作確認は subagent を 1 本投げるのが最短。

## 測定結果 (2026-08-17)

セッションを再起動し `~/.cache/claude/instructions-loaded.jsonl` を読んだ。対照は成立している。

| file_path | memory_type | load_reason |
|---|---|---|
| `~/.claude/CLAUDE.md` | User | session_start |
| リポジトリ直下の `CLAUDE.md` | Project | session_start |
| `~/.claude/rules/probe-user-always.md` (`paths` 無し) | User | session_start |

`paths` を持つ `probe-user-scoped.md` はこの 3 件に並んでいない。同一ディレクトリの同一形式で片方だけが出るため、分岐点が `paths` frontmatter の有無であることを単独レコードより強く言える。

フックの申告とは独立に、再起動後のコンテキストへ `probe-user-always.md` の本文が実際に注入されていること、`probe-user-scoped.md` の本文は入っていないことも確認した。
「フックは鳴ったが中身は入っていない」形の乖離は無い。

確定: `paths` を持たない `~/.claude/rules/*.md` は session_start で常時ロードされる。

### このログで測れないこと

auto-memory の `MEMORY.md` と SessionStart フックの `additionalContext` は、コンテキストへ実際に入っているのにレコードが 1 件も出ない。
このログは注入経路の一部しか見ていない。

したがってレコードの非存在を「ロードされていない」と読んではならない。
今回 `probe-user-scoped.md` を陰性と判定できたのは、同じ経路 (rules ディレクトリの走査) の対照が出ているからであって、経路が違うものには同じ推論を使えない。

## 二重ロードの発見と解消 (2026-08-20)

分割に着手する前に、同じ 54KB を 2 回払っている経路が見つかった。分割で減らす量とは別勘定になる。

`Read` ツールで `home/.claude/` 配下のファイルを読むと、祖先の `home/.claude/CLAUDE.md` が `nested_traversal` でコンテキストへ注入される。
このファイルは `~/.claude/CLAUDE.md` の symlink 実体なので、User memory として既にロード済みの内容と完全に同一である。

| 読み方 | 発火 |
|---|---|
| `Bash` の `head` で同ディレクトリのファイルを読む | しない |
| `Read` ツールで読む | する |

同じディレクトリの同種のファイルで片方だけが出るため、分岐点がツールの種別であることを単独レコードより強く言える。
同一セッション内では 2 回目以降は発火しないが、subagent は起動ごとに新鮮なコンテキストを持つため、起動した本数だけ二重化する。

`claudeMdExcludes` (settings.json のキー) で止まる。除外の有無で対照を取った。

| 設定 | subagent のコンテキスト | フックのログ |
|---|---|---|
| 除外なし | 注入される | `nested_traversal` を記録 |
| 除外あり (プロジェクトの local) | 注入されない | 記録なし |
| 除外あり (ユーザースコープ) | 注入されない | 記録なし |

セッション再起動なしで効いた。
ユーザースコープへ置いたのは、config-guard が `home/.claude/settings.json` を index 経由で検査しており、取り付けを不変条件として pin できるため。

### 残る穴

- config-guard が見るのは `home/.claude/settings.json` だけで、プロジェクトスコープの settings は覆っていない
- `claudeMdExcludes` というキー名が Claude Code 側で変わったら静かに壊れる。設定の存在は pin できるが、それが効いていることは pin できない (未知のキーは無警告で無視される)
- skill の重複登録 (`home:` プレフィックスで 15 個) は別経路で、この除外では止まらない。載るのは description だけなので影響は小さい

## 分割案の下書き

`paths` で絞れるかどうかで性質が分かれる。
絞れない側を rules に置いても常時ロード量は減らないため、置き場所の判断はこの軸で行う。

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

測定の結果、常時ロード組も rules へ置けることが確定した。
ただし置いても session_start で払うトークンは変わらない。
減るのは CLAUDE.md 本体の行数と族ごとの独立性であって、セッション開始時のコストではない。

したがって本 Issue の目的である常時ロード量の削減を達成する経路は 2 つに限られる。

1. `paths` で絞れる族を条件付きロードへ移す
2. 常時ロード組そのものを skill へ逃がすか削る

置き場所を rules へ移すだけでは達成されない。
1で移せる量が上の3つ分しかないため、削減幅の主たる決定要因は 2 の側になる。

skill 側への切り分けの軸を 1 本立てる。rules に置くのは「こう振る舞え」という規範、skill に置くのは「こういう事実がある」という知識。
現行ファイルは 1 項目の中でこの 2 つが混ざっており、行数が膨らんでいる主因になっている。Node の `--test-name-pattern` の挙動、zsh の `pipestatus`、BSD sed の `\b`、tirith の除外集合といった一次実測は `verification-latest-techniques` skill へ寄せられる。

言語別 (rust / typescript / swift / kotlin) は現状ゼロ行のため、この Issue では作らない。
空ファイルを先に置くと、存在するのに参照価値が無い状態が続いて信用を落とす。

## タスク

- [x] セッション再起動後に `~/.cache/claude/instructions-loaded.jsonl` を読み、未確認の 1 点を確定する(2026-08-17 に実測。`paths` 無しの rules は session_start で常時ロードされる)
- [x] nested traversal による二重ロードを止める
      (`claudeMdExcludes` をユーザースコープの settings.json へ配線し、config-guard で取り付けを pin した。
      検査対象・検査機構・取り付けの 3 種の変異でいずれも赤くなることを確認済み)
- [ ] 確定結果を踏まえて、常時ロード組と条件付きロード組の置き場所を決める
- [ ] 工程 1: 族ごとに畳んで読む単位を減らす (移設より先に行う。圧縮後に残るものが変わるため)
      - [x] 「観測した結果が…」カテゴリ。21 項目 → 6 項目 (3 族 + 3 単独)、97 行 17,010B → 57 行 15,208B
      - [ ] 残る 12 カテゴリ
- [x] 観測フック `home/.claude/hooks/instructions-loaded-log.py` を常設するか決め、常設するならIssue #26 の集約方針に合わせてテストと lint の対象へ入れる
      (常設で確定。Issue #26 の集約を先に行い `scripts/claude-hooks/` の 4 本目として入れた。
      黒箱テスト 12 件を書き、fail-safe / ensure_ascii / 追記 / 除外集合の 4 箇所へ変異注入して
      いずれも赤くなることを確認済み)
- [ ] 規範と知識の切り分け軸で各項目を仕分ける (rules 行きか skill 行きか)
- [ ] スコープできる 3 つを `paths` 付き rules として切り出し、subagent 経由で発火を確認する
- [ ] スコープできない 3 つの置き場所を決めて切り出す
- [ ] CLAUDE.md 本体に残す核を確定する (RFC2119 の定義、開発スタイル、個人情報、CI コスト、作業プロトコル)
- [x] プローブ 3 点を撤去する (`~/.claude/rules/` の 2 枚と `.cache/probe.rulescope`)
      (2026-08-20 に実測して確認。`~/.claude/rules/` は空、`.cache/probe.rulescope` も不在。
      観測フックのログ `~/.cache/claude/instructions-loaded.jsonl` は残っている)
- [ ] 分割後に位置参照が壊れていないことを確認する

## 関連

- [Issue #35: CLAUDE.md の指示量と読む単位を減らす](../35_CLAUDE.md%20の指示量と読む単位を減らす/issue.md) (親)
- [Issue #24: CLAUDE.md の MUST GLOBAL を族でまとめて読む単位を減らす](../24_CLAUDE.md%20の%20MUST%20GLOBAL%20を族でまとめて読む単位を減らす/issue.md)。
  #24 の「位置参照を族名参照へ張り替える」は本 Issue の前提条件。位置参照を残したまま分割すると
  参照先が別ファイルへ飛び、沈黙して壊れる
- [Issue #26: Claude Code フックの共通基盤を集約する](../26_Claude%20Code%20フックの共通基盤を集約する/issue.md)。
  本 Issue で足した観測フックが 4 本目のフックになる
