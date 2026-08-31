---
status: open
---

# fix: 検査層の告知を SubagentStart 経由で subagent へ届ける

## 背景

`guard-health.py` は SessionStart で検査層の沈黙を測り、`systemMessage` と `additionalContext`
の両方へ 1 通を載せる。この告知が subagent の文脈へ届いていないことを ISSUE-70 で確定させた。
届かない理由は「発火するが注入されない」ではなく、SessionStart hook が subagent の起動では
そもそも発火しないためである。

このリポジトリの既定の実行形態は subagent-driven で、実際に Bash を打つのは主に subagent で
ある。届いていない現状では、コマンドを打つ側だけが検査層の沈黙を知らない。apm ガードについては
さらに具体的な穴になる。shim が沈黙しているマシンでは、フックが自力で捕まえられない形
(包み込み / 変数間接 / xargs) はどの層からも信号が出ない。

## 埋める経路 (2026-09-01 実測)

`SubagentStart` hook が使える。発火し、`hookSpecificOutput.additionalContext` が subagent の
文脈へ届くことをカナリア文字列で確認した。実測の生データと対照の取り方は ISSUE-70 が持つ。

ただしこのマシンにある公式ドキュメント (`working-with-claude-code` skill の `hooks.md` と
`hooks-guide.md`) は `SubagentStart` を 1 件も記述していない。実測が唯一の根拠なので、上流の
変更で挙動が変わりうることを織り込むこと。

発火の頻度は確かめていない。プローブを登録した後に起動した subagent 1 本で発火を見ただけで、
毎回走るかは n=1 のまま残っている。告知が何回出るかも、コストの見積もりもここに乗るので先に
測る。

`handoff-sentinel.py` が持つ `agent_id` ゲートをここへ持ち込まないこと。あのゲートは
SessionStart では効く場面が無いが、SubagentStart では到達するので告知が全部消える。

## 決めること

`guard-health.py` は `_HOOK_EVENT_NAME` を `"SessionStart"` の定数で固定している。
`hookSpecificOutput.hookEventName` が実イベント名と一致する必要があるかは未確認で、カナリア
実験では一致させた形しか試していない。一致が不要なら定数のままでも配線でき、必要なら呼び出し
側から渡す形へ変える。

## タスク

- [ ] `SubagentStart` が subagent の起動ごとに発火するかを測る
- [ ] `hookEventName` が実イベント名と一致しないときの挙動を測る
- [ ] `guard-health.py` の `_HOOK_EVENT_NAME` を呼び出し側から渡す形へ変えるか決める
- [ ] `home/.claude/settings.json` の `SubagentStart` へ `guard-health.py` を配線する
- [ ] config-guard の配線検査を SubagentStart にも広げる。settings.json の配線を pin して
      いるのはこの検査なので、配線と同時に更新する
- [ ] 発火のたびにプローブが走るコストを測り、許容できるか判断する
- [ ] 変異注入で、配線を外すと赤くなることを確認する

## 関連

ISSUE-70: 告知が subagent へ届いていないことを測って確定させた Issue。実測の生データと対照の
取り方はあちらが持つ。closed なので `closed/` 配下にある

ISSUE-59: セッション頭で検査層の沈黙を検出する層を作った Issue。closed なので `closed/` 配下に
ある

ISSUE-67: コンテキスト閾値の通知が 1 セッション 1 回で再武装しない。別のフックだが、告知を
いつ何回出すかという同じ問いを扱う
