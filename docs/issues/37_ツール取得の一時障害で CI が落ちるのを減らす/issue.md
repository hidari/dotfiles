---
status: open
---

# ci: ツール取得の一時障害で CI が落ちるのを減らす

## 背景

2026-08-18 の 1 日で、CI が 3 回赤くなった。いずれもテストやコードの失敗ではなく、
外部からのツール取得が失敗したものである。2026-10-31に仕分けた72件 (届いたのは2026-10-22〜2026-10-30) から足した分は、各節の末尾と、新しく立てた節に置いた。

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

`setup-uv` composite action は `.github/workflows/test.yml` の、uv を使う全 job から呼ばれる
(2026-09-17 時点で 6 job)。この 1 つの取得が失敗すると、それらがまとめて落ちうる。
週次の `mise-update-check.yml` も同じ composite action を呼ぶので、失敗するとその週の更新通知が止まる。

## 受け箱から届いた実例 (2026-10-31の仕分け)

別のリポジトリの CI で、just の導入に使う setup-just が恒常的に落ちた報告。

- setup-just (中身は setup-crate) の「no release for just matching version specifier」を一過性と読んで再実行するのは効かなかった。org へ移した後から起きはじめ (移管前の25回の run では0件、移管後はほぼすべての run のどこかの job)、release も asset も存在していた (実測)。setup-crate は API の例外を握らず、一覧の応答から target 名を含む asset のある release を絞るだけなので、一覧の応答が違ったときにも同じエラーになるという読みで、原因の特定まではしていない (推測)
- 導入を、固定の URL で落として sha256 を照合する自前のスクリプトへ置き換えると、setup-just の失敗が消え、取得物の差し替えも検出できるようになった。sha256 は API の asset の digest、落とした実物、release の SHA256SUMS の3つで突き合わせ、macOS のランナーは `sha256sum` を持たないことがあるので `shasum -a 256 --check --strict` を使った。置き換えた後の最初の run で Linux と macOS の全 job が通った (実測)

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

- Issue 5 (closed): CI のツール取得の curl-verify-extract を共通 composite action へ括り出す。
  - 取得手順の重複を `scripts/ci/download-and-verify.sh` へ寄せた Issue。本 Issue は
    その取得が失敗したときの振る舞いを扱う
- PR #115 と PR #116 の CI で観測 (どちらも該当 job の再実行で緑)
- ISSUE-50: GitHub Repository Rulesets を導入する。必須ステータスチェックを入れると、この
  Issue が扱う一時障害がそのままマージのブロックになる。あちらは本 Issue を先行に置いている
- ISSUE-98: Python 系の job の形を見直す。job を減らすと setup-uv の取得回数も減る
