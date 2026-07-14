// App.jsx — root, tweaks, view switching, time tick

const storedPreference = (key, fallback) => {
  try {
    return window.localStorage.getItem(`dailydex:${key}`) || fallback;
  } catch (_) {
    return fallback;
  }
};
const storedChoice = (key, fallback, choices) => {
  const value = storedPreference(key, fallback);
  if (choices.includes(value)) return value;
  try {
    window.localStorage.removeItem(`dailydex:${key}`);
  } catch (_) {}
  return fallback;
};
const serverPersona = window.DD_DATA && window.DD_DATA.persona || "multi";
const personaChoices = Object.keys(window.DD_DATA?.personas || {});
const TWEAK_DEFAULTS = {
  "theme": storedChoice("theme", "dark", ["dark", "light", "editorial"]),
  "persona": storedChoice("persona", personaChoices.includes(serverPersona) ? serverPersona : "multi", personaChoices.length ? personaChoices : ["multi"])
};
const App = () => {
  const [t, setRawTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = useState("today");
  const [now, setNow] = useState("");
  const [dataVersion, setDataVersion] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedClusterSlug, setSelectedClusterSlug] = useState(window.DD_DATA?.clusters?.[0]?.slug || null);
  const [railOpen, setRailOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [onboarded, setOnboarded] = useState(window.DD_DATA?.creator_identity?.onboarding_completed === true);
  const previousFocusRef = useRef(null);
  const setTweak = React.useCallback((key, value) => {
    setRawTweak(key, value);
    try {
      window.localStorage.setItem(`dailydex:${key}`, value);
    } catch (_) {}
  }, [setRawTweak]);

  // expose tweaks for nav rendering without prop-drilling
  window.__tweaks = t;

  // Re-render whenever the live data layer swaps window.DD_DATA.
  useEffect(() => window.DDX && window.DDX.onReload(() => setDataVersion(v => v + 1)), []);

  // Pick up work triggered elsewhere when focus returns, plus a conservative poll.
  useEffect(() => {
    if (!window.DDX) return;
    const pull = async () => {
      try {
        await window.DDX.reload();
      } catch (e) {}
    };
    const onFocus = () => pull();
    window.addEventListener("focus", onFocus);
    const id = setInterval(pull, 120000);
    return () => {
      window.removeEventListener("focus", onFocus);
      clearInterval(id);
    };
  }, []);
  useEffect(() => {
    const main = document.querySelector(".main");
    const topbar = document.querySelector(".topbar");
    if (navOpen) {
      previousFocusRef.current = document.activeElement;
      if (main) main.inert = true;
      if (topbar) topbar.inert = true;
      requestAnimationFrame(() => document.querySelector(".nav-mobile-close")?.focus());
    } else {
      if (main) main.inert = false;
      if (topbar) topbar.inert = false;
      if (previousFocusRef.current?.focus) previousFocusRef.current.focus();
      previousFocusRef.current = null;
    }
  }, [navOpen]);
  useEffect(() => {
    const clusters = window.DD_DATA?.clusters || [];
    if (!clusters.length) {
      setSelectedClusterSlug(null);
    } else if (!clusters.some(cluster => cluster.slug === selectedClusterSlug)) {
      setSelectedClusterSlug(clusters[0].slug);
    }
  }, [dataVersion]);
  useEffect(() => {
    const closeOverlays = event => {
      if (event.key !== "Escape") return;
      setNavOpen(false);
      setRailOpen(false);
    };
    window.addEventListener("keydown", closeOverlays);
    return () => window.removeEventListener("keydown", closeOverlays);
  }, []);
  const onRefresh = async () => {
    if (!window.DDX || refreshing) return;
    setRefreshing(true);
    try {
      await window.DDX.refresh();
    } finally {
      setRefreshing(false);
    }
  };

  // sync theme on <html>
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", t.theme || "dark");
  }, [t.theme]);

  // live clock
  useEffect(() => {
    const fmt = () => {
      const d = new Date();
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      const ss = String(d.getSeconds()).padStart(2, "0");
      setNow(`${hh}:${mm}:${ss}`);
    };
    fmt();
    const id = setInterval(fmt, 1000);
    return () => clearInterval(id);
  }, []);
  const navigate = (nextView, clusterSlug) => {
    const normalizedView = nextView === "pulse" ? "today" : nextView;
    if (clusterSlug) setSelectedClusterSlug(clusterSlug);else if (normalizedView === "today") setSelectedClusterSlug(window.DD_DATA?.clusters?.[0]?.slug || null);
    React.startTransition(() => setView(normalizedView));
    setNavOpen(false);
  };
  const Views = {
    today: TodayView,
    pulse: TodayView,
    brief: BriefView,
    clusters: ClustersView,
    thumbs: ThumbsView,
    research: ResearchView,
    pipeline: PipelineView,
    studio: StudioView,
    benchmarks: BenchmarksView,
    profile: ProfileView,
    copilot: CopilotChatView,
    settings: SettingsView
  };
  const CurrentView = Views[view] || TodayView;
  if (!onboarded) {
    return /*#__PURE__*/React.createElement(OnboardingView, {
      onComplete: () => setOnboarded(true)
    });
  }
  return /*#__PURE__*/React.createElement("div", {
    className: `app${railOpen ? " app--rail-open" : ""}${navOpen ? " app--nav-open" : ""}`
  }, /*#__PURE__*/React.createElement(Nav, {
    view: view,
    setView: navigate,
    onClose: () => setNavOpen(false)
  }), navOpen && /*#__PURE__*/React.createElement("button", {
    className: "nav-backdrop",
    "aria-label": "Close navigation",
    onClick: () => setNavOpen(false)
  }), /*#__PURE__*/React.createElement(Topbar, {
    now: now,
    onOpenSettings: () => navigate("settings"),
    onRefresh: onRefresh,
    refreshing: refreshing,
    onToggleAgents: () => setRailOpen(open => !open),
    railOpen: railOpen,
    onToggleNav: () => setNavOpen(open => !open),
    navOpen: navOpen
  }), /*#__PURE__*/React.createElement("main", {
    className: "main",
    "data-version": dataVersion
  }, /*#__PURE__*/React.createElement("div", {
    className: "main-scroll",
    key: view
  }, /*#__PURE__*/React.createElement(CurrentView, {
    onJump: navigate,
    selectedClusterSlug: selectedClusterSlug,
    setSelectedClusterSlug: setSelectedClusterSlug,
    tweaks: t,
    setTweak: setTweak
  }))), railOpen && /*#__PURE__*/React.createElement(AgentRail, {
    selectedClusterSlug: selectedClusterSlug,
    onClose: () => setRailOpen(false)
  }), /*#__PURE__*/React.createElement(CopilotDock, {
    context: view,
    selectedClusterSlug: selectedClusterSlug
  }));
};

// Error boundary — a single render throw must never blank the whole app.
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      error: null
    };
  }
  static getDerivedStateFromError(error) {
    return {
      error
    };
  }
  componentDidCatch(error, info) {
    console.error("Cockpit render error:", error, info);
  }
  render() {
    if (this.state.error) {
      return /*#__PURE__*/React.createElement("div", {
        style: {
          position: "fixed",
          inset: 0,
          display: "grid",
          placeItems: "center",
          background: "var(--bg-0, #0B0E14)",
          color: "var(--text, #C9D1D9)",
          padding: 24
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          maxWidth: 460,
          textAlign: "center"
        }
      }, /*#__PURE__*/React.createElement("h2", {
        style: {
          color: "var(--text-hi, #fff)",
          marginBottom: 8
        }
      }, "Something broke rendering this view"), /*#__PURE__*/React.createElement("p", {
        style: {
          fontSize: 13,
          lineHeight: 1.5,
          marginBottom: 20,
          color: "var(--text-mid, #8b949e)"
        }
      }, "The cockpit hit an unexpected error. Your data is safe \u2014 reload to recover."), /*#__PURE__*/React.createElement("pre", {
        style: {
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 11,
          textAlign: "left",
          background: "#07090C",
          border: "1px solid var(--line-hi, #222)",
          borderRadius: 6,
          padding: 12,
          overflow: "auto",
          maxHeight: 160,
          marginBottom: 20
        }
      }, String(this.state.error && this.state.error.message || this.state.error)), /*#__PURE__*/React.createElement("button", {
        onClick: () => location.reload(),
        style: {
          padding: "10px 24px",
          background: "var(--signal, #E8B339)",
          border: "none",
          borderRadius: 6,
          color: "#1A1100",
          fontWeight: 700,
          cursor: "pointer"
        }
      }, "Reload Cockpit")));
    }
    return this.props.children;
  }
}

// Mount
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(/*#__PURE__*/React.createElement(ErrorBoundary, null, /*#__PURE__*/React.createElement(App, null)));