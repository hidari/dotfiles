---
name: in-repo-issue
description: リポジトリ内 Markdown (`docs/issues/<NNN>-<slug>/issue.md`) で Issue を起票・更新・分割・クローズする。 「Issue を立てて / 起票して / 作って」「Issue #NNN をクローズして」「この Plan を Issue に紐付けて」「Issue を分割して / 子 Issue にして」と言われたとき、 PR 作成時に Issue リンクを書くとき、 既存 Issue の status / PR 紐付けを更新するときに使う。 GitHub Issues 連携 / `.claude/plans/*` からの Plan 結合はオプションで、 プロジェクト CLAUDE.md の有効化指示に従う。
---

# In-Repo Issue Management

リポジトリ内の Markdown だけで Issue を起票・更新・分割・クローズする skill。
ネットワーク往復 (gh issue) なしで grep ベースのトレーサビリティを担保する。

GitHub Issues との併用や、 ExitPlanMode 後の Plan 永続化フローはオプション機能として末尾節に記述する。

## 用語と構造

| 用語     | 実体                                                       |
|--------|----------------------------------------------------------|
| Issue  | `docs/issues/<NNN>-<sanitized-title>/issue.md`           |
| Plan   | 同ディレクトリ内 `plan.md` (任意、 1 Issue 1 Plan)                  |
| 補助資料   | 同ディレクトリ内 `notes/<name>.md` (任意)                         |
| 番号 NNN | プロジェクト内連番。 新規プロジェクトは 1 から、 既存は max+1                    |
| アーカイブ  | `docs/issues/archive/` (編集禁止、 historical reference)      |
| テンプレ   | `docs/issues/_template/NNN-template/` (コピー元)             |

ファイル名は `issue.md` / `plan.md` で固定。 ディレクトリ名 `<NNN>-<slug>` に番号とタイトルを持たせ、 中身は短い固定名でアクセスを楽にする。

## 初期化 (新規プロジェクト)

`docs/issues/` が存在しないプロジェクトで初めて Issue を立てる場合:

```bash
mkdir -p docs/issues
cp -r ~/.claude/skills/in-repo-issue/_template/NNN-template docs/issues/_template/
```

以降は Phase A で起票する。 番号は 1 から開始。

## いつ使うか

### 必ず使う

- 新規 Issue 起票指示があったとき (「Issue を立てて」「起票して」「作って」)
- 既存 Issue の status 更新・クローズ・PR リンク追加
- PR 本文・コミットメッセージ作成時の Issue リンク確認
- 親 Issue を子 Issue に分割するとき

### オプション (プロジェクト CLAUDE.md で有効化された場合のみ)

- ExitPlanMode 直後に `.claude/plans/*.md` を Issue ディレクトリの `plan.md` に永続化 (「Plan 結合」節)
- GitHub Issues との連携 / 移行 (「GitHub Issues 連携」節)

### 使わない

- typo 修正のような軽微変更
- 1-2 ステップの即時修正で進捗追跡不要なもの
- 調査・質問応答のみのセッション

## ライフサイクル

### Phase A: 起票

A.1 タイトルを決める。 プロジェクトが conventional commits prefix を採用していれば `feat:` `fix:` `improve:` 等を付ける。

A.2 番号を採番する (10 進数強制で 0 prefix の罠を避ける):

```bash
MAX=$(find docs/issues -maxdepth 1 -type d -regex '.*/[0-9]+-.*' \
  | sed -E 's|.*/([0-9]+)-.*|\1|' \
  | sort -n | tail -1)
NEXT=$((10#${MAX:-0} + 1))
echo "next: ${NEXT}"
```

新規プロジェクトで一件もない場合は `NEXT=1` になる。 GitHub Issues 連携プロジェクトで番号衝突を避けたい場合は「GitHub Issues 連携」節の採番ロジックを使う。

A.3 ディレクトリ名を作る。 タイトルから FS-safe 文字列を作って付ける。 サニタイズ規則:

- 置換対象 (→ ハイフン `-`): 半角空白 / 全角空白 / `:` / `/` / `?` / `<` / `>` / `|` / `*` / `"` / `\`
- **保持** (置換しない): 全角括弧 `（）` / 全角句読点 `、` `。` / 半角カンマ `,` / セミコロン `;` / `+` / `_` / `(` `)` / 通常の日本語文字
- **連続ハイフン正規化**: `--+` → `-`
- **末尾整形**: 先頭・末尾の `-_.` を除去
- **長さ制限**: タイトル部分を **Unicode コードポイント単位で 60 文字以内** にカット (バイトではない)。 カット後に末尾の `-_.` を再除去
- 結果が空文字列なら `untitled`

```bash
# 例:
# "feat: 作品詳細ページに SNS シェアボタンを追加"
#   → "feat-作品詳細ページに-SNS-シェアボタンを追加"
# "Stripe アカウント法人切り替え（合同会社 Hermitian）"
#   → "Stripe-アカウント法人切り替え（合同会社-Hermitian）"   (全角括弧は保持)

DIR=docs/issues/${NEXT}-<sanitized-title>
mkdir -p "${DIR}"
```

A.4 テンプレをコピーして frontmatter を埋める:

```bash
cp docs/issues/_template/NNN-template/issue.md "${DIR}/issue.md"
# その後 Edit で frontmatter の placeholder (NNN / title / created_at / updated_at) を実値に置換
```

A.5 frontmatter 必須項目を全て設定する。 特に `status: open / created_at` は欠けると後の grep 検索が壊れる。

A.6 コミット:

```
docs(issues): Issue #NNN <title> を起票
```

例:
```
docs(issues): Issue #1 feat: ユーザープロフィール基盤 を起票
```

### Phase B: 更新

B.1 frontmatter `updated_at` を今日の日付に更新する。 既に今日の値なら no-op (変更不要)。

B.2 status 遷移は `open → in_progress → closed` の順を守る。 飛び越えない。

B.3 in_progress 移行時は実装ブランチ名を frontmatter `branch` に追記すると、 後で「この Issue でどのブランチが動いてた?」がわかる:

```yaml
status: in_progress
branch: feat/<feature-name>
```

B.4 関連 Issue / 関連 PR が判明したら frontmatter `related_issues` / `related_prs` に追記する:

```yaml
related_issues: [12, 18]
related_prs: ["#34", "#41"]
```

B.5 コミット:

```
docs(issues): Issue #NNN を <変更内容> に更新
```

### Phase C: 分割 (親 → 子 Issue)

「Plan が複数必要」「PR が PR-A, PR-B などに分かれる」が分割シグナル。

C.1 子 Issue を Phase A で順次起票する。 タイトルの prefix / scope は親から継承する (例: 親が `improve(test):` なら子も `improve(test):` を使う)。

C.2 子 frontmatter に `parent_issue` を設定:

```yaml
parent_issue: 5
```

C.3 親 frontmatter `child_issues` に子番号を全部追記:

```yaml
child_issues: [6, 7]
```

C.4 子 frontmatter `related_issues` に兄弟番号を入れる (親は parent_issue で表現済みなので含めない):

```yaml
# 子 Issue #6 の場合
parent_issue: 5
related_issues: [7]   # 兄弟のみ
```

C.5 親 Markdown 末尾に「## 子 Issue」節を追加して各子へのリンクを書く。

C.6 親の `plan.md` は: 子で分担するなら削除 (`git rm`)。 全体俯瞰として残すなら維持。

C.7 コミット:

```
docs(issues): Issue #NNN を子 Issue (#NN1, #NN2) に分割
```

### Phase D: クローズ

D.1 PR がマージされたら frontmatter を全て更新:

```yaml
status: closed
closed_at: YYYY-MM-DD
related_prs: ["#PR番号", ...]
updated_at: YYYY-MM-DD
```

D.2 コミット:

```
docs(issues): Issue #NNN をクローズ (PR #M)
```

D.3 GitHub Issues を併用しているプロジェクトでは GitHub 側 auto-close が走らないため、 必ずこの skill 経由で in-repo を手動 close する (詳細は「GitHub Issues 連携」節)。

## frontmatter スキーマ

### 必須

```yaml
issue_number: 1                       # 整数
title: "<title>"                       # 二重引用符
status: open                           # open / in_progress / closed
created_at: 2026-05-08                 # YYYY-MM-DD
updated_at: 2026-05-08                 # status 変更や PR 追加時に更新
closed_at: null                        # closed のとき YYYY-MM-DD、 それ以外は null
```

### 推奨 (運用が楽になる)

```yaml
priority: 2                            # 0 (即時対応) / 1 (他より優先) / 2 (空いたとき)
parent_issue: null                     # 子 Issue のときのみ整数
child_issues: []                       # 親 Issue のときのみ整数配列
related_issues: []                     # 整数配列
related_prs: []                        # 文字列配列、 例 ["#12"]
branch: null                           # in_progress 時の作業ブランチ名
```

`priority` の決め方:
- 子 Issue 起票時は **親から継承**
- 親が無い / 不明 / 推測手がかりが無い場合は **default 2** (空いたとき)
- GitHub Issues 移行時は label (`priority 0` / `bug` 等) から推測可能なら設定、 そうでなければ default 2

### プロジェクト裁量 (CLAUDE.md で値セットを定義)

```yaml
component: <project-defined>           # 例: frontend / backend / infra
type: <project-defined>                # 例: feature / fix / improve / refactor / docs
source: <project-defined>              # GitHub Issues 併用時のみ。 例: github (移行) / in-repo (新規)
```

**フォーマット注意**:
- YAML の `: ` (コロン+空白) を厳守。 grep で絞り込む生命線
- 文字列値は二重引用符 (`"..."`)。 シングルクォートやクォートなしは禁止
- 配列の空は `[]`、 値ありはフロー形式 `[1, 2]` で統一
- null は文字列 `null` (YAML)

## 検索手順

```bash
# 全 open Issue
grep -lr '^status: open$' docs/issues/*/issue.md

# 特定 component + open
grep -l '^component: frontend$' docs/issues/*/issue.md \
  | xargs grep -l '^status: open$'

# priority 0 全件
grep -lr '^priority: 0$' docs/issues/*/issue.md

# 親 Issue 一覧 (child_issues 非空)
grep -lr '^child_issues:' docs/issues/*/issue.md \
  | xargs grep -L '^child_issues: \[\]$'

# 番号で開く (タイトルが分からなくても良い)
ls docs/issues/5-*/issue.md | head -1

# closed 一覧
grep -lr '^status: closed$' docs/issues/*/issue.md
```

## PR / コミット規約

### コミットメッセージ

```
<prefix>(<scope>): <subject>
```

`<prefix>` はプロジェクトが conventional commits を採用していれば使う (`feat`, `fix`, `improve`, `refactor`, `docs`, `chore`, etc.)。

本文 or subject に `Issue #NNN` を含めて、 後で grep / git log で辿れるようにする。

### PR

PR タイトル (例):
```
<prefix>(<scope>): <subject> (Issue #NNN)
```

PR 本文に必ず Issue 本体への相対リンクを書く:
```markdown
Closes [Issue #NNN](../../docs/issues/NNN-<slug>/issue.md)
```

GitHub Issues を併用しないプロジェクトでも、 PR レビュー時に Issue 本体に飛べるリンクは必須。

## オプション: Plan 結合

プロジェクト CLAUDE.md でこのフローを採用する場合のみ実行する。 採用しないプロジェクトでは Plan は `.claude/plans/` だけに置き、 Issue ディレクトリへコピーしない。

ExitPlanMode 直後、 Claude Code は `.claude/plans/<random-name>.md` に Plan を書き出している。 これを対応 Issue ディレクトリに永続化する。

1. 対応する Issue が無ければ Phase A で起票してから戻る
2. 既に `plan.md` が存在する場合は **Phase C (分割) に進むシグナル**。 同じファイルを上書きしない (既存 Plan を失う)。 同一 Plan の改訂版なら直接 `plan.md` を Edit で更新 (git history で旧版を辿れる)
3. コピー (元の `.claude/plans/*.md` は残す):

   ```bash
   cp .claude/plans/<plan-file>.md docs/issues/<NNN>-*/plan.md
   ```

4. frontmatter `updated_at` を今日の日付に更新する
5. コミット:

   ```
   docs(issues): Issue #NNN に Plan を結合
   ```

## オプション: GitHub Issues 連携

GitHub Issues を併用 / 移行するプロジェクトのみ。 採用しない場合は読み飛ばして良い。

### 採番 (衝突回避)

GitHub Issues 番号と in-repo 番号を共通の連番で運用する場合、 max を取って +1:

```bash
MAX_GH=$(gh issue list --state all --limit 1000 --json number \
  | jq -r 'map(.number) | max // 0')
MAX_LOCAL=$(find docs/issues -maxdepth 1 -type d -regex '.*/[0-9]+-.*' \
  | sed -E 's|.*/([0-9]+)-.*|\1|' | sort -n | tail -1 || echo 0)
GH=${MAX_GH:-0}
LOCAL=${MAX_LOCAL:-0}
NEXT=$(( ( 10#${GH} > 10#${LOCAL} ? 10#${GH} : 10#${LOCAL} ) + 1 ))
```

### 既存 GitHub Issue を in-repo に移行

1. `gh issue view <NNN> --json number,title,body,labels,createdAt,updatedAt` で取得
2. Phase A で `docs/issues/<NNN>-<slug>/issue.md` を作成 (番号は **GitHub Issue 番号と一致** させる)
3. frontmatter `source: github` を付ける。 日付は次のように設定:
   - `created_at`: GitHub 側 `createdAt` (元の作成日) を採用
   - `updated_at`: 移行作業日 (今日)。 移行は frontmatter の構造変更を伴うため updated とみなす
4. **必須**: GitHub 側 Issue に「Migrated to in-repo: docs/issues/NNN-...」コメントを残す。 移行先パスを文字列で書き、 後日 GitHub 側で URL クリックで辿れるようにする
5. **必須**: GitHub 側 Issue を close する。 コマンド:

   ```bash
   gh issue close <NNN> --reason "not planned" \
     --comment "Migrated to in-repo. See comment above for the new location."
   ```

   `--reason "not planned"` を使う (GitHub の選択肢は `completed` / `not planned` の 2 値のみ。 「移行 / move」用 reason は無いため、 「実装としては未完で計画変更 = not planned」を慣例的に採用)

一括移行する場合は `scripts/_oneshot/migrate_issues.py` のような uv スクリプトでまとめて処理する。

### auto-close の代替

GitHub Issues 廃止 / 移行後は GitHub 側 auto-close が走らないため、 PR がマージされたら必ず Phase D で in-repo 側を手動 close する。

PR タイトル / コミットメッセージで `Issue #NNN` 形式を維持しておけば、 GitHub 側 #NNN が closed であっても「Migrated to in-repo」コメントから in-repo に辿れる。

## Red flags / よくある失敗

| 思考の罠                                  | 実態                                                                                       |
|---------------------------------------|------------------------------------------------------------------------------------------|
| 「Plan は別ディレクトリに置きたい」                  | NG。 1 Issue 1 Plan の規約を破ると Plan の在処が散逸し検索性が落ちる。 複数必要な時点で Issue 分割のシグナル                   |
| 「番号は適当でいい」                            | NG。 GitHub Issues 併用プロジェクトでは番号衝突。 単独プロジェクトでも採番が揺れると過去コミット内 `Issue #NNN` の指示先がブレる         |
| 「frontmatter は大体合ってればいい」             | NG。 `status: open` の grep が運用の生命線。 ハイフン / コロン / クォートのフォーマット崩壊で grep が漏れる                 |
| 「PR 本文の Issue 相対リンクは省略 OK」            | NG。 PR レビュー時に Issue 本体に飛べないと未来の自分の認知負荷が上がる                                                |
| 「クローズ時 status だけ更新」                   | NG。 `closed_at` と `related_prs` を必ず埋める。 「この Issue どの PR で消化した?」を後日検索で答えるため               |
| 「テンプレなしで起票」                           | NG。 必ず `_template/NNN-template/issue.md` をコピー。 章欠落で後から書き直す手戻りが多発                          |
| 「子 Issue 起票時に親の child_issues 更新を忘れる」 | NG。 親→子の片方向リンクだけだと「親はこれ?」を grep で逆引きできない                                                 |
| 「複数 Plan を 1 Issue に並列で書く」            | NG。 Phase C で分割するシグナル。 親が肥大化すると「結局何の Issue?」が分からなくなる                                     |
| 「採番に bash 算術で `$((007 + 1))`」         | NG。 0 prefix は 8 進数解釈で `value too great for base` エラー。 `$((10#${MAX} + 1))` で 10 進強制   |
| 「ファイル名を `Issue_NNN_*.md` のままにしたい」     | NG。 ディレクトリ名 `<NNN>-<slug>` に番号があるので冗長。 内側は固定名 `issue.md` / `plan.md`                     |
| 「Plan 結合は全プロジェクトで必須」                  | NG。 これはオプション。 `.claude/plans/` をワーキングディレクトリとして使うか、 Issue 永続化するかはプロジェクト CLAUDE.md で宣言する  |

## 関連

- `git-branch-switcher`: Issue 起票後、 必ずブランチ作成
- `pre-merge-quality-gate`: PR マージ前、 `status: closed` 更新と PR リンク追加が完了していること
- `empirical-prompt-tuning`: この skill 自体をチューニングするとき
- プロジェクト `CLAUDE.md` — Plan 結合 / GitHub Issues 連携を有効化するか、 `component` / `type` / `source` の値セットを定義
