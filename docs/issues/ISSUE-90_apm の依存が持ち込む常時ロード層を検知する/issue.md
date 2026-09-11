---
status: open
---

# feat(config-guard): apm の依存が持ち込む常時ロード層を検知する

## 背景

委譲元のリポジトリで、apm の依存が同梱する `CLAUDE.md` が、配下のファイルを Read しただけで
コンテキストへ注入される形を踏んだ。委譲元は対照付きで「Read では発火し Bash 経由では発火
しない」ことまで実測している。同じ Read で `~/.claude/rules/` 側の scoped rules も一緒に
入ったので、機構は「Read が何を引き連れるか」の一段上にある。

**dotfiles には 2026-09-12 時点でこの面が無い。** apm は skill / plugin のサブツリーだけを
取得しており、リポジトリ全体を clone しないため。

| 走査 | 結果 (2026-09-12) |
| --- | --- |
| `home/apm_modules` 配下の `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` | 0 件 |
| 対照: `home/apm_modules` 配下の `*.md` | 69 件 (走査は機能している) |
| リポジトリ全体の `CLAUDE.md` | 2 件 (ルートと `home/.claude/`) |

問題は注入そのものではなく、**この状態が変わったときに気づく層が無いこと**。apm の依存に
パッケージ単位のものを 1 つ足す、あるいは apm の取得単位が変わるだけで面が生まれるが、
`instruction_budget` は常時ロード層しか見ないので数字に出ない。ISSUE-48 が記録する
「指示だけが常時ロードにあり、確認手段が発火しない状態」と同じ形になる。

### 既にある配線

`home/.claude/settings.json` の `claudeMdExcludes` に `**/home/.claude/CLAUDE.md` が 1 件あり、
config-guard が pin している (ISSUE-36 で配線、消さないこと)。schema の記述では「絶対パスに
picomatch で照合」。

### 未検証

委譲元も確かめていない 3 点。dotfiles で面が生まれる前に測っておく価値がある。

- `claudeMdExcludes` は `AGENTS.md` にも効くか (キー名は CLAUDE.md を指しているが実装が
  どこまで見るか不明)
- 除外するとトークンを払わなくなるのか、読み込んでから捨てるだけなのか
- user スコープの glob が project 配下の `apm_modules/` に届くか

## タスク

- [ ] `apm_modules` 配下に常時ロード層のファイル (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`) が
      現れたら報告する検査を config-guard へ置く
- [ ] 検査が実際に検出することを変異で確かめる。合成したプローブは apm の deploy 先と同じ
      構造上の位置に置く (位置が違うと別経路で成立する)
- [ ] `claudeMdExcludes` の未検証 3 点を live probe で測る。測った結果はメモリか
      `references/` へ残す
- [ ] ISSUE-46 のマイルストーン表へ入れる

## 未決

- **優先度。** 現状 0 件なので実害が無い。ISSUE-88 / ISSUE-89 より後でよいか、それとも
  「面が生まれてからでは遅い」側と見るか
- **検査の置き場。** config-guard の既存検査 (`instruction_budget` / `rules_paths` /
  `instruction_refs` / `term_definitions`) のどれかへ足すか、新しい検査として独立させるか。
  `instruction_budget` は常時ロード層を数える検査なので近いが、`apm_modules` は ignore 済みの
  再生成物であって追跡下ではない。config-guard の scan は追跡下のファイルだけを母集団にするので、
  **既存の scan 経路では apm_modules を見られない可能性がある**。ここは着手前に確かめる
- **`claudeMdExcludes` を先に広げるか。** 面が生まれる前に `**/apm_modules/**/CLAUDE.md` を
  足しておく案。ただし効くかどうかが未検証の 3 点に依存するので、測る前に足すと「足したのに
  効かない」を沈黙で抱えることになる

## 関連

- ISSUE-48 — 観測カテゴリの主語を観測へ引き上げ未被覆の軸を塞ぐ。「指示だけが常時ロードにあり
  確認手段が発火しない」形は軸F が記録している
- ISSUE-46 — 両リポジトリの Issue をマイルストーンへ整理し着手順を決める。所属の canonical は
  あちらの表
- ISSUE-36 (closed) — `claudeMdExcludes` の配線はここで入った
- メモリ reference-claude-md-nested-traversal が Read 発火と subagent ごとの課金を持つ
