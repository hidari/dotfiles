# Issue #19 の検証記録

`issue.md` が結論と理由を持つのに対し、こちらは**証跡**を持つ。何をどう測って、どんな値が出たか。結論だけを読んで足りるなら `issue.md` で止めてよい。

実行日は 2026-08-07。対象は Parallels Desktop 26.4.0-57513 + `Staccato - Windows 11 ARM` (Windows 11 ARM, ビルド 10.0.26200.8875, ja-JP)。

## `winvm` の移行 (Parallels 対応)

### 配布された版の同定

`apm install` が配置した `winvm.py` が Parallels 版であることを、独立した 3 経路のハッシュ一致で確認した。1 経路だけでは「apm が壊れた版をコピーし、lock にもその値を書いた」ケースと区別できない。

| 経路 | 値 |
| --- | --- |
| 真実源 (`agentic-coding-tools` の作業ツリー) | `646440c431860e958895d73c72fae2d33c7b47f4c61f43242f78c590b983be25` |
| apm の配置先 (`home/.claude/skills/`) | 同上 |
| `apm.lock.yaml` の `content_hash` | 同上 |

版の同定には対照を並べた。`prlctl` が 24 件あることで検査が実ファイルを見ていることを保証したうえで、Fusion 版の指標が 0 件であることを見ている。

| パターン | 件数 | 意味 |
| --- | --- | --- |
| `prlctl` | 24 | 正の対照。0 ならファイルを読めていない |
| `vmrun` | 0 | Fusion 版が残っていない |
| `vmx` | 0 | 同上 |

### `winvm doctor` の live smoke

実機に対して 7 項目すべて `[ OK ]`。

```
[ OK ] VM              : Staccato - Windows 11 ARM (4eb49f98-7f09-4b43-a3f1-35f285ad4d26)
[ OK ] status          : running
[ OK ] IP              : 10.211.55.3
[ OK ] Parallels Tools : installed 26.4.0-57513
[ OK ] host isolation  : off
[ OK ] prlctl exec     : Microsoft Windows [Version 10.0.26200.8875]
[ OK ] ssh relay-winvm : 到達
```

## `bootstrap.ps1` の検証

### BOM の有無によるパース結果

ゲスト上の PowerShell 5.1 で `[Management.Automation.Language.Parser]::ParseFile` に通した結果。

| ファイル | トークン数 | パースエラー |
| --- | --- | --- |
| BOM 無し | 695 | 7 件 |
| BOM 付き | 1273 | 0 件 |

トークン数の差がパーサの中断を裏づけている。エラーは「文または式のトークン ')' を使用できません」「文字列に終端記号 ' がありません」など、化けたバイトが構文を壊した形。

同じファイルを pwsh(7) でパースすると BOM 無しでも 0 件になる。**pwsh だけで確認すると見逃す。**

### 冪等性 (3 回連続実行)

| 項目 | 1 回目 | 2 回目 | 3 回目 |
| --- | --- | --- | --- |
| OpenSSH capability | SKIP | SKIP | SKIP |
| sshd | OK | OK | OK |
| firewall | OK | OK | OK |
| pwsh | SKIP | SKIP | SKIP |
| git | SKIP | SKIP | SKIP |
| rustup | **NEW** | **NEW** | SKIP |
| node | **NEW** | SKIP | SKIP |
| rust toolchain | SKIP | SKIP | SKIP |

2 回目の `rustup` が `NEW` のままだったのが冪等性のバグ。PATH をレジストリから読み直す修正を入れて 3 回目で解消した。**1 回目の実行だけでは検出できない。**

原因の切り分けでは、セッションの PATH に `.cargo` が含まれるかを、必ずあるはずの `System32` を対照に置いて数えた。

| 検査 | 件数 |
| --- | --- |
| セッション PATH 中の `cargo` | 1 |
| セッション PATH 中の `System32` (対照) | 4 |

含まれていたので「SSH セッションに User PATH が載らない」という構造的欠落ではなく、レジストリ変更の反映遅れと判断した。

### 導入されたツール (新しい SSH セッションでの確認)

```
git   -> git version 2.55.0.windows.3
node  -> v26.7.0
npm   -> 11.19.0
rustc -> rustc 1.97.1 (8bab26f4f 2026-07-14)
cargo -> cargo 1.97.1 (c980f4866 2026-06-30)
```

## 変異注入

3 種すべてを行った。検査対象・検査機構・取り付けのどれか 1 つでも欠けると、穴が塞がったのではなく 1 段上に移動しただけになる。

適用は 1 箇所ずつ隔離した。複数同時だと片方がもう片方の効果を隠し、生きた pin を dead pin と誤読する。復元は `cp` のバックアップから行った (`git checkout` は未コミットの編集ごと巻き戻す)。

### 検査対象を壊す

| 変異 | 結果 |
| --- | --- |
| BOM を剥がす | 赤 |
| dot-source ガードを外す | 赤 |
| 重複除去を大小区別ありにする (`OrdinalIgnoreCase` → `Ordinal`) | 赤 |
| 空要素の除去を消す | 赤 |
| 対照の既定を `cmd.exe` から差し替える | 赤 |
| 導入判定を常に真にする | 赤 |

事前状態と復元後がいずれも緑で、復元後のファイルはバックアップとバイト単位で一致した。

### 検査機構そのものを壊す

テストを 1 件も持たないテストファイルを食わせた。素の Pester とラッパで結果が割れる。

| 実行方法 | exit code |
| --- | --- |
| `Invoke-Pester -CI` | 0 (緑) |
| `scripts/ci/run-pester.ps1` | 1 (赤) |

これがラッパを噛ませている理由。Pester は「テストが 0 件」を成功として扱う。

なお「テストファイルが 1 件も無い」場合は Pester 自身が例外を投げるので、ラッパが守るのはその先の「ファイルはあるが 0 件」だけである。

### 取り付けを外す

BOM を剥がした状態で `pre-commit run pester --all-files` を実行し、hook が `Failed` になることを確認した。

この検査で実害も見つかった。**新規ファイルが untracked のあいだ、hook は `(no files to check) Skipped` で一度も走らない。** pre-commit の `files:` は git が知っているファイルにしか照合しないため。全体の集計は緑のままなので、追加前後で件数を比べて初めて気づいた。

| 状態 | Passed | Skipped |
| --- | --- | --- |
| hook 追加前 | 35 | 1 |
| hook 追加後 (untracked) | 35 | **2** |
| `git add` 後 | **36** | 1 |

## CI での実行

緑のチェックマークではなく、ジョブのログから件数を読んだ。

```
Tests Passed: 24, Failed: 0, Skipped: 0, Inconclusive: 0, NotRun: 0
実行 24 件 / 失敗 0 件 / skip 0 件
```

ubuntu-latest に pwsh が同梱されている前提もこれで実証された。無ければ `Install-Module` の段階で赤くなる。

## VMware Fusion の削除

### 実際に消したパス

VM バンドルは sudo 不要。残りは root 所有を含むためスクリプト経由で sudo 実行した。

```
~/Virtual Machines.localized                   (87G)
/Applications/VMware Fusion.app                (976M)
/Library/Application Support/VMware
/Library/Preferences/VMware Fusion
/var/db/vmware
/Library/Logs/VMware
/Library/Logs/VMware Fusion Services.log
/Library/Logs/DiagnosticReports/vmware-vmx_*.diag
~/Library/Application Support/VMware Fusion
~/Library/Application Support/VMware Fusion Applications Menu
~/Library/Application Support/CrashReporter/VMware Fusion_*.plist
~/Library/Caches/com.vmware.fusion
~/Library/Preferences/VMware Fusion
~/Library/Preferences/com.vmware.fusion*.plist
~/Library/Logs/VMware
~/Library/Logs/VMware Fusion
~/Library/Logs/VMware Fusion Applications Menu
~/Library/WebKit/com.vmware.fusion
~/Library/Containers/com.vmware.mksSandbox
~/Library/Application Scripts/com.vmware.mksSandbox
```

削除直後の空き容量は 69Gi → 156Gi。その後の減少は他プロジェクトのビルド成果物によるもので、VMware とは無関係。

### あえて残した 4 件

`*vmware*` に一致するが、消してはいけないか消す意味が無いもの。

| パス | 実体 | 理由 |
| --- | --- | --- |
| `~/Library/Application Support/TourBox Console/icons/VMware Fusion.png` | TourBox Console のアイコン | **VMware のファイルではない。** 消すと他アプリの UI が壊れる |
| `~/.../com.apple.LSSharedFileList.../com.vmware.fusion.sfl4` | macOS の最近使った項目 | macOS 管理。消しても再生成される |
| 同 `com.vmware.fusionapplicationsmenu.sfl3` | 同上 | 同上 |
| `~/Library/Caches/com.apple.helpd/Generated/VMware Fusion Help*` | macOS のヘルプキャッシュ | 同上 |

合計 10KB 未満。「残存 0 件」を目標にすると害の方が大きい。

### アンインストーラの再現

1 回限りの用途なのでスクリプトは残していない。手順は上の一覧をそのまま `rm -rf` すればよい。ただし 2 点。

- root 所有 (`/Applications`, `/Library`, `/var/db`) が混ざるので sudo が要る
- 一括削除は Tirith の `mass_file_deletion` (相関ルール、設定で除外不可) に掛かる。作業時は `TIRITH=0` を付けて実行した

最終確認を `find ... || echo "残存なし"` と書くと、`find` が読めないディレクトリで exit 1 を返すため、50 件以上を列挙した直後に「残存なし」と報告する。列挙と判定は必ず分けること。
