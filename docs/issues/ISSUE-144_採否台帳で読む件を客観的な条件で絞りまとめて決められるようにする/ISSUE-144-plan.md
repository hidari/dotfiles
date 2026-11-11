# ISSUE-144 実装計画: 採否台帳で読む件を客観的な条件で絞りまとめて決められるようにする

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Goal: 台帳ページに昇格の条件・確かめ済みとモデルの判断の2群表示・まとめての判断を足し、組み立ての一式をテスト付きで追跡下へ移す。

Architecture: 組み立て (Python) がデータに確かめ済みの印を付けてページへ埋め込む。ページの判定は純粋関数の `logic.js` に寄せて `node --test` で固め、DOM と保存先の配線は `script.js` に残す。保存先の偽物を差し込んだページを Playwright で1経路通す。

Tech Stack: Python 3.12 (標準ライブラリのみ、テストは pytest / ruff / mypy、uv)、素の JavaScript (ビルド無し)、node:test、Playwright (台帳のディレクトリに閉じた pnpm の devDependency)。

Spec: `docs/issues/ISSUE-144_採否台帳で読む件を客観的な条件で絞りまとめて決められるようにする/ISSUE-144-spec.md`

## Global Constraints

- dotfiles は PUBLIC。ユーザーのメモ (`decisions` の `note`) を追跡下・ログ・コミット・PR 本文に出さない
- 既存の ID は振り直さない。既存の件の欄は、確かめ済みの印を足す以外に変えない
- 台帳のデータは追跡しない。置き場は `.hidari/ledger/items.json` (`.hidari/` は ignore 済み)
- Python は標準ライブラリだけ。JS の依存は Playwright だけで、`scripts/knowledge-ledger/` の package.json に閉じ、pnpm で入れる。E2E は手元だけで回し CI に載せない
- コード内のコメントは日本語、外に見える UI の文言は今のページと同じく日本語のまま (このページの読み手はユーザー本人)
- 日本語の散文を Bash のコマンド文字列に載せない。コミット本文は Write で `.cache/` に書いて `-F` で渡す
- Artifact (台帳ページ) は別のアカウントが持っている。Artifact に触る作業 (タスク 6) は持ち主のアカウントのセッションで行う

## Review Focus

- 既存の25件の判断は `decidedAt` を持たない。`updatedAt` で代えたうえで、`appended` (タイムゾーンの無い日付) と UTC の ISO 時刻を比べる箇所で日付がずれないこと。ブラウザのローカル日付に直して比べる (タスク 3 の `needs_review` のテスト)
- 選んでから付けるまでのあいだに、別の端末の判断が届いて対象が判断済みになる。対象は付ける瞬間の判断で決め直す (タスク 3 の `bulk_targets`、タスク 4 で呼ぶ位置)
- 保存先に繋がらない、または書けない表示でまとめての判断を押す。ボタンを無効にし、控えに積まない (タスク 4)
- 条件の文書が無い・壊れている・知らない欄を持つ。落ちずに「条件なし」として扱い、知らない述語を持つ節は昇格させず警告を出す (タスク 3 の `parse_conditions`)
- 引用の参照先が組み立ての時点で消えている、札が0個。どちらもカードが壊れず、群の中身が空のときは群ごと出さない (タスク 2 と 3)

## ファイルの配置

- Create `scripts/knowledge-ledger/pyproject.toml` — 他の `scripts/*` と同じ形 (hatchling、dev に pytest / ruff / mypy、mypy strict)
- Create `scripts/knowledge-ledger/src/knowledge_ledger/build.py` — ページの組み立て (今の `build.py`)
- Create `scripts/knowledge-ledger/src/knowledge_ledger/merge.py` — 増分の取り込み (今の `merge.py`)
- Create `scripts/knowledge-ledger/src/knowledge_ledger/delta.py` — 仕分けの差分から増分を作る (今の `delta.py`)
- Create `scripts/knowledge-ledger/src/knowledge_ledger/verify.py` — 確かめ済みの印
- Create `scripts/knowledge-ledger/page/head.html`、`page/logic.js`、`page/script.js` — 雛形
- Create `scripts/knowledge-ledger/tests/` (pytest) と `scripts/knowledge-ledger/page/logic.test.cjs` (node:test)
- Create `scripts/knowledge-ledger/e2e/` (Playwright) と `scripts/knowledge-ledger/package.json`
- Modify `.pre-commit-config.yaml` と `.github/workflows/test.yml` — 他の `scripts/*` の hook と job の形に揃える

### Task 1: 組み立ての一式を追跡下へ移し、今の出力を変えないことを固める

Files:
- Create: `scripts/knowledge-ledger/` の pyproject・src の3本・`page/head.html`・`page/script.js`・`tests/test_build.py`・`tests/test_merge.py`・`tests/test_delta.py`
- Modify: `.pre-commit-config.yaml`、`.github/workflows/test.yml`
- Move: `.cache/ledger/items-new.json` → `.hidari/ledger/items.json`

Interfaces:
- Produces: `build.build_page(items: list[dict], head: str, scripts: list[str]) -> str`、CLI `python -m knowledge_ledger.build <items.json> <out.html>`。`merge.main(argv)` と `delta.main(argv)` は今の引数に `--today YYYY-MM-DD` を足す (`TODAY` の直書きをやめる)

- [ ] Step 1: `.cache/ledger/` の5本 (`build.py` / `merge.py` / `delta.py` / `part-head.html` / `part-script.js`) を全文読む。追跡下へ入れる前の決まり。読んだら `commit-and-pr-message` の入口で5本を漏洩検査し rc 0 を確かめる
- [ ] Step 2: 回帰の基準を取る。今の `build.py` で `items-new.json` から組んだページのハッシュを `.cache/` に控え、`.cache/ledger/page.html` と一致することを確かめる
- [ ] Step 3: 失敗するテストを書く。`test_build.py`: `test_build_page_matches_legacy_output` (固定の小さな items と雛形で、今の `build.py` と同じ文字列を返す)、`test_build_page_escapes_lt` (`<` が `<` になる)、`test_build_page_rejects_duplicate_ids`、`test_build_page_rejects_script_close_in_template`。`test_merge.py`: 既存の件がバイト単位で不変、追記で `report_count` が子の数だけ増え `appended` が `--today` になる、quote が参照先に無ければ none へ落ちる。`test_delta.py`: 今の docstring の3規則 (新しい最上位の箇条、既存の箇条への子、台帳に無い箇条への子) を小さな git リポジトリの fixture で1件ずつ。fixture のリポジトリには identity を書く (CI に git identity は無い)
- [ ] Step 4: `uv run --directory scripts/knowledge-ledger pytest -q` で赤を確かめる
- [ ] Step 5: 3本を `src/knowledge_ledger/` へ移し、テストが呼べる関数と `main(argv)` に分ける。雛形は `page/` へ改名して移す。中身の振る舞いは変えない
- [ ] Step 6: テストの緑と、Step 2 のハッシュと新しい CLI の出力の一致を確かめる
- [ ] Step 7: データを `.hidari/ledger/items.json` へ移し、`git check-ignore -v .hidari/ledger/items.json` で ignore されていることを確かめる
- [ ] Step 8: pre-commit に ruff check / ruff format --check / mypy / pytest の4つ、CI に同じ4つの job を、`scripts/mise-update-notifier` の形を写して足す。新しい hook は untracked のあいだ Skipped になるので、`git add` してから `pre-commit run --files` で Passed の件数を数える
- [ ] Step 9: コミット

### Task 2: 確かめ済みの印を組み立てで付ける

Files:
- Create: `scripts/knowledge-ledger/src/knowledge_ledger/verify.py`、`tests/test_verify.py`
- Modify: `src/knowledge_ledger/build.py` (埋め込む前に印を付ける)

Interfaces:
- Consumes: Task 1 の `build_page`
- Produces: `verify_item(item: dict, read_ref: Callable[[str], str | None]) -> dict` が返すのは `{"labels_ok": list[str], "labels_ng": list[str], "quote_ok": bool}`。build はこれを各件の `verified` 欄に入れる。`read_ref` は `covered.path` を読んで中身を返し、読めなければ None (`~/` 始まりはホーム、それ以外はリポジトリのルートから)

- [ ] Step 1: 失敗するテストを書く。`test_labels_checked_against_text_and_basis` (札が `basis` にだけ在っても ok)、`test_label_missing_goes_ng`、`test_quote_ok_only_when_ref_contains_quote`、`test_quote_ng_when_ref_unreadable` (read_ref が None)、`test_no_quote_means_quote_ok_false`、`test_zero_labels` (両方の列が空)。`~/.claude` 配下を指す引用は read_ref の偽物で代える
- [ ] Step 2: 赤を確かめる
- [ ] Step 3: 実装する。照らす原文は `text` と `basis` を改行で繋いだもの (`reports` は含めない。spec の実測の前提と同じ)
- [ ] Step 4: 緑を確かめる。加えて実データで数え、`labels_ng` の合計が2、`quote_ok` が290であることを確かめる (spec の実測の前提)。数が違えば止めて報告する
- [ ] Step 5: コミット

### Task 3: ページの判定を純粋関数にする

Files:
- Create: `scripts/knowledge-ledger/page/logic.js`、`page/logic.test.cjs`
- Modify: `src/knowledge_ledger/build.py` (`logic.js` を `script.js` の前に埋める)

Interfaces:
- Produces (`logic.js` はグローバル `LedgerLogic` を定義し、`module` があれば `module.exports` にも入れる):
  - `parseConditions(raw) -> {clauses: Clause[], warnings: string[]}`。`Clause = {preds: Pred[]}`、`Pred = {field, op, value, negate}`。field と op の組は `issue:eq`、`section:eq`、`added:gte`、`appended:exists`、`appended:gte`、`label:has` (札の完全一致)、`report_count:gte` の7つだけ
  - `promoted(item, clauses) -> boolean` — どれかの節の全述語を満たせば true。知らない述語を持つ節は false
  - `localDate(iso: string) -> "YYYY-MM-DD"` — 実行環境のローカル日付
  - `needsReview(item, decisionDoc) -> boolean` — 判断があり、`item.appended` が `localDate(decidedAt ?? updatedAt)` より後
  - `inDefaultList(item, decisionDoc, clauses) -> boolean` — 節が0個なら未判断の全件。そうでなければ (昇格かつ未判断) または needsReview
  - `bulkTargets(selectedIds, decisionOf) -> {apply: string[], skipped: string[]}` — 付ける瞬間の判断で分ける
  - `undoTargets(lastBulk) -> string[]` — 直前のまとめての判断で付けた件だけ
  - `cardGroups(item) -> {verified: Entry[], model: Entry[]}` — 振り分けは spec の「カードの見せ方」節。`report_count` は model。`verified.labels_ng` の札と、`quote_ok` が false の引用は model
  - `conditionCounts(items, clauses) -> number[]` — 節ごとの該当件数

- [ ] Step 1: 失敗するテストを書く。各関数に正常・境界・否定を1つずつ。必ず入れるもの: 和と積の区別 (2節のどちらかで昇格、1節の2述語は両方要る)、`negate` で `label:has 推測` を外す、知らない field の節が昇格させず warnings に載る、`raw` が null・配列でない・壊れた JSON の文字列で落ちない、節0個で未判断の全件、`needsReview` が `decidedAt` を `updatedAt` より優先し、両方無ければ false。`localDate` は `TZ=Asia/Tokyo` と `TZ=UTC` で `2026-11-10T16:00:00Z` がそれぞれ `2026-11-11` と `2026-11-10` を返す (テストは TZ を変えた子プロセスで回す)。`bulkTargets` は判断済みを skipped へ、`cardGroups` は札0個と引用無しで空の列を返す
- [ ] Step 2: `node --test scripts/knowledge-ledger/page/logic.test.cjs` で赤を確かめる (ディレクトリではなくファイルを渡す)
- [ ] Step 3: 実装する
- [ ] Step 4: 緑を確かめ、pre-commit と CI に `node --test` の hook と job を足す (node は mise の pin を使う)
- [ ] Step 5: コミット

### Task 4: ページに条件・2群・まとめての判断を配線する

Files:
- Modify: `scripts/knowledge-ledger/page/script.js`、`page/head.html`

Interfaces:
- Consumes: Task 3 の全関数、Task 2 の `verified` 欄
- Produces: 保存先の形。`decisions/<id>` に `decidedAt` (判断を変えたときと「このままでよい」のときだけ進む ISO 時刻) を足す。条件は `settings/promotion` の文書に `{clauses, updatedAt}` で置く。E2E が引く要素の id は `cond-editor`、`cond-add`、`cond-save`、`show-stored`、`select-page`、`bulk-bar`、`bulk-count`、`bulk-adopt`、`bulk-hold`、`bulk-reject`、`bulk-undo`、`bulk-skipped`、カードの選択は `data-select` 属性を持つ checkbox

- [ ] Step 1: 既定の一覧を `inDefaultList` に替え、`show-stored` (保管中も含める) を足す。保管中のカードには「保管中 (判断していない)」と出す。節0個のときは一覧の上に「昇格の条件がまだありません」と出す
- [ ] Step 2: 条件の編集 UI を足す。節の追加・削除、述語の追加・削除、節ごとの該当件数 (`conditionCounts`)。保存は `settings/promotion` への1回の書き込みで、書けない表示では編集を無効にする
- [ ] Step 3: カードを `cardGroups` で2群に描く。群の見出しは「原文に在る」と「モデルの判断」。中身が空の群は出さない
- [ ] Step 4: 選択とまとめての判断を足す。押した瞬間に `bulkTargets` を呼び、apply の件だけ今の `change()` に通す (メモは送らない)。skipped の件数を `bulk-skipped` に出す。取り消しは `undoTargets` の件に `{decision: null}` を送る。書けない表示ではまとめてのボタンを無効にする
- [ ] Step 5: `writeOnce` と `change` に `decidedAt` を通し、判断の後に追記があった件に「このままでよい」を足す (`decidedAt` だけを送る)。既存のメモの保存が `decidedAt` を進めないこと
- [ ] Step 6: 実データで組み、手元の file:// で開いて閲覧だけの状態が壊れていないことを1回見る (保存先は無いので書き込みは試さない)
- [ ] Step 7: コミット

### Task 5: E2E で決定的な経路を1本通す

Files:
- Create: `scripts/knowledge-ledger/package.json`、`pnpm-lock.yaml`、`playwright.config.ts`、`e2e/fake-db.js`、`e2e/ledger.spec.ts`

Interfaces:
- Consumes: Task 4 の要素の id と保存先の形
- Produces: `e2e/fake-db.js` は `window.claude = {use}` を定義し、`use("db")` が `collection(name).doc(id)` の `get / set / update`、`collection(name).onSnapshot(cb)` を持つメモリ上の偽物を返す。書き込みは `window.__writes` に `{path, fields}` で積む。`use("user")` は `can("data.write")` が true

- [ ] Step 1: `~/.claude/references/testing.md` の「E2E の生成」節に従い、`pnpm exec playwright init-agents --loop=claude` で Test Agents を用意する
- [ ] Step 2: 偽物を書き、10件の fixture (判断済み2件、`appended` 付き1件を含む) で組んだページに `addInitScript` で差し込む
- [ ] Step 3: Planner / Generator で次の経路のテストを作る: 条件 (`report_count:gte 2`) を保存する → 一覧が該当件だけになる → このページの全件を選ぶ → 採らないを付ける → `__writes` に未判断だった件だけが `decision` と `decidedAt` を持って載り、どれも `note` を持たない → `bulk-skipped` が判断済みの件数を出す → 取り消すと付けた件だけに `decision: null` が送られる
- [ ] Step 4: 変異を1つずつ入れて赤を確かめる。`bulkTargets` が skipped を作らない、`undoTargets` が skipped まで戻す、`change` がメモを送る。どれも戻したら緑
- [ ] Step 5: コミット

### Task 6: 持ち主のアカウントで公開し、一致率を数える

このタスクは台帳を持つアカウントのセッションで行う。ユーザーが切り替えてから始める。

- [ ] Step 1: `db_rules_get` で台帳の規則を読む。規則が明示されていて `settings` の書き込みを許さないなら、規則を足す案をユーザーに見せて止まる
- [ ] Step 2: `.hidari/ledger/items.json` から組んだページを publish する (`url` を付けて同じ Artifact へ)
- [ ] Step 3: claude.ai で1回だけ手で確かめる。2026-11-10 の手順 (未判断の件で書き、確かめてから消す) を、まとめての判断と取り消しで行う
- [ ] Step 4: `decisions` を読み、判断の値だけを見立て × 置き場の案 × 照合の状態の組ごとに数えて会話でユーザーへ見せる。メモは集計にも出力にも使わない。結果は追跡下に置かない
- [ ] Step 5: ユーザーが昇格の条件の初期値を決める (該当件数を見ながら)

## 完了の前に

- pre-commit を全ファイルで回し、Passed と Skipped を分けて数える
- `.cache/ledger/` の書き捨てを消す (データは `.hidari/ledger/` へ移した後)
- ISSUE-46 のマイルストーンの所属をユーザーに聞く
