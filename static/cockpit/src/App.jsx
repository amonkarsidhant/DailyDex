// App.jsx — root, tweaks, view switching, time tick

const TWEAK_DEFAULTS = {
  "theme": "dark",
  "persona": (window.DD_DATA && window.DD_DATA.persona) || "multi"
};

const App = () => {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = useState("pulse");
  const [now, setNow] = useState("");

  // expose tweaks for nav rendering without prop-drilling
  window.__tweaks = t;

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
  };
  const CurrentView = Views[view] || PulseView;

  return (
    <div className="app">
      <Nav view={view} setView={setView}/>
      <Topbar now={now} onOpenTweaks={() => {/* host controls */}}/>
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

// Mount
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App/>);
