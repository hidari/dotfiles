# mise-update-notifier

mise で exact pin したツールに新しい版が出ていないかを調べ、Markdown で報告する。

## なぜ必要か

`home/.config/mise/config.toml` は全ツールを exact pin しており、その規約は config-guard
(`config_guard.mise_pins`) が強制している。ところがこの exact pin こそが素の `mise outdated`
を無力化する。`mise outdated` は「requested レンジ内に新しい版があるか」を見るが、pin は
レンジ幅がゼロなので、どれだけ新版が出ても常に up to date と報告される。

そこで pin と比べるべき「最新版」を 2 通り別々に問い合わせ、危険度で分けて報告する。

- 互換範囲の最新: 破壊的変更を跨がない範囲での最新。`mise latest <tool>@<compatible>`
- 絶対的な最新: メジャーを跨いだ最新。`mise latest <tool>`

互換範囲は pin された版から導出するので、メジャー番号をどこにも二重に書かない。semver の
0.x は minor が破壊的変更の軸なので、0 系だけ major.minor を互換範囲とする。

## 使い方

リポジトリルートから実行する。`--project` を使うのは cwd を移動させないため
(`--directory` だと cwd が変わり、相対パスの `--config` が解決できない)。

```
uv run --project scripts/mise-update-notifier mise-update-notifier \
  --config home/.config/mise/config.toml --body-out tmp/body.md
```

標準出力に JSON のサマリ (`has_updates` と件数) を出し、`--body-out` へ Markdown 本文を書く。
GitHub Actions からは週次で呼ばれ、更新があれば単一の Issue を更新し、無くなれば閉じる。
