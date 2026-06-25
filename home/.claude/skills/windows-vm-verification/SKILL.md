---
name: windows-vm-verification
description: VMware Fusion 上の Windows 検証 VM を繋ぐ/直す/調べる/検証する generic CLI (winvm)。起動不能 ("ディレクトリが空ではありません" = stale disk lock) の復旧、SSH 越しの NTFS/health 確認、cfg(windows) コードの remote 検証 (ローカル変更を scp 同期して remote コマンド実行)、NAT DHCP からの IP 解決を扱う。VMware Fusion の Windows VM を操作・検証する時に使う。
---

# Windows VM 検証スキル (winvm)

## いつ使うか

- VMware Fusion で Windows VM が起動できない ("ディレクトリが空ではありません" エラー)
- SSH 経由で VM の NTFS 健全性・開発ツールチェーンを確認したい
- macOS 側の変更を Windows VM に同期して `cfg(windows)` コードを検証したい
- NAT DHCP による IP 変化で SSH 接続先が不明になった

## winvm CLI 概要

`winvm.py` は uv で実行する単一ファイル CLI。設定は **環境変数**でも **引数**でも渡せ、引数が優先する。

| 環境変数 | 対応引数 | 意味 |
|---|---|---|
| `WINVM_VMX` | `--vmx` | `.vmx` ファイルのパス |
| `WINVM_HOST` | `--host` | SSH ホスト名 (ssh config alias) |
| `WINVM_REPO` | `--repo` | VM 上のリポジトリパス (Windows 形式) |
| `WINVM_BASE` | `--base` | 差分基点ブランチ/コミット |
| `WINVM_LEASES` | `--leases` | VMware DHCP leases ファイルパス |

## サブコマンド

### `resolve-ip`

```
winvm resolve-ip --vmx <bundle.vmx> [--leases <path>]
```

`.vmx` の `ethernet0.generatedAddress`（fallback: `ethernet0.address`）から MAC アドレスを取り出し、VMware NAT の DHCP leases ファイル（デフォルト: `/var/db/vmware/vmnet-dhcpd-vmnet8.leases`）で最新エントリを検索して IP を標準出力に出力する。マッチなしは非 0 終了。

**ポイント**: MAC アドレスを `.vmx` から直接導出するため、VM を再構築しても IP 解決がドリフトしない。

### `recover`

```
winvm recover --vmx <bundle.vmx> [--backup <dir>] [--delete] [--dry-run]
```

起動を阻む `*.lck` ロックディレクトリを除去して VM を復旧する。

- **デフォルト = 可逆 MOVE**: 各ロックをバンドル内の `.winvm-lck-backup-<timestamp>/` に移動（取り消し可能）
- `--backup <dir>`: バックアップ先を明示指定
- `--delete`: 不可逆削除（明示オプションが必要）
- `--dry-run`: 実際には何もせず対象を表示のみ

**安全機構**: `vmware-vmx` プロセスが実行中の場合は拒否する（多層防御）。

#### 手順: "ディレクトリが空ではありません" で VM が起動しない場合

1. VM を VMware Fusion から停止済みにする
2. `vmware-vmx` プロセスが残っていないことを確認

   ```bash
   pgrep -l vmware-vmx
   ```

3. `winvm recover` で stale ロックを除去（まず dry-run で確認）

   ```bash
   winvm recover --vmx ~/Virtual\ Machines/<vm>.vmwarevm/<vm>.vmx --dry-run
   winvm recover --vmx ~/Virtual\ Machines/<vm>.vmwarevm/<vm>.vmx
   ```

4. VMware Fusion から VM を再起動

### `health`

```
winvm health --host <alias> [--repo <winpath>] [--check-tools node,cargo,...]
```

SSH 越しに以下を確認する:

- NTFS ボリューム健全性 (`chkdsk` 相当)
- dirty bit の有無
- NTFS 破損イベント (Windows Event Log)
- 予期しないシャットダウンイベント
- （オプション）開発ツールチェーンの存在確認とバージョン
- （オプション）リポジトリの HEAD

**実装の注意点**:

- PowerShell スクリプトは `scp` で転送し `powershell -File` で実行する。`-EncodedCommand` は cmd.exe の 8191 文字制限に引っかかる長いコマンドで失敗するため使用しない
- 出力文字化けを防ぐため `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` をスクリプト冒頭に設定する
- ラベルは ASCII にして cp932 モジュラリティの問題を回避する

### `run`

```
winvm run --host <alias> --repo <winpath> [--base <ref>] [--skip-when-no-changes] -- <remote cmd>
```

macOS 上のローカル変更を Windows VM に同期して remote コマンドを実行する。`cfg(windows)` 対象コードの検証に使う。

1. VM の現在 HEAD を差分基点として計算
2. `git delta`・working tree・untracked の変更ファイルを `scp` で同期
3. VM をプリスティン状態にリセットしてから同期
4. 指定のリモートコマンドを実行

`--skip-when-no-changes`: 差分がない場合はスキップ（CI 的ユースケース）

## 接続セットアップ

SSH 接続先の IP は VMware NAT DHCP で動的に変わる。`~/.ssh/config` に `ProxyCommand` として `winvm resolve-ip` を組み込むことで、SSH クライアントが自動的に現在の IP を解決する。

テンプレート: `references/ssh-config.template` を参照。

### 初回セットアップ手順

1. `winvm.py` を PATH が通った場所に配置（または `winvm` シェル関数/alias を設定）

   ```bash
   # 例: uv で実行する関数を .zshrc などに追加
   winvm() { uv run /path/to/winvm.py "$@"; }
   ```

2. SSH 鍵ペアを生成（既存のものがあれば流用可）

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_winvm -C "winvm"
   ```

3. VM 上の `~/.ssh/authorized_keys` に公開鍵を登録

4. `references/ssh-config.template` を参考に `~/.ssh/config` に Host エントリを追加

5. 接続確認

   ```bash
   ssh <alias> "hostname"
   ```

## トラブルシューティング

詳細は `references/troubleshooting.md` を参照。
