---
status: open
---

# refactor: skill バンドルの command と agent の二重登録を止める

## 背景

`security-blue-red-team` と `web-monkey-qa` の 2 bundle は、同じ command 5 個と agent 3 個が
prefix 有無の 2 通りで system prompt に載っている。description が完全に一致した分を毎ターン
払っている。

出所は Claude Code ではなく apm の deploy 規則にある。apm は root SKILL.md を持つパッケージを
`.claude/skills/<pkg>/` へ verbatim コピーし、`.claude-plugin/` を持つパッケージの `agents/` と
`commands/` を `.claude/agents/` `.claude/commands/` へ flat 分解する。両方を持つパッケージは
両方の規則が走るので、同じ内容が 2 箇所に置かれ、Claude Code がそれぞれを別経路で登録する。
apm 0.28.0 にこれを抑止するノブは無い。

実測と選択肢の比較は
[Issue #36](../closed/36_CLAUDE.md%20を%20rules%20と%20skill%20へ分割し常時ロード量を減らす/issue.md) の
「command と agent の二重登録の出所を確定し方針を決めた」節が canonical。同節で S5 を採ることを
決めた。上流の 2 bundle から sub-skills を撤去して bundle を command と agent だけにし、dotfiles
側は apm install 後に flat 側の deploy 先を消す。登録は prefix 名の 1 経路になる。

残す側を prefix 経路にしたのは、そちらが plugin の契約を満たしているため。`schemas/` が届くのも
`${CLAUDE_PLUGIN_ROOT}` が解決するのも verbatim コピー経由の側だけで、flat 側にはその経路が無い。
削減幅は #36 の「シナリオごとの常時ロード bytes」表の S5 行が canonical。

作業の主体は PUBLIC リポジトリ [hidari/agentic-coding-tools](https://github.com/hidari/agentic-coding-tools)
側にあり、dotfiles 側は flat 側の後始末と apm の pin を揃える部分を持つ。

## 着手前に確認すること

`security-red-team` と `security-blue-team` の sub-skill は、長い日本語の description で
自然言語からの自動起動を担っている。撤去するとその起動経路が失われる。root SKILL.md か
command の description へ移すか、落とすかを決める必要がある。この trade-off は Issue 36 の
該当節に書かれていない。

## 調査結果 (2026-08-25)

以下は実測で、着手時にそのまま使える。

### 実行順序に制約がある

上流で prefix 名へ揃える、そのあと dotfiles で flat を消す。逆順は壊れる。bare 名が
解決しているのは flat 配置のおかげなので、flat を先に消すと参照が解決しなくなる。

### 上流 main は無保護だが PR 経由で進める

classic の branch protection API が 404、ruleset も空であることを、dotfiles の
protect-main を対照に置いて確認した。それでも PR 経由にする。

### 撤去で失われるものは 4 つのうち 2 つだけ

sub-skill 4 個のうち 2 個は既に dead で、同名 command が prefix 名前空間で勝つため
一度も system prompt に載っていない。

| sub-skill | 常時ロード | 撤去で失われるもの |
| --- | --- | --- |
| `security-red-team` | 載る | 自然言語の trigger 語彙、使われない条件の振り分け案内 |
| `security-blue-team` | 載る | 同上 |
| `security-vulnerability-assessment` | dead | 実質なし (要精査) |
| `monkey-qa` | dead | dispatcher 本体 11.4KB (command 経由で使われている) |

`fingerprint` の要件と `DO NOT` の責務境界は agent 側が canonical なので失われない。

### 数え方の落とし穴が 2 つ

`${CLAUDE_PLUGIN_ROOT}/schemas/` の参照 6 箇所は agents/ と commands/ に限った数で正しい。
skills 配下 9 と root SKILL.md 1 を足すと 16 になるだけで、母集団を揃えずに数え直すと
「本文が間違っている」という誤った結論が出る。

bare dispatch 6 箇所も正しい (commands 3 + skills 3)。ただし commands 側は
`` - `subagent_type`: `red-team-agent` `` という記法なので、`subagent_type[=:" ]` のような
文字クラスで引くと 3 箇所が落ちる。

### flat 側の後始末をどこへ置くかは実機で決着済み

`apm lifecycle` は採らない。実測で次が分かっている。

- `post-install` イベントは存在するが、trust していないと走らない。しかも
  `apm install` は exit 0 を返すので、走らなかったことに気づけない
- trust は lifecycle ブロックのハッシュに紐づくので、ブロックを編集すると失効する
- trust の保存先は `~/.apm/scripts-trust.json` でマシンローカル、dotfiles の追跡外

採るのは 2 層。`apm install` を呼ぶ場所 (`bootstrap.sh` の `install_apm_packages`) に
後始末を隣接させ、config-guard に「flat の deploy 先が空であること」を不変条件として足す。
bootstrap 単独では日常の `apm install` を取りこぼすので不十分。

## タスク

- [ ] sub-skill の description が担っていた自然言語からの自動起動の移し先を決める
      (root `SKILL.md` へ移す / command の description へ移す / 落とす)
- [ ] `security-vulnerability-assessment` が撤去で失うものを精査する。現時点では dead で
      実質なしと見ているが確定していない
- [ ] 2 bundle から sub-skills を撤去する (`security-blue-red-team/skills/` の 3 個と
      `web-monkey-qa/skills/` の 1 個)。plugin.json の `"skills"` 宣言も外す。
      root `SKILL.md` は残す (verbatim コピーが `schemas/` の唯一の deploy 経路のため)
- [ ] `/monkey-qa` は `Skill(skill="web-monkey-qa:monkey-qa")` を起動する薄い entry point で、
      実体が撤去する sub-skill 側にある。dispatcher 本体を command へ取り込む
- [ ] security bundle の bare dispatch 6 箇所 (`subagent_type: red-team-agent` 等) を prefix 名へ
      揃える。web-monkey-qa は既に prefix 名で呼んでいるので対象外
- [ ] 撤去した skill への参照を残さない。`web-monkey-qa/README.md` と
      `web-monkey-qa/commands/monkey-qa.md` に加え、security bundle の root `SKILL.md` 自身
      (component 表と description) も該当する
- [ ] `${CLAUDE_PLUGIN_ROOT}/schemas/<name>` の参照 6 箇所が撤去後も解決することを確かめる
- [ ] dotfiles 側で flat 側の deploy 先を消す後始末を入れる。apm install のたびに再生成される。
      置き場は決着済みで、`bootstrap.sh` の `install_apm_packages` に隣接させ、config-guard で
      「flat の deploy 先が空であること」を不変条件として pin する (経緯は上の調査結果)
- [ ] `apm install --frozen` と `apm audit` が、flat 側を消した状態で通ることを確かめる
- [ ] dotfiles の `home/apm.yml` の agentic-coding-tools 向け pin をまとめて新 SHA へ揃え、
      `apm install` で供給を繋ぐ
- [ ] 新セッションで登録が prefix 名の 1 経路になったことを実測し、削減後のバイト数を
      Issue #36 へ記録する

## 関連

- [Issue #36: CLAUDE.md を rules と skill へ分割し常時ロード量を減らす](../closed/36_CLAUDE.md%20を%20rules%20と%20skill%20へ分割し常時ロード量を減らす/issue.md)。
  本 Issue の実測と方針決定はすべて #36 側にある。派生
- [Issue #25: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する](../closed/25_skill%20と%20plugin%20を新規%20PUBLIC%20リポジトリへ集約し%20apm%20配布へ移行する/issue.md)。
  供給を apm 1 経路へ寄せた Issue。本 Issue はその経路の中で起きている二重配置を扱う
- flat 分解を抑止するノブが無いこと自体は上流の設計判断なので、必要なら
  [microsoft/apm](https://github.com/microsoft/apm) へ報告する余地がある。ノブが入れば dotfiles
  側の後始末は不要になるが、本 Issue は上流の変更を待たずに閉じられる
