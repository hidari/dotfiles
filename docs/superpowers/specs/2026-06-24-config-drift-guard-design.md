# config drift guard 設計

## 背景と目的

PR #22 で chrome-devtools を公式 plugin へ移行した際、自作 skill と settings.json に散在する MCP ツール名・skill/plugin 参照を手作業で stale 修正した。これらの literal は plugin 名・server 名・tool 名が変わるたび silent に rot するが、検出する仕組みが無い。さらに settings.json は skip-worktree により committed（curated subset）と live（superset）の二重状態を持ち、その契約が in-repo に文書化されていない。

本設計は follow-up issue #1（stale 参照の CI ガード）と #2（settings.json の二重管理文書化と curation 機械化）を、共有の Python 検査ツール `config-guard` で同時に解決する。CLAUDE.md MUST GLOBAL「静的検査可能なルールはプロンプトではなく linter か ast-grep で記述する」に直接合致する。

## 確定した設計判断

- 検出ロジックは Hybrid。既知の legacy/誤名を denylist で確実に弾き、それ以外は形（shape）だけ検証する。built-in ツール名の完全 allowlist 照合はしない。
- 検査対象スコープは skills の allowed-tools と committed settings.json の permissions の両方。
- 実装は Python + pytest（既存 backup-tool と同じ uv プロジェクト構成）。
- issue #2 の機械チェックは committed 単体の不変条件検証。strict subset 検証は現状ファイルで committed-only キー（model 等）により即 fail するため採用しない。
- 両 issue を 1 本の PR で Close する（validator を共有するため）。

## 調査で確定した一次情報

- legacy literal（`mcp__chrome-devtools__` / `claude-in-chrome`）はリポから完全除去済み。本ガードは再混入を防ぐ regression guard として機能する。
- allowed-tools を持つ skill は 2 つ（chrome-devtools-debugger / git-branch-switcher）で、いずれも現状クリーン。
- committed と live は strict subset 関係ではない。committed-only: `model`、deny の `NoteboolEdit`（タイポ）と `NotebookRead`、ask の `git commit`/`git push`。live-only: 個人通知トグル、dead な `enabledMcpjsonServers`、ローカル絶対パス（`/Users/<name>`）を含む `hidari-plugins` marketplace。値分岐: `effortLevel`（committed=high / live=xhigh）。
- 引き継ぎの「canonical built-in 15 個」リストは不完全だった。feature-dev サブエージェントの tools 定義に `LS` / `NotebookRead` / `KillShell` / `BashOutput` が実在ツール名として現れる。よって committed deny の `NotebookRead` は妥当であり、純粋に invalid なのは `NoteboolEdit`（タイポ）のみ。

## アーキテクチャ

`scripts/config-guard/` を uv プロジェクトとして新設する（backup-tool と対称: ruff / ruff format / mypy strict / pytest）。各モジュールは単一責任で分離する。

- `tool_refs`: トークン 1 個を受け取り妥当性を返す純粋関数 `validate_tool_token`。denylist と shape 規則のみに依存し、ファイル I/O を持たない。
- `extractors`: 検査対象からトークン列を抽出する。SKILL.md の YAML frontmatter の allowed-tools リスト、settings.json の permissions.{allow,deny,ask}。
- `git_source`: settings.json の内容を git の index（`git show :home/.claude/settings.json`）から読む。working tree は決して読まない。
- `settings_invariants`: committed settings.json の構造不変条件を検証する。
- `cli`: リポジトリをスキャンし、検出結果を出力する。検出が 1 件でもあれば非ゼロ終了する。

## 検査A: ツール名妥当性（Hybrid）

`validate_tool_token(token) -> str | None`（None は妥当、str はエラー理由）の判定順序:

1. denylist 該当なら invalid。対象は移行済み server の legacy MCP 形（`mcp__chrome-devtools__*`, `mcp__claude-in-chrome__*`）と、既知の誤名・タイポの bare name（`Git`, `NoteboolEdit`）。新たな server が plugin 化したら legacy prefix を 1 行追加する。
2. shape にマッチすれば妥当。妥当な shape は次のいずれか。
   - MCP 形: `mcp__<server>__<tool>`。plugin 形（`mcp__plugin_<plugin>_<server>__<tool>`）と非 plugin 形（`mcp__claude_ai_Gmail__authenticate` 等）の双方を許容する。
   - built-in 形: PascalCase 等のツール名ヘッド（例 `Read`, `WebFetch`, `LS`）に任意の permission specifier `(...)` が続く形（例 `Bash(git *)`, `Read(.hidari/**)`）。
3. どちらにも該当しなければ invalid（malformed）。

built-in 名の完全リスト照合をしないため、Claude Code が新ツールを追加しても検証器が drift しない。代償として novel typo（shape は妥当だが実在しない PascalCase 名）は見逃すが、これは Hybrid 採用時に受容したトレードオフであり、観測済みの誤名は denylist が捕捉する。

抽出した token 列を SKILL.md と settings.json の双方に同じ validator で適用する。

## 検査B: committed settings.json 不変条件

セキュリティと正当性に絞ったハードフェイルのみとし、個人の好み（通知トグル等）は咎めない。

- valid JSON としてパースできること。
- `/Users/` や `/home/` 等のユーザー絶対パスを値に含まないこと（gitleaks との多層防御）。
- `directory` source の marketplace、および非公開 marketplace 由来の plugin（`*@hidari-plugins` 等、公式・公開 marketplace 以外）を含まないこと。
- `enabledMcpjsonServers` キーを含まないこと（PR #22 で削除した dead config の再滞留を構造的に防ぐ）。
- permissions.{allow,deny,ask} の各トークンが検査A を通ること。

検査B は committed のみを対象とする。live（skip-worktree, CI 外）の hygiene は CI では検証できず、文書化された契約で担保する。

## settings.json の git-source 規約

settings.json は skip-worktree のため working tree = live superset である。検査器が working file を読むと個人トグルや `/Users` パスを誤検出する。これを防ぐため `git_source` は git の index（`git show :home/.claude/settings.json`）から内容を取得し、working file は決して読まない。

index は clean commit 直後は HEAD と同一内容を持ち、pre-commit の cacheinfo dance で差し替えた時は staged 内容を持つ。よって index 一本で「staged 優先・HEAD 等価」の双方を満たし、別途 HEAD フォールバックは不要。index に存在しない（削除を含む）場合は RuntimeError とする。

この「working file を読まない」挙動を、staged と HEAD と working で内容が異なる一時 git リポジトリを使って実際にテストする。

## 付随する修正

committed settings.json の deny にある `NoteboolEdit`（タイポ）を `NotebookEdit` に修正する。検査A が走ると fail するため必須。修正は skip-worktree dance で committed blob だけを差し替え、working file は触らない（`git show HEAD:` で取得、テキスト編集、`git hash-object -w`、`git update-index --cacheinfo 100644,<sha>,<path>`、staged diff 検証、commit、`--skip-worktree` 再設定）。`NotebookRead` は実在ツール名なので保持する。

## ドキュメント追加（issue #2）

README に Claude Code config の skip-worktree 契約を説明するセクションを追加する。committed = curated public-safe subset / working = live superset、なぜ分けるか、committed だけを安全に編集する手順（dance）、そして役割分担（gitleaks は秘匿検出、config-guard は構造 curation）を明記する。ディレクトリツリーは載せない。

## CI / pre-commit 配線

- `.github/workflows/test.yml` に `config-guard` job を追加する。uv sync、ruff check、ruff format --check、mypy strict、pytest、最後にリポジトリへ guard 実行という backup-tool job と対称の構成にする。
- `.pre-commit-config.yaml` に config-guard の ruff / mypy / pytest フックと guard 実行フックを追加する。

## テスト戦略

仕様としてのテストを徹底し、TDD で進める。

- `validate_tool_token` の妥当・invalid の網羅。妥当例（`Read`, `Bash(git *)`, `mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot`, `mcp__claude_ai_Gmail__authenticate`, `LS`, `NotebookRead`）と invalid 例（`Git`, `NoteboolEdit`, `mcp__chrome-devtools__navigate_page`, `mcp__claude-in-chrome__x`, 空文字, lowercase garbage）。exact なエラー理由まで検証する。
- extractors が SKILL.md frontmatter と settings.json permissions から正しい token 集合を抽出すること。allowed-tools が無い skill では空集合になること。
- git_source が git の index から読み、working file を読まないこと（staged/HEAD/working で内容が異なる一時 git リポジトリで検証）。
- settings_invariants の各不変条件（/Users パス、directory marketplace、enabledMcpjsonServers、不正トークン）について、good ケースが通り bad ケースが確実に fail すること。
- cli が good fixture で exit 0、bad fixture で exit 1 を返し、検出箇所を出力すること。

## 受け入れ基準

- 現状の skills と（NoteboolEdit 修正後の）committed settings.json で guard が exit 0 になる。
- legacy MCP literal、`Git`、`NoteboolEdit`、`/Users` パス、`enabledMcpjsonServers` のいずれかを混入させた fixture で guard が exit 1 になる。
- test.yml の config-guard job と pre-commit フックが緑になる。
- README に skip-worktree 契約が明記される。
- 全 lint / format / type / test が警告 0・エラー 0。

## スコープ外と既知のトレードオフ

- novel typo（shape 妥当だが実在しない PascalCase 名）は検出しない。Hybrid の受容済みトレードオフ。
- live settings.json の hygiene は CI では検証しない。文書化された契約で担保する。
- plugin 由来 MCP ツールの実在性は検証しない（plugin はリポにチェックインされていないため形のみ検証可能）。
</content>
</invoke>
