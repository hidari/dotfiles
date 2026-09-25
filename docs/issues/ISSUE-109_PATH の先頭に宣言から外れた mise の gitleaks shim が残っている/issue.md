---
status: open
---

# chore: PATH の先頭に宣言から外れた mise の gitleaks shim が残っている

## 背景

2026-09-25のセッションで、PATH 上の gitleaks が mise の shim (`~/.local/share/mise/shims/gitleaks`、実体は `mise` への symlink) に解決されていると気づいた。dotfiles の宣言では gitleaks は Brewfile (`home/.Brewfile`) の管理で、mise の global 設定 (`home/.config/mise/config.toml`) の pin は node だけである。

2026-09-26に確かめた状態:

- `whence -a gitleaks` は shim、`/opt/homebrew/bin/gitleaks` の順に返す
- `mise which gitleaks` は「gitleaks is a mise bin however it is not currently active」で rc 1
- `~/.local/share/mise/installs/gitleaks` に 8.30.1 の実体が残っている。同じ installs には、global 設定に無い道具がほかに8つある (一覧は `ls ~/.local/share/mise/installs` で引ける)
- dotfiles の中で `gitleaks` を叩くと、shim は `MISE_LOG_LEVEL=trace` の出力で `shim[gitleaks] SYSTEM /opt/homebrew/bin/gitleaks` と解決し、Homebrew 版が走る。pre-commit の gitleaks hook は `language: system` なので同じ経路を通る。今のところ動作は正しく、版もどちらも 8.30.1

ただし shim は cwd から見える mise の設定で解決先を変えるので、gitleaks を pin する mise 設定の配下では別の版へ静かに落ちる。shim が残った理由 (過去に dotfiles が pin していたのか、別リポジトリの設定から入ったのか) は確かめていない。別リポジトリの pin はそのリポジトリにとっての版の canonical なので、残りの8つを消してよいかは道具ごとに違う。

## 決めること

- gitleaks の shim と installs を消すか (`mise uninstall` と `mise reshim`)。消す前に、gitleaks を pin しているリポジトリが無いことを確かめる
- 同じ形を検査で拾うか。`config_guard.tool_provisioning` はリポジトリの宣言 (Brewfile と mise の設定) だけを読み、CI でも回る検査なので、ホストの PATH と installs は射程の外にある。拾うならホストの状態を見る側 (セッション頭の guard-health のプローブなど) が候補で、「宣言に無い shim が、宣言済みのコマンドより PATH の前に出る」を条件にできるかを見る

## タスク

- [ ] gitleaks を pin しているリポジトリが無いか確かめ、shim と installs を消すか決める
- [ ] 同じ形を検査で拾うか決め、拾うなら置き場を決めて実装する

## 関連

ISSUE-94: Brewfile の構文と記法を検査する層がどこにも無い。tool_provisioning の射程の話が重なる

ISSUE-95: Brewfile の射程が散文どうしで食い違い実機とずれている

ISSUE-106: この Issue を起票したブランチの作業
