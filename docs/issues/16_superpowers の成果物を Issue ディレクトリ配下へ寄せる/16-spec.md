# Issue 単位で成果物を束ねる置き場規約の設計

## 背景と目的

作業の記録が 3 系統に分かれていて、互いに参照が無い。Issue 本体は `docs/issues/<NNN>_<title>/` に、brainstorming が書く設計は `docs/superpowers/specs/` に、writing-plans が書く実装計画は `docs/superpowers/plans/` にある。Issue を `closed/` へ移しても spec と plan は元の場所に残り、Issue 単位で作業の全体を追える状態になっていない。

相互リンクは双方向とも 0 件である。リンクを張る運用に切り替える案もあるが、リンクは人手なので張り忘れが検出できない。成果物を Issue ディレクトリ配下へ置けば、参照は「同じディレクトリ」になりリンク自体が不要になる。張り忘れが原理的に起きない形に構造を変えるのが本設計の狙いである。

加えて本規約は dotfiles 固有にしない。他の個人プロジェクトでも同じ形を使いたいが、クライアントワークでは流儀が異なるので採用しない選択肢も要る。規約の実体を再利用可能な skill に置き、プロジェクト側にはポインタ 1 行だけを置く 2 層構成にする。

## 確定した設計判断

- spec と plan の両方を Issue ディレクトリ配下へ寄せる。close 時の `git mv` は配下の全ファイルを同一コミットで動かすため、Issue とその設計・計画が原子的に移動する。
- ファイル名は `<NNN>-spec.md` と `<NNN>-plan.md` とする。番号を前置する理由は sdd の workspace 名が plan ファイルの basename から導出されるためで、`plan.md` にすると全 Issue の workspace が `.superpowers/sdd/plan/` へ集中する。これは上流 superpowers が plan ごとのサブディレクトリ化で構造的に潰したばかりの衝突であり、こちらで再現する必要はない。副次的な利点として、期待されるファイル名がディレクトリ名の純粋関数になる。
- 出力先の変更は skill の fork ではなくプロジェクト CLAUDE.md による上書きで行う。上流の writing-plans と brainstorming はどちらも既定パスの直後に「ユーザー設定が既定を上書きする」旨を明記しており、上書きは仕様どおりの経路である。fork は更新追随のコストを恒久的に負う。
- `.superpowers/sdd/` は Issue ディレクトリ配下へ入れない。上流 skill が「plan が所有する git-ignored な作業領域であり、最終レビュー clean 後に削除せよ、git history が記録である」と規定する中間生成物であり、追跡ディレクトリの中に `*` を書いた `.gitignore` の穴を空ける価値がない。
- 既存の成果物は Issue #15 に 1 対 1 で対応する 2 件だけを移し、残り 12 件は `docs/superpowers/archive/` へ退避する。遡及起票は行わない。採番は max+1 なので遡及 Issue は最新番号を得るが中身は 2026-06 から 07 の古い作業になり、番号順と時系列が食い違う。また実際には存在しなかった「起票から作業へ」の因果を偽装することになる。
- 検出は移植可能な 1 段のみとする。config-guard へのモジュール追加は行わない。全プロジェクトで検査が完全に同一になり、実装が 1 つで済む。
- 起票のタイミングは spec を書き出す直前に固定する。brainstorming の対話フェーズは Issue を必要としない。その時点ではタイトルもスコープも未確定であり、探索の結果「作らない」と決まった場合に空の Issue が残る。
- `dev-workflow:in-repo-issue` の `SKILL.md:13` は書き換える。当初は「補助資料を任意として汎用的に規定しており、本規約はその具体化にあたるため矛盾しない」と判断したが、実際には同行が `plan.md` という literal のファイル名を挙げており、本規約が名指しで衝突すると否定した名前そのものだった。汎用的な規定を持つことと、特定のファイル名を挙げることは別である。命名をプロジェクト規約に委ねる汎用的な表現へ書き換えることで解決した。

## 調査で確定した一次情報

2026-08-01 から 02 にかけて、dotfiles は `7295a71`、claude-plugins は `19ed74a`、superpowers は 6.2.0 で実測した。

上流 skill の規定。

- writing-plans は `SKILL.md:18` で保存先を規定し、`:19` に「User preferences for plan location override this default」を持つ。
- brainstorming は `SKILL.md:29` と `:107` で保存先を規定し、`:108` に「User preferences for spec location override this default」を持つ。
- subagent-driven-development は作業領域を plan ごとのサブディレクトリと規定し、フラット配置を古いパスとして明示的に否定している。workspace 名は補助スクリプト `sdd-workspace:31` の `basename "$plan" .md` で決まる。同スクリプトが `.superpowers/sdd/.gitignore` に `*` を書く。
- `docs/superpowers/` へ書き込む skill は brainstorming と writing-plans の 2 つだけである。

Issue ディレクトリの規約。

- `dev-workflow:in-repo-issue` は `SKILL.md:13` で「補助資料 = 同ディレクトリ内 `plan.md` / `notes/<name>.md` (任意)」を既に規定している。`spec.md` への言及は無い。
- close はディレクトリ丸ごとの `git mv` で行い、配下の補助資料も同一コミットに入る。reopen は逆方向の `git mv` で番号を維持する。
- 採番は highwatermark を使わず、全ブランチ横断の max+1 を毎回計算する。実測で MAX=16 / NEXT=17。
- Issue #10 が実際に issue ディレクトリ直下へ `plan.md` を置いた前例がある（`d1beca4`、クローズ時に削除）。現存する 16 件の Issue ディレクトリはすべて `issue.md` 単独である。

成果物と Issue の対応。

- plan と spec は 7 テーマすべてで 1 対 1 に対応し、各対は同一コミットで導入されている。
- Issue に対応が付くのは 4 ファイル（2 テーマ）のみ。markdown-link-check が Issue #15 に 1 対 1、config-drift-guard が Issue #1 と #2 の両方にまたがる。残る 10 ファイル（5 テーマ）に対応 Issue は無い。
- 導入コミットの subject に現れる括弧内の番号は PR 番号であって Issue 番号ではない。対応関係の判定でこれを取り違えると、存在しない対応を作ってしまう。

`.superpowers/sdd/` の実態。

- 107 ファイル、1,501,134 バイト（1.43 MiB）。フラット直下 53 件、`archive-session-handoff/` 41 件、`2026-07-31-markdown-link-check/` 13 件の混在で、上流規約に従うのは最後の 1 つだけである。
- 名前衝突は実害を出している。フラット直下の `task-1-brief.md` は symlink-pairs plan のもので、2 日前の nvim-contrast-palette plan の同名ファイルは上書きされて現存しない。
- 容量の大半を占める `review-*.diff` の参照先 SHA は、squash merge により大半が HEAD から到達不能である（サンプル 3 件中 2 件）。オブジェクト自体は gc 前なのでローカルには残っている。

再利用を阻む制約。

- claude-plugins は PRIVATE、dotfiles は PUBLIC である。pre-commit の外部 repo 参照は dotfiles の CI で clone 認証に詰まる。
- `CLAUDE_PLUGIN_ROOT` は plugin の hooks.json と MCP 設定内でのみ展開され、シェルには export されない。両リポジトリに使用例は 0 件。
- 絶対パスの直書きは gitleaks の macos-user-path ルールが弾く。
- claude-plugins には `.pre-commit-hooks.yaml` も実行可能スクリプトも CI も無い。skill 配下の非 SKILL.md ファイルの前例は `in-repo-issue/templates/issue.md` 1 件のみで、`cp` による vendoring を導線としている。
- プロジェクト単位で skill の有効・無効を宣言する公式機構は `enabledPlugins`（plugin 単位の明示列挙）だけである。SKILL.md の frontmatter は name / description / allowed-tools の 3 つのみで、条件付き有効化に使えるフィールドは存在しない。既存の「profile が無ければ動かない」skill 群は、harness の機能ではなく SKILL.md 本文の散文で停止条件を実現している。
- config-guard を他プロジェクトで動かす障壁は Python ではない。zero-dep であり system python3 に PYTHONPATH を通すだけで完走する。真の障壁は `scan()` が無条件に `home/.claude/settings.json` を読む dotfiles 固有のハードコードで、他リポジトリを渡すと例外で落ちる。

移行で切れる参照。

- `2026-07-03-session-handoff-design.md` を指す参照が 2 件ある。`home/.claude/hooks/handoff-sentinel.py:8` の Python docstring 内と、`scripts/handoff-sentinel/README.md:5` のバッククォート囲みで、どちらも Markdown リンク記法ではないため Issue #15 の相対リンク検査では捕捉できない。
- 他の 13 ファイルに inbound 参照は無い。

## アーキテクチャ

規約の実体を skill に 1 箇所だけ持ち、プロジェクト側にはポインタを置く。

```
claude-plugins                              各プロジェクト
────────────────────────────                ──────────────────────────────
plugins/dev-workflow/skills/                CLAUDE.md
  issue-scoped-artifacts/       ◀ポインタ─    「spec / plan は skill の規約に従う」
    SKILL.md
      ・置き場と命名の規約                   .pre-commit-config.yaml
      ・起票タイミング                         language: fail の hook
      ・採用手順                             docs/issues/<NNN>_<title>/
      ・移行手順                               issue.md
      ・sdd の basename 注意                   <NNN>-spec.md
                                               <NNN>-plan.md
```

skill は呼ばれなければ効かない。したがって成果物の出力先を変える常設ルールは user instruction として context に存在しなければならず、プロジェクト CLAUDE.md のポインタは利便ではなく機構上の必須要素である。そして必須であることが、そのまま opt-in の実現になる。1 行足せば採用、足さなければ不採用となり、クライアントワークでは何もしなくてよい。

skill を `in-repo-issue` に統合せず独立させる理由は責務の分離である。`in-repo-issue` は Issue の起票・更新・クローズを担い、成果物の置き場は別の関心事である。分けておけば「Issue 管理は使うが superpowers は使わない」プロジェクトが規約のノイズを受けない。

## 規約

Issue ディレクトリ配下に置くファイルは次のとおり。

| ファイル | 書き手 | 必須 |
| --- | --- | --- |
| `issue.md` | in-repo-issue | 必須 |
| `<NNN>-spec.md` | brainstorming | 任意 |
| `<NNN>-plan.md` | writing-plans | 任意 |
| `notes/<name>.md` | 手動 | 任意 |

`<NNN>` は Issue ディレクトリ名の先頭の番号と一致させる。`notes/` は `in-repo-issue` の既存規定をそのまま踏襲する。

プロジェクト CLAUDE.md に置くポインタは 1 行とし、規約の手順と理由は書かず、成果物の名前だけを示す。名前を含めるのは、skill が起動しなかった場合に番号前置が失われる経路を塞ぐためであり、同じ literal は既に同リポジトリの `.pre-commit-config.yaml` の entry メッセージに存在するので新しい drift 源にはならない。推奨文面は skill が採用手順の一部として提示し、各プロジェクトはそれを写す。

## 検出

`.pre-commit-config.yaml` に `language: fail` の hook を 1 本置く。skill が YAML スニペットとして配り、各プロジェクトの `.pre-commit-config.yaml` にあるコピーが操作上の実体になる。

捕捉する失敗モードは「CLAUDE.md の上書きが効かず、成果物が上流 skill の既定パスへ落ちる」ことである。既定パスは `docs/superpowers/plans/` と `docs/superpowers/specs/` の 2 つしか存在しないため、この 2 パスに現れたファイルを弾けばこの失敗モードは漏れなく捕捉される。

`language: fail` を選ぶ理由は移植性である。`ENVIRONMENT_DIR` が None で `install_environment` が no_install なので環境構築が発生せず、Python も Node も要らない。private リポジトリの clone 認証も、絶対パス直書きによる gitleaks 抵触も回避できる。

この検査は Issue ディレクトリ配下のファイル名違反を見ない。`spec.md` のような番号なしの名前も、`15_` 配下に置かれた `16-spec.md` も通過する。ファイル名まで検査するにはリポジトリ固有のロジックが要り、全プロジェクトで同一という性質を失う。今回はこれを既知の限界として受け入れる。

## 移行

`docs/superpowers/plans/` と `docs/superpowers/specs/` を撤去する。

- markdown-link-check の plan と spec を `docs/issues/closed/15_<title>/15-plan.md` と `15-spec.md` へ `git mv` する。
- 残る 6 テーマ 12 ファイルを `docs/superpowers/archive/` へ `git mv` する。ファイル名は現状のまま平らに置く。
- config-drift-guard を archive へ送るのは、1 テーマが Issue #1 と #2 の両方にまたがりどちらへ置くかが人の判断になるためである。判断を要する対応付けは、忘れが検出できない人手のリンクと同じ性質を持つ。

移行で切れる 2 件の参照を新しいパスへ更新する。どちらも Markdown リンクではないため既存の検査では守られず、`git grep` による不在確認で担保する。

一方で移行する 14 ファイル自身が持つ旧パスへの平文参照 8 箇所は書き換えない。性質が 2 種類あり、`設計 spec: docs/superpowers/specs/...` のような生きたポインタと、`git add docs/superpowers/specs/...` のような当時のコマンド転記や当時のファイル内容の転記が混在している。後者を書き換えると記録が事実と食い違い、前者だけを選んで直すには 1 行ずつの人の判断が要る。判断を要する対応付けを避けるという本設計の方針をここでも通す。代わりに `docs/superpowers/archive/README.md` を新設し、文書内のパスが移行前の構成を指したままであることと、現行の規約の canonical がどこにあるかを述べる。

移動対象が持つ Markdown リンク記法はすべてコードフェンス内とインラインコード内にある。`markdown_links` はコード領域を除外するため、移動で基準ディレクトリが変わっても判定は変わらない。

`.superpowers/sdd/` は削除する。追跡外なのでコミットには現れない。削除により次回の plan 実行時に `sdd-workspace` が `<NNN>-plan/` 形式のサブディレクトリを新規生成するため、上流最新形式への追随も同時に完了する。

削除に伴い `.superpowers/sdd/.gitignore` も消える。現在 `.superpowers/` が git から隠れているのはこのファイルだけによるものなので、リポジトリの `.gitignore` に `.superpowers/` を加える。brainstorming の visual companion が書く `.superpowers/brainstorm/` はそもそも ignore されておらず、この追加で同時に塞がる。姉妹リポジトリの claude-plugins は既に `.superpowers/` を ignore しており、揃う形になる。

## 作業の順序

claude-plugins への skill 追加を先に行い、dotfiles の変更を後に行う。CLAUDE.md のポインタが指す skill が存在しない期間を作らないためである。

claude-plugins には skill 追加の前に PR #5 を処理する。この PR は in-repo-issue の採番を全ブランチ横断にする 1 ファイル 9 行追加 4 行削除の修正で、MERGEABLE かつ CLEAN のまま 2026-07-23 から開いている。marketplace が directory ソースでこの作業ディレクトリそのものを指すため、現在 live な採番挙動はこの未マージブランチのものである。main を checkout すると挙動が退行する状態にあり、新しい skill を足す前に main を live に一致させる。

claude-plugins 側に Issue は起票しない。設計は dotfiles の Issue #16 が所有する 1 つであり、claude-plugins 側はその実装 PR として出す。規約の趣旨とも一貫する。

## 検証方法

skill には自動テストの仕組みが無いため、実測で担保する。

- 検出 hook。dotfiles 上で live smoke を行う。`docs/superpowers/specs/` 配下のファイルを staged にした状態で exit 1 と違反ファイル名の表示を確認し、規約に従ったファイルのみの状態で exit 0 を確認する。後者を確認しなければ「何をしても落ちる hook」と区別できない。scratch リポジトリでの事前検証では両方を確認済みで、日本語ディレクトリ名も問題なく通ることを確認した。
- 規約そのもの。dogfooding で確かめる。本 Issue の spec と plan が `docs/issues/16_<title>/16-spec.md` と `16-plan.md` に着地することが最初の実例になる。
- 移行。`config-guard scan` の `markdown_links` が相対リンク切れを検出する。Markdown リンクではない 2 件は `git grep` で旧パスの不在を確認する。
- 移行の完全性。`docs/superpowers/plans/` と `docs/superpowers/specs/` が存在しないこと、および archive に `.md` ファイル 12 件と `README.md` 1 件の計 13 件が揃っていることを確認する。

## 今回やらないこと

- 既存 12 ファイルへの遡及 Issue 起票。番号順と時系列が食い違い、実在しなかった因果を偽装するため行わない。
- Issue ディレクトリ配下のファイル名検査。移植可能な 1 段構成という判断は維持する。skill が配るスニペットは全プロジェクト共通の floor であり、ここを崩さない。そのうえで dotfiles では config-guard にファイル名の検査を足す余地がある。検査対象が `issue-scoped-artifacts` hook (`docs/superpowers/`) と重ならないため literal の重複は起きず、CI は既に config-guard をフルスキャンしているので CI 費用も増えない。規約のうち実害を防いでいるのは `<NNN>` の一致であって「`docs/superpowers/` に置かないこと」ではないため、この検査には別途価値がある。[Issue #17](../17_Issue%20ディレクトリ配下の成果物ファイル名を%20config-guard%20で検査する/issue.md) として起票済み。
- config-guard の repo 非依存化。`scan()` の dotfiles 固有ハードコードは本設計の検出方式では不要になったため、別の必要が生じるまで触らない。
