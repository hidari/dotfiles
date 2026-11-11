"use strict";
// ページの判定 (logic.js) の仕様。node --test で回す
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const L = require("./logic.js");

const pred = (field, op, value, negate = false) => ({ field, op, value, negate });
const clause = (...preds) => ({ preds });
const item = (o = {}) => ({ id: "K1-001", issue: "ISSUE-1", section: "s", labels: [], report_count: 1, ...o });

test("parseConditions: 正常な文書から節と述語を取り出す", () => {
  const r = L.parseConditions({ clauses: [clause(pred("issue", "eq", "ISSUE-1"))] });
  assert.deepEqual(r.warnings, []);
  assert.deepEqual(r.clauses, [clause(pred("issue", "eq", "ISSUE-1"))]);
});

test("parseConditions: JSON の文字列も受ける", () => {
  const r = L.parseConditions(JSON.stringify({ clauses: [clause(pred("appended", "exists", null))] }));
  assert.equal(r.clauses.length, 1);
});

test("parseConditions: null・配列でない・壊れた JSON でも落ちず空と警告を返す", () => {
  assert.deepEqual(L.parseConditions(null).clauses, []);
  assert.deepEqual(L.parseConditions(null).warnings, []);
  assert.deepEqual(L.parseConditions(undefined).clauses, []);
  assert.deepEqual(L.parseConditions(42).clauses, []);
  const notArray = L.parseConditions({ clauses: "x" });
  assert.deepEqual(notArray.clauses, []);
  assert.equal(notArray.warnings.length, 1);
  const broken = L.parseConditions("{oops");
  assert.deepEqual(broken.clauses, []);
  assert.equal(broken.warnings.length, 1);
  const badClause = L.parseConditions({ clauses: [null, { preds: "x" }] });
  assert.equal(badClause.clauses.length, 2);
  assert.equal(badClause.warnings.length, 2);
  assert.equal(L.promoted(item(), badClause.clauses), false);
});

test("parseConditions: 知らない field と op の組は警告に載り、その節は昇格させない", () => {
  const r = L.parseConditions({ clauses: [clause(pred("summary", "eq", "x")), clause(pred("issue", "gte", "x"))] });
  assert.equal(r.warnings.length, 2);
  assert.equal(L.promoted(item({ summary: "x", issue: "x" }), r.clauses), false);
});

test("parseConditions: 値の形が op に合わない述語は警告に載り、その節は昇格させない (negate でも反転して通らない)", () => {
  const bad = [
    pred("report_count", "gte", "abc"), pred("report_count", "gte", null), pred("report_count", "gte", true),
    pred("added", "gte", "昨日"), pred("issue", "eq", 5), pred("label", "has", ""),
  ];
  for (const p of bad) {
    const r = L.parseConditions({ clauses: [clause(p)] });
    assert.equal(r.warnings.length, 1, JSON.stringify(p));
    assert.equal(L.promoted(item({ report_count: 0, issue: "x" }), r.clauses), false, JSON.stringify(p));
    const neg = L.parseConditions({ clauses: [clause({ ...p, negate: true })] });
    assert.equal(L.promoted(item({ report_count: 0, issue: "x" }), neg.clauses), false, JSON.stringify(p));
  }
  // negate が真偽値でない述語も使えない
  const badNegate = L.parseConditions({ clauses: [clause(pred("report_count", "gte", 1, "yes"))] });
  assert.equal(badNegate.warnings.length, 1);
  assert.equal(L.promoted(item({ report_count: 0 }), badNegate.clauses), false);
  assert.deepEqual(L.parseConditions({ clauses: [clause(pred("report_count", "gte", "3"))] }).warnings, []);
  assert.deepEqual(L.parseConditions({ clauses: [{ preds: [{ field: "label", op: "has", value: "a" }] }] }).warnings, []);
});

test("parseConditions: 7つの組はすべて警告なし", () => {
  const preds = [
    pred("issue", "eq", "a"), pred("section", "eq", "a"), pred("added", "gte", "2026-01-01"),
    pred("appended", "exists", null), pred("appended", "gte", "2026-01-01"),
    pred("label", "has", "実測"), pred("report_count", "gte", 2),
  ];
  assert.deepEqual(L.parseConditions({ clauses: [clause(...preds)] }).warnings, []);
});

test("promoted: 節の中は積、節どうしは和", () => {
  const a = pred("issue", "eq", "ISSUE-1"), b = pred("section", "eq", "s");
  const it = item({ issue: "ISSUE-1", section: "other" });
  assert.equal(L.promoted(it, [clause(a, b)]), false);
  assert.equal(L.promoted(it, [clause(a), clause(b)]), true);
  assert.equal(L.promoted(item({ section: "s" }), [clause(a, b)]), true);
  assert.equal(L.promoted(it, []), false);
  assert.equal(L.promoted(it, [clause()]), false);
});

test("promoted: 各述語の境界", () => {
  assert.equal(L.promoted(item({ added: "2026-11-10" }), [clause(pred("added", "gte", "2026-11-10"))]), true);
  assert.equal(L.promoted(item({ added: "2026-11-09" }), [clause(pred("added", "gte", "2026-11-10"))]), false);
  assert.equal(L.promoted(item(), [clause(pred("added", "gte", "2026-11-10"))]), false);
  assert.equal(L.promoted(item({ appended: "2026-11-10" }), [clause(pred("appended", "exists", null))]), true);
  assert.equal(L.promoted(item(), [clause(pred("appended", "exists", null))]), false);
  assert.equal(L.promoted(item({ appended: "2026-11-10" }), [clause(pred("appended", "gte", "2026-11-11"))]), false);
  assert.equal(L.promoted(item({ report_count: 3 }), [clause(pred("report_count", "gte", 3))]), true);
  assert.equal(L.promoted(item({ report_count: 2 }), [clause(pred("report_count", "gte", 3))]), false);
  assert.equal(L.promoted(item({ labels: ["実測"] }), [clause(pred("label", "has", "実測"))]), true);
  assert.equal(L.promoted(item({ labels: ["実測値"] }), [clause(pred("label", "has", "実測"))]), false);
});

test("promoted: negate で札を外す", () => {
  const c = [clause(pred("label", "has", "実測"), pred("label", "has", "推測", true))];
  assert.equal(L.promoted(item({ labels: ["実測"] }), c), true);
  assert.equal(L.promoted(item({ labels: ["実測", "推測"] }), c), false);
});

test("localDate: 実行環境のタイムゾーンの日付 (TZ を変えた子プロセスで確かめる)", () => {
  const run = tz => {
    const r = spawnSync(
      process.execPath,
      ["-e", 'process.stdout.write(require("./logic.js").localDate("2026-11-10T16:00:00Z"))'],
      { cwd: __dirname, env: { ...process.env, TZ: tz }, encoding: "utf8" },
    );
    assert.equal(r.status, 0, r.stderr);
    return r.stdout;
  };
  assert.equal(run("Asia/Tokyo"), "2026-11-11");
  assert.equal(run("UTC"), "2026-11-10");
});

test("localDate: 読めない値は空文字", () => {
  assert.equal(L.localDate("not a date"), "");
  assert.equal(L.localDate(undefined), "");
});

test("needsReview: 追記が判断の日と同じ日かそれより後なら true", () => {
  const doc = { decision: "採る", updatedAt: "2026-11-10T03:00:00Z" };
  const day = L.localDate(doc.updatedAt);
  assert.equal(L.needsReview(item({ appended: day }), doc), true);
  assert.equal(L.needsReview(item({ appended: "2999-01-01" }), doc), true);
  assert.equal(L.needsReview(item({ appended: "2000-01-01" }), doc), false);
});

test("needsReview: 追記の日付は判断時刻の UTC の日ではなくローカルの日と比べる (TZ を変えた子プロセス)", () => {
  const run = tz => {
    const code = 'const L = require("./logic.js");' +
      'process.stdout.write(String(L.needsReview({ appended: "2026-11-10" }, { decision: "採る", decidedAt: "2026-11-10T16:00:00Z" })))';
    const r = spawnSync(process.execPath, ["-e", code], { cwd: __dirname, env: { ...process.env, TZ: tz }, encoding: "utf8" });
    assert.equal(r.status, 0, r.stderr);
    return r.stdout;
  };
  assert.equal(run("Asia/Tokyo"), "false");
  assert.equal(run("UTC"), "true");
});

test("needsReview: decidedAt が updatedAt より優先され、両方無ければ false", () => {
  const it = item({ appended: "2026-11-05" });
  const late = { decision: "採る", updatedAt: "2026-11-01T12:00:00Z", decidedAt: "2026-11-09T12:00:00Z" };
  assert.equal(L.needsReview(it, late), false);
  const early = { decision: "採る", updatedAt: "2026-11-09T12:00:00Z", decidedAt: "2026-11-01T12:00:00Z" };
  assert.equal(L.needsReview(it, early), true);
  assert.equal(L.needsReview(it, { decision: "採る" }), false);
  assert.equal(L.needsReview(it, { decision: "採る", updatedAt: "壊れた" }), false);
});

test("needsReview: 判断が無い・追記が無ければ false", () => {
  const it = item({ appended: "2026-11-10" });
  assert.equal(L.needsReview(it, null), false);
  assert.equal(L.needsReview(it, { decision: null, updatedAt: "2026-11-01T00:00:00Z" }), false);
  assert.equal(L.needsReview(item(), { decision: "採る", updatedAt: "2026-11-01T00:00:00Z" }), false);
});

test("inDefaultList: 節0個は未判断の全件、見直し対象は節によらず入る", () => {
  assert.equal(L.inDefaultList(item(), null, []), true);
  assert.equal(L.inDefaultList(item(), { decision: "採る", updatedAt: "2026-11-01T00:00:00Z" }, []), false);
  const review = item({ appended: "2999-01-01" });
  const doc = { decision: "採る", updatedAt: "2026-11-01T00:00:00Z" };
  assert.equal(L.inDefaultList(review, doc, []), true);
  assert.equal(L.inDefaultList(review, doc, [clause(pred("issue", "eq", "none"))]), true);
});

test("inDefaultList: 節があれば昇格かつ未判断", () => {
  const c = [clause(pred("issue", "eq", "ISSUE-1"))];
  assert.equal(L.inDefaultList(item(), null, c), true);
  assert.equal(L.inDefaultList(item({ issue: "ISSUE-2" }), null, c), false);
  assert.equal(L.inDefaultList(item(), { decision: "保留", updatedAt: "2026-11-01T00:00:00Z" }, c), false);
  assert.equal(L.inDefaultList(item(), { decision: null }, c), true);
});

test("bulkTargets: 判断済みは skipped へ、順序と重複", () => {
  const decided = { b: "採る", d: "保留" };
  const r = L.bulkTargets(["a", "b", "c", "d", "a"], id => decided[id] || null);
  assert.deepEqual(r, { apply: ["a", "c"], skipped: ["b", "d"] });
  assert.deepEqual(L.bulkTargets([], () => null), { apply: [], skipped: [] });
});

test("undoTargets: 直前のまとめての判断で付けた件だけ", () => {
  assert.deepEqual(L.undoTargets({ apply: ["a", "c"], skipped: ["b"] }), ["a", "c"]);
  assert.deepEqual(L.undoTargets(null), []);
  const last = { apply: ["a"], skipped: [] };
  L.undoTargets(last).push("x");
  assert.deepEqual(last.apply, ["a"]);
});

test("cardGroups: 確かめ済みとモデルの判断に振り分ける", () => {
  const it = item({
    summary: "要約", recommendation: "採る", reason: "理由", placement: "rules", placement_detail: "詳細",
    labels: ["実測", "推測"], report_count: 3, added: "2026-11-01", appended: "2026-11-05",
    covered: { status: "partial", path: "a.md", quote: "引用" },
    verified: { labels_ok: ["実測"], labels_ng: ["推測"], quote_ok: true },
  });
  const g = L.cardGroups(it);
  const has = (list, key, value) => list.some(e => e.key === key && (value === undefined || e.value === value));
  assert.ok(has(g.verified, "label", "実測"));
  assert.ok(has(g.verified, "quote", "引用"));
  assert.ok(has(g.verified, "issue", "ISSUE-1"));
  assert.ok(has(g.verified, "section"));
  assert.ok(has(g.verified, "added", "2026-11-01"));
  assert.ok(has(g.verified, "appended", "2026-11-05"));
  assert.ok(has(g.model, "label", "推測"));
  assert.ok(!has(g.verified, "label", "推測"));
  assert.ok(has(g.model, "report_count", 3));
  assert.ok(!has(g.verified, "report_count"));
  for (const k of ["summary", "recommendation", "reason", "placement", "placement_detail", "covered_status"]) {
    assert.ok(has(g.model, k), k);
    assert.ok(!has(g.verified, k), k);
  }
});

test("cardGroups: 引用が確かめられなければ model へ", () => {
  const g = L.cardGroups(item({
    covered: { status: "partial", path: "a.md", quote: "消えた引用" },
    verified: { labels_ok: [], labels_ng: [], quote_ok: false },
  }));
  assert.ok(g.model.some(e => e.key === "quote" && e.value === "消えた引用"));
  assert.ok(!g.verified.some(e => e.key === "quote"));
});

test("cardGroups: 札0個と引用無しなら空の列を返す", () => {
  const g = L.cardGroups({ verified: { labels_ok: [], labels_ng: [], quote_ok: false } });
  assert.deepEqual(g, { verified: [], model: [] });
  assert.deepEqual(L.cardGroups({}), { verified: [], model: [] });
});

test("conditionCounts: 節ごとの該当件数", () => {
  const items = [item({ id: "a" }), item({ id: "b", issue: "ISSUE-2" }), item({ id: "c", issue: "ISSUE-2", labels: ["実測"] })];
  const clauses = [clause(pred("issue", "eq", "ISSUE-2")), clause(pred("label", "has", "実測")), clause(pred("x", "eq", 1))];
  assert.deepEqual(L.conditionCounts(items, clauses), [2, 1, 0]);
  assert.deepEqual(L.conditionCounts(items, []), []);
  assert.deepEqual(L.conditionCounts([], clauses), [0, 0, 0]);
});
