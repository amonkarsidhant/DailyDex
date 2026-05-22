// ClustersView — every cross-source story as a deep card, sourced and angled

const ClusterCard = ({ c, expanded, onToggle }) => {
  const S = window.DD_DATA.SOURCES;
  return (
    <div className="panel" style={{ overflow: "hidden" }}>
      <div style={{
        display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 16, padding: "16px 18px",
        cursor: "pointer",
      }} onClick={onToggle}>
        <div style={{
          width: 64, height: 64, borderRadius: 8, display: "grid", placeItems: "center",
          background: `radial-gradient(circle at 30% 30%, ${S[c.sources[0]].color}33, ${S[c.sources[0]].color}08)`,
          border: `1px solid ${S[c.sources[0]].color}55`,
        }}>
          <div className="mono tnum" style={{ color: S[c.sources[0]].color, fontWeight: 700, fontSize: 22 }}>{c.creator_score}</div>
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <h3 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em", color: "var(--text-hi)", margin: 0 }}>{c.topic}</h3>
            <FormatBadge format={c.best_content_format}/>
            {c.has_demoable_item && (
              <span className="chip" style={{ color: "var(--signal-up)", borderColor: "rgba(124,255,178,0.3)", background: "rgba(124,255,178,0.05)" }}>demoable</span>
            )}
            <Momentum delta={c.momentum} big/>
          </div>
          <p style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--text)", margin: "8px 0 0", textWrap: "pretty", maxWidth: 760 }}>
            {c.why_this_is_a_story}
          </p>
          <div style={{ display: "flex", gap: 14, marginTop: 12, alignItems: "center" }}>
            <div style={{ display: "flex", gap: 4 }}>
              {c.sources.map(s => <SourceChip key={s} src={s}/>)}
            </div>
            <span style={{ width: 1, height: 14, background: "var(--line)" }}/>
            <span className="mono" style={{ fontSize: 11, color: "var(--text-lo)" }}>
              first seen <span style={{ color: "var(--text-hi)" }}>{c.first_seen_hrs}h ago</span> · {c.related_items.length} items · avg signal <span style={{ color: "var(--text-hi)" }}>{c.average_signal_score}</span>
            </span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
          <Waveform data={c.pulse} w={140} h={36} color={S[c.sources[0]].color}/>
          <button className="btn ghost" style={{ padding: "4px 8px" }} onClick={onToggle}>{expanded ? "−" : "+"} details</button>
        </div>
      </div>

      {expanded && (
        <div style={{
          display: "grid", gridTemplateColumns: "1.2fr 1fr",
          padding: "0 18px 18px", gap: 22, borderTop: "1px solid var(--line)", paddingTop: 16,
        }}>
          <div>
            <div className="label" style={{ marginBottom: 8 }}>Recommended angle</div>
            <p className="serif" style={{
              fontSize: 17, fontStyle: "italic", lineHeight: 1.4,
              color: "var(--text-hi)", margin: 0, textWrap: "pretty",
            }}>{c.recommended_angle}</p>

            <div className="label" style={{ marginTop: 18, marginBottom: 10 }}>Source evidence</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {c.related_items.map((it, i) => (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "auto 1fr auto auto",
                  gap: 12, alignItems: "center",
                  padding: "8px 10px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
                }}>
                  <SourceChip src={it.source_type}/>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ color: "var(--text-hi)", fontSize: 12.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {it.title}
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2 }}>
                      {[it.stars && `★ ${it.stars}`, it.downloads && `↓ ${it.downloads}`, it.views && `▶ ${it.views}`, it.citations, it.source, it.channel].filter(Boolean).join(" · ")}
                      {it.delta && <span style={{ color: "var(--signal-up)", marginLeft: 6 }}>{it.delta}</span>}
                    </div>
                  </div>
                  <ScoreBar value={it.signal_score} w={50} label={false}/>
                  <span className="mono tnum" style={{ fontSize: 11, color: "var(--text-hi)", fontWeight: 600, minWidth: 24, textAlign: "right" }}>{it.signal_score}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: action card */}
          <div>
            <div className="label" style={{ marginBottom: 8 }}>Make this into</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <ActionTile label="Long-form" icon={<I.YT size={14}/>} sub="14–18 min" hot onClick={() => makeInto(c, "YouTube long-form")}/>
              <ActionTile label="Short" icon={<I.Play size={11}/>} sub="< 60s" onClick={() => makeInto(c, "YouTube short")}/>
              <ActionTile label="Carousel" icon={<I.Doc size={14}/>} sub="LinkedIn · 8 slides" onClick={() => makeInto(c, "LinkedIn carousel")}/>
              <ActionTile label="Newsletter" icon={<I.Paper size={14}/>} sub="~1,200w" onClick={() => makeInto(c, "Newsletter")}/>
            </div>

            <div className="label" style={{ marginTop: 18, marginBottom: 8 }}>Auto-actions</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <AutoRow icon="🔎" label="Build research pack" desc="merges 5 sources + key claims" agent="topic_researcher" c={c} />
              <AutoRow icon="✎" label="Draft 3-beat script" desc="brand voice + signature angle" agent="script_writer" c={c} />
              <AutoRow icon="▣" label="Generate thumbnails" desc="6 variants × CTR-scored" agent="thumbnail_director" c={c} />
              <AutoRow icon="↗" label="Adapt for LinkedIn" desc="reshape tone + add 1 chart" agent="cross_poster" c={c} />
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
              <button className="btn primary" style={{ flex: 1, justifyContent: "center" }}
                      onClick={() => {
                        ["topic_researcher","script_writer","thumbnail_director","cross_poster"]
                          .forEach(a => window.DDX && window.DDX.dispatch(a, c.topic, c.slug));
                      }}>
                <I.Spark size={11}/> Dispatch all agents
              </button>
              <button className="btn ghost" title="Save to pipeline" onClick={() => {
                if (!window.DDX) return;
                window.DDX.saveToPipeline({
                  title: c.topic, working_title: c.topic, topic: c.topic, category: c.topic,
                  format: c.best_content_format, creator_score: c.creator_score,
                  signal_score: c.average_signal_score, pipeline_type: "creator", status: "idea",
                }).then(() => { alert("Saved to pipeline."); window.DDX.reload(); });
              }}><I.Save size={12}/></button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const makeInto = (c, format) => {
  if (!window.DDX) return;
  window.DDX.saveToPipeline({
    title: c.topic, working_title: c.topic, topic: c.topic, category: c.topic,
    format, creator_score: c.creator_score, signal_score: c.average_signal_score,
    pipeline_type: "creator", status: "idea",
  }).then(() => { alert(`Saved "${c.topic}" as ${format} idea.`); window.DDX.reload(); });
};

const ActionTile = ({ label, icon, sub, hot, onClick }) => (
  <button onClick={onClick} style={{
    display: "flex", alignItems: "center", gap: 10, padding: "10px 12px",
    background: hot ? "rgba(240,183,47,0.06)" : "var(--bg-2)",
    border: `1px solid ${hot ? "rgba(240,183,47,0.45)" : "var(--line-2)"}`,
    borderRadius: 4, cursor: "pointer", textAlign: "left",
    color: hot ? "var(--text-hi)" : "var(--text)",
  }}>
    <span style={{ color: hot ? "var(--signal)" : "var(--text-mid)" }}>{icon}</span>
    <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
      <span style={{ fontSize: 12.5, fontWeight: 600 }}>{label}</span>
      <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2 }}>{sub}</span>
    </span>
    {hot && <span className="mono" style={{ marginLeft: "auto", fontSize: 9.5, color: "var(--signal)", letterSpacing: "0.05em" }}>RECOMMENDED</span>}
  </button>
);

const AutoRow = ({ icon, label, desc, agent, c }) => {
  const [state, setState] = useState("ready");
  const run = async () => {
    if (!window.DDX || state === "running") return;
    setState("running");
    try { await window.DDX.dispatch(agent, c.topic, c.slug); setState("dispatched"); }
    catch (e) { setState("ready"); }
  };
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "24px 1fr auto", gap: 10, alignItems: "center",
      padding: "8px 10px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
    }}>
      <span style={{ color: "var(--signal)", fontSize: 14, lineHeight: 1, textAlign: "center" }}>{icon}</span>
      <div style={{ lineHeight: 1.15 }}>
        <div style={{ color: "var(--text-hi)", fontSize: 12.5, fontWeight: 500 }}>{label}</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2 }}>{desc}</div>
      </div>
      <button className="btn ghost" style={{ padding: "3px 7px", fontSize: 10 }} onClick={run} disabled={state==="running"}>
        {state === "dispatched" ? "✓ Sent" : state === "running" ? "…" : "Run"}
      </button>
    </div>
  );
};

const ClustersView = ({ onJump }) => {
  const { clusters } = window.DD_DATA;
  const [expandedId, setExpandedId] = useState(clusters[0].slug);
  const [sortMode, setSortMode] = useState("momentum");

  const sorted = [...clusters].sort((a, b) => {
    if (sortMode === "score") return b.creator_score - a.creator_score;
    if (sortMode === "fresh") return a.first_seen_hrs - b.first_seen_hrs;
    return b.momentum - a.momentum;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="panel crosshair" style={{ overflow: "hidden" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <PanelHeader no="01"
          actions={
            <>
              {["momentum","score","fresh"].map(m => (
                <button key={m} className="btn ghost"
                  onClick={() => setSortMode(m)}
                  style={{
                    color: sortMode === m ? "var(--text-hi)" : "var(--text-mid)",
                    borderColor: sortMode === m ? "var(--signal)" : "var(--line-2)",
                  }}>
                  {m}
                </button>
              ))}
            </>
          }>
          Content clusters · {clusters.length} active stories
        </PanelHeader>
        <div style={{ padding: "16px 20px" }}>
          <p className="serif" style={{
            fontSize: 22, lineHeight: 1.3, color: "var(--text-hi)", margin: 0, fontStyle: "italic", maxWidth: 720,
          }}>
            A cluster is a topic appearing across <span style={{ color: "var(--signal)" }}>two or more source families</span> in the last week.
            Each one is a real story; each one has its angle pre-extracted.
          </p>
        </div>
      </div>

      {sorted.map(c => (
        <ClusterCard key={c.slug} c={c}
          expanded={expandedId === c.slug}
          onToggle={() => setExpandedId(expandedId === c.slug ? null : c.slug)}/>
      ))}
    </div>
  );
};

window.ClustersView = ClustersView;
