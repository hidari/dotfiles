---
status: closed
---

# fix: 検査層の告知が subagent の文脈へ届いていない可能性がある

## 背景

`guard-health.py` は SessionStart で検査層の沈黙を測り、`systemMessage` と
`additionalContext` の両方へ 1 通を載せる。両方へ載せるのは、ユーザーの UI とモデルの文脈で
届く相手が違うためである。

2026-09-01 に、この告知が subagent の文脈へ届いていない可能性を示す観測が出た。

## 結論 (2026-09-01 実測)

届いていない。理由は「発火するが注入されない」ではなく、SessionStart hook が subagent の
起動ではそもそも発火しないためである。

同時に埋める経路も確定した。`SubagentStart` hook が実在し、そちらは subagent の文脈へ届く。
埋める方針で決め、実装は ISSUE-71 が持つ。

## 測り方と対照

一時的な hook プローブを追跡外の `.claude/settings.local.json` へ登録し、payload の要点
(`hook_event_name` / `agent_id` / `session_id` / `source` / `tool_name`) をログへ落とした。
`guard-health.py` を書き換えなかったのは、追跡下の live スクリプトを一時編集すると revert の
し忘れがそのままコミットに乗るためである。

| プローブ | 件数 | 内訳 |
| --- | --- | --- |
| SessionStart | 1 | headless セッション (`source: startup`) のみ |
| SubagentStart | 1 | subagent の起動時。`agent_id` あり |
| SubagentStop | 5 | subagent の終了時。`agent_id` あり |
| PreToolUse | 38 | 親と subagent の両方。subagent 側は `agent_id` あり |
| PostToolUse | 36 | 同上 |

subagent は観測期間中に 5 本走ったが、SessionStart はそのどれでも発火しなかった。

SubagentStart だけ件数が SubagentStop と食い違うのは、そのプローブを観測の後半で登録したため
である。登録より後に起動した subagent は 1 本で、その 1 本では発火した。毎回発火するかは
n=1 なので確かめていない。

0 件を「発火しない」と読むために対照を 2 つ置いた。1 つは同じプローブスクリプトが
PreToolUse / PostToolUse / SubagentStop で非空を返すことで、スクリプトとパス解決の故障という
対立仮説を潰す。もう 1 つは headless セッション (`claude -p`) を 1 本起動し、SessionStart
プローブが新しい `session_id` と `source: startup` で 1 件書くことである。後者が無いと
「SessionStart の登録そのものが反映されていない」という対立仮説が残り、0 件はどちらとも読める。

## 埋める経路

`SubagentStart` hook は発火し、`hookSpecificOutput.additionalContext` が subagent の文脈へ
届く。カナリア文字列を注入して subagent に探させ、`SubagentStart hook additional context:
<文字列>` という独立した system メッセージとして届くことを確認した。発火した hook の
`agent_id` とカナリアを受け取った subagent の ID は一致する。

ただしこのマシンにある公式ドキュメント (`working-with-claude-code` skill の `hooks.md` と
`hooks-guide.md`) は `SubagentStart` を 1 件も記述していない。実測が唯一の根拠である。

## 届いていたもの / いなかったもの

subagent の文脈に無かったものは、いずれも SessionStart hook の出力である。

- `guard-health.py` の告知
- `settings.json` が出す日本語の日付行
- `settings.local.json` が cat する PRIVATE_CLAUDE.md
- `handoff-sentinel.py` が注入する引き継ぎ

一方で届いていたものがある。CLAUDE.md (user / project)、MEMORY.md 全文、userEmail、そして
英語の `Today's date is ...` である。最後のものは hook 由来ではなく Claude Code 本体が入れる
もので、日本語の日付行とは別経路にあたる。

## 確度と、根拠にならなかった読み

`handoff-sentinel.py` の `agent_id` ゲートとの非対称を根拠に挙げる読みは成立しない。
あの行は `main()` に置かれた全 action 共通のガードで、SessionStart 固有ではなく
PostToolUse と Stop も通る。ゲートの存在は「payload に `agent_id` が入りうる」ことしか
意味せず、どのイベントで入るかは区別しない。

## agent_id ゲートの非対称について

design ドキュメント (`docs/superpowers/archive/2026-07-03-session-handoff-design.md`) は
`agent_id` ゲートを 3 イベント共通のものとして定めており、SessionStart 側にも
`test_agent_id付きのsubagentでは注入しない` という pin がある。

この非対称は仕様の取り違えではない。ただし pin の一部は到達しない条件を守っている。
SessionStart は subagent で発火しないので、そのゲートが効く場面が実環境に無い。PostToolUse と
Stop 側のゲートは到達する。`guard-health.py` にゲートが無いことは、SessionStart に配線されて
いる限り実害を持たない。

## 副産物

- `.claude/settings.local.json` の hook 登録変更は実行中セッションへ反映される。即時ではなく
  数回のツール呼び出しぶんのラグがあった
- 観測期間中に、自分が明示的に投げていない subagent が 2 本走っていた (SubagentStop の
  `agent_id` が 5 種類あり、こちらが投げたのは 3 本)
- 公式ドキュメントを調べさせた subagent の報告は、行番号の出典がすべて実在しなかった。
  `hooks-guide.md` は 332 行なのに 494 / 581 / 690 / 839 行を引用し、`agent_id` も
  `SubagentStart` も記述は 0 件である。結論の一部は実測と一致したが、根拠は捏造だった
- `.zshrc` の `claude` 関数は非対話シェルへ届くのに、それが呼ぶ `_claude_config_dir` は届かず
  `command not found` になる。同じ `function name() {}` 形式なのに片方だけ欠ける。ISSUE-44 の
  材料になる

## タスク

- [x] 「SessionStart が subagent では発火しない」のか「発火するが出力が注入されない」のかを
      切り分ける。`guard-health.py` へ一時的なログ書き出しを入れて subagent を 1 本投げれば
      判別できる
- [x] 届いていないと確定した場合、埋めるかどうかを決める。別層の重複で埋めると canonical が
      2 つになるので、埋め方は自明ではない
- [x] `guard-health.py` に `agent_id` ゲートが無く `handoff-sentinel.py` にはある非対称を、
      仕様の取り違えかどうかまで見て 1 行で残す

## 関連

ISSUE-71: 埋める実装を持つ Issue。SubagentStart への配線と、その検査の更新を扱う

ISSUE-68: コマンド単位の告知を畳むか判断した Issue。この観測を判断の根拠には数えなかったが、
材料として本文に残した。closed なので `closed/` 配下にある

ISSUE-59: セッション頭で検査層の沈黙を検出する層を作った Issue。closed なので `closed/` 配下に
ある

ISSUE-67: コンテキスト閾値の通知が 1 セッション 1 回で再武装しない。別のフックだが、
セッション頭の 1 回で足りるかという同じ問いを扱う

ISSUE-44: `.zshrc` が非対話シェルへ運ぶ設定を絞る Issue。副産物の `_claude_config_dir` が
届かない件はあちらの材料になる
