// Shared primitives: Sparkline, ScoreBar, SourcePulse, SignalRing, SourceChip, RadarPlot

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
    {["github","huggingface","youtube","blogs","papers","hackernews"].map(k => {
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
  <div style={{
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
  Waveform, FakeThumb, FormatBadge, KPI, PanelHeader, downloadScript,
});

