---
status: open
---

# docs(rules): 検査機構の作り方の知見を規範層へ取り込む

## 背景

委譲元から届いた「検査機構を作るときの落とし穴」の知見を、dotfiles の規範層 (常時層の
CLAUDE.md / paths 付き rules / references) へ取り込む。

材料は検証ワークフローで実測と突き合わせてある。**委譲元の主張のうち 3 件は反証または
解釈依存なので、そのまま規範として書かないこと。**

### 反証された前提

- 「分母と分子を両方数えて突き合わせる手当てが既存に無い」は偽。`rules/testing-practices.md`
  が既に「数える」ことを規定し、`references/testing.md` の「範囲の穴は 3 種の変異では
  見えない」節が Pester の実例を分母と分子の形で持つ。**新規なのは 2 点だけ** — (a) 突き合わせを
  常設の別検査として置くこと (b) 落ちた側が列数最大という偏りの向き
- 委譲元の推測「INS-1 と INS-6 は失敗側にトリガがあるので paths 付き rules へ寄せられる」の
  うち INS-1 は誤り。検査機構を足すときに編集するのは `scripts/**/*.py` / `rules/*.yml` /
  `sgconfig.yml` / `.pre-commit-config.yaml` / `.github/workflows/*.yml` で、どの rules の
  `paths` にも一致しない。同型は ISSUE-48 の軸F が既に記録している
- INS-3 の新規性は解釈に依存する。`references/observation.md` の既存 3 実例はいずれも
  その場で書いた使い捨てコマンドなので、射程は実質すでに届いている。確実に新規なのは
  「ツールの出力どうしを突き合わせている限り決着しない、一次の実体へ降りて初めて付く」という
  決め手の方

### 取り込む知見

識別子は検証ワークフローの採番。内容の canonical は `.cache/delegation-inspection-mechanisms.md`
と検証結果 (`.cache/delegation-verification-summary.txt`)。

| ID | 内容 | 置き場の提案 |
| --- | --- | --- |
| INS-1 | 検査機構を足したら「対象が何件あり、そのうち何件を実際に見たか」を突き合わせる検査を別に常設する | `references/testing.md` へ追記 + `rules/testing-practices.md` の「数える」項を締める |
| INS-1B | 件数の閾値で置いた陽性対照は総崩れしか検出しない | `references/observation.md` の「非 0 件も証明にならない」節 |
| INS-2 | 検証手段の層の優先順位 (型システム > 構文木 > トークナイザ > 正規表現)。さらに上位として、外部からの検証よりテストコードへ落とせないかを先に問う | **未決** (常時層が素直だが余裕 0) |
| INS-2C | 実装の確認や調査でコードを引くとき grep より ast-grep を優先する | **未決** (dotfiles の指示層か skill の description か) |
| INS-3 | 使い捨ての検証ツールの誤りは検証対象の欠陥と同じ形で出る。決着はツールの出力どうしでは付かず一次の実体へ降りる | `references/observation.md` の「対照側も同じだけ壊れる」節 |
| INS-4 | 外部サービスとの契約を増やしたら Fake 側にも同じ契約を足す。テストの本数では防げない | **未決** (失敗の瞬間は本番アダプタ側の編集) |
| INS-5 | 変異の見逃しは pin が弱いとは限らない。到達不能な分岐は見逃しとして現れ、正解は pin の強化ではなく分岐の撤去 | `rules/testing-practices.md` + `references/testing.md` |
| INS-6 | fixture の深さが pin の射程を決める。実コードの構造の深さを fixture が持たないとその深さに依存する機構が守られない | `rules/testing-practices.md` + `references/testing.md` |

### 予算

常時層 +600B / scoped +350B / references +1800B (検証ワークフローの見積もり)。

常時層は余裕 0 なので、INS-2 / INS-2C / INS-4 を常時層へ置くなら `BUDGET_RAISES` への記録が
要る。予算の上限の canonical は config-guard の `instruction_budget`。

## タスク

- [ ] INS-1 を `references/testing.md` へ追記し、`rules/testing-practices.md` の「数える」項を
      「分母と分子を両方数えて突き合わせる検査を別に置く」へ締める
- [ ] INS-1B を `references/observation.md` の陽性対照の項へ足す
- [ ] INS-3 を `references/observation.md` の対照の節へ足す
- [ ] INS-5 を `rules/testing-practices.md` と `references/testing.md` へ足す
- [ ] INS-6 を `rules/testing-practices.md` と `references/testing.md` へ足す
- [ ] INS-2 の置き場を決めて入れる。常時層なら `BUDGET_RAISES` への記録を同じ変更に含める
- [ ] INS-2C の置き場を決めて入れる。skill の description へ置くなら cross-repo の変更になる
- [ ] INS-4 の置き場を決めて入れる
- [ ] 足した規範が委譲元のトリガから到達するかを確かめる。`references/` へ足すだけでは常時層から
      到達できず、ISSUE-48 が孤児の節の実例を持つ
- [ ] 新規の scoped rules を足した場合は `config_guard.rules_paths.EXPECTED_PATHS` への pin を
      足す (`check_rules_paths` が「pin が無い」で報告する)
- [ ] ISSUE-46 のマイルストーン表へ入れる

## 未決

着手前に決める。決めずに個別へ入れると常時層の配分が判断できなくなる。

- **INS-2 の置き場。** トリガ (検証手段を選ぶ瞬間) に file surface が無いので ISSUE-36 の基準では
  常時層だが余裕 0 で `BUDGET_RAISES` が要る。代案は (a) 検査記述面 (`sgconfig.yml` /
  `rules/*.yml` / `.pre-commit-config.yaml` / `scripts/**/*.py` / `.github/workflows/*.yml`) へ
  向けた新規 `paths` 付き rules (b) ISSUE-48 の再構成で観測カテゴリを圧縮した分で払う。
  (a) は scoped rules が Read ツールでしか発火しないため、検査を書く前に検査ファイルを Read する
  とは限らず到達が弱い
- **INS-2C の置き場。** dotfiles の指示層へ置くか、`ast-grep-practice` skill の description へ
  置くか。後者なら常時層のバイトを 1 も使わず (skill description は別勘定) トリガも全セッションへ
  届くが、実体は agentic-coding-tools 側にあり dotfiles 単独では完結しない。cross-repo の変更を
  許すか
- **INS-4 の置き場。** 失敗の瞬間は本番アダプタ側の編集なので `rules/testing-practices.md` の
  `paths` は届かない。CLAUDE.md の語彙定義 (契約テスト) を +60B 程度で締めれば正しいトリガに
  載るが `BUDGET_RAISES` が要る。`testing-practices.md` へ置く案は「Fake を開いた時点で発火する」
  ので遅いが非ゼロ
- **ISSUE-48 との着手順。** INS-1B と INS-3 は観測カテゴリの参照先に触るので、ISSUE-48 の
  再構成より先に足すと再構成のたたき台が動く。逆に後追いにすると滞留する
- **1 Issue にまとめるか置き場ごとに割るか。** references と scoped rules だけで完結する
  INS-1 / INS-1B / INS-3 / INS-5 / INS-6 は予算に当たらないので先に通せる。予算に当たる
  INS-2 / INS-2C と INS-4 だけを別 Issue にして ISSUE-48 の隣へ置く形もある
- **BUDGET_RAISES をまとめるか。** ISSUE-89 (Rust のビルド規範) も常時層に触りうる。
  3 件をまとめて 1 回で払うか個別に上げるか
- **INS-3 の扱い。** 上記のとおり新規性が解釈に依存する。散文が「使い捨て」を名指ししていない
  だけを理由に追記するなら、canonical カテゴリの検算 3 (書いた宣言の範囲が実態より広くないか) の
  逆方向 (既存の宣言が実態より狭く読まれていた) を根拠にすることになる

## 関連

- ISSUE-48 — 観測カテゴリの主語を観測へ引き上げ未被覆の軸を塞ぐ。INS-1B と INS-3 が触る
  `references/observation.md` はあちらの再構成対象。着手順は上の未決
- ISSUE-46 — 両リポジトリの Issue をマイルストーンへ整理し着手順を決める。所属の canonical は
  あちらの表
- ISSUE-89 — Rust のビルド規範。常時層の予算を共有するので配分をまとめて決める
- 材料は `.cache/delegation-inspection-mechanisms.md` (委譲元の原文) と
  `.cache/delegation-verification-summary.txt` (反証と配置提案)。どちらも追跡外
