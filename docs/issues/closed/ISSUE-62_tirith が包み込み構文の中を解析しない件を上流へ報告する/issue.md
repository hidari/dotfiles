---
status: closed
---

# docs: tirith が包み込み構文の中を解析しない件を上流へ報告する

## 背景

tirith 0.3.3 は区切り (改行 / `;` / パイプ) を正しく展開するが、包み込み (`` ` ``  / `$( )` /
`bash -c` / `sh -c` / `eval`) の中を見ない。包んだだけで block が allow になる。

ISSUE-56 で実測済み (対照 5 件つきの表を同 Issue が持つ)。この Issue はその結果を上流へ
報告する作業を担当する。dotfiles 側の手当ては ISSUE-56 で完了しており、根本原因は tirith
側にあるので、こちらで塞ぐ設計は採らないと判断済みである。

効いているのはラッパー名ではなくクォートである。`nohup` / `timeout` / `ssh host '...'` /
`xargs -I{} bash -c '...'` / `python3 -c` も同様に素通りする。列挙で塞ぐ形が成立しない
ことの根拠になるので、報告に含める価値がある。

CRITICAL の finding が包むと MEDIUM へ退化して warn になる点まで含めて報告する。severity が
下がるので、閾値で運用している利用者は「軽い指摘」として通してしまう。

## 報告先を決める必要がある

tirith のドキュメントは tirith.dev ではなく tirith.sh にある (メモリに記録済み)。報告の
受け口 (GitHub Issues か、別の窓口か) を確認してから書く。

セキュリティ検査ツールのバイパス報告にあたるので、公開 Issue で出すか非公開の窓口を使うかを
先に判断する。公開して困る種類ではない (シェルのパーサが `bash -c` を追わないという、
実装を見れば分かる範囲の話) が、受け口の作法に従う。

## タスク

- [ ] 報告先と作法を確認する (公開 Issue か非公開の窓口か)
- [ ] 報告に載せる最小の再現手順を作る。ISSUE-56 の表は dotfiles のフック経由なので、
      tirith 単体で再現する形に直す
- [ ] 報告時点の tirith のバージョンを確認する。0.3.3 で測ったが、報告までに上流が
      進んでいれば測り直す (pin は mise の config.toml が持つ)
- [ ] 報告する。severity の退化 (CRITICAL が MEDIUM の warn になる) を含める
- [ ] 上流の反応を ISSUE-56 か本 Issue へ書き戻す。修正が入ったら dotfiles 側の
      「包み込みは 2 層を同時にすり抜ける」という前提が変わる

## クローズの記録 (2026-10-02)

報告する対象が消えたので、報告せずに閉じる。タスクの1〜4は実施していない。

tirith 0.4.1 をフックと同じ argv (`check --json --non-interactive --shell posix`) で呼んで測った。`curl … | sh` を `bash -c` / `sh -c` / `eval` / `nohup` / `timeout` / `$( )` で包むと、包まない形と同じ `curl_pipe_shell:HIGH` で block された。バッククォートと `xargs -I{} bash -c` の形は `analysis_incomplete:HIGH` で block された。無害なコマンドを `bash -c` で包んだ対照は allow だったので、包み込みそのものではなく中身で判定している。

タスク5の書き戻しは同じ PR で行った。`tirith-check.py` の docstring にあった「包み込みの中身は tirith が解析しないため素通りする」を直した。「allow は出さない」という方針は、`analysis_incomplete` を返す形が残るので変えていない。

確かめていないことが2つある。CRITICAL の finding が包み込みで MEDIUM へ退化するかは測っていない (相関ルールの時間窓を汚すため)。`ssh host '...'` の形も測っていない。

タスク3の「pin は mise の config.toml が持つ」は古い。tirith は Homebrew へ移っている。

## 関連

- ISSUE-56: tirith の fail-open。実測表と、フック側で前処理しないという判断を持つ。
  この Issue の一次資料
- ISSUE-59: 検査層が沈黙している状態をセッション頭で検出する。tirith 不在の検出を扱う。
  こちらは tirith が居るが射程が狭い場合なので別
- Issue 26: Claude Code フックの共通基盤を集約する
