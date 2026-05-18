---
description: Universal Red Team security tester. Reads <project>/.claude/security-profile.yml and dispatches red-team-agent.
argument-hint: [--layer=1|2|3|4|all] [--target=local|staging]
---

# /security-redteam

product-agnostic な Red Team セキュリティテストを起動する。 詳細手順は `red-team-agent` の system prompt に集約されているので、 本 command は **薄い entry point** に徹する。

## 引数 parsing

`$ARGUMENTS` から以下を抽出:

- `--layer=<1|2|3|4|all>` (default: `all`)
- `--target=<local|staging>` (default: profile の `environment.kind` から自動解決)

未対応の値 → エラーで終了。

## 事前検証

以下を Bash で実行 (text grep ではなく **構造化 YAML parse** で行う。 `kind: "production" # was staging` のようなコメント混在や継続行を text match で取りこぼさないため):

1. `<cwd>/.claude/security-profile.yml` が存在するか確認。 無ければ「 profile が無い。 wrap skill が初期化する必要がある」 と出力して exit
2. 以下の Python one-liner で profile を構造化 parse し、 `environment.kind` と `environment.allow_targets` を抽出:
   ```bash
   python3 -c "
   import sys, yaml
   p = yaml.safe_load(open('.claude/security-profile.yml'))
   env = p.get('environment', {})
   if env.get('kind') == 'production':
       sys.stderr.write('ABORTED: environment.kind=production. /security-redteam refuses to run.\n')
       sys.exit(1)
   print(len(env.get('allow_targets', []) or []))
   "
   ```
   - exit code 非ゼロなら **即時拒否し exit** (production または YAML parse 失敗)
   - stdout の数字が 0 で `--layer` が `2|3|4|all` を含むなら警告を出して `--layer=1` に縮退するか確認

## Dispatch

Agent tool で `red-team-agent` を起動:

- `subagent_type`: `red-team-agent`
- 引数として渡す値:
  - `SECURITY_PROFILE`: `<cwd>/.claude/security-profile.yml` の絶対パス
  - `LAYERS`: parsed `--layer` 値
  - `TARGET`: parsed `--target` 値
  - `OUTPUT_DIR`: `docs/security-reviews/` (cwd 相対)

## Dispatch 後

Agent の出力 (findings.json と red-team.md のパス、 severity 集計) を user に報告。 後続 (Blue Team 連鎖 / Issue 起票 / PR 作成) は user の判断に委ねる。
