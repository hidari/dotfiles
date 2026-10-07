---
status: open
---

# docs: agentic-coding-tools の skill から撤去済みの Tirith フックを前提にした説明を外す

## 背景

ISSUE-115 で dotfiles から tirith の Claude Code PreToolUse フックを撤去した。agentic-coding-tools が apm で配る次の skill は、配布元の環境にそのフックがある前提で説明を書いている。

- `commit-and-pr-message`: 「前提: なぜファイル経由なのか」節が、ファイル経由にする理由の片方を Tirith の `confusable_text` に置いている。発火条件の表や「配布元の環境では tirith を呼ぶ hook の wrapper が最終判定を下す」という記述もある
- `pre-merge-quality-gate`: Phase 5 に「Tirith が止めるのは本文をインラインで渡したときだけ」という1文がある

手順そのもの (本文をファイルに書き、検査してから file 系フラグで渡す) は、検査と受け渡しが同じファイルを読むという理由だけで成り立つので変わらない。直すのは「配布元の環境ではこう止められる」という事実の記述で、撤去後の配布元では偽になった。コマンド文字列を検査する hook を持つ利用者の環境のための説明として残すか、節ごと畳むかを決める。

PRIVATE_CLAUDE.md の運用どおり、agentic-coding-tools への修正の進め方は dotfiles 側で決める。

## タスク

- [ ] 2つの skill の Tirith への言及を全件洗い出し、それぞれ「一般の hook を持つ環境の説明として残す / 消す」を決める
- [ ] agentic-coding-tools 側で直し、タグを切る
- [ ] dotfiles の apm.yml の pin を新しいタグへ揃えて `apm install` し、配布物 (`home/.claude/skills/` 配下) に撤去前提の記述が残っていないことを確かめる

## 関連

- ISSUE-115: tirith の Claude Code フックの撤去
- agentic-coding-tools の skill の canonical はそちらのリポジトリにあり、`home/.claude/skills/` は apm の展開物なので直接は編集しない
