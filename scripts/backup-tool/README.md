# ストレージバックアップツール

macOS 向けの rsync ベース外部ストレージバックアップツールです。
`rsync` を `subprocess` 経由で呼び出す Python CLI として実装されており、
ユニットテストと型検査によって信頼性を担保しています。

## 特徴

- rsync の `--delete-before` で転送前に不要ファイルを削除してから同期
- バックアップペアを TOML で宣言的に定義
- macOS システムファイル (`.DS_Store`、`._*` など) は自動で除外
- 既知の無害なエラー (`.Spotlight-V100` の削除失敗など) は自動抑制
- 容量不足・未マウント・権限不足を事前にチェック
- `--log-format=json` で構造化ログに切り替え可能
- ログファイルは日次ローテーションされ、古いものは自動削除
- Dry-run モードで実行内容を事前確認可能

## 必要要件

- macOS: Catalina 10.15 以降を推奨
- `uv`: Python 実行環境と依存関係の管理 ([インストール方法](https://docs.astral.sh/uv/))
- `rsync`: Homebrew 版 3.0.0 以降 (macOS デフォルトの openrsync は `--delete-before` の挙動が異なり既知のバグがある)

```bash
brew install uv rsync
```

## セットアップ

### 1. 依存関係のインストール

```bash
cd ~/Develop/dotfiles/scripts/backup-tool
uv sync
```

これで `.venv/` に Python 本体と必要パッケージが入ります。

### 2. PATH に通す

```bash
mkdir -p ~/.local/bin
ln -sf ~/Develop/dotfiles/scripts/backup-tool/backup ~/.local/bin/backup
```

`~/.local/bin` が PATH に含まれていることを確認してください。

### 3. 設定ファイルの作成

テンプレートをコピーして自分の環境に合わせて編集します。

```bash
cd ~/Develop/dotfiles/scripts/backup-tool
cp backup.example.toml backup.toml
$EDITOR backup.toml
```

主な項目:

| キー | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `minimum_free_space_gb` | int | yes | 確保しておきたいマージン (GB) |
| `log_retention_days` | int | yes | ログファイルの保持日数 |
| `log_base_dir` | string | no | ログ出力先 (未指定時は設定ファイル隣の `.backup_logs/`) |
| `error_behavior` | `"continue"` \| `"stop"` | no | エラー発生時の挙動 (デフォルト `continue`) |
| `additional_excludes` | string 配列 | no | 全ペア共通で追加する除外パターン |
| `[[backup_pairs]]` | テーブル配列 | yes | 1 ペア以上のバックアップ対象 |

`backup_pairs` の各要素には `name` / `source` / `destination` が必須で、
`excludes` はオプションです (ペア固有の除外パターン)。

### 4. 旧 backup.conf を使っていた場合の移行

既存の `backup.conf` (Bash 版) がある場合は、以下のコマンドで
TOML フォーマットに自動変換できます。

```bash
backup migrate-config
```

- 既存の `backup.conf` は `backup.conf.bak` にリネームされます
- `backup.toml` が既に存在する場合は上書きせずエラー終了します
- 入出力パスを明示したい場合は `--from PATH` / `--to PATH` を指定

## 使い方

### 通常実行

```bash
backup
```

設定内容の確認プロンプトが表示され、`y` で実行を開始します。
非 TTY 環境 (cron など) および `--log-format=json` 指定時は
確認プロンプトをスキップします。

### Dry-run (事前確認)

```bash
backup --dry-run
# または
backup -n
```

初めて使うとき、または `--delete-before` の影響が気になるときは
必ず dry-run で動作を確認してください。

### JSON ログ

ログを 1 行 1 JSON オブジェクトで出力します。
cron 運用やログ集約システムへの投入に便利です。

```bash
backup --log-format=json
```

### 設定ファイルを明示する

```bash
backup --config /path/to/custom.toml
```

## 除外されるファイル

以下のファイル・ディレクトリは自動的に除外されます。詳細は
`src/backup_tool/excludes.py` を参照してください。

### macOS システムファイル

- `.DS_Store` / `._*` / `.localized` / `.VolumeIcon.icns`
- `.Spotlight-V100` / `.metadata_never_index*`
- `.Trashes` / `.TemporaryItems`
- `.fseventsd` / `.DocumentRevisions-V100`
- `.ql_*` / `.apdisk`
- `.PKInstallSandboxManager*`
- `.AppleDB` / `.AppleDesktop`

### Windows システムファイル

- `Thumbs.db` / `desktop.ini`

個別に除外を追加したい場合は `backup.toml` の
`additional_excludes` (全ペア共通) か `[[backup_pairs]].excludes`
(ペア固有) を編集します。

除外パターンはあくまで「ソースから転送しない」ルールで、バックアップ先に
既存の excludes 対象ファイルがあっても削除はしません。これは macOS 保護
ディレクトリ (`.Trashes` / `.Spotlight-V100` など) への削除試行が
`Operation not permitted` を誘発するのを防ぐためです。

## ログ

ログは既定で `.backup_logs/backup_YYYYMMDD_HHMMSS.log` として保存されます。
`log_base_dir` を設定すれば出力先を変更できます。

```
/Volumes/Primary/.backup_logs/
  ├── backup_20260401_143000.log
  ├── backup_20260402_093000.log
  └── ...
```

保持期間を超えた古いログは実行時に自動削除されます。

## 終了コード

| コード | 意味 |
| --- | --- |
| 0 | 全ペアが成功 (rsync code 23 の部分的成功を含む) |
| 1 | 設定不備・ユーザー中止・マイグレーション失敗 |
| 2 | 一部のペアが失敗 |
| 3 | 全ペアが失敗 |

## 開発者向け

### 依存関係

開発用パッケージ (`pytest`, `pytest-cov`, `ruff`, `mypy`) は `uv sync`
で自動的にインストールされます。

### テスト

```bash
uv run pytest
uv run pytest --cov=backup_tool --cov-report=term-missing
```

### 静的検査

```bash
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src tests
```

## トラブルシューティング

### 設定ファイルが見つかりません

`backup.toml` が存在しない状態でコマンドを実行すると表示されます。
`backup.example.toml` をコピーするか、旧 `backup.conf` がある場合は
`backup migrate-config` で変換してください。

### マウントされていません

指定したボリュームがマウントされていないか、パスが間違っている可能性があります。

```bash
ls /Volumes/
```

### 総容量が不足しています

バックアップ先の総容量がソースデータ + マージンに満たない場合に表示されます。
対処:

1. `backup.toml` の `minimum_free_space_gb` を小さくする (最低 50 GB 程度を推奨)
2. より大きなストレージに変更する

### Operation not permitted

`.Spotlight-V100` や `.Trashes` へのアクセス拒否エラーは macOS の保護機能による
正常動作で、ログ上は「抑制されたシステムエラー」として集計のみ表示されます。
実データには影響しません。

### 部分的成功 (rsync code 23)

rsync が「一部ファイルを転送できなかった」ことを示すコードです。多くは
システム保護ファイルの削除失敗で、データのバックアップ自体は成功しています。
詳細はログファイルで確認してください。

## 注意事項

- このツールは `rsync --delete-before` を使用します。
  バックアップ元にないファイルはバックアップ先から削除されます。
  初めて使うときは必ず dry-run で確認してください。
- 設定ファイルの source / destination を取り違えるとデータが失われます。
  設定を保存する前に必ず見直してください。
- cron / launchd で定期実行する場合は `--log-format=json` と
  ログの定期的な監視をセットで設定することを推奨します。
