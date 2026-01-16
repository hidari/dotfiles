---
name: playwright-explorer
description: Playwright MCPを使用してWebアプリケーションを探索的にテストし、バグや問題を発見します。手動テストの代替や品質保証の補助に使用します。
allowed-tools:
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_navigate_back
  - mcp__playwright__browser_tabs
  - mcp__playwright__browser_close
  - mcp__playwright__browser_resize
  - mcp__playwright__browser_snapshot
  - mcp__playwright__browser_take_screenshot
  - mcp__playwright__browser_click
  - mcp__playwright__browser_hover
  - mcp__playwright__browser_drag
  - mcp__playwright__browser_type
  - mcp__playwright__browser_fill_form
  - mcp__playwright__browser_select_option
  - mcp__playwright__browser_file_upload
  - mcp__playwright__browser_press_key
  - mcp__playwright__browser_handle_dialog
  - mcp__playwright__browser_wait_for
  - mcp__playwright__browser_evaluate
  - mcp__playwright__browser_console_messages
  - mcp__playwright__browser_network_requests
  - mcp__playwright__browser_run_code
  - Read
  - Write
  - Bash
---

# Playwright Explorer スキル

このスキルは、Playwrightを使用してWebアプリケーションを探索的にテストし、潜在的な問題やバグを発見する機能を提供します。

## 提供する機能

- インタラクティブなページ探索
- エッジケースの発見
- アクセシビリティ問題の検出
- UX 問題の特定
- 発見した問題の Beads 登録

## 探索的テストとは

探索的テストは、事前に定義されたテストケースに従うのではなく、アプリケーションを自由に操作しながら問題を発見するアプローチです。

特徴：
- 創造的な操作パターン
- エッジケースの探索
- ユーザー視点での検証
- 直感と経験に基づく調査

## コアワークフロー

探索的テストを行う際は、以下のステップに従ってください：

1. テスト対象の機能・画面を選定
2. ページ構造を把握
3. 様々な操作パターンを試行
4. 問題を発見・記録
5. 発見した問題を Beads に登録

## 探索戦略

### 戦略 1: 境界値テスト

入力フィールドに対して境界値を試す：

```
mcp__playwright__browser_snapshot
```
→ 入力フィールドを特定

テストする値：
- 空文字列
- 最小値/最大値
- 特殊文字（`<>&"'`、絵文字）
- 非常に長い文字列
- 数値フィールドに文字
- 日付フィールドに無効な日付

```
mcp__playwright__browser_type (element: "名前入力欄", ref: "...", text: "<script>alert('xss')</script>")
```

### 戦略 2: ナビゲーションテスト

ページ遷移の様々なパターンを試す：

- 戻るボタン連打
- ブラウザの戻る/進む
- タブを複数開いて操作
- ログアウト後に戻る
- URLの直接アクセス

```
mcp__playwright__browser_navigate_back
```

### 戦略 3: 状態変化テスト

アプリケーションの状態を変えながら動作確認：

- 未ログイン → ログイン
- 権限なし → 権限あり
- データなし → データあり
- オフライン → オンライン

### 戦略 4: 並行操作テスト

複数のタブで同時に操作：

```
mcp__playwright__browser_tabs (action: "new")
mcp__playwright__browser_navigate (url: "...")
```

- 同じフォームを複数タブで編集
- 同じリソースを同時に削除
- ログアウトと他の操作の並行

### 戦略 5: レスポンシブテスト

様々な画面サイズで確認：

```
mcp__playwright__browser_resize (width: 375, height: 667)  // iPhone SE
mcp__playwright__browser_resize (width: 768, height: 1024)  // iPad
mcp__playwright__browser_resize (width: 1920, height: 1080)  // Desktop
```

### 戦略 6: エラーハンドリングテスト

エラー状態を意図的に発生させる：

- ネットワークエラー（開発者ツールで throttling）
- 無効なデータ送信
- タイムアウト
- 権限エラー

## 詳細フロー

### ステップ 1: 対象の把握

テスト対象のページにアクセスし、構造を理解：

```
mcp__playwright__browser_navigate (url: "対象URL")
mcp__playwright__browser_snapshot
```

スナップショットから：
- 利用可能な要素
- インタラクション可能な部分
- フォーム構造
を把握します。

### ステップ 2: ハッピーパスの確認

まず正常系が動作することを確認：

1. 主要機能を一通り操作
2. 期待通りの動作を確認
3. 基準点として記録

### ステップ 3: エッジケースの探索

様々な「普通でない」操作を試す：

**入力系**
```
mcp__playwright__browser_type (element: "検索欄", ref: "...", text: "")  // 空検索
mcp__playwright__browser_type (element: "検索欄", ref: "...", text: "a".repeat(1000))  // 長い文字列
```

**操作系**
```
mcp__playwright__browser_click (element: "送信ボタン", ref: "...")  // 連打
mcp__playwright__browser_click (element: "送信ボタン", ref: "...")
mcp__playwright__browser_click (element: "送信ボタン", ref: "...")
```

### ステップ 4: 問題の記録

問題を発見したら即座に記録：

1. スクリーンショットを取得
```
mcp__playwright__browser_take_screenshot (filename: "bug_001.png")
```

2. コンソールエラーを確認
```
mcp__playwright__browser_console_messages (level: "error")
```

3. 現在の状態をスナップショット
```
mcp__playwright__browser_snapshot
```

### ステップ 5: Beads への登録

発見した問題を Beads に登録：

```bash
bd create --title="[Explorer] {問題タイトル}" \
  --description="再現手順:
1. ...
2. ...

期待結果: ...
実際の結果: ...
スクリーンショット: docs/debug-reports/explorer/{filename}" \
  -t bug -p {優先度}
```

## 探索チェックリスト

### フォーム探索

- [ ] 必須フィールドを空で送信
- [ ] 各フィールドに無効な値を入力
- [ ] 最大長を超える入力
- [ ] 特殊文字の入力（XSS テスト）
- [ ] コピペで入力
- [ ] オートコンプリートの動作
- [ ] Tab キーでのフォーカス移動
- [ ] Enter キーでの送信

### ナビゲーション探索

- [ ] 全リンクのクリック
- [ ] ブラウザの戻る/進む
- [ ] ブックマークからのアクセス
- [ ] 直接 URL 入力
- [ ] 404 ページの確認
- [ ] リダイレクトの動作

### 認証探索

- [ ] 未ログインでの保護ページアクセス
- [ ] セッション切れ後の操作
- [ ] 複数タブでのログイン/ログアウト
- [ ] パスワードリセットフロー
- [ ] 権限のないリソースへのアクセス

### データ操作探索

- [ ] 作成 → 編集 → 削除のフロー
- [ ] 同じデータの重複作成
- [ ] 存在しないデータの操作
- [ ] 大量データの表示
- [ ] 検索・フィルター機能

### UI/UX 探索

- [ ] ローディング状態の表示
- [ ] エラーメッセージの分かりやすさ
- [ ] 成功メッセージの表示
- [ ] ホバー状態
- [ ] フォーカス状態
- [ ] 無効化状態

## 問題分類

### 重要度別

| 重要度 | 基準 | 例 |
|--------|------|-----|
| P0 | セキュリティ/データ損失 | XSS, CSRF, データ削除不能 |
| P1 | 主要機能が動作しない | ログインできない, 購入できない |
| P2 | 機能は動くが問題あり | エラーメッセージが不適切 |
| P3 | 軽微な問題 | レイアウトずれ, typo |

### 種類別

- **機能バグ**: 期待通りに動作しない
- **UI バグ**: 表示の問題
- **UX 問題**: 使いにくさ
- **パフォーマンス**: 遅延
- **アクセシビリティ**: a11y 違反
- **セキュリティ**: 脆弱性

## レポートテンプレート

```markdown
# 探索的テストレポート

## セッション情報
- テスト日時: {日時}
- 対象機能: {機能名}
- 対象URL: {URL}
- テスト時間: {分}

## 探索範囲
- {探索した機能1}
- {探索した機能2}
- ...

## 発見した問題

### 問題 1: {タイトル}
- 重要度: P{0-3}
- 種類: {種類}
- 再現手順:
  1. ...
  2. ...
- 期待結果: ...
- 実際の結果: ...
- スクリーンショット: {path}
- Beads ID: bd-xxx

### 問題 2: ...

## 探索中の気づき
- {良かった点}
- {改善提案}

## 未探索の領域
- {今回探索できなかった部分}
```

保存先: `docs/debug-reports/explorer/`

## インタラクション例

### 例 1: 新機能の探索

ユーザー：「新しいコレクション作成機能を探索的にテストして」

プロセス：
1. コレクション作成ページに移動
2. 正常系を確認
3. 様々なエッジケースを試行
   - 空のタイトル
   - 長いタイトル
   - 特殊文字
   - 画像なし/大量画像
4. 発見した問題を記録
5. Beads に登録
6. レポート作成

### 例 2: 特定機能の深掘り

ユーザー：「認証周りを重点的に探索して」

プロセス：
1. ログインフローを確認
2. パスワードリセットを試行
3. セッション管理を確認
4. 権限チェックを確認
5. セキュリティ的な問題がないか確認
6. 発見した問題を報告

### 例 3: リグレッション確認

ユーザー：「直近の変更で壊れてないか全体をざっと見て」

プロセス：
1. 主要ページを巡回
2. 各ページでスナップショット取得
3. コンソールエラーをチェック
4. 明らかな問題がないか確認
5. 気になる点があれば深掘り
6. サマリーを報告

## 他スキルとの連携

### スキルの使い分け

| 目的 | 推奨スキル |
|------|-----------|
| 探索的テスト | playwright-explorer（このスキル） |
| E2Eテストの自動生成 | playwright-e2e-generator |
| クロスブラウザテスト | playwright-cross-browser |
| バグの再現・テストケース化 | playwright-bug-reproducer |
| パフォーマンス分析 | chrome-devtools-debugger |
| 手動テスト中の調査 | chrome-devtools-debugger |

### 協調ワークフロー

**パターン 1: 探索 → 詳細分析**

1. `playwright-explorer` で探索的テストを実行
2. バグを発見
3. `chrome-devtools-debugger` に切り替えて詳細分析
   - ネットワークリクエストの詳細
   - パフォーマンストレース
   - コンソールエラーの詳細

**パターン 2: 探索 → テストケース化**

1. `playwright-explorer` で新機能を探索
2. 重要なフローを特定
3. `playwright-e2e-generator` でテストとして記録
4. バグを発見した場合は `playwright-bug-reproducer` で再現テスト

**パターン 3: 探索 → クロスブラウザ確認**

1. `playwright-explorer` で Chrome で探索
2. 問題なければ `playwright-cross-browser` で他ブラウザ確認

### このスキルの強み

- 自由なページ探索
- 境界値テスト、ナビゲーションテストなどのチェックリスト
- 発見した問題を即座に Beads 登録

## 重要な考慮事項

### テスト環境

- 本番環境でのテストは避ける
- テストデータを使用
- テスト後のクリーンアップ

### セキュリティテスト

- XSS テストは慎重に
- 本番データへの影響を考慮
- 脆弱性を発見した場合は適切に報告

### 探索のバランス

- 広く浅くと深く狭くのバランス
- 時間制限を設ける
- 優先度の高い機能から探索

### 発見の共有

- 発見した問題は即座に記録
- 再現手順は詳細に
- スクリーンショットは必須
- Beads への登録を忘れずに
