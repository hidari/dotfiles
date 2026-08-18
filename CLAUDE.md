# CLAUDE.md

このファイルは、Claude Code (claude.ai/code) がこのリポジトリでコードを操作する際のガイダンスを提供します。

## プロジェクト概要

dotfiles はユーザーが自信のMacの設定ファイルなどを管理するためのリポジトリです。

## 基本原則

- シンプルに保つ
- テスタブルなコードを徹底して単体テスト、統合テストを必ず記述しテストで全機能の動作を保証する
- 手動テストによる動作確認を最小限にすることをなにより重要視する
- ボーイスカウトルールに必ず従う（定義は user CLAUDE.md が canonical で、ここでは再定義しない）
- コードとテストがファーストクラスドキュメント（= the single source of truth）
- テストコードは仕様としてのテストの考え方を徹底する

## [MUST] 必ず守らなければならないルール

- 原則として feature-devプラグイン を使用して設計・実装・レビューを行う
- 作業開始前に `dev-workflow:git-branch-switcher` スキルでブランチを選択する
- superpowers の spec / plan は Issue ディレクトリ配下へ `<NNN>-spec.md` / `<NNN>-plan.md` として置く（規約と手順の canonical は `dev-workflow:issue-scoped-artifacts` skill）
- ブランチのpush後は以下の手順でPull Requestを確認してください
   1. `gh pr list --head $(git branch --show-current) --base main` で Pull Request の存在を確認
   2. Pull Requestが無ければ `gh pr create --assignee @me --base main --fill` で作成
- 既存コードの変更時もユニット/統合テストは必ず書き、他のテストを参考に一貫性を持たせる
- PRのマージ前には必ず `/simplify` と `feature-dev:code-reviewer` プラグインによるレビューを実行すること
- 警告やエラーは処理中のタスクや変更に関係ないものでも即座に修正し、常に警告0個を維持すること
- 本リポジトリでの言語は次のとおり確定させる（user CLAUDE.md が「プロジェクトごとに確定させる」ことを求めている）
   - ログメッセージはシステム内部ログを日本語、フロント側など外部に見えるものを英語にする
   - コード内のコメントは日本語で書く
- 規模が小さいため、後方互換性の破壊はためらわず、最も堅牢で合理的、シンプル（NOT EASY）なコードを記述しコードベースをきれいに維持すること
- シェルスクリプトに他言語（AppleScript 等）を埋め込むときは、埋め込み側の構文検査をテストで pin すること。ヒアドキュメントを変数へ受けるならコマンド置換ではなく `IFS='' read -r -d '' VAR <<'EOF' || true` を使う（理由: 埋め込み言語の構文エラーはホスト言語の検査を素通りし、実行するまで露見しない。AppleScript では変数名 `path` / `round` が予約語と衝突して -1700 / -2741 になった。`$(cat <<'EOF')` で受けると本文中のアポストロフィ [`AppleScript's`] をコマンド置換のパーサがクォート開始と解釈して終端を見失う。変数へ受ければテストが source するだけで本文を検査でき、マーカーで切り出す text-parse も要らなくなる）

## 注意

1. リポジトリルートに存在する以下のファイルはこのリポジトリの管理のためのファイルです
   - `.gitignore`
   - `CLAUDE.md`
   - `LICENSE`
   - `README.md`
2. 上記以外のファイル、ディレクトリはMac上にて使用するものです
