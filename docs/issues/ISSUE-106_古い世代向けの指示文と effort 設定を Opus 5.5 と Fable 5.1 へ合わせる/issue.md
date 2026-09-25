---
status: open
---

# agent: 古い世代向けの指示文と effort 設定を Opus 5.5 と Fable 5.1 へ合わせる

## 背景

2026-09-24 のセッションで `/claude-api prompt-audit` を dotfiles のプロンプト面へ当てた。対象は常時ロードの `home/.claude/CLAUDE.md` と `CLAUDE.md`、`home/.claude/references/`、`home/.claude/rules/`、`home/.claude/settings.json`、hook がモデルへ渡す文面。対象モデルはメインセッションの Claude Opus 5.5 と、`home/.claude/CLAUDE.md` が subagent に指名する Claude Fable 5.1 とした。

見つかったのは、thinking を切れた世代や装飾が多かった世代に合わせて書いた指示と、前の世代で最適だった設定である。今のモデルでは効かないか、ハーネス側の指示と逆向きになっている。目的は特定の古い指示を直すことで、行数を減らすことではない。references の経緯の記述と、実際に踏んだ失敗への規範は、監査で意図して残した。

根拠は Claude API skill (Claude Code 2.1.280 同梱) の `shared/prompt-audit.md` と、`shared/model-migration.md` の Opus 5.5 / Fable 5.1 の節。

## 着手前に確認すること

- 常時層の予算 (`scripts/config-guard/src/config_guard/instruction_budget.py`) は、起票したブランチで実態に約 500B の余白を残す値へ下げた (2026-09-25 のユーザー判断)。反映で常時層が増えるときは config-guard の pytest で予算の検査を通し、超えるなら `BUDGET_RAISES` へ記録する
- 行番号は起票時点の作業ツリーのもの。置換前の文面で引き直すこと
- 提案差分は finding ごとのパッチとして `.cache/prompt-audit/F01.patch` から `F13.patch` に置いた (全部をまとめたものは `all.patch`)。起票時点の作業ツリーに `git apply --check` で当たることを確認済み。作業ツリーが変わったら `python3 .cache/prompt-audit/make_patches.py` で作り直す。置換前の文面がちょうど 1 回見つからない finding はそこでエラーになって止まる。`.cache/` は追跡外なので、消えていたら下の記述から書き直す

## 指摘と直し方

### `home/.claude/CLAUDE.md`

- F01 (179 行目)「Claude Codeの言語設定に忠実に、しかし思考能力は落とさないこと」。thinking が常にオンのモデルで深さを確実に動かせるのは effort で、散文での指示は効き方が不確か (移行文書は、思考を減らしたいなら散文より先に effort を下げるよう勧めている)。2025-11 に最初の CLAUDE.md を作った時点から在る行。口調で中身が薄まらないという目的だけを残し「言語設定の口調は文体にだけ効かせ、技術的な正確さと検証の深さは口調に引きずられないこと」へ置き換える
- F03 (183 行目)「疑問点、懸念点、仕様の不明点がなくなるまでAskUserQuestionで質問すること」。ハーネスの AskUserQuestion の説明は「答えで次の行動が変わる判断にだけ使う」で、この行と逆向き。指示に忠実なモデルほど「なくなるまで」を字義どおりに読み、要らない確認でターンを止める。「読み方で成果物が実質的に変わる疑問点・懸念点・仕様の不明点は、進める前に AskUserQuestion で質問すること。それ以外の細かな判断は自分で決め、置いた前提を報告に書くこと」へ置き換える
- F06 (71 行目)「検索は Grep ツールや素の `grep` ではなく `rg (ripgrep)` を既定にすること。」。メインセッションのツール一覧に Grep は無い。逆に `feature-dev:code-reviewer` のように Grep はあって Bash が無い subagent では、唯一の検索手段を禁じることになる。この repo はマージ前にその code-reviewer を必須にしており、常時ロードの層は subagent にも載る。「Bash で検索するときは素の `grep` ではなく `rg (ripgrep)` を既定にすること」へ置き換える。(2026-09-25 追記) 71 行目は起票したブランチで行ごと削除したので、この項は反映不要になった (ユーザー判断)。Claude Code の既定の検索経路は、メインセッションでは Bash の grep (埋め込みの ugrep を `--hidden --ignore-files -I` 付きで呼ぶシェル関数)、subagent では rg ベースの Grep ツール (`--hidden` 付き) で、どちらも dot 始まりのパスを見る。ignore 配下は別で、grep の関数は `.gitignore` に従い、リポジトリ直下から `grep -r` を叩くと `.cache/` 配下が警告なしの rc 1 / 0 件になる (実測)。Grep ツールも引数に `--no-ignore` を持たないので従うはずである (引数から読んだもので live では確かめていない)。Bash で素の rg を打つと dot 始まりまで落ちるので、規範で rg へ寄せる理由が無い
- F09 (31 行目)「どんなときでもユーザーデータを守るセキュリティを第一に考え、決して手を抜かない」。手を抜くな系の念押しは今のモデルには要らず、残る情報は優先順位だけ。「[MUST GLOBAL] ユーザーデータを守るセキュリティを、他のどの要求よりも優先すること」へ置き換える
- F10 (37 行目)「手動テストによる動作確認を最小限にすることをなにより重要視する」。F09 の「第一」と最上級が 2 つ並び、強調が情報を運ばない。「重視する」へ置き換える。理由の部分 (個人開発でリソースが限られる) は残す
- F11 (42 行目)「あらゆる作業は抽象と具象の視点、局所的と大局的の視点を適度に往復しながら常に全体最適を目指すこと」。「往復しながら」は成功の基準ではなく考え方の手順で、thinking が常にオンのモデルには思考の中身への指図になる。「[MUST] 局所最適で止めず、常に全体最適を目指すこと」へ置き換える

書き換えた行でも強度ラベル (`[MUST GLOBAL]` / `[MUST]`) は変えない。常時ロードの層の予算は、起票時点の見積もりで正味 +68 B (26527 B / 上限 27753 B)。

### `home/.claude/references/delegation.md`

- F02 (「Agent tool と Workflow の許可」の節)。この節は 2.1.229 で測った 2 行 (「Do not call the AgentTool unless the user requested it」と「Do not use workflows or deep-research unless the user requested it」) を現在形で書いている。2.1.280 のバイナリでは、2 行とも文字列どおりには見つからない (対照の `AskUserQuestion` は 48 行に現れる)。代わりに「Do not use the ${mt} tool, workflows, or deep-research unless the user, a CLAUDE.md file, or a skill asks for it」という 1 行があり、許可の出どころとして CLAUDE.md が名指しされている (2026-09-24 実測)。`${mt}` へは `"Agent"` を代入する箇所があるが、スコープは確かめていない。この行がどの条件で注入されるかも未確認。これとは別に、Workflow ツールの説明は opt-in の経路を 5 つ列挙しているが (プロンプト中の ultracode、セッションで ultracode が有効、ユーザー自身の言葉、Workflow を呼ぶよう指示する skill や slash command、名前付きの保存済み workflow)、そこに CLAUDE.md は含まれない。`home/.claude/CLAUDE.md` の恒久許可は残し、この節を 2.1.280 の実態へ直す

### `home/.claude/settings.json`

- F04 `"effortLevel": "xhigh"` (2026-04-10 に high で入り、2026-07-29 に xhigh へ上げた)。xhigh は Opus 4.7 から 4.8 / Fable 5 の世代でコーディングの最適値だった。Opus 5.5 は同じ段でも前の世代より多く考え、xhigh / max は計測で得がある作業に取っておくのが推奨。Fable 5.1 も推奨の出発点は high で、xhigh では長い成果物を thinking で下書きしてから本文で書き直し、出力がほぼ倍になる。週次リミットが実制約なので毎ターンの消費に効く。high を出発点にして、重い作業のセッションだけ上げる

### `home/.claude/hooks/handoff-sentinel.py`

- F05 (292 行目) の通知文にある `推定 {tokens} tokens`。prompt-audit のガイドは残量の数値をモデルへ見せないよう勧めており、Fable 5.1 の移行文書も早すぎる切り上げ (context anxiety) の原因として挙げている。この通知はそもそも切り上げを指示するので、数値はモデルの判断に何も足さない。ユーザーが続行を選んだ後も数値だけが文脈に残る。使用率は statusline が人に見せている
- 数値を落とすと、数値を観測点にしていたテスト 3 本が落ちる (`test_usage3フィールドは合算される`、`test_U2028を含む最新entryも取りこぼさず発火する`、`test_コンテキスト超過と同時なら両方の通知が出る`)。前 2 本は発火の有無へ、3 本目は通知固有の文言へ観測点を移す。合算の検証は、合計がしきい値ちょうどになるデータのおかげで発火の有無だけで保てる。数値を含まないことを pin するテストを 1 本足す
- 作業ツリー外のコピーでパッチを当て、ruff / mypy / pytest (82 件) が通ることを確認した。変異は 4 種を 1 つずつ入れ、それぞれ狙いのテストだけが赤くなった (合算から 1 フィールドを落とす、通知へ数値を戻す、JSONL を `splitlines()` で割る、コンテキスト通知があるとレートリミット側を飛ばす)

### `home/.claude/rules/markdown-practices.md`

- F07 (7 から 9 行目) の強調・区切り線・絵文字・テーブルの禁止。理由の無い禁止の形で、装飾が多かった世代向けの書き方。この rule は `*.md` を Read した時点でロードされるので、ファイルの規約のつもりが会話の応答の書式まで縛る。ファイルに限った理由付きの肯定形として「Markdown ファイルは、レンダリングされない素のテキストで読まれる前提で書く。強調（`**これ**`）・区切り線（`---`）・過剰な絵文字・テーブルは素のテキストでは読みづらいので使わず、構造は見出しとリストで示す」と「README.md などブラウザ等でプレビューされる見込みがあるファイルに限り、テーブル記法を使ってよい」へ置き換える。理由は 9 行目の条件から推定したもので、違っていたら差し替える。10 行目の「順序が必要な場合にのみ Ordered List を使うことを検討すること」も「のみ」と「検討」が噛み合わず、見出しの [MUST] より弱く読める。8 行目と 9 行目は同じ規則を 2 回言っているので、反映するときに 1 文へまとめる
- F08 (14 行目)「強調したい場合を除いて、数字の前後に空白を入れないこと」。指示ファイル群は少なくとも 95 行でこれを破っている (行単位で数えたので実際の箇所数はもっと多い。`home/.claude/CLAUDE.md` の見出し 3 本を含む)。例は規則より強く効くので、この行はモデルへの合図にならない。同じファイルの 22 行目は、静的に検査できる規則を linter へ回すよう求めている。削除するか、採るならファイル群を一括で整形して pre-commit の検査で強制するかを決める。(2026-09-25 追記) 14 行目は起票したブランチで rule から外し、この判断を待つことにした (ユーザー判断)。15 行目「テキスト上の見た目のために文の途中で改行を行わないこと」にも同じ論点 (22 行目との矛盾と、散文だけでは守られないこと) が当てはまるので、同じ判断に含める。強制する形の候補は pre-commit の `language: pygrep` の hook。15 行目は残したので起票したブランチで触った open な文書は結合したが、触っていない references (`delegation.md`・`git-workflow.md`・`host-environment.md`) と ISSUE-46 には文中の改行が残っている

### `CLAUDE.md`

- F12 (26 から 30 行目)。ヒアドキュメントの理由 2 行 (`$(cat <<'EOF')` のアポストロフィの件と、変数で受ければ source で検査できる件) が AppleScript の予約語の行の子になっていて、規則 (26 行目の `IFS read`) から切り離されている。予約語の行も過去形の出来事で、規則になっていない。理由を 26 行目の下へ付け替え、予約語の行は「AppleScript では `path` / `round` を変数名に使わない。予約語と衝突して -1700 / -2741 で落ちる」へ置き換える
- F13 (12 行目)「## [MUST] 必ず守らなければならないルール」。ラベルと見出しが同じことを言うだけで、見出しとして中身を示さない。「## [MUST] このリポジトリでの作業規約」へ置き換える

### 採否を決めるもの (監査で確度が低く、差分を作らなかった)

- L1 `home/.claude/CLAUDE.md` 180 行目「ハルシネーションを極力避けて」。Opus 5.5 は根拠の無い数字や出典を出しにくくなったと文書にあるが、削る害も確認されていない。後半の「わからないことはわからないと言う」は残す
- L2 `home/.claude/CLAUDE.md` 163 から 164 行目の、着手前のテストとブランチ選択。字義どおりに読むと読み取りだけの調査にも掛かる。dotfiles では作業ツリーが live 設定の実体なので、ブランチの切り替えが live 設定を変える。適用範囲を「ファイルを変更するタスク」と書くかどうか
- L3 `home/.claude/CLAUDE.md` 39 行目「拡張性のある設計」。Fable 5.1 は effort が高いと頼まれていない抽象化に寄りやすいと文書にある。同じ行の KISS が釣り合いを取っている
- L4 `home/.claude/CLAUDE.md` 132 から 133 行目と 139 行目の XSS / SQLi / HTTPS / セキュリティヘッダー。モデルの既定の再掲で害は小さい
- L5 `home/.claude/references/premises.md` 19 行目「現状の Claude が…」。どのモデルの観測かが書かれていない。Fable 5.1 の文書も余計なテストや周辺の修正を挙げているので、規範は今も効いている。観測した時期を添えるかどうか
- L6 `home/.claude/settings.json` の `"ultracode": true`。ultracode が注入する「token cost is not a constraint」を、memory の「並列 agent は 3 本まで」が打ち消している。逆向きの指示をモデルが毎回調停している状態。ultracode が他に何を変えるかは未確認
- L7 `home/.claude/CLAUDE.md` のセキュリティ節の先頭「攻撃者が攻撃可能な要素を最小に抑える」は、見出し「攻撃者が使える面を最小に保ち防御を 1 層に頼らない」の言い直しになっている。消すかどうか
- L8 `home/.claude/CLAUDE.md` の canonical 節の検算の項が持つ理由 (「これは二重管理を消す作業がそのまま同型の欠陥を作り…」) は、`home/.claude/references/canonical.md` の「散文を参照へ書き換えたあとの検算」節とほぼ同じ文。冒頭の「手当ての詳細は references が持つ」に従って CLAUDE.md 側の理由を落とすかどうか
- L9 `home/.claude/CLAUDE.md` の pnpm の項から、起票したブランチで `settings.json` の `permissions.deny` を canonical として指す注記を削った。npm / npx の列挙が散文と deny に互いの参照なしで並ぶ。短い参照を戻すかどうか
- L10 references の各節が CLAUDE.md や rules の規範文をほぼそのまま再掲している (`canonical.md`・`observation.md`・`security.md`・`testing.md`)。片方だけ直すと食い違い、起票したブランチでも実際に食い違った。references は規範を名前で参照し、事例と手当てだけを持つ形にするかどうか

コンテキスト閾値 (`DEFAULT_CONTEXT_THRESHOLD_PCT`) の前提の見直しは、同じ機構を扱う ISSUE-67 へ判断材料として移した。

## タスク

- [x] 起票時点の未コミット変更 (tgrep の撤去、CLAUDE.md の整理、Markdown の規範の移設) を先にコミットする
- [ ] F01・F03・F09・F10・F11 を `home/.claude/CLAUDE.md` へ反映し、config-guard の scan と pytest の両方を通す
- [ ] F02 を `home/.claude/references/delegation.md` へ反映する
- [ ] F04 の effort の段を決めて `home/.claude/settings.json` へ反映する
- [ ] F05 を hook とテストへ反映する。ISSUE-67 と同じ関数を触るので、後から入る側も数値を含まないことを pin するテストを残す
- [ ] F07 を反映し、F08 は削除か検査での強制かを決めてから反映する
- [ ] F12 と F13 を `CLAUDE.md` へ反映する
- [ ] L1 から L10 の採否を決め、採るものは同じ PR で直す
- [ ] 文面の変更をモデルの挙動で確かめるかを決める。確かめるなら 1 件ずつ、`empirical-prompt-tuning` skill を名指しで使う
- [ ] 反映が済んだら `.cache/prompt-audit/` を消す

## 関連

ISSUE-67: handoff-sentinel のコンテキスト閾値の通知が再武装しない件。F05 が同じ関数 (`_context_notices`) とテストを触る

ISSUE-107: F05 と同じ通知の推定値が、advisor を呼んだ応答で占有量の約 2 倍になる。F05 で数値を見せなくしても、推定の誤りと誤発火は残る
