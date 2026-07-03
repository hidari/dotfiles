# 設計: session-handoff スキルと handoff-sentinel hook

セッション品質が劣化する2つの状況で作業状態を引き継ぎ書に外部化し、
新しいセッションへシームレスに引き継ぐための user (マシン) スコープ機構。

## 目的

1. コンテキストウィンドウの使用率がしきい値を超えたとき、引き継ぎ書を
   `<リポルート>/tmp/handoff.md` に書き出してセッション切替を誘導する
2. ツール呼び出しの破損 (本文への tool-call XML 断片の漏れ、ツール実行エラーの連発) が
   規定回数連続したとき、同じ引き継ぎ書を書き出して Claude Code の再起動を誘導する
3. 新しいセッションの開始時に handoff.md を自動で読み込ませ、引き継ぎを完結させる

## 背景と制約 (公式ドキュメント裏取り済み)

- Skill は自動発火機構を持たない。「条件を満たしたら実行」は hook (harness 実行) の責務であり、
  hook がモデルへ additionalContext / Stop reason を注入して skill 発動を促す構造になる
- hook の入力 JSON にはコンテキスト使用率フィールドが存在しない。
  transcript (JSONL) の assistant メッセージ `usage` から自力計算する
  (statusline は `context_window.used_percentage` を受け取れるが、表示系に検知の副作用を
  持たせる結合を避け、transcript 自己完結型を採る)
- 破損の実観測パターン: `court` のような崩れたテキストに続いて生の
  `<invoke name="Bash">` ブロックが本文に表示されツールが実行されない、
  およびツール実行エラーの連発
- handoff 手順は全トリガーで同一のため、skill は 1 つに統合しトリガーを列挙する
  (2 skill 分割は手順書の二重管理になるため不採用)

## アーキテクチャ

責務を 3 層に分離する。

| 層 | 担当 | 内容 |
|---|---|---|
| 検知 | handoff-sentinel.py (hook) | 条件判定とモデルへの通知・handoff.md の自動注入 |
| 手順 | SKILL.md | handoff.md を書く手順とトリガー別の締め案内 |
| 書式 | template.md | 引き継ぎ書構造の canonical (SKILL.md は構造を再掲しない) |

### 配置

- `home/.claude/skills/session-handoff/SKILL.md`
- `home/.claude/skills/session-handoff/template.md`
- `home/.claude/hooks/handoff-sentinel.py`
- `scripts/handoff-sentinel/tests/test_handoff_sentinel.py` (tirith-hook と同じ pytest 流儀)
- `home/.claude/settings.json` に PostToolUse (matcher `*`) / Stop / SessionStart の配線を追加

`~/.claude/skills` と `~/.claude/hooks` はリポへの symlink のため、リポ変更が即 live になる。
settings.json は skip-worktree 運用のため committed 版と live 版の両方を更新する。

## コンポーネント

### handoff-sentinel.py

単一スクリプトを 3 イベントに配線し、第1引数 (`posttool` / `stop` / `session`) で分岐する。

共通ガード:

- 入力 JSON に `agent_id` があれば (subagent) 即 exit 0
- `transcript_path` が無い・読めない・壊れている場合は exit 0
- 全例外を握って exit 0 (検知機構の故障で作業を止めない fail-safe)

PostToolUse (コンテキスト監視):

- transcript 末尾から最後の assistant メッセージの `usage` を読み、
  `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` を現在の占有量とする
- 占有量がウィンドウサイズ × しきい値を超えたら `hookSpecificOutput.additionalContext` で
  「session-handoff スキルを発動して tmp/handoff.md を書き、セッション切替を促せ」と注入する
- しきい値は使用率 50%、ウィンドウサイズは 200k tokens を要求値とする。
  runtime の canonical はスクリプト内の定数であり、環境変数
  `HANDOFF_CONTEXT_WINDOW_TOKENS` / `HANDOFF_CONTEXT_THRESHOLD_PCT` で上書きできる。
  他ファイル (SKILL.md 等) はこの値を再掲しない
- 通知は `~/.cache/claude/handoff-sentinel/<session_id>.notified` の state ファイルで
  1 セッション 1 回に制限する

Stop (破損監視):

- transcript の末尾から遡り、最新イベントで終わる「破損イベント」の連続数を数える。
  破損イベントは次の 2 種:
  - assistant の text ブロックに漏れた tool-call 断片
    (`<invoke` / `</invoke>` / `<parameter` / antml 文字列)。
    ただし同一 assistant メッセージ内に正常な tool_use ブロックが存在する場合は数えない
    (tool-call 記法を話題として扱う会話の誤検知ガード)
  - `tool_result` の `is_error` が真のエントリ
- 正常に完了したツール実行が挟まったら連続カウントをリセットする
- 連続 5 イベント (要求値。canonical はスクリプト内定数、環境変数
  `HANDOFF_BROKEN_STREAK` で上書き可) で停止をブロックし、reason で
  「session-handoff スキルを発動して tmp/handoff.md を書き、ユーザーに再起動を促してから停止せよ」
  と指示する
- 入力の `stop_hook_active` フラグと state ファイル
  (`~/.cache/claude/handoff-sentinel/<session_id>.blocked`) の両方で block を
  1 セッション 1 回に制限する (block 無限ループでセッションが停止不能になる事故の防止)

SessionStart (引き継ぎ注入):

- `cwd` から `git rev-parse --show-toplevel` でリポルートを解決する
  (リポ外なら cwd をルートと見なす)
- `<ルート>/tmp/handoff.md` が存在すれば内容を `additionalContext` で注入し、
  同ディレクトリの `handoff-consumed-<UTC タイムスタンプ>.md` へリネームして
  二重読み込みを防ぐ
- 注入サイズには上限 (canonical はスクリプト内定数) を設け、超過時は先頭のみ注入して
  切り詰めた旨を明記する (新セッションのコンテキストを冒頭から圧迫しない)

### SKILL.md

- frontmatter: `name: session-handoff`。description には発動経路を列挙する:
  hook からのコンテキスト超過通知、hook からの破損検知通知、
  ユーザーの手動依頼 (「引き継ぎ書いて」「handoff して」等)
- ユーザーが任意のタイミングで `/session-handoff` スラッシュコマンドとして直接呼べること。
  model 発火 (hook 通知経由) と user 発火の両方を維持するため、
  `disable-model-invocation` 等の発動経路を制限する frontmatter は設定しない
- 手順:
  1. リポルートを解決し `tmp/` を `mkdir -p` する
  2. 同梱の `template.md` を読み、各セクションを埋めて `tmp/handoff.md` に書き出す
     (既存があれば上書き。最新の引き継ぎが常に正)
  3. トリガー別の締め:
     - コンテキスト超過通知 → 「/clear するか新セッションを開いて再開して。
       SessionStart で自動で引き継がれる」と案内して停止
     - 破損検知通知 → 「Claude Code の再起動を推奨」と案内して停止
     - 手動 → 書き出した旨だけ報告
- しきい値等の数値と引き継ぎ書の構造は SKILL.md に記載しない
  (それぞれ handoff-sentinel.py と template.md が canonical)

### template.md

引き継ぎ書構造の canonical。5 セクションで構成し、各セクションに
「何を書くべきか」のガイドをプレースホルダとして記述する:

1. タスクと目的: いま何をなぜやっているか
2. 完了済み: 検証状態 (テスト・lint の緑/赤) 込みで
3. 未完と次の一手: 再開後まず何をすべきか
4. キー情報: ブランチ、PR 番号、重要ファイルパス、実行中プロセス
5. 決定事項とハマりどころ: 会話中に決まったこと、踏んだ罠

全セクション共通の方針として「コードや git 履歴から復元できない情報を優先する」
(diff や履歴はリポが持っている。会話コンテキストにしかない判断・状態を凝縮する)。

## データフロー

1. コンテキスト超過: ツール実行 → PostToolUse で sentinel が使用率計算 →
   超過なら additionalContext → モデルが skill 手順で handoff.md を書き切替を案内
2. 破損: ターン終了 → Stop で sentinel が transcript 走査 → 5 連続で block + reason →
   モデルが handoff.md を書き再起動を案内して停止
3. 引き継ぎ: 新セッション開始 → SessionStart で sentinel が handoff.md を注入 +
   consumed リネーム → モデルは前セッションの状態を把握した状態で開始

## エラー処理

- sentinel は全経路 fail-safe (例外握り + exit 0)。検知の欠落は許容し、作業阻害は許容しない
- Stop block は 1 セッション 1 回。2 回目以降の破損は検知しても block しない
- handoff.md のリネーム失敗時は注入をスキップする
  (注入だけ成功してリネームが失敗すると次回も再注入されるため、原子性を優先)
- transcript の JSONL に未知の構造が混ざっても該当行のみ無視する

## テスト (仕様としてのテスト)

pytest を `scripts/handoff-sentinel/tests/` に配置し、synthetic な JSONL fixture を
stdin / transcript として食わせて判定ロジックを検証する。

- 使用率がしきい値直下では発火しない (negative) / 直上で発火する (positive) の境界値
- 通知済み session_id では再発火しない
- 破損イベント 4 連続 + 正常ツール実行でカウントがリセットされる (negative)
- 破損イベント 5 連続で block が発火し reason に skill 名が含まれる (exact 検証)
- text に tool-call 断片があっても同一メッセージに正常な tool_use があれば数えない
- `stop_hook_active` が真のとき block しない / blocked state ファイルがあるとき block しない
- subagent (`agent_id` あり) では全イベントで何も出力しない
- SessionStart: handoff.md の内容が注入 JSON に exact で含まれ、consumed リネームが行われる
- SessionStart: handoff.md 不在時は何も出力しない (negative)
- 壊れた JSONL・空 transcript でも exit 0 で異常終了しない (fail-safe)

## 配備と live smoke

- skill / hook スクリプトは symlink 経由で即 live
- settings.json は skip-worktree dance (退避 → no-skip → 編集 → 復元) で
  committed 版・live 版の両方に配線を追加する
- live smoke (ユニット緑だけで完了としない):
  1. ダミーの tmp/handoff.md を置いて新セッションを起こし、SessionStart 注入と
     consumed リネームを実機確認する
  2. しきい値を環境変数で極小にした状態でツールを実行し、コンテキスト超過通知が
     additionalContext として届くことを実機確認する
  3. `/session-handoff` を手動起動し、template.md 準拠の tmp/handoff.md が
     生成されることを実機確認する

## 受け入れ条件

- pytest が全緑で、警告ゼロ
- live smoke 2 種が実機で確認できている
- SKILL.md にしきい値の数値と引き継ぎ書構造の再掲がない
- settings.json の committed 版と live 版の両方に配線があり、gitleaks を通過する
