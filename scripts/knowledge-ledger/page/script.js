(() => {
  const ITEMS = JSON.parse(document.getElementById("data").textContent);
  const byId = new Map(ITEMS.map(i => [i.id, i]));
  const PER = 25;
  const LS_UI = "ledger.ui.v1", LS_PENDING = "ledger.pending.v1";
  const $ = s => document.getElementById(s);

  // 保存先が返した判断 (confirmed) と、まだ届いていない手元の変更 (pending) を分けて持つ。
  // 表示は pending を confirmed に重ねたもの。保存先の古いスナップショットが手元の変更を消さない
  const confirmed = new Map();
  const pending = new Map();
  const failed = new Set();
  const busy = new Set(), dirty = new Set();
  // 前回の同期の後に打たれた (input があった) メモ欄。打っていない欄はフォーカスを外しても書かない
  const noteDirty = new WeakSet();
  const sticky = new Set();
  let db = null, canWrite = true, page = 0, shownStage = 0;
  // 購読ごとの状態。seen はキャッシュでない届きが一度でもあったか (文書が無い届きも含み、戻さない)、
  // live は今つながっているか、err は購読そのものが失敗したか (条件の側だけが立て、戻さない)。
  // 判断の側の切断は live を落とすだけにする。押した判断は控えて送り直すので、カードは切断後も押せる
  const src = { decisions: { seen: false, live: false, err: false }, settings: { seen: false, live: false, err: false } };
  // 書いてよい: 保存先の値を一度は見た。届く前に書くと、まだ見ていない保存済みの値を上書きする
  const canAuthor = s => canWrite && s.seen && !s.err;
  // 今送ってよい: さらにつながっている。切断後は確定済みの値が古いかもしれない
  const canSend = s => canAuthor(s) && s.live;
  const canEditCond = () => canSend(src.decisions) && canAuthor(src.settings);
  const L = LedgerLogic, BASE_DATE = L.BASE_DATE, addedOf = L.addedOf;
  // 保存先から読んだ昇格の条件 (一覧の絞りに効く) と、編集中の写し
  const COND_DOC = ["settings", "promotion"];
  const stored = { clauses: [], warnings: [], updatedAt: "" };
  let draft = [], draftDirty = false, condBusy = false;
  // まとめての判断: 選択は絞り込みやページ送りをまたいで残し、取り消しは直前の1回だけ
  const selected = new Set();
  let lastBulk = null;

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
  const saveUi = () => ls.set(LS_UI, { ...Object.fromEntries(UI_FIELDS.map(k => [k, $(k).value])), stored: $("show-stored").checked, page });
  const restoreUi = () => {
    const u = ls.get(LS_UI);
    if (!u) { fillSections(); return; }
    const setSel = k => { const el = $(k); if (u[k] == null) return; if (el.tagName !== "SELECT" || [...el.options].some(o => o.value === u[k])) el.value = u[k]; };
    setSel("f-issue"); fillSections();
    for (const k of UI_FIELDS) if (k !== "f-issue") setSel(k);
    $("show-stored").checked = u.stored === true;
    page = Number.isInteger(u.page) && u.page >= 0 ? u.page : 0;
  };
  restoreUi();

  function filtered() {
    const st = $("f-state").value, iss = $("f-issue").value, sec = $("f-section").value, rec = $("f-rec").value, cov = $("f-cov").value, add = $("f-added").value;
    const q = $("f-q").value.trim().toLowerCase();
    const showStored = $("show-stored").checked;
    let r = ITEMS.filter(i => {
      const doc = view(i.id), d = doc.decision || null;
      if (!sticky.has(i.id)) {
        // 既定の一覧は昇格した未判断の件と、判断の後に追記があった件。保管中も含めるときは未判断の全件
        if (st === "todo" && !(showStored ? (L.needsReview(i, doc) || !d) : L.inDefaultList(i, doc, stored.clauses))) return false;
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
    if ($("f-sort").value === "rep") r = r.slice().sort((a, b) => L.reportsOf(b) - L.reportsOf(a) || a.order - b.order);
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
    $("retry").hidden = !(failed.size && canWrite);
    paintChrome();
  }

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const RETRYABLE = new Set(["unavailable", "resource_exhausted"]);
  // 書く欄はこの4つと updatedAt だけ。前の版の控えや文書が持つ欄 (seenAppended など) は送らない。
  // decidedAt は判断を変えたときと「このままでよい」のときだけ patch に載る
  const WRITTEN = ["decision", "note", "decidedAt", "seenReports"];
  const written = o => Object.fromEntries(WRITTEN.filter(k => o && o[k] !== undefined).map(k => [k, o[k]]));
  async function writeOnce(id, patch) {
    const ref = db.collection("decisions").doc(id);
    const fields = { ...written(patch), updatedAt: patch.updatedAt };
    if (confirmed.has(id)) {
      // 既存の文書は変えた欄だけを merge する。古い手元の値で他の欄を上書きしない
      try { await ref.update(fields); return { ...confirmed.get(id), ...fields }; }
      catch (e) { if (!(e && e.code === "invalid_argument")) throw e; }
    }
    // 判断とメモは null の値も既定へ寄せる (?? と同じ)
    const body = { ...written(confirmed.get(id)), ...fields };
    body.decision ??= null; body.note ??= "";
    await ref.set(body);
    return body;
  }
  async function flush(id) {
    if (!canSend(src.decisions)) return;
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
          if (err.code === "invalid_argument" || err.code === "not_granted" || err.code === "revoked") { canWrite = false; status("この表示では判断を書き込めません。控えはこのブラウザに残しています。", true); paintCond(); }
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

  // 書き込みの入口。判断が一度も届いていなければ何もしない (false を返す)
  function change(id, patch) {
    if (!src.decisions.seen) return false;
    const now = new Date().toISOString();
    // 判断を変えたときだけ decidedAt が進む。メモだけの保存では進めない。
    // 「このままでよい」は呼び出し側が decidedAt だけを渡す
    // 同じときに、見た時点の届いた報告の数 (seenReports) も記録する
    const stamp = patch.decision !== undefined || patch.decidedAt !== undefined;
    const decidedAt = patch.decision !== undefined ? { decidedAt: now } : {};
    const seen = stamp ? { seenReports: L.reportsOf(byId.get(id)) } : {};
    pending.set(id, { ...(pending.get(id) || {}), ...patch, ...decidedAt, ...seen, updatedAt: now });
    persistPending();
    paint(id); tallies();
    flush(id);
    return true;
  }
  // 押した件は絞り込みから外れても組み直すまで一覧に残す
  const commit = (id, patch) => { if (change(id, patch)) sticky.add(id); };
  const typing = () => !!document.activeElement && document.activeElement.tagName === "TEXTAREA";

  const KEY_LABEL = { issue: "Issue", section: "分野", added: "載った日", appended: "追記の日", label: "札", quote: "既存の規範の引用", summary: "要約", recommendation: "見立て", reason: "理由", placement: "置き場の案", placement_detail: "置き場の詳細", covered_status: "既存の規範", report_count: "届いた報告", version_dependent: "版への依存" };
  const COV_LABEL = { covered: "既にある", partial: "一部ある", none: "無い" };
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
    // 判断が一度も届いていない間は「まだ」が未確認なので押させない。一括と違い切断後も押せる (控えて送り直す)
    const usable = canAuthor(src.decisions);
    for (const b of c.btns) { b.setAttribute("aria-pressed", String(b.dataset.v === d)); b.disabled = !usable; }
    c.undo.disabled = !usable || !d;
    c.ta.disabled = !usable;
    if (document.activeElement !== c.ta && !(pending.get(id)?.note !== undefined && busy.has(id))) { c.ta.value = v.note || ""; noteDirty.delete(c.ta); }
    const [t, warn] = savedText(id);
    text(c.saved, t); c.saved.className = "saved" + (warn ? " warn" : "");
    const review = L.needsReview(i, v);
    c.after.hidden = !review;
    c.ack.hidden = !review; c.ack.disabled = !canSend(src.decisions);
    // 昇格の条件に当てはまらない未判断の件は保管中。「採らない」と読める表示にしない
    c.stored.hidden = !(!d && !review && stored.clauses.length > 0 && !L.promoted(i, stored.clauses));
    c.sel.checked = selected.has(id);
  }

  function card(i) {
    const c = mk("article", "card");
    const meta = mk("div", "cid");
    const dl = mk("span", "dlabel");
    const pick = mk("label", "pick");
    const sel = mk("input"); sel.type = "checkbox"; sel.setAttribute("data-select", i.id); sel.setAttribute("aria-label", i.id + " を選ぶ");
    sel.addEventListener("change", () => { if (sel.checked) selected.add(i.id); else selected.delete(i.id); paintChrome(); });
    pick.append(sel, document.createTextNode("選ぶ"));
    meta.append(pick, mk("span", null, i.id), dl);
    c.append(meta);
    const chips = mk("div", "chips");
    const storedChip = mk("span", "chip stored", "保管中 (判断していない)"); storedChip.hidden = true; chips.append(storedChip);
    const after = mk("span", "chip after", "判断の後に報告が追記された"); after.hidden = true; chips.append(after);
    const ack = mk("button", "ack", "このままでよい"); ack.type = "button"; ack.hidden = true;
    // 判断が届く前は confirmed に件が無く、書くと set で既存の判断を null で上書きしうるので、確定済みの判断がある件だけ通す
    ack.addEventListener("click", () => { if (canSend(src.decisions) && confirmed.get(i.id)?.decision && L.needsReview(i, view(i.id))) commit(i.id, { decidedAt: new Date().toISOString() }); });
    chips.append(ack);
    c.append(chips);
    const groups = L.cardGroups(i);
    for (const [cls, title, entries] of [["verified", "原文に在る", groups.verified], ["model", "モデルの判断", groups.model]]) {
      if (!entries.length) continue;
      const g = mk("section", "grp " + cls); g.setAttribute("aria-label", title);
      g.append(mk("h3", null, title));
      for (const e of entries) {
        const row = mk("div", "row" + (e.key === "summary" ? " summary-row" : ""));
        row.append(mk("span", "k", KEY_LABEL[e.key] || e.key), mk("span", "v", e.key === "covered_status" ? COV_LABEL[e.value] || e.value : e.key === "report_count" ? e.value + " 件" : e.key === "version_dependent" ? "あり" : e.value));
        g.append(row);
        if (e.key === "quote" && i.covered && i.covered.path) g.append(mk("div", "path", i.covered.path));
      }
      c.append(g);
    }
    const det = mk("details"); det.append(mk("summary", null, "原文"), mk("pre", null, i.text + (i.basis ? "\n\n根拠: " + i.basis : "") + (i.reports && i.reports.length ? "\n\n" + i.reports.map(r => r.text).join("\n") : "")));
    c.append(det);
    if (!(i.covered && i.covered.quote) && i.covered && i.covered.searched && i.covered.searched.length) {
      c.append(mk("div", "path", "探した語: " + i.covered.searched.join("、")));
    }
    const dec = mk("div", "decide");
    const btnBox = mk("div", "btns"); btnBox.setAttribute("role", "group"); btnBox.setAttribute("aria-label", i.id + " の判断");
    const btns = [];
    for (const v of ["採る", "保留", "採らない"]) {
      const bt = mk("button", null, v); bt.type = "button"; bt.dataset.v = v;
      // 押し直しで外れる作りだと二度押しで判断が消えるので、選び直すだけにする
      bt.addEventListener("click", () => { if (decisionOf(i.id) !== v) commit(i.id, { decision: v }); });
      btns.push(bt); btnBox.append(bt);
    }
    const undo = mk("button", "undo", "取り消す"); undo.type = "button";
    undo.addEventListener("click", () => { if (decisionOf(i.id)) commit(i.id, { decision: null }); });
    btnBox.append(undo);
    const ta = mk("textarea"); ta.id = "note-" + i.id; ta.placeholder = "メモ (理由、置き場の指定など)";
    ta.setAttribute("aria-label", i.id + " のメモ");
    let tm = null;
    // 打った (input があった) ときだけ書く。打たずに外したときは、フォーカス中に届いたメモを上書きせず保存先の値へ戻す
    const commitNote = () => {
      clearTimeout(tm);
      if (!noteDirty.has(ta)) { ta.value = view(i.id).note || ""; return; }
      noteDirty.delete(ta);
      if ((view(i.id).note || "") !== ta.value) change(i.id, { note: ta.value });
    };
    ta.addEventListener("input", () => { noteDirty.add(ta); clearTimeout(tm); tm = setTimeout(commitNote, 900); });
    ta.addEventListener("blur", commitNote);
    const saved = mk("div", "saved");
    dec.append(btnBox, ta, saved);
    c.append(dec);
    cards.set(i.id, { el: c, dl, btns, undo, ta, saved, after, ack, stored: storedChip, sel });
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
    // card() の中では list に繋がる前なので paint が何もしない。繋がった後に塗る
    for (const i of slice) paint(i.id);
    text($("count"), r.length + " 件 (全 " + ITEMS.length + " 件)");
    text($("pageinfo"), (page + 1) + " / " + pages);
    $("prev").disabled = page === 0; $("next").disabled = page >= pages - 1;
    // 「判断がまだの全件」が実際に出ているときだけ言う
    $("cond-none").hidden = stored.clauses.length > 0 || $("f-state").value !== "todo" || $("show-stored").checked;
    tallies(); saveUi();
  }
  const repaintAll = () => { for (const id of cards.keys()) paint(id); tallies(); };
  const resetView = () => { sticky.clear(); page = 0; render(); };

  for (const id of ["f-state", "f-section", "f-rec", "f-cov", "f-added", "f-sort", "show-stored"]) $(id).addEventListener("change", resetView);
  $("f-issue").addEventListener("change", () => { fillSections(); resetView(); });
  let qt = null; $("f-q").addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(resetView, 250); });
  $("prev").addEventListener("click", () => { sticky.clear(); page--; render(); window.scrollTo({ top: 0 }); });
  $("next").addEventListener("click", () => { sticky.clear(); page++; render(); window.scrollTo({ top: 0 }); });
  $("retry").addEventListener("click", () => { failed.clear(); tallies(); flushAll(); });
  window.addEventListener("online", () => { if (failed.size) { failed.clear(); flushAll(); } });
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") persistPending(); });


  // 昇格の条件の編集。述語の組と選択肢の文言は logic.js の PRED_KINDS が持つ
  const kindOf = p => L.PRED_KINDS.find(k => k.kind === p.field + ":" + p.op);
  const newPred = () => ({ field: "issue", op: "eq", value: "", negate: false });
  const clone = v => JSON.parse(JSON.stringify(v));
  const datalist = (id, values) => { const d = mk("datalist"); d.id = id; for (const v of values) d.append(new Option(v, v)); return d; };

  // 入力 (編集中の写し・保存済みの条件・購読の状態・書ける権限・condBusy) が変わったときだけ呼ぶ
  function paintCond() {
    const editable = canEditCond(), w = editable && !condBusy;
    const ed = $("cond-editor");
    for (const el of ed.querySelectorAll("select, input, button")) el.disabled = !editable;
    const issues = draftIssues();
    $("cond-add").disabled = !w; $("cond-save").disabled = !w || !draftDirty || issues.length > 0;
    // 編集中の写しは1回の塗りで1度だけ読む
    const clauses = L.parseConditions({ clauses: draft }).clauses;
    const counts = L.conditionCounts(ITEMS, clauses);
    ed.querySelectorAll("[data-count]").forEach((el, n) => text(el, "該当 " + (counts[n] ?? 0) + " 件"));
    // 保存済みの空の節は stored.warnings と draftIssues の両方に同じ文言で出るので重ねない
    const warn = [...new Set([...stored.warnings, ...issues])];
    text($("cond-warn"), warn.length ? warn.join(" / ") : "");
    const total = draft.length ? "いずれかの節に当てはまる件: " + ITEMS.filter(it => L.promoted(it, clauses)).length + " 件" : "";
    if (!$("cond-msg").dataset.keep) text($("cond-msg"), (editable ? "" : "この表示では条件を編集できません。") + (draftDirty ? "未保存の変更があります。" : "") + total);
  }
  // 値がまだ入っていない述語と、使えない述語を分けて言う。どちらも保存は止める
  function draftIssues() {
    const out = [];
    draft.forEach((cl, ci) => {
      // 述語の無い節は何も昇格させないので保存させない (文言は parseConditions の警告と同じ)
      if (!cl.preds.length) out.push("節 " + (ci + 1) + " に述語が無い");
      cl.preds.forEach((p, pi) => {
        const k = kindOf(p), at = "節 " + (ci + 1) + " の述語 " + (pi + 1);
        if (k && k.input && (p.value === "" || p.value === null || p.value === undefined)) out.push(at + " は値がまだ入っていない");
        else if (L.parseConditions({ clauses: [{ preds: [p] }] }).warnings.length) out.push(at + " は使えない述語");
      });
    });
    return out;
  }

  function renderCond() {
    const ed = $("cond-editor"); ed.replaceChildren();
    ed.append(datalist("dl-issue", uniq(i => i.issue)), datalist("dl-section", uniq(i => i.section)), datalist("dl-label", [...new Set(ITEMS.flatMap(i => i.labels || []))]));
    draft.forEach((cl, ci) => {
      const box = mk("div", "clause"); box.setAttribute("role", "group"); box.setAttribute("aria-label", "節 " + (ci + 1));
      const head = mk("div", "clause-head", "節 " + (ci + 1) + " (次を全部満たす)");
      head.append(mk("span", "hint")); head.lastChild.setAttribute("data-count", "");
      const rm = mk("button", null, "節を削除"); rm.type = "button";
      rm.addEventListener("click", () => { draft.splice(ci, 1); condEdited(true); });
      head.append(rm); box.append(head);
      cl.preds.forEach((p, pi) => {
        const row = mk("div", "pred");
        const tag = "節" + (ci + 1) + "の述語" + (pi + 1);
        const kind = mk("select"); kind.setAttribute("aria-label", tag + " の種類");
        for (const k of L.PRED_KINDS) kind.append(new Option(k.label, k.kind));
        kind.value = (kindOf(p) || L.PRED_KINDS[0]).kind;
        kind.addEventListener("change", () => { const [f, o] = kind.value.split(":"); p.field = f; p.op = o; p.value = o === "exists" ? null : ""; condEdited(true); });
        const neg = mk("label", "neg"); const cb = mk("input"); cb.type = "checkbox"; cb.checked = !!p.negate; cb.setAttribute("aria-label", tag + " の否定");
        cb.addEventListener("change", () => { p.negate = cb.checked; condEdited(false); });
        neg.append(cb, document.createTextNode("否定"));
        row.append(kind, neg);
        const k = kindOf(p);
        if (k && k.input) {
          const inp = mk("input"); inp.type = k.input; inp.value = p.value ?? ""; inp.setAttribute("aria-label", tag + " の値");
          // 文字の欄は datalist "dl-<field>" で台帳にある値を候補に出す
          if (k.input === "text") inp.setAttribute("list", "dl-" + p.field); if (k.input === "number") inp.min = "1";
          inp.addEventListener("input", () => { p.value = k.input === "number" && inp.value !== "" && Number.isFinite(Number(inp.value)) ? Number(inp.value) : inp.value; condEdited(false); });
          row.append(inp);
        }
        const del = mk("button", null, "述語を削除"); del.type = "button";
        del.addEventListener("click", () => { cl.preds.splice(pi, 1); condEdited(true); });
        row.append(del); box.append(row);
      });
      const add = mk("button", null, "述語を追加"); add.type = "button";
      add.addEventListener("click", () => { cl.preds.push(newPred()); condEdited(true); });
      box.append(add); ed.append(box);
    });
    paintCond();
  }
  // 構造が変わるときだけ組み直す。値の入力中に組み直すとフォーカスを失う
  function condEdited(structural) {
    draftDirty = true; delete $("cond-msg").dataset.keep;
    if (structural) renderCond(); else paintCond();
  }
  function applyStored(raw) {
    const r = L.parseConditions(raw);
    const changed = JSON.stringify(r.clauses) !== JSON.stringify(stored.clauses);
    stored.clauses = r.clauses; stored.warnings = r.warnings; stored.updatedAt = (raw && raw.updatedAt) || "";
    // 編集中なら写しは残し、保存済みの側の警告だけ塗り直す
    if (!draftDirty) { draft = clone(stored.clauses); renderCond(); } else paintCond();
    return changed;
  }
  $("cond-add").addEventListener("click", () => { draft.push({ preds: [newPred()] }); condEdited(true); });
  $("cond-save").addEventListener("click", async () => {
    if (!canEditCond() || condBusy) return;
    const { clauses, warnings } = L.parseConditions({ clauses: draft });
    if (warnings.length || draftIssues().length) { paintCond(); return; }
    condBusy = true; paintCond();
    const doc = { clauses, updatedAt: new Date().toISOString() };
    const msg = $("cond-msg");
    try {
      await db.collection(COND_DOC[0]).doc(COND_DOC[1]).set(doc);
      draftDirty = false; applyStored(doc);
      text(msg, "条件を保存しました。"); msg.dataset.keep = "1";
      render();
    } catch (e) {
      text(msg, "条件を保存できませんでした (" + (e && e.code) + ")。編集中の内容は残してあります。"); msg.dataset.keep = "1";
    } finally { condBusy = false; paintCond(); }
  });

  // まとめての判断。押した瞬間の選択に bulkTargets を掛け、判断済みの件は触らない
  function paintChrome() {
    const n = selected.size, w = canSend(src.decisions);
    text($("bulk-count"), n);
    for (const id of ["bulk-adopt", "bulk-hold", "bulk-reject"]) $(id).disabled = !w || n === 0;
    $("select-page").disabled = !w;
    $("bulk-clear").disabled = n === 0;
    $("bulk-undo").disabled = !w || !lastBulk;
  }
  const syncSelection = () => { for (const [id, c] of cards) c.sel.checked = selected.has(id); paintChrome(); };
  for (const b of ["bulk-adopt", "bulk-hold", "bulk-reject"]) {
    $(b).addEventListener("click", () => {
      if (!canSend(src.decisions)) return;
      const v = $(b).dataset.v;
      const { apply, skipped } = L.bulkTargets([...selected], decisionOf);
      const marks = new Map();
      for (const id of apply) { commit(id, { decision: v }); marks.set(id, view(id).decidedAt); }
      // 付ける件が無かったときは直前のまとめての判断の取り消しを残す
      if (apply.length) lastBulk = { apply, value: v, marks };
      selected.clear();
      text($("bulk-skipped"), skipped.length ? skipped.length + " 件は判断済みのため飛ばした" : "");
      text($("bulk-msg"), apply.length ? apply.length + " 件に「" + v + "」を付けた" : "付ける件がなかった");
      syncSelection();
    });
  }
  $("select-page").addEventListener("click", () => { for (const id of cards.keys()) selected.add(id); syncSelection(); });
  $("bulk-clear").addEventListener("click", () => { selected.clear(); syncSelection(); });
  $("bulk-undo").addEventListener("click", () => {
    if (!canSend(src.decisions) || !lastBulk) return;
    // 一括の後に個別に判断し直した件は、一括が付けた値と判断の時刻が違うので戻さない
    const ids = L.undoTargets(lastBulk), keep = ids.filter(id => decisionOf(id) === lastBulk.value && view(id).decidedAt === lastBulk.marks.get(id));
    for (const id of keep) commit(id, { decision: null });
    text($("bulk-skipped"), "");
    text($("bulk-msg"), keep.length + " 件を未判断へ戻した" + (ids.length > keep.length ? " (" + (ids.length - keep.length) + " 件はその後に判断を変えたため戻していない)" : ""));
    lastBulk = null; paintChrome();
  });

  function status(t, warn) { const s = $("status"); text(s, t); s.className = warn ? "warn" : ""; }
  // 購読の状態を変えたら、それを読む条件の編集を塗り直す
  const setSrc = (s, patch) => { Object.assign(s, patch); paintCond(); };

  renderCond();
  render();

  (async () => {
    const api = window.claude && typeof window.claude.use === "function" ? window.claude : null;
    db = api ? await api.use("db") : null;
    if (!db) { canWrite = false; status("判断の保存先に接続できないため、閲覧だけできます。claude.ai でこのページを開くと判断を記録できます。", true); repaintAll(); return; }
    const user = await api.use("user");
    try { const w = user ? await user.can("data.write") : null; if (w === false) canWrite = false; } catch (_) {}
    // 判断が一度も届いていなければ、カードの判断は押せないので控えるとは言わない
    const keepText = () => src.decisions.seen ? "押した判断はこのブラウザに控え、開き直したときに送り直します。" : "判断が届くまで判断とメモは押せません。";
    const timer = setTimeout(() => status("保存先からの応答がまだありません。表示中の判断は古いかもしれません。" + keepText(), true), 10000);
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
        if (!src.decisions.live) { setSrc(src.decisions, { seen: true, live: true }); flushAll(); }
      }
      persistPending();
      // 判断が届く前の一覧は絞り込みが効いていないので、最初の届きと最初の確定で組み直す。
      // それ以降は入力中のメモを壊さないよう、表示中のカードを塗り直すだけにする
      const stage = fresh ? 2 : 1;
      if (stage > shownStage && !typing()) { shownStage = stage; render(); }
      else repaintAll();
    }, e => { clearTimeout(timer); setSrc(src.decisions, { live: false }); status("保存先との接続が切れました (" + (e && e.code) + ")。" + keepText(), true); repaintAll(); });
    // 条件の購読は判断の購読の後に付ける。条件の側が同期で投げても判断は届く
    const condError = e => { text($("cond-msg"), "条件の保存先を読めませんでした (" + (e && e.code) + ")。"); $("cond-msg").dataset.keep = "1"; setSrc(src.settings, { live: false, err: true }); };
    try {
      db.collection(COND_DOC[0]).onSnapshot(snap => {
        // キャッシュの届きは見せるだけにし、届いたとは数えない。空や古いキャッシュで編集を開くと、保存で保存済みの条件を上書きする
        if (!snap.metadata.fromCache && !src.settings.live) setSrc(src.settings, { seen: true, live: true });
        const d = snap.docs.find(x => x.id === COND_DOC[1]);
        if (!d) return;
        const v = d.data();
        // 新しい方を残す。自分の保存の直後に古い版が届いても巻き戻さない
        if ((v.updatedAt || "") >= stored.updatedAt && applyStored(v) && !typing()) render();
      }, condError);
    } catch (e) { condError(e); }
  })();
})();
