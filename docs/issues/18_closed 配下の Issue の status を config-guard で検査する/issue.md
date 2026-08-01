---
status: open
---

# closed 配下の Issue の status を config-guard で検査する

## 背景

Issue #16 のクローズを実地で行ったとき、`git mv` が新パスへ stage するのは HEAD の内容であり、直前の Edit (`status: open` → `status: closed`) は unstaged のまま残ることを実測した。`git status` は `RM` を返す。明示 `git add` で回避したが、これを忘れると frontmatter が `status: open` のまま `closed/` 配下に入る。

この不整合は沈黙する。`dev-workflow:in-repo-issue` の検索手順が使う `grep -lr '^status: open$' docs/issues/[0-9]*/issue.md` は `closed/` を含まないグロブなので、open のまま closed 配下にある Issue は open 一覧に出てこない。`ls docs/issues/closed/` には出るので「閉じた」ようには見える。どちらの経路からも異常として現れない。

同 skill の Phase E は「ディレクトリ位置と frontmatter の不整合は Phase D の手順違反なので、E ではディレクトリ位置だけで判定する」と明記している。つまり不整合が起こりうることは前提になっているが、起きたことを知る手段が無い。

ディレクトリ位置と `status` は 1 対 1 で対応すべき値であり、両方ともリポジトリ内に静的に存在するので機械検査できる。Issue #17 と同じく検査対象は Issue ディレクトリ配下で、config-guard は既に CI でリポジトリ全体をフルスキャンしているため CI 費用も増えない。

skill 側では claude-plugins の PR #7 で D.4 の記述を「add しなければ必ず収まらない」と実測に沿う形へ直したが、これは手順を読む側への指示であって検出ではない。

## タスク

- [ ] config-guard に検査モジュールを追加する (`docs/issues/closed/<NNN>_<title>/issue.md` は `status: closed` を持ち、`docs/issues/<NNN>_<title>/issue.md` は持たないことを検査する)
- [ ] 仕様をテストで表現する (closed 配下で closed は通す、closed 配下で open は落とす、active 配下で open と in_progress は通す、active 配下で closed は落とす)
- [ ] pre-commit (`config-guard-scan`) と CI に配線する。既存の `scan()` 経由で自動的に検査対象へ入ることを確認する

## 関連

[Issue #16](../closed/16_superpowers%20の成果物を%20Issue%20ディレクトリ配下へ寄せる/issue.md) のクローズ作業で実測した挙動が出発点。

[Issue #17](../17_Issue%20ディレクトリ配下の成果物ファイル名を%20config-guard%20で検査する/issue.md) と同種で、どちらも config-guard による Issue ディレクトリの検査強化にあたる。片方を実装するときにもう片方も併せて入れる形が自然。
