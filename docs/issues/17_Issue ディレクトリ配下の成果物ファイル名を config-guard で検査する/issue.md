---
status: open
---

# Issue ディレクトリ配下の成果物ファイル名を config-guard で検査する

## 背景

Issue #16 で導入した `issue-scoped-artifacts` hook は、上流 superpowers (`brainstorming` / `writing-plans`) が既定パスへ書いてしまった場合、つまり成果物が `docs/superpowers/plans/` や `docs/superpowers/specs/` に落ちた場合しか捕捉しない。Issue ディレクトリ配下に置かれたファイル名の違反、たとえば番号の無い `spec.md` や、`15_` 配下に置かれた `16-spec.md` のような番号不一致は検出しない。

規約のうち実害を防いでいるのは `<NNN>` の一致であって「`docs/superpowers/` に置かないこと」ではない。番号前置の理由は subagent-driven-development の workspace 名の衝突回避であり、`plan.md` のような番号なしの名前にすると全 Issue の workspace が `.superpowers/sdd/plan/` へ集中し、上流が「plan ごとのサブディレクトリ化」で潰したばかりの衝突を再現してしまう。つまり守る価値の高い方が現状 prose のみで、機械検査が付いていない。

この検査は dotfiles 固有でよい。検査対象は Issue ディレクトリ配下のファイル名であり、`issue-scoped-artifacts` hook の対象 (`docs/superpowers/`) とは重ならないため、literal の重複は起きない。config-guard は既に CI でリポジトリ全体をフルスキャンしているため、検査を追加しても CI 費用は増えない。

期待されるファイル名 (`<NNN>-spec.md` / `<NNN>-plan.md`) はディレクトリ名 (`<NNN>_<title>`) の純粋関数なので、exact match で機械的に検査できる。

## タスク

- [ ] config-guard に検査モジュールを追加する (`docs/issues/<NNN>_<title>/` 配下の `spec.md` / `plan.md` 系ファイルの名前が、ディレクトリ名先頭の `<NNN>` と一致するかを検査する)
- [ ] 仕様をテストで表現する (番号が一致するファイルは通す、番号の無い `spec.md` は落とす、`15_` 配下に置かれた `16-spec.md` のような番号不一致も落とす)
- [ ] pre-commit (`config-guard-scan`) と CI に配線する。既存の `scan()` 経由で自動的に検査対象へ入ることを確認する

## 関連

[Issue #16](../16_superpowers%20の成果物を%20Issue%20ディレクトリ配下へ寄せる/issue.md) の最終レビューで検出した既知の限界。`16-spec.md` と `16-plan.md` の「今回やらないこと」節を参照。
