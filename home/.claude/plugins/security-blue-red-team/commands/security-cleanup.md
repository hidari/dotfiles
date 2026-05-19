---
description: Consume a cleanup-queue.json emitted by red-team-agent (Layer 3). Re-validates the production gate + seed_id_prefix invariant before executing each cleanup_command. Use after /security-redteam with Layer 3 to purge security_redteam_<UUID> seeds from staging / local.
argument-hint: [--from=<path>] [--dry-run]
---

# /security-cleanup

Layer 3 で seed されたテスト用リソースを purge する。 本 command は `red-team-agent` が出力した `cleanup-queue.json` を消費し、 各エントリの `cleanup_command` を順次 Bash 実行する。 **production gate と `seed_id_prefix` 不変条件を再検証** してから実行するので、 万一 cleanup-queue が改変されていても暴走しない。

## 引数 parsing

`$ARGUMENTS` から以下を抽出:

- `--from=<path>` (optional): `cleanup-queue.json` の絶対パスまたは cwd 相対パス。 省略時は `docs/security-reviews/<latest YYYY-MM-DD>/cleanup-queue.json` を自動補完
- `--dry-run` (flag, default: false): true なら resolved コマンド一覧を表示するだけで実行しない (検証用)

## 事前検証 (Production Gate 二重防御 + 不変条件)

1. `<cwd>/.claude/security-profile.yml` の存在確認。 無ければ exit
2. profile を構造化 YAML parse し、 `environment.kind` が `production` でないことを確認 (production なら即時拒否)
3. `cleanup-queue.json` を構造化 JSON parse し、 schema (`~/.claude/plugins/security-blue-red-team/schemas/cleanup-queue.schema.json`) に照らして検証
4. cleanup-queue.json の `metadata.environment_kind` が `local` または `staging` であることを再確認 (production であれば immediate abort、 queue が profile と矛盾している場合も abort)
5. profile から `environment.cleanup.seed_id_prefix` を抽出 (default: `security_redteam_`)
6. cleanup-queue.items[] を巡回し、 各 `seed_id` が profile の `seed_id_prefix` で **始まる** ことを確認 (1 件でも違反したら 全実行を中止 し報告)

## Cleanup 実行

検証を全て通過したら、 cleanup-queue.items[] を順次:

1. `cleanup_command` を表示
2. `--dry-run` ならスキップ (次のエントリへ)
3. Bash tool で execute、 stdout / stderr / exit code を記録
4. 1 件失敗しても他のエントリは続行 (集約 report を出すため)

## 出力

- cleanup-queue.json と同じディレクトリに `cleanup-log.json` を生成。 schema:
  ```json
  {
    "items": [
      {
        "seed_type": "...",
        "seed_id": "security_redteam_...",
        "cleanup_command": "...",
        "exit_code": 0,
        "stdout": "...",
        "stderr": "...",
        "executed_at": "ISO 8601 UTC"
      }
    ],
    "summary": { "total": N, "success": N, "failed": N, "dry_run": bool }
  }
  ```
- 終了時に summary を user に報告
- 失敗が 1 件でもあれば command 全体の exit code を非 0 で終了

## 責務境界 (DO NOT)

- production environment に対して絶対に実行しない (二重防御: profile.environment.kind + cleanup-queue.metadata.environment_kind)
- `seed_id_prefix` で始まらない `seed_id` を絶対に処理しない (queue が改変されていても safety net として機能する重要なガード)
- cleanup-queue.json schema 違反のエントリを実行しない
- `cleanup_command` を生成 / 改変しない (queue に書かれた resolved command をそのまま実行)
- 他 skill を呼ばない (本 command は cleanup のみが責務)
