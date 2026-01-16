---
name: playwright-bug-reproducer
description: Playwright MCPを使用して報告されたバグを再現し、再現テストケースを自動生成します。バグ修正の検証やリグレッションテストの作成に使用します。
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
  - Glob
---

# Playwright Bug Reproducer スキル

このスキルは、報告されたバグを Playwright で再現し、再現テストケースを自動生成する機能を提供します。

## 提供する機能

- バグ報告に基づいた再現手順の実行
- 再現成功時のエビデンス収集
- 再現テストケースの自動生成
- 修正後のリグレッションテスト作成

## コアワークフロー

バグを再現してテストケース化する際は、以下のステップに従ってください：

1. バグ報告の内容を理解
2. 再現環境を準備
3. 再現手順を実行
4. 再現結果を記録
5. 再現テストコードを生成
6. 修正後の検証用テストを保存

## 詳細フロー

### ステップ 1: バグ報告の理解

Beads や GitHub Issue からバグ報告を取得：

```bash
bd show {beads-id}
```

または GitHub Issue を確認：

```bash
gh issue view {issue-number}
```

バグ報告から以下を抽出：
- 再現手順
- 期待される動作
- 実際の動作
- 発生環境
- スクリーンショット/動画（あれば）

### ステップ 2: 環境準備

バグが発生する条件を整える：

1. 適切なブラウザサイズを設定
```
mcp__playwright__browser_resize (width: {width}, height: {height})
```

2. 必要なページに移動
```
mcp__playwright__browser_navigate (url: "{URL}")
```

3. 必要な状態を作成（ログイン、データ準備など）

### ステップ 3: 再現手順の実行

報告された手順を一つずつ実行：

**各ステップで状態を記録**

```
// 手順1を実行前
mcp__playwright__browser_snapshot
mcp__playwright__browser_take_screenshot (filename: "step1_before.png")

// 手順1を実行
mcp__playwright__browser_click (element: "...", ref: "...")

// 手順1を実行後
mcp__playwright__browser_snapshot
mcp__playwright__browser_take_screenshot (filename: "step1_after.png")
mcp__playwright__browser_console_messages (level: "error")
```

### ステップ 4: 再現結果の判定

**再現成功の場合**

1. バグ状態のエビデンスを収集
```
mcp__playwright__browser_take_screenshot (filename: "bug_reproduced.png")
mcp__playwright__browser_console_messages
mcp__playwright__browser_network_requests
```

2. 状態を詳細に記録
```
mcp__playwright__browser_snapshot
```

**再現失敗の場合**

1. 環境の違いを確認
2. 手順の解釈を見直し
3. 追加情報を報告者に確認

### ステップ 5: 再現テストコードの生成

再現できた手順をテストコードに変換：

```typescript
import { test, expect } from '@playwright/test';

test.describe('Bug: {バグタイトル}', () => {
  test('should reproduce issue #{issue-number}', async ({ page }) => {
    // 再現手順
    await page.goto('{URL}');

    // 手順1
    await page.getByRole('button', { name: '{ボタン名}' }).click();

    // 手順2
    await page.getByRole('textbox', { name: '{入力欄名}' }).fill('{入力値}');

    // バグの検証（現在の動作）
    // Note: このテストはバグ修正後に失敗するようになる
    await expect(page.getByText('{エラーメッセージ}')).toBeVisible();
  });

  test('should work correctly after fix', async ({ page }) => {
    // 修正後に期待される動作
    await page.goto('{URL}');

    // 同じ手順
    await page.getByRole('button', { name: '{ボタン名}' }).click();
    await page.getByRole('textbox', { name: '{入力欄名}' }).fill('{入力値}');

    // 正しい動作の検証
    await expect(page.getByText('{成功メッセージ}')).toBeVisible();
  });
});
```

### ステップ 6: テストの検証

生成したテストを `browser_run_code` で検証：

```
mcp__playwright__browser_run_code (code: "async (page) => {
  // 再現コードを実行してみる
}")
```

### ステップ 7: テストファイルの保存

```
保存先: e2e/tests/bugs/issue-{number}.spec.ts
```

## バグ再現のテクニック

### 環境依存のバグ

**画面サイズ依存**
```
mcp__playwright__browser_resize (width: 320, height: 568)  // 小さい画面
```

**ブラウザ依存**
→ `playwright-cross-browser` スキルと連携

### タイミング依存のバグ

**遅いネットワーク**
```
mcp__playwright__browser_evaluate (function: "() => { /* スロットル設定 */ }")
```

**操作の速度**
```
mcp__playwright__browser_type (element: "...", ref: "...", text: "...", slowly: true)
```

### 状態依存のバグ

**特定のデータ状態**
- テストデータの準備
- シードデータの確認

**認証状態**
- ログイン/ログアウト状態
- セッションの有効期限

### 競合状態のバグ

**複数タブでの操作**
```
mcp__playwright__browser_tabs (action: "new")
// タブ1で操作
mcp__playwright__browser_tabs (action: "select", index: 0)
// タブ0で操作
```

**連続した操作**
```
// 素早い連続クリック
mcp__playwright__browser_run_code (code: "async (page) => {
  const button = page.getByRole('button', { name: 'Submit' });
  await Promise.all([
    button.click(),
    button.click(),
  ]);
}")
```

## 再現レポートテンプレート

```markdown
# バグ再現レポート

## バグ情報
- Issue: #{number} / Beads: {beads-id}
- タイトル: {タイトル}
- 報告日: {日付}
- 報告者: {報告者}

## 再現結果
- ステータス: ✅ 再現成功 / ❌ 再現失敗 / ⚠️ 部分的に再現

## 再現環境
- ブラウザ: Chromium {version}
- 画面サイズ: {width}x{height}
- 認証状態: {状態}

## 再現手順（実行した内容）

### 手順 1: {説明}
- 実行: {実行した操作}
- 結果: {結果}
- スクリーンショット: step1.png

### 手順 2: {説明}
...

## 再現時の観察

### コンソールエラー
```
{エラーメッセージ}
```

### ネットワークエラー
```
{エラーメッセージ}
```

### 画面状態
{スナップショットからの情報}

## 原因の推測
{分析結果}

## 生成したテストケース
- ファイル: e2e/tests/bugs/issue-{number}.spec.ts
- 内容: {簡単な説明}

## 追加情報
{その他の気づき}
```

保存先: `docs/debug-reports/bugs/`
ファイル名: `{YYYYMMDD}_issue_{number}_reproduction.md`

## テストコードパターン

### パターン 1: 単純なバグ再現

```typescript
test('Issue #123: ボタンクリックでエラー', async ({ page }) => {
  await page.goto('/feature');
  await page.getByRole('button', { name: 'Action' }).click();

  // バグ: エラーメッセージが表示される
  // 修正後: この expect は失敗し、下の expect が成功する
  await expect(page.getByText('予期しないエラー')).not.toBeVisible();
  await expect(page.getByText('成功しました')).toBeVisible();
});
```

### パターン 2: 入力値によるバグ

```typescript
test('Issue #456: 特殊文字でエラー', async ({ page }) => {
  await page.goto('/form');

  // バグを引き起こす入力
  await page.getByRole('textbox', { name: 'Title' }).fill('Test <script>');
  await page.getByRole('button', { name: 'Submit' }).click();

  // XSS 攻撃が防がれることを確認
  await expect(page.locator('script')).not.toBeAttached();
  await expect(page.getByText('保存しました')).toBeVisible();
});
```

### パターン 3: 画面サイズによるバグ

```typescript
test('Issue #789: モバイルでメニューが表示されない', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto('/');

  // ハンバーガーメニューをクリック
  await page.getByRole('button', { name: 'Menu' }).click();

  // メニューが表示されることを確認
  await expect(page.getByRole('navigation')).toBeVisible();
});
```

### パターン 4: 競合状態によるバグ

```typescript
test('Issue #101: 連続クリックでデータ重複', async ({ page }) => {
  await page.goto('/create');

  // フォーム入力
  await page.getByRole('textbox', { name: 'Name' }).fill('Test Item');

  // 送信ボタンを連続クリック
  const submitButton = page.getByRole('button', { name: 'Create' });
  await submitButton.click();
  await submitButton.click(); // 2回目は無視されるべき

  // 結果を確認
  await page.goto('/list');
  const items = page.getByText('Test Item');
  await expect(items).toHaveCount(1); // 1つだけ作成されている
});
```

## インタラクション例

### 例 1: Issue からバグを再現

ユーザー：「#42 のバグを再現してテストにして」

プロセス：
1. `gh issue view 42` でバグ内容を確認
2. 再現環境を準備
3. 報告された手順を実行
4. バグを再現
5. スクリーンショットを取得
6. テストコードを生成
7. `e2e/tests/bugs/issue-42.spec.ts` に保存
8. 再現レポートを作成

### 例 2: Beads からバグを再現

ユーザー：「bd-abc123 のバグを再現して」

プロセス：
1. `bd show bd-abc123` でバグ内容を確認
2. 再現手順を実行
3. 結果を記録
4. テストコードを生成

### 例 3: 再現できないバグの調査

ユーザー：「このバグ再現できる？」

プロセス：
1. 報告された手順を試行
2. 再現できない場合は環境の違いを確認
3. 追加の情報を収集
4. 部分的な再現や類似の問題を確認
5. 調査結果をレポート

## 他スキルとの連携

### スキルの使い分け

| 目的 | 推奨スキル |
|------|-----------|
| バグの再現・テストケース化 | playwright-bug-reproducer（このスキル） |
| E2Eテストの自動生成 | playwright-e2e-generator |
| クロスブラウザテスト | playwright-cross-browser |
| 探索的テスト | playwright-explorer |
| パフォーマンス分析 | chrome-devtools-debugger |
| 手動テスト中の調査 | chrome-devtools-debugger |

### 協調ワークフロー

**パターン 1: 再現 → 詳細分析**

1. `playwright-bug-reproducer` でバグを再現
2. 再現成功したら `chrome-devtools-debugger` で詳細分析
   - ネットワークリクエストの詳細
   - パフォーマンス問題の調査
   - JavaScript エラーのスタックトレース

**パターン 2: 再現 → 修正 → リグレッションテスト**

1. `playwright-bug-reproducer` でバグ再現テストを作成
2. バグを修正
3. `playwright-e2e-generator` で正常系のテストも追加
4. 両方のテストが通ることを確認

**パターン 3: クロスブラウザでのバグ再現**

1. 「Safari で動かない」というバグ報告
2. `playwright-bug-reproducer` で WebKit で再現を試みる
3. 再現成功したら `playwright-cross-browser` で他ブラウザでも確認

### このスキルの強み

- Beads/GitHub Issue と連携したバグ追跡
- 再現手順の詳細なドキュメント化
- 修正確認用テストの自動生成

## ベストプラクティス

### 再現の正確性

- 報告された手順を忠実に実行
- 環境条件を可能な限り合わせる
- 再現できない場合は追加情報を求める

### テストの品質

- 再現テストは明確で読みやすく
- 1テスト1バグの原則
- 修正後に意味のあるテストになるよう設計

### コミュニケーション

- 再現結果は速やかに共有
- 再現できない場合は正直に報告
- 追加情報が必要な場合は具体的に質問

## Beads との連携

バグ再現後の Beads 更新：

```bash
# 再現成功時
bd update {beads-id} --status in_progress
bd comment {beads-id} "再現成功。テストケース作成: e2e/tests/bugs/issue-{number}.spec.ts"

# 再現失敗時
bd comment {beads-id} "再現できず。追加情報が必要: {必要な情報}"
```
