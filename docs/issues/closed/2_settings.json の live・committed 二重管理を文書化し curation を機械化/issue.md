---
status: closed
---

# docs: settings.json の live・committed 二重管理を文書化し curation を機械化

## 背景

`home/.claude/settings.json` は git `skip-worktree` で管理されており、二重の状態を持つ:

- committed HEAD = gitleaks-safe な curated subset（`/Users/<name>` パスや個人トグルを含まない）
- working tree（live、`~/.claude/settings.json` の symlink 実体）= `/Users` パス・`hidari-plugins` marketplace・個人トグル等を含む superset

両者は手作業の skip-worktree dance（save → `--no-skip-worktree` → 編集 → commit → restore → `--skip-worktree`、または `git update-index --cacheinfo` で committed blob だけ差し替え）で維持されている。この契約は in-repo に文書化されておらず（README は symlink 一覧を載せるが curation / divergence には触れていない）、利用者のローカルメモリにしか存在しない。

結果として、dead config（例: PR #22 で削除した no-op な `enabledMcpjsonServers`）が live 側に残り続けたり、committed / live が意図せず drift するリスクがある。

## タスク

- [x] skip-worktree 契約（committed = subset / live = superset、なぜそうしているか、編集手順）を README または docs に明記する
- [x] curation の機械化方針を検討する（案 A: committed template + live を生成する generator、案 B: committed が期待 shape の strict subset であることを検証する CI チェック）
- [x] 採用案を実装し、dead config が committed / live に滞留しないことを保証する
- [x] gitleaks ガードとの役割分担を整理する（gitleaks は秘匿検出、本機構は構造 curation）

## 関連

- 起点 PR: #22（committed から no-op な `enabledMcpjsonServers` を削除、live は skip-worktree で無変更）
- 関連: `home/.claude/settings.json`（skip-worktree 対象）、README の symlink セクション
- 関連ルール: CLAUDE.md「個人情報を含む設定ファイルはコミットしないこと」
