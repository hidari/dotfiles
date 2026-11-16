# 変更の記録と公開の一次実測

`~/.claude/CLAUDE.md` の「変更の記録と公開は粒度と経路を決めてから行う」カテゴリが持つ規範の、手当ての詳細と一次実測。

規範の遵守そのものには要らない。手当ての具体が要るとき、規範を疑うとき、似た失敗を踏んで「これは既知か」を確かめるときに読む。

例外が 1 つある。次のプレフィックス一覧は遵守の瞬間に引く参照表で、規範ではなく列挙であることを理由に常時層から外した。

## コミットメッセージのプレフィックス

- `feat:` 新機能の追加
- `fix:` バグ修正
- `improve:` 既存機能の挙動変更を伴う改善
- `refactor:` 既存機能の挙動変更を伴わないリファクタリング
- `test:` テスト関連（追加・修正・削除）
- `style:` コードスタイル（フォーマット、セミコロンなど）
- `docs:` ドキュメントの更新・追加
- `ci:` CI/CD関連の変更
- `perf:` パフォーマンス改善
- `depends:` 外部依存関係の変更
- `build:` ビルドに関わる処理や設定の変更
- `config:` 設定値の変更
- `chore:` その他の作業（typoの修正、コメントの修正など）
- `agent:` コーディングエージェントの振る舞いを変更

大きな機能や修正を実施している最中に作業中の変更をコミットする際には、それぞれのプレフィックスの後ろに `(wip)` を付ける。

## 保護ブランチの判定に classic API だけを使わない

classic 404 でも ruleset で保護されているリポジトリが存在する。
classic 404 を「保護なし」と誤判定すると、ruleset 保護を bypass 特権で素通り push し、required checks / PR レビューを欠落させる。

ruleset 側は list endpoint (`gh api repos/<owner>/<repo>/rulesets`) では判定できない。
返るのは ruleset の id と name と target と enforcement だけで `rules` を持たず、何が強制されているかを答えないためである (2026-08-31 に dotfiles で実測)。
`rules` を持つのは detail endpoint (`/rulesets/{id}`) と、branch に実効している rule を直接返す `/rules/branches/<default-branch>` で、判定には後者を使う。
判定式は出力に `pull_request` が含まれるか。

この判定を静かに壊す形が 3 つある。

- endpoint は branch 名が空でも実在しなくても rc 0 と空を返す。空を「保護なし」と読むと、branch 名を間違えただけの状態が否定側の結論になる
- branch 名を literal で書かない。保護の対象は default branch でその名前はプロジェクトごとに違うので、`gh repo view --json defaultBranchRef` から取る
- 終了コードを見るときはパイプへ繋がない。`| head` のように別コマンドで終端すると `$?` はその終端コマンドの rc になり、`gh` 自身の失敗が消える

同じ手順を skill `dev-workflow:in-repo-issue` も持つ。あちらのトリガは Issue の起票とクローズで、この規範のトリガ (保護ブランチへ直 push する前) とは交わらない。canonical をどちらか一方へ寄せると寄せなかった側の経路から到達できなくなるので、重複は意図して残す。

## 日本語の散文をファイル経由で渡す理由

禁止すべき文字種を覚えて避ける方式は、書くたびに判定を要求するので繰り返し失敗した。
heredoc は中身が command 文字列を通るので回避にならない。

対象コマンドの一覧・機構・発火条件の実測は skill `dev-workflow:commit-and-pr-message` が持つ。

## push の完了確認

手当ては `~/.claude/references/observation.md` の「成否が隠れる」項が持つ。

## squash マージ後の取り込み確認

`git cherry` は squash で patch-id が変わるため信用できない。
origin/main への取り込みは空のファイル diff で確認する。

ツリーのハッシュ (`git rev-parse <rev>^{tree}`) の一致は、空のファイル diff と同じことを1つの値で比べる形で、次の2つの用途に使えた (いずれも実測)。

- strict な required check の下では、squash 後の main のツリーが、マージゲートが緑だった PR の head のツリーとハッシュで一致した。main の push で CI を回さない構成でも、main が検証済みであることを確かめられる
- squash で先に入った PR の上に積んだブランチを `git rebase --onto origin/main <元の PR の HEAD>` で載せ替える前に、main のツリーと元の PR の HEAD のツリーのハッシュを比べる。一致していれば、載せ替えても作業ツリーは1バイトも変わらない (並列のレビュー agent が読んでいる最中も含む)

squash の後のローカルのブランチは `git branch -d` で消えない。消し方に2つの罠がある (いずれも実測)。

- `-D` で消すのは、`gh pr list --head <b> --state merged --json headRefOid` の値とローカルの `git rev-parse <b>` が一致するときだけにする。一致していれば、未 push のコミットを失わない
- `gh pr merge --delete-branch` は、そのブランチが別の git worktree でチェックアウトされていると、ローカルのブランチの削除を飛ばして警告だけ出す (merge とリモートの削除は済む)。あとで `git worktree remove` と `git branch -D` を手で打つ (gh の版は未記録)

## hook が走らない経路

hook に載せた検査を素通りする経路 (cherry-pick での取り込み、タグを起点にするリリースでのタグだけの push) を踏むときに開く。

古いブランチのコミットを cherry-pick で新しいブランチへ取り込むとき、cherry-pick は pre-commit の hook を走らせない。差分を増分で見る検査は取り込んだコミットを一度も見ないので、違反が黙って CI まで素通りする。ローカルにだけ残っていた古いブランチの2コミットを取り込んだとき、記法の検査の違反112件がローカルの CI まで届いた (実測)。書き捨てのリポジトリに追記するだけの `pre-commit` hook を置くと、2回の commit で2行が書かれ、`git cherry-pick` の後も2行のままだった (2026-11-11に git 2.56.0 で再現した)。

古いコミットを取り込んだら、直後に増分の検査を手で回す (実測)。`pre-commit run --from-ref <base> --to-ref HEAD` 相当で足りる見込みだが、範囲指定が hook と同じ検査を走らせるかは確かめていない (推測)。rebase で取り込む場合も同じかは試していない。

既存のコミットへタグだけを push すると、pre-commit の pre-push hook は走らなかった。使い捨ての bare リモートで、新しいコミットを含む push を対照に確かめた (実測)。pre-push に CI 相当の検査を載せていても、タグを起点にするリリースは検査を通らない。手当ては、タグを起点にリリースするタスクの側で、検査を前段に置くこと。
