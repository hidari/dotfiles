# 設計: 汎用 Skill `windows-vm-verification`

作成日: 2026-06-26
ステータス: 設計確定 (実装計画待ち)

## 目的

VMware Fusion 上の Windows 検証 VM を「繋ぐ・直す・調べる・検証する」一連の操作を、
プロジェクト非依存の再利用可能な Skill として切り出す。現状この機能は relay リポジトリの
`crates/xtask/src/winvm_check.rs` (sync-and-run) と `~/.ssh` の dotfile (IP resolver / ssh config) と
セッション中のアドホックな ops 手順 (stale-lock 復旧 / health チェック) に散在しており、
他プロジェクトから再利用できない。

非目標 (out of scope):
- VM の作成・プロビジョニング自体 (別途 docs/Windows検証環境構築.md が担う)
- VMware Fusion 以外のハイパーバイザ対応 (NAT lease / vmrun に依存するため Fusion 専用)
- relay 固有の検証コマンド (check-desktop 等) のロジック — これは呼び出し側が渡す

## 背景: 今セッションで判明した2バグ (設計の動機)

1. 起動不能 "ディレクトリが空ではありません": クラッシュで machine-id が変わり、VMware が自分の
   古い disk ロックを「別マシン」扱いして自動破棄できず `FileLockWaitForPossession timeout` →
   stale `仮想ディスク.vmdk.lck` を手で消すまで起動不能。
2. SSH 不通: IP resolver (`~/.ssh/relay-winvm-ip.sh`) がハードコード MAC を持ち、VM 作り直しで
   NIC MAC が変わると死んだ lease の IP を返す (doc は更新済みだが dotfile への反映漏れ = drift)。

本設計は (1) を `recover` サブコマンドで手順化し、(2) を **MAC を `.vmx` から動的導出**することで
ドリフトの class ごと根絶する。

## アーキテクチャ

### generic / 固有の境界

境界線は「VM 1台を特定する情報」= `.vmx` バンドルパス・ssh host alias・remote repo パス・実行コマンド。
これらは全て **呼び出し側 (relay の xtask ラッパー) が注入**し、`winvm.py` 本体はハードコードしない。
よって公開リポ (dotfiles) に置いても秘密を含まない。

### 配置

```
dotfiles/home/.claude/skills/windows-vm-verification/   公開・generic
├── SKILL.md            いつ/どう使う・接続セットアップ・復旧・health・検証の手順書
├── winvm.py            uv 単一ファイル CLI (PEP723, stdlib のみ想定)
├── test_winvm.py       純粋ロジックの spec テスト
└── references/
    ├── ssh-config.template     ~/.ssh/config Host 雛形 (ProxyCommand 込み)
    └── troubleshooting.md      既知症状 ("Host is down"=stale lease 等) → 対処

dotfiles bootstrap: winvm.py を ~/.local/bin/winvm (PATH 上) へ symlink (または uv tool install)

relay 側 (薄いラッパー、固有設定のみ)
└── crates/xtask/src/winvm_check.rs  → Command::new("winvm") を relay 設定で呼ぶ数行へ縮小
```

### relay からの依存形態

relay の xtask は既に `ssh` / `scp` / `vmrun` / `git` を `Command::new(...)` で叩いている。
`winvm` を **PATH 上の外部 CLI** として1つ追加するだけで、依存の種類は増えない。
home パスのハードコードはしない。`winvm` 未導入時は `vmrun` 不在と同種の親切なエラーを出す。

## コンポーネント: `winvm.py` サブコマンド

全て generic。設定は引数 + env (`WINVM_VMX` / `WINVM_HOST` / `WINVM_REPO` / `WINVM_BASE` /
`WINVM_LEASES`)。引数が env を上書きする。

| subcommand | 役割 | 主な入力 | 出力/効果 |
|---|---|---|---|
| `resolve-ip` | VMware NAT lease から VM 現 IP を解決 | `--vmx`, `--leases` | IP を stdout。MAC を `.vmx` の `ethernet0.generatedAddress` (static 時は `ethernet0.address`) から導出。無一致は非ゼロ終了 |
| `recover` | stale `*.lck` を除去し起動不能を解消 | `--vmx`, `--backup <dir>`, `--dry-run` | `vmware-vmx` 稼働中は中止 (多層防御)。既定は backup へ移動 (可逆)。除去内容を報告 |
| `health` | SSH 越しに VM 健全性を検査 | `--host`, `--repo`, `--check-tools` | NTFS health/dirty bit/破損イベント/予期しないshutdown を検査 (generic) + toolchain/repo (parameterize) |
| `run` | git 差分を scp 同期して remote コマンド実行 | `--host`, `--repo`, `--base`, `--skip-when-no-changes`, `-- <cmd>` | VM HEAD を diff base に同期 → reset → scp delta → remote 実行 (winvm_check.rs の移植) |

### resolve-ip と ssh config の接続

ssh config の `ProxyCommand` を `~/.ssh/relay-winvm-ip.sh` (awk) から
`winvm resolve-ip --vmx <path>` へ差し替える。awk resolver は廃止。
これにより MAC drift が設計レベルで解消する。host 鍵は `HostKeyAlias` で固定し IP churn を吸収 (現状維持)。

レイヤリング: `resolve-ip` は primitive で、ssh config の ProxyCommand が消費する。
`health` / `run` の `--host` は ssh の宛先 (`~/.ssh/config` の Host alias、その ProxyCommand が
`winvm resolve-ip` を呼ぶ / または直接 `user@ip`) であり、IP 解決は ssh の通常の alias 解決に委ねる。
よって `winvm` 自身は run/health で resolve-ip を再実行せず、ssh の経路に一本化する。

## データフロー (run の場合)

1. 呼び出し側 (xtask) が env/引数で VM 固有値 + remote コマンドを渡す
2. `winvm run` が `ssh <host> "git -C <repo> rev-parse HEAD"` で VM の現コミットを取得 → diff base
3. ローカル git で `diff base..HEAD` + working tree + untracked のファイル一覧を算出 (純粋ロジック)
4. VM を pristine に reset (`git checkout -- . && git clean -fd`) し前回残骸を除去
5. 親ディレクトリ作成 → 各ファイルを scp → `ssh <host> "cd <repo> && <cmd>"`
6. `--skip-when-no-changes` 時、同期対象 0 なら check 実行せず成功で抜ける

## エラー処理

- `resolve-ip`: 一致 lease 無し = 非ゼロ終了 (ProxyCommand が明確に失敗)。SKILL.md に
  "Host is down" = ARP 不能 = stale lease の兆候、を明記
- `recover`: `vmware-vmx` 稼働検出で中止。既定 backup 移動で可逆、`--dry-run` で事前確認
- `run` / `health`: ssh/scp 失敗を明示エラー。PowerShell は **scp + `-File`** で渡す
  (cmd の 8191 字制限で長い `-EncodedCommand` が壊れるため) + ASCII ラベル +
  `[Console]::OutputEncoding=UTF8` (cp932 文字化け回避)。これらは今セッションで得た知見の仕様化
- xtask ラッパー: `winvm` が PATH に無ければ導入手順を案内して失敗

## テスト (仕様書としてのテスト)

`test_winvm.py` で純粋ロジックを exact assertion + negative case で固定。`uv run python -m pytest`
(または stdlib unittest) で skill 単体で緑にできる。

- `.vmx` からの MAC 抽出: generated / static / 複数 NIC / 欠落
- lease パース: 同一 MAC の最新ブロック選択 / 無一致で None
- `files_to_sync`: dedup / 空行除去 / 安定ソート
- `to_windows_path`: スラッシュ→バックスラッシュ
- `resolve_diff_base`: vm_head 既知ならそれ / 未知なら fallback
- `mkdir_command`: 親ディレクトリ dedup 連結 / 直下のみなら None

(既存の winvm_check.rs の Rust spec テストを移植 + MAC/lease パースを追加)

## relay 側の移行

1. `winvm_check.rs` を「`winvm run`/`winvm health` を relay 設定で exec」する数行へ縮小。
   `winvm-check` = `run --skip-when-no-changes -- cargo xtask check-desktop`、
   `winvm-bundle` = `run -- cargo xtask build-desktop --verbose`。argv 構築が純粋なら小テストを残す
2. Rust 側の純粋ロジック spec テストは Python (`test_winvm.py`) へ移管。重複は残さない
3. `docs/Windows検証環境構築.md` は generic 部分を skill へ委譲、relay 固有 (host alias `relay-winvm`・
   repo パス `C:/Hidari/Develop/relay`・MAC source=`.vmx`) のみ残す
4. `~/.ssh/relay-winvm-ip.sh` を廃止し ssh config の ProxyCommand を `winvm resolve-ip` へ差し替え

## 受け入れ条件

- 別プロジェクトが `winvm.py` を一切変更せず、env/引数だけで resolve-ip/recover/health/run を実行できる
- `winvm resolve-ip` が `.vmx` 由来の MAC で正しい IP を返し、VM 作り直し後も手修正不要
- relay の `cargo xtask winvm-check` が従来通り動作し、ロジック重複が無い
- `test_winvm.py` が緑で、純粋ロジックの仕様を読んで理解できる
- relay リポに home パスのハードコードが無い
