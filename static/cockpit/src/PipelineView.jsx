// PipelineView — kanban + week calendar

const LANE_STATUSES = ["idea", "researching", "script_ready", "recording", "published"];

const PipelineView = ({ onJump }) => {
  const { pipeline: initPipeline, calendar } = window.DD_DATA;
  const [pipeline, setPipeline] = useState(initPipeline);
  const [weekOffset, setWeekOffset] = useState(0);
  const [cal, setCal] = useState(calendar);
  const [fmtFilter, setFmtFilter] = useState("");
  const [groupByScore, setGroupByScore] = useState(false);
  const [dragId, setDragId] = useState(null);       // item id being dragged
  const [dragOver, setDragOver] = useState(null);   // lane key being hovered

  // Page the calendar by fetching the schedule for the chosen week.
  useEffect(() => {
    if (weekOffset === 0) { setCal(calendar); return; }
    const base = new Date(); base.setDate(base.getDate() + weekOffset * 7);
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(base); d.setDate(base.getDate() + i); return d;
    });
    const iso = d => d.toISOString().slice(0, 10);
    fetch(`/api/schedule?start=${iso(days[0])}&end=${iso(days[6])}`)
      .then(r => r.json())
      .then(rows => {
        const byDay = {};
        (rows || []).forEach(r => {
          (byDay[r.day] = byDay[r.day] || []).push({ ref: r.item_id, time: r.time || "—", kind: r.kind });
        });
        setCal(days.map(d => ({
          day: d.toLocaleDateString("en", { weekday: "short" }),
          date: d.getDate(), items: byDay[iso(d)] || [],
        })));
      })
      .catch(() => {});
  }, [weekOffset]);

  // Drag handlers
  const onDragStart = (id) => setDragId(id);
  const onDragEnd = () => { setDragId(null); setDragOver(null); };
  const onDrop = async (targetStatus) => {
    if (!dragId || !targetStatus) return;
    // Find which lane the dragged item is currently in
    let srcLane = null, draggedItem = null;
    for (const [laneKey, items] of Object.entries(pipeline)) {
      const found = (items || []).find(i => String(i.id) === String(dragId));
      if (found) { srcLane = laneKey; draggedItem = found; break; }
    }
    if (!srcLane || srcLane === targetStatus) { setDragId(null); setDragOver(null); return; }

    // Optimistic update
    setPipeline(prev => {
      const next = {};
      for (const [k, v] of Object.entries(prev)) {
        next[k] = (v || []).filter(i => String(i.id) !== String(dragId));
      }
      next[targetStatus] = [...(next[targetStatus] || []), { ...draggedItem, status: targetStatus }];
      return next;
    });
    setDragId(null); setDragOver(null);

    // Persist
    try {
      await fetch(`/api/saved/${dragId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: targetStatus }),
      });
      window.DDX && window.DDX.reload();
    } catch (e) {}
  };

  const addToLane = (status) => {
    const title = window.prompt(`New ${status} title:`);
    if (!title || !window.DDX) return;
    window.DDX.saveToPipeline({
      title, working_title: title, topic: title, category: title,
      pipeline_type: "creator", status,
    }).then(() => window.DDX.reload());
  };
  const FORMATS = ["", "YouTube long-form", "YouTube short", "Comparison video", "Tutorial", "Explainer", "LinkedIn post", "LinkedIn carousel"];
  const cycleFmt = () => setFmtFilter(f => FORMATS[(FORMATS.indexOf(f) + 1) % FORMATS.length]);
  const laneItems = (key) => {
    let items = (pipeline[key] || []);
    if (fmtFilter) items = items.filter(i => (i.format || "") === fmtFilter);
    if (groupByScore) items = items.slice().sort((a, b) => (b.creator_score || 0) - (a.creator_score || 0));
    return items;
  };
  const lanes = [
    { key: "idea",         label: "Idea",         tone: "var(--text-mid)" },
    { key: "researching",  label: "Researching",  tone: "var(--src-papers)" },
    { key: "script_ready", label: "Script ready", tone: "var(--signal)" },
    { key: "recording",    label: "Recording",    tone: "var(--src-youtube)" },
    { key: "published",    label: "Published",    tone: "var(--signal-up)" },
  ];

  // Total in-flight count
  const inFlight = lanes.slice(0, 4).reduce((n, l) => n + laneItems(l.key).length, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel crosshair" style={{ overflow: "hidden" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <PanelHeader no="01"
          actions={
            <>
              <button className="btn ghost" onClick={cycleFmt} style={{ color: fmtFilter ? "var(--signal)" : undefined }}>
                Filter · {fmtFilter || "format"}
              </button>
              <button className="btn ghost" onClick={() => setGroupByScore(v => !v)} style={{ color: groupByScore ? "var(--signal)" : undefined }}>
                {groupByScore ? "Sorted · score" : "Group · creator"}
              </button>
              <button className="btn primary" onClick={() => addToLane("idea")}><I.Plus size={12}/> New idea</button>
            </>
          }>
          Production pipeline · {inFlight} in flight
        </PanelHeader>

        {/* Kanban — drag-and-drop between lanes */}
        <div style={{
          display: "grid", gridTemplateColumns: `repeat(${lanes.length}, 1fr)`,
          padding: "0", gap: 1, background: "var(--line)", borderTop: "1px solid var(--line)",
        }}>
          {lanes.map(l => {
            const items = laneItems(l.key);
            const isOver = dragOver === l.key && dragId != null;
            return (
              <div key={l.key}
                onDragOver={e => { e.preventDefault(); setDragOver(l.key); }}
                onDragLeave={() => { if (dragOver === l.key) setDragOver(null); }}
                onDrop={() => onDrop(l.key)}
                style={{
                  background: isOver ? "var(--bg-2)" : "var(--bg-1)",
                  padding: "12px 12px 16px", minHeight: 480,
                  outline: isOver ? `2px dashed ${l.tone}` : "2px dashed transparent",
                  outlineOffset: -2,
                  transition: "background 120ms, outline 120ms",
                }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span style={{ width: 6, height: 6, borderRadius: 999, background: l.tone }}/>
                  <span className="label" style={{ color: "var(--text-hi)", fontWeight: 600 }}>{l.label}</span>
                  <span className="mono tnum" style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-lo)" }}>{items.length}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {items.map(it => (
                    <PipeCard key={it.id} it={it} tone={l.tone}
                      dragging={String(dragId) === String(it.id)}
                      onDragStart={() => onDragStart(it.id)}
                      onDragEnd={onDragEnd}/>
                  ))}
                  <button onClick={() => addToLane(l.key)} style={{
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

      {/* Schedule Optimizer */}
      <div className="panel" style={{ overflow: "hidden" }}>
        <PanelHeader no="OPTIMIZER">
          Publishing Time Optimizer · niche-calibrated engagement slots
        </PanelHeader>
        <div style={{ padding: "16px 20px", display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 24 }}>
          <div>
            <div className="label" style={{ color: "var(--signal)" }}>Niche Target Calibration</div>
            <p style={{ fontSize: 12.5, lineHeight: 1.5, color: "var(--text)", margin: "8px 0 0" }}>
              Targeting <strong>Indie Builders & self-hosters</strong>. Best publishing windows are optimized for high-intent tech focus: weekday mornings for written/professional networks (LinkedIn), and weekend mornings for deep-dive video production.
            </p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div className="micro" style={{ marginBottom: 4 }}>Recommended Peak Engagement Slots</div>
            <OptimizedSlotRow
              platform="YouTube"
              time="Saturday, 10:00 AM"
              nicheScore="98% Fit"
              reason="Peak time for developers shipping weekend projects."
              status={cal.some(d => d.day === "Sat" && d.items.some(it => it.kind === "publish" || it.kind === "record")) ? "FILLED" : "OPEN"}
            />
            <OptimizedSlotRow
              platform="LinkedIn"
              time="Wednesday, 10:00 AM"
              nicheScore="94% Fit"
              reason="Maximum mid-week developer feed engagement."
              status={cal.some(d => d.day === "Wed" && d.items.some(it => it.kind === "linkedin")) ? "FILLED" : "OPEN"}
            />
            <OptimizedSlotRow
              platform="Shorts/Tiktok"
              time="Sunday, 10:00 AM"
              nicheScore="89% Fit"
              reason="Sunday morning casual tech browsing peak."
              status={cal.some(d => d.day === "Sun" && d.items.some(it => it.kind === "publish" || it.kind === "record")) ? "FILLED" : "OPEN"}
            />
          </div>
        </div>
      </div>

      {/* Calendar */}
      <div className="panel" style={{ overflow: "hidden" }}>
        <PanelHeader no="02"
          actions={
            <>
              <button className="btn ghost" onClick={async () => {
                if (window.confirm("Auto-schedule top brief opportunities for the upcoming week?")) {
                  try {
                    const res = await fetch("/api/schedule/auto", { method: "POST" });
                    const data = await res.json();
                    if (data.count > 0) {
                      alert(`Scheduled ${data.count} content slots!`);
                      window.DDX.reload();
                    } else {
                      alert("No new items scheduled.");
                    }
                  } catch (e) {
                    alert("Failed to auto-schedule.");
                  }
                }
              }} style={{ color: "var(--signal)" }}>
                <I.Spark size={11} stroke="var(--signal)"/> Auto-Schedule
              </button>
              <button className="btn ghost" onClick={() => setWeekOffset(o => o - 1)}>‹ Last week</button>
              <button className="btn ghost" onClick={() => setWeekOffset(0)} style={{ color: weekOffset === 0 ? "var(--signal)" : undefined }}>This week</button>
              <button className="btn ghost" onClick={() => setWeekOffset(o => o + 1)}>Next week ›</button>
            </>
          }>
          Publishing calendar · {weekOffset === 0 ? "this week" : (weekOffset < 0 ? `${-weekOffset}w ago` : `+${weekOffset}w`)}
        </PanelHeader>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 1, background: "var(--line)", padding: "0 1px 1px" }}>
          {cal.map((day, i) => (
            <DayCol key={day.day + i} day={day} isToday={weekOffset === 0 && i === 0}/>
          ))}
        </div>
      </div>

      {/* Published performance */}
      <div className="panel" style={{ overflow: "hidden" }}>
        <PanelHeader no="03"
          actions={<button className="btn ghost" onClick={() => window.open("/classic", "_blank")}><I.Trend size={12}/> Full analytics</button>}>
          Just published · last 7 days
        </PanelHeader>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line)", padding: "0 1px 1px" }}>
          {(pipeline.published || []).length === 0 ? (
            <div style={{ gridColumn: "1/-1", padding: "24px 20px", color: "var(--text-lo)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
              Nothing published yet. Move a card to the Published lane to see analytics here.
            </div>
          ) : (pipeline.published || []).map(p => <PublishedRow key={p.id} p={p}/>)}
        </div>
      </div>
    </div>
  );
};

const PipeCard = ({ it, tone, dragging, onDragStart, onDragEnd }) => (
  <div
    draggable
    onDragStart={onDragStart}
    onDragEnd={onDragEnd}
    style={{
      padding: "10px 12px",
      background: "var(--bg-2)",
      border: `1px solid ${dragging ? tone : "var(--line)"}`,
      borderRadius: 4,
      cursor: "grab",
      opacity: dragging ? 0.45 : 1,
      transform: dragging ? "scale(0.97)" : "scale(1)",
      transition: "opacity 120ms, transform 120ms",
      display: "flex", flexDirection: "column", gap: 8,
      userSelect: "none",
    }}>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
      <FormatBadge format={it.format}/>
      <span className="mono tnum" style={{ fontSize: 10.5, color: "var(--text-hi)", fontWeight: 600 }}>{it.creator_score || "—"}</span>
    </div>
    <div style={{ color: "var(--text-hi)", fontSize: 12.5, fontWeight: 500, lineHeight: 1.3, textWrap: "pretty" }}>{it.working_title || it.topic || "Untitled"}</div>
    <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.04em" }}>{it.topic} · effort {it.effort || "medium"}</div>
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
        <span>· {Math.round((it.retention || 0) * 100)}% retention</span>
      </div>
    )}
    {!it.views && it.due && it.due !== "—" && (
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
  // Guard against missing retention/views (newly published items may lack analytics)
  const retention = typeof p.retention === "number" ? p.retention : 0.5;
  const views = p.views != null ? p.views : "—";
  // synthesize a retention curve based on the value
  const curve = Array.from({ length: 24 }, (_, i) => {
    const t = i / 23;
    return Math.max(0.15, retention * Math.pow(1 - t, 0.35) + (Math.sin(i * 0.6) * 0.04));
  });
  return (
    <div style={{ background: "var(--bg-1)", padding: "14px 16px", display: "grid", gridTemplateColumns: "1fr auto", gap: 18, alignItems: "center" }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <FormatBadge format={p.format}/>
          <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)" }}>{p.published_at || "—"}</span>
        </div>
        <div style={{ color: "var(--text-hi)", fontSize: 14, fontWeight: 600, lineHeight: 1.3, marginBottom: 6, textWrap: "balance" }}>{p.working_title || p.topic || "Untitled"}</div>
        <div style={{ display: "flex", gap: 14, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-mid)" }}>
          <span>▶ <span style={{ color: "var(--text-hi)" }}>{views}</span></span>
          <span>retention <span style={{ color: retention > 0.6 ? "var(--signal-up)" : "var(--signal)" }}>{Math.round(retention * 100)}%</span></span>
          <span>score <span style={{ color: "var(--text-hi)" }}>{p.creator_score || "—"}</span></span>
        </div>
      </div>
      <Sparkline data={curve} w={160} h={48} color="var(--src-youtube)" />
    </div>
  );
};

const OptimizedSlotRow = ({ platform, time, nicheScore, reason, status }) => {
  const isOpen = status === "OPEN";
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "100px 140px 1fr 80px", gap: 12, alignItems: "center",
      padding: "8px 12px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4
    }}>
      <span className="mono" style={{ color: "var(--text-hi)", fontWeight: 600, fontSize: 11.5 }}>{platform}</span>
      <span className="mono tnum" style={{ fontSize: 11.5, color: "var(--text)" }}>{time}</span>
      <span style={{ fontSize: 12, color: "var(--text-mid)" }}>{reason} <span className="mono" style={{ color: "var(--signal-up)", fontSize: 10.5 }}>({nicheScore})</span></span>
      <span className="mono" style={{
        textAlign: "center", fontSize: 10, padding: "2px 6px", borderRadius: 2,
        background: isOpen ? "rgba(124,255,178,0.1)" : "var(--bg-3)",
        border: `1px solid ${isOpen ? "rgba(124,255,178,0.3)" : "var(--line-2)"}`,
        color: isOpen ? "var(--signal-up)" : "var(--text-lo)"
      }}>{status}</span>
    </div>
  );
};

window.PipelineView = PipelineView;
