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
    ignoreTopic(topic, items) {
      return jpost("/api/ignore-topic", { topic, items });
    },

    // Creator Central
    studio() { return jget("/api/studio"); },
    studioRun(topN, slugs) { return jpost("/api/studio/run", { top_n: topN || 0, slugs: slugs || null }); },
    studioRegenerate(storyKey, fmt, provider) {
      return jpost(`/api/studio/${encodeURIComponent(storyKey)}/${fmt}/regenerate`,
                   provider ? { provider } : {});
    },
    studioStream(onLog) {
      const es = new EventSource("/api/studio/stream");
      es.onmessage = (e) => { try { onLog(JSON.parse(e.data)); } catch (_) {} };
      return es;
    },
    editorialApprove() { return jpost("/api/editorial/approve", {}); },
    publish(item_id, platform) { return jpost("/api/publish", { item_id, platform }); },
    simulateAnalytics() { return jpost("/api/analytics/simulate", {}); },

    // Advanced Creator Integrations
    syncNotion(itemId) {
      return jpost("/api/integrations/notion/sync", { item_id: itemId });
    },
    repurposeVideo(itemId) {
      return jpost("/api/integrations/repurpose", { item_id: itemId });
    },
    getRepurposedClips(parentItemId) {
      return jget(`/api/integrations/repurpose?parent_item_id=${parentItemId}`);
    },
    publishRepurposedClip(clipId) {
      return jpost(`/api/integrations/repurpose/${clipId}/publish`, {});
    },
    startABTest(itemId, variantATitle, variantBTitle, variantAImage, variantBImage) {
      return jpost("/api/integrations/ab-test", {
        item_id: itemId,
        variant_a_title: variantATitle,
        variant_b_title: variantBTitle,
        variant_a_image: variantAImage || "",
        variant_b_image: variantBImage || ""
      });
    },
    getActiveABTest(itemId) {
      return jget(`/api/integrations/ab-test/active?item_id=${itemId}`);
    },

    // Settings (BYOK)
    getSettings() { return jget("/api/settings"); },
    saveSettings(updates) {
      return fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      }).then(r => r.json());
    },
    deleteSetting(key) {
      return fetch(`/api/settings/${key}`, { method: "DELETE" }).then(r => r.json());
    },
    validateYouTubeKey(api_key) {
      return jpost("/api/settings/validate/youtube", { api_key });
    },
    validateFalKey(api_key) {
      return jpost("/api/settings/validate/fal", { api_key });
    },
    getProviderInfo() { return jget("/api/settings/provider-info"); },

    // Real image generation (Flux via fal.ai)
    generateThumbnailImage(topic, style, extra_context, num_variants, variant_id) {
      return jpost("/api/thumbnails/generate-image", {
        topic, style: style || "dark_tech",
        extra_context, num_variants: num_variants || 1,
        variant_id: variant_id || null,
      });
    },
    getThumbnailStyles() { return jget("/api/thumbnails/styles"); },
  };

  window.DDX = DDX;
})();
