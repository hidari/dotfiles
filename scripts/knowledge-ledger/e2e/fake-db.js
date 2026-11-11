// claude.ai が差し込む window.claude の偽物。メモリ上の保存先を持つ。
// 設定は addInitScript が window.__fakeSeed で渡す:
//   { docs: { <collection>: { <id>: <fields> } }, delayDecisions: boolean, throwSettings: boolean }
// 書き込みは window.__writes に { op, path, fields } で積む。
// 別の端末からの書き込みは window.__remoteUpdate で入れ (__writes には積まない)、購読の切断は window.__failSnapshot で起こす
(() => {
  const seed = window.__fakeSeed || {};
  const store = new Map();
  const listeners = new Map();
  window.__writes = [];

  const bucket = name => { if (!store.has(name)) store.set(name, new Map()); return store.get(name); };
  for (const [name, docs] of Object.entries(seed.docs || {})) {
    for (const [id, fields] of Object.entries(docs)) bucket(name).set(id, structuredClone(fields));
  }

  const snapshot = name => ({
    metadata: { fromCache: false },
    docs: [...bucket(name)].map(([id, fields]) => ({ id, data: () => structuredClone(fields) })),
  });

  // 最初の decisions の届きだけを、テストが放すまで止める
  let release = null;
  const held = seed.delayDecisions ? new Promise(r => { release = r; }) : null;
  window.__releaseDecisions = () => release && release();

  const notify = name => { for (const cb of listeners.get(name) || []) cb(snapshot(name)); };
  window.__remoteUpdate = (name, id, fields) => { bucket(name).set(id, { ...(bucket(name).get(id) || {}), ...structuredClone(fields) }); notify(name); };
  // 購読が切れたことを伝える (onSnapshot の第2引数を呼ぶ)
  const errorCbs = new Map();
  window.__failSnapshot = (name, code) => { for (const cb of errorCbs.get(name) || []) cb({ code }); };

  const collection = name => ({
    doc: id => ({
      async get() { const f = bucket(name).get(id); return { exists: !!f, id, data: () => structuredClone(f) }; },
      async set(fields) {
        window.__writes.push({ op: "set", path: name + "/" + id, fields: structuredClone(fields) });
        bucket(name).set(id, structuredClone(fields)); notify(name);
      },
      async update(fields) {
        window.__writes.push({ op: "update", path: name + "/" + id, fields: structuredClone(fields) });
        bucket(name).set(id, { ...(bucket(name).get(id) || {}), ...structuredClone(fields) }); notify(name);
      },
    }),
    onSnapshot(cb, onError) {
      // 購読の呼び出しそのものが同期で投げる保存先を真似る
      if (name === "settings" && seed.throwSettings) throw Object.assign(new Error("settings"), { code: "internal" });
      if (!listeners.has(name)) listeners.set(name, []);
      listeners.get(name).push(cb);
      if (onError) { if (!errorCbs.has(name)) errorCbs.set(name, []); errorCbs.get(name).push(onError); }
      const first = () => cb(snapshot(name));
      if (name === "decisions" && held) held.then(first); else queueMicrotask(first);
      return () => {};
    },
  });

  window.claude = {
    use: async name => {
      if (name === "db") return { collection };
      if (name === "user") return { can: async () => true };
      return null;
    },
  };
})();
