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

このスキルは、Chrome DevToolsを使ってWebサイトを体系的にデバッグし、問題を特定・報告する機能を提供します。

## 提供する機能

- ネットワークエラーの検出と分析
- コンソールエラーの収集と分類
- パフォーマンス問題の調査（Core Web Vitals含む）
- UI/UXの問題の確認とスクリーンショット取得
- 体系的なデバッグレポートの作成

## コアワークフロー

Webサイトのデバッグを行う際は、以下のステップに従ってください：

1. 現在のブラウザの状態を確認する
2. 対象URLを理解する（または新しいページを開く）
3. ページの初期状態をスナップショットで確認
4. ネットワークリクエストを分析
5. コンソールメッセージを確認
6. 必要に応じてパフォーマンストレースを実行
7. 発見した問題を整理してレポートを作成

## デバッグフロー詳細

### ステップ 1: ブラウザの状態確認

まず、現在開いているページを確認します：

```
mcp__chrome-devtools__list_pages
```

複数のページが開いている場合は、適切なページを選択します：

```
mcp__chrome-devtools__select_page
```

### ステップ 2: 対象URLへのナビゲート

デバッグ対象のURLが指定されている場合は、そのURLに移動します：

```
mcp__chrome-devtools__navigate_page
```

新しいページを開く必要がある場合：

```
mcp__chrome-devtools__new_page
```

### ステップ 3: ページの初期状態確認

ページが読み込まれたら、スナップショットを取得してページの構造を確認します：

```
mcp__chrome-devtools__take_snapshot
```

これにより、以下が確認できます：
- ページの主要な要素
- アクセシビリティツリー
- 現在選択されているDevTools要素

視覚的な確認が必要な場合はスクリーンショットを取得：

```
mcp__chrome-devtools__take_screenshot
```

### ステップ 4: ネットワークリクエストの分析

すべてのネットワークリクエストを一覧表示します：

```
mcp__chrome-devtools__list_network_requests
```

重要な確認ポイント：
- 失敗したリクエスト（4xx, 5xxステータス）
- 遅いリクエスト（レスポンスタイムが長い）
- ブロックされたリクエスト（CORS、CSPエラー等）

問題のあるリクエストがあれば、詳細を取得：

```
mcp__chrome-devtools__get_network_request
```

### ステップ 5: コンソールメッセージの確認

コンソールに出力されたメッセージを一覧表示：

```
mcp__chrome-devtools__list_console_messages
```

特に注目すべき項目：
- エラーメッセージ（`error` タイプ）
- 警告メッセージ（`warn` タイプ）
- 未処理のPromiseリジェクション
- セキュリティ関連の警告

重要なメッセージがあれば詳細を取得：

```
mcp__chrome-devtools__get_console_message
```

### ステップ 6: パフォーマンストレース（必要に応じて）

パフォーマンス問題が疑われる場合、トレースを開始：

```
mcp__chrome-devtools__performance_start_trace
```

ページをリロードするか、特定の操作を実行した後、トレースを停止：

```
mcp__chrome-devtools__performance_stop_trace
```

Core Web Vitalsや具体的なパフォーマンスインサイトを分析：

```
mcp__chrome-devtools__performance_analyze_insight
```

### ステップ 7: デバッグレポートの作成

収集した情報を整理して、以下の構造でレポートを作成します：

```markdown
# デバッグレポート - {URL} - {日時}

## 概要
- 対象URL: {url}
- 検査日時: {timestamp}
- ページタイトル: {title}

## ネットワークの問題
### エラー
- [{status_code}] {url} - {error_message}
  - 原因: {analysis}
  - 推奨対応: {recommendation}

### 警告
- {description}

## コンソールの問題
### エラー
- {error_message}
  - ファイル: {source}:{line}
  - 原因: {analysis}
  - 推奨対応: {recommendation}

### 警告
- {warning_message}

## パフォーマンス
### Core Web Vitals
- LCP: {value}
- FID: {value}
- CLS: {value}

### 主な問題
- {performance_issue}
  - 影響: {impact}
  - 推奨対応: {recommendation}

## UI/UXの問題
- {issue_description}
  - スクリーンショット: {path}
  - 推奨対応: {recommendation}

## 優先度順の推奨対応
1. [高] {action_item}
2. [中] {action_item}
3. [低] {action_item}
```

保存先: `docs/debug-reports/`
ファイル名: `{YYYYMMDD}_{HHmmss}_debug_report.md`

## 高度な使用方法

### インタラクティブなデバッグ

特定の操作後の状態を確認する場合：

1. 要素をクリック：
```
mcp__chrome-devtools__click
```

2. フォームに入力：
```
mcp__chrome-devtools__fill
```

3. 要素にホバー：
```
mcp__chrome-devtools__hover
```

4. 特定のテキストを待機：
```
mcp__chrome-devtools__wait_for
```

### JavaScriptの評価

ページの状態を動的に確認：

```
mcp__chrome-devtools__evaluate_script
```

例：
- ローカルストレージの内容確認
- グローバル変数の値確認
- DOM操作の実行

### デバイスエミュレーション

モバイルデバイスでの問題を確認：

```
mcp__chrome-devtools__emulate
```

または画面サイズを変更：

```
mcp__chrome-devtools__resize_page
```

## デバッグシナリオ別ガイド

### シナリオ 1: ページが表示されない

1. ページに移動
2. ネットワークリクエストを確認（失敗したリソース読み込み）
3. コンソールエラーを確認（JavaScriptエラー）
4. スクリーンショットで実際の表示を確認

### シナリオ 2: APIリクエストが失敗する

1. ページを操作してAPIリクエストを発生させる
2. ネットワークリクエストをフィルタ（`xhr`, `fetch`）
3. 失敗したリクエストの詳細を取得（ステータス、ヘッダー、ボディ）
4. CORSやCSP問題をコンソールで確認

### シナリオ 3: ページが遅い

1. パフォーマンストレースを開始
2. ページをリロード
3. トレースを停止して分析
4. Core Web Vitalsを確認
5. 遅いリソースをネットワークタブで特定
6. JavaScriptの実行時間を確認

### シナリオ 4: レイアウトが崩れている

1. スナップショットで要素構造を確認
2. スクリーンショットで視覚的な問題を記録
3. 異なる画面サイズで再現性を確認
4. コンソールでCSS関連の警告を確認

## ベストプラクティス

### 体系的なアプローチ

- 必ず最初にスナップショットとネットワーク・コンソールの確認から始める
- 仮説を立ててから深掘りする（すべてを詳細に見ない）
- 関連する問題をグループ化して報告

### 優先順位付け

デバッグ結果の重要度を以下の基準で判断：
- **高**: ページが機能しない、セキュリティ問題、データ損失の可能性
- **中**: パフォーマンス問題、UX低下、警告メッセージ
- **低**: マイナーなUI問題、最適化の余地

### 再現性の確保

- 問題の再現手順を明確に記録
- 環境情報（ブラウザ、画面サイズ、ネットワーク条件）を記録
- 必要に応じてスクリーンショットやトレースファイルを保存

### エラーの文脈理解

単純にエラーをリストするのではなく：
- エラーの原因を分析
- ビジネスへの影響を評価
- 具体的な修正案を提示

### レポートの読みやすさ

- 技術的な詳細と推奨対応を分けて記述
- コードスニペットやスクリーンショットを適切に使用
- 優先度順にアクションアイテムを整理

## 他スキルとの連携

### Playwright スキルとの使い分け

| 目的 | 推奨スキル |
|------|-----------|
| パフォーマンス分析（Core Web Vitals） | chrome-devtools-debugger |
| 手動テスト中に発見した問題の調査 | chrome-devtools-debugger |
| E2Eテストの自動生成 | playwright-e2e-generator |
| クロスブラウザテスト | playwright-cross-browser |
| 探索的テスト | playwright-explorer |
| バグの再現・テストケース化 | playwright-bug-reproducer |

### 協調ワークフロー

**パターン 1: 探索 → 詳細分析**

1. `playwright-explorer` で探索的テストを実行
2. バグを発見したら、その状態を記録
3. `chrome-devtools-debugger` に切り替えて詳細分析
   - ネットワークリクエストの詳細確認
   - パフォーマンストレースの取得
   - コンソールエラーの詳細調査

**パターン 2: 手動テスト → デバッグ → テスト化**

1. 手動でブラウザを操作中に問題を発見
2. `chrome-devtools-debugger` でその場で調査（セッションを引き継げる）
3. 原因を特定
4. `playwright-bug-reproducer` で再現テストを作成

**パターン 3: バグ報告 → 再現 → 分析 → 修正確認**

1. バグ報告を受け取る
2. `playwright-bug-reproducer` で再現を試みる
3. 再現成功したら `chrome-devtools-debugger` で詳細分析
4. 修正後、再現テストで確認

### このスキルの強み

- **今開いているブラウザ**に接続できる（手動テストとシームレスに連携）
- パフォーマンストレース（Core Web Vitals）の取得と分析
- ネットワークリクエストの詳細な分析（ヘッダー、ボディ）
- デバイスエミュレーション

## 重要な考慮事項

### プライバシーとセキュリティ

- 認証情報や個人情報をレポートに含めない
- スクリーンショットに機密情報が映り込んでいないか確認
- 必要に応じて情報をマスクまたは省略

### パフォーマンス

- トレースは負荷が高いため、本当に必要な時のみ実行
- 大量のリクエストがある場合は適切にフィルタリング
- 長時間のセッションは避ける（ブラウザのメモリ消費）

### ツールの制限

- DevToolsは開発者ツールであり、本番環境の監視には適さない
- ブラウザの状態に依存するため、環境によって結果が異なる可能性
- 一部の問題（サーバーサイドの問題等）はDevToolsでは検出できない

## インタラクション例

### 例 1: 新しいWebサイトのデバッグ

ユーザー：「https://example.com をデバッグして問題を報告して」

プロセス：
1. 新しいページを開いてURLに移動
2. スナップショットとスクリーンショットを取得
3. ネットワークリクエストを確認
4. コンソールメッセージを確認
5. 問題を発見した場合は詳細を調査
6. デバッグレポートを作成

応答：「example.comのデバッグが完了しました。3つのネットワークエラーと2つのコンソールエラーを発見しました。詳細なレポートを作成しました。」

### 例 2: パフォーマンス問題の調査

ユーザー：「このページの読み込みが遅い原因を調べて」

プロセス：
1. 現在のページでパフォーマンストレースを開始
2. ページをリロード
3. トレースを停止して分析
4. Core Web Vitalsを確認
5. ネットワークリクエストで遅いリソースを特定
6. 推奨対応をまとめる

応答：「パフォーマンストレースの結果、LCPが4.2秒と遅いです。主な原因は大きな画像ファイル(3.5MB)の読み込みです。画像の最適化を推奨します。」

### 例 3: APIエラーの調査

ユーザー：「ログインボタンをクリックした時のエラーを調べて」

プロセス：
1. 現在のページのスナップショットを取得
2. ログインボタンを特定してクリック
3. ネットワークリクエストで新しいリクエストを確認
4. 失敗したAPIリクエストの詳細を取得
5. コンソールエラーを確認
6. 問題をまとめて報告

応答：「ログインAPIリクエストが401エラーで失敗しています。リクエストヘッダーにAuthorizationヘッダーが含まれていないことが原因です。」
