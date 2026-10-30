// 注意が必要な次の agent へフォーカスする。
// blocked (入力待ち) を done (完了・未読) より優先し、同じグループ内は呼ぶたびに順送りで巡回する。
// キーから mod.open:unread で overlay として開かれ、init で一度だけ動いてすぐ閉じる。

import { View, div } from "gpui-kit";
import { agents, run, notify, closeOverlay, props } from "herdr";

export default class Unread extends View {
  init(_props, cx) {
    const all = agents();
    let targets = all.filter((a) => a.status === "blocked");
    if (targets.length === 0) targets = all.filter((a) => a.status === "done");
    if (targets.length === 0) {
      notify({ title: "No blocked or unread agents", level: "info", timeout: 2000 });
    } else {
      // 既に対象グループにフォーカスしているなら次の要素へ、そうでなければ先頭へ
      const i = targets.findIndex((a) => a.focused);
      run("agent.focus", { terminal: targets[(i + 1) % targets.length].address });
    }
    // overlay は init の時点ではまだ開き終わっていないので、閉じるのは次の tick に回す
    cx.spawn(async () => {
      const overlay = props()?.overlay;
      if (overlay) closeOverlay(overlay);
    });
  }

  render() {
    return div();
  }
}
