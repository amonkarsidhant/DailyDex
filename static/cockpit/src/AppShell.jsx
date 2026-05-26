// AppShell — nav, topbar, agent rail, copilot dock
const { useState, useEffect, useMemo, useRef } = React;

// ─── Left nav ───────────────────────────────────────────────────────────────
const NavItem = ({ icon, label, sub, active, hot, onClick }) => (
  <button onClick={onClick} style={{
    display: "grid", gridTemplateColumns: "20px 1fr auto",
    alignItems: "center", columnGap: 10,
    width: "100%", textAlign: "left",
    padding: "9px 12px",
    background: active ? "var(--bg-3)" : "transparent",
    color: active ? "var(--text-hi)" : "var(--text)",
    border: "none",
    borderLeft: `2px solid ${active ? "var(--signal)" : "transparent"}`,
    cursor: "pointer",
    fontFamily: "var(--font-sans)",
    fontSize: 13,
    transition: "background 120ms, color 120ms, border-color 120ms",
  }} onMouseEnter={e => { if (!active) e.currentTarget.style.background = "var(--bg-2)"; }}
     onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}>
    <span style={{ color: active ? "var(--signal)" : "var(--text-mid)", display: "flex" }}>{icon}</span>
    <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.15 }}>
      <span style={{ fontWeight: active ? 600 : 500 }}>{label}</span>
      {sub && <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2, letterSpacing: "0.04em" }}>{sub}</span>}
    </span>
    {hot && (
      <span className="mono tnum" style={{
        fontSize: 10, color: "var(--signal-up)",
        background: "rgba(124,255,178,0.10)",
        border: "1px solid rgba(124,255,178,0.3)",
        padding: "1px 5px", borderRadius: 999,
      }}>{hot}</span>
    )}
  </button>
);

const Nav = ({ view, setView }) => {
  const items = [
    { key: "pulse",     icon: <I.Pulse size={15}/>,    label: "Pulse",    sub: "trend radar",         hot: "8 new" },
    { key: "brief",     icon: <I.Brief size={15}/>,    label: "Brief",    sub: "today's pick" },
    { key: "clusters",  icon: <I.Cluster size={15}/>,  label: "Clusters", sub: "cross-source stories" },
    { key: "thumbs",    icon: <I.Thumb size={15}/>,    label: "Thumb Lab",sub: "title × thumb"  },
    { key: "research",  icon: <I.Research size={15}/>, label: "Research", sub: "evidence packs" },
    { key: "pipeline",  icon: <I.Pipeline size={15}/>, label: "Pipeline", sub: "+ calendar"        },
    { key: "studio",    icon: <I.Studio size={15}/>,   label: "Creator Central", sub: "autonomous content" },
  ];
  return (
    <nav className="nav" style={{ display: "flex", flexDirection: "column" }}>
      {/* Brand */}
      <div style={{
        padding: "16px 16px 14px", borderBottom: "1px solid var(--line)",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 6,
          background: "linear-gradient(135deg, var(--signal) 0%, var(--signal-hot) 100%)",
          display: "grid", placeItems: "center",
          boxShadow: "0 0 0 1px rgba(240,183,47,0.4), 0 4px 12px rgba(240,183,47,0.25)",
        }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="#1A1100">
            <path d="M2 13 L7 3 L9 7 L12 7 L14 13 Z"/>
          </svg>
        </div>
        <div style={{ lineHeight: 1.1 }}>
          <div style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 15, letterSpacing: "-0.01em" }}>DailyDex</div>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--text-lo)", letterSpacing: "0.12em", marginTop: 2 }}>CREATOR · COCKPIT</div>
        </div>
      </div>

      {/* Persona switch (mini display) */}
      <PersonaBadge />

      {/* Items */}
      <div style={{ padding: "8px 0", display: "flex", flexDirection: "column", gap: 2 }}>
        <div className="micro" style={{ padding: "8px 16px 4px" }}>Workspace</div>
        {items.map(it => <NavItem key={it.key} {...it} active={view === it.key} onClick={() => setView(it.key)} />)}
      </div>

      {/* Saved / tracked counts at bottom */}
      <div style={{ marginTop: "auto", padding: 14, borderTop: "1px solid var(--line)" }}>
        <div className="micro" style={{ marginBottom: 8 }}>State</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <MiniStat label="Saved" value="34" />
          <MiniStat label="Tracked" value="11" />
          <MiniStat label="In pipe" value="6" />
          <MiniStat label="Drafts" value="3" color="var(--signal)"/>
        </div>
      </div>
    </nav>
  );
};

const MiniStat = ({ label, value, color }) => (
  <div style={{ padding: "6px 8px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4 }}>
    <div className="mono tnum" style={{ color: color || "var(--text-hi)", fontWeight: 600, fontSize: 16 }}>{value}</div>
    <div className="micro" style={{ marginTop: 2 }}>{label}</div>
  </div>
);

const PersonaBadge = () => {
  const persona = window.__tweaks?.persona || "multi";
  const p = window.DD_DATA.personas[persona];
  return (
    <div style={{
      margin: "12px 12px 4px", padding: "10px 12px",
      background: "var(--bg-2)", border: "1px solid var(--line)",
      borderRadius: 6,
    }}>
      <div className="micro">Persona</div>
      <div style={{ color: "var(--text-hi)", fontWeight: 600, marginTop: 4, fontSize: 13 }}>{p.label}</div>
      <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2, letterSpacing: "0.04em" }}>{p.sub}</div>
    </div>
  );
};

// ─── Topbar ─────────────────────────────────────────────────────────────────
const Topbar = ({ now, onOpenTweaks, onRefresh, refreshing }) => {
  const { sourceHealth, SOURCES } = window.DD_DATA;
  return (
    <header className="topbar" style={{
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      alignItems: "center", padding: "0 16px", gap: 16,
    }}>
      {/* Left: clock + status */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="blink" style={{ width: 7, height: 7, borderRadius: 999, background: "var(--signal-up)", boxShadow: "0 0 6px var(--signal-up)" }}/>
          <span className="mono" style={{ fontSize: 11, color: "var(--text-mid)", letterSpacing: "0.06em" }}>LIVE</span>
        </div>
        <span style={{ width: 1, height: 18, background: "var(--line)" }}/>
        <span className="mono tnum" style={{ fontSize: 12, color: "var(--text)" }}>{now}</span>
        <span className="micro">{(new Date()).toDateString().slice(4)}</span>
      </div>

      {/* Center: source health */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, justifySelf: "center" }}>
        {["github","huggingface","youtube","blogs","papers"].map(k => {
          const h = sourceHealth[k]; const S = SOURCES[k];
          return (
            <div key={k} title={`${S.label} · last fetch ${h.last_fetch_min}m ago · ${h.items_24h} items / 24h`}
                 style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: 999, background: h.fresh ? S.color : "var(--text-lo)",
                             boxShadow: h.fresh ? `0 0 4px ${S.color}` : "none" }}/>
              <span className="mono" style={{ fontSize: 11, color: "var(--text)", letterSpacing: "0.04em", textTransform: "uppercase" }}>{S.abbr}</span>
              <span className="mono tnum" style={{ fontSize: 10, color: "var(--text-lo)" }}>{h.last_fetch_min}m</span>
              <Momentum delta={h.delta} />
            </div>
          );
        })}
      </div>

      {/* Right: actions */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button className="btn ghost" onClick={onRefresh} disabled={refreshing}
                style={{ opacity: refreshing ? 0.6 : 1 }}>
          <I.Refresh size={13}/> {refreshing ? "Refreshing…" : "Refresh"}
        </button>
        <button className="btn ghost icon" aria-label="notifications" onClick={() => {
          const sh = window.DD_DATA.sourceHealth || {};
          const lines = Object.entries(sh).map(([k, v]) => `${k}: ${v.items_24h} items${v.error ? " ⚠ " + v.error : ""}`);
          alert("Fetch status (24h):\n\n" + lines.join("\n"));
        }}><I.Bell size={14}/></button>
        <button className="btn ghost icon" onClick={onOpenTweaks} aria-label="settings"><I.Settings size={14}/></button>
        <span style={{ width: 1, height: 22, background: "var(--line)", margin: "0 4px" }}/>
        <div style={{
          width: 28, height: 28, borderRadius: 999,
          background: "linear-gradient(135deg, var(--signal), var(--src-youtube))",
          display: "grid", placeItems: "center", color: "#1A1100", fontWeight: 700, fontSize: 11,
        }}>JM</div>
      </div>
    </header>
  );
};

// ─── Agent rail ─────────────────────────────────────────────────────────────
const AgentCard = ({ a }) => {
  const logs = (a.logs && a.logs.length) ? a.logs : ["queued…"];
  const [logIdx, setLogIdx] = useState(Math.max(0, logs.length - 1));
  useEffect(() => {
    const id = setInterval(() => setLogIdx(i => (i + 1) % logs.length), 2400);
    return () => clearInterval(id);
  }, [logs.length]);
  return (
    <div style={{
      padding: "10px 12px",
      borderBottom: "1px solid var(--line)",
      position: "relative",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{
          width: 22, height: 22, borderRadius: 4, display: "grid", placeItems: "center",
          background: "var(--bg-3)", border: "1px solid var(--line-2)",
          color: "var(--signal)", fontFamily: "var(--font-mono)", fontSize: 12,
        }}>{a.icon}</div>
        <div style={{ flex: 1, minWidth: 0, lineHeight: 1.1 }}>
          <div style={{ color: "var(--text-hi)", fontWeight: 600, fontSize: 12.5 }}>{a.name}</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.04em", marginTop: 2,
                                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {a.task}
          </div>
        </div>
        <span className="mono tnum" style={{ fontSize: 10, color: "var(--signal)" }}>{Math.round(a.progress * 100)}%</span>
      </div>

      {/* Progress */}
      <div style={{ height: 3, background: "var(--bg-3)", borderRadius: 2, marginTop: 8, overflow: "hidden", position: "relative" }}>
        <div style={{ height: "100%", width: `${a.progress * 100}%`, background: "var(--signal)", borderRadius: 2 }}/>
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent)",
          animation: "scan 1.8s linear infinite",
        }}/>
      </div>

      {/* Live log */}
      <div className="mono" style={{
        marginTop: 8, fontSize: 10.5, color: "var(--text-mid)",
        background: "var(--bg-0)", border: "1px solid var(--line)",
        padding: "5px 7px", borderRadius: 3,
        display: "flex", alignItems: "center", gap: 6, minHeight: 22,
      }}>
        <span style={{ color: "var(--signal-up)" }}>›</span>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
          {logs[logIdx]}
        </span>
        <span className="blink">▍</span>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)" }}>{a.stage}</span>
        <span className="mono tnum" style={{ fontSize: 10, color: "var(--text-lo)" }}>~{a.eta_sec}s</span>
      </div>
    </div>
  );
};

const AGENT_OPTIONS = [
  ["topic_researcher", "Topic Researcher"],
  ["script_writer", "Script Writer"],
  ["thumbnail_director", "Thumbnail Director"],
  ["cross_poster", "Cross-Poster"],
];

const AgentRail = () => {
  const [active, setActive] = useState(window.DD_DATA.agents || []);
  const [recent, setRecent] = useState([]);
  const [picking, setPicking] = useState(false);

  const pull = async () => {
    if (!window.DDX) return;
    try {
      const snap = await window.DDX.agents();
      setActive(snap.active || []);
      setRecent(snap.recent_done || []);
    } catch (e) {}
  };

  useEffect(() => {
    pull();
    if (!window.DDX) return;
    const es = window.DDX.agentStream(() => pull());   // re-snapshot on any event
    const id = setInterval(pull, 3000);                // safety poll while running
    return () => { try { es.close(); } catch (_) {} clearInterval(id); };
  }, []);

  const dispatch = async (agent_type) => {
    setPicking(false);
    const top = window.DD_DATA.clusters[0] || {};
    try { await window.DDX.dispatch(agent_type, top.topic, top.slug); } catch (e) {}
    pull();
  };

  return (
    <aside className="rail" style={{ display: "flex", flexDirection: "column" }}>
      <div style={{
        padding: "12px 14px", borderBottom: "1px solid var(--line)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="label" style={{ color: "var(--text-hi)", fontWeight: 600 }}>Agents</span>
          <span className="chip" style={{ color: "var(--signal-up)", borderColor: "rgba(124,255,178,0.3)", background: "rgba(124,255,178,0.08)" }}>
            <span style={{ width: 5, height: 5, borderRadius: 999, background: "var(--signal-up)" }}/>
            {active.length} active
          </span>
        </div>
        <button className="btn ghost icon" aria-label="dispatch" onClick={() => setPicking(p => !p)}><I.Plus size={12}/></button>
      </div>

      {picking && (
        <div style={{ padding: "8px 14px", borderBottom: "1px solid var(--line)", display: "flex", flexWrap: "wrap", gap: 6 }}>
          {AGENT_OPTIONS.map(([type, label]) => (
            <button key={type} className="btn ghost" style={{ textTransform: "none", letterSpacing: 0 }}
                    onClick={() => dispatch(type)}>{label}</button>
          ))}
        </div>
      )}

      <div style={{ flex: 1, overflowY: "auto" }}>
        {active.length === 0 && (
          <div className="mono" style={{ padding: "16px 14px", fontSize: 11, color: "var(--text-lo)" }}>
            No agents running. Dispatch one ↑ or below.
          </div>
        )}
        {active.map(a => <AgentCard key={a.id} a={a}/>)}

        {/* Recent completions */}
        <div style={{ padding: "12px 14px 8px" }}>
          <div className="micro" style={{ marginBottom: 8 }}>Just finished</div>
          {recent.length === 0 && <div className="mono" style={{ fontSize: 10, color: "var(--text-vlo)" }}>nothing yet</div>}
          {recent.slice(0, 3).map(r => (
            <CompletedRow key={r.id} topic={r.task || r.name}
                          what={r.result_summary || "done"}
                          when={r.duration_sec != null ? `${r.duration_sec}s` : "·"} />
          ))}
        </div>
      </div>

      <div style={{ padding: "10px 14px", borderTop: "1px solid var(--line)" }}>
        <button className="btn primary" style={{ width: "100%", justifyContent: "center" }}
                onClick={() => setPicking(p => !p)}>
          <I.Plus size={12}/> Dispatch a new agent
        </button>
      </div>
    </aside>
  );
};

const CompletedRow = ({ topic, what, when }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: "1px dashed var(--line)" }}>
    <span style={{ color: "var(--signal-up)", fontFamily: "var(--font-mono)", fontSize: 11 }}>✓</span>
    <div style={{ flex: 1, minWidth: 0, lineHeight: 1.1 }}>
      <div style={{ color: "var(--text-hi)", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{topic}</div>
      <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2 }}>{what}</div>
    </div>
    <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)" }}>{when} ago</span>
  </div>
);

// ─── Copilot dock ───────────────────────────────────────────────────────────
const CopilotDock = ({ context }) => {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState("");
  const [model, setModel] = useState("");
  const submit = async () => {
    if (!q.trim()) return;
    setBusy(true); setAnswer("");
    try {
      const focused = (window.DD_DATA.clusters[0] || {}).slug;
      const r = await window.DDX.copilot(context, q, { focused_cluster: focused });
      setAnswer(r.answer || "No answer.");
      if (r.model) setModel(r.model);
    } catch (e) {
      setAnswer("Copilot is offline — check the LLM provider on the server.");
    } finally { setBusy(false); }
  };
  const modelLabel = (model || (window.DD_DATA.copilotModel) || "minimaxai/minimax-m2.7")
    .split("/").pop().replace(/-/g, " ").toUpperCase();
  const suggestions = {
    pulse: ["rank clusters by momentum", "which topic peaks tonight?", "what did I miss yesterday?"],
    brief: ["rewrite the hook punchier", "generate 3 contrarian titles", "what's the strongest counterpoint?"],
    clusters: ["which cluster has best demo value?", "draft a comparison outline", "what would Karpathy cover?"],
    thumbs: ["pick the winning thumbnail", "generate a variant with a face", "what colors maximize CTR?"],
    research: ["summarize all evidence", "extract 5 cited stats", "find a counter-source"],
    pipeline: ["what should I publish first?", "reschedule based on momentum", "any stale items?"],
  };
  const sugs = suggestions[context] || suggestions.pulse;

  return (
    <div className="dock" style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", alignItems: "center", gap: 12, padding: "0 16px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{
          width: 26, height: 26, borderRadius: 6,
          background: "linear-gradient(135deg, var(--signal), var(--src-papers))",
          display: "grid", placeItems: "center",
          boxShadow: "0 0 12px rgba(240,183,47,0.25)",
        }}>
          <I.Spark size={13} stroke="#1A1100" strokeWidth={2}/>
        </div>
        <div style={{ lineHeight: 1.1 }}>
          <div style={{ color: "var(--text-hi)", fontSize: 12, fontWeight: 600 }}>Copilot</div>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--text-lo)", letterSpacing: "0.06em" }}>CONTEXT · {context.toUpperCase()}</div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {answer ? (
          <div style={{
            flex: 1, padding: "8px 12px", background: "var(--bg-2)", border: "1px solid var(--line)",
            borderRadius: 6, color: "var(--text-hi)", fontSize: 12.5, lineHeight: 1.4,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>{answer}</div>
        ) : (
          <>
            <div style={{ display: "flex", gap: 6, overflow: "hidden" }}>
              {sugs.map((s, i) => (
                <button key={i} className="btn ghost" style={{ textTransform: "none", letterSpacing: "0" }}
                        onClick={() => { setQ(s); }}>
                  {s}
                </button>
              ))}
            </div>
          </>
        )}
        <div style={{ flex: 1, position: "relative" }}>
          <input
            value={q} onChange={e => setQ(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") submit(); }}
            placeholder="Ask the copilot about this view…"
            style={{
              width: "100%", height: 36, padding: "0 38px 0 14px",
              background: "var(--bg-2)", border: "1px solid var(--line-2)", borderRadius: 6,
              color: "var(--text-hi)", fontFamily: "var(--font-sans)", fontSize: 13,
              outline: "none",
            }}/>
          <button onClick={submit} disabled={busy} style={{
            position: "absolute", right: 4, top: 4, height: 28, width: 28,
            display: "grid", placeItems: "center",
            background: "var(--signal)", color: "#1A1100",
            border: "none", borderRadius: 4, cursor: "pointer",
            opacity: busy ? 0.5 : 1,
          }}>
            {busy ? <span className="blink">…</span> : <I.Send size={13} stroke="#1A1100" strokeWidth={1.8}/>}
          </button>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.06em" }}>{modelLabel}</span>
        <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--signal-up)", boxShadow: "0 0 4px var(--signal-up)" }}/>
      </div>
    </div>
  );
};

Object.assign(window, { Nav, Topbar, AgentRail, CopilotDock });
