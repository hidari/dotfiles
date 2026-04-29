---
name: chrome-devtools-debugger
description: chrome-devtools-mcp を使ってWebサイトの問題を体系的にデバッグします。ネットワークエラー、コンソールエラー、パフォーマンス問題、UI/UXの問題を調査する際に使用します。
allowed-tools:
  - mcp__chrome-devtools__list_pages
  - mcp__chrome-devtools__select_page
  - mcp__chrome-devtools__new_page
  - mcp__chrome-devtools__close_page
  - mcp__chrome-devtools__navigate_page
  - mcp__chrome-devtools__take_snapshot
  - mcp__chrome-devtools__take_screenshot
  - mcp__chrome-devtools__list_network_requests
  - mcp__chrome-devtools__get_network_request
  - mcp__chrome-devtools__list_console_messages
  - mcp__chrome-devtools__get_console_message
  - mcp__chrome-devtools__performance_start_trace
  - mcp__chrome-devtools__performance_stop_trace
  - mcp__chrome-devtools__performance_analyze_insight
  - mcp__chrome-devtools__click
  - mcp__chrome-devtools__fill
  - mcp__chrome-devtools__hover
  - mcp__chrome-devtools__press_key
  - mcp__chrome-devtools__wait_for
  - mcp__chrome-devtools__evaluate_script
  - mcp__chrome-devtools__emulate
  - mcp__chrome-devtools__resize_page
  - Read
  - Write
---

# Browser Debugger スキル

chrome-devtools MCP を使い、ネットワーク・コンソール・パフォーマンス・UI/UX の問題を体系的に調査してレポート化します。

## 前提

- `mcp__chrome-devtools__*` ツールが利用可能であること。`list_pages` 呼び出しで失敗する場合は MCP 未接続。即座にユーザーに申告して、ローカル MCP の起動 (chrome-devtools-mcp プラグイン) を促す。
- 出力ベースディレクトリ: `git rev-parse --show-toplevel` の結果 (git リポジトリ内のとき) 配下の `docs/debug-reports/`。git 外ではカレントワーキングディレクトリ配下に同パス。存在しなければ Write の前に Bash の `mkdir -p` で作成。
- レポートファイル名: `{YYYYMMDD}_{HHmmss}_debug_report.md` (ローカルタイム ISO 8601 由来、例 `20260425_143000_debug_report.md`)。
- スクリーンショット保存先: `docs/debug-reports/assets/{YYYYMMDD}_{HHmmss}_{label}.png`。`take_screenshot` の filename 引数にこのパスを直接渡す。`{label}` はデバイス未指定時は `main`、モバイル / レスポンシブ確認時はデバイス識別子 (`iphone14` / `pixel7` / `ipadmini` 等)。
- 認証が必要な操作で認証情報が手元に無い場合は事前にユーザー確認。テストアカウントが存在するなら指示を求め、本番アカウントは使用しない。

## コアフロー

すべての依頼で次の順を踏む。シナリオによりステップ 5 (パフォーマンス) と 6 (インタラクション) は条件付き。

### 1. ページ選択

`list_pages` で既存タブ一覧を取得。

- 対象 URL のページが既存タブにあれば `select_page` で切り替え
- 無ければ `new_page` で新規タブを開き、続けて `navigate_page` で遷移

### 2. 初期状態の取得

- `take_snapshot`: アクセシビリティツリー取得。要素の uid はインタラクション (3 章) と要素特定で必須
- `take_screenshot`: 視覚的記録。後段のレポートで参照

### 3. ネットワーク調査

`list_network_requests` で全リクエスト取得。次の条件に該当するものを抽出:

- 4xx / 5xx ステータス
- duration が 1000ms 以上
- CORS / CSP / mixed-content でブロックされたもの (コンソール 4 章と相互参照)

該当がある場合、各リクエストに `get_network_request` でリクエスト/レスポンスヘッダー・ボディを取得。

抽出件数が 50 件超など大量になる場合は、URL パターン (ホスト + パス第 1 階層) でグルーピングして件数 / 平均 duration / 最遅 duration を集計し、上位 10 パターンと最も遅い 5 リクエストの詳細だけ `get_network_request` する。

### 4. コンソール調査

`list_console_messages` で全件取得し、次のレベルだけ抽出:

- `error`
- `warn` (ただし「Deprecation」「Slow」など実害が分かるもののみ)
- 未処理 Promise rejection
- セキュリティ警告

詳細が必要なものに `get_console_message`。

### 5. パフォーマンストレース (条件付き)

次のいずれかに該当する場合のみ実施:

- 3 章で 1000ms 以上のリクエストが 1 件以上ある
- ユーザーが「遅い」「重い」を明示的に訴えている
- LCP / FID / CLS への懸念がある依頼

実施手順:

1. `performance_start_trace`
2. `navigate_page` で同じ URL に再遷移 (リロード相当)
3. `performance_stop_trace`
4. `performance_analyze_insight` で Core Web Vitals と詳細インサイトを取得

### 6. インタラクション (条件付き)

ユーザー操作後の状態を見る依頼ではここを実行。

要素特定の優先順位:

1. `take_snapshot` 結果から該当要素の uid を取得し、`click` / `fill` / `hover` の uid 引数に渡す (推奨)
2. uid で特定不能な場合のみ `evaluate_script` で `document.querySelector(...)` ベースのクリックにフォールバック

同名候補が複数ヒットした場合の選別優先順 (例: 「ログイン」がヘッダーリンクと送信ボタンの両方に存在):

1. `<form>` 内の `type="submit"` ボタン
2. `<form>` 内の `<button>` または `<input>`
3. 画面中央付近の主要 CTA
4. nav / header 内のリンク
上記で一意に絞れない場合はユーザーに確認。

ネットワーク差分の取り方 (クリック後に発生したリクエストだけ追う):

1. クリック前に `list_network_requests` を呼びベースラインのリクエスト ID 一覧を記録
2. `click` を実行
3. `wait_for` で完了シグナルを待機
   - 既定タイムアウト: 5 秒
   - 待機文字列の選び方: 想定される成功テキスト (例: 「ようこそ」「ダッシュボード」「ログアウト」) または失敗テキスト (例: 「エラー」「失敗」「Unauthorized」「Invalid」) のいずれか実際に出るほうを 1 つ
   - どちらも特定不能なら `evaluate_script` で `performance.getEntriesByType('resource')` の件数増加を待つフォールバック
4. クリック後に `list_network_requests` を再取得
5. ベースラインに無い ID = クリックで発生した新規分

### 7. レポート保存

下のテンプレに従い、`Write` で `docs/debug-reports/{YYYYMMDD}_{HHmmss}_debug_report.md` に保存。問題ゼロでもミニマム版 (概要 + 「問題なし」明記) を必ず保存。

## モバイル / レスポンシブ確認

「モバイルで」「スマホで」「表示崩れ」の依頼ではコアフロー §2 の前にエミュレートを設定する (順序: `emulate` → `navigate_page`)。

特に指定がない場合の標準デバイスセット:

| プリセット     | ツール           | 引数                          | label      |
|-----------|---------------|-----------------------------|------------|
| iPhone 14 | `emulate`     | デバイス: `iPhone 14` (375x812) | `iphone14` |
| Pixel 7   | `emulate`     | デバイス: `Pixel 7` (412x915)   | `pixel7`   |
| iPad mini | `resize_page` | 768x1024                    | `ipadmini` |

iPad mini が `resize_page` なのは、`emulate` のデバイスプリセットに iPad mini が無い前提のフォールバック。実環境で `emulate` が iPad mini を受け付けるなら `emulate` を優先してよい。

3 サイズすべてで §2 〜 §4 を回す。差分があった場合のみ詳細記録 (差分判定: スクショ目視、横スクロールフラグの値、`evaluate_script` 数値の差で 1 つでも変化があれば「差分あり」)。

「表示崩れ」判定の主軸 (この順):

1. `take_screenshot` の目視 — 主軸。視覚的な重なり / はみ出し / 改行崩れを最初に見る
2. `evaluate_script` での横スクロール検出 (`document.documentElement.scrollWidth > window.innerWidth`) — 主軸の補強。true なら確定で崩れ
3. `take_snapshot` のアクセシビリティツリー — 補助。要素の親子関係や role 構造の異常確認
4. コンソール CSS 警告 (4 章) — 補助。深い CSS 由来の問題のみ

モバイル特有チェック観点 (1 回の `evaluate_script` でまとめて取得して良い):

- `<meta name="viewport">` の有無と内容 (`document.querySelector('meta[name=viewport]')?.content`)
- 横スクロール発生: `document.documentElement.scrollWidth > window.innerWidth`
- 入力要素の font-size: 16px 未満は iOS で自動ズームが起きる
- タップターゲット: button / a / input の clientWidth & clientHeight が 44px 未満は対象不足

3 デバイス分の結果は **1 つのレポートファイル**にまとめ、`## モバイル / レスポンシブ` セクション配下に各デバイスの小見出し (`### iPhone 14`, `### Pixel 7`, `### iPad mini`) で並べる (デバイス別ファイル分割はしない)。

## レポートテンプレ

```markdown
# デバッグレポート - {url} - {timestamp}

## 概要
- 対象URL: {url}
- 検査日時: {timestamp}  # ローカルタイム ISO 8601 (例: 2026-04-25T14:30:00+09:00)
- ページタイトル: {title}  # take_snapshot のルート node の name
- ビューポート: {device or size}  # モバイル時のみ

## ネットワーク
### エラー
- [{status_code}] {url} - {error_message}
  - 観察事実: {get_network_request の生データ要約}
  - 推定原因: {analysis}  # 既知パターン (下表) に該当 → 該当を記載、不明 → 「要追調査: <観察事実>」
  - 推奨対応: {recommendation}  # 同上、不明なら「ログ拡充」「再現手順確立」

### 警告
- {description}

## コンソール
### エラー
- {error_message}
  - ファイル: {source}:{line}  # get_console_message から
  - 推定原因: {analysis}
  - 推奨対応: {recommendation}

### 警告
- {warning_message}

## パフォーマンス  # 5 章実施時のみ。未実施なら「未計測」と明記
### Core Web Vitals
- LCP: {value}
- FID: {value}
- CLS: {value}

### 主な問題
- {performance_issue}
  - 影響: {impact}  # performance_analyze_insight の severity
  - 推奨対応: {recommendation}

## UI/UX
- {issue_description}
  - スクリーンショット: docs/debug-reports/assets/{YYYYMMDD}_{HHmmss}_{label}.png
  - 推奨対応: {recommendation}

## 優先度順の推奨対応
1. [高] {action_item}
2. [中] {action_item}
3. [低] {action_item}
```

### analysis / recommendation の既知パターン

| 観察事実                       | 推定原因           | 推奨対応                           |
|----------------------------|----------------|--------------------------------|
| 401 + Authorization ヘッダー無し | 認証ヘッダー未設定      | API クライアント側でトークン付与を確認          |
| 401 + Authorization ヘッダー有り | トークン期限切れ / 不正  | リフレッシュトークン処理 / トークン再発行         |
| 403                        | 権限不足           | ロール / スコープ確認                   |
| 404 + 静的ファイル               | ビルド出力 / パス間違い  | ビルド成果物の確認、パス修正                 |
| CORS preflight 失敗          | サーバー側 CORS 未設定 | Access-Control-Allow-Origin 設定 |
| CSP violation              | CSP ヘッダー設定     | meta CSP or HTTP ヘッダー側で許可リスト追加 |
| LCP > 2.5s + 大きな画像         | 画像最適化不足        | WebP / AVIF 化、レスポンシブ画像         |
| CLS > 0.1 + 動的要素           | レイアウトシフト       | 寸法予約、aspect-ratio 指定           |

該当パターンが無ければ「要追調査: <観察事実>」と記載し、推奨対応欄に「再現手順確立」「サーバー側ログ確認」など次のアクションを書く。空欄禁止。

### 問題ゼロ時のミニマム版

ネットワーク・コンソール・(取得時)パフォーマンス全部クリアの場合、テンプレの全セクションを残さず、次の最小構成のみで保存:

```markdown
# デバッグレポート - {url} - {timestamp}

## 概要
- 対象URL: {url}
- 検査日時: {timestamp}
- ページタイトル: {title}
- ビューポート: {device or size}  # モバイル時のみ

## 結論
問題なし。

### 確認した観点
- ネットワーク: {n} 件、エラー 0、1000ms 超 0
- コンソール: error 0 / warn 0 (実害ありのみカウント)
- パフォーマンス: {実施した場合は LCP/CLS の値、未実施なら「未計測 (条件未該当)」}
```

### 優先度判定

- 高: ページが機能しない / セキュリティ警告 / 認証エラー / データ損失リスク
- 中: パフォーマンス低下 / UX 警告 / 4xx (404 含むがメインフロー外) / 重要度の高い deprecated 警告
- 低: マイナーな UI 問題 / コンソール warn / 最適化提案

## 機密情報マスク

レポート保存時に必ず `<REDACTED>` で置換 (Write 直前にチェック):

- リクエストヘッダー: `Authorization`, `Cookie`, `X-API-Key`, `X-Auth-Token`, `Proxy-Authorization`
- レスポンスヘッダー: `Set-Cookie`
- レスポンス本文 / コンソール出力中のフィールド名: `token`, `access_token`, `refresh_token`, `password`, `secret`, `api_key`, `email`
- リクエスト URL のクエリパラメータ: `access_token`, `token`, `code`, `state`, `session`, `api_key` (例: `?access_token=xxx` を `?access_token=<REDACTED>` に置換)
- Bearer トークン本体 (`Bearer xxxx` の `xxxx` 部分)
- スクリーンショット: 個人情報・トークン文字列が映っていないか目視確認。映っていれば該当領域をクロップ or 撮り直し

## 他スキルとの使い分け

| 目的                                            | スキル                      |
|-----------------------------------------------|--------------------------|
| パフォーマンス分析 (Core Web Vitals)                   | chrome-devtools-debugger |
| 手動操作中に発見した問題のその場調査                            | chrome-devtools-debugger |
| ネットワーク詳細 (ヘッダー・ボディ) の解析                       | chrome-devtools-debugger |
| Playwright Test (E2E) の作成 / レビュー              | playwright-test          |
| Playwright CLI (codegen / screenshot / shard) | playwright-cli           |

このスキルの強み: 開いている Chrome セッションに接続できるので、手動テストとシームレスに連携。Playwright は隔離ブラウザを起動するため、ログインセッション等を引き継げない。

## 重要な考慮事項

### パフォーマンス

- トレースは負荷が高いため、コアフロー §5 の条件に該当する場合のみ
- 大量リクエストがあるサイトは `list_network_requests` の取得結果を要約 (URL パターン別件数) してから精査
- 長時間セッションは避ける (ブラウザのメモリ消費)

### ツールの制限

- DevTools は開発者ツール、本番監視には不適
- ブラウザ状態に依存するため環境差で結果が変わりうる
- サーバーサイド原因はここでは確証は得られない (推定までで止め、サーバーログ確認を推奨対応に書く)
