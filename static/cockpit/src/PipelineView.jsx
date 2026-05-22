// PipelineView — kanban + week calendar

const PipelineView = ({ onJump }) => {
  const { pipeline, calendar } = window.DD_DATA;
  const lanes = [
    { key: "idea",         label: "Idea",         tone: "var(--text-mid)" },
    { key: "researching",  label: "Researching",  tone: "var(--src-papers)" },
    { key: "script_ready", label: "Script ready", tone: "var(--signal)" },
    { key: "recording",    label: "Recording",    tone: "var(--src-youtube)" },
    { key: "published",    label: "Published",    tone: "var(--signal-up)" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel crosshair" style={{ overflow: "hidden" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <PanelHeader no="01"
          actions={
            <>
              <button className="btn ghost">Filter · format</button>
              <button className="btn ghost">Group · creator</button>
              <button className="btn primary"><I.Plus size={12}/> New idea</button>
            </>
          }>
          Production pipeline · 6 in flight
        </PanelHeader>

        {/* Kanban */}
        <div style={{
          display: "grid", gridTemplateColumns: `repeat(${lanes.length}, 1fr)`,
          padding: "0", gap: 1, background: "var(--line)", borderTop: "1px solid var(--line)",
        }}>
          {lanes.map(l => {
            const items = pipeline[l.key] || [];
            return (
              <div key={l.key} style={{ background: "var(--bg-1)", padding: "12px 12px 16px", minHeight: 480 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span style={{ width: 6, height: 6, borderRadius: 999, background: l.tone }}/>
                  <span className="label" style={{ color: "var(--text-hi)", fontWeight: 600 }}>{l.label}</span>
                  <span className="mono tnum" style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-lo)" }}>{items.length}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {items.map(it => <PipeCard key={it.id} it={it} tone={l.tone}/>)}
                  <button style={{
                    padding: "8px 10px", border: "1px dashed var(--line-2)", background: "transparent",
                    color: "var(--text-lo)", fontSize: 11.5, borderRadius: 4, cursor: "pointer",
                    fontFamily: "var(--font-mono)", letterSpacing: "0.04em",
                  }}>+ ADD</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Calendar */}
      <div className="panel" style={{ overflow: "hidden" }}>
        <PanelHeader no="02"
          actions={
            <>
              <button className="btn ghost">‹ Last week</button>
              <button className="btn ghost">This week</button>
              <button className="btn ghost">Next week ›</button>
            </>
          }>
          Publishing calendar · week of May 26
        </PanelHeader>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 1, background: "var(--line)", padding: "0 1px 1px" }}>
          {calendar.map((day, i) => (
            <DayCol key={day.day} day={day} isToday={i === 0}/>
          ))}
        </div>
      </div>

      {/* Published performance */}
      <div className="panel" style={{ overflow: "hidden" }}>
        <PanelHeader no="03"
          actions={<button className="btn ghost"><I.Trend size={12}/> Full analytics</button>}>
          Just published · last 7 days
        </PanelHeader>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)", padding: "0 1px 1px" }}>
          {pipeline.published.map(p => <PublishedRow key={p.id} p={p}/>)}
        </div>
      </div>
    </div>
  );
};

const PipeCard = ({ it, tone }) => (
  <div style={{
    padding: "10px 12px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
    cursor: "grab",
    display: "flex", flexDirection: "column", gap: 8,
  }}>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
      <FormatBadge format={it.format}/>
      <span className="mono tnum" style={{ fontSize: 10.5, color: "var(--text-hi)", fontWeight: 600 }}>{it.creator_score}</span>
    </div>
    <div style={{ color: "var(--text-hi)", fontSize: 12.5, fontWeight: 500, lineHeight: 1.3, textWrap: "pretty" }}>{it.working_title}</div>
    <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.04em" }}>{it.topic} · effort {it.effort}</div>
    {it.research_pct !== undefined && (
      <div>
        <div style={{ height: 3, background: "var(--bg-0)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${it.research_pct * 100}%`, background: tone }}/>
        </div>
        <span className="mono" style={{ fontSize: 9.5, color: "var(--text-lo)", marginTop: 4, display: "block" }}>
          agent · {Math.round(it.research_pct * 100)}%
        </span>
      </div>
    )}
    {it.views && (
      <div style={{ display: "flex", gap: 8, fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--text-mid)" }}>
        <span>▶ {it.views}</span>
        <span>· {Math.round(it.retention * 100)}% retention</span>
      </div>
    )}
    {!it.views && it.due !== "—" && (
      <div className="mono" style={{ fontSize: 10, color: tone, letterSpacing: "0.04em" }}>due · {it.due}</div>
    )}
  </div>
);

const DayCol = ({ day, isToday }) => {
  const kindColors = {
    record: "var(--src-youtube)",
    edit: "var(--signal)",
    outline: "var(--text-mid)",
    linkedin: "var(--src-blogs)",
    newsletter: "var(--src-papers)",
    publish: "var(--signal-up)",
  };
  const kindLabels = { record: "RECORD", edit: "EDIT", outline: "OUTLINE", linkedin: "LINKEDIN", newsletter: "NEWSLETTER", publish: "PUBLISH" };
  return (
    <div style={{ background: "var(--bg-1)", minHeight: 240, padding: "10px 10px 12px", borderTop: isToday ? "2px solid var(--signal)" : "2px solid transparent" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 10 }}>
        <span className="mono" style={{ color: isToday ? "var(--signal)" : "var(--text-mid)", fontWeight: 600, fontSize: 11, letterSpacing: "0.06em" }}>{day.day.toUpperCase()}</span>
        <span className="mono tnum" style={{ color: isToday ? "var(--text-hi)" : "var(--text-lo)", fontSize: 16, fontWeight: 600 }}>{day.date}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {day.items.map((it, i) => (
          <div key={i} style={{
            padding: "6px 8px",
            background: "var(--bg-2)",
            borderLeft: `2px solid ${kindColors[it.kind]}`,
            borderRadius: 2,
          }}>
            <div className="mono" style={{ fontSize: 9.5, color: kindColors[it.kind], letterSpacing: "0.05em" }}>{kindLabels[it.kind]}</div>
            <div className="mono tnum" style={{ fontSize: 10.5, color: "var(--text-hi)", marginTop: 2 }}>{it.time}</div>
          </div>
        ))}
        {day.items.length === 0 && (
          <span className="mono" style={{ fontSize: 10, color: "var(--text-vlo)", letterSpacing: "0.04em" }}>— open —</span>
        )}
      </div>
    </div>
  );
};

const PublishedRow = ({ p }) => {
  // synthesize a retention curve based on the value
  const curve = Array.from({ length: 24 }, (_, i) => {
    const t = i / 23;
    return Math.max(0.15, p.retention * Math.pow(1 - t, 0.35) + (Math.sin(i * 0.6) * 0.04));
  });
  return (
    <div style={{ background: "var(--bg-1)", padding: "14px 16px", display: "grid", gridTemplateColumns: "1fr auto", gap: 18, alignItems: "center" }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <FormatBadge format={p.format}/>
          <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)" }}>{p.published_at}</span>
        </div>
        <div style={{ color: "var(--text-hi)", fontSize: 14, fontWeight: 600, lineHeight: 1.3, marginBottom: 6, textWrap: "balance" }}>{p.working_title}</div>
        <div style={{ display: "flex", gap: 14, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-mid)" }}>
          <span>▶ <span style={{ color: "var(--text-hi)" }}>{p.views}</span></span>
          <span>retention <span style={{ color: p.retention > 0.6 ? "var(--signal-up)" : "var(--signal)" }}>{Math.round(p.retention * 100)}%</span></span>
          <span>score <span style={{ color: "var(--text-hi)" }}>{p.creator_score}</span></span>
        </div>
      </div>
      <Sparkline data={curve} w={160} h={48} color="var(--src-youtube)" />
    </div>
  );
};

window.PipelineView = PipelineView;
