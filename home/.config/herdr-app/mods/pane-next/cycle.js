// 今のタブの pane を並び順で巡回する。pane-next と pane-prev が同じ内容を持ち、向きは main.js が渡す。
// mod はフォルダの外を import できないので共有できず、食い違わないことは scripts/tests/herdr-app-mods.bats が見る。
// herdr-app には巡回コマンドが無いので、キーから mod.open で overlay として開き、一度だけ動いてすぐ閉じる。

import { View, div } from "gpui-kit";
import { panes, focused, run, closeOverlay, props } from "herdr";

export function cycler(step) {
  return class PaneCycle extends View {
    init(_props, cx) {
      const tab = focused()?.tab;
      const list = panes().filter((p) => p.tab === tab);
      const i = list.findIndex((p) => p.focused);
      if (list.length > 1 && i >= 0) {
        run("pane.focus", { pane: list[(i + step + list.length) % list.length].pane });
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
  };
}
