// cockpit-live.js — bridges the prototype UI to the live DailyDex backend.
// Loaded as plain JS before the Babel component scripts so window.DDX exists.
(function () {
  const listeners = new Set();

  async function jget(url) {
    const r = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!r.ok) throw new Error(`${url} -> ${r.status}`);
    return r.json();
  }
  async function jpost(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw new Error(`${url} -> ${r.status}`);
    return r.json();
  }

  const DDX = {
    // Re-pull the full DD_DATA payload and notify the app to re-render.
    async reload() {
      const data = await jget("/api/cockpit-data");
      window.DD_DATA = data;
      listeners.forEach((fn) => { try { fn(data); } catch (e) {} });
      return data;
    },
    // Trigger a backend fetch+rescore, then reload the UI data.
    async refresh() {
      await jpost("/api/refresh", {});
      return DDX.reload();
    },
    onReload(fn) { listeners.add(fn); return () => listeners.delete(fn); },

    copilot(view, question, context) {
      return jpost("/api/copilot", { view, question, context: context || {} });
    },
    agents() { return jget("/api/agents"); },
    dispatch(agent_type, topic, target_id) {
      return jpost("/api/agents/dispatch", { agent_type, topic, target_id });
    },
    agentStream(onEvent) {
      const es = new EventSource("/api/agents/stream");
      es.onmessage = (e) => { try { onEvent(JSON.parse(e.data)); } catch (_) {} };
      return es;
    },
    genThumbnails(content_hash, topic, count) {
      return jpost("/api/thumbnails/generate", { content_hash, topic, count: count || 6 });
    },
    pickThumbnail(id) { return jpost(`/api/thumbnails/${id}/pick`, {}); },
    schedule(item_id, day, kind, time) {
      return jpost("/api/schedule", { item_id, day, kind, time });
    },
    saveToPipeline(item) { return jpost("/api/save", item); },
  };

  window.DDX = DDX;
})();
