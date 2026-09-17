---
status: open
---

# feat: apm の pin が上流の最新から遅れたことを告げる

## 背景

ISSUE-97 のタスクと実例を切り出し、ISSUE-53 を待たずに進める (2026-09-17、ユーザーの裁定)。
担当の範囲は、ISSUE-53 が持つ横断スイープの報告項目の 1 つにあたる。

### 実例 (2026-09-17)

`home/apm.yml` の agentic-coding-tools の pin は v0.7.0 のままで、上流は 2026-09-16 に v0.8.0 を
出していた。v0.7.0 から v0.8.0 で変わった SKILL.md は 5 つあり、配布済みの 5 つはすべて v0.7.0 と
バイト単位で一致し、v0.8.0 とは一致しない。上流のセッションからの連絡で気づいた。

### 今ある経路と、足りなかった理由

- 上流の release 手順は、release を切ったら消費側 (dotfiles の `home/apm.yml`) の pin を揃えるよう
  促す段を持つ。今回気づけたのはこの経路で、release を切ったセッションが連絡を送るかに依存する
- README の「apm による skill 配信」節は「upstream 追従は `apm outdated` / `apm update` で確認・
  更新する」と書くが、誰も起動しない
- config-guard の `apm_pins` は、pin が上流の最新かを「覆わない」と docstring に明記している
- guard-health の登録済みプローブ (`guard_probes.PROBES`) にも鮮度を見るものは無い。`apm` の
  プローブが見るのは apm ガードの shim の位置である
- 追跡下で `apm outdated` を呼ぶ配線は無い

上流 ISSUE-32 の設計表は、層 0 に「消費側 pin の鮮度」を置き、担当を両リポジトリとしている。
一方で spec は、層 3 (横断スイープ) の報告項目にも「pin と上流 main の距離」を置いている。

### 切り出した理由

ISSUE-53 は、配布先の母数の定義から始まる。この Issue が見るのは dotfiles の manifest なので、
母数の問いを要しない。

### 前例

- `mise-update-check.yml` は、exact pin したツールの更新を週次で調べ、単一の GitHub Issue を
  更新し続ける。報告するかは互換範囲の更新だけで決め、メジャー越えは単独では黙る。常時開いた
  通知はやがて見られなくなるため (`scripts/mise-update-notifier/README.md`)
- 同じ README は、exact pin こそが素の `mise outdated` を無力化すると記録している。SHA で pin した
  apm の manifest でも同じことが起きうる
- `scripts/node-security-notifier` は、LaunchAgent で日次に起動して macOS へ通知する、ローカルの
  定期経路である

## 決めること

- **対象の範囲。**manifest は agentic-coding-tools のほかに、第三者の上流 (mizchi/skills と
  yusukebe/ax) も SHA で pin している。mizchi/skills は別製品の接頭辞付き tag しか持たないので、
  tag の差では距離を表せない
- **基準点。**上流 main か、最新の release か。spec の報告項目は main との距離で、release を
  切った直後以外は両者が分かれる。決めた方へ、ISSUE-53 の記述も揃える
- **鳴る条件と黙る条件。**agentic-coding-tools の release は 0.x で、毎回 minor が上がる。前例の
  互換範囲の規則をそのまま写すと、v0.7.0 から v0.8.0 は単独では黙る。release ごとに鳴らすと、
  pin を上げるまで通知が開く。前例も更新を取り込めば閉じるので、常時開くのは pin を意図して
  上げない場合に限る。黙らせる軸は、前例と同じく閉じる条件が成り立つかで選ぶ
- **pin の版の読み方。**pin の行末の tag 注記は手書きで、上流 ISSUE-36 は同じ形の注記が実体と
  食い違っていた記録を持つ。版は SHA から導出し、注記を判定に使わない形にするか。注記を
  残すなら、SHA との食い違いの検出もこの Issue が持つ
- **告げる経路と、上流との分担。**
  - 上流の release 手順に役割を持たせるか、dotfiles 側の pull だけで持つか。pull だけで持つなら、
    上流 ISSUE-32 の層 0 のこの行を引き取ったことを上流へ伝えるかも決める
  - pull の候補は、週次の CI、LaunchAgent、SessionStart のプローブ
  - 週次の CI なら、前例の Issue 更新の step を 2 本目の workflow へ写さず、共有する形を決める
  - SessionStart なら、ISSUE-83 と ISSUE-71 が先に効く。上流への問い合わせが要るので、待ち時間の
    上限と、オフラインを「見ていない」として出す形も決める
  - ここで決めた経路を、ISSUE-97 の写しの告知も使えるか
- **添える中身。**中身を添えない警報は、中身を見ないまま更新を促す装置になる。上流の release
  手順は、release note に配布物の変更一覧と前回 tag からの commit range を必ず入れると定めている
  ので、pin の tag から最新 tag までの release note を引ける。自前で commit range と touched paths
  の要約を作るなら、ISSUE-53 の「由来 SHA が古い」の報告と共有し、先に作った側の形をもう一方が使う

## タスク

- [ ] SHA で pin した manifest に対して `apm outdated` が何を報告するかを確かめ、結果に合わせて
      README の「apm による skill 配信」節を直す
- [ ] 対象の範囲、基準点、鳴る条件と黙る条件を決める
- [ ] 告げる経路と上流との分担を決める
- [ ] 実装し、鳴る側と鳴らない側の対照で確かめる。上流はどちらも v0.8.0 に固定する。鳴る側は
      pin を c80627f の `home/apm.yml` のまま、鳴らない側は pin を v0.8.0 が指す commit
      (ac85917。tag オブジェクトの SHA ではない) にした組で再現する。第三者の上流は、決めた
      範囲に合わせて除くか固定する

## 関連

- ISSUE-97: 開発環境のベースを配る構想。この Issue のタスクと実例の出所
- ISSUE-53: 横断スイープ (層 3) の担当。報告項目のうち pin と上流 main の距離はこの Issue が持つ
- ISSUE-83 と ISSUE-71: SessionStart で告げる形を採るときの前提
- agentic-coding-tools の ISSUE-32: 層 0 と層 3 の両方に pin の鮮度を置いている
- agentic-coding-tools の ISSUE-36: 型 6 (配布層自体) の 1 回目の実例を持つ
