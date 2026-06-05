// App.jsx — root, tweaks, view switching, time tick

const TWEAK_DEFAULTS = {
  "theme": "dark",
  "persona": (window.DD_DATA && window.DD_DATA.persona) || "multi"
};

const App = () => {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = useState("pulse");
  const [now, setNow] = useState("");
  const [dataVersion, setDataVersion] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [onboarded, setOnboarded] = useState(window.DD_DATA?.creator_identity?.onboarding_completed === true);

  // expose tweaks for nav rendering without prop-drilling
  window.__tweaks = t;

  // Re-render whenever the live data layer swaps window.DD_DATA.
  useEffect(() => window.DDX && window.DDX.onReload(() => setDataVersion(v => v + 1)), []);

  // Auto-refresh: pick up a fetch triggered elsewhere (e.g. the home dashboard)
  // when the tab regains focus, plus a slow background poll.
  useEffect(() => {
    if (!window.DDX) return;
    let last = (window.DD_DATA && window.DD_DATA.last_updated) || null;
    const pull = async () => {
      try {
        const d = await window.DDX.reload();
        last = d.last_updated || last;
      } catch (e) {}
    };
    const onFocus = () => pull();
    window.addEventListener("focus", onFocus);
    const id = setInterval(pull, 30000);
    return () => { window.removeEventListener("focus", onFocus); clearInterval(id); };
  }, []);

  const onRefresh = async () => {
    if (!window.DDX || refreshing) return;
    setRefreshing(true);
    try { await window.DDX.refresh(); } finally { setRefreshing(false); }
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

  const Views = {
    pulse:    PulseView,
    brief:    BriefView,
    clusters: ClustersView,
    thumbs:   ThumbsView,
    research: ResearchView,
    pipeline: PipelineView,
    studio:   StudioView,
    benchmarks: BenchmarksView,
    profile:  ProfileView,
    copilot:  CopilotChatView,
    settings: SettingsView,
  };
  const CurrentView = Views[view] || PulseView;

  if (!onboarded) {
    return <OnboardingView onComplete={() => setOnboarded(true)} />;
  }

  return (
    <div className="app">
      <Nav view={view} setView={setView}/>
      <Topbar now={now} onOpenTweaks={() => window.__toggleTweaks && window.__toggleTweaks()}
              onRefresh={onRefresh} refreshing={refreshing}/>
      <main className="main">
        <div className="main-scroll" key={view}>
          <CurrentView onJump={setView}/>
        </div>
      </main>
      <AgentRail/>
      <CopilotDock context={view}/>

      <TweaksPanel>
        <TweakSection label="Theme"/>
        <TweakRadio label="Visual theme" value={t.theme}
          options={["dark", "light", "editorial"]}
          onChange={(v) => setTweak("theme", v)}/>

        <TweakSection label="Persona"/>
        <TweakSelect label="Creator persona" value={t.persona}
          options={[
            { value: "multi",      label: "Multi-format (YT + LI + Newsletter)" },
            { value: "shorts",     label: "Shorts-first" },
            { value: "newsletter", label: "Newsletter writer" },
            { value: "educator",   label: "Educator" },
          ]}
          onChange={(v) => setTweak("persona", v)}/>
        <div style={{
          padding: "8px 10px", background: "rgba(0,0,0,0.04)",
          borderRadius: 6, fontSize: 11, lineHeight: 1.4, color: "rgba(41,38,27,0.65)",
        }}>
          Persona rewrites the Brief headline, CTAs, and which format gets priority in the cross-post split.
        </div>
      </TweaksPanel>
    </div>
  );
};

// Error boundary — a single render throw must never blank the whole app.
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error("Cockpit render error:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{
          position: "fixed", inset: 0, display: "grid", placeItems: "center",
          background: "var(--bg-0, #0B0E14)", color: "var(--text, #C9D1D9)", padding: 24
        }}>
          <div style={{ maxWidth: 460, textAlign: "center" }}>
            <h2 style={{ color: "var(--text-hi, #fff)", marginBottom: 8 }}>Something broke rendering this view</h2>
            <p style={{ fontSize: 13, lineHeight: 1.5, marginBottom: 20, color: "var(--text-mid, #8b949e)" }}>
              The cockpit hit an unexpected error. Your data is safe — reload to recover.
            </p>
            <pre style={{
              fontFamily: "var(--font-mono, monospace)", fontSize: 11, textAlign: "left",
              background: "#07090C", border: "1px solid var(--line-hi, #222)", borderRadius: 6,
              padding: 12, overflow: "auto", maxHeight: 160, marginBottom: 20
            }}>{String(this.state.error && this.state.error.message || this.state.error)}</pre>
            <button onClick={() => location.reload()} style={{
              padding: "10px 24px", background: "var(--signal, #E8B339)", border: "none",
              borderRadius: 6, color: "#1A1100", fontWeight: 700, cursor: "pointer"
            }}>Reload Cockpit</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// Mount
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<ErrorBoundary><App/></ErrorBoundary>);
