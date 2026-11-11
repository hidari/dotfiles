// ページの判定。DOM にも保存先にも触れない純粋関数だけを置く。
// ブラウザではグローバル LedgerLogic、node では module.exports で使う
var LedgerLogic = (() => {
  // added を持たない件 (最初に載せた578件) が台帳に載った日
  const BASE_DATE = "2026-11-04";
  const DATE = /^\d{4}-\d{2}-\d{2}$/;
  const nonEmpty = v => typeof v === "string" && v !== "";
  const isDate = v => typeof v === "string" && DATE.test(v);
  // 使える述語は field と op の組でこの7つだけ。ok は op に合う値の形で、合わない述語は知らない述語と同じに扱う。
  // label と input は条件の編集画面の選択肢と値の欄の型 (input が null なら値を取らない)
  const PRED_KINDS = [
    { kind: "issue:eq", label: "Issue が", input: "text", ok: nonEmpty },
    { kind: "section:eq", label: "分野が", input: "text", ok: nonEmpty },
    { kind: "added:gte", label: "載った日が次の日以降", input: "date", ok: isDate },
    { kind: "appended:exists", label: "追記がある", input: null, ok: () => true },
    { kind: "appended:gte", label: "追記の日が次の日以降", input: "date", ok: isDate },
    { kind: "label:has", label: "札に次を含む", input: "text", ok: nonEmpty },
    { kind: "report_count:gte", label: "届いた報告が次の件数以上", input: "number", ok: v => (typeof v === "number" || nonEmpty(v)) && Number.isFinite(Number(v)) },
  ];
  const BY_KIND = new Map(PRED_KINDS.map(k => [k.kind, k]));
  const isValid = p => { const k = BY_KIND.get(p.field + ":" + p.op); return !!k && k.ok(p.value) && typeof p.negate === "boolean"; };
  const isObj = v => v !== null && typeof v === "object" && !Array.isArray(v);

  function parseConditions(raw) {
    const warnings = [];
    let doc = raw;
    if (typeof raw === "string") {
      try { doc = JSON.parse(raw); } catch (_) {
        return { clauses: [], warnings: ["条件の JSON を読めなかった"] };
      }
    }
    if (doc === null || doc === undefined) return { clauses: [], warnings };
    if (!isObj(doc) || !Array.isArray(doc.clauses)) {
      return { clauses: [], warnings: ["条件の形が違う (clauses の配列が無い)"] };
    }
    const clauses = doc.clauses.map((c, i) => {
      if (!isObj(c) || !Array.isArray(c.preds)) {
        warnings.push("節 " + (i + 1) + " の形が違う");
        return { preds: [] };
      }
      const preds = c.preds.map(p => {
        const q = isObj(p) ? p : {};
        return { field: q.field, op: q.op, value: q.value === undefined ? null : q.value, negate: q.negate === undefined ? false : q.negate };
      });
      if (!preds.length) warnings.push("節 " + (i + 1) + " に述語が無い");
      for (const p of preds) {
        if (!isValid(p)) warnings.push("節 " + (i + 1) + " に使えない述語 " + p.field + ":" + p.op + " がある");
      }
      return { preds };
    });
    return { clauses, warnings };
  }

  function holds(item, p) {
    switch (p.field + ":" + p.op) {
      case "issue:eq": return item.issue === p.value;
      case "section:eq": return item.section === p.value;
      case "added:gte": return (item.added || BASE_DATE) >= p.value;
      case "appended:exists": return !!item.appended;
      case "appended:gte": return !!item.appended && item.appended >= p.value;
      case "label:has": return (item.labels || []).includes(p.value);
      case "report_count:gte": return (item.report_count || 0) >= Number(p.value);
      default: return false;
    }
  }

  // 空の節は何も絞らないので昇格させない。知らない述語や値の形が合わない述語を持つ節も昇格させない
  function clauseMatches(item, c) {
    return c.preds.length > 0 && c.preds.every(p => isValid(p) && holds(item, p) !== p.negate);
  }
  const promoted = (item, clauses) => clauses.some(c => clauseMatches(item, c));

  function localDate(iso) {
    const d = new Date(iso);
    if (iso === undefined || iso === null || Number.isNaN(d.getTime())) return "";
    const pad = n => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }

  const decided = doc => !!(doc && doc.decision);

  // 届いた報告の数。merge.py と同じく無ければ1と数える
  const reportsOf = item => item.report_count || 1;

  // 判断か「このままでよい」の時点で見た報告の数 (seenReports) を今の数と比べる。merge.py は追記のたびに数を増やすので、
  // 同じ日に2度目の追記があっても見分けられる。seenReports を持たない判断は日付で比べ、同じ日は前後を決められないので見直しへ倒す (>=)
  function needsReview(item, doc) {
    if (!decided(doc) || !item.appended) return false;
    // 今より多い数は新しい版のページが書いたもの。古い版で開いても見直しに出さない
    if (typeof doc.seenReports === "number") return doc.seenReports < reportsOf(item);
    const day = localDate(doc.decidedAt ?? doc.updatedAt);
    return day !== "" && item.appended >= day;
  }

  function inDefaultList(item, doc, clauses) {
    if (needsReview(item, doc)) return true;
    if (decided(doc)) return false;
    return clauses.length === 0 || promoted(item, clauses);
  }

  function bulkTargets(selectedIds, decisionOf) {
    const apply = [], skipped = [];
    for (const id of new Set(selectedIds)) (decisionOf(id) ? skipped : apply).push(id);
    return { apply, skipped };
  }

  const undoTargets = lastBulk => (lastBulk && Array.isArray(lastBulk.apply) ? lastBulk.apply.slice() : []);

  // 確かめ済みは「原文に逐語で在る」ことだけを意味する。印は組み立て時に付いた item.verified を読む
  function cardGroups(item) {
    const v = item.verified || { labels_ok: [], labels_ng: [], quote_ok: false };
    const verified = [], model = [];
    const put = (list, key, value) => {
      if (value !== undefined && value !== null && value !== "") list.push({ key, value });
    };
    put(verified, "issue", item.issue);
    put(verified, "section", item.section);
    put(verified, "added", item.added);
    put(verified, "appended", item.appended);
    for (const lb of v.labels_ok || []) put(verified, "label", lb);
    const covered = item.covered || {};
    put(v.quote_ok ? verified : model, "quote", covered.quote);
    for (const lb of v.labels_ng || []) put(model, "label", lb);
    put(model, "summary", item.summary);
    put(model, "recommendation", item.recommendation);
    put(model, "reason", item.reason);
    put(model, "placement", item.placement);
    put(model, "placement_detail", item.placement_detail);
    put(model, "covered_status", covered.status);
    put(model, "report_count", item.report_count);
    if (item.version_dependent === true) model.push({ key: "version_dependent", value: true });
    return { verified, model };
  }

  const conditionCounts = (items, clauses) =>
    clauses.map(c => items.reduce((n, it) => n + (clauseMatches(it, c) ? 1 : 0), 0));

  return { BASE_DATE, PRED_KINDS, reportsOf, parseConditions, promoted, localDate, needsReview, inDefaultList, bulkTargets, undoTargets, cardGroups, conditionCounts };
})();

if (typeof module !== "undefined") module.exports = LedgerLogic;
