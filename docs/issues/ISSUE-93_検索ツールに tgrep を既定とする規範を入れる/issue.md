---
status: in_progress
---

# agent: 検索ツールに tgrep を既定とする規範を入れる

## 背景

2026-09-12 にユーザーから「既存の Grep ツールや `grep` ではなく `tgrep` を積極的に使ってほしい」と
明示的に指示された。agentic-coding-tools 側はこれを project memory へ記録したが、memory は
プロジェクト単位でしか効かず他のリポジトリには届かない。全リポジトリへ効く canonical は
user CLAUDE.md なので、規範の起票と実装が dotfiles へ委譲された。

道具そのものの配線は PR #215 の副産物として済んでいる。`home/.Brewfile` が `tgrep` を宣言し、
索引キャッシュ `.tgrep/` の ignore は `home/.config/git/.gitignore_global` にある (このリポジトリ
限定のツールではないので repo 側ではなく global へ置いた)。足りないのは規範だけ。

規範が要るのは、速いからではなく **外し方が「もっともらしい 0 件」で返るから**にあたる。
tgrep は面が 3 つ (索引 / 検索 / 常駐) に分かれていて、どの面で外しても検索は rc 0 で
成功したように見える。速度のためだけなら道具を入れた時点で目的は足りている。

## 実測 (2026-09-13、このリポジトリの常駐サーバーに対して)

前セッションの観測を根拠にせず、3 つの面すべてを自分で再現した。probe と対照は
`.cache/probe-tgrep-surfaces.sh` と `.cache/probe-tgrep-hidden-blindspot.sh`。

### 面 1: 常駐索引は dot 始まりを含まない

| 値 | 実測 |
| --- | --- |
| 追跡ファイル総数 | 373 |
| dot 始まりのパスコンポーネントを持つもの | 85 |
| 差 (可視ファイル) | 288 |
| `tgrep status` の `Files:` | 288 |

可視ファイルの実数と索引のファイル数がちょうど一致する。dot 始まりの 85 件は索引の外にある。
このリポジトリは積荷がほぼ全部 dot 始まり (`home/.claude/` `home/.config/` `.github/`) なので
影響が大きい。

### 面 2: 同じ語を 2 経路で引くと結果が割れる

probe には「追跡下で 1 ファイルにしか無く、そのファイルが dot 始まり」を満たす語を選んだ
(`gitleaks_version` / `.github/workflows/test.yml`)。最初に選んだ語は dot 始まり以外にも
出現していて交絡したので、選び直している。

| 経路 | ヒット | stderr |
| --- | --- | --- |
| ディレクトリ走査 (常駐索引) | 0 | 0 行 |
| 明示パス (索引を迂回) | 1 | ― |
| 対照: 可視ファイルの語をディレクトリ走査 | 27 | ― |

対照が非 0 を返すので、0 件は「経路が壊れている」ではなく「索引が dot を持たない」を意味する。
**stderr は 0 行で、索引の外を見ていないことは出力に一切現れない。**

対照側も同じ穴を踏んでいる。`SYMLINK_PAIRS` は `git grep` で 32 ファイルなのにディレクトリ走査は
27 件しか返さない。差の 5 件が hidden 配下にある。

### 面 3: 検索時の `--hidden` は索引を捨てる

存在しない語で測る (ヒットが 0 で揃うので、差は走査量だけを反映する)。

| モード | 所要 |
| --- | --- |
| 索引経由 | 34 ms |
| `--hidden` 付き | 1381 ms |

約 40 倍。`--hidden` を足せば面 2 の probe は 1 件返るようになるが、それは索引が直ったのではなく
全走査へ落ちた結果にあたる。落ちたことも stderr には出ない (0 行)。

### 面 4: パイプの stdin を読まない

`printf '... LEAK_GUARD_DENYLIST ...' | tgrep LEAK_GUARD_DENYLIST` は stdin を無視して
カレントディレクトリを走査し、渡していないファイルの中身を 3 行返した。**もっともらしい別物が
返るので、パイプが効いていないことに気づけない。**

## 置き場所の判定

`home:context-loading-mechanics` の判定基準は「その規範が回避したい失敗の側で、一致するファイルの
Read が起きるか」。この規範が回避したい失敗は「`grep` で引いて偽陰性を掴むこと」で、その瞬間は
まだ何も Read していない。**したがって `paths` 付き rules へはスコープできず、常時層に置くしかない。**
同 skill が「シェルの使い方やコマンドの組み立てに関する規範も移せない」として挙げている型と同じ。

常時層に置くのはトリガ文と判定文だけで、一次実測は `home/.claude/references/observation.md` が
持つ。カテゴリの H2 と observation.md の H2 が 1 対 1 で対応する既存の構造に合わせる。

置き先のカテゴリは `## [MUST] 観測した結果がその主張の証拠になっているか確かめ、観測自体を加工や
連結で壊さない`。3 点とも「検査が劣化しても劣化を申告しない」形で、このカテゴリが既に持つ
「0 件・空・緑を健全の根拠にする前に」と「検索キーの偽陰性」の延長にあたる。

## 制約

- tgrep の内部仕様 (poll 間隔・reconcile 時間・索引ファイルの構成・具体的なミリ秒数) を常時層の
  散文へ再掲しない。CI が捕捉できない形で drift する
- 常時ロード層は現在ちょうど予算上限 (27030B) なので、追記すると必ず config-guard が赤くなる。
  `ALWAYS_LOADED_BUDGET_BYTES` を実態へ合わせて引き上げ、`BUDGET_RAISES` へ (日付, 引き上げ後の値,
  理由) を 1 行足す。許可条件の canonical は `budget_ratchet.evaluate_ratchet`
- 予算は実態から 2000B 以上離せない (`test_budget_tracks_the_real_repo_closely`)。余裕を持たせず
  書いた分ちょうどに合わせる

## 採らなかった案

いずれもユーザー裁定で確定済み。自然に再提案される種類なので理由を残す。

### `permissions.deny` へ bare `Grep` を入れる

不採用。理由は 3 つで、索引の無いリポジトリで詰まる、リポジトリ外を探せない、Explore など
Grep に依存する組み込み subagent がある。pnpm の規範は deny を canonical にしてその手前で
読ませる構成だが、検索ツールでは deny 側が成立しない。

### 常時層を削って相殺する

不採用。予算は引き上げる。

### scoped rule (`paths` 付き rules) へ逃がす

成立しない。上の「置き場所の判定」のとおり。

## タスク

- [x] tgrep の 3 つの面を実測で再現する (前セッションの観測を根拠にしない)
- [x] 置き場所を `home:context-loading-mechanics` の判定基準で決める
- [ ] `home/.claude/CLAUDE.md` のカテゴリへトップレベル項目を足す
- [ ] `home/.claude/references/observation.md` へ対応する H2 と一次実測を足す
- [ ] `ALWAYS_LOADED_BUDGET_BYTES` を実態へ合わせ `BUDGET_RAISES` へ 1 行足す
- [ ] ISSUE-46 の検算節へ、この Issue が起票と同じ PR で閉じるため表に現れないことを残す
- [ ] bats と config-guard を緑にする

## 関連

ISSUE-46: マイルストーン表。この Issue は起票と同じ PR でクローズするため表には載せない
(ISSUE-92 で確立した扱いで、同 Issue の検算節が「今後も同じ形は起きる」と一般化している)。
内容としては常時層への追記なので M10 相当

ISSUE-92: 直前の委譲。あちらも agentic-coding-tools からの委譲を dotfiles 側の配線として
受けたもので、`tgrep` の Brewfile 宣言と `.tgrep/` の ignore はあちらの PR の副産物として入った
