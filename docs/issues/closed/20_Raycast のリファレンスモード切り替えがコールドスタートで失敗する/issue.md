---
status: closed
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

- [x] UI 描画の待機を固定 delay から条件ベースのポーリング (タイムアウト付き) へ置き換える
- [x] メニュー展開の待機も同じく条件ベースにする
- [x] 失敗時に System Settings を閉じてから終了する
- [x] プリセットが実際に適用されたことを確認してから終了する
- [x] 編集用プリセットを `Photography (P3-D65)` へ変更する
- [x] トグルの遷移規則を純粋な bash 関数へ切り出し、bats でテストする
- [x] Raycast の `@raycast.mode` を見直し、失敗が利用者に届く形にする
- [x] 外部ディスプレイを外した状態で live smoke を再実行する
- [x] `reveal pane id` によるペイン遷移の完了を待つ方法を特定する
- [x] コールドスタートとウォームスタートの双方で live smoke を実行し、往復を確認する
- [x] Raycast から起動する経路で live smoke を実行する

## 調査記録 (2026-08-03)

### root cause は層状だった

背景に書いた「固定 delay が短い」は第 1 層でしかなく、条件ベースのポーリングへ
置き換えても live smoke は通らなかった。ポーリング中の状態を記録したところ、
System Settings が一度も前面に出ていないことが分かった。

```
round 1 front=Google Chrome proc=true windows=1 winName=[] popups=0
round 3 front=Nabla         proc=true windows=1 winName=[] popups=0
round 6 front=ghostty       proc=true windows=1 winName=[] popups=0
```

System Settings は SwiftUI 製で、前面に出るまでウィンドウの中身を描画しない。
一度描画されれば背面でも UI ツリーは残るため、ウォームスタートでは `activate` だけでも
動いてしまう。これがコールドスタートでだけ失敗していた理由 (第 2 層)。

### フォアグラウンド化の対照実験

同一条件 (コールドスタート) で 3 手段を比較した。

| 手段 | 結果 |
| --- | --- |
| `tell application ... to activate` 1 回のみ | 40 秒待って popup 0。frontmost は他アプリのまま |
| 同 activate を毎周回 | 25 秒待って popup 0。frontmost にはなるが window 名は空 |
| System Events の `set frontmost to true` | 1 周目 (0.6 秒) で popup 3、window 名は「ディスプレイ」 |

「フォアグラウンドになること」と「UI が描画されること」は別物だった。
2 番目の手段だけを見ていると「まだ待ち足りない」と誤読してタイムアウトを伸ばし続けることになる。

ただしこの対照はディスプレイ構成を固定しないまま取った。外部ディスプレイ接続下では
内蔵ディスプレイのプリセット popup が UI ツリーに現れない可能性があり、
この交絡を排除した再検証が要る。

### ネイティブ実装の可否

プリセット切り替えの公開 API は 3 方向とも存在しない。

- App Intents: `DisplaysSettingsIntentsExtension.appex` が公開するのは AutoBrightness /
  AutomaticReconnect / MagicEdge / ShareKeyboard / TrueTone の 5 つのみ
- Shortcuts: 上と同一なので同じく無い
- Framework: 設定ペイン `DisplaysExt.appex` がリンクするのは `CoreBrightness` /
  `DisplayServices` / `ProDisplayLibrary` (いずれも PrivateFrameworks) と
  `CoreDisplay` / `ColorSync`。プリセットを扱うのは private 側

`ProDisplayLibrary` は dyld shared cache に統合されており実ファイルが無いため、
シンボルの静的確認にも手間がかかる。ネイティブ化しても private API を dlopen する形になり、
壊れやすさが「UI 階層依存」から「API シグネチャ依存」へ移るだけでリスクは消えない。
実装コストだけが増えるため、ネイティブ化は採らない判断をした。

### UI 要素の識別手段

プリセット popup を識別できる安定した属性は存在しない。実測で 3 つの popup すべてが
`AXIdentifier` を持たず、`AXHelp` / `AXTitle` も `missing value` だった。
現在選択中の値をプリセット名リストと照合する方式が唯一の手段となる。

### 実装済みの内容

`fix/raycast-reference-mode-toggle` ブランチに wip コミット済み。

- 条件ベースのポーリング、System Events 経由の前面化、適用後の突き合わせ、失敗経路の後片付け
- トグルの遷移規則を bash 関数へ切り出し、bats 14 件で pin
- 5 箇所の変異注入 (空チェック / source ガード / 適用後の突き合わせ / close の呼び出し /
  トグル分岐の反転) で全 pin が生きていることを確認済み

bash 側のオーケストレーションは経路を差し替えても再利用できる形になっている。

## 調査記録 (2026-08-04)

### 外部ディスプレイの交絡は無かった

前回の記録が残した「外部ディスプレイ接続下では内蔵ディスプレイのプリセット popup が
UI ツリーに現れない可能性」は否定された。内蔵ディスプレイのみ
(Built-in Liquid Retina XDR Display / Connection Type: Internal) の状態で
コールドスタートを実行しても、20 秒のタイムアウトを使い切って popup 0 で失敗した。

### root cause の第 3 層: reveal は黙って捨てられる

失敗直後に UI ツリーをダンプすると、サイドバー・ツールバー・検索フィールドは
描画されているのに window 名が空で、右のコンテンツペインだけが空だった。
その状態で `reveal pane id` を送り直すと、0.5 秒後に window 名が「ディスプレイ」へ
変わり、深さ 6 にプリセット popup が現れた。

条件を揃えた対照 (コールドスタート、reveal をループ外で 1 回だけ送る修正前の実装):

| 観測 | 結果 |
| --- | --- |
| reveal のエラー | none (エラーを返さない) |
| 前面化 | 全周回で frontmost=true |
| 12 周 6 秒の観測 | window 名は空のまま popup 0 |
| reveal を再送した 0.5 秒後 | window 名「ディスプレイ」、popup 1 |

`reveal pane id` はコールドスタートでエラーを返さないまま無視される。`try` で囲っても
成否を判定できず、ペインが開かないまま UI 走査だけが空回りしていた。
前セッションで解決した前面化は第 2 層で、これはその下の第 3 層にあたる。

### 待ち時間の問題ではなかった

`activate` のブロック時間を 3 回測ると 0 / 0 / 1 秒で、いずれも直後の reveal は
捨てられた (3/3)。一方で別の試行では 1 周目の reveal が効いた。
「N 秒待てば効く」のではなく実行ごとに揺れるため、待ち時間を伸ばす方向では解決しない。

これが「`reveal pane id` によるペイン遷移の完了を待つ方法」への答えでもある。
完了を表す信号は存在せず、待つこともできない。到達したかどうかは window 名が
空でないことで判定し、届いていなければ送り直す。

### UI ツリー走査のコスト

再帰走査 1 回に実測 6 秒かかる (System Events の AX API は要素ごとに IPC が走る)。
ポーリング 1 周が 6.5 秒になるため、タイムアウト 20 秒では実質 3 周しか回れない。
ペインが選ばれるまで走査に入らない形へ変え、空の間は 0.5 秒周期で reveal を
送り直すようにした。所要時間は 20 秒から 15 秒へ短縮している。

### live smoke

内蔵ディスプレイのみ、ターミナルからの実行。

| 条件 | 結果 |
| --- | --- |
| 修正前 コールドスタート | 失敗 (20 秒タイムアウト、popup 0) |
| 修正後 コールドスタート 4 回 | すべて成功 (15 / 15 / 15 / 17 秒) |
| 修正後 ウォーム (別ペイン・前面) | 成功 (14 秒) |
| 修正後 ウォーム (別ペイン・背面) | 成功 (13 秒) |

往復 (編集用と普段用の交互切り替え) と、適用後に System Settings が閉じることも確認した。

Raycast から起動する経路も利用者が 2 回実行して往復を確認した。アクセシビリティ権限の
主体はアプリごとに異なるため、ターミナルで通ることは Raycast で通ることを保証しない。

### レビューで判明したこと

pre-merge quality gate (simplify 4 観点 / code-reviewer / boy scout sweep) を通し、
実装を次のとおり直した。詳細はコミット本文にある。

- プリセット名が bash 定数と AppleScript のリストへ二重に書かれており、片方だけ変えても
  bats が緑のまま通っていた。bash 側を canonical にして引数で渡す形へ変えた
- 埋め込み AppleScript をマーカーで切り出して検査する方式は、範囲が狭まったときに断片
  だけをコンパイルして緑のまま劣化する (先頭 33 行でも exit 0)。ヒアドキュメントを変数へ
  受け、テストは source するだけで本文を得る形にした
- 失敗経路の後片付けが 4 箇所にコピーされ、うち 3 箇所は削除してもテストが緑だった。
  本体を切り出して 1 箇所へ集約した

「非起動の System Settings へ quit を送るとアプリが起動してしまう」という指摘は、実測
(0.074 秒で完了、プロセスは残らない) で否定した。

### 走査方式の比較

UI ツリーの走査を幅優先へ変えた。方式ごとに独立プロセスで、順序を 4 通り変えて計測した。

| 方式 | 実測 |
| --- | --- |
| 深さ優先 + 要素ごとに role | 6 / 6 / 7 / 7 秒 |
| 深さ優先 + 1 階層まとめて role | 5 / 5 / 6 / 6 秒 |
| 幅優先 + 1 階層まとめて role | 4 / 4 / 4 / 4 秒 |

実ワークロードでの効果はフェーズで異なる。read は走査に入る時点で UI ツリーがまだ軽く
8.7 秒から 8.6 秒とほぼ変わらない。apply は描画済みのツリーを歩くので 8.3 秒から
6.8 秒へ短縮した。全体では 17 秒から 15.4 秒。

### 本 Issue から切り出した残課題

- Issue #22: 走査を 1 回に減らす (apply 側の走査 4 秒がまだ残っている)
- Issue #23: 外部ディスプレイ接続時にどのディスプレイを切り替えるか確認する

## 関連

未追跡だったスクリプトを本 Issue の対応で追跡下へ入れる。配線自体は既に
`bootstrap.sh:36` の `home/.config/raycast/scripts|.config/raycast/scripts` で symlink 済みで、
live とリポジトリのファイルは inode が同一であることを確認済み。

sRGB での最終確認を物理的に再現したくなった場合は、`Internet & Web (sRGB)` へ直行する
スクリプトを別途足す余地を残す。本 Issue で AppleScript 側を「指定したプリセットへ切り替える」
形に整えておけば、薄いラッパーで追加できる。
