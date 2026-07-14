function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// AppShell — nav, topbar, agent rail, copilot dock
const {
  useState,
  useEffect,
  useMemo,
  useRef,
  useCallback
} = React;

// ─── Left nav ───────────────────────────────────────────────────────────────
const NavItem = ({
  icon,
  label,
  sub,
  active,
  hot,
  onClick
}) => /*#__PURE__*/React.createElement("button", {
  onClick: onClick,
  className: `nav-item${active ? " nav-item--active" : ""}`,
  style: {
    display: "grid",
    gridTemplateColumns: "20px 1fr auto",
    alignItems: "center",
    columnGap: 10,
    width: "100%",
    textAlign: "left",
    padding: "9px 12px",
    background: active ? "var(--bg-3)" : "transparent",
    color: active ? "var(--text-hi)" : "var(--text)",
    border: "none",
    borderLeft: `2px solid ${active ? "var(--signal)" : "transparent"}`,
    cursor: "pointer",
    fontFamily: "var(--font-sans)",
    fontSize: 13,
    transition: "background 120ms, color 120ms, border-color 120ms"
  }
}, /*#__PURE__*/React.createElement("span", {
  style: {
    color: active ? "var(--signal)" : "var(--text-mid)",
    display: "flex"
  }
}, icon), /*#__PURE__*/React.createElement("span", {
  style: {
    display: "flex",
    flexDirection: "column",
    lineHeight: 1.15
  }
}, /*#__PURE__*/React.createElement("span", {
  style: {
    fontWeight: active ? 600 : 500
  }
}, label), sub && /*#__PURE__*/React.createElement("span", {
  className: "mono",
  style: {
    fontSize: 10,
    color: "var(--text-lo)",
    marginTop: 2,
    letterSpacing: "0.04em"
  }
}, sub)), hot && /*#__PURE__*/React.createElement("span", {
  className: "mono tnum",
  style: {
    fontSize: 10,
    color: "var(--signal-up)",
    background: "rgba(124,255,178,0.10)",
    border: "1px solid rgba(124,255,178,0.3)",
    padding: "1px 5px",
    borderRadius: 999
  }
}, hot));
const Nav = ({
  view,
  setView,
  onClose
}) => {
  const freshCount = useMemo(() => {
    if (!window.DD_DATA || !window.DD_DATA.clusters) return 0;
    return window.DD_DATA.clusters.filter(c => c.first_seen_hrs <= 24).length;
  }, [window.DD_DATA?.clusters]);
  const workflowItems = [{
    key: "today",
    icon: /*#__PURE__*/React.createElement(I.Pulse, {
      size: 15
    }),
    label: "Today",
    sub: "decide and act",
    hot: freshCount > 0 ? `${freshCount} new` : null
  }, {
    key: "clusters",
    icon: /*#__PURE__*/React.createElement(I.Cluster, {
      size: 15
    }),
    label: "Discover",
    sub: "signals and stories"
  }, {
    key: "studio",
    icon: /*#__PURE__*/React.createElement(I.Studio, {
      size: 15
    }),
    label: "Produce",
    sub: "multi-format drafts"
  }, {
    key: "pipeline",
    icon: /*#__PURE__*/React.createElement(I.Pipeline, {
      size: 15
    }),
    label: "Publish",
    sub: "pipeline and calendar"
  }, {
    key: "benchmarks",
    icon: /*#__PURE__*/React.createElement(I.Trend, {
      size: 15
    }),
    label: "Insights",
    sub: "AI model benchmarks"
  }];
  const toolItems = [{
    key: "research",
    icon: /*#__PURE__*/React.createElement(I.Research, {
      size: 15
    }),
    label: "Research",
    sub: "evidence packs"
  }, {
    key: "thumbs",
    icon: /*#__PURE__*/React.createElement(I.Thumb, {
      size: 15
    }),
    label: "Thumb Lab",
    sub: "title and thumbnail"
  }];
  return /*#__PURE__*/React.createElement("nav", {
    id: "primary-navigation",
    className: "nav",
    style: {
      display: "flex",
      flexDirection: "column"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "16px 16px 14px",
      borderBottom: "1px solid var(--line)",
      display: "flex",
      alignItems: "center",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 28,
      height: 28,
      borderRadius: 6,
      background: "linear-gradient(135deg, var(--signal) 0%, var(--signal-hot) 100%)",
      display: "grid",
      placeItems: "center",
      boxShadow: "0 0 0 1px rgba(240,183,47,0.4), 0 4px 12px rgba(240,183,47,0.25)"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 16 16",
    fill: "#1A1100"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M2 13 L7 3 L9 7 L12 7 L14 13 Z"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      lineHeight: 1.1,
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontWeight: 700,
      fontSize: 15,
      letterSpacing: "-0.01em"
    }
  }, "DailyDex"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 9.5,
      color: "var(--text-lo)",
      letterSpacing: "0.12em",
      marginTop: 2
    }
  }, "CREATOR \xB7 COCKPIT")), /*#__PURE__*/React.createElement("button", {
    className: "nav-mobile-close",
    "aria-label": "Close navigation",
    onClick: onClose
  }, /*#__PURE__*/React.createElement(I.X, {
    size: 14
  }))), /*#__PURE__*/React.createElement(PersonaBadge, {
    onClick: () => setView("settings")
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "8px 0",
      display: "flex",
      flexDirection: "column",
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      padding: "8px 16px 4px"
    }
  }, "Workflow"), workflowItems.map(it => /*#__PURE__*/React.createElement(NavItem, _extends({
    key: it.key
  }, it, {
    active: view === it.key,
    onClick: () => setView(it.key)
  }))), /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      padding: "14px 16px 4px"
    }
  }, "Tools"), toolItems.map(it => /*#__PURE__*/React.createElement(NavItem, _extends({
    key: it.key
  }, it, {
    active: view === it.key,
    onClick: () => setView(it.key)
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "8px 0",
      borderTop: "1px solid var(--line)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      padding: "8px 16px 4px"
    }
  }, "Config"), /*#__PURE__*/React.createElement(NavItem, {
    key: "settings",
    icon: /*#__PURE__*/React.createElement(I.Settings, {
      size: 15
    }),
    label: "Settings",
    sub: "BYOK \xB7 API keys",
    active: view === "settings",
    onClick: () => setView("settings")
  })), /*#__PURE__*/React.createElement("div", {
    className: "nav-footnote"
  }, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Private workspace"), /*#__PURE__*/React.createElement("span", null, "Actions and source state now live on Today.")));
};
const PersonaBadge = ({
  onClick
}) => {
  const persona = window.__tweaks?.persona || "multi";
  const p = window.DD_DATA.personas[persona] || window.DD_DATA.personas.multi || Object.values(window.DD_DATA.personas)[0];
  if (!p) return null;
  return /*#__PURE__*/React.createElement("button", {
    className: "persona-badge",
    onClick: onClick,
    style: {
      margin: "12px 12px 4px",
      padding: "10px 12px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 6,
      textAlign: "left",
      cursor: "pointer",
      fontFamily: "var(--font-sans)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro"
  }, "Persona"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontWeight: 600,
      marginTop: 4,
      fontSize: 13
    }
  }, p.label), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      marginTop: 2,
      letterSpacing: "0.04em"
    }
  }, p.sub));
};

// ─── Topbar ─────────────────────────────────────────────────────────────────
const Topbar = ({
  now,
  onOpenSettings,
  onRefresh,
  refreshing,
  onToggleAgents,
  railOpen,
  onToggleNav,
  navOpen
}) => {
  const {
    sourceHealth = {},
    SOURCES = {}
  } = window.DD_DATA;
  const sourceKeys = Object.keys(SOURCES || {});
  const issueCount = sourceKeys.filter(key => {
    const health = sourceHealth[key] || {};
    return health.error || health.status === "failed" || health.using_cache;
  }).length;
  const knownCount = sourceKeys.filter(key => sourceHealth[key]?.last_fetch_min != null).length;
  const staleCount = sourceKeys.filter(key => sourceHealth[key]?.last_fetch_min != null && !sourceHealth[key]?.fresh).length;
  const allCurrent = sourceKeys.length > 0 && knownCount === sourceKeys.length && staleCount === 0 && issueCount === 0;
  const statusLabel = issueCount > 0 ? `${issueCount} source issue${issueCount === 1 ? "" : "s"}` : staleCount > 0 ? `${staleCount} source${staleCount === 1 ? "" : "s"} stale` : allCurrent ? "Sources current" : knownCount > 0 ? `${knownCount}/${sourceKeys.length} sources reporting` : "Awaiting first fetch";
  const identity = window.DD_DATA.creator_identity || {};
  const initials = (identity.name || identity.email || "DD").split(/\s|@/).filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join("") || "DD";
  const activeAgents = window.DD_DATA.stats?.active_agents_count || 0;
  return /*#__PURE__*/React.createElement("header", {
    className: "topbar",
    style: {
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      alignItems: "center",
      padding: "0 16px",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "topbar-left",
    style: {
      display: "flex",
      alignItems: "center",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost icon topbar-menu",
    "aria-label": "Open navigation",
    "aria-controls": "primary-navigation",
    "aria-expanded": navOpen,
    onClick: onToggleNav
  }, /*#__PURE__*/React.createElement(I.Menu, {
    size: 15
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 7,
      height: 7,
      borderRadius: 999,
      background: issueCount ? "var(--signal-down)" : allCurrent ? "var(--signal-up)" : knownCount ? "var(--signal)" : "var(--text-lo)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: issueCount ? "var(--signal-down)" : allCurrent ? "var(--text-mid)" : knownCount ? "var(--signal)" : "var(--text-mid)",
      letterSpacing: "0.04em"
    }
  }, statusLabel)), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 1,
      height: 18,
      background: "var(--line)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      fontSize: 12,
      color: "var(--text)"
    }
  }, now)), /*#__PURE__*/React.createElement("div", {
    className: "topbar-sources",
    style: {
      display: "flex",
      alignItems: "center",
      gap: 14,
      justifySelf: "center"
    }
  }, sourceKeys.map(k => {
    const h = sourceHealth[k] || {};
    const S = SOURCES[k];
    const age = h.last_fetch_min == null ? "--" : `${h.last_fetch_min}m`;
    return /*#__PURE__*/React.createElement("div", {
      key: k,
      title: `${S.label} - ${h.item_count || 0} items in latest fetch${h.error ? ` - ${h.error}` : ""}`,
      style: {
        display: "flex",
        alignItems: "center",
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 6,
        height: 6,
        borderRadius: 999,
        background: h.error ? "var(--signal-down)" : h.fresh ? S.color : "var(--text-lo)"
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 11,
        color: "var(--text)",
        letterSpacing: "0.04em",
        textTransform: "uppercase"
      }
    }, S.abbr), /*#__PURE__*/React.createElement("span", {
      className: "mono tnum",
      style: {
        fontSize: 10,
        color: "var(--text-lo)"
      }
    }, age));
  })), /*#__PURE__*/React.createElement("div", {
    className: "topbar-actions",
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: onRefresh,
    disabled: refreshing,
    style: {
      opacity: refreshing ? 0.6 : 1
    }
  }, /*#__PURE__*/React.createElement(I.Refresh, {
    size: 13
  }), " ", refreshing ? "Refreshing…" : "Refresh"), /*#__PURE__*/React.createElement("button", {
    className: `btn ghost${railOpen ? " is-active" : ""}`,
    onClick: onToggleAgents,
    "aria-expanded": railOpen
  }, /*#__PURE__*/React.createElement(I.Spark, {
    size: 13
  }), " Agents", activeAgents ? ` ${activeAgents}` : ""), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost icon",
    onClick: onOpenSettings,
    "aria-label": "Open settings"
  }, /*#__PURE__*/React.createElement(I.Settings, {
    size: 14
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 1,
      height: 22,
      background: "var(--line)",
      margin: "0 4px"
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "topbar-avatar",
    title: identity.name || identity.email || "DailyDex creator",
    style: {
      width: 28,
      height: 28,
      borderRadius: 999,
      background: identity.avatar ? `url(${identity.avatar}) center/cover` : "linear-gradient(135deg, var(--signal), var(--src-youtube))",
      display: "grid",
      placeItems: "center",
      color: "#1A1100",
      fontWeight: 700,
      fontSize: 11
    }
  }, identity.avatar ? "" : initials)));
};

// ─── Agent rail ─────────────────────────────────────────────────────────────
const AgentCard = ({
  a
}) => {
  const logs = a.logs && a.logs.length ? a.logs : ["queued…"];
  const [logIdx, setLogIdx] = useState(Math.max(0, logs.length - 1));
  useEffect(() => {
    const id = setInterval(() => setLogIdx(i => (i + 1) % logs.length), 2400);
    return () => clearInterval(id);
  }, [logs.length]);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 12px",
      borderBottom: "1px solid var(--line)",
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 22,
      height: 22,
      borderRadius: 4,
      display: "grid",
      placeItems: "center",
      background: "var(--bg-3)",
      border: "1px solid var(--line-2)",
      color: "var(--signal)",
      fontFamily: "var(--font-mono)",
      fontSize: 12
    }
  }, a.icon), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0,
      lineHeight: 1.1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontWeight: 600,
      fontSize: 12.5
    }
  }, a.name), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      letterSpacing: "0.04em",
      marginTop: 2,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, a.task)), /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      fontSize: 10,
      color: "var(--signal)"
    }
  }, Math.round(a.progress * 100), "%")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 3,
      background: "var(--bg-3)",
      borderRadius: 2,
      marginTop: 8,
      overflow: "hidden",
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      width: `${a.progress * 100}%`,
      background: "var(--signal)",
      borderRadius: 2
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent)",
      animation: "scan 1.8s linear infinite"
    }
  })), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      marginTop: 8,
      fontSize: 10.5,
      color: "var(--text-mid)",
      background: "var(--bg-0)",
      border: "1px solid var(--line)",
      padding: "5px 7px",
      borderRadius: 3,
      display: "flex",
      alignItems: "center",
      gap: 6,
      minHeight: 22
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal-up)"
    }
  }, "\u203A"), /*#__PURE__*/React.createElement("span", {
    style: {
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
      flex: 1
    }
  }, logs[logIdx]), /*#__PURE__*/React.createElement("span", {
    className: "blink"
  }, "\u258D")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      marginTop: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)"
    }
  }, a.stage), /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      fontSize: 10,
      color: "var(--text-lo)"
    }
  }, a.eta_sec != null ? `~${a.eta_sec}s` : "")));
};
const EditorialBoard = () => {
  const [briefing, setBriefing] = useState(window.DD_DATA?.editorial_briefing || null);
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [msg, setMsg] = useState("");
  const [expanded, setExpanded] = useState(false);
  const briefingRef = useRef(null);
  const verified = briefing?.status === "ready";
  const approved = briefing?.status === "approved";
  useEffect(() => {
    setBriefing(window.DD_DATA?.editorial_briefing || null);
  }, [window.DD_DATA?.editorial_briefing?.generated_at]);

  // Use a ref to manage innerHTML lifecycle and prevent detached DOM leaks
  useEffect(() => {
    if (briefingRef.current && briefing?.briefing) {
      briefingRef.current.innerHTML = safeMarkdown(briefing.briefing);
    }
    return () => {
      if (briefingRef.current) briefingRef.current.innerHTML = '';
    };
  }, [briefing?.briefing]);
  const handleRegen = async () => {
    setLoading(true);
    setMsg("");
    try {
      const res = await fetch("/api/editorial/briefing", {
        method: "POST"
      });
      if (res.ok) {
        const result = await res.json();
        setBriefing(result);
        if (window.DDX) await window.DDX.reload();
        setMsg(result.status === "ready" ? "Editorial plan regenerated." : result.note || "No verified plan was generated.");
      } else {
        setMsg("Failed to regenerate.");
      }
    } catch (e) {
      setMsg("Error regenerating briefing");
    } finally {
      setLoading(false);
    }
  };
  const handleApprove = async () => {
    if (!verified) return;
    setApproving(true);
    setMsg("");
    try {
      const res = await fetch("/api/editorial/approve", {
        method: "POST"
      });
      if (res.ok) {
        const result = await res.json();
        setMsg(`Approved! Saved ${result.saved_count} topics and dispatched agents.`);
        if (window.DDX) await window.DDX.reload();
      } else {
        const err = await res.json();
        setMsg(err.error || "Approval failed");
      }
    } catch (e) {
      setMsg("Failed to approve & queue");
    } finally {
      setApproving(false);
    }
  };
  if (!briefing || !briefing.briefing) {
    return /*#__PURE__*/React.createElement("section", {
      className: "panel today-editorial",
      "aria-labelledby": "editorial-title"
    }, /*#__PURE__*/React.createElement(PanelHeader, {
      no: "PLAN"
    }, /*#__PURE__*/React.createElement("span", {
      id: "editorial-title"
    }, "Editorial plan")), /*#__PURE__*/React.createElement("div", {
      className: "today-editorial__empty"
    }, /*#__PURE__*/React.createElement("span", {
      className: "micro"
    }, "Optional strategy pass"), /*#__PURE__*/React.createElement("strong", null, "Turn the top signals into a cross-format production plan."), /*#__PURE__*/React.createElement("p", null, "Generate this only when you want an LLM synthesis. Opening Today never invokes a model."), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: handleRegen,
      disabled: loading
    }, loading ? "Generating..." : "Generate editorial plan"), msg && /*#__PURE__*/React.createElement("span", {
      className: "today-inline-message",
      role: "status"
    }, msg)));
  }
  return /*#__PURE__*/React.createElement("section", {
    className: "panel today-editorial",
    "aria-labelledby": "editorial-title"
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "PLAN"
  }, /*#__PURE__*/React.createElement("span", {
    id: "editorial-title"
  }, "Editorial plan")), /*#__PURE__*/React.createElement("div", {
    className: "today-editorial__body"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal)",
      display: "flex"
    }
  }, /*#__PURE__*/React.createElement(I.Spark, {
    size: 14
  })), /*#__PURE__*/React.createElement("span", {
    className: "micro",
    style: {
      letterSpacing: "0.06em",
      color: "var(--text-hi)",
      fontWeight: 600
    }
  }, "Cross-format strategy")), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 9,
      color: verified ? "var(--signal-up)" : "var(--signal)",
      textTransform: "uppercase"
    }
  }, verified ? "Verified synthesis" : briefing.status || "Unverified")), !verified && briefing.note && /*#__PURE__*/React.createElement("div", {
    className: "today-editorial__note"
  }, briefing.note), /*#__PURE__*/React.createElement("div", {
    style: {
      maxHeight: expanded ? "300px" : "110px",
      overflowY: "auto",
      fontSize: 12,
      color: "var(--text)",
      lineHeight: 1.4,
      marginBottom: 10,
      position: "relative",
      borderBottom: expanded ? "none" : "1px dashed var(--line)",
      paddingBottom: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "briefing-markdown",
    ref: briefingRef
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 10,
      padding: "4px 8px",
      height: "auto"
    },
    onClick: () => setExpanded(e => !e)
  }, expanded ? "Show Less" : "Expand Plan"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost icon",
    style: {
      padding: "4px 8px",
      height: "auto",
      minWidth: 0
    },
    onClick: handleRegen,
    disabled: loading,
    title: "Regenerate plan"
  }, loading ? "..." : /*#__PURE__*/React.createElement(I.Refresh, {
    size: 10
  })), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    style: {
      fontSize: 11,
      padding: "4px 10px",
      height: "auto",
      background: "linear-gradient(90deg, var(--signal) 0%, var(--signal-hot) 100%)",
      border: "none",
      color: "#1a1100",
      fontWeight: 600
    },
    onClick: handleApprove,
    disabled: approving || !verified
  }, approving ? "Queuing..." : verified ? "Approve & Queue All" : approved ? "Plan queued" : "Approval unavailable"))), msg && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      fontSize: 10,
      color: msg.includes("Approved") || msg.includes("regenerated") ? "var(--signal-up)" : "var(--signal-down)",
      textAlign: "right"
    }
  }, msg)));
};
const AGENT_OPTIONS = [["topic_researcher", "Topic Researcher"], ["script_writer", "Script Writer"], ["thumbnail_director", "Thumbnail Director"], ["cross_poster", "Cross-Poster"]];
const AgentRail = ({
  selectedClusterSlug,
  onClose
}) => {
  const [active, setActive] = useState(window.DD_DATA.agents || []);
  const [recent, setRecent] = useState([]);
  const [picking, setPicking] = useState(false);
  const [enrichStatus, setEnrichStatus] = useState(null);
  const lastActiveRef = useRef(false);
  const dispatchTarget = window.DD_DATA.clusters.find(cluster => cluster.slug === selectedClusterSlug) || window.DD_DATA.clusters[0] || {};
  const pull = useCallback(async () => {
    if (!window.DDX) return;
    try {
      const snap = await window.DDX.agents();
      setActive(snap.active || []);
      setRecent(snap.recent_done || []);
    } catch (e) {}
    try {
      const res = await fetch("/api/enrich-status");
      if (res.ok) {
        const estatus = await res.json();
        setEnrichStatus(estatus);
        const isCurrentlyActive = estatus.enabled && (estatus.queued > 0 || estatus.in_flight > 0);
        if (lastActiveRef.current && !isCurrentlyActive) {
          // Finished enrichment, trigger reload
          window.DDX.reload();
        }
        lastActiveRef.current = isCurrentlyActive;
      }
    } catch (e) {}
  }, []);
  useEffect(() => {
    pull();
    if (!window.DDX) return;
    const es = window.DDX.agentStream(() => pull()); // re-snapshot on any event
    const id = setInterval(pull, 3000); // safety poll while running
    return () => {
      try {
        es.close();
      } catch (_) {}
      clearInterval(id);
    };
  }, []);
  const dispatch = async agent_type => {
    setPicking(false);
    try {
      await window.DDX.dispatch(agent_type, dispatchTarget.topic, dispatchTarget.slug);
    } catch (e) {}
    pull();
  };
  return /*#__PURE__*/React.createElement("aside", {
    className: "rail",
    style: {
      display: "flex",
      flexDirection: "column"
    },
    "aria-label": "Agent activity"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "12px 14px",
      borderBottom: "1px solid var(--line)",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "label",
    style: {
      color: "var(--text-hi)",
      fontWeight: 600
    }
  }, "Agents"), /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      color: "var(--signal-up)",
      borderColor: "rgba(124,255,178,0.3)",
      background: "rgba(124,255,178,0.08)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 5,
      height: 5,
      borderRadius: 999,
      background: "var(--signal-up)"
    }
  }), active.length, " active")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost icon",
    "aria-label": "Dispatch agent",
    onClick: () => setPicking(p => !p)
  }, /*#__PURE__*/React.createElement(I.Plus, {
    size: 12
  })), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost icon",
    "aria-label": "Close agents",
    onClick: onClose
  }, /*#__PURE__*/React.createElement(I.X, {
    size: 12
  })))), picking && /*#__PURE__*/React.createElement("div", {
    key: "agent-picker",
    style: {
      padding: "8px 14px",
      borderBottom: "1px solid var(--line)",
      display: "flex",
      flexWrap: "wrap",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      width: "100%",
      color: "var(--text-lo)",
      fontSize: 9.5
    }
  }, "Target: ", dispatchTarget.topic || "No selected story"), AGENT_OPTIONS.map(([type, label]) => /*#__PURE__*/React.createElement("button", {
    key: type,
    className: "btn ghost",
    style: {
      textTransform: "none",
      letterSpacing: 0
    },
    onClick: () => dispatch(type)
  }, label))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: "auto"
    }
  }, enrichStatus && enrichStatus.enabled && /*#__PURE__*/React.createElement("div", {
    style: {
      margin: "12px 14px",
      padding: "10px 12px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: enrichStatus.queued > 0 || enrichStatus.in_flight > 0 ? "blink" : "",
    style: {
      width: 6,
      height: 6,
      borderRadius: 999,
      background: enrichStatus.queued > 0 || enrichStatus.in_flight > 0 ? "var(--signal)" : "var(--text-lo)",
      boxShadow: enrichStatus.queued > 0 || enrichStatus.in_flight > 0 ? "0 0 6px var(--signal)" : "none"
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "micro",
    style: {
      letterSpacing: "0.06em",
      color: "var(--text-hi)"
    }
  }, "Background AI Engine")), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 9,
      color: "var(--text-lo)",
      textTransform: "uppercase"
    }
  }, enrichStatus.provider)), enrichStatus.queued > 0 || enrichStatus.in_flight > 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: "var(--text)"
    }
  }, "Enriching creator packs..."), /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      fontSize: 10,
      color: "var(--signal)"
    }
  }, enrichStatus.in_flight, " active \xB7 ", enrichStatus.queued, " queued")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 3,
      background: "var(--bg-3)",
      borderRadius: 2,
      marginTop: 6,
      overflow: "hidden",
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      width: "40%",
      background: "var(--signal)",
      borderRadius: 2,
      animation: "scan 1.5s linear infinite"
    }
  }))) : /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 6,
      display: "flex",
      justifyContent: "space-between",
      fontSize: 11,
      color: "var(--text-lo)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "All topics up-to-date"), /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, enrichStatus.enriched_today, " enriched today")), enrichStatus.last_error && /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 9,
      color: "var(--signal-down)",
      marginTop: 6,
      wordBreak: "break-all"
    }
  }, "Error: ", enrichStatus.last_error)), active.length === 0 && /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      padding: "16px 14px",
      fontSize: 11,
      color: "var(--text-lo)"
    }
  }, "No agents running. Dispatch one \u2191 or below."), active.map(a => /*#__PURE__*/React.createElement(AgentCard, {
    key: a.id,
    a: a
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "12px 14px 8px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginBottom: 8
    }
  }, "Just finished"), recent.length === 0 && /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-vlo)"
    }
  }, "nothing yet"), recent.slice(0, 3).map(r => /*#__PURE__*/React.createElement(CompletedRow, {
    key: r.id,
    topic: r.task || r.name,
    what: r.result_summary || "done",
    when: r.duration_sec != null ? `${r.duration_sec}s` : "·"
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 14px",
      borderTop: "1px solid var(--line)"
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    style: {
      width: "100%",
      justifyContent: "center"
    },
    onClick: () => setPicking(p => !p)
  }, /*#__PURE__*/React.createElement(I.Plus, {
    size: 12
  }), " Dispatch a new agent")));
};
const CompletedRow = ({
  topic,
  what,
  when
}) => /*#__PURE__*/React.createElement("div", {
  style: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 0",
    borderBottom: "1px dashed var(--line)"
  }
}, /*#__PURE__*/React.createElement("span", {
  style: {
    color: "var(--signal-up)",
    fontFamily: "var(--font-mono)",
    fontSize: 11
  }
}, "\u2713"), /*#__PURE__*/React.createElement("div", {
  style: {
    flex: 1,
    minWidth: 0,
    lineHeight: 1.1
  }
}, /*#__PURE__*/React.createElement("div", {
  style: {
    color: "var(--text-hi)",
    fontSize: 12,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap"
  }
}, topic), /*#__PURE__*/React.createElement("div", {
  className: "mono",
  style: {
    fontSize: 10,
    color: "var(--text-lo)",
    marginTop: 2
  }
}, what)), /*#__PURE__*/React.createElement("span", {
  className: "mono",
  style: {
    fontSize: 10,
    color: "var(--text-lo)"
  }
}, when, " ago"));

// ─── Copilot dock ───────────────────────────────────────────────────────────
const cleanMarkdownForTicker = txt => {
  if (!txt) return "";
  let clean = txt;
  if (clean.includes("|")) {
    clean = clean.split("|")[0].trim();
  }
  clean = clean.replace(/\*\*?/g, "");
  clean = clean.replace(/`/g, "");
  clean = clean.replace(/^\s*[-*+]\s+/mg, "");
  return clean.replace(/\s+/g, " ").trim();
};
const CopilotDock = ({
  context,
  selectedClusterSlug
}) => {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState("");
  const [model, setModel] = useState("");
  const requestVersion = useRef(0);
  useEffect(() => {
    requestVersion.current += 1;
    setQ("");
    setAnswer("");
    setModel("");
    setBusy(false);
  }, [context, selectedClusterSlug]);
  const submit = async () => {
    if (!q.trim()) return;
    const version = ++requestVersion.current;
    setBusy(true);
    setAnswer("");
    try {
      const r = await window.DDX.copilot(context, q, {
        focused_cluster: selectedClusterSlug
      });
      if (version !== requestVersion.current) return;
      setAnswer(r.answer || "No answer.");
      if (r.model) setModel(r.model);
    } catch (e) {
      if (version !== requestVersion.current) return;
      setAnswer("Copilot is offline. Check the LLM provider in Settings.");
    } finally {
      if (version === requestVersion.current) setBusy(false);
    }
  };
  const configuredModel = model || window.DD_DATA.copilotModel || "";
  const modelLabel = configuredModel ? configuredModel.split("/").pop().replace(/-/g, " ").toUpperCase() : "AUTO";
  const suggestions = {
    today: ["why is this the best pick?", "what should I make first?", "what changed today?"],
    pulse: ["why is this the best pick?", "what should I make first?", "what changed today?"],
    brief: ["rewrite the hook punchier", "generate 3 contrarian titles", "what's the strongest counterpoint?"],
    clusters: ["which cluster has best demo value?", "draft a comparison outline", "what would Karpathy cover?"],
    thumbs: ["pick the winning thumbnail", "generate a variant with a face", "what colors maximize CTR?"],
    research: ["summarize all evidence", "extract 5 cited stats", "find a counter-source"],
    pipeline: ["what should I publish first?", "reschedule based on momentum", "any stale items?"]
  };
  const sugs = suggestions[context] || suggestions.pulse;
  if (!open) {
    return /*#__PURE__*/React.createElement("button", {
      className: "copilot-launcher",
      onClick: () => setOpen(true),
      "aria-label": "Open creator copilot"
    }, /*#__PURE__*/React.createElement("span", {
      className: "copilot-launcher__icon"
    }, /*#__PURE__*/React.createElement(I.Spark, {
      size: 14,
      stroke: "#1A1100"
    })), /*#__PURE__*/React.createElement("span", null, "Ask Copilot"));
  }
  return /*#__PURE__*/React.createElement("aside", {
    className: "dock dock--open",
    "aria-label": "Creator copilot"
  }, /*#__PURE__*/React.createElement("div", {
    className: "dock__header"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 26,
      height: 26,
      borderRadius: 6,
      background: "linear-gradient(135deg, var(--signal), var(--src-papers))",
      display: "grid",
      placeItems: "center",
      boxShadow: "0 0 12px rgba(240,183,47,0.25)"
    }
  }, /*#__PURE__*/React.createElement(I.Spark, {
    size: 13,
    stroke: "#1A1100",
    strokeWidth: 2
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      lineHeight: 1.1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontSize: 12,
      fontWeight: 600
    }
  }, "Copilot"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 9.5,
      color: "var(--text-lo)",
      letterSpacing: "0.06em"
    }
  }, "CONTEXT \xB7 ", context.toUpperCase()))), /*#__PURE__*/React.createElement("span", {
    className: "dock__model mono"
  }, modelLabel), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost icon",
    onClick: () => setOpen(false),
    "aria-label": "Close copilot"
  }, /*#__PURE__*/React.createElement(I.X, {
    size: 12
  }))), /*#__PURE__*/React.createElement("div", {
    className: "dock__body"
  }, answer ? /*#__PURE__*/React.createElement("div", {
    className: "dock__answer"
  }, cleanMarkdownForTicker(answer)) : /*#__PURE__*/React.createElement("div", {
    className: "dock__suggestions"
  }, sugs.map((s, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    className: "text-button",
    onClick: () => setQ(s)
  }, s))), /*#__PURE__*/React.createElement("div", {
    className: "dock__input"
  }, /*#__PURE__*/React.createElement("input", {
    value: q,
    onChange: e => setQ(e.target.value),
    onKeyDown: e => {
      if (e.key === "Enter") submit();
    },
    placeholder: "Ask about the selected story...",
    style: {
      width: "100%",
      height: 36,
      padding: "0 38px 0 14px",
      background: "var(--bg-2)",
      border: "1px solid var(--line-2)",
      borderRadius: 6,
      color: "var(--text-hi)",
      fontFamily: "var(--font-sans)",
      fontSize: 13,
      outline: "none"
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: submit,
    disabled: busy,
    style: {
      position: "absolute",
      right: 4,
      top: 4,
      height: 28,
      width: 28,
      display: "grid",
      placeItems: "center",
      background: "var(--signal)",
      color: "#1A1100",
      border: "none",
      borderRadius: 4,
      cursor: "pointer",
      opacity: busy ? 0.5 : 1
    }
  }, busy ? /*#__PURE__*/React.createElement("span", {
    className: "blink"
  }, "\u2026") : /*#__PURE__*/React.createElement(I.Send, {
    size: 13,
    stroke: "#1A1100",
    strokeWidth: 1.8
  })))));
};
Object.assign(window, {
  Nav,
  Topbar,
  AgentRail,
  CopilotDock
});