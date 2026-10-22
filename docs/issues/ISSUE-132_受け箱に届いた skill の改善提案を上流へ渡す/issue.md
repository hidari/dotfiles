---
status: open
---

# feat: 受け箱に届いた skill の改善提案を上流へ渡す

## 背景

2026-10-21 に受け箱へ届いたまとめのうち、配布している skill (canonical は agentic-coding-tools) と、外部の plugin の skill への改善提案をここへ集める。どれも他のリポジトリのセッションの報告で、dotfiles で確かめたことは項目ごとに分けて書く。

### in-repo-issue: 親子のキーを拡張したプロジェクトで Phase E が無音で終わる

報告 (実測): Phase E は frontmatter の `^parent:` と `^children:` を grep する。プロジェクトが frontmatter のキーを別名 (例: `parent_issue:` / `child_issues:`) で持っていると grep は0件を返し、Phase E は「親なし」として無音で終わる。親子のリンクが実在しても伝播の提案が出ない。報告元では同梱の側で親のクローズが済んでいたので実害は無かった。

報告者の提案 (推測): 親子のキー名をハードコードせず、プロジェクトのテンプレートから読む。または `parent` も `children` も見つからないのに frontmatter に `parent` / `child` を含むキーがあれば警告を出す。対象は Phase E と A.6、検索手順の親一覧。

同じ報告で、クローズを feature PR に同梱したあとの Phase C は C.3 の「既に closed」分岐で no-op になり、破綻しなかったことも確かめられている (実測)。skill が同梱節で述べている挙動どおりである。

dotfiles で確かめたこと: skill の frontmatter スキーマは `parent` / `children` を名指しし、「これ以外は持たない」と書いている。報告元のキーはこの規約の外にある。直す向きは2つあり、規約外のキーを検出して知らせる (0件を健全と読ませない) か、キー名を可変にするかで、前者は規約を変えずに済む。

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

### superpowers の subagent-driven-development (外部の plugin)

dotfiles も agentic-coding-tools も canonical を持たない。直せるのは、こちらが brief を書く側の手順 (ISSUE-100 のテンプレート) までである。

- 報告 (実測): 同梱の `scripts/review-package` と `scripts/task-brief` は、cwd が対象のリポジトリの中でないと `fatal: not a git repository` と `bad BASE` で止まる。skill のディレクトリへ cd して相対で呼ぶのではなく、リポジトリの中から絶対パスで呼ぶ
- 報告 (実測): 型を剥がして走るテストランナーは型を見ないので、型エラーがあってもテストは緑になる。implementer の brief に型検査の recipe を書かないと implementer も reviewer も型を見ず、コントローラの gate で初めて赤になった。提案は、implementer と reviewer の brief の雛形に「型検査の recipe を回す」を入れること

## タスク

- [ ] in-repo-issue の件を agentic-coding-tools へ渡す。規約外のキーを検出して知らせる形と、キー名を可変にする形のどちらにするかを決めてもらう
- [ ] session-handoff の2件 (subagent の resume、相手をセッション名で書かせない) を agentic-coding-tools へ渡す
- [ ] simplify を読み取り専用の reviewer で回す形を、pre-merge-quality-gate に入れるかを決める。dotfiles の gate でも並列の4観点がブランチを書き換えうるかを確かめてから決める
- [ ] superpowers の2件は、brief の雛形 (ISSUE-100) に「型検査の recipe」と「同梱スクリプトはリポジトリの中から絶対パスで呼ぶ」を入れるかを決める

## 関連

- agentic-coding-tools の ISSUE-46: Phase E の子探索が空振りしたときの倒れ方。キーの不一致も同じく空振りとして現れる
- ISSUE-84: 引き継ぎが無音で失われる経路。resume できない subagent も、引き継ぎ書を読んだ側から見ると同じく黙って失われる
- ISSUE-100: マージ前ゲートの dispatch プロンプトのテンプレート。brief の雛形の置き場
