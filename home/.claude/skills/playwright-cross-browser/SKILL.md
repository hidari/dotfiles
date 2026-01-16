---
name: playwright-cross-browser
description: Playwright MCPを使用してFirefox/WebKitなどChrome以外のブラウザでの動作確認を行います。クロスブラウザ互換性の問題を調査する際に使用します。
allowed-tools:
  - mcp__playwright__browser_install
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_navigate_back
  - mcp__playwright__browser_tabs
  - mcp__playwright__browser_close
  - mcp__playwright__browser_resize
  - mcp__playwright__browser_snapshot
  - mcp__playwright__browser_take_screenshot
  - mcp__playwright__browser_click
  - mcp__playwright__browser_hover
  - mcp__playwright__browser_type
  - mcp__playwright__browser_fill_form
  - mcp__playwright__browser_select_option
  - mcp__playwright__browser_press_key
  - mcp__playwright__browser_wait_for
  - mcp__playwright__browser_evaluate
  - mcp__playwright__browser_console_messages
  - mcp__playwright__browser_network_requests
  - Read
  - Write
---

# Playwright Cross-Browser スキル

このスキルは、PlaywrightのマルチブラウザサポートをフルVitに活用し、Firefox/WebKit（Safari）での動作確認を行います。

## 提供する機能

- Firefox/WebKit での動作検証
- ブラウザ間の挙動差異の特定
- クロスブラウザ互換性レポートの作成
- ブラウザ固有のバグの調査

## サポートブラウザ

| ブラウザ | エンジン | 用途 |
|---------|---------|------|
| Chromium | Blink | Chrome/Edge互換 |
| Firefox | Gecko | Firefox互換 |
| WebKit | WebKit | Safari/iOS互換 |

## コアワークフロー

クロスブラウザテストを行う際は、以下のステップに従ってください：

1. テスト対象のシナリオを明確化
2. 必要なブラウザをインストール（初回のみ）
3. 各ブラウザで同じ操作を実行
4. 差異を記録・分析
5. 互換性レポートを作成

## 詳細フロー

### ステップ 1: ブラウザのセットアップ

Playwright MCPの設定でブラウザを切り替えます。ブラウザが未インストールの場合：

```
mcp__playwright__browser_install
```

**注意**: Playwright MCPの設定ファイル（`.mcp.json`など）でブラウザを指定する必要があります。

### ステップ 2: 基準動作の記録（Chrome）

まずChromeで期待される動作を確認・記録します：

1. ページに移動
```
mcp__playwright__browser_navigate (url: "対象URL")
```

2. スナップショットを取得
```
mcp__playwright__browser_snapshot
```

3. スクリーンショットを保存
```
mcp__playwright__browser_take_screenshot (filename: "chrome_baseline.png")
```

4. 必要な操作を実行して結果を記録

### ステップ 3: 他ブラウザでの検証

Firefox/WebKitで同じ操作を実行：

1. ブラウザ設定を変更（Playwright MCP設定）
2. 同じ手順を実行
3. スクリーンショットを取得
```
mcp__playwright__browser_take_screenshot (filename: "firefox_test.png")
```

4. 差異を確認

### ステップ 4: 差異の分析

各ブラウザの結果を比較：

**確認ポイント**
- レイアウトの差異
- スタイルの適用状況
- JavaScript の動作
- フォーム要素の挙動
- アニメーション/トランジション
- Web API のサポート状況

**コンソールメッセージの確認**
```
mcp__playwright__browser_console_messages (level: "error")
```

**ネットワークリクエストの確認**
```
mcp__playwright__browser_network_requests
```

### ステップ 5: レポート作成

## ブラウザ間の一般的な差異

### CSS 関連

| 問題 | 影響ブラウザ | 対処法 |
|------|-------------|--------|
| Flexbox のギャップ | 古いSafari | `gap` の代わりに `margin` |
| Grid の auto-fit | Firefox | 明示的なサイズ指定 |
| backdrop-filter | 一部ブラウザ | フォールバック背景色 |
| :has() セレクタ | Firefox (旧) | JavaScript で代替 |

### JavaScript 関連

| 問題 | 影響ブラウザ | 対処法 |
|------|-------------|--------|
| ResizeObserver | 古いSafari | ポリフィル |
| Intl API | 一部機能 | フォールバック |
| scrollIntoView options | Safari | 簡易版を使用 |

### フォーム関連

| 問題 | 影響ブラウザ | 対処法 |
|------|-------------|--------|
| date input | Safari | カスタム日付ピッカー |
| color input | 一部 | カスタムカラーピッカー |
| autocomplete | 挙動差異 | 明示的な設定 |

## レポートテンプレート

```markdown
# クロスブラウザ互換性レポート

## 概要
- テスト日時: {日時}
- 対象URL: {URL}
- テストシナリオ: {シナリオ名}

## テスト環境
- Chromium: {バージョン}
- Firefox: {バージョン}
- WebKit: {バージョン}

## テスト結果

### 機能動作

| 機能 | Chrome | Firefox | WebKit | 備考 |
|------|--------|---------|--------|------|
| ページ表示 | ✅ | ✅ | ✅ | |
| ログイン | ✅ | ✅ | ⚠️ | Safari で入力遅延 |
| 画像アップロード | ✅ | ✅ | ❌ | WebKit で失敗 |

### 視覚的な差異

| 項目 | 状況 | スクリーンショット |
|------|------|------------------|
| ヘッダーレイアウト | 差異あり | chrome_header.png vs firefox_header.png |

### コンソールエラー

#### Chrome
- なし

#### Firefox
- `Warning: ...`

#### WebKit
- `Error: ...`

## 発見された問題

### 問題 1: {問題タイトル}

**影響ブラウザ**: WebKit
**重要度**: 高

**現象**:
{現象の説明}

**原因**:
{原因の分析}

**推奨対応**:
{対応方法}

**参考リンク**:
- {関連ドキュメント}

## 推奨アクション

1. [高] {アクション}
2. [中] {アクション}
3. [低] {アクション}
```

保存先: `docs/debug-reports/cross-browser/`
ファイル名: `{YYYYMMDD}_{HHmmss}_cross_browser_report.md`

## 一般的なクロスブラウザ問題の調査手順

### シナリオ 1: Safari で動かない

1. WebKit でページを開く
2. コンソールエラーを確認
3. ネットワークリクエストを確認
4. 問題の要素をスナップショットで特定
5. `browser_evaluate` で JavaScript の状態を確認

```
mcp__playwright__browser_evaluate (function: "() => { return { userAgent: navigator.userAgent, features: { ... } } }")
```

### シナリオ 2: Firefox でレイアウトが崩れる

1. Firefox でページを開く
2. スクリーンショットを取得
3. Chrome と比較
4. 問題の要素を特定
5. CSS の適用状況を確認

### シナリオ 3: 特定のブラウザでフォームが送信できない

1. 問題のブラウザでページを開く
2. フォーム要素をスナップショットで確認
3. 入力操作を実行
4. 送信をクリック
5. ネットワークリクエストを確認
6. コンソールエラーを確認

## ブラウザ切り替えの設定

Playwright MCPでブラウザを切り替えるには、設定ファイルを変更する必要があります：

```json
// .mcp.json の例
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@anthropic-ai/playwright-mcp@latest", "--browser", "firefox"]
    }
  }
}
```

ブラウザオプション:
- `chromium` (デフォルト)
- `firefox`
- `webkit`

## ベストプラクティス

### テスト戦略

- 重要な機能は全ブラウザでテスト
- マイナーな機能はChrome + 1つの代替ブラウザ
- Safari 向けは WebKit で十分な場合が多い

### レポートの精度

- スクリーンショットは同じビューポートサイズで取得
- 差異は具体的に記述（「違う」ではなく「10px ずれている」）
- 再現手順を明確に記録

### 問題の分類

- **Critical**: 機能が動作しない
- **Major**: UX に大きな影響
- **Minor**: 軽微な視覚的差異
- **Enhancement**: 改善の余地あり

## インタラクション例

### 例 1: 新機能のクロスブラウザ確認

ユーザー：「新しいギャラリーページをFirefoxとSafariでも確認して」

プロセス：
1. Chrome で基準動作を確認
2. Firefox に切り替えて同じ操作
3. WebKit に切り替えて同じ操作
4. 各ブラウザのスクリーンショットを比較
5. 差異があればレポート作成

### 例 2: Safari 固有のバグ調査

ユーザー：「Safari でログインできないって報告があった」

プロセス：
1. WebKit でログインページを開く
2. ログインフォームに入力
3. コンソールエラーを確認
4. ネットワークリクエストを確認
5. 原因を特定してレポート

## 他スキルとの連携

### スキルの使い分け

| 目的 | 推奨スキル |
|------|-----------|
| クロスブラウザテスト | playwright-cross-browser（このスキル） |
| E2Eテストの自動生成 | playwright-e2e-generator |
| 探索的テスト | playwright-explorer |
| バグの再現・テストケース化 | playwright-bug-reproducer |
| パフォーマンス分析 | chrome-devtools-debugger |
| 手動テスト中の調査 | chrome-devtools-debugger |

### 協調ワークフロー

**パターン 1: クロスブラウザ問題の詳細分析**

1. `playwright-cross-browser` で Firefox/WebKit での問題を発見
2. 問題が複雑な場合、`chrome-devtools-debugger` で Chromium での詳細分析
3. 比較して原因を特定

**パターン 2: 互換性問題のテストケース化**

1. `playwright-cross-browser` で問題を発見
2. `playwright-bug-reproducer` で再現テストを作成
3. 修正後、`playwright-cross-browser` で全ブラウザ確認

**パターン 3: 新機能のクロスブラウザ検証**

1. `playwright-e2e-generator` でテストを作成
2. `playwright-cross-browser` で Firefox/WebKit でも動作確認
3. 問題があれば修正してテストを更新

### このスキルの強み

- Firefox/WebKit（Safari）での動作確認
- ブラウザ間の差異を比較分析
- `browser_install` で必要なブラウザを自動セットアップ

## 重要な考慮事項

### モバイルブラウザ

- iOS Safari は WebKit と同等
- Android Chrome は Chromium と同等
- ただし、タッチイベントやビューポートの挙動は異なる場合あり

### ブラウザバージョン

- Playwright は最新の安定版ブラウザを使用
- 古いバージョンのテストには別途対応が必要

### 実際のブラウザとの差異

- Playwright のブラウザは実際のブラウザに近いが完全に同一ではない
- 重要な問題は実機でも確認することを推奨
