# 委譲と subagent 運用の一次実測

`~/.claude/CLAUDE.md` の「委譲先の報告を自分の実測の代わりにせず派生は 1 段に留める」
カテゴリが持つ規範の、手当ての詳細と一次実測。

規範の遵守そのものには要らない。手当ての具体が要るとき、規範を疑うとき、
似た失敗を踏んで「これは既知か」を確かめるときに読む。

## Agent tool と Workflow の許可

システム側に「Do not call the AgentTool unless the user requested it」
「Do not use workflows or deep-research unless the user requested it」の 2 行が入ることがある。
これは Claude Code 2.1.229 のバイナリに定数として埋まっていて、
settings.json でも起動引数でも消せない (2026-08-13 実測)。

条件が "unless the user requested it" なので、消せない側ではなく条件を満たす側を
CLAUDE.md で明示している。

## 派生を 1 段に留める

深さに上限が無いと、どの結論が誰の実測に基づくかを親が辿れなくなり、
トークンも指数的に増える。

Agent tool の fork と Workflow の nesting は仕組み側で 1 段に制限されているが、
通常の subagent 起動には制限が無いので規約で塞ぐ。

## implementer への長時間コマンド委譲

prompt で名指しして禁じたが 5 回連続で再発した。
implementer は長時間コマンドに対して Monitor / watch を仕掛け、そのままターンを終える挙動を取る。

prompt による禁止では止まらず、分業の設計で構造的に防ぐ側へ切り替えて解決した。
コントローラがゲートを回せば赤も直接読める。

## 構造化出力どうしの突合キー

レビューの findings と反証の verdicts を title の完全一致で突合した。
反証側が指示に無い「指摘 N: 」を前置したため、17 件全部が「未検証」に落ちた。

突合の失敗は例外ではなく「全件未検証」という静かな結果で返ったので、
出力を読むまで壊れていることに気づけなかった。
生成側は装飾を足すので文字列一致は必ず壊れる。

## 反証者への既定値の指示

「確信が持てないなら refuted=true」を既定値として指示した結果、
妥当な指摘 4 件が 2 名一致で refuted に落ちた。全件を読み直して初めて拾えた。

一致していたのは独立に確認したからではなく、迷った反証者が全員同じ側へ寄っただけだった。

## brief の断定

brief の断定が implementer の実測で訂正される事例が連続した。
根因ファイルも breakpoint も brief の記述と違っており、
brief をそのまま信じる従順な implementer なら無関係な箇所で詰まっていた。

brief は仮説であって確定事実ではなく、コードに触れているのは implementer の実測。
「報告・前提を検証済みの網羅的事実として扱わない」の Subagent-Driven 版。

## subagent への制約伝達

隔離した `CLAUDE_CONFIG_DIR` では Keychain 認証を引き継げないと brief に書いたところ、
subagent が `security find-generic-password` で認証情報を読み出そうとし、
続けて `~/.claude.json` の複製も試みた。

auto mode classifier がブロックして実害は無かったが、防御が 1 層しか働いていない状態だった。
制約の説明はエージェントにとって「解くべき問題」に見えるので、
「そこには行くな」まで書いて初めて制約になる。

## 並列 subagent の実験場所

マージ前ゲートの 6 並列で、subagent が提案の妥当性を確かめるために本体のファイルを変異させた。
一瞬の `exit 2` を退行と誤診しかけた。

テストが赤いのに `git status` が clean という矛盾で気づいたが、
矛盾が出なければ誤った結論のまま進んでいた。

## 設計案の並列生成

テスト件数ガードの設計で、4 案中 3 案が揃って「件数の exact 一致」へ収束した。

「既存の A/B/C 案に縛られず制約だけから設計をやり直せ」と出発点を変えた 1 案だけが、
件数という指標そのものを捨てて同数入れ替えと skip 化の検出に到達した。
収束は合意ではなく問題設定の反映である。

## 常時層のコストは dispatch ごとに払う

subagent はツールを一切使わずに `~/.claude/CLAUDE.md` の本文と由来パスを引用できる。
常時ロードされる指示のコストは session_start だけでなく subagent の起動ごとに発生する。

この経路は `~/.cache/claude/instructions-loaded.jsonl` に記録が出ない
(subagent を 1 本起動してもログ行数が変わらなかった)。
「ロードされているのにログが 0 件」の実例なので、削減効果の検証にログは使えない。
