# issue-scoped-artifacts ポインタの展開メモ

調査日 2026-08-06。`~/Develop` 配下の CLAUDE.md / AGENTS.md 計 129 ファイルを深さ無制限で走査した結果。

## 何をするものか

superpowers の brainstorming / writing-plans が生成する spec と plan を、既定の
`docs/superpowers/(specs|plans)/` ではなく Issue ディレクトリ配下
(`docs/issues/<NNN>_<title>/<NNN>-spec.md` と `<NNN>-plan.md`) へ置かせる規約。

skill 側が opt-in 設計になっていて、プロジェクトの CLAUDE.md にポインタがある場合にのみ適用され、
無いプロジェクトでは何もせず既定の置き場に従う。したがって展開作業はポインタ 1 行を足すだけで済む。

skill 本体は dev-workflow plugin (user scope) にあるので全プロジェクトから見えている。
効いていないのは発動条件だけ。

## 追加する 1 行

各リポジトリの CLAUDE.md の MUST ルール節へ、箇条書きとして追加する。

```
- superpowers の spec / plan は Issue ディレクトリ配下へ `<NNN>-spec.md` / `<NNN>-plan.md` として置く（規約と手順の canonical は `dev-workflow:issue-scoped-artifacts` skill）
```

dotfiles (22 行目) と scriptoria (94 行目) に入っている文面と完全一致。両者に drift は無い。

規約の中身を書かず skill を canonical として指しているのが要点。散文と skill に同じルールを
二重に書くと drift するので、この 1 行は「どこに置くか」だけを述べ、命名規則や手順は skill に委ねる。

## 追加先の候補

| リポジトリ | Issue ディレクトリ数 | 旧置き場のファイル数 | 状態 |
|---|---|---|---|
| astralys-art | 56 | 18 | 追加済み |
| studio-Hamiltonian-logo-automation | 32 | 30 | 追加済み |
| relay | 21 | 27 | 追加済み |
| compose-lite | 10 | 2 | 未追加 |
| melnics | 8 | 0 | 未追加 |
| capture-one-scripts | 3 | 16 | 未追加 |
| claude-plugins | 2 | 4 | 未追加 |
| home | 2 | 11 | 未追加 |
| sherpa | 2 | 7 | 未追加 |
| cospl | 0 | 8 | 保留 |
| dotfiles | 15 | 13 | 追加済み |
| scriptoria | 83 | 26 | 追加済み |

「Issue ディレクトリ数」は `docs/issues/` 直下のディレクトリ数、「旧置き場のファイル数」は
`docs/superpowers/` 配下の総ファイル数。

### cospl だけ性質が違う

`docs/superpowers/` に 8 ファイルある一方で `docs/issues/` が存在しない。ポインタを足しても
行き先が無いので、先に `dev-workflow:in-repo-issue` で Issue 運用を始めるかどうかの判断が要る。

### melnics は旧置き場が空

`docs/superpowers/` が 0 件なので、移行対象の既存ファイルが無い。ポインタを足すだけで完結する。

## pre-commit ゲート (任意)

dotfiles にはこの hook も入っていて、旧置き場へ書き込もうとすると落ちる。
`.pre-commit-config.yaml` を持つのは 12 リポジトリ中 dotfiles だけなので、pre-commit を
使っているリポジトリ限定。

```yaml
      - id: issue-scoped-artifacts
        name: spec と plan は Issue ディレクトリ配下へ置く
        language: fail
        entry: "この成果物は docs/issues/<NNN>_<title>/<NNN>-spec.md または <NNN>-plan.md へ置く"
        files: '^docs/superpowers/(plans|specs)/'
```

既存の旧置き場ファイルがあっても導入して問題ない。pre-commit は staged なファイルしか見ないため、
触らない限り発火しない。逆に旧置き場のファイルを後から編集したときには落ちる。移行の合図として
使うならちょうどよい挙動だが、意図しない足止めになるようなら `files` の正規表現を調整する。

## 注意

- 既存の `docs/superpowers/` 配下のファイルは移動されない。ポインタは新規生成物の置き場を
  変えるだけで、過去分の移行は別作業になる
- 旧置き場のファイル数が多いリポジトリ (studio-Hamiltonian-logo-automation 30 件、
  relay 27 件、scriptoria 26 件) は、移行するなら参照の張り替えも要る
