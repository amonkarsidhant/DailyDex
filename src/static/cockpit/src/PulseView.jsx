// TodayView - a live research desk that compiles only after creator selection.

const deskRelativeTime = value => {
  if (!value) return "Not fetched yet";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Fetch time unavailable";
  const minutes = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
};

const DeskSourceStrip = () => {
  const { SOURCES = {}, sourceHealth = {} } = window.DD_DATA;
  return (
    <div className="desk-source-strip" aria-label="Source freshness">
      {Object.keys(SOURCES).map(key => {
        const source = SOURCES[key];
        const health = sourceHealth[key] || {};
        const issue = !!health.error || health.status === "failed" || health.using_cache;
        return (
          <span className={`desk-source${issue ? " desk-source--issue" : ""}`} key={key}
                title={health.error || `${health.item_count || 0} current items`}>
            <i style={{ background: issue ? "var(--signal-down)" : source.color }}/>
            {source.abbr}
          </span>
        );
      })}
    </div>
  );
};

const SignalQueue = ({ clusters, selectedSlug, onSelect }) => (
  <aside className="signal-queue" aria-label="Current story signals">
    <div className="signal-queue__header">
      <div>
        <span className="micro">Current signals</span>
        <strong>Pick what deserves a desk</strong>
      </div>
      <span className="signal-queue__count mono">{clusters.length}</span>
    </div>
    <div className="signal-queue__list">
      {clusters.map((cluster, index) => (
        <button key={cluster.slug}
                className={`signal-row${selectedSlug === cluster.slug ? " signal-row--selected" : ""}`}
                onClick={() => onSelect(cluster.slug)}
                aria-pressed={selectedSlug === cluster.slug}>
          <span className="signal-row__rank mono">{String(index + 1).padStart(2, "0")}</span>
          <span className="signal-row__body">
            <strong>{cluster.topic}</strong>
            <span className="signal-row__sources">
              {(cluster.sources || []).slice(0, 4).map(source => (
                <SourceChip key={source} src={source}/>
              ))}
            </span>
          </span>
          <span className="signal-row__metrics">
            <b>{Math.round(cluster.creator_score || cluster.average_signal_score || 0)}</b>
            <Momentum delta={cluster.momentum}/>
            <small>{cluster.source_count} families</small>
          </span>
        </button>
      ))}
    </div>
  </aside>
);

const EvidenceCitation = ({ ids, evidence }) => (
  <span className="desk-citations">
    {(ids || []).map(id => {
      const source = evidence.find(record => record.id === id);
      return source?.url ? (
        <a key={id} href={source.url} target="_blank" rel="noopener noreferrer" title={source.title}>{id}</a>
      ) : <span key={id}>{id}</span>;
    })}
  </span>
);

const CompiledBrief = ({ result, evidence, onSteer }) => (
  <div className="desk-brief">
    <header className="desk-brief__header">
      <span className="micro">Fresh editorial brief</span>
      <h1>{result.story_title} <EvidenceCitation ids={result.story_title_evidence_ids} evidence={evidence}/></h1>
      <p>{result.editorial_thesis} <EvidenceCitation ids={result.editorial_thesis_evidence_ids} evidence={evidence}/></p>
    </header>

    <div className="desk-brief__lead">
      <div className="desk-hook-card">
        <span>Opening line</span>
        <blockquote>{result.hook} <EvidenceCitation ids={result.hook_evidence_ids} evidence={evidence}/></blockquote>
      </div>
      <div className="desk-payoff-card">
        <span>Audience payoff</span>
        <p>{result.audience_payoff} <EvidenceCitation ids={result.audience_payoff_evidence_ids} evidence={evidence}/></p>
      </div>
    </div>

    <section className="desk-section">
      <div className="desk-section__heading"><span className="micro">Three ways into the story</span><small>Choose one to brief the desk again</small></div>
      <div className="desk-angle-grid">
        {(result.angles || []).map((angle, index) => (
          <button key={`${angle.name}-${index}`} className="desk-angle"
                  onClick={() => onSteer(`Develop the ${angle.name} angle. Keep it evidence-led and make the editorial take sharper.`)}>
            <span className="mono">0{index + 1}</span>
            <strong>{angle.name}</strong>
            <p>{angle.take}</p>
            <EvidenceCitation ids={angle.evidence_ids} evidence={evidence}/>
          </button>
        ))}
      </div>
    </section>

    <div className="desk-brief__split">
      <section className="desk-section desk-format-card">
        <span className="micro">Best treatment</span>
        <strong>{result.recommended_format}</strong>
        <p>{result.format_reason} <EvidenceCitation ids={result.format_reason_evidence_ids} evidence={evidence}/></p>
        <div><span>Concrete demo</span><p>{result.demo_idea} <EvidenceCitation ids={result.demo_evidence_ids} evidence={evidence}/></p></div>
      </section>
      <section className="desk-section desk-titles-card">
        <span className="micro">Working titles</span>
        {(result.titles || []).map((title, index) => (
          <button key={index} onClick={() => navigator.clipboard?.writeText(title)}>
            <span className="mono">{index + 1}</span>{title}
          </button>
        ))}
        <EvidenceCitation ids={result.titles_evidence_ids} evidence={evidence}/>
      </section>
    </div>

    <section className="desk-section desk-facts">
      <div className="desk-section__heading"><span className="micro">Claims the sources support</span><small>Every claim links back to evidence</small></div>
      {(result.key_facts || []).map((fact, index) => (
        <div key={index}><span className="desk-facts__mark">+</span><p>{fact.claim}</p><EvidenceCitation ids={fact.evidence_ids} evidence={evidence}/></div>
      ))}
    </section>

    {!!result.caveats?.length && (
      <section className="desk-caveats">
        <span className="micro">What the desk would not claim yet <EvidenceCitation ids={result.caveats_evidence_ids} evidence={evidence}/></span>
        {result.caveats.map((caveat, index) => <p key={index}>{caveat}</p>)}
      </section>
    )}
  </div>
);

const LiveResearchDesk = ({ cluster }) => {
  const [desk, setDesk] = useState({
    phase: "idle", message: "", evidence: [], draft: "", result: null,
    error: "", cacheHit: false, model: "", generatedAt: null, lockedUntil: null,
  });
  const [instruction, setInstruction] = useState("");
  const requestRef = useRef(0);
  const abortRef = useRef(null);

  const compile = requestInstruction => {
    if (!cluster || !window.DDX) return;
    const requestId = ++requestRef.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setDesk({
      phase: "starting", message: "Opening the live research desk...", evidence: [], draft: "",
      result: null, error: "", cacheHit: false, model: "", generatedAt: null, lockedUntil: null,
    });
    window.DDX.compile(cluster.slug, requestInstruction || "", event => {
      if (requestRef.current !== requestId) return;
      if (event.type === "status") {
        setDesk(current => ({ ...current, phase: event.phase, message: event.message || current.message }));
      } else if (event.type === "cache") {
        setDesk(current => ({
          ...current, phase: "cached", cacheHit: true, model: event.model || "",
          generatedAt: event.generated_at, lockedUntil: event.locked_until,
          message: "Today's desk brief is already compiled. Replaying the cited work.",
        }));
      } else if (event.type === "evidence") {
        setDesk(current => {
          const remaining = current.evidence.filter(record => record.id !== event.record.id);
          return { ...current, evidence: [...remaining, event.record].sort((a, b) => a.id.localeCompare(b.id)) };
        });
      } else if (event.type === "draft_reset") {
        setDesk(current => ({ ...current, draft: "" }));
      } else if (event.type === "token") {
        setDesk(current => ({ ...current, phase: "compiling", draft: (current.draft + event.token).slice(-50000) }));
      } else if (event.type === "result") {
        setDesk(current => ({
          ...current, phase: "done", result: event.result, draft: "", error: "",
          cacheHit: !!event.cache_hit, model: event.model || "",
          generatedAt: event.generated_at, lockedUntil: event.locked_until,
          message: event.cache_hit ? "Replayed today's compiled desk brief." : "Fresh desk brief compiled from live evidence.",
        }));
      } else if (event.type === "error") {
        setDesk(current => ({ ...current, phase: "error", error: event.message || "The desk could not compile this story." }));
      }
    }, controller.signal).catch(error => {
      if (requestRef.current !== requestId || error.name === "AbortError") return;
      setDesk(current => ({ ...current, phase: "error", error: error.message || "The research desk is unavailable." }));
    });
  };

  useEffect(() => {
    setInstruction("");
    compile("");
    return () => abortRef.current?.abort();
  }, [cluster?.slug]);

  const submit = event => {
    event.preventDefault();
    if (!instruction.trim()) return;
    compile(instruction.trim());
  };

  const isWorking = ["starting", "waiting", "evidence", "compiling", "repairing"].includes(desk.phase);
  const lockText = desk.lockedUntil
    ? `Daily brief locked until ${new Date(desk.lockedUntil * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`
    : "One fresh default brief per signal every 24 hours";

  return (
    <main className="research-desk" aria-live="polite">
      <header className="research-desk__topbar">
        <div>
          <span className="micro">Live research desk</span>
          <strong>{cluster.topic}</strong>
        </div>
        <div className="research-desk__meta">
          <span>{desk.cacheHit ? "24H REPLAY" : isWorking ? "COMPILING LIVE" : "SOURCE-BACKED"}</span>
          <small>{lockText}</small>
        </div>
      </header>

      <div className="research-desk__signal">
        <span>Creator fit <b>{Math.round(cluster.creator_score || 0)}</b></span>
        <span>Signal <b>{Math.round(cluster.average_signal_score || 0)}</b></span>
        <span>Coverage <b>{cluster.source_count}</b></span>
        <Momentum delta={cluster.momentum} big/>
      </div>

      {isWorking && (
        <section className="desk-working">
          <div className="desk-working__pulse"><i/><i/><i/></div>
          <div><strong>{desk.message}</strong><span>{desk.evidence.length} source{desk.evidence.length === 1 ? "" : "s"} read</span></div>
          {desk.phase === "compiling" && desk.draft && (
            <pre>{desk.draft.slice(-900)}</pre>
          )}
        </section>
      )}

      {desk.error && <div className="desk-error"><strong>Compile stopped</strong><span>{desk.error}</span><button className="btn ghost" onClick={() => compile(instruction)}>Try again</button></div>}
      {desk.result && <CompiledBrief result={desk.result} evidence={desk.evidence} onSteer={value => { setInstruction(value); compile(value); }}/>}

      {!!desk.evidence.length && (
        <section className="desk-evidence-ledger">
          <div className="desk-section__heading"><span className="micro">Evidence ledger</span><small>Read live when this brief was compiled</small></div>
          <div>
            {desk.evidence.map(record => (
              <a key={record.id} href={record.url || undefined} target={record.url ? "_blank" : undefined} rel="noopener noreferrer">
                <span className="mono">{record.id}</span>
                <span><strong>{record.title}</strong><small>{record.source_type} · {record.facts?.length || 0} facts · {record.quotes?.length || 0} quotes</small></span>
                <I.ArrowR size={12}/>
              </a>
            ))}
          </div>
        </section>
      )}

      <form className="desk-prompt" onSubmit={submit}>
        <div><span className="micro">Direct the desk</span><small>Each distinct request gets its own 24-hour cited brief.</small></div>
        <div className="desk-prompt__input">
          <input value={instruction} onChange={event => setInstruction(event.target.value)}
                  placeholder="Focus on the cost, the technical trade-off, or the audience debate..."
                  maxLength={500}/>
          <button className="btn primary" disabled={isWorking || !instruction.trim()}>{isWorking ? "Working..." : "Compile"}</button>
        </div>
        <div className="desk-prompt__suggestions">
          {["Find the skeptical angle", "Make this practical for builders", "Focus on what the sources disagree about"].map(value => (
            <button type="button" key={value} onClick={() => { setInstruction(value); compile(value); }} disabled={isWorking}>{value}</button>
          ))}
        </div>
      </form>
    </main>
  );
};

const TodayView = ({ selectedClusterSlug, setSelectedClusterSlug }) => {
  const { clusters = [], meta = {} } = window.DD_DATA;
  const [activeSlug, setActiveSlug] = useState(null);
  const cluster = clusters.find(item => item.slug === activeSlug) || null;

  useEffect(() => {
    if (activeSlug && !clusters.some(item => item.slug === activeSlug)) setActiveSlug(null);
  }, [activeSlug, clusters]);

  if (!clusters.length) {
    return (
      <div className="panel today-empty">
        <span className="micro">Research desk</span>
        <h1>No current signals</h1>
        <p>Fetch sources, then select a signal for a fresh creator-specific compile.</p>
        <button className="btn primary" onClick={() => window.DDX?.refresh()}>Fetch sources</button>
      </div>
    );
  }

  return (
    <div className="today-view live-desk-view">
      <header className="live-desk-header">
        <div>
          <span className="micro">DailyDex research room</span>
          <h1>Choose a signal. Get a fresh desk brief.</h1>
          <p>No generic angles. The desk reads the sources and writes for your audience when you select.</p>
        </div>
        <div><DeskSourceStrip/><span className="mono">signals updated {deskRelativeTime(meta.last_updated || meta.fetched_at)}</span></div>
      </header>
      <div className="live-desk-layout">
        <SignalQueue clusters={clusters} selectedSlug={activeSlug}
                     onSelect={slug => { setActiveSlug(slug); setSelectedClusterSlug?.(slug); }}/>
        {cluster ? <LiveResearchDesk key={cluster.slug} cluster={cluster}/> : (
          <main className="research-desk desk-unselected">
            <span className="micro">Desk closed</span>
            <h2>Select a current signal</h2>
            <p>Nothing compiles until you choose the story that deserves deeper research.</p>
          </main>
        )}
      </div>
    </div>
  );
};

window.TodayView = TodayView;
window.PulseView = TodayView;
