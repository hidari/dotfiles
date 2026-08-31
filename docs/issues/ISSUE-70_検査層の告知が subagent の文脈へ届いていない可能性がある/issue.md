---
status: open
---

# fix: 検査層の告知が subagent の文脈へ届いていない可能性がある

## 背景

`guard-health.py` は SessionStart で検査層の沈黙を測り、`systemMessage` と
`additionalContext` の両方へ 1 通を載せる。両方へ載せるのは、ユーザーの UI とモデルの文脈で
届く相手が違うためである。

2026-09-01 に、この告知が subagent の文脈へ届いていない可能性を示す観測が出た。確定して
いないので、まず測る Issue である。

## 観測 (2026-09-01)

判断の場で走らせた subagent 2 本が、独立に同じことを報告した。

- 自分の文脈に「検査層の健全性」の行が無い
- 一方で自分の Bash 呼び出しには PreToolUse 由来の tirith の通知が届いており、deny も効いた

沈黙が偶然でないことも subagent 側で測られている。当時このマシンは apm ガードが沈黙した
状態で、subagent の Bash 環境で `guard_resolve.shim_resolves()` が偽、`shim_exists()` が真、
`guard_probes.probe_apm().healthy` が偽を返した。SessionStart が走っていれば必ず 1 件を
告げていた条件である。

対照も 1 つ取られている。`settings.json` の SessionStart には日付を出すだけのフックも居るが、
それも subagent へ届いていない。タイムアウトで捨てられただけという対立仮説はこれで消える。

## 確度と、根拠にならなかった読み

確かめたのは subagent の自己申告と配線の読みだけである。

`handoff-sentinel.py` の `agent_id` ゲートとの非対称を根拠に挙げる読みがあったが、これは
成立しない。あの行は `main()` に置かれた全 action 共通のガードで、SessionStart 固有ではなく
PostToolUse と Stop も通る。むしろゲートが存在すること自体は「payload に `agent_id` が入り
うる」ことを意味するので、フックが agent の文脈で発火する経路があることの傍証になる。

## なぜ気にするか

このリポジトリの既定の実行形態は subagent-driven である。実際に Bash を打つのは主に
subagent なので、届いていないなら「コマンドを打つ側だけが検査層の沈黙を知らない」ことに
なる。

apm ガードについてはさらに具体的な穴になる。shim が沈黙しているマシンでは、フックが自力で
捕まえられない形 (包み込み / 変数間接 / xargs) はどの層からも信号が出ない。

## タスク

- [ ] 「SessionStart が subagent では発火しない」のか「発火するが出力が注入されない」のかを
      切り分ける。`guard-health.py` へ一時的なログ書き出しを入れて subagent を 1 本投げれば
      判別できる
- [ ] 届いていないと確定した場合、埋めるかどうかを決める。別層の重複で埋めると canonical が
      2 つになるので、埋め方は自明ではない
- [ ] `guard-health.py` に `agent_id` ゲートが無く `handoff-sentinel.py` にはある非対称を、
      仕様の取り違えかどうかまで見て 1 行で残す

## 関連

ISSUE-68: コマンド単位の告知を畳むか判断した Issue。この観測を判断の根拠には数えなかったが、
材料として本文に残した。closed なので `closed/` 配下にある

ISSUE-59: セッション頭で検査層の沈黙を検出する層を作った Issue。closed なので `closed/` 配下に
ある

ISSUE-67: コンテキスト閾値の通知が 1 セッション 1 回で再武装しない。別のフックだが、
セッション頭の 1 回で足りるかという同じ問いを扱う
