// PulseView — the hero. Trend radar + cross-source momentum board.
// "Get there first" — the entire screen is built around emergence over time.

const RadarPlot = ({ clusters, onPick, picked }) => {
  const size = 460;
  const cx = size / 2, cy = size / 2;
  const rings = [0.25, 0.5, 0.75, 1];
  const [angle, setAngle] = useState(0);
  useEffect(() => {
    let raf;
    const tick = () => { setAngle(a => (a + 0.5) % 360); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // each ring = age bucket
  const rings_labels = ["NOW", "24h", "72h", "1w+"];

  return (
    <div style={{ position: "relative", width: size, height: size, margin: "0 auto" }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Rings */}
        {rings.map((r, i) => (
          <circle key={i} cx={cx} cy={cy} r={r * (size / 2 - 12)}
                  fill="none" stroke="var(--line-2)" strokeWidth={1}
                  strokeDasharray={i < rings.length - 1 ? "2 4" : "0"}
                  opacity={0.6}/>
        ))}
        {/* Cross axes */}
        <line x1={cx} y1={12} x2={cx} y2={size - 12} stroke="var(--line)" strokeWidth={1}/>
        <line x1={12} y1={cy} x2={size - 12} y2={cy} stroke="var(--line)" strokeWidth={1}/>

        {/* Ring labels */}
        {rings.map((r, i) => (
          <text key={"l" + i} x={cx + 4} y={cy - r * (size / 2 - 12) - 4}
                fill="var(--text-lo)" fontSize="9" fontFamily="var(--font-mono)" letterSpacing="0.08em">
            {rings_labels[i]}
          </text>
        ))}

        {/* Sweep */}
        <defs>
          <linearGradient id="sweep" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%"   stopColor="var(--signal)" stopOpacity="0"/>
            <stop offset="100%" stopColor="var(--signal)" stopOpacity="0.35"/>
          </linearGradient>
        </defs>
        <g transform={`rotate(${angle} ${cx} ${cy})`}>
          <path d={`M ${cx} ${cy} L ${cx + size / 2 - 12} ${cy} A ${size / 2 - 12} ${size / 2 - 12} 0 0 0 ${cx + (size / 2 - 12) * Math.cos(-Math.PI / 4)} ${cy + (size / 2 - 12) * Math.sin(-Math.PI / 4)} Z`}
                fill="url(#sweep)"/>
          <line x1={cx} y1={cy}
                x2={cx + size / 2 - 12} y2={cy}
                stroke="var(--signal)" strokeWidth={1} opacity={0.6}/>
        </g>

        {/* Blips */}
        {clusters.map((c, i) => {
          const r = Math.min(1, c.first_seen_hrs / 168) * (size / 2 - 30);
          const ang = Math.atan2(c.angle_y, c.angle_x);
          const x = cx + Math.cos(ang) * r;
          const y = cy + Math.sin(ang) * r;
          const S = window.DD_DATA.SOURCES;
          const sourceColors = c.sources.map(s => S[s].color);
          const radius = 6 + (c.creator_score - 60) / 6;
          const isPicked = picked === c.slug;
          return (
            <g key={c.slug} onClick={() => onPick(c.slug)} style={{ cursor: "pointer" }}>
              {/* Ping */}
              {c.momentum > 20 && (
                <circle cx={x} cy={y} r={radius} fill="none" stroke={sourceColors[0]} strokeWidth={1}
                        style={{ transformOrigin: `${x}px ${y}px`, animation: "ping 2s ease-out infinite" }}/>
              )}
              {/* Halo if picked */}
              {isPicked && <circle cx={x} cy={y} r={radius + 8} fill="none" stroke="var(--signal)" strokeWidth={1} strokeDasharray="3 3"/>}
              {/* Multi-source ring (each arc = one source family) */}
              {sourceColors.map((col, ci) => {
                const start = (ci / sourceColors.length) * Math.PI * 2;
                const end = ((ci + 1) / sourceColors.length) * Math.PI * 2;
                const x1 = x + Math.cos(start) * (radius + 2);
                const y1 = y + Math.sin(start) * (radius + 2);
                const x2 = x + Math.cos(end) * (radius + 2);
                const y2 = y + Math.sin(end) * (radius + 2);
                return (
                  <path key={ci}
                        d={`M ${x1} ${y1} A ${radius + 2} ${radius + 2} 0 0 1 ${x2} ${y2}`}
                        fill="none" stroke={col} strokeWidth={1.8} strokeLinecap="butt"/>
                );
              })}
              <circle cx={x} cy={y} r={radius} fill={sourceColors[0]} opacity={0.92}/>
              <circle cx={x} cy={y} r={radius - 2} fill="var(--bg-0)"/>
              <text x={x} y={y + 3} fill={sourceColors[0]} fontSize="9" fontFamily="var(--font-mono)" textAnchor="middle" fontWeight={600}>
                {c.creator_score}
              </text>
              <text x={x + radius + 8} y={y + 3}
                    fill={isPicked ? "var(--text-hi)" : "var(--text)"} fontSize="11"
                    fontFamily="var(--font-sans)" fontWeight={isPicked ? 600 : 500}>
                {c.topic}
              </text>
              <text x={x + radius + 8} y={y + 16}
                    fill="var(--text-lo)" fontSize="9.5" fontFamily="var(--font-mono)" letterSpacing="0.04em">
                {c.first_seen_hrs}h · {c.source_count}× sources · {c.momentum > 0 ? "+" : ""}{c.momentum}%
              </text>
            </g>
          );
        })}

        {/* Center mark */}
        <circle cx={cx} cy={cy} r={3} fill="var(--signal)"/>
        <text x={cx + 8} y={cy + 12} fill="var(--text-lo)" fontSize="9" fontFamily="var(--font-mono)" letterSpacing="0.08em">YOU · NOW</text>
      </svg>

      {/* Corner axis labels */}
      <div className="mono" style={{ position: "absolute", top: 4, left: 4, fontSize: 9, color: "var(--text-lo)", letterSpacing: "0.08em" }}>VISUAL</div>
      <div className="mono" style={{ position: "absolute", bottom: 4, left: 4, fontSize: 9, color: "var(--text-lo)", letterSpacing: "0.08em" }}>EXPLAINER</div>
      <div className="mono" style={{ position: "absolute", top: 4, right: 4, fontSize: 9, color: "var(--text-lo)", letterSpacing: "0.08em" }}>DEMO</div>
      <div className="mono" style={{ position: "absolute", bottom: 4, right: 4, fontSize: 9, color: "var(--text-lo)", letterSpacing: "0.08em" }}>CULTURAL</div>
    </div>
  );
};

const PulseDetail = ({ cluster, onJump }) => {
  if (!cluster) return null;
  const S = window.DD_DATA.SOURCES;
  return (
    <div className="panel" style={{ overflow: "hidden", marginTop: 16 }}>
      <PanelHeader no="03"
        actions={
          <>
            <button className="btn ghost" onClick={() => onJump("clusters")}>Open cluster →</button>
            <button className="btn primary" onClick={() => onJump("brief")}>Make this today</button>
          </>
        }>
        Focused signal · {cluster.topic}
      </PanelHeader>
      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr 1fr", gap: 0 }}>
        {/* Why now */}
        <div style={{ padding: "14px 16px", borderRight: "1px solid var(--line)" }}>
          <div className="micro">Why this is a story now</div>
          <p className="serif" style={{
            fontSize: 18, lineHeight: 1.32, marginTop: 8, color: "var(--text-hi)",
            fontStyle: "italic", textWrap: "pretty",
          }}>{cluster.why_this_is_a_story}</p>
          <div className="micro" style={{ marginTop: 16 }}>Recommended angle</div>
          <p style={{ fontSize: 13, lineHeight: 1.45, marginTop: 6, color: "var(--text)", textWrap: "pretty" }}>
            {cluster.recommended_angle}
          </p>
        </div>

        {/* Pulse + scores */}
        <div style={{ padding: "14px 16px", borderRight: "1px solid var(--line)" }}>
          <div className="micro">24h pulse</div>
          <div style={{ marginTop: 10 }}>
            <Waveform data={cluster.pulse} w={280} h={56} color={S[cluster.sources[0]].color}/>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
              <span className="mono" style={{ fontSize: 9.5, color: "var(--text-lo)" }}>−24h</span>
              <span className="mono" style={{ fontSize: 9.5, color: "var(--text-lo)" }}>−12h</span>
              <span className="mono" style={{ fontSize: 9.5, color: "var(--text-hi)" }}>NOW</span>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 14 }}>
            <KPI label="Creator score" value={cluster.creator_score} sub="of 100" color="var(--signal)"/>
            <KPI label="Signal score" value={cluster.average_signal_score} sub="avg of cluster"/>
            <KPI label="Momentum" value={(cluster.momentum > 0 ? "+" : "") + cluster.momentum + "%"} sub="24h Δ"
                 color={cluster.momentum > 0 ? "var(--signal-up)" : "var(--signal-down)"}/>
            <KPI label="First seen" value={cluster.first_seen_hrs + "h"} sub="ago"/>
          </div>
        </div>

        {/* Source evidence */}
        <div style={{ padding: "14px 16px" }}>
          <div className="micro">Source evidence ({cluster.source_count})</div>
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
            {cluster.related_items.slice(0, 5).map((it, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 10, alignItems: "center",
                padding: "6px 8px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
              }}>
                <SourceChip src={it.source_type}/>
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: "var(--text-hi)", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.title}</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2 }}>
                    {[it.stars && `★ ${it.stars}`, it.downloads && `↓ ${it.downloads}`, it.views && `▶ ${it.views}`, it.citations].filter(Boolean).join(" · ")}
                    {it.delta && <span style={{ color: "var(--signal-up)", marginLeft: 6 }}>{it.delta}</span>}
                  </div>
                </div>
                <span className="mono tnum" style={{ fontSize: 11, color: "var(--text-hi)", fontWeight: 600 }}>{it.signal_score}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const PULSE_SORTS = [
  ["momentum", "Momentum", (a, b) => b.momentum - a.momentum],
  ["creator", "Creator score", (a, b) => b.creator_score - a.creator_score],
  ["signal", "Signal", (a, b) => b.average_signal_score - a.average_signal_score],
  ["fresh", "First seen", (a, b) => a.first_seen_hrs - b.first_seen_hrs],
];

const PulseTable = ({ clusters, picked, onPick }) => {
  const [sortIdx, setSortIdx] = useState(0);
  const [demoOnly, setDemoOnly] = useState(false);
  const [, label, cmp] = PULSE_SORTS[sortIdx];
  let rows = demoOnly ? clusters.filter(c => c.has_demoable_item) : clusters.slice();
  rows = rows.sort(cmp);
  return (
    <div className="panel" style={{ overflow: "hidden" }}>
      <PanelHeader no="02"
        actions={
          <>
            <button className="btn ghost" onClick={() => setDemoOnly(v => !v)}
                    style={{ color: demoOnly ? "var(--signal)" : undefined }}>
              <I.Filter size={12}/> {demoOnly ? "Demoable only" : "Filter"}
            </button>
            <button className="btn ghost" onClick={() => setSortIdx(i => (i + 1) % PULSE_SORTS.length)}>
              Sort · {label}
            </button>
          </>
        }>
        Momentum board · {rows.length} active topics
      </PanelHeader>
      <div style={{
        display: "grid",
        gridTemplateColumns: "30px 1.4fr 0.9fr 110px 90px 90px 90px 90px",
        padding: "8px 14px", borderBottom: "1px solid var(--line)",
        color: "var(--text-lo)", fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.06em",
        textTransform: "uppercase", gap: 12,
      }}>
        <span>#</span>
        <span>Topic</span>
        <span>Sources</span>
        <span>24h Pulse</span>
        <span style={{ textAlign: "right" }}>Creator</span>
        <span style={{ textAlign: "right" }}>Signal</span>
        <span style={{ textAlign: "right" }}>Δ24h</span>
        <span style={{ textAlign: "right" }}>First Seen</span>
      </div>
      {rows.map((c, i) => {
        const S = window.DD_DATA.SOURCES;
        const isPicked = picked === c.slug;
        return (
          <div key={c.slug} onClick={() => onPick(c.slug)}
               style={{
                 display: "grid",
                 gridTemplateColumns: "30px 1.4fr 0.9fr 110px 90px 90px 90px 90px",
                 padding: "10px 14px",
                 borderBottom: "1px solid var(--line)",
                 gap: 12, alignItems: "center",
                 cursor: "pointer",
                 background: isPicked ? "var(--bg-2)" : "transparent",
                 borderLeft: isPicked ? "2px solid var(--signal)" : "2px solid transparent",
               }}
               onMouseEnter={e => { if (!isPicked) e.currentTarget.style.background = "var(--bg-2)"; }}
               onMouseLeave={e => { if (!isPicked) e.currentTarget.style.background = "transparent"; }}>
            <span className="mono tnum" style={{ color: "var(--text-lo)", fontSize: 11 }}>{String(i + 1).padStart(2, "0")}</span>
            <div style={{ minWidth: 0 }}>
              <div style={{ color: "var(--text-hi)", fontWeight: 600, fontSize: 13.5, letterSpacing: "-0.005em" }}>{c.topic}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 2 }}>
                {c.best_content_format} · {c.has_demoable_item ? "demoable" : "explainer-only"}
              </div>
            </div>
            <SourceStack sources={c.sources}/>
            <Sparkline data={c.pulse} w={100} h={22} color={S[c.sources[0]].color} dotLast/>
            <span style={{ textAlign: "right" }}>
              <ScoreBar value={c.creator_score} w={60} color="var(--signal)" label={false}/>
              <span className="mono tnum" style={{ fontSize: 11, color: "var(--text-hi)", marginLeft: 6, fontWeight: 600 }}>{c.creator_score}</span>
            </span>
            <span className="mono tnum" style={{ textAlign: "right", color: "var(--text-hi)", fontSize: 12 }}>{c.average_signal_score}</span>
            <span style={{ textAlign: "right" }}><Momentum delta={c.momentum}/></span>
            <span className="mono tnum" style={{ textAlign: "right", color: "var(--text-mid)", fontSize: 11 }}>{c.first_seen_hrs}h</span>
          </div>
        );
      })}
    </div>
  );
};

const PulseView = ({ onJump }) => {
  const { clusters } = window.DD_DATA;
  const [picked, setPicked] = useState(clusters[0] ? clusters[0].slug : null);

  if (!clusters.length) {
    return (
      <div className="panel crosshair" style={{ padding: "48px 22px", textAlign: "center" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <div className="label" style={{ marginBottom: 10 }}>Trend pulse</div>
        <h1 className="serif" style={{ fontSize: 26, color: "var(--text-hi)", margin: "0 0 12px", fontWeight: 600 }}>
          No clusters yet
        </h1>
        <p style={{ color: "var(--text-mid)", maxWidth: 420, margin: "0 auto 18px" }}>
          The radar fills in once sources have been fetched and grouped into cross-source topics.
        </p>
        <button className="btn primary" onClick={() => window.DDX && window.DDX.refresh()}>
          Fetch sources now
        </button>
      </div>
    );
  }

  const focused = clusters.find(c => c.slug === picked) || clusters[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Hero — radar + top stats */}
      <div className="panel crosshair" style={{ overflow: "hidden" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <PanelHeader no="01"
          actions={
            <>
              <span className="chip" style={{ color: "var(--signal-up)", borderColor: "rgba(124,255,178,0.35)", background: "rgba(124,255,178,0.06)" }}>
                <span style={{ width: 5, height: 5, borderRadius: 999, background: "var(--signal-up)" }}/>
                3 emerging now
              </span>
              <button className="btn ghost" onClick={() => window.DDX && window.DDX.refresh()}>Last 7d</button>
              <button className="btn ghost" onClick={() => setPicked(clusters[0].slug)}>Reset</button>
            </>
          }>
          Trend pulse · cross-source emergence radar
        </PanelHeader>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 460px 1fr", padding: "18px 22px", gap: 18, alignItems: "center" }}>
          <div>
            <div className="label">Hero of the day</div>
            <h1 className="serif" style={{
              fontFamily: "var(--font-sans)",
              fontSize: 38, lineHeight: 1.05, letterSpacing: "-0.02em",
              margin: "10px 0 14px", color: "var(--text-hi)", fontWeight: 600,
              textWrap: "balance",
            }}>
              <span style={{ color: "var(--signal)" }}>{focused.topic}</span> is breaking out across {focused.source_count} source families.
            </h1>
            <p style={{ fontSize: 14, lineHeight: 1.55, color: "var(--text)", margin: 0, maxWidth: 380, textWrap: "pretty" }}>
              First lit up <span className="mono" style={{ color: "var(--text-hi)" }}>{focused.first_seen_hrs}h ago</span>.
              Momentum <span style={{ color: "var(--signal-up)" }}>{focused.momentum > 0 ? "+" : ""}{focused.momentum}%</span> in
              the last 24h. The agentic researcher is already pulling a brief.
            </p>
            <div style={{ display: "flex", gap: 8, marginTop: 18, flexWrap: "wrap" }}>
              <button className="btn primary" onClick={() => onJump("brief")}>Open today's brief <I.ArrowR size={12}/></button>
              <button className="btn ghost" onClick={() => onJump("research")}>Watch the research</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginTop: 26, paddingTop: 18, borderTop: "1px solid var(--line)" }}>
              <KPI label="Tracked topics" value="11" sub="+3 today"/>
              <KPI label="Active agents" value="4" sub="researching now" color="var(--signal)"/>
              <KPI label="Avg lead time" value="2.4d" sub="vs press cycle" color="var(--signal-up)"/>
            </div>
          </div>

          <RadarPlot clusters={clusters} picked={picked} onPick={setPicked}/>

          <div>
            <div className="label" style={{ marginBottom: 10 }}>Source pulse · 24h</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {["github","huggingface","youtube","blogs","papers"].map(k => {
                const S = window.DD_DATA.SOURCES[k];
                const h = window.DD_DATA.sourceHealth[k];
                // synthesize per-source pulse from clusters
                const series = Array.from({ length: 24 }, (_, i) =>
                  clusters.filter(c => c.sources.includes(k)).reduce((s, c) => s + c.pulse[i], 0) / 4
                );
                return (
                  <div key={k} style={{
                    display: "grid", gridTemplateColumns: "auto 1fr auto",
                    gap: 10, alignItems: "center",
                    padding: "8px 10px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
                  }}>
                    <SourceChip src={k}/>
                    <Sparkline data={series} w={120} h={22} color={S.color} dotLast/>
                    <span className="mono tnum" style={{ fontSize: 11, color: "var(--text-hi)" }}>
                      {h.items_24h}
                      <span className="mono" style={{
                        fontSize: 9.5, color: h.delta > 0 ? "var(--signal-up)" : "var(--signal-down)", marginLeft: 4
                      }}>{h.delta > 0 ? "+" : ""}{h.delta}</span>
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 10, letterSpacing: "0.04em" }}>
              {window.DD_DATA.sourceHealth.papers.error && (
                <span style={{ color: "var(--signal-down)" }}>⚠ {window.DD_DATA.sourceHealth.papers.error}</span>
              )}
            </div>
          </div>
        </div>
      </div>

      <PulseTable clusters={clusters} picked={picked} onPick={setPicked}/>
      <PulseDetail cluster={focused} onJump={onJump}/>
    </div>
  );
};

window.PulseView = PulseView;
