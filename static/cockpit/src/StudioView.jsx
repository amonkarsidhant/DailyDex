// StudioView — Creator Central: autonomous, multi-format content factory.
// Reads window.DD_DATA.studio = { stories, providers, skills, run }.

// Elapsed timer shown while factory is running
const RunTimer = ({ startMs }) => {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startMs) / 1000)), 1000);
    return () => clearInterval(id);
  }, [startMs]);
  const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const s = String(elapsed % 60).padStart(2, "0");
  return (
    <span className="mono" style={{ fontSize: 11, color: "var(--signal)", letterSpacing: "0.06em" }}>
      ⏱ {m}:{s}
    </span>
  );
};

const STUDIO_FMT_META = {
  shorts:  { icon: "📱", label: "YouTube Short" },
  video:   { icon: "🎬", label: "Long-form Video" },
  podcast: { icon: "🎙️", label: "Podcast Script" },
  blog:    { icon: "📝", label: "Blog Post" },
};

const StudioStatusDot = ({ status }) => {
  const color = status === "ready" ? "var(--signal-up)"
    : status === "generating" ? "var(--signal)"
    : status === "failed" ? "var(--signal-down)" : "var(--text-lo)";
  return <span style={{ width: 7, height: 7, borderRadius: 999, background: color,
    display: "inline-block", animation: status === "generating" ? "pulse 1.4s infinite" : "none" }}/>;
};

const StudioFormatCard = ({ storyKey, fmt, data, onRegen, busy, broll = [], cues = [] }) => {
  const [open, setOpen] = useState(false);
  const meta = STUDIO_FMT_META[fmt] || { icon: "•", label: fmt };
  const body = data?.body || "";
  const preview = body.slice(0, open ? body.length : 320);

  const handleDownload = () => {
    let content = `# Script: ${meta.label}\n\n${body}\n\n`;
    if (broll.length > 0) {
      content += `## Suggested B-Roll\n` + broll.map(x => `- ${x}`).join("\n") + "\n\n";
    }
    if (cues.length > 0) {
      content += `## On-Screen Cues\n` + cues.map(x => `- ${x}`).join("\n") + "\n\n";
    }
    window.downloadScript(`${storyKey}-${fmt}.md`, content);
  };

  return (
    <div className="panel" style={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px",
        borderBottom: "1px solid var(--line)" }}>
        <span style={{ fontSize: 15 }}>{meta.icon}</span>
        <span style={{ fontWeight: 600, color: "var(--text-hi)" }}>{meta.label}</span>
        <span style={{ flex: 1 }}/>
        <StudioStatusDot status={data?.status}/>
        {data?.provider && <span className="chip" style={{ fontSize: 10 }}>{data.provider}</span>}
      </div>
      <div style={{ padding: "12px", flex: 1 }}>
        {body ? (
          <pre className="mono" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word",
            fontSize: 11.5, lineHeight: 1.5, color: "var(--text)", margin: 0,
            maxHeight: open ? "none" : 180, overflow: "hidden" }}>{preview}{!open && body.length > 320 ? "…" : ""}</pre>
        ) : (
          <div style={{ color: "var(--text-lo)", fontStyle: "italic", fontSize: 12 }}>
            {data?.status === "generating" ? "Generating…" : data?.error || "Not generated yet."}
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 6, padding: "8px 12px", borderTop: "1px solid var(--line)" }}>
        {body && body.length > 320 &&
          <button className="btn ghost" onClick={() => setOpen(o => !o)}>{open ? "Less" : "Expand"}</button>}
        {body &&
          <button className="btn ghost" onClick={() => navigator.clipboard?.writeText(body)}>Copy</button>}
        {body &&
          <button className="btn ghost" onClick={handleDownload}>Download</button>}
        <span style={{ flex: 1 }}/>
        <button className="btn ghost" disabled={busy}
          onClick={() => onRegen(storyKey, fmt)}>{busy ? "…" : "Regenerate"}</button>
      </div>
    </div>
  );
};

const StudioView = ({ onJump }) => {
  const [studioData, setStudioData] = useState(window.DD_DATA.studio || {});
  const providers = studioData.providers || [];
  const skills = studioData.skills || [];
  const stories = studioData.stories || [];
  const running = studioData.run?.running;
  const [busyKey, setBusyKey] = useState(null);
  const [kicking, setKicking] = useState(false);
  const [pollId, setPollId] = useState(null);
  const [lastRunMs, setLastRunMs] = useState(null);

  const available = providers.filter(p => p.available);

  // Poll /api/studio while factory is running, then reload DD_DATA on completion
  useEffect(() => {
    if (!kicking && !running) return;
    const id = setInterval(async () => {
      try {
        const r = await fetch("/api/studio");
        const data = await r.json();
        setStudioData(data);
        if (!data.run?.running) {
          clearInterval(id);
          setKicking(false);
          // Sync the global DD_DATA so other views also refresh
          if (window.DDX) {
            const full = await window.DDX.reload();
            if (full && full.studio) setStudioData(full.studio);
          }
        }
      } catch (e) {}
    }, 3000);
    setPollId(id);
    return () => clearInterval(id);
  }, [kicking, running]);

  const runFactory = async () => {
    if (kicking || running) return;
    setKicking(true);
    setLastRunMs(Date.now());
    try { await window.DDX?.studioRun(0); } catch (e) { setKicking(false); }
  };
  const regen = async (storyKey, fmt) => {
    setBusyKey(storyKey + ":" + fmt);
    try { await window.DDX?.studioRegenerate(storyKey, fmt); } catch (e) {}
    setBusyKey(null);
    // Refresh just the studio data
    try {
      const r = await fetch("/api/studio");
      const data = await r.json();
      setStudioData(data);
    } catch (e) {
      window.DDX?.reload();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header — providers + run control */}
      <div className="panel crosshair" style={{ overflow: "hidden" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <PanelHeader no="01" actions={
          <>
            {(kicking || running) && lastRunMs && (
              <RunTimer startMs={lastRunMs}/>
            )}
            <span className="chip" style={{ color: available.length ? "var(--signal-up)" : "var(--text-mid)" }}>
              <span style={{ width: 5, height: 5, borderRadius: 999, background: "currentColor",
                animation: kicking || running ? "pulse 1s infinite" : "none" }}/>
              {available.length > 0
                ? `${available.length} provider${available.length > 1 ? "s" : ""} online`
                : "No providers — set ANTHROPIC_API_KEY"}
            </span>
            <button className="btn primary" disabled={kicking || running} onClick={runFactory}>
              {kicking || running ? "Factory running…" : "Run factory now"}
            </button>
          </>
        }>
          Creator Central · autonomous content factory
        </PanelHeader>
        <div style={{ padding: "16px 22px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
          <div>
            <div className="label" style={{ marginBottom: 8 }}>Model CLIs detected</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {providers.map(p => (
                <span key={p.name} className="chip" style={{
                  opacity: p.available ? 1 : 0.4,
                  borderColor: p.available ? "var(--line-hi)" : "var(--line)" }}>
                  <span style={{ width: 5, height: 5, borderRadius: 999,
                    background: p.available ? "var(--signal-up)" : "var(--text-lo)" }}/>
                  {p.name}{p.available && p.model ? ` · ${p.model.split("/").pop()}` : ""}
                </span>
              ))}
            </div>
          </div>
          <div>
            <div className="label" style={{ marginBottom: 8 }}>Generator skills</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {skills.map(s => (
                <span key={s.format} className="chip">{s.icon} {s.label}</span>
              ))}
            </div>
            <p style={{ color: "var(--text-mid)", fontSize: 12, marginTop: 12, marginBottom: 0 }}>
              Top stories are auto-researched and turned into every format, unattended.
              Runs on the hourly schedule; trigger a run above anytime.
            </p>
          </div>
        </div>
      </div>

      {/* Stories */}
      {stories.length === 0 ? (
        <div className="panel crosshair" style={{ padding: "48px 22px", textAlign: "center" }}>
          <span className="ch-bl"/><span className="ch-br"/>
          <h1 className="serif" style={{ fontSize: 24, color: "var(--text-hi)", margin: "0 0 10px", fontWeight: 600 }}>
            No content generated yet
          </h1>
          <p style={{ color: "var(--text-mid)", maxWidth: 440, margin: "0 auto 18px" }}>
            Creator Central picks the top stories and writes shorts, video, podcast and blog
            drafts on its own. Kick the first run to populate it.
          </p>
          <button className="btn primary" disabled={kicking} onClick={runFactory}>
            {kicking ? "Starting…" : "Run factory now"}
          </button>
        </div>
      ) : stories.map(story => (
        <div key={story.story_key} className="panel" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)",
            display: "flex", alignItems: "baseline", gap: 10 }}>
            <h2 className="serif" style={{ fontSize: 20, color: "var(--text-hi)", margin: 0, fontWeight: 600 }}>
              {story.topic}
            </h2>
            <span className="micro">{Object.keys(story.formats || {}).length} formats</span>
            <span style={{ flex: 1 }}/>
            <button className="btn ghost" onClick={() => onJump && onJump("research")}>See research</button>
          </div>
          <div style={{ padding: 16, display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
            {["shorts", "video", "podcast", "blog"].map(fmt => {
              const opp = window.DD_DATA.opportunities?.find(o => o.topic === story.topic || o.slug === story.story_key);
              return (
                <StudioFormatCard key={fmt} storyKey={story.story_key} fmt={fmt}
                  data={(story.formats || {})[fmt]} onRegen={regen}
                  busy={busyKey === story.story_key + ":" + fmt}
                  broll={opp?.broll_list || []}
                  cues={opp?.on_screen_cues || []}/>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
