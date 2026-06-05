// PulseView — the hero. Trend radar + cross-source momentum board.
// "Get there first" — the entire screen is built around emergence over time.

const RadarPlot = ({
  clusters,
  onPick,
  picked
}) => {
  const size = 460;
  const cx = size / 2,
    cy = size / 2;
  const rings = [0.25, 0.5, 0.75, 1];
  const [angle, setAngle] = useState(0);
  const [hoveredBlip, setHoveredBlip] = useState(null);
  useEffect(() => {
    let raf;
    const tick = () => {
      setAngle(a => (a + 0.5) % 360);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // each ring = age bucket
  const rings_labels = ["NOW", "24h", "72h", "1w+"];
  const rawBlips = clusters.map((c, i) => {
    const minR = 45;
    const maxR = size / 2 - 35;
    const r = minR + Math.min(1, c.first_seen_hrs / 168) * (maxR - minR);
    const mag = Math.hypot(c.angle_x, c.angle_y);
    const baseAng = mag < 0.05 ? i * (360 / clusters.length) * Math.PI / 180 : Math.atan2(c.angle_y, c.angle_x);
    // Add deterministic angular spread so they don't align on a straight line
    const ang = baseAng + (i - clusters.length / 2) * 0.18;
    return {
      cluster: c,
      i,
      x: cx + Math.cos(ang) * r,
      y: cy + Math.sin(ang) * r,
      radius: 6 + (c.creator_score - 60) / 6
    };
  });

  // Relaxation loop to resolve overlaps
  const adjustedBlips = [...rawBlips];
  const iterations = 80;
  const minVerticalDist = 20; // text line height/vertical clearance
  const minHorizontalDist = 120; // horizontal region of label collision
  const minR = 45;
  for (let step = 0; step < iterations; step++) {
    for (let j = 0; j < adjustedBlips.length; j++) {
      for (let k = j + 1; k < adjustedBlips.length; k++) {
        const a = adjustedBlips[j];
        const b = adjustedBlips[k];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy);

        // 1. Circle overlap check
        const rSum = a.radius + b.radius + 12; // sum of radii + padding
        if (dist < rSum) {
          const push = (rSum - dist) / 2;
          const ux = dist > 0.1 ? dx / dist : Math.cos(j);
          const uy = dist > 0.1 ? dy / dist : Math.sin(j);
          a.x -= ux * push;
          a.y -= uy * push;
          b.x += ux * push;
          b.y += uy * push;
        }

        // 2. Text/label overlap check (horizontal proximity requires vertical stack)
        if (Math.abs(a.x - b.x) < minHorizontalDist && Math.abs(a.y - b.y) < minVerticalDist) {
          const overlap = minVerticalDist - Math.abs(a.y - b.y);
          const pushY = overlap / 2;
          if (a.y <= b.y) {
            a.y -= pushY;
            b.y += pushY;
          } else {
            a.y += pushY;
            b.y -= pushY;
          }
        }

        // 3. Enforce minimum radius from center (repel from center NOW zone)
        const distA = Math.hypot(a.x - cx, a.y - cy);
        if (distA < minR) {
          const ux = distA > 0.1 ? (a.x - cx) / distA : 1;
          const uy = distA > 0.1 ? (a.y - cy) / distA : 0;
          a.x = cx + ux * minR;
          a.y = cy + uy * minR;
        }
        const distB = Math.hypot(b.x - cx, b.y - cy);
        if (distB < minR) {
          const ux = distB > 0.1 ? (b.x - cx) / distB : 1;
          const uy = distB > 0.1 ? (b.y - cy) / distB : 0;
          b.x = cx + ux * minR;
          b.y = cy + uy * minR;
        }

        // Clamp to SVG view box boundaries
        a.x = Math.max(25, Math.min(size - 130, a.x));
        a.y = Math.max(25, Math.min(size - 25, a.y));
        b.x = Math.max(25, Math.min(size - 130, b.x));
        b.y = Math.max(25, Math.min(size - 25, b.y));
      }
    }
  }

  // Final clamping pass to guarantee all blips and text labels stay inside the canvas
  adjustedBlips.forEach(b => {
    b.x = Math.max(30, Math.min(size - 140, b.x));
    b.y = Math.max(35, Math.min(size - 30, b.y));
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      width: size,
      height: size,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: `0 0 ${size} ${size}`
  }, rings.map((r, i) => /*#__PURE__*/React.createElement("circle", {
    key: i,
    cx: cx,
    cy: cy,
    r: r * (size / 2 - 12),
    fill: "none",
    stroke: "var(--line-2)",
    strokeWidth: 1,
    strokeDasharray: i < rings.length - 1 ? "2 4" : "0",
    opacity: 0.6
  })), /*#__PURE__*/React.createElement("line", {
    x1: cx,
    y1: 12,
    x2: cx,
    y2: size - 12,
    stroke: "var(--line)",
    strokeWidth: 1
  }), /*#__PURE__*/React.createElement("line", {
    x1: 12,
    y1: cy,
    x2: size - 12,
    y2: cy,
    stroke: "var(--line)",
    strokeWidth: 1
  }), rings.map((r, i) => /*#__PURE__*/React.createElement("text", {
    key: "l" + i,
    x: cx + 4,
    y: cy - r * (size / 2 - 12) - 4,
    fill: "var(--text-lo)",
    fontSize: "9",
    fontFamily: "var(--font-mono)",
    letterSpacing: "0.08em"
  }, rings_labels[i])), /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("linearGradient", {
    id: "sweep",
    x1: "0",
    x2: "1",
    y1: "0",
    y2: "0"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0%",
    stopColor: "var(--signal)",
    stopOpacity: "0"
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "100%",
    stopColor: "var(--signal)",
    stopOpacity: "0.35"
  }))), /*#__PURE__*/React.createElement("g", {
    transform: `rotate(${angle} ${cx} ${cy})`
  }, /*#__PURE__*/React.createElement("path", {
    d: `M ${cx} ${cy} L ${cx + size / 2 - 12} ${cy} A ${size / 2 - 12} ${size / 2 - 12} 0 0 0 ${cx + (size / 2 - 12) * Math.cos(-Math.PI / 4)} ${cy + (size / 2 - 12) * Math.sin(-Math.PI / 4)} Z`,
    fill: "url(#sweep)"
  }), /*#__PURE__*/React.createElement("line", {
    x1: cx,
    y1: cy,
    x2: cx + size / 2 - 12,
    y2: cy,
    stroke: "var(--signal)",
    strokeWidth: 1,
    opacity: 0.6
  })), adjustedBlips.map(bInfo => {
    const c = bInfo.cluster;
    const {
      x,
      y,
      radius
    } = bInfo;
    const S = window.DD_DATA.SOURCES;
    const sourceColors = c.sources.map(s => S[s].color);
    const isPicked = picked === c.slug;
    return /*#__PURE__*/React.createElement("g", {
      key: c.slug,
      onClick: () => onPick(c.slug),
      style: {
        cursor: "pointer"
      },
      onMouseEnter: () => setHoveredBlip(bInfo),
      onMouseLeave: () => setHoveredBlip(null)
    }, c.momentum > 20 && /*#__PURE__*/React.createElement("circle", {
      cx: x,
      cy: y,
      r: radius,
      fill: "none",
      stroke: sourceColors[0],
      strokeWidth: 1,
      style: {
        transformOrigin: `${x}px ${y}px`,
        animation: "ping 2s ease-out infinite"
      }
    }), isPicked && /*#__PURE__*/React.createElement("circle", {
      cx: x,
      cy: y,
      r: radius + 8,
      fill: "none",
      stroke: "var(--signal)",
      strokeWidth: 1,
      strokeDasharray: "3 3"
    }), sourceColors.map((col, ci) => {
      const start = ci / sourceColors.length * Math.PI * 2;
      const end = (ci + 1) / sourceColors.length * Math.PI * 2;
      const x1 = x + Math.cos(start) * (radius + 2);
      const y1 = y + Math.sin(start) * (radius + 2);
      const x2 = x + Math.cos(end) * (radius + 2);
      const y2 = y + Math.sin(end) * (radius + 2);
      return /*#__PURE__*/React.createElement("path", {
        key: ci,
        d: `M ${x1} ${y1} A ${radius + 2} ${radius + 2} 0 0 1 ${x2} ${y2}`,
        fill: "none",
        stroke: col,
        strokeWidth: 1.8,
        strokeLinecap: "butt"
      });
    }), /*#__PURE__*/React.createElement("circle", {
      cx: x,
      cy: y,
      r: radius,
      fill: sourceColors[0],
      opacity: 0.92
    }), /*#__PURE__*/React.createElement("circle", {
      cx: x,
      cy: y,
      r: radius - 2,
      fill: "var(--bg-0)"
    }), /*#__PURE__*/React.createElement("text", {
      x: x,
      y: y + 3,
      fill: sourceColors[0],
      fontSize: "9",
      fontFamily: "var(--font-mono)",
      textAnchor: "middle",
      fontWeight: 600
    }, c.creator_score), /*#__PURE__*/React.createElement("text", {
      x: x + radius + 8,
      y: y + 3,
      fill: isPicked ? "var(--text-hi)" : "var(--text)",
      fontSize: "11",
      fontFamily: "var(--font-sans)",
      fontWeight: isPicked ? 600 : 500
    }, c.topic), /*#__PURE__*/React.createElement("text", {
      x: x + radius + 8,
      y: y + 14,
      fill: "var(--text-lo)",
      fontSize: "9.5",
      fontFamily: "var(--font-mono)",
      letterSpacing: "0.04em"
    }, c.first_seen_hrs, "h \xB7 ", c.source_count, "\xD7 sources \xB7 ", c.momentum > 0 ? "+" : "", c.momentum, "%"));
  }), /*#__PURE__*/React.createElement("circle", {
    cx: cx,
    cy: cy,
    r: 3,
    fill: "var(--signal)"
  }), /*#__PURE__*/React.createElement("text", {
    x: cx + 8,
    y: cy + 12,
    fill: "var(--text-lo)",
    fontSize: "9",
    fontFamily: "var(--font-mono)",
    letterSpacing: "0.08em"
  }, "YOU \xB7 NOW"), /*#__PURE__*/React.createElement("text", {
    x: 18,
    y: cy - 6,
    fill: "var(--text-lo)",
    fontSize: "9",
    fontFamily: "var(--font-mono)",
    letterSpacing: "0.08em"
  }, "VISUAL"), /*#__PURE__*/React.createElement("text", {
    x: size - 18,
    y: cy - 6,
    fill: "var(--text-lo)",
    fontSize: "9",
    fontFamily: "var(--font-mono)",
    letterSpacing: "0.08em",
    textAnchor: "end"
  }, "DEMO"), /*#__PURE__*/React.createElement("text", {
    x: cx + 8,
    y: 22,
    fill: "var(--text-lo)",
    fontSize: "9",
    fontFamily: "var(--font-mono)",
    letterSpacing: "0.08em"
  }, "EXPLAINER"), /*#__PURE__*/React.createElement("text", {
    x: cx + 8,
    y: size - 16,
    fill: "var(--text-lo)",
    fontSize: "9",
    fontFamily: "var(--font-mono)",
    letterSpacing: "0.08em"
  }, "CULTURAL")), hoveredBlip && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      left: hoveredBlip.x,
      top: hoveredBlip.y - 48,
      transform: "translateX(-50%)",
      pointerEvents: "none",
      background: "rgba(22, 22, 26, 0.88)",
      backdropFilter: "blur(12px) saturate(180%)",
      border: "1px solid var(--line-2)",
      boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.4)",
      borderRadius: 6,
      padding: "8px 12px",
      zIndex: 100,
      minWidth: 160,
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      fontSize: 11.5,
      color: "var(--text-hi)",
      marginBottom: 2
    }
  }, hoveredBlip.cluster.topic), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 9.5,
      color: "var(--text-lo)"
    }
  }, "Score: ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal)",
      fontWeight: 600
    }
  }, hoveredBlip.cluster.creator_score), " \xB7 ", hoveredBlip.cluster.source_count, "\xD7 sources")));
};
const PulseDetail = ({
  cluster,
  onJump
}) => {
  if (!cluster) return null;
  const S = window.DD_DATA.SOURCES;
  return /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      overflow: "hidden",
      marginTop: 16
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "03",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => onJump("clusters")
    }, "Open cluster \u2192"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      style: {
        color: "var(--signal-down)",
        borderColor: "rgba(255,90,90,0.3)"
      },
      onClick: async () => {
        if (confirm(`Ignore trend cluster "${cluster.topic}"? This will hide all associated items.`)) {
          await window.DDX.ignoreTopic(cluster.topic, cluster.related_items);
          window.DDX.refresh();
        }
      }
    }, "Ignore Trend"), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      onClick: () => onJump("brief")
    }, "Make this today"))
  }, "Focused signal \xB7 ", cluster.topic), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.1fr 1fr 1fr",
      gap: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "14px 16px",
      borderRight: "1px solid var(--line)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro"
  }, "Why this is a story now"), /*#__PURE__*/React.createElement("p", {
    className: "serif",
    style: {
      fontSize: 18,
      lineHeight: 1.32,
      marginTop: 8,
      color: "var(--text-hi)",
      fontStyle: "italic",
      textWrap: "pretty"
    }
  }, cluster.why_this_is_a_story), /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginTop: 16
    }
  }, "Recommended angle"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 13,
      lineHeight: 1.45,
      marginTop: 6,
      color: "var(--text)",
      textWrap: "pretty"
    }
  }, cluster.recommended_angle)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "14px 16px",
      borderRight: "1px solid var(--line)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro"
  }, "24h pulse"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 10
    }
  }, /*#__PURE__*/React.createElement(Waveform, {
    data: cluster.pulse,
    w: 280,
    h: 56,
    color: S[cluster.sources[0]].color
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      marginTop: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 9.5,
      color: "var(--text-lo)"
    }
  }, "\u221224h"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 9.5,
      color: "var(--text-lo)"
    }
  }, "\u221212h"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 9.5,
      color: "var(--text-hi)"
    }
  }, "NOW"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 12,
      marginTop: 14
    }
  }, /*#__PURE__*/React.createElement(KPI, {
    label: "Creator score",
    value: cluster.creator_score,
    sub: "of 100",
    color: "var(--signal)"
  }), /*#__PURE__*/React.createElement(KPI, {
    label: "Signal score",
    value: cluster.average_signal_score,
    sub: "avg of cluster"
  }), /*#__PURE__*/React.createElement(KPI, {
    label: "Momentum",
    value: (cluster.momentum > 0 ? "+" : "") + cluster.momentum + "%",
    sub: "24h \u0394",
    color: cluster.momentum > 0 ? "var(--signal-up)" : "var(--signal-down)"
  }), /*#__PURE__*/React.createElement(KPI, {
    label: "First seen",
    value: cluster.first_seen_hrs + "h",
    sub: "ago"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 16,
      paddingTop: 14,
      borderTop: "1px solid var(--line)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginBottom: 8
    }
  }, "Creator Score Breakdown"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      fontSize: 11
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-mid)"
    }
  }, "\uD83D\uDCC5 Recency"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--text-hi)"
    }
  }, cluster.score_breakdown?.recency ?? 50, "/100")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      fontSize: 11
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-mid)"
    }
  }, "\uD83D\uDD25 Popularity & Growth"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--text-hi)"
    }
  }, cluster.score_breakdown?.popularity ?? 50, "/100")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      fontSize: 11
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-mid)"
    }
  }, "\uD83E\uDD16 Agentic Suitability"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--text-hi)"
    }
  }, cluster.score_breakdown?.agentic ?? 50, "/100")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      fontSize: 11
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-mid)"
    }
  }, "\uD83D\uDD0C Local Suitability"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--text-hi)"
    }
  }, cluster.score_breakdown?.local ?? 50, "/100")))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 16,
      paddingTop: 14,
      borderTop: "1px solid var(--line)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginBottom: 8
    }
  }, "Score Changelog"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      maxHeight: 100,
      overflowY: "auto"
    }
  }, (cluster.changelog || []).map((ch, idx) => /*#__PURE__*/React.createElement("div", {
    key: idx,
    style: {
      fontSize: 11,
      lineHeight: 1.35,
      padding: "5px 8px",
      borderRadius: 4,
      background: ch.type === "up" ? "rgba(124,255,178,0.06)" : ch.type === "down" ? "rgba(255,107,107,0.06)" : "var(--bg-0)",
      borderLeft: `2px solid ${ch.type === "up" ? "var(--signal-up)" : ch.type === "down" ? "var(--signal-down)" : "var(--line-hi)"}`,
      color: "var(--text-hi)"
    }
  }, ch.message))))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "14px 16px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro"
  }, "Source evidence (", cluster.source_count, ")"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, cluster.related_items.slice(0, 5).map((it, i) => /*#__PURE__*/React.createElement("a", {
    href: it.url,
    target: "_blank",
    rel: "noopener noreferrer",
    key: i,
    className: "evidence-link",
    style: {
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      gap: 10,
      alignItems: "center",
      padding: "6px 8px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 4,
      textDecoration: "none",
      cursor: "pointer",
      transition: "border-color 0.15s ease, background 0.15s ease"
    },
    onMouseEnter: e => {
      e.currentTarget.style.borderColor = "var(--signal)";
      e.currentTarget.style.background = "var(--bg-3)";
    },
    onMouseLeave: e => {
      e.currentTarget.style.borderColor = "var(--line)";
      e.currentTarget.style.background = "var(--bg-2)";
    }
  }, /*#__PURE__*/React.createElement(SourceChip, {
    src: it.source_type
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontSize: 12,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, it.title), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      marginTop: 2
    }
  }, [it.stars && `★ ${it.stars}`, it.downloads && `↓ ${it.downloads}`, it.views && `▶ ${it.views}`, it.citations].filter(Boolean).join(" · "), it.delta && /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal-up)",
      marginLeft: 6
    }
  }, it.delta))), /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      fontSize: 11,
      color: "var(--text-hi)",
      fontWeight: 600
    }
  }, it.signal_score)))))));
};
const PULSE_SORTS = [["momentum", "Momentum", (a, b) => b.momentum - a.momentum], ["creator", "Creator score", (a, b) => b.creator_score - a.creator_score], ["signal", "Signal", (a, b) => b.average_signal_score - a.average_signal_score], ["fresh", "First seen", (a, b) => a.first_seen_hrs - b.first_seen_hrs]];
const PulseTable = ({
  clusters,
  picked,
  onPick
}) => {
  const [sortIdx, setSortIdx] = useState(0);
  const [demoOnly, setDemoOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [, label, cmp] = PULSE_SORTS[sortIdx];
  let rows = demoOnly ? clusters.filter(c => c.has_demoable_item) : clusters.slice();
  if (searchQuery) {
    rows = rows.filter(c => c.topic.toLowerCase().includes(searchQuery.toLowerCase()));
  }
  rows = rows.sort(cmp);
  return /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "02",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("input", {
      type: "text",
      placeholder: "Search trends...",
      value: searchQuery,
      onChange: e => setSearchQuery(e.target.value),
      style: {
        background: "var(--bg-3)",
        border: "1px solid var(--line)",
        borderRadius: 4,
        padding: "4px 8px",
        fontSize: 11,
        color: "var(--text-hi)",
        fontFamily: "var(--font-sans)",
        outline: "none",
        width: 140,
        marginRight: 8
      }
    }), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setDemoOnly(v => !v),
      style: {
        color: demoOnly ? "var(--signal)" : undefined
      }
    }, /*#__PURE__*/React.createElement(I.Filter, {
      size: 12
    }), " ", demoOnly ? "Demoable only" : "Filter"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setSortIdx(i => (i + 1) % PULSE_SORTS.length)
    }, "Sort \xB7 ", label))
  }, "Momentum board \xB7 ", rows.length, " active topics"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "30px 1.4fr 0.9fr 110px 90px 90px 90px 90px",
      padding: "8px 14px",
      borderBottom: "1px solid var(--line)",
      color: "var(--text-lo)",
      fontFamily: "var(--font-mono)",
      fontSize: 10,
      letterSpacing: "0.06em",
      textTransform: "uppercase",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", null, "#"), /*#__PURE__*/React.createElement("span", null, "Topic"), /*#__PURE__*/React.createElement("span", null, "Sources"), /*#__PURE__*/React.createElement("span", null, "24h Pulse"), /*#__PURE__*/React.createElement("span", {
    style: {
      textAlign: "right"
    }
  }, "Creator"), /*#__PURE__*/React.createElement("span", {
    style: {
      textAlign: "right"
    }
  }, "Signal"), /*#__PURE__*/React.createElement("span", {
    style: {
      textAlign: "right"
    }
  }, "\u039424h"), /*#__PURE__*/React.createElement("span", {
    style: {
      textAlign: "right"
    }
  }, "First Seen")), rows.map((c, i) => {
    const S = window.DD_DATA.SOURCES;
    const isPicked = picked === c.slug;
    return /*#__PURE__*/React.createElement("div", {
      key: c.slug,
      onClick: () => onPick(c.slug),
      style: {
        display: "grid",
        gridTemplateColumns: "30px 1.4fr 0.9fr 110px 90px 90px 90px 90px",
        padding: "10px 14px",
        borderBottom: "1px solid var(--line)",
        gap: 12,
        alignItems: "center",
        cursor: "pointer",
        background: isPicked ? "var(--bg-2)" : "transparent",
        borderLeft: isPicked ? "2px solid var(--signal)" : "2px solid transparent"
      },
      onMouseEnter: e => {
        if (!isPicked) e.currentTarget.style.background = "var(--bg-2)";
      },
      onMouseLeave: e => {
        if (!isPicked) e.currentTarget.style.background = "transparent";
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "mono tnum",
      style: {
        color: "var(--text-lo)",
        fontSize: 11
      }
    }, String(i + 1).padStart(2, "0")), /*#__PURE__*/React.createElement("div", {
      style: {
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        color: "var(--text-hi)",
        fontWeight: 600,
        fontSize: 13.5,
        letterSpacing: "-0.005em"
      }
    }, c.topic), /*#__PURE__*/React.createElement("div", {
      className: "mono",
      style: {
        fontSize: 10,
        color: "var(--text-lo)",
        marginTop: 2
      }
    }, c.best_content_format, " \xB7 ", c.has_demoable_item ? "demoable" : "explainer-only")), /*#__PURE__*/React.createElement(SourceStack, {
      sources: c.sources
    }), /*#__PURE__*/React.createElement(Sparkline, {
      data: c.pulse,
      w: 100,
      h: 22,
      color: S[c.sources[0]].color,
      dotLast: true
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        textAlign: "right"
      }
    }, /*#__PURE__*/React.createElement(ScoreBar, {
      value: c.creator_score,
      w: 60,
      color: "var(--signal)",
      label: false
    }), /*#__PURE__*/React.createElement("span", {
      className: "mono tnum",
      style: {
        fontSize: 11,
        color: "var(--text-hi)",
        marginLeft: 6,
        fontWeight: 600
      }
    }, c.creator_score)), /*#__PURE__*/React.createElement("span", {
      className: "mono tnum",
      style: {
        textAlign: "right",
        color: "var(--text-hi)",
        fontSize: 12
      }
    }, c.average_signal_score), /*#__PURE__*/React.createElement("span", {
      style: {
        textAlign: "right"
      }
    }, /*#__PURE__*/React.createElement(Momentum, {
      delta: c.momentum
    })), /*#__PURE__*/React.createElement("span", {
      className: "mono tnum",
      style: {
        textAlign: "right",
        color: "var(--text-mid)",
        fontSize: 11
      }
    }, c.first_seen_hrs, "h"));
  }));
};
const PulseView = ({
  onJump
}) => {
  const {
    clusters
  } = window.DD_DATA;
  const [picked, setPicked] = useState(clusters[0] ? clusters[0].slug : null);
  if (!clusters.length) {
    return /*#__PURE__*/React.createElement("div", {
      className: "panel crosshair",
      style: {
        padding: "48px 22px",
        textAlign: "center"
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "ch-bl"
    }), /*#__PURE__*/React.createElement("span", {
      className: "ch-br"
    }), /*#__PURE__*/React.createElement("div", {
      className: "label",
      style: {
        marginBottom: 10
      }
    }, "Trend pulse"), /*#__PURE__*/React.createElement("h1", {
      className: "serif",
      style: {
        fontSize: 26,
        color: "var(--text-hi)",
        margin: "0 0 12px",
        fontWeight: 600
      }
    }, "No clusters yet"), /*#__PURE__*/React.createElement("p", {
      style: {
        color: "var(--text-mid)",
        maxWidth: 420,
        margin: "0 auto 18px"
      }
    }, "The radar fills in once sources have been fetched and grouped into cross-source topics."), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      onClick: () => window.DDX && window.DDX.refresh()
    }, "Fetch sources now"));
  }
  const focused = clusters.find(c => c.slug === picked) || clusters[0];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel crosshair",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "ch-bl"
  }), /*#__PURE__*/React.createElement("span", {
    className: "ch-br"
  }), /*#__PURE__*/React.createElement(PanelHeader, {
    no: "01",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      className: "chip",
      style: {
        color: "var(--signal-up)",
        borderColor: "rgba(124,255,178,0.35)",
        background: "rgba(124,255,178,0.06)"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 5,
        height: 5,
        borderRadius: 999,
        background: "var(--signal-up)"
      }
    }), "3 emerging now"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => window.DDX && window.DDX.refresh()
    }, "Last 7d"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setPicked(clusters[0].slug)
    }, "Reset"))
  }, "Trend pulse \xB7 cross-source emergence radar"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 460px 1fr",
      padding: "18px 22px",
      gap: 18,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label"
  }, "Hero of the day"), /*#__PURE__*/React.createElement("h1", {
    className: "serif",
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: 38,
      lineHeight: 1.05,
      letterSpacing: "-0.02em",
      margin: "10px 0 14px",
      color: "var(--text-hi)",
      fontWeight: 600,
      textWrap: "balance"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal)"
    }
  }, focused.topic), " is breaking out across ", focused.source_count, " source families."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 14,
      lineHeight: 1.55,
      color: "var(--text)",
      margin: 0,
      maxWidth: 380,
      textWrap: "pretty"
    }
  }, "First lit up ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--text-hi)"
    }
  }, focused.first_seen_hrs, "h ago"), ". Momentum ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal-up)"
    }
  }, focused.momentum > 0 ? "+" : "", focused.momentum, "%"), " in the last 24h. The agentic researcher is already pulling a brief."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      marginTop: 18,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: () => onJump("brief")
  }, "Open today's brief ", /*#__PURE__*/React.createElement(I.ArrowR, {
    size: 12
  })), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: () => onJump("research")
  }, "Watch the research")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr 1fr",
      gap: 16,
      marginTop: 26,
      paddingTop: 18,
      borderTop: "1px solid var(--line)"
    }
  }, /*#__PURE__*/React.createElement(KPI, {
    label: "Tracked topics",
    value: window.DD_DATA.stats?.tracked_topics_count ?? 11,
    sub: "in pipeline"
  }), /*#__PURE__*/React.createElement(KPI, {
    label: "Active agents",
    value: window.DD_DATA.agents?.active?.length ?? window.DD_DATA.stats?.active_agents_count ?? 4,
    sub: "researching now",
    color: "var(--signal)"
  }), /*#__PURE__*/React.createElement(KPI, {
    label: "Avg lead time",
    value: `${window.DD_DATA.stats?.avg_lead_time_days ?? 2.4}d`,
    sub: "vs press cycle",
    color: "var(--signal-up)"
  }))), /*#__PURE__*/React.createElement(RadarPlot, {
    clusters: clusters,
    picked: picked,
    onPick: setPicked
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 10
    }
  }, "Source pulse \xB7 24h"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 10
    }
  }, ["github", "huggingface", "youtube", "blogs", "papers", "hackernews"].map(k => {
    const S = window.DD_DATA.SOURCES[k];
    const h = window.DD_DATA.sourceHealth[k];
    // synthesize per-source pulse from clusters
    const series = Array.from({
      length: 24
    }, (_, i) => clusters.filter(c => c.sources.includes(k)).reduce((s, c) => s + c.pulse[i], 0) / 4);
    return /*#__PURE__*/React.createElement("div", {
      key: k,
      style: {
        display: "grid",
        gridTemplateColumns: "auto 1fr auto",
        gap: 10,
        alignItems: "center",
        padding: "8px 10px",
        background: "var(--bg-2)",
        border: "1px solid var(--line)",
        borderRadius: 4
      }
    }, /*#__PURE__*/React.createElement(SourceChip, {
      src: k
    }), /*#__PURE__*/React.createElement(Sparkline, {
      data: series,
      w: 120,
      h: 22,
      color: S.color,
      dotLast: true
    }), /*#__PURE__*/React.createElement("span", {
      className: "mono tnum",
      style: {
        fontSize: 11,
        color: "var(--text-hi)"
      }
    }, h.items_24h, /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 9.5,
        color: h.delta > 0 ? "var(--signal-up)" : "var(--signal-down)",
        marginLeft: 4
      }
    }, h.delta > 0 ? "+" : "", h.delta)));
  })), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      marginTop: 10,
      letterSpacing: "0.04em"
    }
  }, window.DD_DATA.sourceHealth.papers.error && /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal-down)"
    }
  }, "\u26A0 ", window.DD_DATA.sourceHealth.papers.error))))), /*#__PURE__*/React.createElement(PulseTable, {
    clusters: clusters,
    picked: picked,
    onPick: setPicked
  }), /*#__PURE__*/React.createElement(PulseDetail, {
    cluster: focused,
    onJump: onJump
  }));
};
window.PulseView = PulseView;