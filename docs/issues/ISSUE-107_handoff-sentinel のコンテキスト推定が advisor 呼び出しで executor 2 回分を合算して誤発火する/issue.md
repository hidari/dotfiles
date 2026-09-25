---
status: open
---

# fix(hooks): handoff-sentinel のコンテキスト推定が advisor 呼び出しで executor 2 回分を合算して誤発火する

## 背景

2026-09-25 に scriptoria のセッションで、handoff-sentinel の posttool が「コンテキスト使用率がしきい値を超えた (推定 551679 tokens)」と通知し、エージェントが作業を打ち切って handoff を書いた。実際の占有量は約 30% で、ユーザーの手元の表示 (30%) とも一致しており、誤発火だった。

`_context_tokens` は最後の非 sidechain の assistant エントリの `usage` から `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` を足している。advisor ツールを呼んだ応答では、トップレベルの `usage` が executor の複数回の推論を合算した値になっていて、占有量のほぼ 2 倍になる。

実測 (transcript の 2026-09-25T05:33:00Z の assistant エントリ):

- トップレベル: `input_tokens` 4、`cache_read_input_tokens` 543544、`cache_creation_input_tokens` 8131 (合計 551679)
- `usage.iterations` は 3 段
  - 1 段目 `type: "message"`: input 2、cache_read 270024、cache_creation 3496
  - 2 段目 `type: "advisor_message"`、`model: "claude-fable-5-1"`: input 235169 (トップレベルには入っていない)
  - 3 段目 `type: "message"`: input 2、cache_read 273520、cache_creation 4635
- トップレベルは `type: "message"` の 2 段の合計 (270024 + 273520 = 543544)
- 直前のエントリ (advisor なし) は `iterations` が 1 段で、トップレベルと一致する (合計 270026)
- 直後の advisor を含まないエントリは 280121 に戻っている

通知は PostToolUse で鳴るため、advisor を含む応答の直後のツール呼び出しで発火する。推定が占有量のほぼ 2 倍になるので、既定の窓としきい値 (`DEFAULT_CONTEXT_WINDOW_TOKENS` と `DEFAULT_CONTEXT_THRESHOLD_PCT`) のままでも、占有量がしきい値の半分を超えたあたりから advisor を呼ぶたびに誤発火しうる。

## タスク

- [ ] transcript からの推定を直すか、harness の使用率を使うかを決める。statusline は stdin で `context_window.used_percentage` を受け取っており (`home/.claude/statusline-command.sh`)、レートリミットは同じ stdin の値を statusline がキャッシュへ書いて hook が読む経路が既にある (`handoff-sentinel.py` の `_rate_limits_path`)。使用率を同じ経路で渡せば、サーバー側ツールごとの場合分けと窓サイズの決め打ちが要らなくなり、transcript からの推定は statusline が走らないとき (headless など) の fallback に回せる。採る前に、使用率がセッション単位なのでキャッシュのキーをセッションで分けられるか (statusline の stdin が session_id を持つか) と、statusline の表示が実態と合っているか (2026-09-25 にユーザーが食い違いを疑っている、未確認) を確かめる。以下の 3 つは推定を直す形を採るときのタスク
- [ ] 占有量の推定を `usage.iterations` の最後の `type: "message"` の段から取るように直す。`iterations` が無い、または `message` の段が無いときは今のトップレベル合計へ戻す
- [ ] 上の実測値の形 (3 段で advisor を挟むもの / 1 段のもの / `iterations` 無し) を `scripts/claude-hooks/tests/test_handoff_sentinel.py` に fixture として入れ、推定値を exact で pin する。合算に戻す変異で赤くなることを確かめる
- [ ] advisor 以外のサーバー側ツール (web_search など) でも `iterations` が複数段になるかを確かめ、同じ扱いでよいかを決める

## 関連

- 発見元: scriptoria のセッション (2026-09-25)。`.cache/usage-probe.py` と `.cache/usage-spike-keys.py` で transcript を実測した (scriptoria 側の書き捨てで、追跡対象ではない)
- `home/.claude/hooks/handoff-sentinel.py` の `_context_tokens`
- ISSUE-67: 同じ推定値を使うしきい値通知が 1 セッション 1 回しか鳴らない件。再通知を入れると、advisor を呼ぶたびの誤発火がそのまま繰り返しになる
- ISSUE-106: F05 が同じ通知文から推定値を落とす。数値が見えなくなっても推定の誤りと誤発火は残る
