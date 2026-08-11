---
status: open
---

# docs: spec が参照する bootstrap.sh の関数名と行番号を実体に合わせる

## 背景

Issue #25 の Phase 4 でマージ前ゲートが検出した。25-spec.md が 2 箇所で `install_apm_skills()`
という関数を参照しているが、`bootstrap.sh` にこの名前の関数は存在しない。実測した内容は次のとおり。

- spec が参照する名前: `install_apm_skills()` (2 箇所)
- `bootstrap.sh` の実体: `install_apm()` と `install_apm_packages()`
- spec が併記する行番号 `bootstrap.sh:330` は、現在まったく別の位置を指す

同じ spec の別の箇所は `install_apm_packages()` という実在する名前を使っており、
文書内で不一致がある。

行番号による参照は編集のたびに rot する。関数名だけで足りるなら行番号は落とすのが、
CLAUDE.md の「機械検証可能な制約を散文に literal で書かない」に沿う。

## タスク

- [ ] `bootstrap.sh` の実体を読み、spec が指したかった関数を特定する
- [ ] spec の 2 箇所を実在する名前へ直す
- [ ] 行番号による参照を落とすか、落とせない場合の扱いを決める
- [ ] 同種の rot が他の文書に無いか確認する (関数名・行番号の参照を洗う)

## 関連

- [Issue #25: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する](../closed/25_skill%20と%20plugin%20を新規%20PUBLIC%20リポジトリへ集約し%20apm%20配布へ移行する/issue.md)
  検出元かつ修正対象の文書を持つ Issue。#25 は Phase 3b が未完で open のままなので、
  そちらの作業に合わせて直してもよい
