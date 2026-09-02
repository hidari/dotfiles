---
status: open
---

# ci: ツール取得の一時障害で CI が落ちるのを減らす

## 背景

2026-08-18 の 1 日で、CI が 3 回赤くなった。いずれもテストやコードの失敗ではなく、
外部からのツール取得が失敗したものである。

| job | 取得先 | 失敗 |
| --- | --- | --- |
| gitleaks (leak guard) | `github.com/bats-core/bats-core/archive/<sha>.tar.gz` | HTTP 503 |
| handoff-sentinel (python) | `raw.githubusercontent.com/astral-sh/versions/main/v1/uv.ndjson` | タイムアウト |
| all suites (bats) | `codeload.github.com/astral-sh/setup-uv/tar.gz/<sha>` | HTTP 429 (3 回リトライ後) |

3 件とも別のホスト、別の段階で起きており、同じ 1 つの障害ではない。共通するのは
「取得に失敗したらそのまま job が落ちる」という形だけである。3 件とも該当 job の
再実行で緑になったので、恒久的な問題ではなく一時障害への耐性の問題として扱う。

再実行で通るとはいえ実害がある。マージ直前に赤が出ると、原因がコードなのか
インフラなのかをログの失敗行まで読まないと判別できない。判別を誤れば、存在しない
バグを追うか、逆に本物の失敗を「どうせインフラ」と流すことになる。

## uv のバージョンが pin されていない

上の 2 件目は独立した問題を露出させた。`.github/actions/setup-uv/action.yml` は
`astral-sh/setup-uv` を SHA で pin しているが `version` を渡していない。そのため
setup-uv は uv 本体のバージョンを `uv.toml` / `pyproject.toml` から決めようとし、
リポジトリルートにどちらも無いため latest へフォールバックする。CI ログにこう出る。

```
Could not find file: .../uv.toml
Could not find file: .../pyproject.toml
Could not determine uv version from uv.toml or pyproject.toml. Falling back to latest.
Fetching manifest data from https://raw.githubusercontent.com/astral-sh/versions/main/v1/uv.ndjson ...
```

pin していないので、いつ走らせても同じ uv とは限らない。バージョンを固定すれば
マニフェスト取得そのものが消えるかどうかは setup-uv の実装次第なので、確かめてから
判断する。

この非対称は他のツールと比べると際立つ。bats はアーカイブの SHA まで固定し、
mise は exact pin で運用している。uv だけが action の pin だけで本体は latest である。

## 影響範囲

`setup-uv` composite action は `.github/workflows/test.yml` の 8 job から呼ばれる。
この 1 つの取得が失敗すると 8 job が落ちうる。

## タスク

- [ ] 3 件の失敗経路を切り分け、どこが自分で制御できるかを確かめる (自前の
      `scripts/ci/download-and-verify.sh` 経由か、action 内部か、ランナーによる
      action 自体のダウンロードか)
- [ ] 制御できる取得にリトライとバックオフを入れる
- [ ] uv のバージョンを pin する。合わせて、pin するとマニフェスト取得が消えるかを実測する
- [ ] ランナーが行う action 自体のダウンロード (429 の経路) に打てる手があるか調べる。
      無ければ「打てない」と結論して記録する
- [ ] キャッシュで取得回数そのものを減らせるか検討する

## 関連

- [Issue #5: CI のツール取得の curl-verify-extract を共通 composite action へ括り出す](../closed/5_CI%20のツール取得の%20curl-verify-extract%20を共通%20composite%20action%20へ括り出す/issue.md) (closed)。
  - 取得手順の重複を `scripts/ci/download-and-verify.sh` へ寄せた Issue。本 Issue は
    その取得が失敗したときの振る舞いを扱う
- PR #115 と PR #116 の CI で観測 (どちらも該当 job の再実行で緑)
- ISSUE-50: GitHub Repository Rulesets を導入する。必須ステータスチェックを入れると、この
  Issue が扱う一時障害がそのままマージのブロックになる。あちらは本 Issue を先行に置いている
