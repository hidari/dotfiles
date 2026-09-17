---
status: open
---

# agent: writing-plans が plan に求めるコード片を規範へ合わせる補正工程を置く

## 背景

非公開の利用側リポジトリから委譲された (2026-09-17)。1 つの機能を subagent-driven-development で
回した実測から出てきた。

ユーザーの裁定は次のとおり。規範を正とし、上流 (superpowers) には手を入れず、agentic-coding-tools
側に補正の工程を置く。形 (skill / hook / 既存 skill への追記) は dotfiles 側で決める。

### 衝突

- グローバル CLAUDE.md の MUST 項目の子に「SDDを行う際には直接的な実装コード片をできる限り減らし、
  Mermaidによる図示やデシジョンテーブルなどの各種テスト技法を用いること」がある
- superpowers 6.3.0 の writing-plans は、No Placeholders 節で「Steps that describe what to do
  without showing how (code blocks required for code steps)」を plan の失敗として挙げる。Task
  Structure のテンプレートも、失敗するテスト・最小実装・commit の各 step にコードブロックを置く。
  Self-Review の Placeholder scan は、この節のパターンで plan を洗わせる
- **読み替えでは衝突は消えない。**コードブロックの要求は明示されている

### 実測 (利用側リポジトリ)

追跡下の plan 4 本と spec 3 本で、フェンスの中の行 (mermaid を除く) が占める比率を数えた。
分母や、コマンドと出力のフェンスを分けたかは記録に無い。

| 種類 | フェンス内の行の比率 (mermaid を除く) |
| --- | --- |
| spec 3 本 | いずれも 0% |
| plan 4 本 | 5% / 37% / 44% / 57% |

mermaid を使っていたのは 7 本中 1 本 (spec) だけだった。brainstorming にはコードブロックの要求が無い。

実害も出ている。plan が書いた失敗時の挙動の説明 (どのシェルが動くか) を、出荷されたコードの
コメントが明示的に否定していた。plan を根拠にした人は偽の事実を受け取る。

### 優先の宣言には頼れない

- using-superpowers は「User instructions (CLAUDE.md, ...) take precedence over skills」と定める
- ただし冒頭の SUBAGENT-STOP で、dispatch された subagent に自身を無視させる。subagent が plan を
  書く経路には、この宣言が届かない
- plan を書く瞬間に規範と照合する機構も無い。注意喚起を増やしても効かないので、衝突の解消か、
  発火点での可視化が要る

### 補正を置く根拠 (writing-plans 自身の記述)

1. Overview は読み手を「文脈ゼロで、テスト設計に明るくない engineer」と置いている。グローバル
   CLAUDE.md が注入される fresh subagent は、この前提に当たらない
2. 置き場の既定には「(User preferences for plan location override this default)」があり、
   issue-scoped-artifacts が実際に上書きしている。出力を利用者側で補正する先例がある

### 費用の移り先

subagent-driven-development の Model Selection は、散文から実装する implementer の下限を mid-tier に
置き、「When the task's plan text contains the complete code to write, the implementation is
transcription plus testing: use the cheapest tier for that implementer」としている。plan から
コード片を減らすと、実装役の階層が上がる。

## 決めること

- **「SDD」の語義。**グローバル CLAUDE.md はこの語を定義していない。リポジトリ内の他の箇所
  (Issue 16 の plan、上流 ISSUE-57 のたたき台) は subagent-driven-development の意味で使っている。
  規範が指すのが spec 駆動の文書全般なのか、subagent-driven-development の plan なのかを先に確定する。
  規範が置かれた親項目 (書かずに済むことで drift を防ぐ) も材料にする。確定した語義を CLAUDE.md 側で
  明示するかも決める。常時層は予算に余裕が無く、足すなら `BUDGET_RAISES` への記録が要る
  (複数 Issue の調整は ISSUE-88 が持つ)
- **補正が防ぐもの。**上の実害は、実装後の plan が現状の説明として読まれたことによる。コード片を
  減らしても、plan がその時点のスナップショットだと明示されていなければ同じ害は残りうる
- **補正の形。**
  - (a) issue-scoped-artifacts のように、writing-plans の直前に発火する skill
  - (b) plan の書き出しを検査する hook
  - (c) 既存 skill への追記
  - issue-scoped-artifacts はプロジェクト CLAUDE.md のポインタで発火するので、意図的な opt-out と
    書き損ねを区別できない (上流 ISSUE-35)。同じ仕組みに載せるとこの性質も引き継ぐ
- **subagent への到達。**補正が、subagent の書く plan に効く経路になっているか。hook なら、
  SubagentStart で subagent の文脈へ届く経路が ISSUE-71 にある
- **どこまで減らすか。**コードの代わりに何を書くか (Mermaid / デシジョンテーブル / テスト技法)。
  テストのコードも減らすのか。実装役の階層が上がる費用をどう扱うか

## タスク

- [ ] 「SDD」の語義を確定する
- [ ] 補正の形を決める
- [ ] subagent が書く plan へ補正が届くことを実測で確かめる
- [ ] 比べる指標の数え方を固定し、補正前の値を取る。候補は plan のコード片の比率 (分母と、実装・
      コマンド・出力の区別)、plan の記述と出荷コードの食い違い、実装役の階層・費用。数え方を
      決められない指標は比較から外す
- [ ] agentic-coding-tools へ実装を委譲する
- [ ] 補正の後で同じ数え方の値を取り、前後を比べる

## 関連

- ISSUE-100: 同じ委譲元からの依頼 (マージ前ゲートの dispatch プロンプト)
- Issue 16 (closed): 同じ上流 skill の出力 (置き場) を fork せずに補正した前例
- Issue 17: plan の成果物名の検査。補正が plan を書き換えるなら、同じ置き場の規約に従う
- Issue 30: plan のコードブロックが実際に壊れた記録を持つ。コード片が減れば検査の対象面も小さくなる
- ISSUE-88: 常時層へ足す規範の予算調整 (`BUDGET_RAISES`) を持つ
- ISSUE-71: SubagentStart で subagent の文脈へ届ける経路。実測は ISSUE-70 (closed)
- agentic-coding-tools の ISSUE-35: CLAUDE.md のポインタで発火する仕組みが持つ性質
- agentic-coding-tools の ISSUE-57: 「SDD」を subagent-driven-development の意味で使っている例
