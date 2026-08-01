---
status: open
---

# Windows 検証の基盤を VMware Fusion から Parallels へ移す

## 背景

`windows-vm-verification` skill (`home/.claude/skills/windows-vm-verification/`) は VMware Fusion を前提に書かれている。Windows 検証の基盤を Parallels Desktop へ移すため、VMware 固有の部分を置き換える必要がある。

`winvm.py` は 404 行 4 サブコマンドで、ハイパーバイザへの依存度が明確に分かれている。

| サブコマンド | VMware 依存 | 内容 |
| --- | --- | --- |
| `resolve-ip` | 全面 | `.vmx` 本文から NIC MAC を読み、`/var/db/vmware/vmnet-dhcpd-vmnet8.leases` を引いて IP を解決する |
| `recover` | 全面 | `pgrep -f vmware-vmx` で稼働確認し、stale な `*.lck` を除去して起動不能を解消する |
| `run` | なし | git 差分を scp 同期して remote コマンドを実行する。IP が解決できれば動く |
| `health` | なし | SSH 越しに VM の健全性を検査する。同上 |

依存は `resolve-ip` と `recover` の 2 つに集中しており、`run` と `health` は SSH ベースなのでハイパーバイザを問わない。ただし VM の指定方法が `WINVM_VMX` 環境変数で `.vmx` のパスを受け取る形なので、識別子の渡し方は全サブコマンドに影響する。

移行先の環境は準備済みである。Parallels Desktop 26.4.0 がインストールされ `prlctl` が `/usr/local/bin/prlctl` にあり、Windows もインストール済み。`/Library/Preferences/Parallels/parallels_dhcp_leases` も生成されている。

skill 本体だけでなく `SKILL.md` (150 行) と `references/troubleshooting.md` も VMware の手順を書いているので、あわせて更新が要る。テストは `test_winvm.py` (276 行)。

## 検討すべきこと

### VMware Fusion を捨てるか、両対応にするか

CLAUDE.md は「規模が小さいため後方互換性の破壊はためらわず、最も堅牢で合理的、シンプルなコードを書く」と規定しているので、Parallels 一本化が既定路線に見える。両対応にするとハイパーバイザの抽象層が要り、`resolve-ip` と `recover` が分岐を持つことになる。移行期間中に旧環境へ戻す必要があるか、VMware 側に残したい状態があるかを確認したうえで決める。

### `recover` に相当する失敗モードが Parallels にあるか

`recover` は VMware 固有の失敗モード、つまり stale disk lock によって「ディレクトリが空ではありません」となり VM が起動しなくなる事象への対処として作られた。Parallels は `.pvm` バンドルで lock の形が異なるため、同じ事象が起きるかどうかは未検証である。起きないなら移植する対象が無く、逆に Parallels 固有の復旧手順が別に必要になる可能性もある。実機で確かめてから決める。

### IP 解決の方式

`prlctl list -f` で IP が直接取れるなら、MAC の解析と leases のパースが両方とも不要になり `resolve-ip` は大幅に単純化する。取れない場合は `parallels_dhcp_leases` のパースになるが、VMware の leases とは形式が異なる。どちらになるかで実装量が変わるので、先に実機で確かめる。

## タスク

- [ ] Parallels 側の IP 解決方式を実機で確かめる (`prlctl list -f` で足りるか、leases のパースが要るか)
- [ ] `recover` に相当する失敗モードが Parallels に存在するか確かめ、移植・置換・削除のいずれかを決める
- [ ] VMware Fusion を捨てるか両対応にするかを決める
- [ ] VM 識別子の受け取り方を Parallels に合わせて再設計する (`WINVM_VMX` の扱い)
- [ ] `test_winvm.py` を新しい仕様に合わせて書き直す (仕様をテストで表現してから実装する)
- [ ] `winvm.py` を新しい仕様に合わせて実装する
- [ ] `SKILL.md` と `references/troubleshooting.md` を新しい手順に更新する
- [ ] full chain の live smoke を実機で 1 回通す (IP 解決 → scp 同期 → remote 実行 → health)

## 関連

skill の実体は dotfiles 管理下の `home/.claude/skills/windows-vm-verification/` にあり、`~/.claude/skills/` はそこへの symlink である。

skill 新設当時の設計と実装計画は `docs/superpowers/archive/2026-06-26-windows-vm-verification-skill-design.md` と同 `-skill.md` にある。Issue 起票の運用より前の成果物なので Issue ディレクトリ配下には無く、archive に退避されている。

最後のタスクに live smoke を置いたのは、shell-out と外部 CLI のオーケストレーションはユニットテストが緑でも完了としないという規約による。シェルやコマンドのセマンティクスがランタイムで壊れる類の失敗はユニットテストでは原理的に捕捉できない。
