// TodayView - the action-first home for deciding what to make next.

const todayOpportunityFor = (opportunities, cluster) => {
  if (!cluster) return null;
  return (opportunities || []).find(o =>
    o.cluster_slug === cluster.slug ||
    o.slug === cluster.slug ||
    o.creator_topic === cluster.topic ||
    o.topic === cluster.topic
  ) || null;
};

const todayRelativeTime = (value) => {
  if (!value) return "Not fetched yet";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Fetch time unavailable";
  const minutes = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 60000));
  if (minutes < 1) return "Updated just now";
  if (minutes < 60) return `Updated ${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Updated ${hours}h ago`;
  return `Updated ${Math.floor(hours / 24)}d ago`;
};

const TodaySourceStrip = () => {
  const { SOURCES = {}, sourceHealth = {} } = window.DD_DATA;
  return (
    <div className="today-source-strip" aria-label="Source freshness">
      {Object.keys(SOURCES).map(key => {
        const source = SOURCES[key];
        const health = sourceHealth[key] || {};
        const hasIssue = !!health.error || health.status === "failed" || health.using_cache
          || (health.last_fetch_min != null && !health.fresh);
        const age = health.last_fetch_min == null ? "not fetched" : `${health.last_fetch_min}m ago`;
        return (
          <div className={`today-source${hasIssue ? " today-source--issue" : ""}`} key={key}
               title={health.error || `${health.item_count || 0} items in latest fetch`}>
            <span className="today-source__dot" style={{ background: hasIssue ? "var(--signal-down)" : health.last_fetch_min == null ? "var(--text-lo)" : source.color }}/>
            <span className="today-source__abbr">{source.abbr}</span>
            <span className="today-source__age">{age}</span>
          </div>
        );
      })}
    </div>
  );
};

const TodayActionQueue = ({ onJump }) => {
  const { factory_queue = [], pipeline = {}, sourceHealth = {}, SOURCES = {}, stats = {} } = window.DD_DATA;
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState("");
  const allScripts = pipeline.script_ready || [];
  const scripts = allScripts.slice(0, 3);
  const allSourceIssues = Object.entries(sourceHealth)
    .filter(([, health]) => health.error || health.status === "failed" || health.using_cache
      || (health.last_fetch_min != null && !health.fresh));
  const sourceIssues = allSourceIssues.slice(0, 3);
  const sourceValues = Object.values(sourceHealth);
  const hasKnownSources = sourceValues.some(health => health.last_fetch_min != null);
  const allSourcesCurrent = Object.keys(SOURCES).length > 0
    && Object.keys(SOURCES).every(key => sourceHealth[key]?.fresh === true);

  const reviewFactoryItem = async (item, action) => {
    setBusyId(`${item.id}:${action}`);
    setMessage("");
    try {
      const response = await fetch(`/api/factory/${item.id}/${action}`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `${action} failed`);
      setMessage(action === "approve" ? "Short approved for publishing." : "Short rejected.");
      if (window.DDX) await window.DDX.reload();
    } catch (error) {
      setMessage(error.message || "Could not update the review item.");
    } finally {
      setBusyId(null);
    }
  };

  const count = (stats.approval_count ?? factory_queue.length) + allScripts.length + allSourceIssues.length;
  return (
    <section className="panel today-attention" aria-labelledby="attention-title">
      <PanelHeader no="02" actions={<span className="today-count">{count} open</span>}>
        <span id="attention-title">Needs attention</span>
      </PanelHeader>
      <div className="today-attention__body">
        {factory_queue.map(item => (
          <div className="today-action" key={`review-${item.id}`}>
            <span className="today-action__marker today-action__marker--review"/>
            <div className="today-action__copy">
              <span className="today-action__type">Review ready</span>
              <strong>{item.title || item.topic}</strong>
              <span>{item.virality_score ? `Virality score ${Math.round(item.virality_score)}` : "Rendered short awaiting a decision"}</span>
              <video controls preload="metadata" src={`/api/videos/${item.topic ? item.topic.replace(/[^a-zA-Z0-9]/g, "-").toLowerCase() : item.id}.mp4`}
                   style={{ width: "100%", maxHeight: 200, borderRadius: 6, marginTop: 6 }}
                   onError={(e) => { e.target.style.display = "none"; }}/>
            </div>
            <div className="today-action__controls">
              <a className="btn ghost" href={`/api/videos/${item.topic ? item.topic.replace(/[^a-zA-Z0-9]/g, "-").toLowerCase() : item.id}.mp4`}
                 target="_blank" rel="noopener noreferrer" download
                 style={{ textDecoration: "none" }}>Download</a>
              <button className="btn ghost" disabled={busyId != null}
                      onClick={() => reviewFactoryItem(item, "reject")}>Reject</button>
              <button className="btn primary" disabled={busyId != null}
                      onClick={() => reviewFactoryItem(item, "approve")}>
                {busyId === `${item.id}:approve` ? "Approving..." : "Approve"}
              </button>
            </div>
          </div>
        ))}

        {scripts.map(item => (
          <button className="today-action today-action--button" key={`script-${item.id}`}
                  onClick={() => onJump("pipeline")}>
            <span className="today-action__marker today-action__marker--ready"/>
            <span className="today-action__copy">
              <span className="today-action__type">Ready to record</span>
              <strong>{item.working_title || item.topic || "Untitled script"}</strong>
              <span>{item.format || "Script ready"}</span>
            </span>
            <I.ArrowR size={13}/>
          </button>
        ))}

        {sourceIssues.map(([key, health]) => {
          const source = window.DD_DATA.SOURCES[key];
          return (
            <div className="today-action" key={`source-${key}`}>
              <span className="today-action__marker today-action__marker--issue"/>
              <div className="today-action__copy">
                <span className="today-action__type">{health.error || health.using_cache ? "Source issue" : "Source stale"}</span>
                <strong>{source?.label || key}</strong>
                <span>{health.error || (health.using_cache ? "Using cached data" : `Last fetched ${health.last_fetch_min}m ago`)}</span>
              </div>
              <button className="btn ghost" onClick={() => window.DDX && window.DDX.refresh()}>Retry</button>
            </div>
          );
        })}

        {count > factory_queue.length + scripts.length + sourceIssues.length && (
          <div className="today-inline-message">Additional review or source items are not shown in this compact list.</div>
        )}

        {count === 0 && (
          <div className="today-clear">
            <span className="today-clear__mark">OK</span>
            <div><strong>No queued actions</strong><span>{allSourcesCurrent ? "Nothing needs review and all sources are current." : hasKnownSources ? "No review items are queued; some sources are still awaiting a current fetch." : "Source status will appear after the first fetch."}</span></div>
          </div>
        )}
        {message && <div className="today-inline-message" role="status">{message}</div>}
      </div>
    </section>
  );
};

const TodayChanges = ({ clusters, selectedSlug, onSelect, onJump }) => {
  const changed = [...clusters]
    .sort((a, b) => Math.abs(b.momentum || 0) - Math.abs(a.momentum || 0) || b.source_count - a.source_count)
    .slice(0, 4);
  return (
    <section className="panel today-changes" aria-labelledby="changes-title">
      <PanelHeader no="03" actions={<button className="btn ghost" onClick={() => onJump("clusters", selectedSlug)}>Open Discover</button>}>
        <span id="changes-title">What changed</span>
      </PanelHeader>
      <div className="today-changes__list">
        {changed.map(cluster => {
          const note = cluster.changelog?.[0]?.message || "No measured change since the previous snapshot.";
          return (
            <button key={cluster.slug}
                    className={`today-change${selectedSlug === cluster.slug ? " today-change--active" : ""}`}
                    onClick={() => onSelect(cluster.slug)}>
              <span className="today-change__topic">{cluster.topic}</span>
              <Momentum delta={cluster.momentum}/>
              <span className="today-change__note">{note}</span>
              <span className="today-change__sources">{cluster.source_count} sources</span>
            </button>
          );
        })}
      </div>
    </section>
  );
};

const TodayProduction = ({ onJump }) => {
  const { pipeline = {}, calendar = [], agents = [] } = window.DD_DATA;
  const lanes = [
    ["researching", "Researching"],
    ["script_ready", "Script ready"],
    ["recording", "Recording"],
  ];
  const nextDay = calendar.find(day => (day.items || []).length > 0);
  return (
    <section className="panel today-production" aria-labelledby="production-title">
      <PanelHeader no="04" actions={<button className="btn ghost" onClick={() => onJump("pipeline")}>Open Publish</button>}>
        <span id="production-title">Production now</span>
      </PanelHeader>
      <div className="today-production__body">
        <div className="today-production__lanes">
          {lanes.map(([key, label]) => (
            <button key={key} onClick={() => onJump("pipeline")} className="today-lane">
              <span>{label}</span>
              <strong>{(pipeline[key] || []).length}</strong>
            </button>
          ))}
        </div>
        <div className="today-production__next">
          <span className="micro">Next scheduled</span>
          {nextDay ? (
            <><strong>{nextDay.day} {nextDay.date}</strong><span>{nextDay.items.length} production event{nextDay.items.length === 1 ? "" : "s"}</span></>
          ) : (
            <><strong>Calendar open</strong><span>No production events scheduled in the next seven days.</span></>
          )}
        </div>
        <div className="today-production__agents">
          <span className="micro">Agents</span>
          {agents.length ? (
            <><strong>{agents.length} active</strong><span>{agents.slice(0, 2).map(agent => agent.name).join(" + ")}</span></>
          ) : (
            <><strong>Idle</strong><span>Dispatch work from the recommendation when you are ready.</span></>
          )}
        </div>
      </div>
    </section>
  );
};

const TodayGoldenPath = ({ onJump, clusters, pipeline, factory_queue }) => {
  const hasClusters = clusters.length > 0;
  const hasPipeline = Object.values(pipeline || {}).flat().length > 0;
  const hasFactory = (factory_queue || []).length > 0;

  if (hasFactory) return null;

  const steps = [
    { done: hasClusters, label: "Sources fetched", action: "Refresh sources", onAction: () => window.DDX && window.DDX.refresh() },
    { done: hasPipeline, label: "Story saved to pipeline", action: "Save a story", onAction: null },
    { done: false, label: "Render your first short", action: "Click Render short", onAction: null },
    { done: false, label: "Review and approve", action: "Check Needs attention", onAction: null },
  ];
  const completed = steps.filter(s => s.done).length;

  if (completed >= 2) return null;

  return (
    <section className="panel today-golden-path" aria-labelledby="golden-path-title">
      <PanelHeader no="01"><span id="golden-path-title">Get started</span></PanelHeader>
      <div className="today-golden-path__body">
        {steps.map((step, i) => (
          <div key={i} className={`today-golden-path__step${step.done ? " today-golden-path__step--done" : ""}`}>
            <span className="today-golden-path__check">{step.done ? "\u2713" : i + 1}</span>
            <span>{step.label}</span>
            {!step.done && step.onAction && (
              <button className="btn ghost" onClick={step.onAction}>{step.action}</button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
};

const TodayView = ({ onJump, selectedClusterSlug, setSelectedClusterSlug }) => {
  const { clusters = [], opportunities = [], titleSets = {}, meta = {}, pipeline = {}, factory_queue = [] } = window.DD_DATA;
  const fallbackSlug = clusters[0]?.slug || null;
  const selectedSlug = clusters.some(cluster => cluster.slug === selectedClusterSlug)
    ? selectedClusterSlug
    : fallbackSlug;
  const cluster = clusters.find(item => item.slug === selectedSlug) || clusters[0] || null;
  const opportunity = todayOpportunityFor(opportunities, cluster);
  const titles = cluster ? (titleSets[cluster.slug] || opportunity?.suggested_titles || {}) : {};
  const recommendationTitle = titles.practical || titles.curiosity || opportunity?.title || cluster?.topic || "";
  const isTopRecommendation = cluster.slug === clusters[0]?.slug;
  const hook = opportunity?.opening_hook || opportunity?.hook_line || cluster?.recommended_angle || "";
  const saved = Object.values(pipeline).flat().some(item =>
    item.topic === cluster?.topic || item.working_title === recommendationTitle
  );
  const [saving, setSaving] = useState(false);
  const [researching, setResearching] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderMsg, setRenderMsg] = useState("");

  const selectCluster = slug => {
    if (setSelectedClusterSlug) setSelectedClusterSlug(slug);
  };

  const saveRecommendation = async () => {
    if (!cluster || !window.DDX || saved || saving) return;
    setSaving(true);
    try {
      await window.DDX.saveToPipeline({
        title: recommendationTitle,
        working_title: recommendationTitle,
        topic: cluster.topic,
        category: cluster.topic,
        format: opportunity?.best_format || cluster.best_content_format || "YouTube long-form",
        creator_score: cluster.creator_score,
        signal_score: cluster.average_signal_score,
        pipeline_type: "creator",
        status: "idea",
      });
      await window.DDX.reload();
    } finally {
      setSaving(false);
    }
  };

  const startResearch = async () => {
    if (!cluster || !window.DDX || researching) return;
    setResearching(true);
    try {
      await window.DDX.dispatch("topic_researcher", cluster.topic, cluster.slug);
      onJump("research", cluster.slug);
    } finally {
      setResearching(false);
    }
  };

  const renderShort = async () => {
    if (!cluster || !window.DDX || rendering) return;
    setRendering(true);
    setRenderMsg("Rendering vertical short with Remotion...");
    try {
      const res = await window.DDX.factoryRun(1);
      if (res.started) {
        setRenderMsg("Factory started. The short will appear in Needs attention when ready.");
        const poll = setInterval(async () => {
          try {
            const status = await window.DDX.factoryStatus();
            if (!status.running) {
              clearInterval(poll);
              setRendering(false);
              setRenderMsg(status.result?.queued?.length ? "Short rendered! Review it in Needs attention." : "Factory finished. Check the queue.");
              if (window.DDX) await window.DDX.reload();
            }
          } catch (_) { clearInterval(poll); setRendering(false); }
        }, 3000);
      } else {
        setRenderMsg("Factory is already running.");
        setRendering(false);
      }
    } catch (e) {
      setRenderMsg("Failed to start render: " + (e.message || "unknown error"));
      setRendering(false);
    }
  };

  if (!cluster) {
    return (
      <div className="panel today-empty">
        <span className="micro">Today</span>
        <h1>No recommendation yet</h1>
        <p>Fetch sources to build the first cross-source story recommendation.</p>
        <button className="btn primary" onClick={() => window.DDX && window.DDX.refresh()}>Fetch sources</button>
      </div>
    );
  }

  return (
    <div className="today-view">
      <section className="panel crosshair today-hero" aria-labelledby="today-title">
        <span className="ch-bl"/><span className="ch-br"/>
        <div className="today-hero__topline">
          <div>
            <span className="today-eyebrow">{isTopRecommendation ? "Make this next" : "Selected story"}</span>
            <span className="today-freshness">{todayRelativeTime(meta.last_updated || meta.fetched_at)}</span>
          </div>
          <TodaySourceStrip/>
        </div>

        <div className="today-hero__grid">
          <div className="today-recommendation">
            <div className="today-recommendation__meta">
              <FormatBadge format={opportunity?.best_format || cluster.best_content_format}/>
              <span className="chip">Creator score {cluster.creator_score}</span>
              <span className="chip">{cluster.source_count} source families</span>
              <Momentum delta={cluster.momentum} big/>
            </div>
            <h1 id="today-title">{recommendationTitle}</h1>
            <p className="today-recommendation__why">{cluster.why_this_is_a_story}</p>
            {hook && (
              <div className="today-hook">
                <span>Opening angle</span>
                <p>{hook}</p>
              </div>
            )}
            <div className="today-recommendation__actions">
              <button className="btn primary today-primary-action" onClick={() => onJump("brief", cluster.slug)}>
                Open production brief <I.ArrowR size={13}/>
              </button>
              <button className="btn ghost" disabled={rendering} onClick={renderShort}
                      style={rendering ? { borderColor: "var(--signal)", color: "var(--signal)" } : {}}>
                {rendering ? "Rendering..." : "Render short"}
              </button>
              <button className="btn ghost" disabled={researching} onClick={startResearch}>
                {researching ? "Dispatching..." : "Build research pack"}
              </button>
              <button className="btn ghost" disabled={saved || saving} onClick={saveRecommendation}>
                {saved ? "In pipeline" : saving ? "Saving..." : "Save idea"}
              </button>
            </div>
            {renderMsg && <div className="today-inline-message" role="status">{renderMsg}</div>}
          </div>

          <aside className="today-evidence" aria-label="Recommendation evidence">
            <div className="today-evidence__header">
              <span className="micro">Evidence behind the pick</span>
              <button className="text-button" onClick={() => onJump("clusters", cluster.slug)}>Inspect cluster</button>
            </div>
            <div className="today-evidence__list">
              {(cluster.related_items || []).slice(0, 4).map((item, index) => (
                <a key={`${item.url || item.title}-${index}`} href={item.url || undefined}
                   target={item.url ? "_blank" : undefined} rel="noopener noreferrer"
                   className="today-evidence__item">
                  <SourceChip src={item.source_type}/>
                  <span>{item.title}</span>
                  <strong>{item.signal_score}</strong>
                </a>
              ))}
            </div>
            <div className="today-evidence__angle">
              <span className="micro">Recommended angle</span>
              <p>{cluster.recommended_angle}</p>
            </div>
          </aside>
        </div>
      </section>

      <TodayGoldenPath onJump={onJump} clusters={clusters} pipeline={pipeline} factory_queue={factory_queue}/>
      <div className="today-work-grid">
        <TodayActionQueue onJump={onJump}/>
        <EditorialBoard/>
      </div>
      <TodayChanges clusters={clusters} selectedSlug={selectedSlug} onSelect={selectCluster} onJump={onJump}/>
      <TodayProduction onJump={onJump}/>
    </div>
  );
};

window.TodayView = TodayView;
window.PulseView = TodayView;
