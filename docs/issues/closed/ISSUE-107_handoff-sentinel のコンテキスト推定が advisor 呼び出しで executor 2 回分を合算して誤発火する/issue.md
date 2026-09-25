---
status: closed
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

dotfiles のセッション (2026-09-25) でも同じ形を観測した。transcript から引き直した値である。

- 15:34:45Z の assistant エントリ: `iterations` は `message` 463079 / `advisor_message` (`claude-fable-5-1`) 408513 / `message` 465439 の3段で、トップレベル928518は2つの `message` の段の和と一致する。直後の PostToolUse が「推定 928518 tokens」と通知した。実際の占有は最後の `message` の段の465439 (窓の約47%) で、下の「最後の `message` の段から取る」直し方なら鳴らなかった
- 同じセッションの 08:23:41Z にも同じ形があった (213714 + 215704 = 429418、`advisor_message` 199964 は入らない)。しきい値未満だったので鳴っていない
- 対照として、その前のセッションの 07:49:23Z に鳴った「推定 501452 tokens」は `iterations` が `message` 1段だけで、advisor を挟まない本物のしきい値超えだった。直し方を当ててもこちらは鳴る

通知は PostToolUse で鳴るため、advisor を含む応答の直後のツール呼び出しで発火する。推定が占有量のほぼ 2 倍になるので、既定の窓としきい値 (`DEFAULT_CONTEXT_WINDOW_TOKENS` と `DEFAULT_CONTEXT_THRESHOLD_PCT`) のままでも、占有量がしきい値の半分を超えたあたりから advisor を呼ぶたびに誤発火しうる。

## 調べたこと (2026-09-26)

Claude Code 2.1.282のバイナリで、statusline の入力を組む関数と、そこから呼ばれる関数を読んだ。

- statusline の stdin は hook の入力と同じ共通部を持ち、`session_id` と `transcript_path` を含む
- `context_window.used_percentage` は、最後の応答の usage から選んだ段で計算している。`iterations` のうち `advisor_message` と `compaction` を後ろから飛ばし、最初に当たった段が `message` か `fallback_message` で、4つのフィールドが0以上の数、占有量が正のときだけその段を使う。それ以外はトップレベルを使う。harness 自身は advisor による二重計上を受けておらず、statusline の表示は、この Issue で直した推定と同じ段から出ている
- usage を持つ応答を選ぶとき、harness は `<synthetic>` のモデルの応答 (API エラーやレートリミットの告知で、usage は0) を飛ばす。フックは飛ばさないが、PostToolUse の時点で最後の応答はツールを呼んだ本物の応答なので、`<synthetic>` の応答が最後に来ることは無い

9月以降の transcript 5562本で、main スレッドの usage 付きエントリ112840件の `iterations` の形を数えた。

- 1段が112483件、`message`・`advisor_message`・`message` の3段が235件、`message` の2段が19件、`iterations` 無しが86件、空の配列が17件だった
- 複数段のエントリは、どれもトップレベルが `message` の段の和になっていた。`message` の2段は advisor を呼んだ応答で、advisor の段が記録されていなかった
- `server_tool_use` の値が正のエントリは0件で、advisor 以外のサーバー側ツールが段を増やす形は観測されなかった

直したあとの推定を同じ母集団 (数えた時点で113225件) へ当てると、「最後の `message` の段、無ければトップレベル」という単純な規則と全件一致した。推定がトップレベルと違ったのは269件で、トップレベルは推定の1.949倍から2倍だった。

## タスク

- [x] transcript からの推定を直すか、harness の使用率を使うかを決める。statusline は stdin で `context_window.used_percentage` を受け取っており (`home/.claude/statusline-command.sh`)、レートリミットは同じ stdin の値を statusline がキャッシュへ書いて hook が読む経路が既にある (`handoff-sentinel.py` の `_rate_limits_path`)。使用率を同じ経路で渡せば、サーバー側ツールごとの場合分けと窓サイズの決め打ちが要らなくなり、transcript からの推定は statusline が走らないとき (headless など) の fallback に回せる。採る前に、使用率がセッション単位なのでキャッシュのキーをセッションで分けられるか (statusline の stdin が session_id を持つか) と、statusline の表示が実態と合っているか (2026-09-25 にユーザーが食い違いを疑っている、未確認) を確かめる。以下の 3 つは推定を直す形を採るときのタスク
      推定を直す形を採った (2026-09-26)。使用率は直した推定と同じ段から計算されているので、キャッシュ経由で受け取っても分子は変わらない。違いは窓の大きさだけで、statusline が走らない経路の fallback には推定を直す作業がそのまま要る。セッションごとのキャッシュを足すと、ISSUE-67 が挙げる state の後始末の問題も広がる。窓の大きさの決め打ちは、しきい値の見直しと一緒に扱うよう ISSUE-67 へ書いた
- [x] 占有量の推定を `usage.iterations` の最後の `type: "message"` の段から取るように直す。`iterations` が無い、または `message` の段が無いときは今のトップレベル合計へ戻す
      選び方は harness に揃えた (「調べたこと」節)。`fallback_message` の段も数え、`compaction` の段も飛ばす。飛ばさない段に当たったらそこで決め、それより前は探さない
- [x] 上の実測値の形 (3 段で advisor を挟むもの / 1 段のもの / `iterations` 無し) を `scripts/claude-hooks/tests/test_handoff_sentinel.py` に fixture として入れ、推定値を exact で pin する。合算に戻す変異で赤くなることを確かめる
      `message` の2段と空の配列も足した。推定値は、しきい値を100%にして窓を推定値ちょうどにすると鳴り、1つ増やすと鳴らないことで pin した。合算に戻す変異のほか、最初の段から探す、飛ばす型や数える型を減らす、段の値の検証を外すなど12種の変異を1つずつ入れ、すべて狙ったテストが赤くなった
- [x] advisor 以外のサーバー側ツール (web_search など) でも `iterations` が複数段になるかを確かめ、同じ扱いでよいかを決める
      観測された複数段は advisor の呼び出しだけだった (「調べたこと」節)。harness もツールで場合分けせず段の型で選んでいるので、同じ扱いにした

## 関連

- 発見元: scriptoria のセッション (2026-09-25)。`.cache/usage-probe.py` と `.cache/usage-spike-keys.py` で transcript を実測した (scriptoria 側の書き捨てで、追跡対象ではない)
- `home/.claude/hooks/handoff-sentinel.py` の `_context_tokens`
- ISSUE-67: 同じ推定値を使うしきい値通知が 1 セッション 1 回しか鳴らない件。再通知を入れると、advisor を呼ぶたびの誤発火がそのまま繰り返しになる
- ISSUE-106: F05 が同じ通知文から推定値を落とす。数値が見えなくなっても推定の誤りと誤発火は残る
