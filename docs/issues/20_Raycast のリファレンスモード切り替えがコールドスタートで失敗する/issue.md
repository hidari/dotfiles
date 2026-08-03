---
status: open
---

# Raycast のリファレンスモード切り替えがコールドスタートで失敗する

## 背景

`home/.config/raycast/scripts/toggle-reference-mode.sh` は内蔵 XDR ディスプレイのプリセットを
2 値でトグルする Raycast Script Command だが、System Settings が起動していない状態から実行すると
必ず失敗する。

### root cause

スクリプトは System Settings を activate してディスプレイペインを reveal した直後、
固定の `delay 1.0` だけ待って UI ツリーの走査に入る。コールドスタートではこの時点でペインが
まだ描画されておらず、`findPresetPopup` の再帰走査が空のツリーを歩いて `missing value` を返し、
`error "プリセットのコントロールが見つかりませんでした"` が発火する。

実測 (macOS 26.5.2 / M3 Pro / Built-in Liquid Retina XDR Display):

| 条件 | 結果 |
| --- | --- |
| System Settings が既に開いている | 成功。プリセットが実際に切り替わる |
| System Settings が閉じている | `execution error: プリセットのコントロールが見つかりませんでした (-2700)` / exit 1 |

`delay 2.0` へ伸ばしても、quit 直後の再起動では `popups found: 0` かつ window 名が空になる
ケースを観測した。固定 delay では原理的に保証できない。

### 症状が root cause を隠す 2 つの経路

- `error` で異常終了するため、末尾の `tell application "System Settings" to quit` に到達しない。
  結果 System Settings が開きっぱなしで残り、「開くが何も起きない」という見え方になる
  (`pgrep -x "System Settings"` で残存を確認済み)
- Raycast のメタデータが `@raycast.mode silent` なので、エラー HUD が一瞬しか表示されない

### プリセットの選択

現行の編集用プリセットは `HDTV Video (BT.709-BT.1886)` だが、これは放送向けの Rec.709。
用途は Capture One での写真編集で、P3 系で編集し sRGB で最終確認するワークフローを想定するため、
編集用は `Photography (P3-D65)` が適切。sRGB での確認は Capture One のソフトプルーフに任せ、
本 Issue のスコープでは 2 値トグルを維持する。

## タスク

- [ ] UI 描画の待機を固定 delay から条件ベースのポーリング (タイムアウト付き) へ置き換える
- [ ] メニュー展開の待機も同じく条件ベースにする
- [ ] 失敗時に System Settings を閉じてから終了する
- [ ] プリセットが実際に適用されたことを確認してから終了する
- [ ] 編集用プリセットを `Photography (P3-D65)` へ変更する
- [ ] トグルの遷移規則を純粋な bash 関数へ切り出し、bats でテストする
- [ ] Raycast の `@raycast.mode` を見直し、失敗が利用者に届く形にする
- [ ] コールドスタートとウォームスタートの双方で live smoke を実行し、往復を確認する

## 関連

未追跡だったスクリプトを本 Issue の対応で追跡下へ入れる。配線自体は既に
`bootstrap.sh:36` の `home/.config/raycast/scripts|.config/raycast/scripts` で symlink 済みで、
live とリポジトリのファイルは inode が同一であることを確認済み。

sRGB での最終確認を物理的に再現したくなった場合は、`Internet & Web (sRGB)` へ直行する
スクリプトを別途足す余地を残す。本 Issue で AppleScript 側を「指定したプリセットへ切り替える」
形に整えておけば、薄いラッパーで追加できる。

ディスプレイ設定の App Intents (`DisplaysSettingsIntentsExtension.appex`) が公開しているのは
AutoBrightness / AutomaticReconnect / MagicEdge / ShareKeyboard / TrueTone の 5 つのみで、
プリセット切り替えの Intent は存在しない。したがって Shortcuts 経由の代替経路は取れず、
System Events による UI 操作が唯一の手段である。
