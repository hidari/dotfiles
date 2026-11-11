(() => {
  const ITEMS = JSON.parse(document.getElementById("data").textContent);
  const byId = new Map(ITEMS.map(i => [i.id, i]));
  const BASE_DATE = "2026-11-04";
  const PER = 25;
  const LS_UI = "ledger.ui.v1", LS_PENDING = "ledger.pending.v1";
  const $ = s => document.getElementById(s);

  // 保存先が返した判断 (confirmed) と、まだ届いていない手元の変更 (pending) を分けて持つ。
  // 表示は pending を confirmed に重ねたもの。保存先の古いスナップショットが手元の変更を消さない
  const confirmed = new Map();
  const pending = new Map();
  const failed = new Set();
  const busy = new Set(), dirty = new Set();
  const sticky = new Set();
  let db = null, canWrite = true, live = false, page = 0, shownStage = 0;

  const ls = {
    get(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (_) { return null; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} },
  };
  const view = id => ({ ...(confirmed.get(id) || {}), ...(pending.get(id) || {}) });
  const decisionOf = id => view(id).decision || null;
  const persistPending = () => ls.set(LS_PENDING, Object.fromEntries(pending));

  // 前回の訪問で届かなかった変更を戻す
  for (const [id, p] of Object.entries(ls.get(LS_PENDING) || {})) if (byId.has(id) && p && p.updatedAt) pending.set(id, p);

  const text = (el, t) => { el.textContent = t; return el; };
  const mk = (tag, cls, t) => { const e = document.createElement(tag); if (cls) e.className = cls; if (t != null) e.textContent = t; return e; };
  const addedOf = i => i.added || BASE_DATE;

  // 絞り込みの選択肢は台帳のデータから作る
  const uniq = f => [...new Set(ITEMS.map(f))];
  for (const v of uniq(i => i.issue)) $("f-issue").append(new Option(v, v));
  for (const v of uniq(addedOf).sort().reverse()) $("f-added").append(new Option(v === BASE_DATE ? v + " (最初の578件)" : v + " に追加", v));
  const fillSections = () => {
    const iss = $("f-issue").value, sel = $("f-section"), cur = sel.value;
    sel.length = 1;
    for (const v of [...new Set(ITEMS.filter(i => !iss || i.issue === iss).map(i => i.section))]) sel.append(new Option(v, v));
    sel.value = [...sel.options].some(o => o.value === cur) ? cur : "";
  };

  // 絞り込みと開いていたページをこのブラウザに覚える
  const UI_FIELDS = ["f-state", "f-issue", "f-section", "f-rec", "f-cov", "f-added", "f-sort", "f-q"];
  const saveUi = () => ls.set(LS_UI, { ...Object.fromEntries(UI_FIELDS.map(k => [k, $(k).value])), page });
  const restoreUi = () => {
    const u = ls.get(LS_UI);
    if (!u) { fillSections(); return; }
    const setSel = k => { const el = $(k); if (u[k] == null) return; if (el.tagName !== "SELECT" || [...el.options].some(o => o.value === u[k])) el.value = u[k]; };
    setSel("f-issue"); fillSections();
    for (const k of UI_FIELDS) if (k !== "f-issue") setSel(k);
    page = Number.isInteger(u.page) && u.page >= 0 ? u.page : 0;
  };
  restoreUi();

  function filtered() {
    const st = $("f-state").value, iss = $("f-issue").value, sec = $("f-section").value, rec = $("f-rec").value, cov = $("f-cov").value, add = $("f-added").value;
    const q = $("f-q").value.trim().toLowerCase();
    let r = ITEMS.filter(i => {
      const d = decisionOf(i.id);
      if (!sticky.has(i.id)) {
        if (st === "todo" && d) return false;
        if (st && st !== "todo" && d !== st) return false;
      }
      if (iss && i.issue !== iss) return false;
      if (sec && i.section !== sec) return false;
      if (rec && i.recommendation !== rec) return false;
      if (cov && (i.covered?.status || "none") !== cov) return false;
      if (add && addedOf(i) !== add) return false;
      if (q && !(i.summary + "\n" + i.text + "\n" + (i.placement_detail || "") + "\n" + i.id).toLowerCase().includes(q)) return false;
      return true;
    });
    if ($("f-sort").value === "rep") r = r.slice().sort((a, b) => (b.report_count || 1) - (a.report_count || 1) || a.order - b.order);
    return r;
  }

  function tallies() {
    let a = 0, h = 0, rj = 0;
    for (const i of ITEMS) { const d = decisionOf(i.id); if (d === "採る") a++; else if (d === "保留") h++; else if (d === "採らない") rj++; }
    const done = a + h + rj, n = ITEMS.length;
    text($("t-done"), done); text($("t-a"), a); text($("t-h"), h); text($("t-r"), rj); text($("t-left"), n - done);
    $("b-a").style.width = (a / n * 100) + "%"; $("b-h").style.width = (h / n * 100) + "%"; $("b-r").style.width = (rj / n * 100) + "%";
    const u = pending.size;
    text($("unsaved"), u ? "保存先へ届いていない判断 " + u + " 件 (このブラウザに控えてあります)" : "");
    $("unsaved").className = u && failed.size ? "warn" : "";
    $("retry").hidden = !(failed.size && db && canWrite);
  }

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const RETRYABLE = new Set(["unavailable", "resource_exhausted"]);
  async function writeOnce(id, patch) {
    const ref = db.collection("decisions").doc(id);
    const body = { decision: patch.decision !== undefined ? patch.decision : (confirmed.get(id)?.decision ?? null), note: patch.note !== undefined ? patch.note : (confirmed.get(id)?.note ?? ""), updatedAt: patch.updatedAt };
    if (confirmed.has(id)) {
      // 既存の文書は変えた欄だけを merge する。古い手元の値で他の欄を上書きしない
      const fields = { updatedAt: patch.updatedAt };
      if (patch.decision !== undefined) fields.decision = patch.decision;
      if (patch.note !== undefined) fields.note = patch.note;
      try { await ref.update(fields); return { ...confirmed.get(id), ...fields }; }
      catch (e) { if (!(e && e.code === "invalid_argument")) throw e; }
    }
    await ref.set(body);
    return body;
  }
  async function flush(id) {
    if (!db || !canWrite || !live) return;
    if (busy.has(id)) { dirty.add(id); return; }
    busy.add(id); paint(id);
    try {
      do {
        dirty.delete(id);
        const patch = pending.get(id);
        if (!patch) break;
        let saved = null, err = null;
        for (const wait of [0, 1000, 3000, 8000]) {
          if (wait) await sleep(wait + Math.floor(wait * Math.random() * 0.3));
          try { saved = await writeOnce(id, patch); err = null; break; }
          catch (e) { err = e; if (!(e && RETRYABLE.has(e.code))) break; }
        }
        if (err) {
          failed.add(id);
          if (err.code === "invalid_argument" || err.code === "not_granted" || err.code === "revoked") { canWrite = false; status("この表示では判断を書き込めません。控えはこのブラウザに残しています。", true); }
          break;
        }
        const cur = confirmed.get(id);
        if (!cur || (saved.updatedAt || "") >= (cur.updatedAt || "")) confirmed.set(id, saved);
        if (pending.get(id) === patch) pending.delete(id);
        failed.delete(id);
      } while (dirty.has(id));
    } finally {
      busy.delete(id); persistPending(); paint(id); tallies();
    }
  }
  const flushAll = () => { for (const id of [...pending.keys()]) flush(id); };

  function change(id, patch) {
    pending.set(id, { ...(pending.get(id) || {}), ...patch, updatedAt: new Date().toISOString() });
    persistPending();
    paint(id); tallies();
    flush(id);
  }

  const cards = new Map();
  function savedText(id) {
    if (pending.has(id)) {
      if (busy.has(id)) return ["保存しています…", false];
      if (failed.has(id)) return ["保存先へ届いていません。このブラウザに控えてあり、上のボタンか次に開いたときに送り直します", true];
      return [db ? "保存の順番待ちです" : "保存先に接続できていません。このブラウザに控えてあります", !db];
    }
    const t = confirmed.get(id)?.updatedAt;
    return [t ? "保存済み " + new Date(t).toLocaleString("ja-JP", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "", false];
  }
  function paint(id) {
    const c = cards.get(id);
    if (!c || !c.el.isConnected) return;
    const v = view(id), d = v.decision || null, i = byId.get(id);
    c.el.dataset.d = d || "";
    text(c.dl, d ? "判断: " + d : "判断: まだ");
    for (const b of c.btns) { b.setAttribute("aria-pressed", String(b.dataset.v === d)); b.disabled = !canWrite; }
    c.undo.disabled = !canWrite || !d;
    c.ta.disabled = !canWrite;
    if (document.activeElement !== c.ta && !(pending.get(id)?.note !== undefined && busy.has(id))) c.ta.value = v.note || "";
    const [t, warn] = savedText(id);
    text(c.saved, t); c.saved.className = "saved" + (warn ? " warn" : "");
    const after = i.appended && d && (confirmed.get(id)?.updatedAt || "").slice(0, 10) < i.appended;
    c.after.hidden = !after;
  }

  function card(i) {
    const c = mk("article", "card");
    const meta = mk("div", "cid");
    const dl = mk("span", "dlabel");
    meta.append(mk("span", null, i.id), mk("span", null, i.issue + " ・ " + i.section), dl);
    c.append(meta, mk("p", "summary", i.summary || "(要約なし)"));
    const chips = mk("div", "chips");
    if (i.added && i.added !== BASE_DATE) chips.append(mk("span", "chip new", i.added + " に追加"));
    if (i.appended) chips.append(mk("span", "chip new", i.appended + " に追記あり"));
    const after = mk("span", "chip after", "判断の後に報告が追記された"); after.hidden = true; chips.append(after);
    for (const l of (i.labels || [])) chips.append(mk("span", "chip", l));
    if ((i.report_count || 1) > 1) chips.append(mk("span", "chip rep", "届いた報告 " + i.report_count + " 件"));
    const cs = i.covered?.status || "none";
    chips.append(mk("span", "chip cov-" + cs, cs === "covered" ? "既存の規範にある" : cs === "partial" ? "既存の規範に一部ある" : "既存の規範に無い"));
    if (i.placement) chips.append(mk("span", "chip", "置き場の案: " + i.placement));
    if (i.version_dependent) chips.append(mk("span", "chip ver", "版に依存"));
    c.append(chips);
    const mine = mk("div", "mine");
    mine.append(mk("b", null, "見立て: " + (i.recommendation || "-")), document.createTextNode("　" + (i.reason || "")));
    if (i.placement_detail) mine.append(mk("div", "path", i.placement_detail));
    c.append(mine);
    const det = mk("details"); det.append(mk("summary", null, "原文"), mk("pre", null, i.text + (i.basis ? "\n\n根拠: " + i.basis : "") + (i.reports && i.reports.length ? "\n\n" + i.reports.map(r => r.text).join("\n") : "")));
    c.append(det);
    if (i.covered && i.covered.quote) {
      const q = mk("details"); q.append(mk("summary", null, "既存の規範の該当箇所"), mk("div", "path", i.covered.path || ""), mk("p", "quote", i.covered.quote));
      c.append(q);
    } else if (i.covered && i.covered.searched && i.covered.searched.length) {
      c.append(mk("div", "path", "探した語: " + i.covered.searched.join("、")));
    }
    const dec = mk("div", "decide");
    const btnBox = mk("div", "btns"); btnBox.setAttribute("role", "group"); btnBox.setAttribute("aria-label", i.id + " の判断");
    const btns = [];
    for (const v of ["採る", "保留", "採らない"]) {
      const bt = mk("button", null, v); bt.type = "button"; bt.dataset.v = v;
      // 押し直しで外れる作りだと二度押しで判断が消えるので、選び直すだけにする
      bt.addEventListener("click", () => { if (decisionOf(i.id) !== v) { sticky.add(i.id); change(i.id, { decision: v }); } });
      btns.push(bt); btnBox.append(bt);
    }
    const undo = mk("button", "undo", "取り消す"); undo.type = "button";
    undo.addEventListener("click", () => { if (decisionOf(i.id)) { sticky.add(i.id); change(i.id, { decision: null }); } });
    btnBox.append(undo);
    const ta = mk("textarea"); ta.id = "note-" + i.id; ta.placeholder = "メモ (理由、置き場の指定など)";
    ta.setAttribute("aria-label", i.id + " のメモ");
    let tm = null;
    const commitNote = () => { clearTimeout(tm); if ((view(i.id).note || "") !== ta.value) change(i.id, { note: ta.value }); };
    ta.addEventListener("input", () => { clearTimeout(tm); tm = setTimeout(commitNote, 900); });
    ta.addEventListener("blur", commitNote);
    const saved = mk("div", "saved");
    dec.append(btnBox, ta, saved);
    c.append(dec);
    cards.set(i.id, { el: c, dl, btns, undo, ta, saved, after });
    paint(i.id);
    return c;
  }

  function render() {
    const r = filtered();
    const pages = Math.max(1, Math.ceil(r.length / PER));
    if (page >= pages) page = pages - 1;
    const list = $("list"); list.replaceChildren(); cards.clear();
    const slice = r.slice(page * PER, page * PER + PER);
    if (!slice.length) list.append(mk("p", "empty", "条件に合う知見はありません"));
    for (const i of slice) list.append(card(i));
    text($("count"), r.length + " 件 (全 " + ITEMS.length + " 件)");
    text($("pageinfo"), (page + 1) + " / " + pages);
    $("prev").disabled = page === 0; $("next").disabled = page >= pages - 1;
    tallies(); saveUi();
  }
  const repaintAll = () => { for (const id of cards.keys()) paint(id); tallies(); };
  const resetView = () => { sticky.clear(); page = 0; render(); };

  for (const id of ["f-state", "f-section", "f-rec", "f-cov", "f-added", "f-sort"]) $(id).addEventListener("change", resetView);
  $("f-issue").addEventListener("change", () => { fillSections(); resetView(); });
  let qt = null; $("f-q").addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(resetView, 250); });
  $("prev").addEventListener("click", () => { sticky.clear(); page--; render(); window.scrollTo({ top: 0 }); });
  $("next").addEventListener("click", () => { sticky.clear(); page++; render(); window.scrollTo({ top: 0 }); });
  $("retry").addEventListener("click", () => { failed.clear(); tallies(); flushAll(); });
  window.addEventListener("online", () => { if (failed.size) { failed.clear(); flushAll(); } });
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") persistPending(); });

  function status(t, warn) { const s = $("status"); text(s, t); s.className = warn ? "warn" : ""; }

  render();

  (async () => {
    const api = window.claude && typeof window.claude.use === "function" ? window.claude : null;
    db = api ? await api.use("db") : null;
    if (!db) { canWrite = false; status("判断の保存先に接続できないため、閲覧だけできます。claude.ai でこのページを開くと判断を記録できます。", true); repaintAll(); return; }
    const user = await api.use("user");
    try { const w = user ? await user.can("data.write") : null; if (w === false) canWrite = false; } catch (_) {}
    const timer = setTimeout(() => status("保存先からの応答がまだありません。表示中の判断は古いかもしれません。押した判断はこのブラウザに控えます。", true), 10000);
    db.collection("decisions").onSnapshot(snap => {
      const fresh = !snap.metadata.fromCache;
      const seen = new Set();
      for (const doc of snap.docs) {
        if (!byId.has(doc.id)) continue;
        seen.add(doc.id);
        const v = doc.data(), cur = confirmed.get(doc.id);
        // 新しい方を残す。届く順が前後しても、確定済みの書き込みを古い版で巻き戻さない
        if (!cur || (v.updatedAt || "") >= (cur.updatedAt || "")) confirmed.set(doc.id, v);
      }
      if (fresh) for (const id of [...confirmed.keys()]) if (!seen.has(id) && !busy.has(id)) confirmed.delete(id);
      // 保存先の方が新しい判断を持っていれば、手元の古い控えは捨てる
      for (const [id, p] of [...pending]) { const c = confirmed.get(id); if (c && (c.updatedAt || "") > p.updatedAt && !busy.has(id)) pending.delete(id); }
      if (fresh) {
        clearTimeout(timer);
        if (canWrite) status("判断は保存先に自動で記録されます。", false); else status("この表示では閲覧だけできます。", false);
        if (!live) { live = true; flushAll(); }
      }
      persistPending();
      // 判断が届く前の一覧は絞り込みが効いていないので、最初の届きと最初の確定で組み直す。
      // それ以降は入力中のメモを壊さないよう、表示中のカードを塗り直すだけにする
      const stage = fresh ? 2 : 1;
      if (stage > shownStage && !(document.activeElement && document.activeElement.tagName === "TEXTAREA")) { shownStage = stage; render(); }
      else repaintAll();
    }, e => { clearTimeout(timer); live = false; status("保存先との接続が切れました (" + (e && e.code) + ")。押した判断はこのブラウザに控え、開き直したときに送り直します。", true); repaintAll(); });
  })();
})();
