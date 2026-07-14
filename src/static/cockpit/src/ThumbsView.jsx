// ThumbsView — thumbnail explorations with side-by-side title experiments

const ThumbsView = ({ onJump, selectedClusterSlug, setSelectedClusterSlug }) => {
  const { thumbnails, titleSets, clusters, opportunities = [] } = window.DD_DATA;
  const _firstTopic = selectedClusterSlug || (thumbnails[0] && thumbnails[0].topic) || (clusters[0] && clusters[0].slug) || "";
  const [topic, setTopic] = useState(_firstTopic);
  const topicThumbs = thumbnails.filter(t => t.topic === topic);
  const allTopics = [...new Set([...thumbnails.map(t => t.topic), ...clusters.map(c => c.slug).filter(Boolean)])];
  const titles = titleSets[topic] || {};
  const cluster = clusters.find(c => c.slug === topic);
  const opportunity = opportunities.find(item => item.cluster_slug === topic || item.slug === topic);
  const topicContentHash = opportunity?.content_hash || topic;
  const [picked, setPicked] = useState(topicThumbs[0]?.id);
  const [generatingId, setGeneratingId] = useState(null);

  useEffect(() => {
    if (selectedClusterSlug && clusters.some(cluster => cluster.slug === selectedClusterSlug)) {
      setTopic(selectedClusterSlug);
      setPicked(thumbnails.find(thumbnail => thumbnail.topic === selectedClusterSlug)?.id);
    }
  }, [selectedClusterSlug]);

  useEffect(() => {
    const current = thumbnails.filter(thumbnail => thumbnail.topic === topic);
    if (!current.some(thumbnail => thumbnail.id === picked)) {
      setPicked(current[0]?.id);
    }
  }, [thumbnails, topic]);

  const selectTopic = nextTopic => {
    setTopic(nextTopic);
    setPicked(thumbnails.find(thumbnail => thumbnail.topic === nextTopic)?.id);
    if (setSelectedClusterSlug) setSelectedClusterSlug(nextTopic);
  };

  const handleGenerate = async (p) => {
    setGeneratingId(p.id);
    try {
      const res = await window.DDX.generateThumbnailImage(
        cluster?.topic || topic, "dark_tech", p.text || p.text_primary, 1, p.id
      );
      if (res.ok) {
        alert("✓ Real image generated via Flux!");
        await window.DDX.reload();
      } else {
        alert("Generation failed. Check your fal.ai API key.");
      }
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      setGeneratingId(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel crosshair" style={{ overflow: "hidden" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <PanelHeader no="01"
          actions={
            <>
              <button className="btn ghost" onClick={async () => {
                const ch = (topicThumbs[0] || {}).content_hash;
                const cl = clusters.find(c => c.slug === topic) || {};
                if (window.DDX && ch) { await window.DDX.genThumbnails(ch, cl.topic, 6); window.DDX.reload(); }
              }}><I.Refresh size={12}/> Regenerate 6</button>
              <button className="btn primary" onClick={() => {
                const cl = clusters.find(c => c.slug === topic) || {};
                const ch = (topicThumbs[0] || {}).content_hash || topicContentHash;
                if (window.DDX) window.DDX.dispatch("thumbnail_director", cl.topic, ch);
              }}><I.Spark size={11}/> Dispatch director</button>
            </>
          }>
          Thumb Lab · title × thumbnail experiments
        </PanelHeader>

        <div style={{ padding: "16px 20px" }}>
          {/* Topic switcher */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {allTopics.map(t => {
              const c = clusters.find(cl => cl.slug === t);
              return (
                <button key={t}
                  onClick={() => selectTopic(t)}
                  style={{
                    padding: "6px 12px",
                    background: topic === t ? "var(--bg-3)" : "var(--bg-2)",
                    border: `1px solid ${topic === t ? "var(--signal)" : "var(--line-2)"}`,
                    color: topic === t ? "var(--text-hi)" : "var(--text-mid)",
                    borderRadius: 4, cursor: "pointer",
                    fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.04em",
                    textTransform: "uppercase",
                  }}>{c?.topic || t}</button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Picked detail */}
      <div className="panel" style={{ overflow: "hidden" }}>
        <PanelHeader no="02"
          actions={
            <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.06em" }}>
              {topicThumbs.length} variants · sorted by heuristic CTR score
            </span>
          }>
          Variants for {cluster?.topic}
        </PanelHeader>
        <div style={{ display: topicThumbs.length > 0 ? "grid" : "block", gridTemplateColumns: "1.2fr 1fr", padding: "20px 24px", gap: 28 }}>
          {topicThumbs.length === 0 ? (
            <div style={{ padding: "48px 0", textAlign: "center" }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🎨</div>
              <h3 className="serif" style={{ fontSize: 20, color: "var(--text-hi)", margin: "0 0 8px", fontWeight: 600 }}>No Thumbnail Variants Generated Yet</h3>
              <p style={{ color: "var(--text-mid)", maxWidth: 360, margin: "0 auto 16px", fontSize: 12.5 }}>
                Generate thumbnail variants for this topic using the Autonomous Thumbnail Director or compile a set of 6 stubs now.
              </p>
              <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                <button className="btn primary" onClick={async () => {
                  if (window.DDX) {
                    const cl = clusters.find(c => c.slug === topic) || {};
                    await window.DDX.genThumbnails(topicContentHash, cl.topic || topic, 6);
                    window.DDX.reload();
                  }
                }}>Compile 6 variants</button>
                <button className="btn ghost" onClick={() => {
                  const cl = clusters.find(c => c.slug === topic) || {};
                  if (window.DDX) window.DDX.dispatch("thumbnail_director", cl.topic || topic, topicContentHash);
                }}><I.Spark size={11}/> Dispatch director</button>
              </div>
            </div>
          ) : (
            <>
              {/* Big picked thumb */}
              <div>
                {(() => {
                  const p = topicThumbs.find(t => t.id === picked) || topicThumbs[0];
                  return p ? (
                    <>
                      <FakeThumb t={p} w={520} h={293}/>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 10 }}>
                        <div className="mono" style={{ fontSize: 11, color: "var(--text-mid)", letterSpacing: "0.04em" }}>
                          {p.kind.toUpperCase()} · variant {topicThumbs.findIndex(x => x.id === p.id) + 1}
                        </div>
                         <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                           <span className="mono tnum" style={{ fontSize: 12, color: "var(--signal-up)", fontWeight: 600 }}>CTR heuristic {p.ctr}</span>
                          <button className="btn primary" disabled={generatingId === p.id} onClick={() => handleGenerate(p)} style={{ fontSize: 11, padding: "4px 8px" }}>
                            {generatingId === p.id ? "🎨 Generating..." : p.image_path ? "🖼 Regenerate Image" : "🖼 Generate Flux Image"}
                          </button>
                          <button className="btn ghost" onClick={() => {
                            if (window.DDX && p) window.DDX.pickThumbnail(p.id).then(() => { alert("Thumbnail picked."); window.DDX.reload(); });
                          }}><I.Save size={11}/> Save</button>
                          <button className="btn ghost" onClick={async () => {
                            if (!window.DDX || !p) return;
                            await fetch(`/api/thumbnails/${p.id}`, { method: "DELETE" });
                            window.DDX.reload();
                          }}><I.X size={11}/> Reject</button>
                        </div>
                      </div>

                      {/* The current score is a visual heuristic, not channel analytics. */}
                      <div className="panel" style={{ padding: 14, marginTop: 16, background: "var(--bg-2)" }}>
                        <div className="label" style={{ color: "var(--text-hi)" }}>Heuristic score, not measured channel CTR</div>
                        <p style={{ margin: "7px 0 0", color: "var(--text-mid)", fontSize: 11.5, lineHeight: 1.45 }}>
                          This score ranks visual variants using format and visual-potential signals. It is not a claim about historical channel performance.
                        </p>
                      </div>
                    </>
                  ) : null;
                })()}
              </div>

              {/* Title × thumb matrix */}
              <div>
                <div className="label">Pair with title</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                  {Object.entries(titles).map(([k, v]) => (
                    <div key={k} style={{
                      padding: "10px 12px",
                      background: "var(--bg-2)",
                      border: "1px solid var(--line)",
                      borderRadius: 4,
                    }}>
                      <div className="micro">{k.toUpperCase()}</div>
                      <div style={{ color: "var(--text-hi)", fontSize: 13.5, lineHeight: 1.3, marginTop: 4, fontWeight: 500, textWrap: "balance" }}>
                        {v}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="label" style={{ marginTop: 18 }}>Director analysis</div>
                <p style={{ margin: "8px 0 0", fontSize: 12.5, lineHeight: 1.5, color: "var(--text-mid)" }}>
                  Dispatch the Thumbnail Director for story-specific visual reasoning. No channel-performance claim is shown without analytics data.
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Variant grid */}
      {topicThumbs.length > 0 && (
        <div className="panel" style={{ overflow: "hidden" }}>
          <PanelHeader no="03">All variants</PanelHeader>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
            gap: 1, background: "var(--line)", padding: 1,
          }}>
            {topicThumbs.map((t, i) => (
              <button key={t.id}
                   onClick={() => setPicked(t.id)}
                   style={{
                      padding: 16, background: "var(--bg-1)", cursor: "pointer",
                      display: "flex", flexDirection: "column", gap: 10,
                      borderLeft: picked === t.id ? "2px solid var(--signal)" : "2px solid transparent",
                      borderTop: 0, borderRight: 0, borderBottom: 0,
                      color: "inherit", textAlign: "left",
                    }}>
                <FakeThumb t={t} w={300} h={169}/>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span className="mono" style={{ fontSize: 10.5, color: "var(--text-mid)", letterSpacing: "0.05em", display: "flex", gap: 5, alignItems: "center" }}>
                    {t.kind.toUpperCase()}
                    {t.picked && <span style={{ fontSize: 8, color: "var(--signal-up)", padding: "1px 4px", border: "1px solid rgba(124,255,178,0.25)", borderRadius: 2, background: "rgba(124,255,178,0.06)" }}>ACTIVE</span>}
                  </span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <ScoreBar value={Math.round(t.ctr * 10)} w={36} label={false}/>
                    <span className="mono tnum" style={{ fontSize: 11, color: "var(--text-hi)", fontWeight: 600 }}>{t.ctr}</span>
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

window.ThumbsView = ThumbsView;
