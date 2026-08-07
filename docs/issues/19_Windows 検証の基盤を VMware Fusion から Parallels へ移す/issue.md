---
status: in_progress
---

# Windows 検証の基盤を VMware Fusion から Parallels へ移す

## 背景

`windows-vm-verification` skill は VMware Fusion を前提に書かれている。Windows 検証の基盤を Parallels Desktop へ移すため、VMware 固有の部分を置き換える必要がある。

`winvm.py` は 404 行 4 サブコマンドで、ハイパーバイザへの依存度が明確に分かれている。

| サブコマンド | VMware 依存 | 内容 |
| --- | --- | --- |
| `resolve-ip` | 全面 | `.vmx` 本文から NIC MAC を読み、`/var/db/vmware/vmnet-dhcpd-vmnet8.leases` を引いて IP を解決する |
| `recover` | 全面 | `pgrep -f vmware-vmx` で稼働確認し、stale な `*.lck` を除去して起動不能を解消する |
| `run` | なし | git 差分を scp 同期して remote コマンドを実行する。IP が解決できれば動く |
| `health` | なし | SSH 越しに VM の健全性を検査する。同上 |

依存は `resolve-ip` と `recover` の 2 つに集中しており、`run` と `health` は SSH ベースなのでハイパーバイザを問わない。ただし VM の指定方法が `WINVM_VMX` 環境変数で `.vmx` のパスを受け取る形なので、識別子の渡し方は全サブコマンドに影響する。

移行先の環境は準備済みである。Parallels Desktop 26.4.0 がインストールされ `prlctl` が `/usr/local/bin/prlctl` にあり、Windows もインストール済み。

skill 本体だけでなく `SKILL.md` (150 行) と `references/troubleshooting.md` も VMware の手順を書いているので、あわせて更新が要る。テストは `test_winvm.py` (276 行)。

## 決定 (実機で確かめた結果)

検証環境は Parallels Desktop 26.4.0-57513 + `Staccato - Windows 11 ARM` (Windows 11 ARM, ビルド 10.0.26200.8875)。

### VMware Fusion は捨てる

両対応にすると `resolve-ip` と復旧系に分岐が要るだけで、戻す先の要件が無い。CLAUDE.md の「後方互換性の破壊はためらわず、最も堅牢で合理的、シンプルなコードを書く」に従い Parallels 一本化とした。

### IP 解決は `prlctl list -a -f -j` の JSON で足りる

MAC の解析も leases のパースも要らなくなった。ただし `ip_configured` フィールドは形が 3 通りある。

| 状況 | 値 |
| --- | --- |
| 起動中 (`-o` 無し) | `10.211.55.3` |
| 停止中 (`-o` 無し) | `-` (空文字ではなくダッシュ) |
| `-o` 併用時 | `10.211.55.3  fdb2:2c26:f4e4:0:34a5:e9e2:a530:d5ff fe80::a22a:acc8:4abd:345c   ` (空白区切りの複数値、末尾に空白) |

ダッシュや空白をそのまま IP として下流に渡さないよう、IPv4 として妥当なトークンだけを採る実装にした。

`-f` を落とすと `ip_configured` フィールド自体が出ない。`-j` を落とすと表形式に戻る。両方必要。

Parallels は `/etc/hosts` に `<vm名を小文字化しハイフン化した名前>.shared` も書くが、これは Parallels がホストの `/etc/hosts` を維持していることに依存する。`prlctl` を真実源にする方が、VM 未登録 / 停止中 / IP 未割当を区別した診断を出せる。

### `recover` に相当する失敗モードは Parallels に無い。削除した

Fusion の失敗モードはバンドル内に残る `*.lck` **ディレクトリ**で、これが起動を阻んで「ディレクトリが空ではありません」になる。

Parallels の `.pvm` バンドルに対応するものは無い。バンドル直下にあるのは 0 バイトの `vm.lock` ファイル 1 つで、`lsof` でも保持プロセスが見えない。VM の生存を表すのは per-VM の `prl_vm_app --uuid {UUID}` プロセスである (Fusion 版のガードが `pgrep -f vmware-vmx` という全 VM 共通の判定だったのに対し、こちらは VM 単位で判定できる)。固まった VM を落とす手段は Parallels 自身が `prlctl stop <vm> --kill` として持っている。

観測していない失敗モードに対して未検証の除去コードを置くより、無い方が正しい。同等の復旧が要る場面では `prlctl stop <vm> --kill` を使う。

### 代わりに `doctor` を新設した

`recover` の枠には、実際に観測できる失敗モードを診断する `doctor` を置いた。VM の登録・状態・IP・Parallels Tools の状態とバージョン・ホスト隔離フラグ・`prlctl exec` の実行可否を、判定だけでなく**観測値付きで**並べる。`--host` を渡せば SSH 到達性も見る。

この移行で最も時間を取られた詰まり (後述の隔離フラグ) は、`doctor` 1 コマンドで出る。読めなかった項目は OK でも NG でもない第三の状態として表示し、「未確認」を「健全」に読み替えないようにした。

### VM 識別子は `WINVM_VM` / `--vm` で名前または UUID

`prlctl` が受け付ける識別子と同じ集合に揃えた。`winvm` と `prlctl` を混ぜて使っても指す VM がずれない。名前は完全一致で、部分一致はしない。UUID は大小と波括弧の有無を吸収する (`prlctl list -i` と `prl_vm_app` の argv は波括弧付きで出す)。

## 実機で踏んだ罠

### `prlctl exec` が通らない原因は隔離フラグ

`prlctl exec` が `Unable to open new session in this virtual machine. Make sure your virtual machine has finished booting, runs the latest version of Parallels Tools, and is not isolated from the host OS.` で失敗した。

エラーが挙げる 3 つの候補のうち、前 2 つは実測で否定できた (画面キャプチャでデスクトップまで起動済み、Parallels Tools 26.4.0-57513 は Parallels Desktop 本体と同一バージョン)。残る隔離が原因で、`config.pvs` に `<IsolatedVm>1</IsolatedVm>` があった。

`prlctl list -i` の人間向け出力に隔離の行は無く、`config.pvs` の XML にしか出ない。`Host-to-guest apps sharing: off` や `Guest Shared Folders: (-)` が一斉に off なのが手がかりになる (隔離は共有系をまとめて落とすスイッチ)。

解除は `prlctl set "<vm>" --isolate-vm off`。

### `prlctl exec` はコマンドをトークン分割して渡す

`prlctl exec "<vm>" "cmd.exe /c ver"` のようにプログラム名まで 1 文字列に含めると、**エラーも出さず exit 2 で無出力のまま失敗する**。`prlctl exec "<vm>" cmd.exe /c ver` と分割すれば通る。`cmd.exe /c "..."` のようにプログラム名と引数を別トークンにすれば、中身は 1 文字列でよい。

隔離を解除した直後にこれを踏み、「隔離が原因ではなかった」と誤読しかけた。

### sshd は動いているのに SSH が timeout する

OpenSSH Server の導入で作られるファイアウォール規則 `OpenSSH-Server-In-TCP` は **Private プロファイル限定**で入る。一方 Parallels の共有ネットワークは Windows から Public と判定される。

ネットワーク全体を Private に格下げすると探索や共有まで一括で緩むので、規則側だけを `-Profile Any` に広げ、送信元を Parallels のサブネット (`10.211.55.0/24`) に限定した。

### winget の台帳と実体が食い違う

`winget list` は PowerShell 7.6.4.0 を「インストール済み」と言うのに `C:\Program Files\PowerShell\7\pwsh.exe` が無い。実体は Microsoft Store (MSIX) 版で `C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.4.0_arm64__8wekyb3d8bbwe\` にある。

MSIX は app execution alias 経由で露出するが、SSH のような非対話セッションでは解決されないと考えて MSI を入れ直しかけた。実測すると alias 経由で問題なく起動できた (`pwsh -NoProfile -Command $PSVersionTable.PSVersion` が 7.6.4 を返す)。パスの有無で導入判定してはいけない。

### 検査そのものが壊れていて全件 MISSING に見えた

ツールチェーンの有無を cmd.exe の `for %C in (...) do @(where %C >nul 2>nul && ... || ...)` で調べたら全件 MISSING が返った。括弧内でリダイレクトの解釈が変わり `where` の stderr が漏れていたのが原因で、実際には大半が存在した。

`powershell` まで MISSING という**ありえない値**が出たのが気づきの手がかりだった。必ず見つかるはずの対照を検査に混ぜておくと、検査自体の故障を検出できる。

### BOM の無い `.ps1` は日本語環境でだけ壊れる

Windows PowerShell 5.1 は BOM の無い `.ps1` をシステムの ANSI コードページ (ja-JP では CP932) として読む。UTF-8 で書いた日本語コメントのバイト列が別の文字に化け、化けたバイトがアポストロフィを生んで文字列の終端を失う。

実測では BOM 無しで 695 トークン / パースエラー 7 件、BOM 付きで 1273 トークン / 0 件だった。**英語ロケールの Windows では再現しない。** 実行前に `[Management.Automation.Language.Parser]::ParseFile` へ通して初めて分かった。

pwsh(7) は BOM 無しでも UTF-8 として読むので、pwsh だけで確認すると見逃す。このスクリプトは pwsh 自身を導入対象に含むため 5.1 で動く必要があり、BOM は省略できない。

### PATH のレジストリ変更はセッションへ即座に伝わらない

rustup は `%USERPROFILE%\.cargo\bin` を User スコープの PATH へ足す。導入直後に張った SSH セッションではこれがまだ載っておらず、導入済みなのに `rustup` を解決できず再導入が走った。**再導入しても結果は同じなので、出力の状態表示を見ないと気づけない。**

後から張り直したセッションには載っていたので、SSH セッションに User PATH が載らないという構造的な欠落ではなく反映の遅れである (セッションの PATH に `.cargo` が含まれることを、必ずあるはずの `System32` を対照に置いて確認した)。

冪等性は 1 回目の実行では確かめられない。2 回目で初めて出た。

## タスク

- [x] Parallels 側の IP 解決方式を実機で確かめる (`prlctl list -f` で足りるか、leases のパースが要るか)
- [x] `recover` に相当する失敗モードが Parallels に存在するか確かめ、移植・置換・削除のいずれかを決める
- [x] VMware Fusion を捨てるか両対応にするかを決める
- [x] VM 識別子の受け取り方を Parallels に合わせて再設計する (`WINVM_VMX` の扱い)
- [x] `test_winvm.py` を新しい仕様に合わせて書き直す (仕様をテストで表現してから実装する)
- [x] `winvm.py` を新しい仕様に合わせて実装する
- [x] `SKILL.md` と `references/troubleshooting.md` を新しい手順に更新する
- [x] full chain の live smoke を実機で 1 回通す (IP 解決 → scp 同期 → remote 実行 → health)
- [x] `home/apm.yml` の pin を skill 更新後のコミットへ上げ、`apm install` で配布し直す
- [x] ゲスト側のツール導入を冪等なスクリプトにする (`scripts/windows-vm/bootstrap.ps1`)
- [ ] VMware Fusion の VM (87G) と VMware Fusion.app を削除する
      (VM バンドル 87G は削除済み。app と root 所有の残骸は sudo が要るため未了)

## 関連

skill の実体は PUBLIC リポジトリ `agentic-coding-tools` の `skills/devops/windows-vm-verification/` にある (Issue #25 Phase 2 で移設済み)。dotfiles へは apm 経由で配布され、`home/apm.yml` の pin が参照するコミットを決める。dotfiles 側で必要なのは pin の更新だけである。

skill 側の実装は `agentic-coding-tools` の main (`d039316`) に入っている。dotfiles 側の pin もこのコミットを指す。

ゲスト側のツール導入は dotfiles の `scripts/windows-vm/bootstrap.ps1` が持つ。skill ではなく dotfiles に置いたのは、skill が公開リポジトリの汎用 CLI であるのに対し、VM のプロビジョニングは個人の環境構築だからである。skill 側の `references/windows-bootstrap.md` は手順と理由を持ち、こちらはその自動化にあたる。

skill 新設当時の設計と実装計画は `docs/superpowers/archive/2026-06-26-windows-vm-verification-skill-design.md` と同 `-skill.md` にある。Issue 起票の運用より前の成果物なので Issue ディレクトリ配下には無く、archive に退避されている。

live smoke を最後のタスクに置いたのは、shell-out と外部 CLI のオーケストレーションはユニットテストが緑でも完了としないという規約による。シェルやコマンドのセマンティクスがランタイムで壊れる類の失敗はユニットテストでは原理的に捕捉できない。実際、この移行で見つかった罠のうち `prlctl exec` のトークン分割・ファイアウォールのプロファイル・進捗ログの順序入れ替わりの 3 つは live smoke でしか出なかった。
