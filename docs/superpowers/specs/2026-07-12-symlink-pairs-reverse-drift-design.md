# SYMLINK_PAIRS reverse-drift テスト設計

## 背景と目的

`bootstrap.sh` の `SYMLINK_PAIRS` は `"repo_source|home_target"` の配列で、fresh マシンの再現に使う真実源である。現状この配列を守るテストは forward 方向（source→pair）に偏っている。

- `all sources exist`: 宣言された各 pair の source が repo に実在するか。「pair を書いたのにファイルが無い」drift を捕捉する。
- `manages the Ghostty config`: ghostty pair 1 件だけを literal pin し、配列から消えていないかを見る。

欠けているのは reverse 方向（config→pair）である。repo に新しい config を足したが `SYMLINK_PAIRS` へ配線し忘れると、そのファイルは fresh マシンに配置されず、しかも誰も検出しない。ghostty だけを literal pin する現状は N 個の config を手作業で pin することを強いており一般化していない。

本設計は ghostty の literal pin を「home/ 配下の全 config が pair でカバーされているか」を検証する reverse-drift テストへ一般化する。CLAUDE.md MUST GLOBAL「静的検査可能なルールはプロンプトではなく linter か test で記述する」に直接合致する。

## 確定した設計判断

- 検出方式はカバレッジ集合の一致テスト（案A）。「未カバー集合 == 明示 allowlist」をアサートする。差分は「配線し忘れた新 config」（未カバー側の増加）または「stale allowlist」（pair 追加後の消し忘れ）を意味し、drift を対称に捕捉する。
- 粒度混在（whole-dir pair の nvim と file pair の ghostty）は transitive coverage で吸収し、その判定を純粋関数 `symlink_target_covered` の一点に閉じ込める。呼び出し側は「covered か否か」だけを見る。
- ghostty の literal pin テストは削除し reverse テストへ一本化する。「ghostty pair を外すと `home/.config/ghostty/config` が未カバーになり FAIL」で reverse テストが一般的に包含するため、二重に pin しない（DRY / canonical single source）。
- 検査スコープは `home/` 配下のみ。`home/X` は `~/X` を mirror する規約であり、全ファイルが symlink 対象（allowlist を除く）という不変条件が成り立つ。`scripts/` 配下の 2 件（backup / small-id-gen）は個別に cherry-pick したツールで mirror ではないため対象にしない。
- 対象は git-tracked ファイルのみ（`git ls-files 'home/'`）。apm 生成物（`apm_modules/` や vendored skill）は `home/.gitignore` で ignore されており tracked に現れないため自動的に除外される。

## 調査で確定した一次情報

- `SYMLINK_PAIRS` の source は 21 件。うち `home/` 配下が mirror 対象、`scripts/` の 2 件はツール。
- `home/` の tracked ファイルで、どの pair にもカバーされない未カバーは 6 件。その正体と分類は以下。全 6 件が意図的に symlink しないファイルであり allowlist に載せる。
  - `home/.gitignore`: `home/` サブツリー用の gitignore（apm 生成物を ignore）。
  - `home/.gitconfig.private.example`: private gitconfig のテンプレ（実体 `.gitconfig.private` は git-ignored でユーザーが作る）。
  - `home/apm.yml`: apm install が bootstrap で読む manifest。
  - `home/apm.lock.yaml`: apm lockfile（deployed_files の真実源）。
  - `home/.config/herdr/resources/left-arrow.svg`: cheatsheet の `.af`（Affinity）が参照するデザイン素材。symlink 不要。
  - `home/.config/herdr/resources/right-arrow.svg`: 同上。
- 粒度は混在している。whole-dir pair は `nvim` / `raycast/scripts` / `.claude/skills` / `.claude/hooks` の 4 つ。file pair は `ghostty/config` や herdr 配下の個別ファイル（`config.toml` / `scripts/herdr-unread` / `resources/*.af` / `resources/*.png`）。herdr は whole-dir pair ではないため、新規に herdr へ足したファイルは個別 pair か allowlist を要求する。この粒度差こそ reverse テストが吸収すべき対象である。

## アーキテクチャ

既存の forward helper（`missing_symlink_sources`）と対称に、純粋関数とそれを composing する統合テストの型へ揃える。テスト補助は `scripts/tests/bootstrap.bats` 内に置き、既存の SYMLINK_PAIRS テスト群と同居させる。

- `symlink_target_covered`: `file` と可変長 `sources` を受け取り、covered なら 0 を返す純粋関数。ファイル I/O を持たない。covered の定義は「`file` がいずれかの source に一致する（file pair）」または「`file` がいずれかの source の配下にある（dir pair, transitive）」。
- `uncovered_symlink_targets`: 実 `SYMLINK_PAIRS` から source 列を取り、`git ls-files 'home/'` の各ファイルを `symlink_target_covered` に通して未カバーのみを列挙する。
- allowlist: reverse テスト内の test-local な `unmanaged` 配列。`home/` 配下だが意図的に symlink しないファイルを列挙する。各行にコメントで理由を書き自己文書化する。canonical な定義はこの bats 配列であり、本 spec の列挙は設計時点のスナップショットである。
- reverse テスト本体: `uncovered_symlink_targets | sort` と `unmanaged` を sort したものの完全一致を要求する。不一致時は差分を `diff` で出して FAIL する。

既存の forward テスト（`all sources exist` と `missing_symlink_sources` のユニットテスト）はそのまま残す。forward と reverse は別方向の drift を守るため両方必要である。

## coverage 判定ロジック

`symlink_target_covered "$file" "${sources[@]}"` の判定は各 source について以下を順に見る。

1. `file` が source と完全一致 → covered（file pair）。
2. `file` が `source/` の配下（パターン `"$source"/*`） → covered（dir pair の transitive）。

`"$source"/*` の末尾 `/` が prefix 誤爆を防ぐ境界である。source `home/.config/ghostty/config` は `home/.config/ghostty/config-backup` を配下と誤認しない（後者は `.../config/` で始まらないため）。この境界を negative case で pin する。

## allowlist の扱い

allowlist は「home/ 配下だが意図的に symlink しないファイル」という principle を表す。現時点の該当は前述 6 件。新たに symlink しないファイル（別テンプレや別の生成物）を足すときは、pair を書く代わりに allowlist へ理由付きで 1 行足す。逆に allowlist の対象を後で symlink 管理へ移したら、pair を足すと同時に allowlist から消す。どちらの片手落ちも集合不一致で FAIL する。

## 削除するもの

`@test "SYMLINK_PAIRS: manages the Ghostty config"`（ghostty literal pin）を削除する。reverse テストが ghostty の管理を一般的に包含するため。

## テスト戦略

仕様としてのテストを徹底し TDD で進める。

- `symlink_target_covered` の純粋ユニットテスト。covered（exact 一致 / dir 配下の transitive）と uncovered（どの source にも属さない）と prefix 誤爆（`ghostty/config-backup` を `ghostty/config` の配下と誤認しない）を両方向で検証する。exact な真偽まで確かめ、弱い assertion にしない。
- reverse-drift テスト本体。現状の repo で未カバー集合が allowlist と完全一致し green になること。
- 変異注入で pin の有効性を確認する（CLAUDE.md MUST）。同一ファイルに未コミット編集があるため復元は `git checkout` ではなくバックアップ復元か変異箇所のみ戻す。
  - (a) `SYMLINK_PAIRS` から ghostty pair を一時削除 → `home/.config/ghostty/config` が未カバーに現れ reverse テストが FAIL する（ghostty 保護が literal pin 無しでも効くことの確認）。
  - (b) `home/` にダミーの未配線ファイルを一時作成 → 未カバーに現れ FAIL する。
  - (c) `unmanaged` から 1 件削除 → 集合不一致で FAIL する。

## 受け入れ基準

- 現状の repo で reverse-drift テストが green（未カバー集合 == allowlist）。
- 上記 3 種の変異注入で確実に FAIL する。
- 既存 forward テストと nvim/palette 等の全 bats が引き続き green（回帰なし）。
- pre-commit（ast-grep scan / ast-grep test / shellcheck）が green。
- ghostty literal pin 削除後も、ghostty pair を外す変異で reverse テストが FAIL することで ghostty 保護の継続を確認する。

## スコープ外と既知のトレードオフ

- ghostty の pair とファイルを両方削除する操作は意図的な「管理をやめる」判断とみなし、reverse テストはブロックしない（file が無ければ未カバーも発生しない）。小規模リポで後方互換性の破壊をためらわない方針に沿う。
- `scripts/` 配下の非 mirror ファイル（tests / tirith-hook 等）は reverse 検査の対象にしない。mirror 規約が成り立たないため。
- allowlist は明示的な保守を要する。ただし 6 件と小さく各行が自己文書化されるため、暗黙の glob 除外より透明性が高いというトレードオフを受容する。
