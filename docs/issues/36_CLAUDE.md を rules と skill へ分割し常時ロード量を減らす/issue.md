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

`paths` 付き rules の glob 登録はセッション開始時にキャッシュされる。セッション途中で作った `~/.claude/rules/` は自分のセッションからは見えず、同じファイルを読んでも発火しなかった。
subagent は毎回新鮮に走査するため、subagent 経由で読ませて初めて発火した。

この観測は `paths` 付きのプローブで取ったもので、射程は glob 登録に限る。paths 無しの常時層は別の挙動をする (「compact の挙動を実測した」節)。compact を挟まないセッション途中で常時層が拾われるかは未測定。

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

スコープできない (常時ロードのまま):

| 移す先 | 内容 | 理由 |
|---|---|---|
| verification-practices | 検証セクションの残り | 全作業に効く方法論でファイルに紐づかない |
| shell-practices | 検証セクションの Bash ツール項・shell-out 項・`node --test` 項 | 規範が効くのは Bash ツールの使用時と任意の言語でコードを書くときで、`.sh` の編集時ではない |
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

## 工程 1 の打ち切りと工程 2 の設計 (2026-08-21)

### 工程 1 の残余は実測で薄い

畳み込みは「読む単位」を減らす操作であって「量」を減らす操作ではない。
残り 12 カテゴリへ当てても効かないことを、着手前に次の実測で確認した。

| 根拠 | 数値 |
|---|---|
| 質量上位 3 のうち 2 つは既に畳み済み | テスト緑 top=2 項目 / 委譲 top=3 項目 |
| 残り 10 カテゴリの規模 | 各 3KB 未満、項目も 1KB 未満 |
| 語彙と前提 (14 項目 6.6KB) | 異種混在で族が立たない (どのカテゴリにも属さない前提の置き場という設計上の性質) |
| 変更の記録 (16 項目) | うち 13 個はコミット prefix の 1 行列挙で畳めない |

### 切断線を「トリガ文と判定文だけ残す」へ変えた

前セッションの切断線 (遵守時に要る / 疑うときに要る) で事例だけを移す方式を、
事例率が最大 (74%) の委譲カテゴリで試したところ 17.0% 減にとどまった。
全カテゴリへ外挿しても約 10% で、Issue の目的に対して主軸にならない。

事例と機序が同じ文に融合していて単独では切り出せないことが原因。
そこで規範の骨格 (トリガ文 + 判定文) だけを常時層に残し、
手当ての詳細・機序の説明・事例をすべて references へ移す方式へ切り替えた。

観測カテゴリで実測して 64.9% 減。

### 失われるものと引き受けたリスク

方式の性質上、常時層から手当てが消える。遵守の瞬間に効いていたと思われるもの。

- `git push` を繋がずに実行し `git ls-remote` で確認する (push は頻出操作)
- `${PIPESTATUS[0]}` が zsh で空になる (回避策を思いついた瞬間に要る)
- venv の絶対パスが変わったら再インストールする (規範だが references 行きにした)

これらは references を読まないセッションでは規範から自力で導出する必要がある。
成立するのは「トリガ文が発火したら references を読みに行く」場合に限る。

効果指標も代理変数のままである (「常時層に載っていても守られなかった 1 例」節)。

### 追加の実測

- 常時層のコストは session_start だけでなく subagent の dispatch ごとに払う。
  subagent がツールを一切使わずに CLAUDE.md の本文と由来パスを引用できることで確認した。
  この経路は `instructions-loaded.jsonl` に記録が出ない (ログ行数が 64 のまま変わらなかった)。
  「ロードされているのにログが 0 件」の実例であり、削減効果の検証にログを使うと静かに間違える
- CLAUDE.md は 2026-08-12 の 36,599B から 08-21 の 52,766B へ 9 日で +44%。
  一回きりの削減は追記で食われるため、削減量ではなく上限を検査で固定する必要がある
- `bootstrap.bats` の reverse-drift テストは `git ls-files` を使うので tracked ファイルしか見ない。
  新規ファイルを untracked のまま変異注入すると dead pin に見える。
  git add してから変異させると意図したテストだけが赤くなり、未カバーのパスを名指しする

## compact の挙動を実測した (2026-08-21)

分割方針は「compact で何が失われるか」を前提に置いていたが、そこは未検証だった。
同一セッション内で `/compact` を挟み、フックのログと `/context` の 2 系統で観測した。

### 対照の設計

一度発火させて「増えなかった」を見るだけでは compact の効果を分離できない。
compact の前に 3 つの対照を取り、基準線を 73 行に固定した。

| 対照 | 操作 | 結果 |
|---|---|---|
| A | 同じトリガファイルを再 Read | 増えない |
| B | 同じ glob に一致する別ファイルを Read | 増えない (dedup はルール単位) |
| C | session_start より後に作った rules のトリガを Read | 増えない (走査は session_start のキャッシュ) |

### 結果

`load_reason` に `compact` という値が実在する。compact 時に 3 件が記録された。

| file_path | memory_type | load_reason |
|---|---|---|
| `<repo>/CLAUDE.md` | Project | compact |
| `~/.claude/CLAUDE.md` | User | compact |
| `~/.claude/rules/probe-noscope.md` (paths 無し) | User | compact |

`paths` 付きの 2 プローブはどちらも 1 件も出ていない。`probe-compact-rescope.md` は session_start より前 (03:38 JST)、`probe-compact-fresh.md` は後 (03:44 JST) に作ってあり、session_start は 03:40 JST。両方ともファイルが実在して frontmatter も同形であることを確認したうえでの陰性。

`/context` も同じ向きを示した。

| カテゴリ | compact 前 | compact 後 |
|---|---|---|
| 合計 | 92.3k | 70k |
| Memory files | 17.3k (3 ファイル) | 17.5k (4 ファイル) |
| Messages | 42.6k | 19.7k |

Memory files が増えたのは probe-noscope.md (209 トークン) が加わったため。CLAUDE.md 本体は 1 トークンも減っていない。

### 確定したこと

- 常時ロード層 (CLAUDE.md と `paths` 無し rules) は compact で失われない。
  Messages とは別カテゴリに置かれ、compact のたびに再注入される
- 常時層は compact 時にディレクトリを走査し直す。
  session_start より後に作った probe-noscope.md が compact で拾われた
- `paths` 付き rules は Messages 側に入る。compact で再注入されず、圧縮対象になる
- ただし compact は `paths` 付き rules の dedup をリセットする。
  compact 後に一致ファイルを Read すると同じルールが再発火した
  (対照 A で「同一セッション内の再 Read では増えない」を確定させてあるので、compact の効果と言える)
- `paths` 付き rules の glob 登録は compact でも更新されない。
  session_start より後に作った probe-compact-fresh.md は compact 後も発火しなかった。
  常時層は再走査されるのに glob 登録は据え置かれるという非対称がある

事前に立てた予測との突き合わせ。

| 予測 | 結果 |
|---|---|
| 予測 1: CLAUDE.md は compact で失われない | 当たり |
| 予測 2: `paths` 付き rules は失われ dedup により再注入されない | 前半は当たり、後半は外れ |

### 分割方針への影響

`~/.claude/rules/00-core.md` へ常時層を移す案は不要になった。CLAUDE.md 本体が既に compact 耐性を持つ。

`paths` 付き rules には穴がある。compact のあと規範が戻るのは、一致ファイルへ特定の操作をしたときだけ。
どの操作が該当するかで穴の広さが決まる。実測は「発火経路を実測した」節。

`~/.claude/rules/` は symlink ではなく実ディレクトリで、`home/.claude/rules/` はリポジトリに存在しない。
bootstrap の SYMLINK_PAIRS にも無い。切り出す前にここを配線しないと、rules は他マシンへ配布されず
`instruction_budget` の `RULES_GLOB` からも外れる (今は glob が 0 件に一致するので予算検査は素通りしている)。

## 発火経路を実測した (2026-08-21)

compact 節が残した 1 点。`paths` 付き rules が Read で発火することは分かっていたが、
Edit / Write でも発火するかは測っていなかった。

### 前提

compact の実験で使った `probe-compact-rescope.md` (`paths: ["**/*.rulescope"]`) を撤去せずに
前セッションを終え、触らないまま新しいセッションを開始した。glob 登録は session_start でしか
更新されないので、プローブはセッションを跨いで置いておかないと登録されない。
判定後に撤去したので `~/.claude/rules/` は空に戻っている。

### 手順

dedup はルール単位かつセッション単位なので、一致ファイルへの最初の 1 アクションだけが情報を持つ。
順序を固定し、陰性のときだけ次へ進めた。基準線は 86 行。

| # | ツール | 操作 | ログ増分 | 注入 |
|---|---|---|---|---|
| 1 | Write | 新規ファイル `.cache/phase0w.rulescope` を作成 | 0 | なし |
| 2 | Edit | 同じファイルを書き換え | 0 | なし |
| 3 | Read | 同じファイルを読む (positive control) | +1 | あり |

3 で記録された行は `load_reason` が `path_glob_match` で、`trigger_file_path` は 1 で作ったファイル。

### 確定したこと

- 発火するのは Read のみ。Write と Edit では発火しない
- この陰性は dedup 由来ではない。dedup はルール単位なので、1 か 2 で発火していれば
  3 でも注入されないはず。3 が注入された以上 1 と 2 は発火していない。
  ログ増分 0 と合わせて 2 経路で確認している
- トリガファイル側の glob 判定は動的。session_start の時点で存在しなかったファイルが
  発火させている。session_start のキャッシュに固定されるのは rules 側の登録だけで、
  一致するファイルの一覧ではない

### 切り出しへの影響

Edit ツールは原則として同一会話内の事前 Read を要求するので、実運用の Edit は
直前の Read が発火させている。今回それを回避できたのは Write 直後で file state が
current だったため。穴が開くのはこの経路、つまり対象を読まずに書く場面に限られる。

分割案の 3 つでは testing-practices がこれを踏む。TDD で最初にテストを書く場面は
テストファイルの新規作成そのもので、既存を読まずに Write することになる。

## 切り出しを 1 つ実施した (2026-08-21)

配線と最初の 1 つを同じ変更で入れた。git は空ディレクトリを追跡しないので、
`home/.claude/rules/` を作るには最初の rules ファイルが要る。

対象は frontend-practices にした。当初の予定は shell-practices だったが、
下記のとおりスコープできないと分かったので差し替えた。

### shell-practices はスコープできない

分割案は paths を `sh / zsh / bats` としていたが、該当する 3 項目の適用場面は
どれもシェルスクリプトファイルの編集ではない。

| 項目 | 効く場面 |
|---|---|
| Bash ツールでコマンドを組むとき | Bash ツールの使用時。Bash は rules を発火させない |
| shell-out / 外部 CLI オーケストレーション | 任意の言語で subprocess を起動するコードを書くとき |
| `node --test` にはテストファイルか glob を渡す | Bash ツールの使用時 |

判定したセッション自身が反例になっている。`.sh` を Read ツールで 1 度も開かずに
作業したが、Bash ツールでコマンドを組む規範は繰り返し必要だった。
`sh` にスコープしていれば全て沈黙している。

testing-practices にも同じ穴が部分的にある。「検査機構 (ゲート・ガード・lint ルール・
CI チェック) を足したときの変異は 3 種いる」はテストファイル以外を触る場面の規範。

### 発火の確認と、確認できなかったこと

`paths: ["**/*.tsx", "**/*.jsx", "**/*.html", "**/*.css"]` で切り出し、
subagent に `.tsx` を Read させて注入を確認した。見出しと 6 項目がそのまま入っている。

同時に確認できなかったことが 1 つある。その subagent は起動時の User memory にも
同じ 6 項目を持っていた。CLAUDE.md からの削除は済んでいて live ファイルにも残って
いないので、実行中のセッションが session_start でキャッシュした削除前の版を保持し、
subagent がそれを継承したことになる。常時層が compact で再走査される挙動と同じで、
編集の反映も新セッションか compact を待つ。

つまり今回観測したのは「scoped rules が発火する」ことだけで、「常時層から消えた」
ことは観測できていない。後者の確認には新セッションが要る。

### 副次的に直ったもの

bootstrap を走らせたところ、追加の設定ディレクトリ側の `references` が張られて
いなかったことが分かり、同時に張られた。SYMLINK_PAIRS には元から載っていたので
テストは緑のままで、live にだけ穴が開いていた。

## 常時層に載っていても守られなかった 1 例 (2026-08-21)

分割の前提は「量を減らせば読まれる」だった。compact の実測と同じセッションで、その前提に対する反例が 1 件出たので記録する。

### 何が起きたか

ブランチを push したあと、次の形でコマンドを組んだ。

    git push -u origin <branch> 2>&1 | tail -5; echo "exit=${PIPESTATUS[0]}"

出力は `exit=` で、判定が空のまま返った。push 自体は成功していたので実害は無く、`git rev-parse` で local と remote の HEAD を突き合わせ直して確認した。

### 2 層の両側で同時に失敗している

この 1 件は「references へ移したから届かなかった」だけでは説明できない。

| 層 | 内容 | 結果 |
|---|---|---|
| 常時層 `CLAUDE.md` | exit code で判定するコマンドはパイプにも後続コマンドにも繋がない | コンテキストに載っていたが破った |
| `references/observation.md` | 回避策の `${PIPESTATUS[0]}` は zsh では常に空になる。`pipestatus` が 1 始まり | 読まずに回避策を自作し、まさにその誤りを踏んだ |

判定文を破ったうえで、手当てを再発明し損ねた。工程 2 の切断線 (判定文は常時層、手当ては references) は設計どおりに機能しており、失敗したのは判定文の遵守と references の参照のどちらもである。

### 誤りが二重で、しかも同じ形で返る

zsh 5.9 で実測した。

| 式 | 結果 |
|---|---|
| `${PIPESTATUS[0]}` | 空 |
| `${pipestatus[0]}` | 空 |
| `${pipestatus[1]}` | 正しい終了ステータス |

`PIPESTATUS` は zsh に存在せず、加えて zsh の配列は 1 始まりなので `[0]` も空を返す。独立した 2 つの誤りがどちらも空文字列という同じ形で返るため、片方を直しても症状が変わらない。エラーにもならないので、出力を読まなければ判定が行われたように見える。

### この 1 件から言えること / 言えないこと

言えるのは 1 つだけ。規範が常時ロード層に載っていることは遵守の保証にならない。

言えないのは以下。n=1 で対照が無い。

- 分割によって遵守率が上がるか下がるか
- 常時層が 33KB だから守れなかったのか、量とは無関係なのか
- references へ移した項目の遵守率が実際に落ちているか

より一般には、本 Issue が測っているのはバイト数だけで、遵守そのものは測っていない。削減量は目的ではなく代理変数であり、代理変数の改善が目的の改善を意味することはこの 1 件では支持されていない。

## タスク

- [x] セッション再起動後に `~/.cache/claude/instructions-loaded.jsonl` を読み、未確認の 1 点を確定する(2026-08-17 に実測。`paths` 無しの rules は session_start で常時ロードされる)
- [x] nested traversal による二重ロードを止める
      (`claudeMdExcludes` をユーザースコープの settings.json へ配線し、config-guard で取り付けを pin した。
      検査対象・検査機構・取り付けの 3 種の変異でいずれも赤くなることを確認済み)
- [x] 確定結果を踏まえて、常時ロード組と条件付きロード組の置き場所を決める
      (常時ロード組の事例と手当ては `home/.claude/references/*.md` へ。skill にしないのは
      apm の SHA pin 往復が追記のたびに要るため。rules に置かないのは paths 無しが常時ロードされるため)
- [x] 工程 1: 族ごとに畳んで読む単位を減らす
      - [x] 「観測した結果が…」カテゴリ。21 項目 → 6 項目 (3 族 + 3 単独)、97 行 17,010B → 57 行 15,208B
      - [x] 残る 12 カテゴリは実測により適用対象なしと結論して打ち切り (下記「工程 1 の打ち切り」)
- [x] 観測フック `home/.claude/hooks/instructions-loaded-log.py` を常設するか決め、常設するならIssue #26 の集約方針に合わせてテストと lint の対象へ入れる
      (常設で確定。Issue #26 の集約を先に行い `scripts/claude-hooks/` の 4 本目として入れた。
      黒箱テスト 12 件を書き、fail-safe / ensure_ascii / 追記 / 除外集合の 4 箇所へ変異注入して
      いずれも赤くなることを確認済み)
- [x] 工程 2: 各カテゴリをトリガ文と判定文まで削り、手当てと事例を references へ移す
      - [x] 観測 15,837B → 5,610B、テスト緑 6,358B → 3,344B、委譲 6,788B → 4,034B
      - [x] ホスト環境 4,110B → 2,528B、語彙と前提 6,622B → 5,476B
      - [x] 残る 8 カテゴリをまとめて (canonical / security / git-workflow の references を追加)
      - [x] 合計 52,766B → 33,294B (36.9% 減)。references は 8 ファイル計 35,814B
- [x] 常時ロード層の予算を検査で固定する (config-guard の `instruction_budget`)
      (検査対象・検査機構・取り付けの 3 種の変異でいずれも赤くなることを確認済み。
      覆う範囲は User スコープの CLAUDE.md と paths 無し rules のみで、
      プロジェクト CLAUDE.md・skill description・MEMORY.md は範囲外であることを docstring に明記)
- [x] compact で常時ロード層が失われるかを実測する
      (対照 3 点で基準線を固定してから `/compact` を挟み、フックのログと `/context` の 2 系統で観測した。
      結果は「compact の挙動を実測した」節)
- [x] `home/.claude/rules/` を作り bootstrap の SYMLINK_PAIRS へ配線する
      (最初の切り出しと同じ変更で入れた。結果は「切り出しを 1 つ実施した」節)
- [x] `paths` 付き rules が Read 以外の経路 (Edit / Write) でも発火するかを新セッションで実測する
      (結果は「発火経路を実測した」節)
- [x] frontend-practices を切り出し、subagent 経由で発火を確認する
      (切り出せる候補は 3 つではなく 2 つだった。理由は「切り出しを 1 つ実施した」節)
- [ ] testing-practices を切り出す (検査機構の変異を扱う項は対象外にするか決める)
- [ ] 新セッションで常時層から消えていることを確認する (現セッションは削除前の
      CLAUDE.md をキャッシュしているため、このセッションでは観測できない)
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
