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

async function open(page: Page, delayDecisions = false) {
  await page.addInitScript((seed) => { (window as any).__fakeSeed = seed; }, { docs: { decisions: DECISIONS }, delayDecisions });
  await page.addInitScript({ path: FAKE_DB });
  await page.goto("/index.html");
}

const writes = (page: Page) => page.evaluate(() => (window as any).__writes as Write[]);
const decisionWrites = async (page: Page) => (await writes(page)).filter((w) => w.path.startsWith("decisions/"));

test.describe("昇格の条件とまとめての判断", () => {
  test("条件で絞り、全件を選んで採らないを付け、判断済みには書かず、取り消すと付けた件だけ戻る", async ({ page }) => {
    await open(page);
    await expect(page.locator("#status")).toHaveText("判断は保存先に自動で記録されます。");

    // 条件 report_count:gte 2 を保存する
    await page.locator("#cond-add").click();
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
      // メモは送らない。既存の文書への update は欄ごと無く、新規の set も空のまま
      expect(w.fields.note ?? "").toBe("");
      if (w.op === "update") expect(w.fields).not.toHaveProperty("note");
    }
    // 下書きのメモを持つ T-02 は既存文書なので update で、メモを触らない
    expect(done.find((w) => w.path === "decisions/T-02")!.op).toBe("update");
    // 判断済みの T-01 への書き込みは 0 件
    expect(done.filter((w) => w.path === "decisions/T-01")).toHaveLength(0);

    // 取り消すと付けた件だけに decision: null が送られる
    await page.locator("#bulk-undo").click();
    await expect.poll(async () => (await decisionWrites(page)).length).toBe(6);
    const undone = (await decisionWrites(page)).slice(3);
    expect(undone.map((w) => w.path).sort()).toEqual(["decisions/T-02", "decisions/T-03", "decisions/T-04"]);
    for (const w of undone) expect(w.fields.decision).toBeNull();
  });

  test("判断が届く前は一括・条件・このままでよいを書き込めず、届くと書ける", async ({ page }) => {
    await open(page, true);
    await expect(page.locator("input[data-select]").first()).toBeVisible();

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
    expect(await writes(page)).toHaveLength(0);
  });
});
