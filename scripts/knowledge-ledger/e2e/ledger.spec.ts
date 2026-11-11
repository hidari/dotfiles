import { test, expect, type Page } from "@playwright/test";
import { resolve } from "node:path";

// playwright は package.json のあるこのディレクトリから起動する
const FAKE_DB = resolve("e2e/fake-db.js");

type Write = { op: string; path: string; fields: Record<string, unknown> };

// T-01 は判断済みでメモを持ち、判断の後に追記があり report_count が2 (見直しの対象として既定の一覧に戻る)。
// T-02 は判断が null でメモだけを持つ下書き。T-02..T-04 が未判断で report_count が2以上
const DECISIONS = {
  "T-01": { decision: "採る", note: "既存のメモ", updatedAt: "2026-11-01T00:00:00.000Z", decidedAt: "2026-11-01T00:00:00.000Z" },
  "T-02": { decision: null, note: "下書きのメモ", updatedAt: "2026-11-02T00:00:00.000Z" },
};

// 各件の届いた報告の数 (fixtures/items.json の report_count)
const REPORTS: Record<string, number> = { "T-01": 2, "T-02": 2, "T-03": 3, "T-04": 2 };

async function open(page: Page, opts: { delayDecisions?: boolean; throwSettings?: boolean } = {}) {
  await page.addInitScript((seed) => { (window as any).__fakeSeed = seed; }, { docs: { decisions: DECISIONS }, ...opts });
  await page.addInitScript({ path: FAKE_DB });
  await page.goto("/index.html");
}

const writes = (page: Page) => page.evaluate(() => (window as any).__writes as Write[]);
const decisionWrites = async (page: Page) => (await writes(page)).filter((w) => w.path.startsWith("decisions/"));

test.describe("昇格の条件とまとめての判断", () => {
  test("条件で絞り、全件を選んで採らないを付け、判断済みには書かず、取り消すと付けた件だけ戻る", async ({ page }) => {
    await open(page);
    await expect(page.locator("#status")).toHaveText("判断は保存先に自動で記録されます。");

    // 述語を全部消した節は保存できず、警告に出る
    await page.locator("#cond-add").click();
    const clause1 = page.getByRole("group", { name: "節 1" });
    await clause1.getByRole("button", { name: "述語を削除" }).click();
    await expect(page.locator("#cond-warn")).toContainText("節 1 に述語が無い");
    await expect(page.locator("#cond-save")).toBeDisabled();
    await clause1.getByRole("button", { name: "述語を追加" }).click();
    await expect(page.locator("#cond-warn")).not.toContainText("述語が無い");

    // 条件 report_count:gte 2 を保存する
    await page.getByLabel("節1の述語1 の種類").selectOption("report_count:gte");
    await page.getByLabel("節1の述語1 の値").fill("2");
    await page.locator("#cond-save").click();
    await expect(page.locator("#cond-msg")).toContainText("条件を保存しました。");
    const cond = (await writes(page)).filter((w) => w.path === "settings/promotion");
    expect(cond).toHaveLength(1);
    expect(cond[0].fields.clauses).toEqual([{ preds: [{ field: "report_count", op: "gte", value: 2, negate: false }] }]);

    // 一覧は該当件だけ (未判断の3件と、見直し対象の判断済み1件)
    await expect(page.locator("#count")).toHaveText("4 件 (全 10 件)");
    const ids = () => page.locator("input[data-select]").evaluateAll((els) => els.map((e) => e.getAttribute("data-select")).sort());
    expect(await ids()).toEqual(["T-01", "T-02", "T-03", "T-04"]);

    // このページの全件を選んで採らないを付ける
    await page.locator("#select-page").click();
    await expect(page.locator("#bulk-count")).toHaveText("4");
    await page.locator("#bulk-reject").click();
    await expect(page.locator("#bulk-skipped")).toHaveText("1 件は判断済みのため飛ばした");
    await expect.poll(async () => (await decisionWrites(page)).length).toBe(3);

    const done = await decisionWrites(page);
    expect(done.map((w) => w.path).sort()).toEqual(["decisions/T-02", "decisions/T-03", "decisions/T-04"]);
    for (const w of done) {
      expect(w.fields.decision).toBe("採らない");
      expect(typeof w.fields.decidedAt).toBe("string");
      // 判断の時点で見た報告の数を記録する
      expect(w.fields.seenReports).toBe(REPORTS[w.path.slice("decisions/".length)]);
      // メモは送らない。既存の文書への update は欄ごと無く、新規の set も空のまま
      expect(w.fields.note ?? "").toBe("");
      if (w.op === "update") expect(w.fields).not.toHaveProperty("note");
    }
    // 下書きのメモを持つ T-02 は既存文書なので update で、メモを触らない
    expect(done.find((w) => w.path === "decisions/T-02")!.op).toBe("update");
    // 判断済みの T-01 への書き込みは 0 件
    expect(done.filter((w) => w.path === "decisions/T-01")).toHaveLength(0);

    // 付ける件が無かったまとめての判断は、直前のまとめての判断の取り消しを消さない
    await page.locator("input[data-select='T-01']").check();
    await page.locator("#bulk-hold").click();
    await expect(page.locator("#bulk-msg")).toHaveText("付ける件がなかった");
    await expect(page.locator("#bulk-skipped")).toHaveText("1 件は判断済みのため飛ばした");
    await expect(page.locator("#bulk-undo")).toBeEnabled();
    expect(await decisionWrites(page)).toHaveLength(3);

    // 取り消すと付けた件だけに decision: null が送られる
    await page.locator("#bulk-undo").click();
    await expect.poll(async () => (await decisionWrites(page)).length).toBe(6);
    const undone = (await decisionWrites(page)).slice(3);
    expect(undone.map((w) => w.path).sort()).toEqual(["decisions/T-02", "decisions/T-03", "decisions/T-04"]);
    for (const w of undone) {
      expect(w.fields.decision).toBeNull();
      expect(w.fields).not.toHaveProperty("note");
      expect(w.fields.seenReports).toBe(REPORTS[w.path.slice("decisions/".length)]);
    }
  });

  test("判断が届く前は一括・条件・このままでよい・カードの判断とメモを書き込めず、届くと書ける", async ({ page }) => {
    await open(page, { delayDecisions: true });
    await expect(page.locator("input[data-select]").first()).toBeVisible();
    // 判断済みの T-01 も届く前は「まだ」に見える。押せると届いていない判断を上書きするので押せない
    const t01 = page.getByRole("group", { name: "T-01 の判断" }).getByRole("button");
    const note = page.getByLabel("T-01 のメモ");
    await expect(t01).toHaveCount(4);
    for (const b of await t01.all()) await expect(b).toBeDisabled();
    await expect(note).toBeDisabled();

    // 届く前でも選ぶことはできる (書き込みではない)
    await page.locator("input[data-select='T-03']").check();
    await expect(page.locator("#bulk-count")).toHaveText("1");
    const gated = ["#bulk-adopt", "#bulk-hold", "#bulk-reject", "#bulk-undo", "#select-page", "#cond-add", "#cond-save"];
    for (const sel of gated) await expect(page.locator(sel), sel).toBeDisabled();
    // 判断が届く前は見直しの対象を知らないので、見えている「このままでよい」は無い
    await expect(page.locator("button.ack:visible")).toHaveCount(0);

    // 判断が届くと有効になる。一括の3つは選択がある今だけ
    await page.evaluate(() => (window as any).__releaseDecisions());
    await expect(page.locator("#status")).toHaveText("判断は保存先に自動で記録されます。");
    for (const sel of ["#bulk-adopt", "#bulk-hold", "#bulk-reject", "#select-page", "#cond-add"]) await expect(page.locator(sel), sel).toBeEnabled();
    await expect(page.locator("#bulk-undo")).toBeDisabled();
    await expect(page.locator("button.ack:visible")).toHaveCount(1);
    await expect(page.locator("button.ack:visible")).toBeEnabled();
    for (const b of await t01.all()) await expect(b).toBeEnabled();
    await expect(note).toBeEnabled();
    await expect(note).toHaveValue("既存のメモ");
    expect(await writes(page)).toHaveLength(0);

    // 打たずにフォーカスを外しても書かない
    await note.focus();
    await note.blur();
    // フォーカス中に別の端末がメモを変えても、打っていなければ外したときに上書きせず、届いたメモを見せる
    await note.focus();
    await page.evaluate(() => (window as any).__remoteUpdate("decisions", "T-01", { note: "別の端末のメモ", updatedAt: "2026-11-05T00:00:00.000Z" }));
    await note.blur();
    await expect(note).toHaveValue("別の端末のメモ");
    await page.waitForTimeout(1200);
    expect(await writes(page)).toHaveLength(0);

    // 打って外すと、メモだけを1回送る (遅れて走る保存で2度目を送らない)
    await note.fill("足したメモ");
    await note.blur();
    await expect.poll(async () => (await writes(page)).length).toBe(1);
    await page.waitForTimeout(1200);
    const noteWrites = await writes(page);
    expect(noteWrites).toHaveLength(1);
    expect(noteWrites[0].op).toBe("update");
    expect(noteWrites[0].path).toBe("decisions/T-01");
    expect(noteWrites[0].fields.note).toBe("足したメモ");
    for (const k of ["decision", "decidedAt", "seenReports"]) expect(noteWrites[0].fields).not.toHaveProperty(k);

    // このままでよいは判断の時刻と見た報告の数だけを送り、見直しの印が外れる
    await page.locator("button.ack:visible").click();
    await expect.poll(async () => (await writes(page)).length).toBe(2);
    const ack = (await writes(page))[1];
    expect(ack.path).toBe("decisions/T-01");
    expect(ack.fields.seenReports).toBe(REPORTS["T-01"]);
    expect(typeof ack.fields.decidedAt).toBe("string");
    for (const k of ["decision", "note"]) expect(ack.fields).not.toHaveProperty(k);
    await expect(page.locator("button.ack:visible")).toHaveCount(0);
  });

  test("条件の購読が同期で投げても判断は届き、条件の編集は読むだけになる", async ({ page }) => {
    await open(page, { throwSettings: true });
    await expect(page.locator("#status")).toHaveText("判断は保存先に自動で記録されます。");
    await expect(page.locator("#cond-msg")).toContainText("条件の保存先を読めませんでした");
    await expect(page.locator("#cond-add")).toBeDisabled();
    await expect(page.locator("#cond-save")).toBeDisabled();
    // 判断の方は書ける
    await expect(page.locator("#select-page")).toBeEnabled();
    await expect(page.getByRole("group", { name: "T-03 の判断" }).getByRole("button", { name: "採る" })).toBeEnabled();
  });
});
