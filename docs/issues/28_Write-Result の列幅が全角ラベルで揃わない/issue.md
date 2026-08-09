---
status: open
---

# fix: Write-Result の列幅が全角ラベルで揃わない

## 背景

`scripts/windows-vm/bootstrap.ps1` の `Write-Result` は導入結果を 1 行 1 項目で並べる。
ラベル欄を固定幅にして縦を揃える意図だが、揃うのは半角ラベルのときだけである。

relay 側の同型スクリプトでも実機出力でズレが出ているのを確認した。

## 現状

```powershell
# scripts/windows-vm/bootstrap.ps1:85
Write-Host ('{0} {1,-16}: {2}' -f $tag, $Label, $Detail)
```

.NET の複合書式指定子 `{1,-16}` は **文字数** でパディングする。端末上の表示幅では
ないので、全角文字を含むラベルは 1 文字あたり 2 セル占有して右へはみ出す。

relay 側の実機出力での実例 (同じ `{1,-18}` 形式)。

```
[SKIP] rustup            : C:\Users\sho\.cargo\bin\rustup.exe
[OK  ] rust host         : aarch64-pc-windows-msvc
[OK  ] ビルド検証             : rustc がリンクまで通る      <- ここだけコロンが右へずれる
```

半角ラベルが並ぶ中に全角ラベルが混ざると、その行だけ崩れて読みにくい。

## タスク

- [ ] 表示幅 (East Asian Width) を数えてパディングする補助関数を作る
- [ ] `Write-Result` をその関数経由にする
- [ ] 半角のみ / 全角のみ / 混在の 3 ケースで桁が揃うことを Pester で pin する
- [ ] パディング計算を文字数ベースへ戻す変異でテストが赤くなることを確認する
- [ ] 直したら relay の `crates/xtask/assets/winvm-provision.ps1` にも同じ `Write-Result`
      があるので、そちらへも反映する (別 PR)

## 関連

- `scripts/windows-vm/bootstrap.ps1` — `Write-Result` の定義
- relay `crates/xtask/assets/winvm-provision.ps1` — 同型の `Write-Result` (`{1,-18}`)。
  こちらの実機出力でズレを実測した
- 代替案として、ラベルを半角に統一する手もある。ただし読みやすさを落とすので、
  表示幅で揃える方を先に検討する
