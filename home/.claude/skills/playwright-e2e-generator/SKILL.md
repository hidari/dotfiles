---
name: playwright-e2e-generator
description: Playwright MCPを使用してブラウザ操作を記録し、E2Eテストコードを自動生成します。テスト駆動開発やリグレッションテストの作成に使用します。
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
  - Glob
---

# Playwright E2E Generator スキル

このスキルは、Playwrightを使用してブラウザ操作を実行しながら、E2Eテストコードを自動生成する機能を提供します。

## 提供する機能

- ブラウザ操作の記録とテストコード生成
- 生成したコードの即座の検証（`browser_run_code`）
- アサーションの自動提案
- プロジェクトのテスト規約に沿ったコード生成

## コアワークフロー

E2Eテストを生成する際は、以下のステップに従ってください：

1. 対象機能のユーザーストーリーを理解
2. テストシナリオを設計
3. ブラウザを操作しながらコードを記録
4. アサーションを追加
5. 生成コードを検証
6. テストファイルとして保存

## 詳細フロー

### ステップ 1: テストシナリオの設計

テスト対象の機能を理解し、テストシナリオを設計します：

```
テスト名: ログインフロー
前提条件: 未ログイン状態
手順:
  1. ログインページにアクセス
  2. メールアドレスを入力
  3. OTPを送信
  4. OTPを入力
  5. ホーム画面に遷移することを確認
期待結果: ユーザーがログイン状態になる
```

### ステップ 2: ブラウザの準備

```
mcp__playwright__browser_tabs (action: "new")
mcp__playwright__browser_navigate (url: "対象URL")
```

### ステップ 3: ページ状態の確認

操作前にページのスナップショットを取得して要素を把握：

```
mcp__playwright__browser_snapshot
```

スナップショットから `ref` 値を取得し、操作に使用します。

### ステップ 4: 操作の実行と記録

各操作を実行しながら、対応するPlaywrightコードを記録します：

**クリック操作**
```
mcp__playwright__browser_click (element: "ログインボタン", ref: "button[Login]")
```
→ 生成コード: `await page.getByRole('button', { name: 'Login' }).click();`

**テキスト入力**
```
mcp__playwright__browser_type (element: "メールアドレス入力欄", ref: "textbox[Email]", text: "test@example.com")
```
→ 生成コード: `await page.getByRole('textbox', { name: 'Email' }).fill('test@example.com');`

**フォーム入力（複数フィールド）**
```
mcp__playwright__browser_fill_form (fields: [...])
```

**待機**
```
mcp__playwright__browser_wait_for (text: "ようこそ")
```
→ 生成コード: `await expect(page.getByText('ようこそ')).toBeVisible();`

### ステップ 5: アサーションの追加

テスト成功の判定に必要なアサーションを追加：

- 要素の存在確認
- テキストの確認
- URLの確認
- ネットワークリクエストの確認

```
mcp__playwright__browser_snapshot
```
→ 現在の状態からアサーション対象を特定

### ステップ 6: 生成コードの検証

`browser_run_code` で生成したコードが正しく動作するか検証：

```
mcp__playwright__browser_run_code (code: "async (page) => { ... }")
```

### ステップ 7: テストファイルの保存

プロジェクトの規約に沿ってテストファイルを保存：

```
保存先: e2e/tests/{機能名}.spec.ts
```

## コード生成テンプレート

### 基本テンプレート

```typescript
import { test, expect } from '@playwright/test';

test.describe('{機能名}', () => {
  test('{テスト名}', async ({ page }) => {
    // Arrange: 前提条件のセットアップ
    await page.goto('{URL}');

    // Act: 操作の実行
    {記録した操作}

    // Assert: 結果の検証
    {アサーション}
  });
});
```

### ログインが必要なテスト

```typescript
import { test, expect } from '@playwright/test';

test.describe('{機能名}', () => {
  test.beforeEach(async ({ page }) => {
    // ログイン処理
    await page.goto('/login');
    // ...
  });

  test('{テスト名}', async ({ page }) => {
    // テスト本体
  });
});
```

## ref値からセレクタへの変換ルール

スナップショットで取得した `ref` 値を Playwright セレクタに変換：

| ref パターン | Playwright セレクタ |
|-------------|-------------------|
| `button[Submit]` | `page.getByRole('button', { name: 'Submit' })` |
| `textbox[Email]` | `page.getByRole('textbox', { name: 'Email' })` |
| `link[Home]` | `page.getByRole('link', { name: 'Home' })` |
| `checkbox[Remember]` | `page.getByRole('checkbox', { name: 'Remember' })` |
| `heading[Welcome]` | `page.getByRole('heading', { name: 'Welcome' })` |
| `text=Something` | `page.getByText('Something')` |

## ベストプラクティス

### テストの独立性

- 各テストは独立して実行可能であること
- 前のテストの状態に依存しない
- 必要なセットアップは各テストで行う

### セレクタの選択

優先順位（高→低）：
1. `getByRole` - アクセシビリティロールベース（推奨）
2. `getByText` - テキストコンテンツベース
3. `getByTestId` - data-testid 属性
4. `locator` - CSS/XPath（最後の手段）

### 待機戦略

- 固定時間の待機（`waitForTimeout`）は避ける
- 条件ベースの待機（`waitFor`）を使用
- ネットワークアイドル待機も活用

### アサーション

- 成功パスだけでなく、失敗パスもテスト
- 1テストにつき1つの主要なアサーション
- 関連するアサーションはグループ化

## プロジェクト固有の設定

### テストファイルの配置

```
e2e/
├── tests/
│   ├── auth/           # 認証関連
│   ├── gallery/        # ギャラリー機能
│   ├── collection/     # コレクション機能
│   └── creator/        # クリエイター機能
├── fixtures/           # テストフィクスチャ
└── playwright.config.ts
```

### 環境設定

ローカル開発環境でテストを実行する場合：
- フロントエンド: `http://localhost:5173`
- バックエンド: `http://localhost:8080`

## インタラクション例

### 例 1: シンプルなフォームテスト生成

ユーザー：「お問い合わせフォームのE2Eテストを作って」

プロセス：
1. お問い合わせページに移動
2. フォーム要素をスナップショットで確認
3. 各フィールドに入力
4. 送信ボタンをクリック
5. 成功メッセージを確認
6. テストコードを生成・検証
7. `e2e/tests/contact.spec.ts` に保存

### 例 2: 認証フローのテスト生成

ユーザー：「ログインからログアウトまでのフローをテストにして」

プロセス：
1. ログインページに移動
2. 認証情報を入力
3. ログイン成功を確認
4. ダッシュボードに遷移することを確認
5. ログアウトボタンをクリック
6. ログアウト完了を確認
7. テストコードを生成・保存

### 例 3: 既存テストの更新

ユーザー：「ギャラリーのテストにいいね機能のテストを追加して」

プロセス：
1. 既存のテストファイルを読み込み
2. いいねボタンの動作を確認
3. 新しいテストケースを追加
4. テストを実行して検証
5. ファイルを更新

## 他スキルとの連携

### スキルの使い分け

| 目的 | 推奨スキル |
|------|-----------|
| E2Eテストの自動生成 | playwright-e2e-generator（このスキル） |
| クロスブラウザテスト | playwright-cross-browser |
| 探索的テスト | playwright-explorer |
| バグの再現・テストケース化 | playwright-bug-reproducer |
| パフォーマンス分析 | chrome-devtools-debugger |
| 手動テスト中の調査 | chrome-devtools-debugger |

### 協調ワークフロー

**パターン 1: バグ修正後のリグレッションテスト追加**

1. `playwright-bug-reproducer` でバグ再現テストを作成
2. バグを修正
3. `playwright-e2e-generator` で正常系のテストを追加
4. 両方のテストが通ることを確認

**パターン 2: 探索的テストからの発見をテスト化**

1. `playwright-explorer` で新機能を探索
2. 問題なければ、重要なフローを特定
3. `playwright-e2e-generator` でテストとして記録

**パターン 3: クロスブラウザ対応後のテスト**

1. `playwright-cross-browser` で互換性問題を発見
2. 問題を修正
3. `playwright-e2e-generator` でクロスブラウザテストを追加

### このスキルの強み

- `browser_run_code` で生成したコードを即座に検証
- ref値からPlaywrightセレクタへの変換ルール内蔵
- プロジェクト規約に沿ったテストテンプレート

## 重要な考慮事項

### テストデータ

- テスト用のシードデータを使用
- 本番データには依存しない
- 各テスト後にクリーンアップ

### フレーキーテスト対策

- 適切な待機を設定
- リトライ設定を活用
- ネットワーク状態を考慮

### CI/CD 連携

- 生成したテストは `make e2e-test-full` で実行可能
- GitHub Actions での自動実行を考慮
