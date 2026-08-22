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
[Issue #36](../36_CLAUDE.md%20を%20rules%20と%20skill%20へ分割し常時ロード量を減らす/issue.md) の
「command と agent の二重登録の出所を確定し方針を決めた」節が canonical。同節で S5 を採ることを
決めた。上流の 2 bundle から sub-skills を撤去して bundle を command と agent だけにし、dotfiles
側は apm install 後に flat 側の deploy 先を消す。登録は prefix 名の 1 経路になる。

残す側を prefix 経路にしたのは、そちらが plugin の契約を満たしているため。`schemas/` が届くのも
`${CLAUDE_PLUGIN_ROOT}` が解決するのも verbatim コピー経由の側だけで、flat 側にはその経路が無い。
削減幅は #36 の「シナリオごとの常時ロード bytes」表の S5 行が canonical。

作業の主体は PUBLIC リポジトリ [hidari/agentic-coding-tools](https://github.com/hidari/agentic-coding-tools)
側にあり、dotfiles 側は flat 側の後始末と apm の pin を揃える部分を持つ。

## タスク

- [ ] 2 bundle から sub-skills を撤去する (`security-blue-red-team/skills/` の 3 個と
      `web-monkey-qa/skills/` の 1 個)。plugin.json の `"skills"` 宣言も外す。
      root `SKILL.md` は残す (verbatim コピーが `schemas/` の唯一の deploy 経路のため)
- [ ] `/monkey-qa` は `Skill(skill="web-monkey-qa:monkey-qa")` を起動する薄い entry point で、
      実体が撤去する sub-skill 側にある。dispatcher 本体を command へ取り込む
- [ ] security bundle の bare dispatch 6 箇所 (`subagent_type: red-team-agent` 等) を prefix 名へ
      揃える。web-monkey-qa は既に prefix 名で呼んでいるので対象外
- [ ] 撤去した skill への参照を残さない。`web-monkey-qa/README.md` と
      `web-monkey-qa/commands/monkey-qa.md` が該当する
- [ ] `${CLAUDE_PLUGIN_ROOT}/schemas/<name>` の参照 6 箇所が撤去後も解決することを確かめる
- [ ] dotfiles 側で flat 側の deploy 先を消す後始末を入れる。apm install のたびに再生成されるので、
      bootstrap に置くか apm の lifecycle script に置くかを決め、config-guard で取り付けを pin する
- [ ] `apm install --frozen` と `apm audit` が、flat 側を消した状態で通ることを確かめる
- [ ] dotfiles の `home/apm.yml` の agentic-coding-tools 向け pin をまとめて新 SHA へ揃え、
      `apm install` で供給を繋ぐ
- [ ] 新セッションで登録が prefix 名の 1 経路になったことを実測し、削減後のバイト数を
      Issue #36 へ記録する

## 関連

- [Issue #36: CLAUDE.md を rules と skill へ分割し常時ロード量を減らす](../36_CLAUDE.md%20を%20rules%20と%20skill%20へ分割し常時ロード量を減らす/issue.md)。
  本 Issue の実測と方針決定はすべて #36 側にある。派生
- [Issue #25: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する](../closed/25_skill%20と%20plugin%20を新規%20PUBLIC%20リポジトリへ集約し%20apm%20配布へ移行する/issue.md)。
  供給を apm 1 経路へ寄せた Issue。本 Issue はその経路の中で起きている二重配置を扱う
- flat 分解を抑止するノブが無いこと自体は上流の設計判断なので、必要なら
  [microsoft/apm](https://github.com/microsoft/apm) へ報告する余地がある。ノブが入れば dotfiles
  側の後始末は不要になるが、本 Issue は上流の変更を待たずに閉じられる
