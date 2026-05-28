// ClustersView — every cross-source story as a deep card, sourced and angled.
// Agents are real: they call the LLM, stream logs via SSE, and surface results inline.

// ── Agent event bus ───────────────────────────────────────────────────────
// Module-level singleton so one EventSource is shared across all AutoRow instances.
// Shape per run_id: { logs: string[], status: string, stage: string, progress: number, result: string|null }

const _agentState = new Map();
const _agentListeners = new Set();

const _notifyAgentListeners = () =>
  _agentListeners.forEach(fn => { try { fn(); } catch {} });

let _agentES = null;
const _connectAgentStream = () => {
  if (_agentES && _agentES.readyState !== EventSource.CLOSED) return;
  _agentES = new EventSource("/api/agents/stream");
  _agentES.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data);
      const rid = ev.run_id || ev.run?.id;
      if (!rid) return;
      const s = _agentState.get(rid) || { logs: [], status: "queued", stage: "", progress: 0, result: null };
      if (ev.type === "started") {
        s.status = "queued"; s.logs = [];
      } else if (ev.type === "status") {
        s.status   = ev.status   || s.status;
        s.stage    = ev.stage    || s.stage;
        s.progress = ev.progress ?? s.progress;
      } else if (ev.type === "log") {
        s.logs = [...s.logs, ev.line];
      } else if (ev.type === "done") {
        s.status   = "done";
        s.progress = 1;
        // Fetch full generated content
        fetch(`/api/agents/${rid}/result`)
          .then(r => r.json())
          .then(data => {
            const cur = _agentState.get(rid);
            if (cur && data.text) {
              cur.result = data.text;
              _agentState.set(rid, { ...cur });
              _notifyAgentListeners();
            }
          }).catch(() => {});
      }
      _agentState.set(rid, { ...s, logs: [...s.logs] });
      _notifyAgentListeners();
    } catch {}
  };
  _agentES.onerror = () => setTimeout(_connectAgentStream, 4000);
};

// Hook: subscribe a component to agent stream updates
const useAgentStream = () => {
  const [, forceUpdate] = useState(0);
  useEffect(() => {
    _connectAgentStream();
    const listener = () => forceUpdate(n => n + 1);
    _agentListeners.add(listener);
    return () => _agentListeners.delete(listener);
  }, []);
  return _agentState;
};

// ── Agent output panel ────────────────────────────────────────────────────

const AgentOutputPanel = ({ state, agentLabel, onClose }) => {
  if (!state) return null;
  const isRunning = state.status === "running" || state.status === "queued";
  return (
    <div style={{
      border: "1px solid var(--line)", borderTop: "none",
      borderBottomLeftRadius: 4, borderBottomRightRadius: 4,
      background: "var(--bg-0)",
    }}>
      {/* Progress bar */}
      <div style={{ height: 2, background: "var(--line)" }}>
        <div style={{
          height: "100%",
          width: `${(state.progress || 0) * 100}%`,
          background: state.status === "error" ? "var(--signal-down)" : "var(--signal)",
          borderRadius: 1, transition: "width 0.5s ease",
        }}/>
      </div>
      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
        {/* Live log stream */}
        {state.logs.length > 0 && (
          <div className="mono" style={{ fontSize: 10.5, lineHeight: 1.7 }}>
            {state.logs.map((line, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "flex-start", gap: 6,
                color: i === state.logs.length - 1 && isRunning ? "var(--text-hi)" : "var(--text-lo)",
              }}>
                <span style={{ color: "var(--signal)", flexShrink: 0, marginTop: 1 }}>›</span>
                <span>{line}</span>
              </div>
            ))}
            {isRunning && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-lo)", marginTop: 2 }}>
                <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--signal)",
                  animation: "pulse 1s infinite", display: "inline-block" }}/>
                <span>{state.stage || "running…"}</span>
              </div>
            )}
          </div>
        )}
        {/* Error */}
        {state.status === "error" && (
          <div style={{ color: "var(--signal-down)", fontSize: 12 }}>
            Agent failed — ensure ANTHROPIC_API_KEY is set and restart the server.
          </div>
        )}
        {/* Full result */}
        {state.result && (
          <>
            <pre className="mono" style={{
              whiteSpace: "pre-wrap", wordBreak: "break-word",
              fontSize: 11, lineHeight: 1.65, color: "var(--text)", margin: 0,
              background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
              padding: "10px 12px", maxHeight: 380, overflowY: "auto",
            }}>{state.result}</pre>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn ghost"
                onClick={() => navigator.clipboard?.writeText(state.result)}>Copy</button>
              <button className="btn ghost"
                onClick={() => window.downloadScript &&
                  window.downloadScript(`${agentLabel}.md`, state.result)}>Download</button>
              <span style={{ flex: 1 }}/>
              {onClose && <button className="btn ghost" onClick={onClose}>Hide</button>}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

// ── AutoRow — real dispatch, live streaming, inline result ────────────────

const AutoRow = ({ icon, label, desc, agent, c }) => {
  const [runId, setRunId] = useState(null);
  const [open, setOpen] = useState(false);
  const agentMap = useAgentStream();
  const state = runId ? (agentMap.get(runId) || null) : null;
  const isActive = state?.status === "running" || state?.status === "queued";
  const hasOutput = state && (state.logs.length > 0 || state.result || state.status === "error");

  const run = async () => {
    if (isActive) return;
    try {
      const res = await window.DDX.dispatch(agent, c.topic, c.slug);
      if (res?.run_id) { setRunId(res.run_id); setOpen(true); }
    } catch (e) { console.error("dispatch:", e); }
  };

  const btnLabel = !state        ? "Run"
    : state.status === "queued"  ? "Queued…"
    : state.status === "running" ? "Running…"
    : state.status === "done"    ? "✓ Done"
    : "Error";

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div style={{
        display: "grid", gridTemplateColumns: "24px 1fr auto", gap: 10, alignItems: "center",
        padding: "8px 10px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
        borderBottomLeftRadius: open && hasOutput ? 0 : 4,
        borderBottomRightRadius: open && hasOutput ? 0 : 4,
      }}>
        <span style={{ color: "var(--signal)", fontSize: 14, textAlign: "center" }}>{icon}</span>
        <div style={{ lineHeight: 1.15 }}>
          <div style={{ color: "var(--text-hi)", fontSize: 12.5, fontWeight: 500 }}>{label}</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2 }}>
            {isActive ? (state.stage || "running…") : desc}
          </div>
        </div>
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          {hasOutput && (
            <button className="btn ghost" style={{ padding: "3px 7px", fontSize: 10 }}
              onClick={() => setOpen(o => !o)}>{open ? "Hide" : "View"}</button>
          )}
          <button className="btn ghost" style={{ padding: "3px 7px", fontSize: 10 }}
            disabled={isActive} onClick={run}>{btnLabel}</button>
        </div>
      </div>
      {open && hasOutput && (
        <AgentOutputPanel state={state} agentLabel={`${agent}-${c.slug}`}
          onClose={() => setOpen(false)}/>
      )}
    </div>
  );
};

// ── Dispatch all — tracks all 4 agent run_ids concurrently ───────────────

const AGENT_TYPES = ["topic_researcher", "script_writer", "thumbnail_director", "cross_poster"];

const DispatchAllButton = ({ c }) => {
  const [runs, setRuns] = useState([]); // [{ agent, run_id }]
  const [dispatching, setDispatching] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const agentMap = useAgentStream();

  const dispatchAll = async () => {
    if (dispatching) return;
    setDispatching(true); setPanelOpen(true);
    const ids = [];
    for (const agent of AGENT_TYPES) {
      try {
        const res = await window.DDX.dispatch(agent, c.topic, c.slug);
        if (res?.run_id) ids.push({ agent, run_id: res.run_id });
      } catch {}
    }
    setRuns(ids); setDispatching(false);
  };

  const doneCount = runs.filter(({ run_id }) => agentMap.get(run_id)?.status === "done").length;
  const anyRunning = runs.some(({ run_id }) => {
    const s = agentMap.get(run_id)?.status;
    return s === "running" || s === "queued";
  });

  return (
    <div style={{ flex: 1 }}>
      <button className="btn primary" style={{ width: "100%", justifyContent: "center" }}
        disabled={dispatching || anyRunning} onClick={dispatchAll}>
        <I.Spark size={11}/>
        {dispatching   ? "Dispatching…"
         : anyRunning  ? `Running… ${doneCount}/${runs.length} done`
         : runs.length ? "Run all again"
         : "Dispatch all agents"}
      </button>
      {panelOpen && runs.length > 0 && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          {runs.map(({ agent, run_id }) => {
            const state = agentMap.get(run_id);
            const hasOutput = state && (state.logs.length > 0 || state.result || state.status === "error");
            return (
              <div key={run_id} style={{
                background: "var(--bg-2)", border: "1px solid var(--line)",
                borderRadius: 4, overflow: "hidden",
              }}>
                <div style={{ padding: "6px 10px", display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="mono" style={{ fontSize: 10.5, color: "var(--text-mid)", flex: 1 }}>
                    {agent.replace(/_/g, " ")}
                  </span>
                  {state && (
                    <span className="mono" style={{ fontSize: 10,
                      color: state.status === "done"  ? "var(--signal-up)"
                           : state.status === "error" ? "var(--signal-down)"
                           : "var(--signal)" }}>
                      {state.status}
                    </span>
                  )}
                </div>
                {state && hasOutput && (
                  <AgentOutputPanel state={state} agentLabel={`${agent}-${run_id}`}/>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ── ClusterCard ───────────────────────────────────────────────────────────

const ClusterCard = ({ c, expanded, onToggle }) => {
  const S = window.DD_DATA.SOURCES;
  const primaryKey = (c.sources && c.sources.length > 0 && S[c.sources[0]]) ? c.sources[0] : Object.keys(S)[0];
  const primarySrc = S[primaryKey] || { color: "var(--signal)", label: "Source" };

  return (
    <div className="panel" style={{ overflow: "hidden" }}>
      {/* Header — always visible */}
      <div style={{
        display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 16, padding: "16px 18px",
        cursor: "pointer",
      }} onClick={onToggle}>
        <div style={{
          width: 64, height: 64, borderRadius: 8, display: "grid", placeItems: "center",
          background: `radial-gradient(circle at 30% 30%, ${primarySrc.color}33, ${primarySrc.color}08)`,
          border: `1px solid ${primarySrc.color}55`,
        }}>
          <div className="mono tnum" style={{ color: primarySrc.color, fontWeight: 700, fontSize: 22 }}>
            {c.creator_score}
          </div>
        </div>

        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <h3 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.015em",
              color: "var(--text-hi)", margin: 0 }}>{c.topic}</h3>
            <FormatBadge format={c.best_content_format}/>
            {c.has_demoable_item && (
              <span className="chip" style={{ color: "var(--signal-up)",
                borderColor: "rgba(124,255,178,0.3)", background: "rgba(124,255,178,0.05)" }}>demoable</span>
            )}
            <Momentum delta={c.momentum} big/>
          </div>
          <p style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--text)", margin: "8px 0 0",
            textWrap: "pretty", maxWidth: 760 }}>{c.why_this_is_a_story}</p>
          <div style={{ display: "flex", gap: 14, marginTop: 12, alignItems: "center" }}>
            <div style={{ display: "flex", gap: 4 }}>
              {c.sources.map(s => <SourceChip key={s} src={s}/>)}
            </div>
            <span style={{ width: 1, height: 14, background: "var(--line)" }}/>
            <span className="mono" style={{ fontSize: 11, color: "var(--text-lo)" }}>
              first seen <span style={{ color: "var(--text-hi)" }}>{c.first_seen_hrs}h ago</span>
              {" · "}{c.related_items.length} items
              {" · "}avg signal <span style={{ color: "var(--text-hi)" }}>{c.average_signal_score}</span>
            </span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
          <Waveform data={c.pulse} w={140} h={36} color={primarySrc.color}/>
          <button className="btn ghost" style={{ padding: "4px 8px" }} onClick={onToggle}>
            {expanded ? "−" : "+"} details
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{
          display: "grid", gridTemplateColumns: "1.2fr 1fr",
          padding: "0 18px 18px", gap: 22,
          borderTop: "1px solid var(--line)", paddingTop: 16,
        }}>
          {/* Left: angle + evidence */}
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
                  padding: "8px 10px", background: "var(--bg-2)",
                  border: "1px solid var(--line)", borderRadius: 4,
                }}>
                  <SourceChip src={it.source_type}/>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ color: "var(--text-hi)", fontSize: 12.5,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {it.url
                        ? <a href={it.url} target="_blank" rel="noreferrer"
                            style={{ color: "inherit", textDecoration: "none" }}
                            onClick={e => e.stopPropagation()}>{it.title}</a>
                        : it.title}
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2 }}>
                      {[it.stars && `★ ${it.stars}`, it.downloads && `↓ ${it.downloads}`,
                        it.views && `▶ ${it.views}`, it.citations, it.source, it.channel]
                        .filter(Boolean).join(" · ")}
                      {it.delta && <span style={{ color: "var(--signal-up)", marginLeft: 6 }}>{it.delta}</span>}
                    </div>
                  </div>
                  <ScoreBar value={it.signal_score} w={50} label={false}/>
                  <span className="mono tnum" style={{ fontSize: 11, color: "var(--text-hi)",
                    fontWeight: 600, minWidth: 24, textAlign: "right" }}>{it.signal_score}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: format tiles + live agentic actions */}
          <div>
            <div className="label" style={{ marginBottom: 8 }}>Make this into</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <ActionTile label="Long-form"  icon={<I.YT size={14}/>}    sub="14–18 min"       hot onClick={() => makeInto(c, "YouTube long-form")}/>
              <ActionTile label="Short"      icon={<I.Play size={11}/>}  sub="< 60s"            onClick={() => makeInto(c, "YouTube short")}/>
              <ActionTile label="Carousel"   icon={<I.Doc size={14}/>}   sub="LinkedIn · 8 slides" onClick={() => makeInto(c, "LinkedIn carousel")}/>
              <ActionTile label="Newsletter" icon={<I.Paper size={14}/>} sub="~1,200w"          onClick={() => makeInto(c, "Newsletter")}/>
            </div>

            <div className="label" style={{ marginTop: 18, marginBottom: 8 }}>
              Agentic actions · results stream in below each button
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <AutoRow icon="🔎" label="Build research pack"
                desc="leads + strategic brief + narrative hooks" agent="topic_researcher" c={c}/>
              <AutoRow icon="✎" label="Draft video script"
                desc="cold open + 3 sections + demo moment + CTA" agent="script_writer" c={c}/>
              <AutoRow icon="▣" label="Thumbnail concepts"
                desc="6 visual variants with CTR reasoning" agent="thumbnail_director" c={c}/>
              <AutoRow icon="↗" label="LinkedIn carousel"
                desc="8 slides, direct tone, cite real data" agent="cross_poster" c={c}/>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
              <DispatchAllButton c={c}/>
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

// ── helpers ───────────────────────────────────────────────────────────────

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
    {hot && <span className="mono" style={{ marginLeft: "auto", fontSize: 9.5,
      color: "var(--signal)", letterSpacing: "0.05em" }}>RECOMMENDED</span>}
  </button>
);

// ── ClustersView ──────────────────────────────────────────────────────────

const ClustersView = ({ onJump }) => {
  const { clusters } = window.DD_DATA;
  const [expandedId, setExpandedId] = useState(clusters[0] ? clusters[0].slug : null);
  const [sortMode, setSortMode] = useState("momentum");

  if (!clusters.length) {
    return (
      <div className="panel crosshair" style={{ padding: "48px 22px", textAlign: "center" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <div className="label" style={{ marginBottom: 10 }}>Clusters</div>
        <h1 className="serif" style={{ fontSize: 26, color: "var(--text-hi)", margin: "0 0 12px", fontWeight: 600 }}>
          No cross-source stories yet
        </h1>
        <p style={{ color: "var(--text-mid)", maxWidth: 420, margin: "0 auto 18px" }}>
          Clusters appear once sources are fetched and the same topic shows up across families.
        </p>
        <button className="btn primary" onClick={() => window.DDX && window.DDX.refresh()}>
          Fetch sources now
        </button>
      </div>
    );
  }

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
              {["momentum", "score", "fresh"].map(m => (
                <button key={m} className="btn ghost" onClick={() => setSortMode(m)}
                  style={{
                    color: sortMode === m ? "var(--text-hi)" : "var(--text-mid)",
                    borderColor: sortMode === m ? "var(--signal)" : "var(--line-2)",
                  }}>{m}</button>
              ))}
            </>
          }>
          Content clusters · {clusters.length} active stories
        </PanelHeader>
        <div style={{ padding: "16px 20px" }}>
          <p className="serif" style={{
            fontSize: 22, lineHeight: 1.3, color: "var(--text-hi)", margin: 0,
            fontStyle: "italic", maxWidth: 720,
          }}>
            A cluster is a topic appearing across{" "}
            <span style={{ color: "var(--signal)" }}>two or more source families</span> in the last week.
            Expand any story — agents run live, stream logs, and deliver results inline.
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
