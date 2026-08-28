---
status: open
---

# fix(hooks): tirith の fail-open へ tirith 自身の無効化で到達できる

## 背景

`home/.claude/hooks/tirith-check.py` は Bash ツールに対する唯一の実質的なコマンド検査で、
`home/.claude/settings.json` の PreToolUse に配線されている。

このフックには意図的な fail-open が 1 箇所ある。バイナリがどこにも見つからず、かつ
`TIRITH_BIN` も指定されていない場合、stderr に 1 行出して exit 0 する。理由もコードに
書かれており、user スコープで全プロジェクトに効くため tirith 未インストールの環境で
シェルが全死にしないようにするためである。この判断自体は妥当で、本 Issue は覆さない。

問題は、その状態へ到達する手段を tirith 自身が止めないことにある。

### 実測

フックの倒れ方は `TIRITH_BIN` の有無で分岐する。両方を測った。

| 条件 | フックの判定 |
| --- | --- |
| 実バイナリ + 検査対象のコマンド (対照) | deny |
| 実バイナリ + 無害なコマンド (対照) | 素通り (偽陽性なし) |
| `TIRITH_BIN` を存在しないパスへ設定 | deny (設定ミス扱いで fail-closed) |
| `TIRITH_BIN` 未設定 + shim あり + 実体なし | deny |
| `TIRITH_BIN` 未設定 + shim もなし | 素通り (意図的な fail-open) |

`TIRITH_BIN` を明示した場合に fail-closed へ倒れるのはコードのコメントどおりで、
設定ミスとインフラ未整備を区別する設計になっている。

到達には 2 段階が要る。実体を消しただけでは mise の shim が残り、shim が非 0 で終わるため
「非 0 かつ stdout なし」の経路で fail-closed になる。shim まで消して初めて fail-open へ落ちる。

そして tirith 自身は、その 2 段階のどちらも止めない。tirith へ直接検査させた結果 (実行はせず
判定のみ):

| コマンドの形 | tirith の action |
| --- | --- |
| 既知の検査対象コマンド (対照) | block |
| 実体を `rm -f` する形 | allow |
| インストールディレクトリごと `rm -rf` する形 | allow |
| 実体を `mv` で退避する形 | allow |
| 実体から実行権限を落とす形 | allow |

つまり「2 回の許可されるコマンドで検査を沈黙させられる」連鎖が成立する。

ただし起票時の「以降のすべての Bash が素通りする」は過大評価である。fail-open は stdout を
出さない exit 0 であり、これは「判定なし」として通常の permission フローへ落ちる。自動承認では
ないので deny / ask ルールも manual モードのプロンプトも残る。消えるのは tirith の検査だけである。

問題は残る。無効化が exit 0 の素通りとして返り、ユーザーへの唯一の信号が stderr 1 行になる。
しかもこの経路はテレメトリにも残せない。記録の呼び出しは tirith 自身を起動するので、
tirith が不在という当の状態では必ず失敗して握り潰される。通知手段は stderr と
additionalContext と外部の静的検査の 3 つに限られる。

### 委譲先の実効カバレッジ: 包み込み構文の中を見ない

フックは受け取ったコマンド文字列をそのまま tirith へ渡し、判定を tirith に委ねる。したがって
この層が実際に何を止めるかは tirith のパーサの射程で決まる。実 tirith へ直接検査させた結果
(実行はせず判定のみ、対照 5 件つき):

| 形 | tirith の action |
| --- | --- |
| 破壊的コマンドをそのまま (対照) | block |
| 無害なコマンド (対照) | allow |
| 改行で区切って隠す (対照) | block |
| `;` で区切って隠す (対照) | block |
| パイプでインタプリタへ渡す (対照) | block |
| バッククォートで包む | allow |
| `$( )` で包む | allow |
| `bash -c` で包む | allow |
| `sh -c` で包む | allow |
| `eval` で包む | allow |

区切りは正しく展開するが、包み込みの中は見ない。根本原因は tirith 側にありフックの
Python ではないが、この層の実効カバレッジを規定するので記録する。

重要なのは ISSUE-55 との組み合わせである。apm ガードは包み込みを 1 トークンにまとめるが
区切り (改行・CR) で位置判定が外れ、tirith は区切りを扱えるが包み込みを見ない。両者の穴は
相補的ではなく、包み込みの形は 2 層を同時にすり抜ける。多層防御が成立しているかの判断は
この重なりを見てから下す必要がある。

### 環境変数を無フィルタで委譲先へ渡す

フックは `os.environ.copy()` に `TIRITH_INTEGRATION` を足しただけの環境で tirith を起動する。
同じリポジトリの `handoff-sentinel` が git を呼ぶときはロケーション系の `GIT_*` を明示的に
落としており (所在のすり替え防止)、`apm-install-guard` も同様である。tirith 側だけが非対称に
何も落としていない。

起票時は「検査を弱める環境変数が実在するかは特定していない」としていたが、実在する。
バイナリの文字列から `TIRITH_POLICY_ROOT` (policy の所在)、`TIRITH_THREATDB_PATH` と
`TIRITH_THREATDB_SUPPLEMENTAL_PATH` (脅威 DB の所在)、`TIRITH_WARN_ACK_*` (warn の扱い)、
`TIRITH_OFFLINE` などを確認した。加えて `tirith policy effective` の既定が
`fail_mode: open` かつ `allow_bypass_env: true` である。

したがって設計の非対称ではなく実害の経路である。ただし届き方には限りがある。フックの
プロセス環境は Claude Code から継承され、プロジェクトの settings が持つ `env` は
folder trust の後に適用される。その前提が成立するならプロジェクト settings は hooks 自体を
定義できるので、この経路だけを塞いでも意味は薄い。実効があるのは「フックが受け取った環境を
そのまま子へ渡さない」ことの方で、そちらは接頭辞ごと落とせば上流が変数を増やしても漏れない。

フック自身が読む変数 (`TIRITH_BIN` / `TIRITH_FAIL_OPEN`) は子プロセスのフィルタでは
防げない。`os.environ` から直接読むためである。タスク欄はこの 2 種類を区別していなかった。

### 測定上の注意

tirith は相関ルールを持ち、直前のコマンド履歴を時間窓で見る。上記の検査を走らせた直後は
無関係なコマンドの判定まで変わるため、プローブ自身が後続の測定を汚染する。同じ観測を
繰り返すときは窓を抜けるまで待つこと。実際にこのレビュー中、`git push --force` が
最初は block、時間を空けると 8 回連続で allow になった。

### 同じフックにあるもう 1 つの非対称: warn 経路が明示 allow を出す

判定の出し方に、危険度と承認の強さが逆転している箇所がある。

| tirith の結果 | フックの出力 |
| --- | --- |
| clean (exit 0) | 何も出さずに終了 → 通常の permission 判定が働く |
| warn (exit 2) かつ `TIRITH_HOOK_WARN_ACTION` が既定 | `permissionDecision: allow` を明示出力 |
| block (exit 1) | deny |

起票時は「明示 allow が `ask` / `deny` を上書きする」と書いたが、これは誤りである。公式の
permissions リファレンスは「Hook decisions don't bypass permission rules」と明記しており、
フックが allow を返しても deny ルールはブロックし、ask ルールはプロンプトを出す。
`git push` の確認は飛ばない。

実害が消えたわけではなく、別の形に置き換わる。フックの allow が実際に飛ばすのは
allow / deny / ask のどれにも載らない全 Bash コマンドの承認プロンプトである。これは列挙では
なく補集合なので事実上無制限で、`git commit` / `rm` / `curl` / `apm install` などが該当する。

そして頻度も起票時の見積もりと違う。warn (exit 2) は 18 検体中 0 件ではなく、30 検体中
23 件で再現した。条件は「finding の最大 severity が MEDIUM」である。URL 系のヒューリスティクス
(raw IP、非標準ポート、短縮 URL、類似 TLD、非 ASCII パス、二重エンコード) がこの層に集まる。

さらに severity の退化が起きる。素のままなら CRITICAL を含んで block になるコマンドが、
包み込みの中へ入れると MEDIUM だけの warn へ落ちる。つまり「怪しさが高いものほど warn へ
落ちて素通りする」向きの誤りになる。

実行時の permission mode でも重みが変わる。default mode では allow は「プロンプトの省略」
だが、auto mode では classifier の判定そのものを飛ばす。

## タスク

- [x] fail-open へ落ちたことを stderr 1 行より強い形で知らせる。判定を持たない
      `hookSpecificOutput` で additionalContext だけを返す形にした。harness がこの形を
      受理し文脈が届くことは live で確認済み
- [x] warn (exit 2) の発火条件を特定する。finding の最大 severity が MEDIUM のとき
- [x] warn 経路が明示 allow を出すのをやめる。判定を出さず警告文だけを載せる。
      判定の強さを選ぶノブ (`TIRITH_HOOK_WARN_ACTION`) は廃止した
- [x] tirith へ渡す環境を絞る。`TIRITH_` 接頭辞を丸ごと落とし `TIRITH_INTEGRATION` だけ
      足し直す。フック自身が読む変数はこのフィルタの対象外である旨を docstring に書いた
- [x] 決めた方針を変異注入で pin する
- [x] fail-open 経路のテストを足す。起票時に「テストが無い」としたのは誤りで
      `test_binary_not_found_fails_open` が既にあった。通知を見るテストへ書き換えた
- [x] 包み込み構文の扱いを決める。フック側で前処理はしない。この層の射程を docstring へ
      1 箇所書き、残余は受容する
- [ ] 検査が沈黙している状態を検出する層を持つか決める
- [ ] tirith 自身の無効化に当たるコマンドをフック側の denylist で止めるか決める

### 判断: 包み込みをフック側で前処理しない

tirith のトークン化規則は非公開である。前処理が上流の期待と一致しているかをこちらで検証
できないため、緑が何を意味するか言えない。面も有界でない。上流へ報告し、この層の射程を
「トップレベルのトークンとして見える範囲まで」と docstring に書いて残余を受容する。

射程の実測: 区切り (改行 / セミコロン / パイプ) は展開するが、包み込み (バッククォート /
`$( )` / `bash -c` / `sh -c` / `eval`) の中は見ない。効いているのはラッパー名ではなく
クォートで、`nohup` / `timeout` / `ssh host '...'` / `xargs -I{} bash -c '...'` /
`python3 -c` も同じく素通りする。`--shell` の値では判定は変わらない。

### 判断: denylist は作らない

tirith 自身を無効化するコマンド (`rm` / `mv` / `chmod` 等) をフック側で止める案は採らない。
面が有界でなく、`bash -c 'rm ...'` の形は tirith 自身が見ないので同じ穴を相続する。
環境変数による弱化は denylist では原理的に捕まらない。予防ではなく検出へ寄せる。

### 残したタスク

「検査が沈黙している状態を検出する層」は ISSUE-55 で apm 側に同じ機構を入れたので、
形は決まっている。ただし tirith 側は config-guard に置けない (CI に tirith が無く、
skip 条件が検出対象と一致して自己敗北する)。SessionStart での behavioral canary が要り、
設計と実装の範囲が別 Issue の大きさになるので分ける。

## 検証

| 検査 | 結果 |
| --- | --- |
| `uv run --directory scripts/claude-hooks pytest -q` | 159 件緑 |
| `bats scripts/tests/` | 302 件緑 |
| `uv run --project scripts/config-guard config-guard .` | 問題なし |

### 変異注入

| 変異 | 種別 | 結果 |
| --- | --- | --- |
| warn で allow を明示するよう戻す | 検査機構 | kill |
| env フィルタを外して全環境を渡す | 検査機構 | kill |
| fail-open の通知を出さない | 検査対象 | kill |
| 判定を持たないはずの payload に allow を混ぜる | 検査機構 | kill |
| 落とす接頭辞を policy 系だけに絞る | 緩めすぎ | kill |

## 関連

- ISSUE-26 が PreToolUse フックの共通基盤を扱う。fail ポリシーは共有層に置かない判断が
  既に下りており (tirith は環境変数の逃げ道つき fail-closed、apm は無条件 deny)、
  本 Issue はその tirith 側のポリシーの話なので集約とは独立している
- ISSUE-55 が同じ PreToolUse 層の別の穴 (apm ガードの位置判定) を扱う。機序は別だが、
  どちらも失敗が deny ではなく素通りとして返る形である
