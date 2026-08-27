---
status: open
---

# feat(ci): スクリプトと設定に埋め込んだ他言語を構文検査する

## 背景

CLAUDE.md は「シェルスクリプトに他言語を埋め込むときは、埋め込み側の構文検査をテストで
pin すること」を定めている。理由も同じ行にあり、埋め込み言語の構文エラーはホスト言語の
検査を素通りするため、実行するまで露見しない。

現在このルールが適用されていない箇所が 2 つある。どちらも実測で確定させた。

### 1. `herdr-agent-state.sh` の埋め込み Python 75 行

このファイルは SessionStart フックとして毎回走り、本体は `python3 - <<'PY'` へ渡す
75 行の Python である。隔離コピーで変異注入した結果:

| 検体 | shellcheck |
| --- | --- |
| 変更なし | GREEN |
| 埋め込み Python の構文を壊す | **GREEN** |
| ホスト側シェルの構文を壊す (対照) | RED |

対照が RED になるので shellcheck 自体は生きている。埋め込み Python を見ていないだけである。
`scripts/claude-hooks/tests/` にもこのファイルを対象にしたテストは無い (テスト 5 本はすべて
`.py` フック用)。つまり検出網が 1 枚も無い。

現状の 75 行は `compile()` を通る。壊れているのではなく、壊れても気づけない状態にある。

このファイルには `managed by herdr; reinstalling or updating the integration overwrites
this file` と書かれている。外部ツールが不定期に上書きするため、上書き後の版が壊れる経路が
実在する。しかも SessionStart で走るので、壊れても Claude Code のセッションは開始され、
herdr のペイン状態が更新されないという形でしか現れない。

CLAUDE.md が併記する手当て (ヒアドキュメントを変数へ受けて テストから source する) は、
このファイルには使えない。herdr が上書きするので書き換えても次の更新で失われる。
検査はテスト側で本文を切り出す形になる。

### 2. `settings.json` の SessionStart inline shell

`home/.claude/settings.json` の SessionStart には、外部スクリプトではなく JSON の文字列として
直接書かれたシェルが 1 本ある。JSON 文字列の内側でコマンド置換を行い、その出力がそのまま
JSON の値になる形である。

config-guard はこの文字列を読んでいる (`settings_invariants.py` が hooks を走査し、
絶対パスの混入を検出する) が、シェルとしての構文は見ない。`shellcheck` / `bash -n` /
`sh -n` を呼ぶ箇所は config-guard に 0 件である。

### 手当ての実現可能性は確認済み

どちらも検査器が判別能力を持つことを実測した。

- 埋め込み Python: ヒアドキュメントを切り出して `compile()` に掛けると、現状は OK、
  変異版は SyntaxError になる
- inline shell: `bash -n` に掛けると、8 本の hook command すべてが rc=0、
  クォートを 1 つ落とした変異版だけ rc=2 になる

## タスク

- [ ] 検査対象の集合を決める。`.sh` 内のヒアドキュメント本体と `settings.json` の
      hooks.command を対象にするか、より広く取るか
- [ ] ヒアドキュメントの切り出し規約を決める (開始と終了の判定。`<<'PY'` のような
      クォート付きデリミタに限るか、変数展開ありの形も対象にするか)
- [ ] 実装前にテストで仕様を表現する
- [ ] 変異注入 3 種で pin する (検査対象を壊す / 検査機構を壊す / 取り付けを外す)
- [ ] 機構が対象集合のどこまでを覆うかを数える
- [ ] 埋め込み言語の種類が増えたときに検査が追随するか決める
      (現在の対象は Python 1 種類だが、herdr の更新で変わりうる)

## 関連

- ISSUE-30 が「Markdown 内のシェルスニペットを構文検査する」を扱う。根は同じ
  「埋め込み言語が検査網の外」だが、対象が逆向き (Markdown 内のシェル vs スクリプトと設定内の
  他言語) で、必要な機構も違う。ISSUE-30 はフェンス走査の規約を要求するため ISSUE-39 に
  依存するが、本 Issue はヒアドキュメントの切り出しと JSON の読み取りで足りるので独立して
  着手できる
- ISSUE-39 が config-guard の Markdown フェンス走査を 1 実装へ寄せる。本 Issue は
  フェンスを扱わないので依存しない
- ISSUE-26 が Claude Code フックの共通基盤を扱う。`herdr-agent-state.sh` は
  `scripts/claude-hooks/` の対象に入っておらず (Python フック 4 本のみ)、
  取り込むかどうかは同 Issue の範囲と重なる
