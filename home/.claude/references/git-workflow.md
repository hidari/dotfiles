# 変更の記録と公開の一次実測

`~/.claude/CLAUDE.md` の「変更の記録と公開は粒度と経路を決めてから行う」
カテゴリが持つ規範の、手当ての詳細と一次実測。

規範の遵守そのものには要らない。手当ての具体が要るとき、規範を疑うとき、
似た失敗を踏んで「これは既知か」を確かめるときに読む。

例外が 1 つある。次のプレフィックス一覧は遵守の瞬間に引く参照表で、
規範ではなく列挙であることを理由に常時層から外した。

## コミットメッセージのプレフィックス

"Conventional Commits" をベースにする。

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

大きな機能や修正を実施している最中に作業中の変更をコミットする際には、
それぞれのプレフィックスの後ろに `(wip)` を付ける。

## 保護ブランチの判定に classic API だけを使わない

repository ruleset は classic API とは別系統で、
`gh api repos/<owner>/<repo>/branches/<default-branch>/protection` は 404 を返す。

classic 404 を「保護なし」と誤判定すると、
ruleset 保護 (pull_request / required_status_checks 等) を bypass 特権で素通り push し、
required checks / PR レビューを欠落させる。

実際 classic 404 でも ruleset で保護されているリポジトリが存在する。

ruleset 側を `gh api repos/<owner>/<repo>/rulesets` で見ても判定はできない。
このエンドポイントは ruleset の一覧を返すだけで `rules` キーを持たず、
何が強制されているかを答えないためである (2026-08-31 に dotfiles で実測)。
branch に実効している rule を返すのは
`gh api repos/<owner>/<repo>/rules/branches/<branch>` の方である。

判定式と、空出力・branch 名・終了コードの罠は skill
`dev-workflow:in-repo-issue` の「クローズ経路: feature PR 同梱を優先」節が持つ。

## 日本語の散文をファイル経由で渡す理由

禁止すべき文字種を覚えて避ける方式は、書くたびに判定を要求するので繰り返し失敗した。
heredoc は中身が command 文字列を通るので回避にならない。

対象コマンドの一覧・機構・発火条件の実測は skill `dev-workflow:commit-and-pr-message` が持つ。

## push の完了確認

`git push` はパイプにも後続コマンドにも繋がず単独で実行する。
パイプ先の exit code が push 本体の失敗や未完を隠し、
pre-push hook の完走と ref transfer の完了を取り違える。

push 後は次の 2 つで直接確認する。

- `git ls-remote --heads origin <branch>` (リモート ref の存在)
- `git status -sb` (upstream tracking)

## squash マージ後の取り込み確認

`git cherry` は squash で patch-id が変わるため信用できない。
origin/main への取り込みは空のファイル diff で確認する。
