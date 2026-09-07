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

## タスク

- [x] relay と studio の既存履歴に対して gitleaks を走らせ、検出の有無と量を測る。
      検出があれば扱い (直すのか allowlist へ入れるのか) を決めてから取り付ける。
      結果と扱いの判断は「既存履歴の走査 (2026-09-07)」節が持つ
- [ ] `.gitleaks.toml` を 2 リポジトリへ置く。dotfiles の検出集合をそのまま採るのか、
      リポジトリごとに変えるのかを決める。dotfiles の canonical は `.gitleaks.toml` 自身なので
      散文へ再掲しないこと
- [ ] `.pre-commit-config.yaml` を 2 リポジトリへ置く。汎用の hook だけを採り、
      リポジトリ固有のものは持ち込まない
- [ ] 取り付けが実際に効いていることを、検出されるべき文字列を含む一時ファイルで確かめる。
      走らせて 0 件だったことを健全の根拠にしない (正常なら非空になる対照を並べる)
- [ ] `pre-commit install` の実行経路を決める。dotfiles の `bootstrap.sh` を汎用化して
      他リポジトリへも取り付けるのか、各リポジトリで手動にするのかを比較する。
      汎用化するなら対象リポジトリの一覧をどこが持つかが drift の火種になる
- [ ] in-repo Issue の記法検査を含めるかを、既存違反の量を測ったうえで決める

## 関連

ISSUE-53: 配布先の加入状況と写しの drift を見る層が無い。あちらは加入しているかを機構で
見る層の設計で、この Issue は実際に加入させる作業。ISSUE-53 が「pre-commit 自体を持たない
リポジトリには載せる土台が無い」と書いている、その土台をこの Issue が作る。着手はこちらが先。

ISSUE-46: 両リポジトリの Issue をマイルストーンへ整理し着手順を決める

agentic-coding-tools の ISSUE-32: in-repo Issue の検査を配布先で走る状態にする。
記法検査を含めるかの判断はこちらの層 1 (増分モード) に依存する
