// ClustersView — every cross-source story as a deep card, sourced and angled.
// Agents are real: they call the LLM, stream logs via SSE, and surface results inline.

// ── Agent event bus ───────────────────────────────────────────────────────
// Module-level singleton so one EventSource is shared across all AutoRow instances.
// Shape per run_id: { logs: string[], status: string, stage: string, progress: number, result: string|null }

const _agentState = new Map();
const _agentListeners = new Set();
const _notifyAgentListeners = () => _agentListeners.forEach(fn => {
  try {
    fn();
  } catch {}
});
let _agentES = null;
const _connectAgentStream = () => {
  if (_agentES && _agentES.readyState !== EventSource.CLOSED) return;
  _agentES = new EventSource("/api/agents/stream");
  _agentES.onmessage = e => {
    try {
      const ev = JSON.parse(e.data);
      const rid = ev.run_id || ev.run?.id;
      if (!rid) return;
      const s = _agentState.get(rid) || {
        logs: [],
        status: "queued",
        stage: "",
        progress: 0,
        result: null
      };
      if (ev.type === "started") {
        s.status = "queued";
        s.logs = [];
      } else if (ev.type === "status") {
        s.status = ev.status || s.status;
        s.stage = ev.stage || s.stage;
        s.progress = ev.progress ?? s.progress;
      } else if (ev.type === "log") {
        s.logs = [...s.logs, ev.line];
      } else if (ev.type === "done") {
        s.status = "done";
        s.progress = 1;
        // Fetch full generated content
        fetch(`/api/agents/${rid}/result`).then(r => r.json()).then(data => {
          const cur = _agentState.get(rid);
          if (cur && data.text) {
            cur.result = data.text;
            _agentState.set(rid, {
              ...cur
            });
            _notifyAgentListeners();
          }
        }).catch(() => {});
      }
      _agentState.set(rid, {
        ...s,
        logs: [...s.logs]
      });
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

const AgentOutputPanel = ({
  state,
  agentLabel,
  onClose
}) => {
  if (!state) return null;
  const isRunning = state.status === "running" || state.status === "queued";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      border: "1px solid var(--line)",
      borderTop: "none",
      borderBottomLeftRadius: 4,
      borderBottomRightRadius: 4,
      background: "var(--bg-0)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 2,
      background: "var(--line)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      width: `${(state.progress || 0) * 100}%`,
      background: state.status === "error" ? "var(--signal-down)" : "var(--signal)",
      borderRadius: 1,
      transition: "width 0.5s ease"
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 12px",
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, state.logs.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10.5,
      lineHeight: 1.7
    }
  }, state.logs.map((line, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: "flex",
      alignItems: "flex-start",
      gap: 6,
      color: i === state.logs.length - 1 && isRunning ? "var(--text-hi)" : "var(--text-lo)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal)",
      flexShrink: 0,
      marginTop: 1
    }
  }, "\u203A"), /*#__PURE__*/React.createElement("span", null, line))), isRunning && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 6,
      color: "var(--text-lo)",
      marginTop: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: 999,
      background: "var(--signal)",
      animation: "pulse 1s infinite",
      display: "inline-block"
    }
  }), /*#__PURE__*/React.createElement("span", null, state.stage || "running…"))), state.status === "error" && /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--signal-down)",
      fontSize: 12
    }
  }, "Agent failed \u2014 ensure ANTHROPIC_API_KEY is set and restart the server."), state.result && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("pre", {
    className: "mono",
    style: {
      whiteSpace: "pre-wrap",
      wordBreak: "break-word",
      fontSize: 11,
      lineHeight: 1.65,
      color: "var(--text)",
      margin: 0,
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 4,
      padding: "10px 12px",
      maxHeight: 380,
      overflowY: "auto"
    }
  }, state.result), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: () => navigator.clipboard?.writeText(state.result)
  }, "Copy"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: () => window.downloadScript && window.downloadScript(`${agentLabel}.md`, state.result)
  }, "Download"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), onClose && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: onClose
  }, "Hide")))));
};

// ── AutoRow — real dispatch, live streaming, inline result ────────────────

const AutoRow = ({
  icon,
  label,
  desc,
  agent,
  c
}) => {
  const [runId, setRunId] = useState(null);
  const [open, setOpen] = useState(false);
  const agentMap = useAgentStream();
  const state = runId ? agentMap.get(runId) || null : null;
  const isActive = state?.status === "running" || state?.status === "queued";
  const hasOutput = state && (state.logs.length > 0 || state.result || state.status === "error");
  const run = async () => {
    if (isActive) return;
    try {
      const res = await window.DDX.dispatch(agent, c.topic, c.slug);
      if (res?.run_id) {
        setRunId(res.run_id);
        setOpen(true);
      }
    } catch (e) {
      console.error("dispatch:", e);
    }
  };
  const btnLabel = !state ? "Run" : state.status === "queued" ? "Queued…" : state.status === "running" ? "Running…" : state.status === "done" ? "✓ Done" : "Error";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "24px 1fr auto",
      gap: 10,
      alignItems: "center",
      padding: "8px 10px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 4,
      borderBottomLeftRadius: open && hasOutput ? 0 : 4,
      borderBottomRightRadius: open && hasOutput ? 0 : 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal)",
      fontSize: 14,
      textAlign: "center"
    }
  }, icon), /*#__PURE__*/React.createElement("div", {
    style: {
      lineHeight: 1.15
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontSize: 12.5,
      fontWeight: 500
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      marginTop: 2
    }
  }, isActive ? state.stage || "running…" : desc)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 4,
      alignItems: "center"
    }
  }, hasOutput && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      padding: "3px 7px",
      fontSize: 10
    },
    onClick: () => setOpen(o => !o)
  }, open ? "Hide" : "View"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      padding: "3px 7px",
      fontSize: 10
    },
    disabled: isActive,
    onClick: run
  }, btnLabel))), open && hasOutput && /*#__PURE__*/React.createElement(AgentOutputPanel, {
    state: state,
    agentLabel: `${agent}-${c.slug}`,
    onClose: () => setOpen(false)
  }));
};

// ── Dispatch all — tracks all 4 agent run_ids concurrently ───────────────

const AGENT_TYPES = ["topic_researcher", "script_writer", "thumbnail_director", "cross_poster"];
const DispatchAllButton = ({
  c
}) => {
  const [runs, setRuns] = useState([]); // [{ agent, run_id }]
  const [dispatching, setDispatching] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const agentMap = useAgentStream();
  const dispatchAll = async () => {
    if (dispatching) return;
    setDispatching(true);
    setPanelOpen(true);
    const ids = [];
    for (const agent of AGENT_TYPES) {
      try {
        const res = await window.DDX.dispatch(agent, c.topic, c.slug);
        if (res?.run_id) ids.push({
          agent,
          run_id: res.run_id
        });
      } catch {}
    }
    setRuns(ids);
    setDispatching(false);
  };
  const doneCount = runs.filter(({
    run_id
  }) => agentMap.get(run_id)?.status === "done").length;
  const anyRunning = runs.some(({
    run_id
  }) => {
    const s = agentMap.get(run_id)?.status;
    return s === "running" || s === "queued";
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    style: {
      width: "100%",
      justifyContent: "center"
    },
    disabled: dispatching || anyRunning,
    onClick: dispatchAll
  }, /*#__PURE__*/React.createElement(I.Spark, {
    size: 11
  }), dispatching ? "Dispatching…" : anyRunning ? `Running… ${doneCount}/${runs.length} done` : runs.length ? "Run all again" : "Dispatch all agents"), panelOpen && runs.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, runs.map(({
    agent,
    run_id
  }) => {
    const state = agentMap.get(run_id);
    const hasOutput = state && (state.logs.length > 0 || state.result || state.status === "error");
    return /*#__PURE__*/React.createElement("div", {
      key: run_id,
      style: {
        background: "var(--bg-2)",
        border: "1px solid var(--line)",
        borderRadius: 4,
        overflow: "hidden"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "6px 10px",
        display: "flex",
        alignItems: "center",
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 10.5,
        color: "var(--text-mid)",
        flex: 1
      }
    }, agent.replace(/_/g, " ")), state && /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 10,
        color: state.status === "done" ? "var(--signal-up)" : state.status === "error" ? "var(--signal-down)" : "var(--signal)"
      }
    }, state.status)), state && hasOutput && /*#__PURE__*/React.createElement(AgentOutputPanel, {
      state: state,
      agentLabel: `${agent}-${run_id}`
    }));
  })));
};

// ── ClusterCard ───────────────────────────────────────────────────────────

const ClusterCard = ({
  c,
  expanded,
  onToggle
}) => {
  const S = window.DD_DATA.SOURCES;
  const primaryKey = c.sources && c.sources.length > 0 && S[c.sources[0]] ? c.sources[0] : Object.keys(S)[0];
  const primarySrc = S[primaryKey] || {
    color: "var(--signal)",
    label: "Source"
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      gap: 16,
      padding: "16px 18px",
      cursor: "pointer"
    },
    onClick: onToggle
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 64,
      height: 64,
      borderRadius: 8,
      display: "grid",
      placeItems: "center",
      background: `radial-gradient(circle at 30% 30%, ${primarySrc.color}33, ${primarySrc.color}08)`,
      border: `1px solid ${primarySrc.color}55`
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "mono tnum",
    style: {
      color: primarySrc.color,
      fontWeight: 700,
      fontSize: 22
    }
  }, c.creator_score)), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 22,
      fontWeight: 700,
      letterSpacing: "-0.015em",
      color: "var(--text-hi)",
      margin: 0
    }
  }, c.topic), /*#__PURE__*/React.createElement(FormatBadge, {
    format: c.best_content_format
  }), c.has_demoable_item && /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      color: "var(--signal-up)",
      borderColor: "rgba(124,255,178,0.3)",
      background: "rgba(124,255,178,0.05)"
    }
  }, "demoable"), /*#__PURE__*/React.createElement(Momentum, {
    delta: c.momentum,
    big: true
  })), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 13.5,
      lineHeight: 1.5,
      color: "var(--text)",
      margin: "8px 0 0",
      textWrap: "pretty",
      maxWidth: 760
    }
  }, c.why_this_is_a_story), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 14,
      marginTop: 12,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 4
    }
  }, c.sources.map(s => /*#__PURE__*/React.createElement(SourceChip, {
    key: s,
    src: s
  }))), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 1,
      height: 14,
      background: "var(--line)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: "var(--text-lo)"
    }
  }, "first seen ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)"
    }
  }, c.first_seen_hrs, "h ago"), " · ", c.related_items.length, " items", " · ", "avg signal ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)"
    }
  }, c.average_signal_score)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8,
      alignItems: "flex-end"
    }
  }, /*#__PURE__*/React.createElement(Waveform, {
    data: c.pulse,
    w: 140,
    h: 36,
    color: primarySrc.color
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      padding: "4px 8px"
    },
    onClick: event => {
      event.stopPropagation();
      onToggle();
    }
  }, expanded ? "−" : "+", " details"))), expanded && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.2fr 1fr",
      padding: "0 18px 18px",
      gap: 22,
      borderTop: "1px solid var(--line)",
      paddingTop: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 8
    }
  }, "Recommended angle"), /*#__PURE__*/React.createElement("p", {
    className: "serif",
    style: {
      fontSize: 17,
      fontStyle: "italic",
      lineHeight: 1.4,
      color: "var(--text-hi)",
      margin: 0,
      textWrap: "pretty"
    }
  }, c.recommended_angle), /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginTop: 18,
      marginBottom: 10
    }
  }, "Source evidence"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, c.related_items.map((it, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: "grid",
      gridTemplateColumns: "auto 1fr auto auto",
      gap: 12,
      alignItems: "center",
      padding: "8px 10px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 4
    }
  }, /*#__PURE__*/React.createElement(SourceChip, {
    src: it.source_type
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontSize: 12.5,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, it.url ? /*#__PURE__*/React.createElement("a", {
    href: it.url,
    target: "_blank",
    rel: "noreferrer",
    style: {
      color: "inherit",
      textDecoration: "none"
    },
    onClick: e => e.stopPropagation()
  }, it.title) : it.title), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      marginTop: 2
    }
  }, [it.stars && `★ ${it.stars}`, it.downloads && `↓ ${it.downloads}`, it.views && `▶ ${it.views}`, it.citations, it.source, it.channel].filter(Boolean).join(" · "), it.delta && /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal-up)",
      marginLeft: 6
    }
  }, it.delta))), /*#__PURE__*/React.createElement(ScoreBar, {
    value: it.signal_score,
    w: 50,
    label: false
  }), /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      fontSize: 11,
      color: "var(--text-hi)",
      fontWeight: 600,
      minWidth: 24,
      textAlign: "right"
    }
  }, it.signal_score))))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 8
    }
  }, "Make this into"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(ActionTile, {
    label: "Long-form",
    icon: /*#__PURE__*/React.createElement(I.YT, {
      size: 14
    }),
    sub: "14\u201318 min",
    hot: true,
    onClick: () => makeInto(c, "YouTube long-form")
  }), /*#__PURE__*/React.createElement(ActionTile, {
    label: "Short",
    icon: /*#__PURE__*/React.createElement(I.Play, {
      size: 11
    }),
    sub: "< 60s",
    onClick: () => makeInto(c, "YouTube short")
  }), /*#__PURE__*/React.createElement(ActionTile, {
    label: "Carousel",
    icon: /*#__PURE__*/React.createElement(I.Doc, {
      size: 14
    }),
    sub: "LinkedIn \xB7 8 slides",
    onClick: () => makeInto(c, "LinkedIn carousel")
  }), /*#__PURE__*/React.createElement(ActionTile, {
    label: "Newsletter",
    icon: /*#__PURE__*/React.createElement(I.Paper, {
      size: 14
    }),
    sub: "~1,200w",
    onClick: () => makeInto(c, "Newsletter")
  })), /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginTop: 18,
      marginBottom: 8
    }
  }, "Agentic actions \xB7 results stream in below each button"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement(AutoRow, {
    icon: "\uD83D\uDD0E",
    label: "Build research pack",
    desc: "leads + strategic brief + narrative hooks",
    agent: "topic_researcher",
    c: c
  }), /*#__PURE__*/React.createElement(AutoRow, {
    icon: "\u270E",
    label: "Draft video script",
    desc: "cold open + 3 sections + demo moment + CTA",
    agent: "script_writer",
    c: c
  }), /*#__PURE__*/React.createElement(AutoRow, {
    icon: "\u25A3",
    label: "Thumbnail concepts",
    desc: "6 visual variants with CTR reasoning",
    agent: "thumbnail_director",
    c: c
  }), /*#__PURE__*/React.createElement(AutoRow, {
    icon: "\u2197",
    label: "LinkedIn carousel",
    desc: "8 slides, direct tone, cite real data",
    agent: "cross_poster",
    c: c
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      marginTop: 18
    }
  }, /*#__PURE__*/React.createElement(DispatchAllButton, {
    c: c
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    title: "Save to pipeline",
    onClick: () => {
      if (!window.DDX) return;
      window.DDX.saveToPipeline({
        title: c.topic,
        working_title: c.topic,
        topic: c.topic,
        category: c.topic,
        format: c.best_content_format,
        creator_score: c.creator_score,
        signal_score: c.average_signal_score,
        pipeline_type: "creator",
        status: "idea"
      }).then(() => {
        alert("Saved to pipeline.");
        window.DDX.reload();
      });
    }
  }, /*#__PURE__*/React.createElement(I.Save, {
    size: 12
  }))))));
};

// ── helpers ───────────────────────────────────────────────────────────────

const makeInto = (c, format) => {
  if (!window.DDX) return;
  window.DDX.saveToPipeline({
    title: c.topic,
    working_title: c.topic,
    topic: c.topic,
    category: c.topic,
    format,
    creator_score: c.creator_score,
    signal_score: c.average_signal_score,
    pipeline_type: "creator",
    status: "idea"
  }).then(() => {
    alert(`Saved "${c.topic}" as ${format} idea.`);
    window.DDX.reload();
  });
};
const makeIntoCompilation = (comp, format) => {
  if (!window.DDX) return;
  window.DDX.saveToPipeline({
    title: comp.title,
    working_title: comp.title,
    topic: comp.title,
    category: "Compilation",
    format,
    creator_score: comp.creator_score,
    signal_score: comp.signal_score,
    pipeline_type: "creator",
    status: "idea"
  }).then(() => {
    alert(`Saved "${comp.title}" as ${format} compilation.`);
    window.DDX.reload();
  });
};
const CompilationCard = ({
  comp,
  expanded,
  onToggle
}) => {
  return /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      gap: 16,
      padding: "16px 18px",
      cursor: "pointer"
    },
    onClick: onToggle
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 64,
      height: 64,
      borderRadius: 8,
      display: "grid",
      placeItems: "center",
      background: `radial-gradient(circle at 30% 30%, var(--signal)33, var(--signal)08)`,
      border: `1px solid var(--signal)55`
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "mono tnum",
    style: {
      color: "var(--signal)",
      fontWeight: 700,
      fontSize: 22
    }
  }, comp.creator_score)), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 22,
      fontWeight: 700,
      letterSpacing: "-0.015em",
      color: "var(--text-hi)",
      margin: 0
    }
  }, comp.title), /*#__PURE__*/React.createElement(FormatBadge, {
    format: comp.recommended_format
  }), /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      color: "var(--signal-up)",
      borderColor: "rgba(124,255,178,0.3)",
      background: "rgba(124,255,178,0.05)"
    }
  }, "listicle")), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 13.5,
      lineHeight: 1.5,
      color: "var(--text)",
      margin: "8px 0 0",
      textWrap: "pretty",
      maxWidth: 760
    }
  }, comp.theme_description), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 14,
      marginTop: 12,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: "var(--text-lo)"
    }
  }, comp.items.length, " matched tools", " · ", "avg signal ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)"
    }
  }, comp.signal_score)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8,
      alignItems: "flex-end"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)"
    }
  }, "THEMED COMPILATION"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      padding: "4px 8px"
    },
    onClick: event => {
      event.stopPropagation();
      onToggle();
    }
  }, expanded ? "−" : "+", " details"))), expanded && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.2fr 1fr",
      padding: "0 18px 18px",
      gap: 22,
      borderTop: "1px solid var(--line)",
      paddingTop: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 10
    }
  }, "Matched Tools in Listicle"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, comp.items.map((it, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: "grid",
      gridTemplateColumns: "24px 1fr auto",
      gap: 12,
      alignItems: "flex-start",
      padding: "10px 12px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--text-lo)",
      fontSize: 12,
      marginTop: 1
    }
  }, i + 1, "."), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontSize: 13,
      fontWeight: 600
    }
  }, it.url ? /*#__PURE__*/React.createElement("a", {
    href: it.url,
    target: "_blank",
    rel: "noreferrer",
    style: {
      color: "inherit",
      textDecoration: "none"
    },
    onClick: e => e.stopPropagation()
  }, it.title) : it.title), it.description && /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 11.5,
      color: "var(--text)",
      margin: "4px 0 0",
      lineHeight: 1.4
    }
  }, it.description), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 9.5,
      color: "var(--text-lo)",
      marginTop: 4
    }
  }, "source: ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)"
    }
  }, it.source_type), " · ", "creator score: ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)"
    }
  }, it.creator_score), " · ", "signal: ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)"
    }
  }, it.signal_score))))))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 8
    }
  }, "Make this into"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(ActionTile, {
    label: "YouTube Listicle",
    icon: /*#__PURE__*/React.createElement(I.YT, {
      size: 14
    }),
    sub: "10\u201315 min",
    hot: true,
    onClick: () => makeIntoCompilation(comp, "YouTube compilation")
  }), /*#__PURE__*/React.createElement(ActionTile, {
    label: "Shorts Reel",
    icon: /*#__PURE__*/React.createElement(I.Play, {
      size: 11
    }),
    sub: "< 60s",
    onClick: () => makeIntoCompilation(comp, "YouTube short compilation")
  }), /*#__PURE__*/React.createElement(ActionTile, {
    label: "LinkedIn Post",
    icon: /*#__PURE__*/React.createElement(I.Doc, {
      size: 14
    }),
    sub: "Text + Link",
    onClick: () => makeIntoCompilation(comp, "LinkedIn post")
  }), /*#__PURE__*/React.createElement(ActionTile, {
    label: "Newsletter Brief",
    icon: /*#__PURE__*/React.createElement(I.Paper, {
      size: 14
    }),
    sub: "~1,500w",
    onClick: () => makeIntoCompilation(comp, "Newsletter compilation")
  })), /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginTop: 18,
      marginBottom: 8
    }
  }, "Agentic actions \xB7 results stream in below each button"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement(AutoRow, {
    icon: "\u270E",
    label: "Draft listicle script",
    desc: "cold open + countdown pitches + setup + screen cues",
    agent: "script_writer",
    c: {
      topic: comp.title,
      slug: comp.slug
    }
  }), /*#__PURE__*/React.createElement(AutoRow, {
    icon: "\uD83D\uDD0E",
    label: "Compile research pack",
    desc: "multi-repo lead analysis + contrarian shifts",
    agent: "topic_researcher",
    c: {
      topic: comp.title,
      slug: comp.slug
    }
  }), /*#__PURE__*/React.createElement(AutoRow, {
    icon: "\u25A3",
    label: "Listicle thumbnail concepts",
    desc: "6 visual layout variants with CTR projections",
    agent: "thumbnail_director",
    c: {
      topic: comp.title,
      slug: comp.slug
    }
  })))));
};
const ActionTile = ({
  label,
  icon,
  sub,
  hot,
  onClick
}) => /*#__PURE__*/React.createElement("button", {
  onClick: onClick,
  style: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 12px",
    background: hot ? "rgba(240,183,47,0.06)" : "var(--bg-2)",
    border: `1px solid ${hot ? "rgba(240,183,47,0.45)" : "var(--line-2)"}`,
    borderRadius: 4,
    cursor: "pointer",
    textAlign: "left",
    color: hot ? "var(--text-hi)" : "var(--text)"
  }
}, /*#__PURE__*/React.createElement("span", {
  style: {
    color: hot ? "var(--signal)" : "var(--text-mid)"
  }
}, icon), /*#__PURE__*/React.createElement("span", {
  style: {
    display: "flex",
    flexDirection: "column",
    lineHeight: 1.1
  }
}, /*#__PURE__*/React.createElement("span", {
  style: {
    fontSize: 12.5,
    fontWeight: 600
  }
}, label), /*#__PURE__*/React.createElement("span", {
  className: "mono",
  style: {
    fontSize: 10,
    color: "var(--text-lo)",
    marginTop: 2
  }
}, sub)), hot && /*#__PURE__*/React.createElement("span", {
  className: "mono",
  style: {
    marginLeft: "auto",
    fontSize: 9.5,
    color: "var(--signal)",
    letterSpacing: "0.05em"
  }
}, "RECOMMENDED"));

// ── ClustersView ──────────────────────────────────────────────────────────

const ClustersView = ({
  onJump,
  selectedClusterSlug,
  setSelectedClusterSlug
}) => {
  const {
    clusters,
    compilations
  } = window.DD_DATA;
  const [activeTab, setActiveTab] = useState("single"); // "single" or "listicle"
  const initialSlug = clusters.some(cluster => cluster.slug === selectedClusterSlug) ? selectedClusterSlug : clusters[0] ? clusters[0].slug : null;
  const [expandedId, setExpandedId] = useState(initialSlug);
  const [sortMode, setSortMode] = useState("momentum");
  const [viewMode, setViewMode] = useState("list");
  useEffect(() => {
    if (selectedClusterSlug && clusters.some(cluster => cluster.slug === selectedClusterSlug)) {
      setExpandedId(selectedClusterSlug);
    }
  }, [selectedClusterSlug]);
  const selectCluster = slug => {
    setExpandedId(slug);
    if (setSelectedClusterSlug) setSelectedClusterSlug(slug);
  };
  if (!clusters.length) {
    return /*#__PURE__*/React.createElement("div", {
      className: "panel crosshair",
      style: {
        padding: "48px 22px",
        textAlign: "center"
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "ch-bl"
    }), /*#__PURE__*/React.createElement("span", {
      className: "ch-br"
    }), /*#__PURE__*/React.createElement("div", {
      className: "label",
      style: {
        marginBottom: 10
      }
    }, "Clusters"), /*#__PURE__*/React.createElement("h1", {
      className: "serif",
      style: {
        fontSize: 26,
        color: "var(--text-hi)",
        margin: "0 0 12px",
        fontWeight: 600
      }
    }, "No cross-source stories yet"), /*#__PURE__*/React.createElement("p", {
      style: {
        color: "var(--text-mid)",
        maxWidth: 420,
        margin: "0 auto 18px"
      }
    }, "Clusters appear once sources are fetched and the same topic shows up across families."), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      onClick: () => window.DDX && window.DDX.refresh()
    }, "Fetch sources now"));
  }
  const sorted = [...clusters].sort((a, b) => {
    if (sortMode === "score") return b.creator_score - a.creator_score;
    if (sortMode === "fresh") return a.first_seen_hrs - b.first_seen_hrs;
    return b.momentum - a.momentum;
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel crosshair",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "ch-bl"
  }), /*#__PURE__*/React.createElement("span", {
    className: "ch-br"
  }), /*#__PURE__*/React.createElement(PanelHeader, {
    no: "01",
    actions: /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 12,
        alignItems: "center"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        background: "var(--bg-2)",
        padding: "2px",
        borderRadius: "4px",
        border: "1px solid var(--line)"
      }
    }, /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => {
        const firstSlug = clusters[0] ? clusters[0].slug : null;
        setActiveTab("single");
        setExpandedId(firstSlug);
        if (firstSlug && setSelectedClusterSlug) setSelectedClusterSlug(firstSlug);
      },
      style: {
        padding: "3px 8px",
        fontSize: 11,
        background: activeTab === "single" ? "var(--bg-0)" : "transparent",
        borderColor: "transparent",
        color: activeTab === "single" ? "var(--text-hi)" : "var(--text-lo)"
      }
    }, "Single Trends"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => {
        setActiveTab("listicle");
        setExpandedId(compilations && compilations[0] ? compilations[0].slug : null);
      },
      style: {
        padding: "3px 8px",
        fontSize: 11,
        background: activeTab === "listicle" ? "var(--bg-0)" : "transparent",
        borderColor: "transparent",
        color: activeTab === "listicle" ? "var(--text-hi)" : "var(--text-lo)"
      }
    }, "Listicle Compilations")), activeTab === "single" && ["momentum", "score", "fresh"].map(m => /*#__PURE__*/React.createElement("button", {
      key: m,
      className: "btn ghost",
      onClick: () => setSortMode(m),
      style: {
        color: sortMode === m ? "var(--text-hi)" : "var(--text-mid)",
        borderColor: sortMode === m ? "var(--signal)" : "var(--line-2)"
      }
    }, m)), activeTab === "single" && /*#__PURE__*/React.createElement("div", {
      className: "discover-view-toggle"
    }, /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setViewMode("list"),
      "aria-pressed": viewMode === "list"
    }, "List"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setViewMode("radar"),
      "aria-pressed": viewMode === "radar"
    }, "Radar")))
  }, activeTab === "single" ? `Content clusters · ${clusters.length} active stories` : `Weekly themed listicles · ${(compilations || []).length} compilations`), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "16px 20px"
    }
  }, activeTab === "single" ? /*#__PURE__*/React.createElement("p", {
    className: "serif",
    style: {
      fontSize: 22,
      lineHeight: 1.3,
      color: "var(--text-hi)",
      margin: 0,
      fontStyle: "italic",
      maxWidth: 720
    }
  }, "A cluster is a topic appearing across", " ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal)"
    }
  }, "two or more source families"), " in the last week. Expand any story \u2014 agents run live, stream logs, and deliver results inline.") : /*#__PURE__*/React.createElement("p", {
    className: "serif",
    style: {
      fontSize: 22,
      lineHeight: 1.3,
      color: "var(--text-hi)",
      margin: 0,
      fontStyle: "italic",
      maxWidth: 720
    }
  }, "Weekly compilations group the highest-signal developer tools under", " ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal)"
    }
  }, "high-demand YouTube themes"), ". Draft countdown script storyboards, setup commands, and CTR-optimized listicle layouts."))), activeTab === "single" && viewMode === "radar" ? /*#__PURE__*/React.createElement("div", {
    className: "panel discover-radar-panel"
  }, /*#__PURE__*/React.createElement(TrendRadar, {
    clusters: sorted,
    selectedSlug: expandedId,
    onSelect: selectCluster
  }), (() => {
    const selected = clusters.find(cluster => cluster.slug === expandedId) || clusters[0];
    if (!selected) return null;
    return /*#__PURE__*/React.createElement("div", {
      className: "discover-radar-detail"
    }, /*#__PURE__*/React.createElement("span", {
      className: "micro"
    }, "Selected signal"), /*#__PURE__*/React.createElement("h2", null, selected.topic), /*#__PURE__*/React.createElement("p", null, selected.why_this_is_a_story), /*#__PURE__*/React.createElement("div", {
      className: "discover-radar-detail__metrics"
    }, /*#__PURE__*/React.createElement("span", null, "Creator ", /*#__PURE__*/React.createElement("strong", null, selected.creator_score)), /*#__PURE__*/React.createElement("span", null, "Signal ", /*#__PURE__*/React.createElement("strong", null, selected.average_signal_score)), /*#__PURE__*/React.createElement("span", null, "Sources ", /*#__PURE__*/React.createElement("strong", null, selected.source_count))), /*#__PURE__*/React.createElement("div", {
      className: "discover-radar-detail__actions"
    }, /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      onClick: () => onJump("brief", selected.slug)
    }, "Open brief"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setViewMode("list")
    }, "View evidence")));
  })()) : activeTab === "single" ? sorted.map(c => /*#__PURE__*/React.createElement(ClusterCard, {
    key: c.slug,
    c: c,
    expanded: expandedId === c.slug,
    onToggle: () => {
      const next = expandedId === c.slug ? null : c.slug;
      setExpandedId(next);
      if (next && setSelectedClusterSlug) setSelectedClusterSlug(next);
    }
  })) : !compilations || compilations.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      padding: "24px",
      textAlign: "center",
      color: "var(--text-lo)"
    }
  }, "No weekly themed compilations generated yet.") : compilations.map(comp => /*#__PURE__*/React.createElement(CompilationCard, {
    key: comp.slug,
    comp: comp,
    expanded: expandedId === comp.slug,
    onToggle: () => setExpandedId(expandedId === comp.slug ? null : comp.slug)
  })));
};
window.ClustersView = ClustersView;