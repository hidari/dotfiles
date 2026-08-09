---
status: open
---

# fix: run-pester.ps1 の件数ガードを実効化する

## 背景

relay の PR #588 で同型のラッパを実装した際、dotfiles 側の `scripts/ci/run-pester.ps1`
にガードが 2 つとも効いていない状態が見つかった。relay 側では両方直してある。

このラッパの存在理由は `.DESCRIPTION` に書いてあるとおり「Pester はテストを 1 件も
見つけられなくても成功として終わる」ことへの対策である。その対策が現状は働いていない。

## 現状

### 1. `-MinimumCount` に既定値があり、呼び出し元が 2 箇所とも省略している

```powershell
# scripts/ci/run-pester.ps1:22
[int] $MinimumCount = 1
```

呼び出し元は 2 箇所あり、どちらも `-MinimumCount` を渡していない。

```
.pre-commit-config.yaml:262   pwsh -NoProfile -File scripts/ci/run-pester.ps1 -Path scripts/windows-vm/tests/
.github/workflows/test.yml:97 ./scripts/ci/run-pester.ps1 -Path scripts/windows-vm/tests/
```

つまり実際に守っているのは「1 件以上あること」だけで、テストが 1 件を残して全部
消えても緑になる。既定値があると呼び出し側は省略でき、省略されたガードは実質
無意味になる。

### 2. `TotalCount` は Skipped を含むので、skip 経由の 0 件実行を素通しする

```powershell
# scripts/ci/run-pester.ps1:50
if ($result.TotalCount -lt $MinimumCount) {
```

Pester の `TotalCount` には Skipped が計上される。デバッグ中に `Describe` へ `-Skip`
を付けて戻し忘れると、件数は変わらないまま実行 0 件で緑になる。

同じ罠がグローバル CLAUDE.md に `node --test` の事例として記録されている
(「非マッチは tests にも skipped にも計上されないので減算では 0 件を検出できない」の
Pester 版で、こちらは逆に skipped が total に載るために起きる)。

## タスク

- [ ] `-MinimumCount` を `Mandatory` にして既定値を外す
- [ ] 呼び出し元 2 箇所へ実件数を明示する (`.pre-commit-config.yaml` と `.github/workflows/test.yml`)
- [ ] 判定を `PassedCount + FailedCount` (= 実際に走った件数) に変える
- [ ] 表示する「実行 N 件」も同じ値にする (現在は TotalCount を表示していて実態とずれる)
- [ ] 変異注入で確認する: `Describe` へ `-Skip` を付けたら赤くなること
- [ ] 変異注入で確認する: 呼び出し元から `-MinimumCount` を外したら (Mandatory のプロンプトで) 失敗すること
- [ ] pre-commit と CI の両方で緑を確認する

## 関連

- relay PR [#588](https://github.com/HermitianHQ/relay/pull/588) — 同型のラッパで両方を直した実装がある
  (`crates/xtask/pester/run-pester.ps1`)。relay 側は `-MinimumCount` を Mandatory にし、
  `check_pester` が呼び出し時に件数を明示する形になっている
- `scripts/ci/run-pester.ps1` — 本 Issue の対象
- `.pre-commit-config.yaml` / `.github/workflows/test.yml` — 呼び出し元
