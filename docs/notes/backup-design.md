# backup.sh 拡張設計書

このドキュメントは、`scripts/backup.sh` の拡張設計と実装結果をまとめたものです。

## 概要

既存の `backup.sh` を拡張し、以下の機能を追加しました：

1. ボリューム全体だけでなく、ディレクトリ単位での指定
2. 複数のボリューム・ディレクトリのペアを指定可能
3. 既存の単一ペア設定（backup.conf）との後方互換性

## 設計方針

| 項目 | 選択 |
|------|------|
| 言語 | Bash のまま拡張（Python 移行なし） |
| 設定形式 | シェル変数形式を拡張（外部依存なし） |
| 互換性 | 既存の backup.conf がそのまま動作 |

## 動作モード

スクリプトは自動的に設定モードを判定します：

```
1. BACKUP_PAIRS が定義されている → 拡張モードで動作
2. SOURCE_STORAGE/DESTINATION_STORAGE がある → レガシーモードで動作
3. どちらもない → エラー終了
```

## 設定ファイル形式

### レガシーモード（既存、そのまま動作）

```bash
SOURCE_STORAGE="/Volumes/Luna-P"
DESTINATION_STORAGE="/Volumes/Luna-S"
MINIMUM_FREE_SPACE_GB=100
LOG_RETENTION_DAYS=90
```

### 拡張モード（新規追加）

```bash
# 形式: "名前|ソースパス|デスティネーションパス|除外パターン(カンマ区切り,省略可)"
BACKUP_PAIRS=(
    "メインSSD|/Volumes/<MAIN_SSD>|/Volumes/Luna-S"
    "写真フォルダ|/Volumes/Data/Photos|/Volumes/Backup/Photos|*.tmp,cache/"
    "開発用|/Volumes/Dev/Projects|/Volumes/Backup/Projects|node_modules,.venv"
)

MINIMUM_FREE_SPACE_GB=100
LOG_RETENTION_DAYS=90

# オプション: ログディレクトリを明示的に指定
# LOG_BASE_DIR="/Users/username/.backup_logs"

# オプション: エラー時の動作（continue / stop）
# ERROR_BEHAVIOR="continue"
```

## 実装した関数

### 新規追加

| 関数名 | 役割 |
|--------|------|
| `detect_config_mode()` | 設定モード判定（extended/legacy/none） |
| `parse_backup_pair()` | パイプ区切り文字列をパースして変数に展開 |
| `get_path_type()` | パスの種類判定（volume/directory/local） |
| `extract_volume_path()` | パスから親ボリュームを抽出 |
| `check_path()` | 拡張版パス検証（ディレクトリ対応） |
| `execute_backup_pair()` | 単一ペアのバックアップ実行 |
| `run_legacy_mode()` | レガシーモードの処理 |
| `run_extended_mode()` | 拡張モードの処理 |
| `display_all_pairs_info()` | 全ペアの情報表示 |
| `display_summary()` | 実行結果サマリー表示 |
| `setup_logging()` | ログ設定の初期化 |
| `finalize_backup()` | 終了処理 |

### 既存関数（再利用）

- `log()`, `error_exit()` - そのまま利用
- `check_mount()` - `check_path()` から呼び出し
- `check_disk_space()` - そのまま利用
- `filter_rsync_output()` - そのまま利用
- `cleanup_old_logs()` - そのまま利用
- `show_filtered_errors_summary()` - そのまま利用

## 終了コード

| コード | 意味 |
|--------|------|
| 0 | 全て成功 |
| 1 | 設定エラー（起動前） |
| 2 | 一部のペアが失敗（continue モード時） |
| 3 | 全てのペアが失敗 |
| 23 | 非致命的エラー（成功扱い） |

## パスの種類判定

`check_path()` 関数は、指定されたパスの種類を自動判定して適切な検証を行います：

| パス形式 | 種類 | 検証内容 |
|----------|------|----------|
| `/Volumes/XXX` | volume | マウント確認（mount コマンド） |
| `/Volumes/XXX/path/to/dir` | directory | 親ボリュームのマウント確認 + ディレクトリ存在確認 |
| `/Users/XXX/...` | local | ディレクトリ存在確認のみ |

## 制限事項

- パス内にパイプ文字 `|` は使用不可
- 除外パターン内にカンマ `,` は使用不可

## 将来の拡張ポイント

- 並列実行オプション（`&` と `wait` の活用）
- バックアップの優先順位設定
- メール/Slack通知機能
- 増分バックアップオプション

## 対象ファイル

- `scripts/backup.sh` - メインスクリプト（拡張済み）
- `scripts/backup.example.conf` - テンプレート（拡張設定サンプル追加済み）

## 使用方法

### レガシーモードで使用（従来通り）

1. `backup.example.conf` を `backup.conf` にコピー
2. `SOURCE_STORAGE` と `DESTINATION_STORAGE` を設定
3. `./backup.sh` で実行

### 拡張モードで使用（複数ペア）

1. `backup.example.conf` を `backup.conf` にコピー
2. `BACKUP_PAIRS` 配列を設定（`SOURCE_STORAGE`/`DESTINATION_STORAGE` はコメントアウト）
3. `./backup.sh` で実行

### ドライランモード

実際のコピーを行わずに動作確認：

```bash
./backup.sh --dry-run
# または
./backup.sh -n
```
