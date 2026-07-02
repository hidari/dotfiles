# node-security-notifier 設計

作成日 2026-06-25
ステータス 承認済み（実装計画 writing-plans へ移行）

## 背景

dotfiles は mise を version manager とし、`home/.config/mise/config.toml` で node を exact full-version でピンしている（例 `node = "24.18.0"`）。exact 固定は再現性が最強な反面、`24.18.1` のようなセキュリティパッチが出ても `mise outdated` / `mise upgrade` は自動では拾わない。したがってパッチ受領は「新リリースを知る → 手で pin を上げる」運用になる。本ツールはこの「知る」を自動化する。

Node のセキュリティリリースは固定の月次サイクルを持たず不定期で、Node 公式が脆弱性専用フィードを提供している。

## 目的

Node.js のセキュリティ/脆弱性リリースが新たに公開されたら macOS 通知で知らせ、ユーザーが `config.toml` の node pin を手動で更新する起点を作る。

## スコープ

対象とするもの
- Node 公式の脆弱性 RSS フィード（`https://nodejs.org/en/feed/vulnerability.xml`）の新着リリース検知と macOS 通知

対象としないもの（YAGNI）
- pnpm や他ランタイムのセキュリティ追跡（フィードと告知形態が異なるため別ツールに委ねる）
- `mise outdated` による pin 鮮度チェック（CVE 検知とは別軸。今回のスコープ外）
- npm 依存パッケージの脆弱性（`npm audit` / Dependabot の領域で別物）
- 通知からのクリック遷移（osascript の制約。本文に URL 文字列を載せて代替）
- pin の自動更新（手動 bump 運用を意図的に維持）

## アーキテクチャ

functional core + imperative shell を採用する。純粋関数の核（パース・差分・通知コマンド組立）と薄い I/O 殻（HTTP 取得・状態書込・osascript 実行）を分離し、核を fixture とデータで網羅テストする。これにより CLAUDE.md「ユニットテストでモックを使わない」を守りつつ高カバレッジを得る。殻はテスト時に依存注入で本物の test double を差せる構造にする。

外部 pip 依存はゼロ（Python 標準ライブラリのみ）。

## モジュール構成

`scripts/node-security-notifier/`（既存の config-guard と同型）

- `pyproject.toml`（uv / ruff / mypy strict / pytest）
- `src/node_security_notifier/`
  - `models.py` 既読判定に使う `FeedEntry`（guid / title / link / pub_date）のデータ構造
  - `feed.py` XML 文字列を `FeedEntry` のリストへパース（stdlib `xml.etree.ElementTree`、純粋関数）
  - `fetch.py` `urllib` でフィードを取得しバイト列を返す（薄い殻）
  - `state.py` 既読 GUID 集合の JSON load/save（実ファイル I/O）
  - `diff.py` `(current_entries, seen_guids)` から新着 entry を返す（純粋な集合差）
  - `notify.py` osascript 引数の組立（純粋）と実行（薄い殻）に分離
  - `cli.py` 取得→パース→差分→通知→状態保存 のオーケストレーション（取得関数・通知関数・状態パスを注入可能にする）
  - `__main__.py` エントリポイント
- `tests/` ユニットテスト一式
- `run.sh` launchd から呼ぶ薄い wrapper（uv の絶対パス解決 + ツール起動）
- `com.hidari.node-security-notifier.plist` launchd テンプレ（絶対パスはプレースホルダ）
- `README.md`

## データフロー

1. launchd（日次）が `run.sh` を起動し `uv run node-security-notifier` を実行する
2. フィードを取得しパースして現在の `FeedEntry` 群を得る
3. 状態ファイルから既読 GUID 集合を読む
4. `new = current_guids − seen` を算出する
5. 新着があれば osascript で通知する（複数時は上限件数 + サマリでスパムを防ぐ）
6. `seen = seen ∪ current` を保存する
7. 状態ファイルが無い初回は通知せず現状を seed する（過去全件の通知洪水を防ぐ）

## 状態戦略

既読 GUID 集合方式を採用する。各実行で現在のフィードの GUID 集合と既読集合の差を新着とし、実行後に和集合で更新する。順序や同一 pubDate に頑健で、フィードは約 80 件と極小のため集合の無制限増加は実害がない。

代替案と不採用理由
- 最終 pubDate 保存 順序依存かつタイムゾーンパースが脆い
- 最終 GUID + 逆順前提 フィードの並び替えに弱い

状態ファイルの位置 `~/.local/state/node-security-notifier/seen.json`

## 通知仕様

macOS 通知はユーザー向け（外部）なので英語で表記する（CLAUDE.md「外部に見えるものは英語」）。ツール内部のログは日本語。

- title `Node.js Security Release`
- subtitle リリースタイトル（例 `June 2026 Security Releases`）
- body 対象バージョンと `nodejs.org/en/blog/vulnerability`（クリック不可のため URL を文字列で明示）

複数新着時は上限件数（既定 3 件）を個別通知し、超過分はサマリ通知 1 件にまとめる。

## エラー処理

- ネットワーク取得失敗 / XML パース失敗 日本語の内部ログを出し非ゼロ終了。状態は更新せず通知もしない（次回実行で回復）
- 状態ファイル破損 再 seed し通知しない。欠落 初回扱いで seed
- osascript 実行失敗 ログを出し非ゼロ終了

## スケジューラ（launchd + bootstrap）

gitleaks leak guard は `/Users/<name>` パスのコミットをブロックする。plist には絶対パスが必要なため、コミットする plist はプレースホルダ（例 `__DOTFILES_DIR__` / `__HOME__`）で記述し、bootstrap が install 時に実パスへ置換する。これで gitleaks を通しつつ絶対パスを実現する。

- plist テンプレ Label `com.hidari.node-security-notifier`、`StartCalendarInterval` で日次 18:00、標準出力/エラーを `~/.local/state/node-security-notifier/launchd.log` へ
- bootstrap に「plist をレンダリング → `~/Library/LaunchAgents/` へ配置 → `launchctl` で冪等 load（再実行で重複しない）」を追加する
- bootstrap への追加は bats でテストする（dry-run でのレンダリング内容、冪等性）

## テスト計画（TDD）

- feed パース 実フィードを縮約した fixture XML から entries を exact 検証。不正 XML の negative ケース
- diff 既読集合による新着抽出（初回 / 既読済み / 新着混在の各ケース、既読済みは返らない negative）
- state tmp_path で round-trip、欠落と破損のハンドリング
- notify osascript 引数の組立を exact 検証（実行はしない）
- cli fixture バイト + 収集型の test double notifier + tmp 状態で結線（依存注入。モックフレームワーク不使用）。初回 seed で通知ゼロ、新着ありで通知発火を検証
- CI `node-security-notifier (python)` ジョブを `.github/workflows/test.yml` に追加（uv sync --frozen / ruff check / ruff format --check / mypy strict / pytest）

## 既定値（調整可能）

- 実行頻度 日次 18:00
- 状態ファイル `~/.local/state/node-security-notifier/seen.json`
- 初回挙動 通知せず seed
- 複数新着の個別通知上限 3 件（超過はサマリ 1 件）

## 受け入れ基準

- 新しい Node セキュリティリリースが公開された翌実行で macOS 通知が 1 回出る
- 同じリリースで再通知しない（既読集合で抑止）
- 初回実行で過去リリースの通知洪水が出ない
- ネットワーク不通時にクラッシュも誤通知もせず、次回正常実行で回復する
- `uv run` で ruff / mypy strict / pytest が全て緑、CI に新ジョブが追加され緑
- bootstrap 再実行で LaunchAgent が重複登録されない（冪等）
