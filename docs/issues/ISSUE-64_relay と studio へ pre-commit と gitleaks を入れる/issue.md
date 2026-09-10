---
status: in_progress
---

# chore: relay と studio へ pre-commit と gitleaks を入れる

## 背景

ユーザーが管理権を持つ 3 リポジトリ (agentic-coding-tools / relay /
studio-Hamiltonian-logo-automation) を dotfiles と agentic-coding-tools の運用へ揃えたい、
という依頼から始まった。範囲を実測で絞った結果、揃っていないのは品質ゲートだけだった。

秘密の混入を止める層が 2 リポジトリに無い。どちらも PRIVATE だが、非公開であることは
1 層目であって、gitleaks は 2 層目にあたる。1 層に頼らないことは user CLAUDE.md の
「攻撃者が使える面を最小に保ち防御を 1 層に頼らない」が求めている。

## 実測 (2026-08-30)

| 項目 | agentic-coding-tools | relay | studio-Hamiltonian |
| --- | --- | --- | --- |
| `.hidari/` | あり | あり | あり |
| `.claude/settings.local.json` | あり | あり | あり |
| `docs/issues/` | 45 件 | 127 件 | 147 件 |
| `apm.yml` | なし | なし | なし |
| pre-commit | あり | **なし** | **なし** |
| `.gitleaks.toml` | あり | **なし** | **なし** |
| 公開範囲 | PUBLIC | PRIVATE | PRIVATE |

`.hidari/` も `settings.local.json` も `docs/issues/` も 3 リポジトリとも既に揃っている。
移行が要ると思われていた部分は終わっていた。

### 実測表の訂正 (2026-09-11)

上の表の「pre-commit: なし」は 2 つのことを区別していない。実際に無かったのはツールの
ほうだけで、フック体系そのものは両リポジトリとも持っていた。どちらも `core.hooksPath` で
`.githooks/` を指しており、relay は 3 経路、studio は pre-push 1 本を動かしていた。

この取り違えは着手の見積もりを歪める。「フックが無いので入れる」ではなく「既存のフック体系を
別の機構へ移す」が実際の作業で、移植と旧手順の撤去がついてくる。

pre-commit の実体を実測した。git の機能とツールの二層である。

- git の機能: `.git/hooks/pre-commit` を commit 前に呼ぶ
- ツール: pre-commit (pre-commit.com) は Homebrew 経由で `/opt/homebrew/bin/pre-commit` にある
- `pre-commit install` が `.git/hooks/pre-commit` を生成し、ツール自身を呼ばせる

dotfiles では Brewfile がツールを宣言し (`bootstrap.sh:224`)、`bootstrap.sh:866` が
dotfiles 自身に対して `pre-commit install` を実行している。

## 既存履歴の走査 (2026-09-07)

取り付ける前に既存履歴を測った。走査は両リポジトリとも全 ref を対象にしている (`--log-opts=--all`)。
既定ブランチだけを見ると、作業中のブランチにしかない履歴が母集団から落ちる。実際 studio 側は
既定ブランチではない場所にいた。

| 対象 | 走査量 | 検出 |
| --- | --- | --- |
| relay | 613 commits | 0 件 |
| studio-Hamiltonian | 389 commits | 2 件 |
| 対照 (使い捨てリポジトリ) | 1 commit | 2 件 |

**検出の 2 件はどちらも偽陽性だった。**1 件はテスト用に生成した鍵で、ソース自身のコメントが
実サービス認証には使わないダミーだと書いている。もう 1 件は計画ドキュメントに載せたコマンド例で、
長い識別子の entropy が閾値を超えたものである。実体はどちらも秘密ではない。

**2 件とも現在の HEAD に存在しない。**pre-commit の gitleaks は staged 差分だけを見るので、履歴に
残っている検出は取り付けの障害にならない。allowlist も baseline も今は要らない。同種のものを
将来書いたときに初めて赤くなるので、そのとき allowlist を足す。

### 0 件を信じる前に対照が要る

最初に作った対照が 0 件を返した。原因は検体の選び方で、AWS 公式ドキュメントの例示キーを使って
いた。あの値は gitleaks 側で許可されている。**対照が壊れていることは、対照側の 0 件としてしか
現れない。**対象側の 0 件と区別がつかないので、対照が非空になることを先に確かめてから対象の
0 件を読むこと。

検体を秘密鍵の PEM と Slack のボットトークンへ替えたところ 2 件を検出し、走査経路が働いている
ことを確かめられた。relay の 0 件はこの対照の上で読んだ値である。

## 設計の論点

### 取り付けはリポジトリに travel しない

`.git/hooks/` は git の管理下に無いので、`.pre-commit-config.yaml` を commit しても
clone しただけでは効かない。`pre-commit install` を各リポジトリで 1 回実行する必要がある。

設定ファイルは配布されるが、それを呼ぶ側は配布されない。この非対称が「設定を置けば終わり」に
ならない理由である。dotfiles の `bootstrap.sh` は自分自身にしかこれをやっていないので、
汎用化するかどうかがこの Issue の論点になる。

**この論点は実測で解消した (2026-09-11)。**両リポジトリとも既に自前の取り付け経路を持って
いた。relay は `cargo xtask setup`、studio は README の手順である。どちらも
`core.hooksPath` を設定する形だったものを `pre-commit install` へ差し替えれば済み、
`bootstrap.sh` の汎用化は要らない。対象リポジトリの一覧をどこが持つかという drift の火種も
発生しない。

### core.hooksPath が残っていると取り付けは静かに失敗する

移行で最も踏みやすいのはここだった。`core.hooksPath` が設定されていると `pre-commit install`
は警告を出して取り付けに失敗するが、コミット自体は成功する。検査が一度も走らないまま緑が
続くので、`--all-files` の緑だけを見ていると「取り付いた」と誤判定する。relay の最初の
live smoke で実際に陽性検体が素通りした。

relay は `run_setup` の `--unset-all` で塞ぎ、studio は `.githooks/` の撤去と README /
CLAUDE.md からの旧手順の削除で塞いだ。どちらもテストで pin してある。

### apm.yml は置かない (決定済み)

dotfiles が user スコープで `~/.claude/skills/` へ 16 個を配置しており、これは全リポジトリで
効く。PRIVATE_CLAUDE.md も project スコープは「project 固有のもの」に限っている。
3 リポジトリが共通 skill を使うだけなら apm.yml は要らない。

agentic-coding-tools 自身への導入は、canonical がリポジトリ内にあるのに `.claude/skills/` へも
deploy される二重配置になる (apm の deploy 規則として既知で、抑止するノブが無い)。

各リポジトリで版を固定したくなったら後から足せる。足すのは容易なので、要るまで置かない。

### 設定の内容をどこから採るか

agentic-coding-tools の `.pre-commit-config.yaml` は 14 個の hook を持つが、その多くは
そのリポジトリ固有である (`plugin-validate` / `package-shape` / `readme-drift` 等)。
汎用のものだけを採る。公式の `end-of-file-fixer` / `trailing-whitespace` / `check-json` /
`check-yaml` と、local の `gitleaks` がそれにあたる。

in-repo Issue の記法検査 (`issue-id-notation` 系) を含めるかは別の判断が要る。
両リポジトリとも `docs/issues/` を持つので対象にはなるが、既存違反の量を先に測らないと
取り付けた瞬間に赤くなる。上流の増分モードが既存違反を直さずに取り付ける入口になる。

**測って決めた。含めない (2026-09-11)。**既存違反は relay 1745 件 / studio 2010 件あり、
中身は `#242424` のような hex color が主だった。識別子が裸の数字である両リポジトリでは、
本文中の参照と数量表現・色指定を機械的に区別できない。増分モードで取り付けても、色を
1 つ足すたびに偽陽性が出る。

区別できる形にするには識別子の記法そのものを変える必要があり、それは上流
(agentic-coding-tools の ISSUE-22) が rename しない判断を持っているので、この Issue の
範囲では動かせない。

### provisioning は各リポジトリの既定に従う (2026-09-11 裁定)

gitleaks と pre-commit をどこから供給するかは 2 リポジトリで形が違う。揃えるのは
`.gitleaks.toml` の検出集合であって、起動経路ではない。

| リポジトリ | 供給 | 起動 |
| --- | --- | --- |
| relay | mise.toml の pin | `mise exec -- gitleaks` |
| studio | Homebrew | PATH 直起動 |

relay を mise のままにしたのは、あちらの 2026-07-11 の設計 (toolchain-version-guardrails) が
PATH 直起動を明示的に禁じているためである。理由は開発機に古い版が残って pin と食い違った
ことで、gitleaks にも同じ経路が開く。既に actionlint と shellcheck が同じ機構に乗っている。

studio には mise が無く、持ち込むと使っていないリポジトリへ新しいツールチェーンを足すことに
なるので Homebrew 前提にした。どちらもテストで pin してあり、片方の形をもう片方へ写すと
赤くなる。

### 設定ファイル自身の構文検査が無い (未決)

studio の live smoke で見つけた。`.pre-commit-config.yaml` の `name` の値に裸のコロンが
あると YAML が mapping と解釈し、pre-commit が `InvalidConfigError` で起動しない。

配線を pin するテストは YAML をテキストとして読むので、この形を素通りする。実際に studio では
テスト 8 件すべてが緑のまま構文エラーを見逃し、取り付け後の live smoke で初めて露見した。

同じ穴は relay 側にもある。どちらの CI にも pre-commit を走らせる job が無く、
`pre-commit validate-config` を呼ぶ経路もどこにも無い。塞ぐには CI に job を足すか、
テストから validate-config を呼ぶかだが、後者はテストが外部コマンドに依存するので
CI に pre-commit が無い状態では落ちる。どちらを採るかは決めていない。

## タスク

- [x] relay と studio の既存履歴に対して gitleaks を走らせ、検出の有無と量を測る。
      検出があれば扱い (直すのか allowlist へ入れるのか) を決めてから取り付ける。
      結果と扱いの判断は「既存履歴の走査 (2026-09-07)」節が持つ
- [x] `.gitleaks.toml` を 2 リポジトリへ置く。dotfiles の検出集合をそのまま採るのか、
      リポジトリごとに変えるのかを決める。dotfiles の canonical は `.gitleaks.toml` 自身なので
      散文へ再掲しないこと
      → dotfiles と同一の検出集合を採った。両リポジトリとも `cmp` でバイト単位の一致を確認済み。
      PII ルールのコストは `--staged` が差分しか見ないことの実測で消えている
- [x] `.pre-commit-config.yaml` を 2 リポジトリへ置く。汎用の hook だけを採り、
      リポジトリ固有のものは持ち込まない
      → relay は PR #606、studio は PR #316。旧 `.githooks` が持っていた検査は両方とも
      全経路を移してある
- [x] 取り付けが実際に効いていることを、検出されるべき文字列を含む一時ファイルで確かめる。
      走らせて 0 件だったことを健全の根拠にしない (正常なら非空になる対照を並べる)
      → 両リポジトリとも陽性検体で HEAD が動かないことと、陰性側で全 hook を通過することの
      両方を live smoke で確認した。studio では pre-push stage の 714 テスト実行も見ている
- [x] `pre-commit install` の実行経路を決める。dotfiles の `bootstrap.sh` を汎用化して
      他リポジトリへも取り付けるのか、各リポジトリで手動にするのかを比較する。
      汎用化するなら対象リポジトリの一覧をどこが持つかが drift の火種になる
      → 両リポジトリとも自前の経路を既に持っていたので汎用化は不要。判断の根拠は
      「取り付けはリポジトリに travel しない」節が持つ
- [x] in-repo Issue の記法検査を含めるかを、既存違反の量を測ったうえで決める
      → 含めない。件数と理由は「設定の内容をどこから採るか」節が持つ

## 関連

ISSUE-53: 配布先の加入状況と写しの drift を見る層が無い。あちらは加入しているかを機構で
見る層の設計で、この Issue は実際に加入させる作業。ISSUE-53 が「pre-commit 自体を持たない
リポジトリには載せる土台が無い」と書いている、その土台をこの Issue が作る。着手はこちらが先。

ISSUE-46: 両リポジトリの Issue をマイルストーンへ整理し着手順を決める

agentic-coding-tools の ISSUE-32: in-repo Issue の検査を配布先で走る状態にする。
記法検査を含めるかの判断はこちらの層 1 (増分モード) に依存する
