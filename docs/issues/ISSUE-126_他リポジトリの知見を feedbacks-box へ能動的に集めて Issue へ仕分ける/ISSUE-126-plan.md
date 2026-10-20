# ISSUE-126 知見の収集と仕分け Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 他リポジトリのセッションが作業の区切りで知見のまとめを自リポジトリの `.cache/` に残し、セッションの終わりに hook が dotfiles の受け箱へ届け、dotfiles のセッションが main の in-repo Issue へ仕分ける。

**Architecture:** 送る側は user スコープの hook 1本 (`feedbacks-outbox.py`) が SessionStart / Stop / SessionEnd の3つの契機を受け持ち、まとめの書式は agentic-coding-tools の skill `cross-repo-learnings` が持つ。受け取る側は既存の `feedbacks-box.py` の告知の文面を、worktree で起票して PR をマージする手順へ変える。

**Tech Stack:** Python 3 (標準ライブラリのみ)、pytest (`uv run --directory scripts/claude-hooks pytest`)、git reflog、Claude Code hooks、apm。

**Spec:** `docs/issues/ISSUE-126_他リポジトリの知見を feedbacks-box へ能動的に集めて Issue へ仕分ける/ISSUE-126-spec.md`

## Global Constraints

- hook は fail-safe。hook として呼ばれる経路は、例外でも無出力と exit 0
- hook の出力は `hookSpecificOutput.additionalContext` の形だけを使い、`decision: block` は出さない
- 外から来た文字列 (リポジトリ名、ファイル名、パス) を告知へ載せるときは `json.dumps(..., ensure_ascii=False)` で引用する
- skill にも settings.json にも絶対パスを書かない。箱の位置は hook が自分の実体の位置から導く
- 受け箱を持つリポジトリ (main checkout に `docs/.feedbacks-box/` が実在する) では、送る側の hook は何もしない
- subagent (`agent_id` を持つ payload) では何もしない
- hook 本体と `home/.claude/settings.json` の配線は同じコミットに入れる。本体は mode 755
- コードのコメントは日本語。ログと告知の文面も日本語
- 常時ロード層 (CLAUDE.md) には何も足さない
- 新しい文面は数字の前後に空白を入れない

## Review Focus

- ブランチの切り替え・pull・rebase・amend の直後の Stop: 新しいコミットではないので案内しない (Task 3 の reflog 種別のテスト)
- hook を入れる前から続いているセッション (SessionStart の記録が無い) の Stop: 例外にせず、その時点を基準にして案内しない (Task 3)
- SessionEnd が来なかったセッションのまとめ: 同じリポジトリの次の SessionStart で届き、二重に届かない (Task 4)
- 箱を持たない環境 (dotfiles の作業ツリーに `docs/.feedbacks-box/` が無い): まとめを消さずに残す (Task 4)
- 並行する dotfiles のセッション: 仕分け中のまとめは、もう一方のセッションの告知に未処理として出ない (Task 5)

## ファイル構成

- Create: `home/.claude/hooks/feedbacks-outbox.py` 送る側の hook。サブコマンド `session` / `stop` / `end`
- Create: `scripts/claude-hooks/tests/test_feedbacks_outbox.py`
- Modify: `home/.claude/hooks/feedbacks-box.py` 受け取る側の告知の文面と、仕分け中の一覧
- Modify: `scripts/claude-hooks/tests/test_feedbacks_box.py`
- Modify: `home/.claude/settings.json` SessionStart / Stop / SessionEnd へ配線
- agentic-coding-tools 側 Create: `skills/meta/cross-repo-learnings/SKILL.md` と `template.md`
- Modify: `home/apm.yml` と `home/apm.lock.yaml` (pin の更新)

### Task 0: 実装前の実測 (コントローラが行う)

hook の形を決める前提を、インストール済みの Claude Code で確かめる。結果は plan の末尾の「実測の記録」へ書き、食い違えば Task 3 以降を直してから進む。

- [ ] **Step 1:** Stop hook が `hookSpecificOutput.additionalContext` を返したとき、会話が続き、hook のエラー通知が出ないことを確かめる。`.cache/` に置いた使い捨てのリポジトリで、`.claude/settings.local.json` にプローブの hook を配線し、`claude -p` の別プロセスで観測する (user の settings.json は触らない)
- [ ] **Step 2:** 同じ Stop に `decision: block` を返す hook と additionalContext を返す hook が並んだとき、両方の文面が Claude に届くことを確かめる
- [ ] **Step 3:** Workflow の子が Stop を発火させるか、発火するならその payload に `agent_id` があるかを、payload をファイルへ追記するだけのプローブで確かめる。`agent_id` で見分けられなければ、見分けに使えるフィールドを payload から探し、Task 3 の除外条件へ足す
- [ ] **Step 4:** SessionEnd の payload に `session_id` と `cwd` があることを確かめる
- [ ] **Step 5:** 結果を「実測の記録」へ書いてコミットする

### Task 1: 送る側の hook の骨格と除外の判定

**Files:**
- Create: `home/.claude/hooks/feedbacks-outbox.py`
- Create: `scripts/claude-hooks/tests/test_feedbacks_outbox.py`
- Modify: `home/.claude/settings.json`

**Interfaces:**
- Produces:
  - `SKILL_NAME = "cross-repo-learnings"`
  - `OUTBOX_RELATIVE = Path(".cache") / "feedbacks-outbox"` (リポジトリルートから見たまとめの置き場)
  - `dotfiles_box() -> Path` 自分の実体 (`Path(__file__).resolve()`) から辿った dotfiles の `docs/.feedbacks-box`
  - `outbox_path(cwd: str, session_id: str) -> Path` `hook_git.repo_root(cwd) / OUTBOX_RELATIVE / f"{_sanitize(session_id)}.md"`
  - `active(payload: dict[str, Any]) -> Path | None` hook が動いてよいならリポジトリルートを、だめなら None を返す
  - `skill_installed() -> bool` `CLAUDE_CONFIG_DIR` (無ければ `~/.claude`) の `skills/cross-repo-learnings/SKILL.md` が実在するか
  - `main(argv: list[str]) -> int` 第1引数でサブコマンドへ分ける

- [ ] **Step 1: 除外のテストを書く**

`active` が None を返す場合をすべて pin する: `agent_id` を持つ payload、`cwd` が無いか実在しない、cwd のリポジトリの main checkout に `docs/.feedbacks-box/` がある、skill が入っていない (環境変数 `CLAUDE_CONFIG_DIR` を tmp に向けて SKILL.md を置かない)。対照として、すべての条件を満たしたときにリポジトリルートを返すテストを置く。`dotfiles_box()` がこのリポジトリの `docs/.feedbacks-box` を指すことを literal のパスで pin する。

起動形のテスト: subprocess で `feedbacks-outbox.py session` / `stop` / `end` に壊れた JSON と未知のサブコマンドを渡し、どれも exit 0 で無出力。

- [ ] **Step 2: 実行して落ちることを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest -q tests/test_feedbacks_outbox.py`
Expected: FAIL (ファイルが無い)

- [ ] **Step 3: 骨格を実装し、mode 755 にして settings.json へ配線する**

SessionStart (`matcher: "*"`) に `python3 "$HOME/.claude/hooks/feedbacks-outbox.py" session`、Stop に `... stop`、SessionEnd に `... end`。どれも `timeout` は既存の hook に合わせる。この段階ではサブコマンドの本体は何もしない。`_sanitize` は handoff-sentinel の `_sanitize` と同じ文字集合にする (共通化は ISSUE-26 の範囲なのでここではしない)。

- [ ] **Step 4: 実行して通ることを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest -q` と `uv run --directory scripts/config-guard config-guard scan` (コマンドの正確な形は `.pre-commit-config.yaml` の config-guard の entry に従う)
Expected: 全件 PASS、config-guard の検出 0 件

- [ ] **Step 5: コミット**

### Task 2: SessionStart で置き場を伝える

**Files:**
- Modify: `home/.claude/hooks/feedbacks-outbox.py`
- Modify: `scripts/claude-hooks/tests/test_feedbacks_outbox.py`

**Interfaces:**
- Consumes: `active`, `outbox_path`, `SKILL_NAME`
- Produces: `handle_session(payload: dict[str, Any]) -> dict[str, Any] | None`。副作用として状態ファイルへ基準時刻を記録する (Task 3 が読む)
  - 状態の置き場: 環境変数 `FEEDBACKS_OUTBOX_STATE_DIR`、無ければ `~/.cache/claude/feedbacks-outbox/`。ファイルは `<_sanitize(session_id)>.json` で、中身は `{"since": <unix 秒>, "nudges": <int>, "outbox": "<まとめの絶対パス>", "repo": "<_sanitize したリポジトリ名>"}`。`outbox` と `repo` は SessionEnd が git を起動せずに済むように記録する

- [ ] **Step 1: テストを書く**

- `test_置き場とskill名を告げる`: additionalContext に `json.dumps(str(outbox_path(...)))` の文字列と `cross-repo-learnings` が含まれる
- `test_基準時刻を記録する`: 実行後に状態ファイルがあり、`since` が実行前後の時刻のあいだで、`outbox` と `repo` が告げた置き場とリポジトリ名に一致する
- `test_compactやresumeで再実行しても基準時刻を巻き戻さない`: 状態ファイルが既にあれば `since` と `nudges` を保つ
- `test_除外の条件では何も告げず状態も作らない`: `active` が None の payload で、出力が None で状態ファイルが無い

- [ ] **Step 2: 落ちることを確かめる** (Run は Task 1 と同じ。Expected: 4件 FAIL)

- [ ] **Step 3: `handle_session` を実装する**

告知の文面は次の内容を持つ: このセッションのまとめの置き場 (引用したパス)、リポジトリを越えて効く知見が出たら `cross-repo-learnings` skill でそこを更新すること、ユーザーが dotfiles へ送ってと頼んだときも同じ場所へ書くこと、セッションの終わりに hook が届けるので箱へ直接書かないこと。

- [ ] **Step 4: 通ることを確かめる**
- [ ] **Step 5: コミット**

### Task 3: Stop でコミットのあとに案内する

**Files:**
- Modify: `home/.claude/hooks/feedbacks-outbox.py`
- Modify: `scripts/claude-hooks/tests/test_feedbacks_outbox.py`

**Interfaces:**
- Consumes: Task 2 の状態ファイル
- Produces:
  - `MAX_NUDGES = 3`
  - `commits_since(repo_root: Path, since: int) -> list[int]` HEAD の reflog のうち、件名が `commit:` / `commit (initial):` / `commit (merge):` で始まり、時刻が `since` より後のものの unix 秒。`commit (amend):`、`checkout:`、`pull`、`rebase`、`reset`、`merge` (fast-forward) は数えない
  - `handle_stop(payload: dict[str, Any]) -> dict[str, Any] | None`

- [ ] **Step 1: テストを書く**

`make_git_repo` で作ったリポジトリに実際に commit / checkout / amend / reset を打って reflog を作る。
- `test_基準のあとのコミットで案内する`
- `test_基準より前のコミットでは案内しない`
- `test_ブランチの切り替えだけでは案内しない`
- `test_amendだけでは案内しない`
- `test_resetだけでは案内しない`
- `test_案内したコミットでは二度案内しない`: 1回目の案内のあと、新しいコミットが無ければ2回目は None
- `test_新しいコミットがあれば再び案内する`
- `test_案内はMAX_NUDGES回まで`
- `test_stop_hook_activeでは判定せず状態も変えない`: 状態ファイルが実行前後でバイト単位で同じ
- `test_状態が無ければ基準を作るだけで案内しない`: hook を入れる前から続いているセッション
- 案内の文面に、まとめの置き場の引用したパスと `cross-repo-learnings` と「知見が無ければ何もしない」趣旨が含まれる

- [ ] **Step 2: 落ちることを確かめる**
- [ ] **Step 3: 実装する**

reflog は `git -C <repo_root> log -g --date=unix --format=%gd%x09%gs HEAD` を `hook_git` の隔離環境 (`isolated_env()`) とタイムアウト (`RESOLVE_TIMEOUT`) で読む。`%gd` は `HEAD@{<unix 秒>}` になる。案内したら `since` を数えたうち最新の時刻へ進め、`nudges` を1増やす。

- [ ] **Step 4: 通ることを確かめる**
- [ ] **Step 5: 変異注入**: 件名の判定から `commit (amend)` の除外を外す、`stop_hook_active` の早期 return を外す、`MAX_NUDGES` の判定を外す。それぞれ1箇所ずつ入れて、対応するテストが赤になることを確かめて戻す
- [ ] **Step 6: コミット**

### Task 4: SessionEnd と次の SessionStart で箱へ届ける

**Files:**
- Modify: `home/.claude/hooks/feedbacks-outbox.py`
- Modify: `scripts/claude-hooks/tests/test_feedbacks_outbox.py`

**Interfaces:**
- Consumes: `active`, `outbox_path`, `dotfiles_box`
- Produces:
  - `deliver(outbox: Path, box: Path, repo_name: str, today: str) -> Path | None` まとめを `box / f"from-{repo_name}-{today}-{outbox.stem[:8]}.md"` へ書き、成功したら outbox を消して書いた先を返す。box が無ければ何もせず None
  - `handle_end(payload: dict[str, Any]) -> None` 状態ファイルの `outbox` と `repo` を使って、このセッションのまとめを届ける
  - `handle_session` は Task 2 の処理の前に、同じリポジトリの outbox にある他のセッションのまとめを届ける
  - `repo_name` は main checkout のディレクトリ名を `_sanitize` したもの。`today` は UTC の `YYYY-MM-DD`

- [ ] **Step 1: テストを書く**

`dotfiles_box` はテストでは monkeypatch せず、`deliver` に box を引数で渡して検査する。`handle_end` と `handle_session` の箱の位置は環境変数 `FEEDBACKS_BOX_DIR` で上書きできるようにし、テストは tmp を指す。
- `test_まとめを箱へ届けて元を消す`: 届いたファイルの中身が元とバイト単位で同じ
- `test_まとめが無ければ何もしない`
- `test_箱が無ければまとめを残す`
- `test_同名のファイルが箱にあれば上書きしない`: 届けずに outbox を残す
- `test_次のSessionStartで取り残しを届ける`: 他の session_id のまとめが届き、今のセッションのまとめは届かない
- `test_二重に届けない`: `handle_end` を2回呼んでも箱のファイルは1つ
- `test_空のまとめは届けずに消す`

- [ ] **Step 2: 落ちることを確かめる**
- [ ] **Step 3: 実装する**

書き込みは箱の中の一時ファイルへ書いてから `os.replace` で名前を付ける。受け取る側が書きかけを読まないため。SessionEnd の持ち時間は短いので、`handle_end` はファイルのコピー以外のことをしない (git を起動しない)。そのため `handle_end` は `active` を通さず、`agent_id` の除外と、状態ファイルと outbox の実在だけを見る。状態ファイルが無ければ何もしない (次の SessionStart の回収に任せる)。テストに `test_SessionEndはgitを起動しない` を足す (PATH を空のディレクトリに向けても届く)。

- [ ] **Step 4: 通ることを確かめる**
- [ ] **Step 5: 変異注入**: `os.replace` の前の存在確認を外す (同名上書きのテストが赤)、取り残しの回収で今のセッションを除く条件を外す
- [ ] **Step 6: コミット**

### Task 5: 受け取る側の告知を仕分けの手順へ変える

**Files:**
- Modify: `home/.claude/hooks/feedbacks-box.py`
- Modify: `scripts/claude-hooks/tests/test_feedbacks_box.py`

**Interfaces:**
- Produces:
  - `CLAIMED_DIRNAME = ".in-progress"` 仕分けに取りかかったまとめを rename で移す先 (箱の直下)
  - `claimed(box: Path) -> list[str]` 仕分け中の名前の一覧
  - `notice(box: Path, names: list[str], in_progress: list[str]) -> str`

- [ ] **Step 1: テストを書く**
- `test_仕分け中のものは未処理に数えない`: `.in-progress/` の中のファイルは `pending` に出ない (既存のドット除外で満たされるが、仕様として pin する)
- `test_仕分け中のものは別の一覧で告げる`: 未処理が0件でも仕分け中があれば告げる (取りかかったセッションが落ちたときに見えるように)
- `test_告知は仕分けの手順を持つ`: 文面に次の語句が含まれる。`.in-progress` へ移してから取りかかること、main から切った worktree、in-repo Issue だけが出口でメモリへは入れないこと、マージ前のレビューで漏洩スイープに元のまとめも渡すこと、マージしてから消すこと
- 既存のテストのうち文面に依存するもの (「in-repo Issue かメモリ」) を新しい文面に合わせて直す

- [ ] **Step 2: 落ちることを確かめる**
- [ ] **Step 3: 実装する**

文面の手順は spec の「受け取る側: 仕分け」と「仕分けを手で1回通した記録」に従う。worktree では pre-commit のために `home/.claude/skills/` の実体のコピーが要ることと、未マージの Issue を `## 関連` 節に書けないことも文面に含める。docstring の「処理の手順の canonical はこの告知の文面」は保つ。

- [ ] **Step 4: 通ることを確かめる**
- [ ] **Step 5: コミット**

### Task 6: 送信 skill (agentic-coding-tools)

agentic-coding-tools のリポジトリで、そのリポジトリの CLAUDE.md と in-repo Issue の規約に従って行う。並行するセッションとのコンフリクトを避けるため、着手前にユーザーへ確認する。

**Files (agentic-coding-tools):**
- Create: `skills/meta/cross-repo-learnings/SKILL.md`
- Create: `skills/meta/cross-repo-learnings/template.md`

**Interfaces:**
- Consumes: hook が告げるまとめの置き場 (Task 2 の文面)。skill は置き場を自分で決めない
- Produces: skill 名 `cross-repo-learnings` (Task 1 の `SKILL_NAME` と一致させる)

- [ ] **Step 1:** SKILL.md を書く。description は、hook の案内で名指しされたときと、ユーザーが「dotfiles に送って」「知見を送って」と頼んだときに使う、とする。本文は、置き場は hook の告知が与えるので会話の中から探すこと、見つからなければユーザーに聞くこと、まとめは丸ごと書き直してよいこと、知見が無ければ書かないこと、箱へ直接書かないことを持つ。hook が無い環境のふるまいを session-handoff の SKILL.md と同じ書き方で1段落持つ
- [ ] **Step 2:** template.md を書く。セクションは「このセッションで試したこと」「効いたこと」「効かなかったこと」「新しく使った skill や plugin の使用感」「提案」で、各項目の末尾に確かめた度合い (実測 / ドキュメントのみ / 推測) を付ける。報告元が非公開なら固有名と案件の中身を書かない旨を冒頭のコメントに置く
- [ ] **Step 3:** そのリポジトリの検査を通し、PR を作ってマージし、タグを打つ (手順は agentic-coding-tools の CLAUDE.md と release skill に従う)

### Task 7: pin を上げて供給を繋ぐ

**Files:**
- Modify: `home/apm.yml`
- Modify: `home/apm.lock.yaml`

- [ ] **Step 1:** `home/apm.yml` に `hidari/agentic-coding-tools/skills/meta/cross-repo-learnings#<Task 6 の SHA>` を足し、同じリポジトリの他の pin も同じ SHA へ揃える
- [ ] **Step 2:** `apm install` を打ち、`~/.claude/skills/cross-repo-learnings/SKILL.md` が実在することと、`skill_installed()` が True を返すことを確かめる
- [ ] **Step 3:** コミット

### Task 8: 通しの確認と運用指示の書き換え

- [ ] **Step 1:** 受け箱を持たない使い捨てのリポジトリで `claude -p` のセッションを走らせ、コミットさせて案内が出ること、まとめを書かせて SessionEnd で dotfiles の箱へ届くことを確かめる。届いたものは確認後に消す
- [ ] **Step 2:** PRIVATE_CLAUDE.md の箱の説明とファイル名の規約を、この設計に合わせて書き換える案をユーザーへ示す。ファイルは dotfiles の外なので、書き換えはユーザーの確認を取ってから行う
- [ ] **Step 3:** ISSUE-126 のタスクを更新する

## 実測の記録

2026-10-20、Claude Code 2.1.304。`.cache/` に作った使い捨てのリポジトリの `.claude/settings.local.json` にだけプローブの hook を配線し、`claude -p` の別プロセスで観測した。

- Step 1: Stop の hook が `hookSpecificOutput.additionalContext` を返すと会話が続き、モデルは文面に従った。2回目の Stop は `stop_hook_active: true` で来た。transcript には `hook_success` と `hook_additional_context` の attachment として残り、`decision: block` を返したときの `hook_blocking_error` とは別の種類で記録される
- Step 2: 同じ Stop に `decision: block` の hook と additionalContext の hook を並べると、両方の文面が同じ継続の中で届き、モデルは両方に従った
- Step 3: Workflow の子は同じプロセスの subagent として動き、Stop ではなく SubagentStop を発火させた。payload は `agent_id` と `agent_type: "workflow-subagent"` を持つ。Stop は親のセッション (`agent_id` 無し) でだけ発火した。`agent_id` のガードで足り、Task 3 の除外条件に足すものは無い
- Step 4: SessionEnd の payload は `session_id`、`cwd`、`transcript_path`、`reason` を持つ
- Stop の payload は `background_tasks` を持つ。バックグラウンドの作業が走っている途中でも Stop は発火する
