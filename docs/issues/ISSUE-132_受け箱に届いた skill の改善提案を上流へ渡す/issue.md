---
status: open
---

# feat: 受け箱に届いた skill の改善提案を上流へ渡す

## 背景

2026-10-21 に受け箱へ届いたまとめのうち、配布している skill (canonical は agentic-coding-tools)、apm 経由の第三者の上流の skill、外部の plugin と組み込みの skill への改善提案をここへ集める。どれも他のリポジトリのセッションの報告で、dotfiles で確かめたことは項目ごとに分けて書く。

### in-repo-issue: 親子のキーを拡張したプロジェクトで Phase E が無音で終わる

報告 (実測): Phase E は frontmatter の `^parent:` と `^children:` を grep する。プロジェクトが frontmatter のキーを別名 (例: `parent_issue:` / `child_issues:`) で持っていると grep は0件を返し、Phase E は「親なし」として無音で終わる。親子のリンクが実在しても伝播の提案が出ない。報告元では同梱の側で親のクローズが済んでいたので実害は無かった。

報告者の提案 (推測): 親子のキー名をハードコードせず、プロジェクトのテンプレートから読む。または `parent` も `children` も見つからないのに frontmatter に `parent` / `child` を含むキーがあれば警告を出す。対象は Phase E と A.6、検索手順の親一覧。

同じ報告で、クローズを feature PR に同梱したあとの Phase C は C.3 の「既に closed」分岐で no-op になり、破綻しなかったことも確かめられている (実測)。skill が同梱節で述べている挙動どおりである。

dotfiles で確かめたこと: skill の frontmatter スキーマは `parent` / `children` を名指しし、「これ以外は持たない」と書いている。報告元のキーはこの規約の外にある。直す向きは2つあり、規約外のキーを検出して知らせる (0件を健全と読ませない) か、キー名を可変にするかで、前者は規約を変えずに済む。

### in-repo-issue: 既存の Issue を抱えた配布先へ検査を後から取り付ける

2026-10-31に仕分けた分で届いた。どれも別のリポジトリのセッションの報告。`issue-id.py` の外部設定は ISSUE-121 が持つ。

- 既に in-repo Issue を運用している配布先へ、`issue-id.py` の検査を後から取り付けた (pre-commit stage に `--check-diff`、commit-msg stage に `--check-text`、CI に `--check-diff --base origin/main`)。既存の違反を残したまま新しく入る違反だけを止められ、staged に違反を仕込んだ対照は rc=1、本物の変更は rc=0、commit-msg も対照で赤・正常で緑だった。取り付けの前の `--check` の全走査では、旧形式のディレクトリ名・他のリポジトリの Issue を裸の数字で書いたメモ・自リポジトリの古い記法・偽陽性の4種で57件あった (実測)
- 「初期化」節は新規プロジェクト向けの手順で、既存の Issue を抱えたまま後から取り付ける経路 (`--check-diff` を使い、`--check` はまだ赤い) が節の中に無い。docstring には書いてあるので、読めば辿り着ける (実測)。報告者の提案: 増分の入口を使うことと、`--check` を backstop にする時期をどう決めるかを初期化の節に足す (ドキュメントのみ)
- `--check-diff --base main` はコミット済みの差分しか見ず、作業ツリーを数えない件は、ISSUE-121 のタスクの「報告された使い方の罠を SKILL.md に書くか決める」にある
- 上流の `.pre-commit-config.yaml` のコメントにある「commit-msg の hook は `always_run: true` が無いと常に skip される」が再現しなかった。pre-commit の4.7.0で使い捨てのリポジトリを作り、本物の git commit で `always_run` の有無を比べたら、どちらでも hook が走ってコミットを止めた (実測)。報告者の提案: 版を添えて測り直す
- 採番が `ISSUE-<N>` へ移ったとき、利用先の置き場の検査が数字始まりだけを Issue ディレクトリとみなしていたので、新形式の配下が黙って検査の外になり、正しく名付けた plan が外に落ちたと誤検出された。件数が増えないことで気づいた (実測)。報告者の提案: 採番の形式の変更を配るときは、利用先に識別子の形を写した検査が無いかを確かめる手順か告知を添える
- 初期化で配る `issue-id.py` は764行あり、追跡下へ入れる前の全文読みが重い (実測)

### in-repo-issue: Issue の外にある写しと参照

2026-10-31に仕分けた分で届いた。どれも別のリポジトリのセッションの報告。

- Makefile の target などが Issue ディレクトリの中のファイルを glob で指していると、Issue を閉じて `closed/` へ移した時点で黙って見失う (実測)。報告者の提案: パスは変数1つにし、クローズの手順の相対リンクの補正と同じタイミングで道具側の参照も grep する
- in-repo Issue を初めて導入し、リリースまでのロードマップのチェックボックスを `closed/` の所在の写しとして置いて、写しと所在の食い違いを CI の検査で赤にした。順序と依存をロードマップと各 Issue の「前提」の両方に書くと起票の直後にもう食い違ったので、依存の canonical をロードマップ1箇所へ寄せた (実測)。報告者の提案: 箱を写しと位置づけて検査で赤にする形を雛形にし、「依存の canonical は1箇所に決める」指針を skill に足す。dotfiles の ISSUE-75 も似た写しの検査を持つ

### session-handoff: 実行中の subagent はセッションを越えて resume できない

報告 (実測): subagent の agent id は前のセッションの中のプロセスにしか届かず、新しいセッションの一覧には出ない。引き継ぎ書に「同じ implementer を resume する」と書いても使えない。報告元は、作業木の未コミットの変更をコントローラが全文読み、テストとゲートを回してから wip でコミットし、残り (変異注入と報告) だけを新しい subagent に渡した。復元先が HEAD になるので変異の復元も安全になった。

報告者の提案: 引き継ぎ書を書く skill に「実行中の subagent はセッションを越えて resume できない。止めた subagent の続きは、新しい subagent 向けの brief として書き残す」を加える。

dotfiles で確かめたこと: 配布されている session-handoff の SKILL.md に subagent と resume への言及は無い。

### session-handoff: cross-session の相手をセッション名で書かせない

2026-10-23に仕分けた分で届いた。

報告 (実測): handoff に書いた cross-session の相手のセッション名が、引き継いだ時点では別の名前になっていた。セッション名はセッションごとに変わる。

報告者の提案: session-handoff の書式で、相手をセッション名で書かせず、「送る直前に ListAgents で引く」と書かせる。

dotfiles で確かめたこと (2026-10-23): 同じ日に、別のリポジトリのセッションから dotfiles の前のセッションへ宛てた返信が、「宛先のソケットが消えていた」としてこのセッションへ届いた。宛先の名前は、前のセッションが依頼したときのものだった。届け先をどう見つけたかは送り手が書いていないので分からない。名前で覚えた宛先が後から使えなくなるという、上の報告と同じ型である。

### pre-merge-quality-gate の simplify: 並列の reviewer を読み取り専用にする

報告 (実測): simplify を、読み取り専用の4観点の reviewer を並列に立てて指摘だけを受け取り、適用は親が行う形で回した。並列レビュー中に本体が書き換わらず、行番号のずれも起きなかった。4本で8件の指摘が返り、うち1件はクライアント側の重複処理を丸ごと消せる根本の直しだった。

2026-10-23に仕分けた分で、別のリポジトリから同じ形の報告が届いた (実測)。マージ前の品質ゲートの4観点を Workflow の pipeline で回し、レビュー役は読むだけに縛って、修正の適用は指揮役だけが行った。検証役が補ったものは ISSUE-133 の「Claude Code の hook と委譲」節に置いた。

### pre-merge-quality-gate: ゲートの順序、増分、CI の待ち方

2026-10-31に仕分けた分で届いた。どれも別のリポジトリのセッションの報告。

- 前回のゲートが CI や別のレビューと並行で走っていた場合、その指摘を直して積んだコミット自体はどのゲートも通っていない。ゲートが見た commit を特定し、HEAD までの増分にゲートを当てると、約600行の増分から確定の指摘が2件出た (実測)。報告者の提案: マージの経路にこの手順を足す
  - 2026-11-11の仕分けで、別のリポジトリから同じ型の報告が届いた。PR を作る前の品質ゲートの所見を直したコミットはゲートを通っていなかったので、merge の前にその増分 (数コミット、約190行) だけへ4観点 (simplify、code-reviewer、boy-scout、E2E 影響) を Workflow で並列に当て直すと、E2E 影響の観点から Important が1件出た。足した UI テストの1行が、要素の外れる向きと逆にしか画面を寄せず、効いていなかった。直したうえで UI テストを回して緑を確かめた (実測)。引き継ぎ書の「HEAD が Ready の前と同じならゲートの Phase 1 を使い回してよい」という前提は成り立っておらず、前のゲートが見たのはその所見を直す前のコミットだった (実測)。報告者の提案は、merge の前の品質ゲートの手順に「前回のゲートが見た sha と、いまの head の差分 (ゲートの直し自体を含む) に Phase 1 を当てる」を明記すること (実測)。仕分けたセッションの解釈: 親の項は2026-10-31に agentic-coding-tools の ISSUE-99 へ渡し済みで、新しいのは「ゲートの直し自体も増分に含める」ことと、引き継ぎ書の使い回しの前提が外れた実例
- push の直後で新しい run が pending のとき、`gh pr checks --watch` は待たずに「no checks reported」で rc=1 で終わった。前の head の run が in_progress でも同じだった (実測)。報告者の提案: CI を待つ手順を、headSha で run を特定して `gh run watch` で待つ形へ置き換えるか、rc=1 と「no checks reported」の組を「まだ始まっていない」と扱う注記を足す。同じ報告で、新しい run を `gh run list --branch <branch> --json databaseId,headSha` で引き、push した commit と一致する run の ID を `gh run watch --exit-status` に渡すと、pending の間も待ち続けて rc 0で終わった (実測)。/goal の条件文に `gh pr checks --watch` を入れた件は ISSUE-133 の「Claude Code の /goal」節にある
  - 2026-11-11の仕分けで、別のリポジトリから、run が登録される前は空が返るという報告が届いた。`pull_request` だけで起動する CI では、push しただけでは run が登録されず、PR を作った直後の `gh run list --commit <SHA>` は `[]` だった (実測)。CI を待つスクリプトの live smoke は、`git push && gh pr create && gh run list --commit <SHA> && <待ち>` の1本の連結で background 起動して行った (実測)。報告者の手当ては、登録前の空を live smoke で踏むなら、PR の作成と同じ連結に入れること (実測)。仕分けたセッションの解釈: 上の、headSha で run を引いて待つ形は、引いた時点で run が未登録なら空を返すので、空を「run が無い」と読まずに引き直す分岐が要る。dotfiles で確かめたこと (2026-11-13、v2026.11.2 の写し): 配った pre-merge-quality-gate の `scripts/wait-ci-runs.py` は、登録前に `gh run list --commit <SHA>` が `[]` と rc 0 を返すことを docstring に書き、登録まで引き直す。この分岐は上流で実装済み
- 長いゲート (20〜30分) の前に並列レビューを先に回し、修正を入れてから最終のゲートを1回だけ回す順序にした (実測)
- 前のゲートで simplify の Efficiency 観点が出した最適化を効果を数えずに採ったら、直前の処理が既に同じ表を全部読んでいて、省けるのは課金の枠のおよそ0.4%だった。次のゲートの Altitude 観点が「判断の分岐が shell 層に増えた」「adapter の doc と逆を言う」と指摘し、取り下げた (実測)。報告者の提案: Efficiency の提案を採る前に、隣の処理が既に払っている同じコストと課金や上限の枠に並べて効果を数えることを Phase 2 の判断の軸に足し、効果が枠の数%に満たなければ採らないのを既定にする (実測)
- 2026-11-04の仕分けで、別のリポジトリから、merge の後に品質ゲートを事後に回し、merge 前に出せなかった記録を取り返した報告が届いた。見出しを merge 前の結果と分け、merge の可否の宣言は書かない形にした (実測)。事後のゲートの検証役が見つけた照合の射程のずれは ISSUE-88 の INS-82 に置いた
- 2026-11-10の仕分けで、別のリポジトリから、`gh pr merge --delete-branch` はそのブランチが別の git worktree でチェックアウトされていると、ローカルのブランチの削除を飛ばして警告だけ出す (merge とリモートの削除は済む) という報告が届いた。後で worktree remove と branch -D を手で打つ必要がある (実測)。報告者の提案: merge の手順を持つ skill に、「worktree で作業したブランチは --delete-branch がローカルを消さないので、merge の後に worktree remove と branch -D を打つ」の1行を足す (実測)。報告者は skill を名指ししていないので、渡すときに宛先の skill を確かめる
- 2026-11-11の仕分けで、別のリポジトリから届いた。ゲートを当て直すときにレーンへ `git diff --name-only main...HEAD` を渡したままだと、増分だけを見せたくても PR 全体を読み直してしまう。ファイル一覧の範囲も増分に揃えて渡す必要がある (推測。揃えて渡した回は、増分の外への指摘が出なかった)。この節の1項目め (ゲートが見た commit から HEAD までの増分に当てる) の続きにあたる。dotfiles で確かめたこと (2026-11-11): worktree の `home/.claude/skills/` にある pre-merge-quality-gate の SKILL.md (apm が配った写しで、追跡外) を `増分` と `当て直` で grep すると、`増分` は0行、`当て直` は83行目の「割り当て直さず」だけに当たり、増分への当て直しを書いた箇所は無かった (v2026.11.0 の写し。v2026.11.2 でも `増分` は0行)。上流の agentic-coding-tools の ISSUE-99 (closed) は「増分の手順は散文にせず、マージを head の SHA に縛った」と決めているので、この項を渡すと裁定を緩める提案になる
- 2026-11-11の仕分けで、別のリポジトリから届いた。「ゲートが見た SHA を手元の `git rev-parse HEAD` で控える」手順では、他人の push でマージが拒否されたとき、手元を揃えないかぎり同じ SHA を控えて同じ拒否を繰り返す。反証役の見落としの指摘で見つかった (推測。経路は読みで確かめた)。古い SHA を `--match-head-commit` に渡したときの拒否の形は、ISSUE-134 の「GitHub の CLI とリポジトリの管理」節にある。dotfiles で確かめたこと (2026-11-11): worktree の配布の写し (追跡外) の pre-merge-quality-gate の SKILL.md では、`match-head-commit` は0件、`rev-parse` は42行目 (`--show-toplevel` へ cd する箇所) だけで、ゲートが見た SHA の控え方は書いていない (v2026.11.0 の写し)。dotfiles で確かめたこと (2026-11-13、v2026.11.2 の写し): 43行目で `git rev-parse HEAD` を控え、46・180・193行目が `--match-head-commit` を持ち、193行目は「揃えずに戻ると同じ SHA を控えて同じ拒否を繰り返す」とこの報告の懸念を書いている。上流の agentic-coding-tools の PR #109 で入り、v2026.11.1 で配られた

### pre-merge-quality-gate: Phase 3 の実ブラウザ確認の条件

2026-11-11に仕分けた分で届いた。別のリポジトリのセッションの報告。

- pre-merge-quality-gate の Phase 3 の実ブラウザ確認が、プロジェクトの CLAUDE.md が求めるときだけになった (v2026.11.0、ドキュメントのみ)。報告者の提案は、UI のあるプロジェクトで続けるなら、各プロジェクトの CLAUDE.md かグローバル CLAUDE.md に要求を書くか、ユーザーと決めること (ドキュメントのみ)。dotfiles で確かめたこと (2026-11-11): worktree の配布の写し (追跡外) の SKILL.md は、174行目 (v2026.11.0 の写し) に「UI 変更があり、プロジェクトの CLAUDE.md が実ブラウザでの確認を求めていれば」と書いている。グローバル CLAUDE.md は「完了前」の2で「UI を持つプロダクトの画面に関わる変更は、マージ前に実ブラウザで動作を確かめること。プロジェクトの CLAUDE.md が求めていなくても行う」と既に求めているので、このグローバル CLAUDE.md が読まれるセッションでは要求は残っている。仕分けたセッションの解釈: gate の条件の文だけを読むと「プロジェクトが求めなければ省いてよい」と読め、グローバルの規範と向きが食い違う (v2026.11.0 の写しでの読み)。dotfiles で確かめたこと (2026-11-13、v2026.11.2 の写し): SKILL.md の176行目は「UI 変更があり、CLAUDE.md (user スコープかプロジェクトのどちらか) が実ブラウザでの確認を求めていれば」になっており、上の食い違いは上流で解消した

### superpowers の subagent-driven-development (外部の plugin)

dotfiles も agentic-coding-tools も canonical を持たない。直せるのは、こちらが brief を書く側の手順 (ISSUE-100 のテンプレート) までである。

- 報告 (実測): 同梱の `scripts/review-package` と `scripts/task-brief` は、cwd が対象のリポジトリの中でないと `fatal: not a git repository` と `bad BASE` で止まる。skill のディレクトリへ cd して相対で呼ぶのではなく、リポジトリの中から絶対パスで呼ぶ
- 報告 (実測): 型を剥がして走るテストランナーは型を見ないので、型エラーがあってもテストは緑になる。implementer の brief に型検査の recipe を書かないと implementer も reviewer も型を見ず、コントローラの gate で初めて赤になった。提案は、implementer と reviewer の brief の雛形に「型検査の recipe を回す」を入れること
- 報告 (実測): 同梱の `task-brief` スクリプトはタスクの節だけを切り出すので、計画の冒頭の「前提と決定」が brief に入らず、dispatch に行番号つきで足す必要があった
- 報告 (実測): SDD の最終の全ブランチレビューをマージ前ゲートのコードレビューと兼ねると、どのタスクのファイル一覧にも無かったテストの目録の文書の drift を拾った。タスク単位のレビューは brief の範囲しか見ないので、横断の文書は原理的に見えない。報告者の提案: writing-plans の指針に「テストを足すタスクは目録・索引の文書を Files に含める」を入れる
- 報告 (実測): 実装者を Workflow の `isolation: worktree` で依存の無いタスクごとに並列に走らせ (wave)、コントローラが cherry-pick で統合した。件数の行の最終値はコントローラが統合後に実測して決めると brief に書いたので、衝突はその1行だけで、統合後の件数が各タスクの増分の和と一致することで取りこぼしが無いことも確かめられた。報告者の提案: brief の雛形に「件数などの共有の行はコントローラが持つ」を入れる
- 報告 (実測): brief に BASE の SHA を書いておいたので、worktree が想定と違う基点で切られても、実装者が `git merge --ff-only <BASE>` で自力で合わせた。報告者の提案: brief の雛形に「最初に BASE へ ff-only」を入れる。worktree が既定のブランチから切られる機構は ISSUE-133 の「Claude Code の hook と委譲」節にある
- 報告 (実測): 件数の下限と上限 (下限 + 余裕) の両側で縛るテストのガードがあると、「件数の更新は最後のタスクでまとめてよい」という plan の指示は成り立たない。余裕を超えるテストを足したタスクは、自分のゲートで赤になった
- 報告 (実測): subagent-driven-development の pre-flight scan で、各タスクが作る型と使う型を実際のツリーで grep して突き合わせると、散文のレビューを複数通した計画に順序の食い違い (後のタスクが定める型を前のタスクが使う) が残っていた。実装の前に spec を実コードと突き合わせる項は ISSUE-133 の「Claude Code の hook と委譲」節にある
- 報告 (実測): subagent-driven-development の fix-loop の「Minor はループに入れず最終レビューへ回す」が、グローバル CLAUDE.md の警告0とボーイスカウトとぶつかった。規定どおりだと、タスクが新しく作った警告やテストの空回りが最後まで残る。CLAUDE.md を優先して修正のラウンドに入れた。報告者の提案は、「Minor が警告の新規発生や dead pin に当たるときはループに入れる」を規範か `references/delegation.md` に1行足すこと (足せば毎回の上書きが要らなくなる、は推測)。規範に足す候補としては ISSUE-133 の「Claude Code の hook と委譲」節にある
- 報告 (実測): 同梱の `task-brief` は見出しの形を決め打ちしている。英語の「Task」の見出し (`### Task N:`) しか拾わず、日本語の「手順 N」の plan では rc=3 で止まる (エラーの文面には、見出しの候補として手順の見出しが列挙される)。別のリポジトリでは、見出しが「Task A1」のような英字つきの ID だと「not found」で中身の空のファイルを作った (数字の ID を前提にしている)。2026-11-10の仕分けで、2つのリポジトリから届いた。どちらも awk で見出しの範囲を切り出して代えた。前者は、awk で「### 手順 N:」の節と plan の共通の節 (決定表・前提・同じコミットで変える組) を抜き出して brief を作ると、merge 済みの plan を書き換えずに済み、各 brief の行数で抜き出しの漏れを確かめた (実測)。同じ報告者の使用感では、superpowers の7.0.2の workspace・ledger・review-package のスクリプトは言語を問わず動き、task-brief だけが見出しを英語に縛っている (実測)
- 上の task-brief の件の報告者の提案は2つある。日本語で plan を書く規約 (writing-plans や in-repo-issue の Plan 結合) を持つリポジトリでは、plan の見出しを「### Task N: 手順の名前」の形にする規約を足すか、task-brief が使えないときの代わりの手順を skill の側に置く (推測)。計画の Task の ID に英字の接頭辞 (PR ごとの A1、B1 など) を使う運用なら、task-brief の代わりの切り出しを手順に用意するか、計画の見出しを数字だけにする (実測)。superpowers は外部なので、受けるなら brief の雛形 (ISSUE-100) か使う側の規約になる

### superpowers の brainstorming の visual companion (外部の plugin)

2026-11-10に仕分けた分で届いた。別のリポジトリのセッションの報告。

- 報告 (実測): 見た目の案 (アイコン、表記、OG 画像のレイアウト) を並べて選んでもらうのに効いた。カードの幅が狭いので、1200×630のような大きいモックは1列にして zoom で縮めないと切れる。描いたものは自分でスクリーンショットを撮って崩れを確かめてから見せた

### ast-grep-practice (第三者の上流): 規則の例と許す側の対照

2026-10-31に仕分けた分で届いた。どれも別のリポジトリのセッションの報告。ast-grep-practice skill は apm 経由の第三者の上流なので、直せるのは使う側の書き方と上流への報告まで。

dotfiles で確かめたこと (2026-10-31): `home/apm.yml` は ast-grep-practice を `mizchi/skills/tooling/ast-grep-practice` から入れている (justfile と同じ上流)。agentic-coding-tools のセッションも、自分のリポジトリの全履歴にこの skill が一度も出てこないと返してきた。仕分けた時点では agentic-coding-tools の skill として扱っていた。

- tree-sitter の Rust では属性は struct の子ではなく直前の兄弟なので、`kind: struct_item` に `follows: {kind: attribute_item, regex}` を付けると引ける。名前は `has: {field: name}` で取り、JSON の metaVariables から読む。間に別のものを挟むと引けなくなるので、引いた集合を設定側の集合と等号で比べて取りこぼしを赤に倒す (実測。ast-grep の0.45.3)。報告者の提案: skill に例を足す
- 自作の lint 規則 (GritQL / ast-grep など) をコードの片で書くときは、許す側の対照に「同じ字面を持つが別の構文」(別名の `as`、型注釈の中の `as` など) を置く。報告元が GritQL の規則で踏んだ件が根拠 (実測)。報告者の提案: 規則を書く skill の確認項目に足す

### security-blue-red-team: profile の契約と red-team-agent の宛先

2026-10-31に仕分けた分で届いた。別のリポジトリのセッションの報告で、どれも profile の契約か agent の手順への提案にあたる。報告元は wrap 側で smoke と検査を作っている。ISSUE-114 が自作に残すと見立てている Layer 2 / 3 (staging への HTTP) を触る。

- 現行の red-team-agent は endpoint の行の method と path しか読まず、当てるホストは allow_targets から agent が選ぶ。入口を1本化して backend 直を鍵なしで401にした構成では、backend 直のホストにアプリの path を当てて全件401の偽陰性になり、過去のレポートもアプリの path の多くを backend 直へ送っていた (実測)。報告者の提案: profile の契約に endpoint の行の ingress (`environment.ingresses` の名前) と auth を加え、agent が行ごとに宛先を決める (推測)
- 攻撃者が正当に持てる資格を自分のアカウントのセッション cookie に限り、cookie jar を製品自身のログインの経路で作る make target を作った。cookie の形式は認証ライブラリに作らせ、自前で組まない (実測)。報告者の提案: 契約に `environment.sessions` (persona ごとの jar のパスと ingress、作り手は wrap 側) を加える。それまでは認証付きの能動検査を static-only として報告するよう agent に明記し、0件を「穴が無い」と誤読させない (推測)
- profile の行から要求を組み立てて staging に送り、行の宣言と突き合わせる smoke を作った。送るのは expect のある行と GET だけで、expect の無い書き込みは理由付きの SKIP にした (実測)。報告者の提案: 正しい挙動が拒否である行 (`gate_negative` と `expect`) を契約に加え、agent がその行の PASS / FAIL を expect で判定する。edge の応答 (Cloudflare の1xxx) や staging の Basic 認証の柵をアプリの防御と数えない読み方も agent の手順に入れる (推測)
- 認証付きの行の判定を「ログインへの redirect」だけで見ると、未認証を401の JSON で返す API (React Router の Resource Route 系) で、無効になった jar の結果が PASS に化けた。session の行では expect の無い401も FAIL にする。cleanup 後の古い jar で smoke を回すと、この規則とセッションの無効化を同時に live で確かめられた (実測)
- universal の schema の外に、攻撃者モデルの整合の検査 (入口のホストが allow_targets にある、認証付きの行は session だけ、backend 直の認証付きの行を置かない、jar の置き場、related_code_paths の glob が追跡下のファイルに当たる) を足すと、既存の profile の死んだ glob を5本と存在しない endpoint を一度に拾えた (実測)。skill の profile の検証器へ取り込める候補
- `/security-redteam` の command は agent の入力にある `ATTACK_SURFACES_FILTER` を引数に持たないので、ad-hoc の絞り込みは依頼文で伝えるしかない。command の引数の一覧で確かめた (実測)。報告者の提案: command に `ATTACK_SURFACES_FILTER` を渡す引数を足す

### windows-vm-verification: ディスクの容量

2026-10-31に仕分けた分で届いた。どれも別のリポジトリのセッションの報告。

- ゲストでディスクへ書いているプロセスは、`Win32_PerfFormattedData_PerfProc_Process` を `IOWriteBytesPerSec` で並べると1回の exec で特定でき、ホスト側の差分ファイルの増加と突き合わせて原因を Windows Update と確定した (実測)
- スナップショット直後の起動で、無効にしたはずの Windows Update が動き、ホスト側の差分ファイルが27分で約24GB増えた。同じセッションで2回観測した。過去の MSI のインストールで wuauserv が無効から手動へ戻されていて、スナップショットの下ではゲストの上書きもホストでは追記になる (実測)。報告者の提案: 起動前にホストの空きを確かめ、起動直後と MSI を実行するたびに wuauserv / UsoSvc の StartType を確かめる
- VM の縮小は順序が効く。ゲストで不要物の削除と `Dism /StartComponentCleanup /ResetBase` → `Optimize-Volume -ReTrim` → 停止 → スナップショットの削除 (差分の統合) → `prl_disk_tool compact` の順で、統合だけで87GBから69GB、compact で69GBから53GBになった。`compact -i` で事前に見積もれ、compact はスナップショットが0件のときだけ効く (実測)
- ゲストの中のディレクトリのサイズを測るとき、Parallels の共有フォルダとジャンクションを除かないと、ホストのファイルや二重計上で数十GB多く見える (実測)

### windows-vm-verification: GUI 自動化 (UIA)

2026-10-31に仕分けた分で届いた。どれも別のリポジトリのセッションの報告で、skill の gui-automation への提案にあたる。

- パスワード欄への入力は、「空のまま一度送信して必須エラーを出す → 貼る → エラーが消える」を対照にすると、欄の値が読めなくても入ったことを確かめられる (実測)
- UIA の `IsOffscreen=False` は、作業領域の中で見えていることを意味しない。表示倍率125%の小さい画面で、画面下部の要素がタスクバーの裏に入っていたが offscreen は False だった。要素の BoundingRectangle と `Screen.WorkingArea` を比べ、スクリーンショットとの食い違いで確定した (実測)
- UIA の `WindowPattern.SetWindowVisualState(Maximized)` はそのウィンドウでは効かず、Win32 の `ShowWindow(SW_MAXIMIZE)` では効いた (実測)
- ログオン中のユーザーのセッションへ cmd 経由で payload を起動するとコンソールの窓が前面に出ることがあり、直後の仮想キーがアプリではなくコンソールに届いた。閉じる操作は UIA でボタンを直接 Invoke する方が確実 (実測)
- 文言を名前の完全一致で引いたら、リンクの名前に装飾の記号まで入っていて外れた。コードの文字列は前方一致で使うか、UIA のダンプで実名を確かめてから使う (実測)
- 外部の JSON に後から追記した UI 文字列のキーが欠けたまま payload を流すと、PowerShell の `-like ("*" + $null + "*")` が任意の名前に当たり、意図しないリンクを押した。キーの欠落は payload の冒頭で検査すべきだった (実測)
- WebView2 を UIA で操作するときの罠。date の欄は年月日が別の Spinner で `RangeValuePattern.SetValue` は黙って無視される、`FindAll(Descendants)` は時々タイムアウトを投げる、最大化は `SW_MAXIMIZE` ではなく作業領域に合わせた `MoveWindow` を使う、`IsOffscreen` はスクロールの外を意味することもある、印刷プレビューは Esc ではなく UIA のキャンセルで閉じる (実測)。報告者の提案: skill に載せる。上の `ShowWindow(SW_MAXIMIZE)` と `IsOffscreen` の項とは別の画面での結果なので、載せるときは並べて書く

### windows-vm-verification: ネットワークを切る区間

2026-10-31に仕分けた分で届いた。どれも別のリポジトリのセッションの報告。

- 検証 VM でアダプタを無効にする操作を1本のスクリプトにまとめて finally で必ず戻し、別に SYSTEM の一回きりのスケジュールタスクで、15分後に全アダプタを有効に戻す見張りを置いた (実測)
- ゲストのアダプタを切っている間にホストから ssh を打つと、ControlMaster の多重化の接続が壊れたまま残り、戻した後の ssh (それを使うラッパも) が10分固まった。新しい ssh では Broken pipe が出て張り直された (実測)。回避は、区間の前後で `ssh -O exit <host>` するか、その区間だけ `-o ControlMaster=no` にする (推測)。報告者の提案: CLI (winvm) にこの区間を扱う入口を足す
- ネットワークを切っている間は ssh で同期できないので、`prlctl exec` で base64 を書き込み、ハッシュを照合してから使った (実測)

### justfile (第三者の上流): `*args` の展開で引数が割れる

2026-10-31に仕分けた分で届いた。justfile skill は apm 経由の第三者の上流なので、直せるのは使う側の書き方と上流への報告まで。

- justfile の `*args` を `{{ args }}` で展開すると、空白を含む引数が分割される。`just --dry-run` で `-t "a b"` が `-t a b` に割れ、`set positional-arguments` と `"$@"` で保たれた (実測)。justfile skill の例も `{{args}}` の形なので同じ罠を踏む。報告者の提案: 例を直す
  - 2026-11-10の仕分けで、別のリポジトリから同じ手当ての別の理由が届いた。`just` のレシピに引数を素通しするとき、`{{args}}` を本文に書くとレシピ本文を静的に読むテストの補助関数が式の展開を扱えず壊れることがある。`[positional-arguments]` と `"$@"` にすると本文に `{{...}}` が残らず、クォートも安全になる (実測)

### workflow-authoring (組み込みの skill): 反証役へ既定値を指示する参照例

2026-10-31に仕分けた分で届いた。組み込みの skill なので、直せるのは brief を書く側まで。

- workflow-authoring の参照例にある反証役への既定値の指示 (迷ったら反証とみなす) は、グローバルの CLAUDE.md の委譲のカテゴリにある「反証を委ねるとき既定値を指示しない」と衝突するので、使うときに外す必要があった (ドキュメントのみ)

### workflow-authoring (組み込みの skill): テンプレート文字列の中の文字列連結

2026-11-11に仕分けた分で届いた。組み込みの skill なので、直せるのは script と brief を書く側まで。

- Workflow の script で、バッククォートのテンプレート文字列の中に「' + 変数 + '」の連結を書くと展開されず、文字のまま agent へ渡る。共通の前置きに絶対パスがあったので害は無かったが、置き場の指定が壊れうる (実測)。報告者の提案は、Workflow の authoring の注意に「テンプレート文字列の中で文字列連結の綴りを書かない (${} で埋める)」を足すこと (実測)。仕分けたセッションの解釈: workflow-authoring は組み込みの skill なので、受けるなら script と brief を書く側の注意か ISSUE-100 のテンプレートになる

## タスク

- [x] in-repo-issue の件を agentic-coding-tools へ渡す。規約外のキーを検出して知らせる形と、キー名を可変にする形のどちらにするかを決めてもらう
  - 2026-10-31に渡した。agentic-coding-tools の ISSUE-38 (Phase E の親伝播が frontmatter の乖離で発火しない件。同じ機序と「規約外のキーを検出して報告する」タスクを既に持っていた) へ追記された。キー名を可変にするかの裁定は、ユーザーが決めるものとしてあちらに残っている
- [x] session-handoff の2件 (subagent の resume、相手をセッション名で書かせない) を agentic-coding-tools へ渡す
  - 2026-10-31に渡した。agentic-coding-tools の ISSUE-98 に1本で起票された
- [ ] simplify を読み取り専用の reviewer で回す形を、pre-merge-quality-gate に入れるかを決める。dotfiles の gate でも並列の4観点がブランチを書き換えうるかを確かめてから決める。pre-merge-quality-gate の「ゲートの順序、増分、CI の待ち方」節の4項目め (Efficiency の判断の軸) も、渡すかどうかをここで一緒に決める
- [ ] superpowers の2件は、brief の雛形 (ISSUE-100) に「型検査の recipe」と「同梱スクリプトはリポジトリの中から絶対パスで呼ぶ」を入れるかを決める
  - 2026-10-31に足した5件 (計画の冒頭の前提、目録の文書を Files に含める、件数の行はコントローラが持つ、最初に BASE へ ff-only、件数の両側のガード) も、同じく雛形に入れるかを決める
  - pre-flight scan の件と fix-loop の Minor の扱いの件は、ISSUE-133 の委譲の規範の候補と一緒に決める
  - 2026-11-10に足した task-brief の見出しの形の件 (日本語の見出しと英字つきの ID) も、雛形か使う側の規約で受けるかを同じく決める
- [x] in-repo-issue の2節 (後から取り付ける経路、Issue の外にある写しと参照) を agentic-coding-tools へ渡す。`always_run` のコメントは版を添えて測り直してもらい、`issue-id.py` の CLI にかかる分は ISSUE-121 と一緒に渡す
  - 2026-10-31に渡した。後から取り付ける経路は agentic-coding-tools の ISSUE-32 へ追記され (`always_run` は版と files / types の絞り込みの有無をそろえて測り直すタスクになった)、写しと参照は agentic-coding-tools の ISSUE-97 として起票された。`--check-diff` の罠を SKILL.md に書くかは ISSUE-121 のタスクが持ったまま
- [ ] in-repo-issue の「後から取り付ける経路」節の残り2項目 (採番の形式の変更を配るときの告知、配る `issue-id.py` が764行で全文を読むのが重い) を agentic-coding-tools へ渡すか決める。2026-10-31の依頼では範囲を3点に絞って書いたので外れた
- [x] pre-merge-quality-gate の「ゲートの順序、増分、CI の待ち方」節を agentic-coding-tools へ渡す。Efficiency の判断の軸は、simplify を読み取り専用の reviewer で回す件と一緒に決める
  - 2026-10-31に、節の最初の3項目を渡した。agentic-coding-tools の ISSUE-99 として起票された。4項目めは上の simplify のタスクが持つ
- [ ] 「ゲートの順序、増分、CI の待ち方」節の5項目め (merge の後に回す事後のゲート) を agentic-coding-tools へ渡すか決める
- [ ] 「ゲートの順序、増分、CI の待ち方」節の6項目め (worktree のブランチと `--delete-branch`) を、merge の手順を持つ skill へ渡すか決める
- [ ] ast-grep-practice の2件を、第三者の上流 (mizchi/skills) へ報告するか、使う側の書き方で受けるかを決める
- [ ] security-blue-red-team の6件を agentic-coding-tools へ渡す。ISSUE-114 で寄せる範囲を決めてから、契約に足すか自作の層で持つかを決めてもらう
- [x] windows-vm-verification の3節を agentic-coding-tools へ渡す。CLI (winvm) にネットワークを切る区間の入口を足すかも決めてもらう
  - 2026-10-31に渡した。ディスクの容量と GUI 自動化は agentic-coding-tools の ISSUE-100、ネットワークを切る区間 (winvm の入口の判断を含む) は agentic-coding-tools の ISSUE-101 として起票された。配布版の gui-automation.md に既にあった2件 (日付の Spinner、インストーラの後の wuauserv) は除いた
- [ ] justfile の `*args` の件を第三者の上流へ報告するか決める。workflow-authoring の件は brief を書く側で外すことを、ISSUE-100 のテンプレートに入れるか決める
- [ ] 「ゲートの順序、増分、CI の待ち方」節に2026-11-11に足した「当て直しのファイル一覧を増分に揃える」を agentic-coding-tools へ渡すか決める。上流の ISSUE-99 (closed) の裁定 (増分の手順は散文にしない) を緩める提案になるので、閉じるか残すかをユーザーと決める。同じ日に足したほかの2項目 (ゲートが見た SHA の控え方、run の登録前に空が返ること) は v2026.11.1 で上流に入っていた
- [ ] 「pre-merge-quality-gate: Phase 3 の実ブラウザ確認の条件」節の件は v2026.11.1 で gate の条件の文が user スコープの CLAUDE.md を含む形になったので、それで足りるとして閉じるかをユーザーと確かめる
- [ ] 「ゲートの順序、増分、CI の待ち方」節の1項目めに2026-11-11に足した子 (ゲートの直し自体を増分に含める、引き継ぎ書の使い回しの前提が外れた実例) を、agentic-coding-tools の ISSUE-99 へ足すか決める。ISSUE-99 は closed で「増分の手順は散文にせず、マージを head の SHA に縛った」と決めているので、閉じた Issue へは足せない。新しい Issue にするか、裁定のとおり閉じるかをユーザーと決める
- [ ] workflow-authoring のテンプレート文字列の中の文字列連結の件を、ISSUE-100 のテンプレートか Workflow の script を書く側の注意で受けるか決める

## 関連

- agentic-coding-tools の ISSUE-46: Phase E の子探索が空振りしたときの倒れ方。キーの不一致も同じく空振りとして現れる
- ISSUE-84: 引き継ぎが無音で失われる経路。resume できない subagent も、引き継ぎ書を読んだ側から見ると同じく黙って失われる
- ISSUE-100: マージ前ゲートの dispatch プロンプトのテンプレート。brief の雛形の置き場
- ISSUE-121: `issue-id.py` の接頭辞と走査の除外を外から渡す。in-repo-issue の後付けの取り付けと同じ面を持つ
- ISSUE-114: security-blue-red-team を cloudflare の security-audit へ寄せる検討。Layer 2 / 3 を自作に残す見立てで、security-blue-red-team の節の提案が触る層と重なる
- ISSUE-75: 写しの食い違いを config-guard で検査する dotfiles 側の前例。ロードマップを写しにする雛形の提案と形が似ている
