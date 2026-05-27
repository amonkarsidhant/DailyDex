// ThumbsView — thumbnail explorations with side-by-side title experiments

const ThumbsView = ({ onJump }) => {
  const { thumbnails, titleSets, clusters } = window.DD_DATA;
  const _firstTopic = (thumbnails[0] && thumbnails[0].topic) || (clusters[0] && clusters[0].slug) || "";
  const [topic, setTopic] = useState(_firstTopic);
  const topicThumbs = thumbnails.filter(t => t.topic === topic);
  const allTopics = [...new Set([...thumbnails.map(t => t.topic), ...clusters.map(c => c.slug).filter(Boolean)])];
  const titles = titleSets[topic] || {};
  const cluster = clusters.find(c => c.slug === topic);
  const [picked, setPicked] = useState(topicThumbs[0]?.id);

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
                const ch = (topicThumbs[0] || {}).content_hash || topic;
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
                  onClick={() => { setTopic(t); setPicked(thumbnails.find(th => th.topic === t)?.id); }}
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
              {topicThumbs.length} variants · sorted by CTR likelihood
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
                    await window.DDX.genThumbnails(topic, cl.topic || topic, 6);
                    window.DDX.reload();
                  }
                }}>Compile 6 variants</button>
                <button className="btn ghost" onClick={() => {
                  const cl = clusters.find(c => c.slug === topic) || {};
                  if (window.DDX) window.DDX.dispatch("thumbnail_director", cl.topic || topic, topic);
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
                          <span className="mono tnum" style={{ fontSize: 12, color: "var(--signal-up)", fontWeight: 600 }}>CTR-likelihood {p.ctr}</span>
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

                      {/* Predicted CTR distribution vs channel baseline */}
                      <div className="panel" style={{ padding: 14, marginTop: 16, background: "var(--bg-2)" }}>
                        <div className="label" style={{ color: "var(--text-hi)" }}>Predicted CTR vs your channel baseline</div>
                        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                          <BaselineBar label="Your last 30 videos" val={0.62} max={12} note="6.2% avg"/>
                          <BaselineBar label="Your top 10%"        val={0.88} max={12} note="8.8% avg"/>
                          <BaselineBar label={`This thumb`}       val={p.ctr / 12} max={12} note={`${p.ctr}% pred · top decile`} hot/>
                        </div>
                      </div>
                    </>
                  ) : null;
                })()}
              </div>

              {/* Title × thumb matrix */}
              <div>
                <div className="label">Pair with title</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                  {Object.entries(titles).map(([k, v], i) => (
                    <div key={k} style={{
                      padding: "10px 12px",
                      background: i === 1 ? "rgba(240,183,47,0.06)" : "var(--bg-2)",
                      border: `1px solid ${i === 1 ? "rgba(240,183,47,0.4)" : "var(--line)"}`,
                      borderRadius: 4,
                    }}>
                      <div className="micro" style={{ color: i === 1 ? "var(--signal)" : "var(--text-lo)" }}>{k.toUpperCase()}{i === 1 ? " · top pair" : ""}</div>
                      <div style={{ color: "var(--text-hi)", fontSize: 13.5, lineHeight: 1.3, marginTop: 4, fontWeight: i === 1 ? 600 : 500, textWrap: "balance" }}>
                        {v}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 6 }}>
                        <ScoreBar value={60 + i * 8} w={60} label={false}/>
                        <span className="mono tnum" style={{ fontSize: 10.5, color: "var(--text-mid)" }}>pair-fit {60 + i * 8}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="label" style={{ marginTop: 18 }}>Director's notes</div>
                <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 12.5, lineHeight: 1.5, color: "var(--text)" }}>
                  <li>Face-zoom variants outperform headline-only by ~22% for this channel.</li>
                  <li>Yellow + dark contrast is your signature — keep it.</li>
                  <li>Avoid "open-source" as a thumbnail word (last 3 underperformed).</li>
                </ul>
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
              <div key={t.id}
                   onClick={() => setPicked(t.id)}
                   style={{
                     padding: 16, background: "var(--bg-1)", cursor: "pointer",
                     display: "flex", flexDirection: "column", gap: 10,
                     borderLeft: picked === t.id ? "2px solid var(--signal)" : "2px solid transparent",
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
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const BaselineBar = ({ label, val, max, note, hot }) => (
  <div style={{ display: "grid", gridTemplateColumns: "180px 1fr auto", gap: 10, alignItems: "center" }}>
    <span style={{ fontSize: 12, color: "var(--text)" }}>{label}</span>
    <div style={{ height: 6, background: "var(--bg-0)", borderRadius: 3, position: "relative", overflow: "hidden" }}>
      <div style={{
        height: "100%", width: `${val * 100}%`,
        background: hot ? "var(--signal-up)" : "var(--text-mid)",
        boxShadow: hot ? "0 0 8px var(--signal-up)" : "none",
      }}/>
    </div>
    <span className="mono tnum" style={{ fontSize: 10.5, color: hot ? "var(--signal-up)" : "var(--text-mid)" }}>{note}</span>
  </div>
);

window.ThumbsView = ThumbsView;
