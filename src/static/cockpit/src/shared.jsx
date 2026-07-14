// Shared primitives: Sparkline, ScoreBar, SourcePulse, SignalRing, SourceChip, RadarPlot

const escapeHtml = (value) => String(value || "")
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;")
  .replace(/'/g, "&#039;");

const safeMarkdown = (value) => {
  const source = String(value || "");
  if (!window.marked || !window.DOMPurify) return escapeHtml(source).replace(/\n/g, "<br/>");
  try {
    return window.DOMPurify.sanitize(window.marked.parse(source), { USE_PROFILES: { html: true } });
  } catch (_) {
    return escapeHtml(source).replace(/\n/g, "<br/>");
  }
};

const SourceChip = ({ src, size = "sm" }) => {
  const S = window.DD_DATA.SOURCES[src];
  if (!S) return null;
  const big = size === "md";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: big ? "3px 7px" : "1.5px 6px",
      border: `1px solid ${S.color}40`,
      background: `${S.color}12`,
      color: S.color,
      borderRadius: 999,
      fontFamily: "var(--font-mono)",
      fontSize: big ? 11 : 10,
      letterSpacing: "0.05em",
      textTransform: "uppercase",
      lineHeight: 1,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: 999, background: S.color }} />
      {S.label}
    </span>
  );
};

// Sparkline — accepts array of 0..1 values
const Sparkline = ({ data, w = 80, h = 22, color = "var(--signal)", fill = true, dotLast = false }) => {
  if (!data || !data.length) return null;
  const n = data.length;
  const stepX = w / (n - 1);
  const pts = data.map((v, i) => [i * stepX, h - v * h * 0.92 - h * 0.04]);
  const d = pts.map(([x, y], i) => (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1)).join(" ");
  const dFill = d + ` L ${w.toFixed(1)} ${h.toFixed(1)} L 0 ${h.toFixed(1)} Z`;
  const last = pts[pts.length - 1];
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block" }}>
      {fill && <path d={dFill} fill={color} opacity={0.14} />}
      <path d={d} fill="none" stroke={color} strokeWidth={1.2} strokeLinejoin="round" />
      {dotLast && <circle cx={last[0]} cy={last[1]} r={2} fill={color} />}
    </svg>
  );
};

// Score bar — 0..100. Mono. Cockpit-y.
const ScoreBar = ({ value = 0, w = 80, color, label }) => {
  const v = Math.max(0, Math.min(100, value));
  const segs = 20;
  const lit = Math.round((v / 100) * segs);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ display: "inline-flex", gap: 1.5 }}>
        {Array.from({ length: segs }).map((_, i) => (
          <span key={i} style={{
            width: w / segs - 1.5, height: 8,
            background: i < lit ? (color || "var(--signal)") : "var(--bg-3)",
            opacity: i < lit ? 1 : 0.55,
            borderRadius: 1,
          }}/>
        ))}
      </span>
      {label !== false && (
        <span className="mono tnum" style={{ fontSize: 11, color: "var(--text-hi)", fontWeight: 600 }}>{v}</span>
      )}
    </span>
  );
};

// Momentum arrow
const Momentum = ({ delta, big }) => {
  if (delta === 0 || delta == null) return <span className="mono" style={{ color: "var(--text-lo)", fontSize: big ? 13 : 11 }}>—</span>;
  const up = delta > 0;
  const color = up ? "var(--signal-up)" : "var(--signal-down)";
  return (
    <span className="mono tnum" style={{ color, fontSize: big ? 13 : 11, display: "inline-flex", alignItems: "center", gap: 2, fontWeight: 600 }}>
      {up ? "▲" : "▼"}{Math.abs(delta)}%
    </span>
  );
};

// Source pulse — small stacked bars colored by source
const SourceStack = ({ sources }) => (
  <span style={{ display: "inline-flex", gap: 2 }}>
    {Object.keys(window.DD_DATA.SOURCES || {}).map(k => {
      const S = window.DD_DATA.SOURCES[k];
      const on = sources.includes(k);
      return (
        <span key={k} title={S.label} style={{
          width: 12, height: 4,
          background: on ? S.color : "var(--bg-3)",
          borderRadius: 1,
          opacity: on ? 1 : 0.5,
        }}/>
      );
    })}
  </span>
);

// Pulse waveform — uses source-stacked horizontal bars (24 hours)
const Waveform = ({ data, w = 220, h = 36, color = "var(--signal)" }) => {
  const n = data.length;
  const bw = w / n - 1.2;
  return (
    <svg width={w} height={h}>
      {data.map((v, i) => {
        const bh = Math.max(2, v * h * 0.92);
        return (
          <rect key={i}
            x={i * (bw + 1.2)} y={h - bh}
            width={bw} height={bh}
            fill={color} opacity={0.4 + v * 0.55}
            rx={0.6}
          />
        );
      })}
    </svg>
  );
};

// Thumbnail preview — synthetic 16:9 YT-style card built from data
const FakeThumb = ({ t, w = 220, h = 124 }) => {
  if (!t) return null;
  const hue = t.hue;
  const c1 = `oklch(0.58 0.18 ${hue})`;
  const c2 = `oklch(0.32 0.14 ${hue})`;
  const c3 = `oklch(0.18 0.06 ${hue})`;
  const hasImage = !!t.image_path;

  return (
    <div style={{
      width: w, height: h, borderRadius: 6, overflow: "hidden", position: "relative",
      background: hasImage ? `url(${t.image_path}) no-repeat center/cover` : `linear-gradient(135deg, ${c1} 0%, ${c2} 55%, ${c3} 100%)`,
      boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.08)",
      fontFamily: "var(--font-sans)",
    }}>
      {/* synthetic visual element (only show when no real image) */}
      {!hasImage && (
        <div style={{
          position: "absolute", inset: 0,
          background: t.kind === "race"
            ? `repeating-linear-gradient(90deg, transparent 0 12px, rgba(0,0,0,0.18) 12px 13px)`
            : t.kind === "before-after"
              ? `linear-gradient(90deg, rgba(0,0,0,0.4) 0 50%, transparent 50%)`
              : t.kind === "vs-hero"
                ? `radial-gradient(circle at 70% 40%, rgba(255,255,255,0.25), transparent 50%)`
                : `radial-gradient(circle at 30% 35%, rgba(255,255,255,0.25), transparent 55%)`,
        }}/>
      )}
      {/* face placeholder for face-zoom (only show when no real image) */}
      {!hasImage && (t.kind === "face-zoom") && (
        <div style={{
          position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
          width: h * 0.78, height: h * 0.78, borderRadius: "50%",
          background: `radial-gradient(circle at 35% 35%, oklch(0.85 0.06 ${hue}), oklch(0.55 0.1 ${hue}))`,
          boxShadow: "0 4px 18px rgba(0,0,0,0.4), inset 0 0 0 2px rgba(255,255,255,0.18)",
        }}/>
      )}
      {/* Headline */}
      <div style={{
        position: "absolute", left: 10, bottom: 8, right: (t.kind === "face-zoom" && !hasImage) ? "45%" : 10,
        color: "#fff",
        textShadow: "0 2px 8px rgba(0,0,0,0.8), 0 0 4px rgba(0,0,0,0.9)",
        background: "rgba(0,0,0,0.3)",
        padding: "4px 8px",
        borderRadius: 4,
      }}>
        <div style={{ fontWeight: 800, fontSize: w / 12, lineHeight: 1, letterSpacing: "-0.01em" }}>{t.text}</div>
        <div style={{ fontWeight: 500, fontSize: w / 22, opacity: 0.88, marginTop: 4 }}>{t.subtext}</div>
      </div>
      {/* corner badge */}
      <div className="mono" style={{
        position: "absolute", top: 6, left: 6,
        padding: "1px 4px", background: "rgba(0,0,0,0.55)", color: "#fff",
        fontSize: 9, letterSpacing: "0.06em", borderRadius: 2,
      }}>{(t.kind || "").toUpperCase()}</div>
    </div>
  );
};

// Format icon badge (long-form / short / comparison / tutorial / linkedin)
const FormatBadge = ({ format }) => {
  const map = {
    "YouTube long-form":  { c: "var(--src-youtube)",  label: "LONG" },
    "YouTube short":      { c: "var(--src-youtube)",  label: "SHORT" },
    "Comparison video":   { c: "var(--signal)",        label: "COMPARE" },
    "Tutorial":           { c: "var(--src-github)",    label: "TUTORIAL" },
    "Explainer":          { c: "var(--src-papers)",    label: "EXPLAINER" },
    "LinkedIn post":      { c: "var(--src-blogs)",     label: "LINKEDIN" },
    "LinkedIn carousel":  { c: "var(--src-blogs)",     label: "CAROUSEL" },
    "Livestream demo":    { c: "var(--signal-hot)",    label: "LIVE" },
  };
  const e = map[format] || { c: "var(--text-mid)", label: (format || "").toUpperCase() };
  return (
    <span className="mono" style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 6px", border: `1px solid ${e.c}55`, color: e.c,
      background: `${e.c}10`,
      fontSize: 10, letterSpacing: "0.05em",
      borderRadius: 3,
    }}>
      <span style={{ width: 4, height: 4, background: e.c, borderRadius: 999 }}/>
      {e.label}
    </span>
  );
};

const KPI = ({ label, value, sub, color }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
    <span className="micro">{label}</span>
    <span className="mono tnum" style={{ fontSize: 22, color: color || "var(--text-hi)", fontWeight: 600, letterSpacing: "-0.02em" }}>{value}</span>
    {sub && <span className="mono" style={{ fontSize: 10.5, color: "var(--text-mid)" }}>{sub}</span>}
  </div>
);

// PanelHeader — small uppercase label + actions on the right, ASCII rule
const PanelHeader = ({ children, no, actions }) => (
  <div className="panel-header" style={{
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "10px 14px",
    borderBottom: "1px solid var(--line)",
    background: "linear-gradient(180deg, var(--bg-2), var(--bg-1))",
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      {no && <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.06em" }}>{no}</span>}
      <span className="label" style={{ color: "var(--text-hi)", fontWeight: 600 }}>{children}</span>
    </div>
    {actions && <div style={{ display: "flex", gap: 6 }}>{actions}</div>}
  </div>
);

// Static trend radar. The sweep is CSS-driven so animation never re-renders React.
const TrendRadar = ({ clusters = [], selectedSlug, onSelect }) => {
  const size = 460;
  const center = size / 2;
  const points = React.useMemo(() => clusters.slice(0, 10).map((cluster, index) => {
    const magnitude = Math.hypot(cluster.angle_x || 0, cluster.angle_y || 0);
    const angle = magnitude < 0.05
      ? (index / Math.max(1, clusters.length)) * Math.PI * 2
      : Math.atan2(cluster.angle_y, cluster.angle_x);
    const radius = 45 + Math.min(1, (cluster.first_seen_hrs || 0) / 168) * 158;
    return {
      cluster,
      x: Math.max(34, Math.min(size - 142, center + Math.cos(angle + index * 0.08) * radius)),
      y: Math.max(34, Math.min(size - 34, center + Math.sin(angle + index * 0.08) * radius)),
      radius: Math.max(5, Math.min(12, 5 + ((cluster.creator_score || 60) - 60) / 7)),
    };
  }), [clusters]);

  const activate = (event, slug) => {
    if (event.type === "keydown" && event.key !== "Enter" && event.key !== " ") return;
    if (event.type === "keydown") event.preventDefault();
    if (onSelect) onSelect(slug);
  };

  return (
    <div className="trend-radar">
      <svg viewBox={`0 0 ${size} ${size}`} role="group" aria-label="Interactive trend emergence radar">
        {[0.25, 0.5, 0.75, 1].map((ring, index) => (
          <circle key={ring} cx={center} cy={center} r={ring * (size / 2 - 14)}
                  fill="none" stroke="var(--line-2)" strokeWidth="1"
                  strokeDasharray={index < 3 ? "2 4" : undefined}/>
        ))}
        <line x1={center} y1="14" x2={center} y2={size - 14} stroke="var(--line)"/>
        <line x1="14" y1={center} x2={size - 14} y2={center} stroke="var(--line)"/>
        <defs>
          <linearGradient id="discover-radar-sweep" x1="0" x2="1">
            <stop offset="0%" stopColor="var(--signal)" stopOpacity="0"/>
            <stop offset="100%" stopColor="var(--signal)" stopOpacity="0.28"/>
          </linearGradient>
        </defs>
        <g className="trend-radar__sweep">
          <path d={`M ${center} ${center} L ${size - 14} ${center} A ${size / 2 - 14} ${size / 2 - 14} 0 0 0 ${center + 153} ${center - 153} Z`}
                fill="url(#discover-radar-sweep)"/>
          <line x1={center} y1={center} x2={size - 14} y2={center} stroke="var(--signal)" opacity="0.6"/>
        </g>
        <circle cx={center} cy={center} r="3" fill="var(--signal)"/>
        <text x={center + 8} y={center + 14} className="trend-radar__axis">NOW</text>
        <text x="18" y={center - 7} className="trend-radar__axis">VISUAL</text>
        <text x={size - 18} y={center - 7} textAnchor="end" className="trend-radar__axis">DEMO</text>
        <text x={center + 8} y="24" className="trend-radar__axis">EXPLAINER</text>
        <text x={center + 8} y={size - 17} className="trend-radar__axis">CULTURAL</text>
        {points.map(({ cluster, x, y, radius }) => {
          const source = window.DD_DATA.SOURCES[cluster.sources?.[0]] || { color: "var(--signal)" };
          const selected = cluster.slug === selectedSlug;
          return (
            <g key={cluster.slug} role="button" tabIndex="0"
               aria-label={`${cluster.topic}, creator score ${cluster.creator_score}, momentum ${cluster.momentum || 0} percent`}
               className={`trend-radar__blip${selected ? " trend-radar__blip--selected" : ""}`}
               onClick={event => activate(event, cluster.slug)}
               onKeyDown={event => activate(event, cluster.slug)}>
              {selected && <circle cx={x} cy={y} r={radius + 7} fill="none" stroke="var(--signal)" strokeDasharray="3 3"/>}
              <circle cx={x} cy={y} r={radius} fill="var(--bg-0)" stroke={source.color} strokeWidth="2"/>
              <text x={x} y={y + 3} textAnchor="middle" fill={source.color} className="trend-radar__score">{cluster.creator_score}</text>
              <text x={x + radius + 7} y={y + 3} className="trend-radar__label">{cluster.topic}</text>
              <text x={x + radius + 7} y={y + 15} className="trend-radar__meta">{cluster.first_seen_hrs}h · {cluster.source_count} sources</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const downloadScript = (filename, text) => {
  const element = document.createElement("a");
  const file = new Blob([text], {type: 'text/markdown'});
  element.href = URL.createObjectURL(file);
  element.download = filename;
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
};

Object.assign(window, {
  SourceChip, Sparkline, ScoreBar, Momentum, SourceStack,
  Waveform, FakeThumb, FormatBadge, KPI, PanelHeader, TrendRadar, downloadScript,
});
