---
status: open
---

# fix(hooks): 注入されなかった handoff が無音で失われる 3 経路を塞ぐ

## 背景

2026-09-11 に、別リポジトリ (PRIVATE) のセッションで引き継ぎが 1 本失われた。
`.cache/handoff.md` が存在するのに SessionStart が注入せず、ユーザーが明示的に
「handoff から再開する」と言わなければ前セッションの内容は丸ごと消えていた。

`home/.claude/hooks/handoff-sentinel.py` の `_inject_handoff` は fail-closed で、
provenance に記録した内容ハッシュと一致する handoff.md だけを注入する。この設計自体は
正しく、ISSUE-58 が扱う prompt injection 防御の一部である。問題は失敗したときに何も
残らないことにある。

## 何が観測されていないか

`_inject_handoff` には `return None` で抜ける経路が 3 つあり、いずれも痕跡を残さない。

| 経路 | 注入 | `.unread` の最終状態 | 気づけるか |
| --- | --- | --- | --- |
| record 未実行 | されない | 書かれない | 無音 |
| ハッシュ不一致 (record 後に本文を書き換えた) | されない | 書かれない | 無音 |
| rename 失敗 (OSError) | されない | 書かれない | 無音 |
| 注入後そのセッションがツールを使った | される | 消える (読んだ証跡) | 告知なし (正常) |
| 注入後ツール 0 回で終了 | される | 残る | 次セッションが告知 |

ISSUE-80 が作った `.unread` 機構は `_mark_unread` が注入成功後にしか書かないので、
上の 3 行にはセーフティネットが掛からない。ISSUE-80 が塞いだのは「消費されたが読まれ
なかった」で、本 Issue が扱うのは「そもそも消費されなかった」である。同じ関数の裏表に
あたる。

失敗が沈黙で返る点も同型で、区別できる情報がどこにも出ない。

- フックを素で叩いても exit 0 で無出力。「handoff が無い (正常)」と「有るが弾かれた」を
  区別しない
- 書いた側のセッションは既に終わっているので気づけない
- 読む側のセッションは「引き継ぎが無かった」としか見えない

## provenance の有無を判定に使わないこと

調査中に、別リポジトリのセッションが「provenance が無い = record 漏れ」と読んで誤った
対照を組んだ。`prov.unlink` は `handoff.rename` の成功後にしか走らないので、provenance の
不在は「record 未実行」と「正常に消費された後」の両方と整合する。dotfiles 自身も
provenance を持たないまま正常に注入されている。

一方でハッシュ不一致と rename 失敗はどちらも unlink の手前で `return None` するため
provenance が残る。したがって provenance の有無は原因の切り分けには使えるが、
異常の検出には使えない。

## 決めたこと

### probe の述語は `.cache/handoff.md` の存在単独

注入に成功していればフックが `handoff-consumed-<UTC>.md` へリネームするので、元の名前の
まま残っていること自体が「書かれたが注入されていない」を意味する。上の 3 経路をこの 1 つの
述語が過不足なく覆い、正常に消費された後を誤検出しない。原因の切り分けは detail へ
provenance の有無を添えれば足りる。

### 置き場は guard-health の probe 登録簿

SessionStart で既に走っており「読めなかったことを告げる」のが責務なので remit に合う。
既存の probe と同じ層に収まり、新しい配線を要さない。

## 決めていないこと

### hook の実行順に依存しないか

compact や resume でも SessionStart は再発火する (matcher が全開始理由を覆い、
`handle_session` は source を見ていない)。skill が handoff.md を書き出した直後に compact が
起きると、同一セッションで注入・消費が走る。

このとき probe が誤検出しないかは、`handoff-sentinel.py session` と `guard-health.py` の
実行順に依存する。settings.json の配列では前者が先にあるが、同一 matcher の複数エントリが
配列順に実行される保証は未確認である。並行実行なら compact のたびに誤検出が出る。

### 書き出しと record を 1 コマンドに閉じるか (上流への委譲)

手順が 2 つに分かれている限り「本文は書いたが record を忘れた」は成立し続ける。書き出し
ヘルパが record まで含めて完結し、後編集の経路も同じヘルパを通れば構造的に消える。

ただし `session-handoff` skill の canonical は agentic-coding-tools にあり、このリポジトリ
では直せない (ISSUE-77 が同じ制約を記述している)。加えて ISSUE-58 が `record` の呼び出し元を
skill へ限定する機構を検討中で、nonce 案とヘルパ案は同じ場所を触る。委譲の前に両者の
関係を決める必要がある。

## タスク

- [ ] hook の実行順が保証されるかを対照付きで測る。並行なら probe の述語に補正が要る
- [ ] `guard_probes.py` へ probe を足す。述語は `.cache/handoff.md` の存在単独とし、
      detail に provenance の有無を添える
- [ ] 変異注入で pin する。3 経路それぞれで赤くなること、正常に消費された後で沈黙すること
      の両方を見る
- [ ] 書き出しと record を 1 コマンドに閉じる案を上流へ委譲するか決める。ISSUE-58 の
      nonce 案との関係を先に整理すること

## 関連

ISSUE-80 が「消費されたが読まれなかった」経路を扱い `.unread` 機構を作った。本 Issue は
その裏返しで、同じ `_inject_handoff` の失敗側を扱う。あちらのセーフティネットが本 Issue の
3 経路へ届かないことが起票の理由にあたる

ISSUE-58 が同じ provenance を prompt injection の面から扱う。`record` の呼び出し元を
限定する機構を検討しており、本 Issue の上流委譲案と同じ場所を触る。どちらを先に決めるかで
設計が変わる

ISSUE-77 が `session-handoff` skill の説明と実装の乖離を扱う。上流が直せない制約と、
pin を上げて `apm install` を通すまで手元へ届かない経路は本 Issue の委譲案にも同じく効く

Issue 26 が Claude Code フックの共通基盤を扱う。本 Issue が足す probe は state を増やさない
が、必須フック検査へ SessionStart 側を入れるかの判断は同 Issue と ISSUE-58 が持つ
