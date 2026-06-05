// PipelineView — kanban + week calendar

const LANE_STATUSES = ["idea", "researching", "script_ready", "recording", "published"];
const PipelineView = ({
  onJump
}) => {
  const {
    pipeline: initPipeline,
    calendar
  } = window.DD_DATA;
  const [pipeline, setPipeline] = useState(initPipeline);
  const [weekOffset, setWeekOffset] = useState(0);
  const [cal, setCal] = useState(calendar);
  const [fmtFilter, setFmtFilter] = useState("");
  const [groupByScore, setGroupByScore] = useState(false);
  const [dragId, setDragId] = useState(null); // item id being dragged
  const [dragOver, setDragOver] = useState(null); // lane key being hovered

  useEffect(() => {
    setPipeline(window.DD_DATA.pipeline);
  }, [window.DD_DATA.pipeline]);

  // Page the calendar by fetching the schedule for the chosen week.
  useEffect(() => {
    if (weekOffset === 0) {
      setCal(calendar);
      return;
    }
    const base = new Date();
    base.setDate(base.getDate() + weekOffset * 7);
    const days = Array.from({
      length: 7
    }, (_, i) => {
      const d = new Date(base);
      d.setDate(base.getDate() + i);
      return d;
    });
    const iso = d => d.toISOString().slice(0, 10);
    fetch(`/api/schedule?start=${iso(days[0])}&end=${iso(days[6])}`).then(r => r.json()).then(rows => {
      const byDay = {};
      (rows || []).forEach(r => {
        (byDay[r.day] = byDay[r.day] || []).push({
          ref: r.item_id,
          time: r.time || "—",
          kind: r.kind
        });
      });
      setCal(days.map(d => ({
        day: d.toLocaleDateString("en", {
          weekday: "short"
        }),
        date: d.getDate(),
        items: byDay[iso(d)] || []
      })));
    }).catch(() => {});
  }, [weekOffset]);

  // Drag handlers
  const onDragStart = id => setDragId(id);
  const onDragEnd = () => {
    setDragId(null);
    setDragOver(null);
  };
  const onDrop = async targetStatus => {
    if (!dragId || !targetStatus) return;
    // Find which lane the dragged item is currently in
    let srcLane = null,
      draggedItem = null;
    for (const [laneKey, items] of Object.entries(pipeline)) {
      const found = (items || []).find(i => String(i.id) === String(dragId));
      if (found) {
        srcLane = laneKey;
        draggedItem = found;
        break;
      }
    }
    if (!srcLane || srcLane === targetStatus) {
      setDragId(null);
      setDragOver(null);
      return;
    }

    // Optimistic update
    setPipeline(prev => {
      const next = {};
      for (const [k, v] of Object.entries(prev)) {
        next[k] = (v || []).filter(i => String(i.id) !== String(dragId));
      }
      next[targetStatus] = [...(next[targetStatus] || []), {
        ...draggedItem,
        status: targetStatus
      }];
      return next;
    });
    setDragId(null);
    setDragOver(null);

    // Persist
    try {
      await fetch(`/api/saved/${dragId}/status`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          status: targetStatus
        })
      });
      window.DDX && window.DDX.reload();
    } catch (e) {}
  };
  const addToLane = status => {
    const title = window.prompt(`New ${status} title:`);
    if (!title || !window.DDX) return;
    window.DDX.saveToPipeline({
      title,
      working_title: title,
      topic: title,
      category: title,
      pipeline_type: "creator",
      status
    }).then(() => window.DDX.reload());
  };
  const FORMATS = ["", "YouTube long-form", "YouTube short", "Comparison video", "Tutorial", "Explainer", "LinkedIn post", "LinkedIn carousel"];
  const cycleFmt = () => setFmtFilter(f => FORMATS[(FORMATS.indexOf(f) + 1) % FORMATS.length]);
  const laneItems = key => {
    let items = pipeline[key] || [];
    if (fmtFilter) items = items.filter(i => (i.format || "") === fmtFilter);
    if (groupByScore) items = items.slice().sort((a, b) => (b.creator_score || 0) - (a.creator_score || 0));
    return items;
  };
  const lanes = [{
    key: "idea",
    label: "Idea",
    tone: "var(--text-mid)"
  }, {
    key: "researching",
    label: "Researching",
    tone: "var(--src-papers)"
  }, {
    key: "script_ready",
    label: "Script ready",
    tone: "var(--signal)"
  }, {
    key: "recording",
    label: "Recording",
    tone: "var(--src-youtube)"
  }, {
    key: "published",
    label: "Published",
    tone: "var(--signal-up)"
  }];

  // Total in-flight count
  const inFlight = lanes.slice(0, 4).reduce((n, l) => n + laneItems(l.key).length, 0);
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
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: cycleFmt,
      style: {
        color: fmtFilter ? "var(--signal)" : undefined
      }
    }, "Filter \xB7 ", fmtFilter || "format"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setGroupByScore(v => !v),
      style: {
        color: groupByScore ? "var(--signal)" : undefined
      }
    }, groupByScore ? "Sorted · score" : "Group · creator"), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      onClick: () => addToLane("idea")
    }, /*#__PURE__*/React.createElement(I.Plus, {
      size: 12
    }), " New idea"))
  }, "Production pipeline \xB7 ", inFlight, " in flight"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: `repeat(${lanes.length}, 1fr)`,
      padding: "0",
      gap: 1,
      background: "var(--line)",
      borderTop: "1px solid var(--line)"
    }
  }, lanes.map(l => {
    const items = laneItems(l.key);
    const isOver = dragOver === l.key && dragId != null;
    return /*#__PURE__*/React.createElement("div", {
      key: l.key,
      onDragOver: e => {
        e.preventDefault();
        setDragOver(l.key);
      },
      onDragLeave: () => {
        if (dragOver === l.key) setDragOver(null);
      },
      onDrop: () => onDrop(l.key),
      style: {
        background: isOver ? "var(--bg-2)" : "var(--bg-1)",
        padding: "12px 12px 16px",
        minHeight: 480,
        outline: isOver ? `2px dashed ${l.tone}` : "2px dashed transparent",
        outlineOffset: -2,
        transition: "background 120ms, outline 120ms"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 12
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 6,
        height: 6,
        borderRadius: 999,
        background: l.tone
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "label",
      style: {
        color: "var(--text-hi)",
        fontWeight: 600
      }
    }, l.label), /*#__PURE__*/React.createElement("span", {
      className: "mono tnum",
      style: {
        marginLeft: "auto",
        fontSize: 10,
        color: "var(--text-lo)"
      }
    }, items.length)), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        gap: 8
      }
    }, items.map(it => /*#__PURE__*/React.createElement(PipeCard, {
      key: it.id,
      it: it,
      tone: l.tone,
      dragging: String(dragId) === String(it.id),
      onDragStart: () => onDragStart(it.id),
      onDragEnd: onDragEnd
    })), /*#__PURE__*/React.createElement("button", {
      onClick: () => addToLane(l.key),
      style: {
        padding: "8px 10px",
        border: "1px dashed var(--line-2)",
        background: "transparent",
        color: "var(--text-lo)",
        fontSize: 11.5,
        borderRadius: 4,
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        letterSpacing: "0.04em"
      }
    }, "+ ADD")));
  }))), /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "OPTIMIZER"
  }, "Publishing Time Optimizer \xB7 niche-calibrated engagement slots"), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "16px 20px",
      display: "grid",
      gridTemplateColumns: "1fr 1.5fr",
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      color: "var(--signal)"
    }
  }, "Niche Target Calibration"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 12.5,
      lineHeight: 1.5,
      color: "var(--text)",
      margin: "8px 0 0"
    }
  }, "Targeting ", /*#__PURE__*/React.createElement("strong", null, "Indie Builders & self-hosters"), ". Best publishing windows are optimized for high-intent tech focus: weekday mornings for written/professional networks (LinkedIn), and weekend mornings for deep-dive video production.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginBottom: 4
    }
  }, "Recommended Peak Engagement Slots"), /*#__PURE__*/React.createElement(OptimizedSlotRow, {
    platform: "YouTube",
    time: "Saturday, 10:00 AM",
    nicheScore: "98% Fit",
    reason: "Peak time for developers shipping weekend projects.",
    status: cal.some(d => d.day === "Sat" && d.items.some(it => it.kind === "publish" || it.kind === "record")) ? "FILLED" : "OPEN"
  }), /*#__PURE__*/React.createElement(OptimizedSlotRow, {
    platform: "LinkedIn",
    time: "Wednesday, 10:00 AM",
    nicheScore: "94% Fit",
    reason: "Maximum mid-week developer feed engagement.",
    status: cal.some(d => d.day === "Wed" && d.items.some(it => it.kind === "linkedin")) ? "FILLED" : "OPEN"
  }), /*#__PURE__*/React.createElement(OptimizedSlotRow, {
    platform: "Shorts/Tiktok",
    time: "Sunday, 10:00 AM",
    nicheScore: "89% Fit",
    reason: "Sunday morning casual tech browsing peak.",
    status: cal.some(d => d.day === "Sun" && d.items.some(it => it.kind === "publish" || it.kind === "record")) ? "FILLED" : "OPEN"
  })))), /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "02",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: async () => {
        if (window.confirm("Auto-schedule top brief opportunities for the upcoming week?")) {
          try {
            const res = await fetch("/api/schedule/auto", {
              method: "POST"
            });
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
      },
      style: {
        color: "var(--signal)"
      }
    }, /*#__PURE__*/React.createElement(I.Spark, {
      size: 11,
      stroke: "var(--signal)"
    }), " Auto-Schedule"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setWeekOffset(o => o - 1)
    }, "\u2039 Last week"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setWeekOffset(0),
      style: {
        color: weekOffset === 0 ? "var(--signal)" : undefined
      }
    }, "This week"), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => setWeekOffset(o => o + 1)
    }, "Next week \u203A"))
  }, "Publishing calendar \xB7 ", weekOffset === 0 ? "this week" : weekOffset < 0 ? `${-weekOffset}w ago` : `+${weekOffset}w`), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(7, 1fr)",
      gap: 1,
      background: "var(--line)",
      padding: "0 1px 1px"
    }
  }, cal.map((day, i) => /*#__PURE__*/React.createElement(DayCol, {
    key: day.day + i,
    day: day,
    isToday: weekOffset === 0 && i === 0
  })))), /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "03",
    actions: /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => window.open("/classic", "_blank")
    }, /*#__PURE__*/React.createElement(I.Trend, {
      size: 12
    }), " Full analytics")
  }, "Just published \xB7 last 7 days"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 1,
      background: "var(--line)",
      padding: "0 1px 1px"
    }
  }, (pipeline.published || []).length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      gridColumn: "1/-1",
      padding: "24px 20px",
      color: "var(--text-lo)",
      fontFamily: "var(--font-mono)",
      fontSize: 12
    }
  }, "Nothing published yet. Move a card to the Published lane to see analytics here.") : (pipeline.published || []).map(p => /*#__PURE__*/React.createElement(PublishedRow, {
    key: p.id,
    p: p
  })))));
};
const PipeCard = ({
  it,
  tone,
  dragging,
  onDragStart,
  onDragEnd
}) => /*#__PURE__*/React.createElement("div", {
  draggable: true,
  onDragStart: onDragStart,
  onDragEnd: onDragEnd,
  style: {
    padding: "10px 12px",
    background: "var(--bg-2)",
    border: `1px solid ${dragging ? tone : "var(--line)"}`,
    borderRadius: 4,
    cursor: "grab",
    opacity: dragging ? 0.45 : 1,
    transform: dragging ? "scale(0.97)" : "scale(1)",
    transition: "opacity 120ms, transform 120ms",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    userSelect: "none"
  }
}, /*#__PURE__*/React.createElement("div", {
  style: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 6
  }
}, /*#__PURE__*/React.createElement(FormatBadge, {
  format: it.format
}), /*#__PURE__*/React.createElement("span", {
  className: "mono tnum",
  style: {
    fontSize: 10.5,
    color: "var(--text-hi)",
    fontWeight: 600
  }
}, it.creator_score || "—")), /*#__PURE__*/React.createElement("div", {
  style: {
    color: "var(--text-hi)",
    fontSize: 12.5,
    fontWeight: 500,
    lineHeight: 1.3,
    textWrap: "pretty"
  }
}, it.working_title || it.topic || "Untitled"), /*#__PURE__*/React.createElement("div", {
  className: "mono",
  style: {
    fontSize: 10,
    color: "var(--text-lo)",
    letterSpacing: "0.04em"
  }
}, it.topic, " \xB7 effort ", it.effort || "medium"), it.research_pct !== undefined && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
  style: {
    height: 3,
    background: "var(--bg-0)",
    borderRadius: 2,
    overflow: "hidden"
  }
}, /*#__PURE__*/React.createElement("div", {
  style: {
    height: "100%",
    width: `${it.research_pct * 100}%`,
    background: tone
  }
})), /*#__PURE__*/React.createElement("span", {
  className: "mono",
  style: {
    fontSize: 9.5,
    color: "var(--text-lo)",
    marginTop: 4,
    display: "block"
  }
}, "agent \xB7 ", Math.round(it.research_pct * 100), "%")), it.views && /*#__PURE__*/React.createElement("div", {
  style: {
    display: "flex",
    gap: 8,
    fontFamily: "var(--font-mono)",
    fontSize: 10.5,
    color: "var(--text-mid)"
  }
}, /*#__PURE__*/React.createElement("span", null, "\u25B6 ", it.views), /*#__PURE__*/React.createElement("span", null, "\xB7 ", Math.round((it.retention || 0) * 100), "% retention")), !it.views && it.due && it.due !== "—" && /*#__PURE__*/React.createElement("div", {
  className: "mono",
  style: {
    fontSize: 10,
    color: tone,
    letterSpacing: "0.04em"
  }
}, "due \xB7 ", it.due));
const DayCol = ({
  day,
  isToday
}) => {
  const kindColors = {
    record: "var(--src-youtube)",
    edit: "var(--signal)",
    outline: "var(--text-mid)",
    linkedin: "var(--src-blogs)",
    newsletter: "var(--src-papers)",
    publish: "var(--signal-up)"
  };
  const kindLabels = {
    record: "RECORD",
    edit: "EDIT",
    outline: "OUTLINE",
    linkedin: "LINKEDIN",
    newsletter: "NEWSLETTER",
    publish: "PUBLISH"
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--bg-1)",
      minHeight: 240,
      padding: "10px 10px 12px",
      borderTop: isToday ? "2px solid var(--signal)" : "2px solid transparent"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      justifyContent: "space-between",
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: isToday ? "var(--signal)" : "var(--text-mid)",
      fontWeight: 600,
      fontSize: 11,
      letterSpacing: "0.06em"
    }
  }, day.day.toUpperCase()), /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      color: isToday ? "var(--text-hi)" : "var(--text-lo)",
      fontSize: 16,
      fontWeight: 600
    }
  }, day.date)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, day.items.map((it, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      padding: "6px 8px",
      background: "var(--bg-2)",
      borderLeft: `2px solid ${kindColors[it.kind]}`,
      borderRadius: 2
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 9.5,
      color: kindColors[it.kind],
      letterSpacing: "0.05em"
    }
  }, kindLabels[it.kind]), /*#__PURE__*/React.createElement("div", {
    className: "mono tnum",
    style: {
      fontSize: 10.5,
      color: "var(--text-hi)",
      marginTop: 2
    }
  }, it.time))), day.items.length === 0 && /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-vlo)",
      letterSpacing: "0.04em"
    }
  }, "\u2014 open \u2014")));
};
const PublishedRow = ({
  p
}) => {
  const [activeTest, setActiveTest] = useState(null);
  const [showABConfig, setShowABConfig] = useState(false);
  const [altTitle, setAltTitle] = useState("");
  const [submittingAB, setSubmittingAB] = useState(false);
  const [showShortsModal, setShowShortsModal] = useState(false);
  const [clips, setClips] = useState([]);
  const [loadingClips, setLoadingClips] = useState(false);
  const [publishingClipId, setPublishingClipId] = useState(null);

  // Fetch active A/B test
  const fetchActiveTest = () => {
    if (!window.DDX) return;
    window.DDX.getActiveABTest(p.id).then(res => {
      if (res.success) {
        setActiveTest(res.test);
      }
    }).catch(() => {});
  };
  useEffect(() => {
    fetchActiveTest();
  }, [p.id]);

  // Load clips when shorts modal is opened
  const loadClips = async () => {
    if (!window.DDX) return;
    setLoadingClips(true);
    try {
      const res = await window.DDX.repurposeVideo(p.id);
      if (res.success) {
        setClips(res.clips || []);
      }
    } catch (e) {
      alert("Failed to generate clips: " + e.message);
    } finally {
      setLoadingClips(false);
    }
  };
  useEffect(() => {
    if (showShortsModal) {
      loadClips();
    }
  }, [showShortsModal]);
  const handleStartABTest = async e => {
    e.preventDefault();
    if (!altTitle.trim() || !window.DDX) return;
    setSubmittingAB(true);
    try {
      const currentTitle = p.working_title || p.title || "Original Title";
      const res = await window.DDX.startABTest(p.id, currentTitle, altTitle);
      if (res.success) {
        setAltTitle("");
        setShowABConfig(false);
        fetchActiveTest();
        if (window.DDX?.reload) await window.DDX.reload();
      } else {
        alert("A/B Test failed to start: " + (res.error || "Unknown error"));
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      setSubmittingAB(false);
    }
  };
  const handlePublishClip = async clipId => {
    if (!window.DDX) return;
    setPublishingClipId(clipId);
    try {
      const res = await window.DDX.publishRepurposedClip(clipId);
      if (res.success) {
        loadClips();
      }
    } catch (e) {
      alert("Failed to publish clip: " + e.message);
    } finally {
      setPublishingClipId(null);
    }
  };
  const retention = typeof p.retention === "number" ? p.retention : 0.5;
  const views = p.views != null ? p.views : "—";
  const curve = Array.from({
    length: 24
  }, (_, i) => {
    const t = i / 23;
    return Math.max(0.15, retention * Math.pow(1 - t, 0.35) + Math.sin(i * 0.6) * 0.04);
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--bg-1)",
      padding: "16px",
      borderBottom: "1px solid var(--line)",
      display: "flex",
      flexDirection: "column",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr auto",
      gap: 18,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement(FormatBadge, {
    format: p.format
  }), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)"
    }
  }, p.published_at || "—")), /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontSize: 14,
      fontWeight: 600,
      lineHeight: 1.3,
      marginBottom: 6,
      textWrap: "balance"
    }
  }, p.working_title || p.topic || "Untitled"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 14,
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      color: "var(--text-mid)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "\u25B6 ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)"
    }
  }, views)), /*#__PURE__*/React.createElement("span", null, "retention ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: retention > 0.6 ? "var(--signal-up)" : "var(--signal)"
    }
  }, Math.round(retention * 100), "%")), /*#__PURE__*/React.createElement("span", null, "score ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)"
    }
  }, p.creator_score || "—")))), /*#__PURE__*/React.createElement(Sparkline, {
    data: curve,
    w: 160,
    h: 48,
    color: "var(--src-youtube)"
  })), activeTest && /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 6,
      padding: "12px",
      display: "flex",
      flexDirection: "column",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: "var(--text-hi)",
      fontWeight: 600,
      display: "flex",
      alignItems: "center",
      gap: 6
    }
  }, "\uD83D\uDCCA Title A/B Testing Engine", /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      fontSize: 9,
      background: "rgba(240,183,47,0.06)",
      borderColor: "var(--signal)",
      color: "var(--signal)"
    }
  }, "ACTIVE")), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10,
      color: activeTest.variant_b_ctr >= activeTest.variant_a_ctr ? "var(--signal-up)" : "var(--signal)"
    }
  }, "Leading: ", activeTest.variant_b_ctr >= activeTest.variant_a_ctr ? "Variant B" : "Variant A")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      marginBottom: 3
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-mid)",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
      maxWidth: "70%"
    }
  }, /*#__PURE__*/React.createElement("strong", null, "A:"), " ", activeTest.variant_a_title), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--text-hi)"
    }
  }, activeTest.variant_a_views, " views (", ((activeTest.variant_a_ctr || 0) * 100).toFixed(1), "% CTR)")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 4,
      background: "var(--bg-3)",
      borderRadius: 2,
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      background: "var(--text-lo)",
      width: `${Math.min(100, (activeTest.variant_a_ctr || 0) * 1000)}%`
    }
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      marginBottom: 3
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-hi)",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
      maxWidth: "70%"
    }
  }, /*#__PURE__*/React.createElement("strong", null, "B:"), " ", activeTest.variant_b_title), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--signal-up)"
    }
  }, activeTest.variant_b_views, " views (", ((activeTest.variant_b_ctr || 0) * 100).toFixed(1), "% CTR)")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 4,
      background: "var(--bg-3)",
      borderRadius: 2,
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      background: "var(--signal-up)",
      width: `${Math.min(100, (activeTest.variant_b_ctr || 0) * 1000)}%`
    }
  }))))), showABConfig && /*#__PURE__*/React.createElement("form", {
    onSubmit: handleStartABTest,
    style: {
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 6,
      padding: "12px",
      display: "flex",
      flexDirection: "column",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      fontWeight: 600,
      color: "var(--text-hi)"
    }
  }, "Configure A/B Title Test"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: {
      fontSize: 10,
      color: "var(--text-lo)"
    }
  }, "ALTERNATIVE TITLE (VARIANT B)"), /*#__PURE__*/React.createElement("input", {
    type: "text",
    placeholder: "e.g. You Won't Believe How This Code Runs!",
    value: altTitle,
    onChange: e => setAltTitle(e.target.value),
    required: true,
    style: {
      background: "var(--bg-3)",
      border: "1px solid var(--line-2)",
      borderRadius: 4,
      padding: "6px 10px",
      color: "var(--text-hi)",
      fontSize: 12,
      outline: "none"
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      justifyItems: "flex-end",
      justifyContent: "flex-end"
    }
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "btn ghost",
    style: {
      fontSize: 11,
      padding: "4px 10px"
    },
    onClick: () => setShowABConfig(false)
  }, "Cancel"), /*#__PURE__*/React.createElement("button", {
    type: "submit",
    className: "btn primary",
    style: {
      fontSize: 11,
      padding: "4px 12px"
    },
    disabled: submittingAB || !altTitle.trim()
  }, submittingAB ? "Starting…" : "Start Test"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11,
      padding: "4px 10px"
    },
    onClick: () => setShowShortsModal(true)
  }, "\uD83D\uDCF1 Slice 9:16 Shorts"), !activeTest && !showABConfig && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11,
      padding: "4px 10px"
    },
    onClick: () => setShowABConfig(true)
  }, "\uD83D\uDD04 Configure A/B Test")), showShortsModal && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "fixed",
      top: 0,
      left: 0,
      width: "100vw",
      height: "100vh",
      background: "rgba(5, 7, 10, 0.8)",
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      zIndex: 1000,
      backdropFilter: "blur(4px)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      width: "600px",
      maxWidth: "90%",
      background: "var(--bg-1)",
      border: "1px solid var(--line)",
      borderRadius: 8,
      padding: 0,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      maxHeight: "85vh"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      padding: "12px 18px",
      borderBottom: "1px solid var(--line)",
      background: "var(--bg-2)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      fontWeight: 700,
      color: "var(--text-hi)",
      display: "flex",
      alignItems: "center",
      gap: 6
    }
  }, "\uD83D\uDCF1 Multi-Format Auto-Repurposer (9:16 Shorts)"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      minWidth: 0,
      padding: "4px 8px"
    },
    onClick: () => setShowShortsModal(false)
  }, "\u2715")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "18px",
      overflowY: "auto",
      display: "flex",
      flexDirection: "column",
      gap: 14,
      flex: 1
    }
  }, loadingClips ? /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center",
      padding: "40px 0",
      color: "var(--text-lo)",
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "blink"
  }, "\u2702\uFE0F Slicing high-impact segments and hooks...")) : clips.length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center",
      padding: "40px 0",
      color: "var(--text-lo)",
      fontSize: 12
    }
  }, "No vertical shorts clips generated for this item.") : clips.map(clip => /*#__PURE__*/React.createElement("div", {
    key: clip.id,
    style: {
      display: "flex",
      gap: 14,
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 6,
      padding: "12px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: "80px",
      height: "130px",
      background: "linear-gradient(135deg, var(--bg-3) 0%, #111 100%)",
      borderRadius: 4,
      border: "1px solid var(--line-2)",
      flexShrink: 0,
      display: "flex",
      flexDirection: "column",
      justifyContent: "flex-end",
      padding: "6px",
      position: "relative",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      top: 4,
      left: 4,
      fontSize: 8,
      background: "rgba(0,0,0,0.6)",
      padding: "1px 4px",
      borderRadius: 2,
      color: "var(--text-hi)",
      fontFamily: "var(--font-mono)"
    }
  }, clip.start_time), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 8,
      color: "#fff",
      lineHeight: 1.2,
      textShadow: "0 1px 3px rgba(0,0,0,0.8)",
      overflow: "hidden",
      display: "-webkit-box",
      WebkitLineClamp: 3,
      WebkitBoxOrient: "vertical",
      textAlign: "center",
      background: "rgba(0,0,0,0.4)",
      borderRadius: 2,
      padding: "2px"
    }
  }, "\"", clip.hook_text, "\"")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "flex-start",
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12.5,
      fontWeight: 600,
      color: "var(--text-hi)",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
      maxWidth: "60%"
    }
  }, clip.title), /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      fontSize: 9.5,
      borderColor: "rgba(124,255,178,0.3)",
      background: "rgba(124,255,178,0.06)",
      color: "var(--signal-up)"
    }
  }, "\uD83D\uDD25 ", clip.virality_score, "% virality")), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      marginBottom: 6
    }
  }, "Duration: ", clip.start_time, " \u2013 ", clip.end_time), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 11,
      color: "var(--text-mid)",
      margin: 0,
      fontStyle: "italic",
      lineHeight: 1.4
    }
  }, "Hook: \"", clip.hook_text, "\"")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "flex-end",
      marginTop: 8
    }
  }, clip.status === "live" ? /*#__PURE__*/React.createElement("a", {
    href: clip.published_url,
    target: "_blank",
    rel: "noopener noreferrer",
    className: "btn ghost",
    style: {
      fontSize: 11,
      padding: "4px 10px",
      color: "var(--signal-up)"
    }
  }, "\u2705 Live \u2197") : /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    style: {
      fontSize: 11,
      padding: "4px 12px"
    },
    disabled: publishingClipId === clip.id,
    onClick: () => handlePublishClip(clip.id)
  }, publishingClipId === clip.id ? "Publishing…" : "🚀 Publish Short")))))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 18px",
      borderTop: "1px solid var(--line)",
      background: "var(--bg-2)",
      display: "flex",
      justifyContent: "flex-end"
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11,
      padding: "6px 14px"
    },
    onClick: () => setShowShortsModal(false)
  }, "Close")))));
};
const OptimizedSlotRow = ({
  platform,
  time,
  nicheScore,
  reason,
  status
}) => {
  const isOpen = status === "OPEN";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "100px 140px 1fr 80px",
      gap: 12,
      alignItems: "center",
      padding: "8px 12px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--text-hi)",
      fontWeight: 600,
      fontSize: 11.5
    }
  }, platform), /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      fontSize: 11.5,
      color: "var(--text)"
    }
  }, time), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: "var(--text-mid)"
    }
  }, reason, " ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: "var(--signal-up)",
      fontSize: 10.5
    }
  }, "(", nicheScore, ")")), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      textAlign: "center",
      fontSize: 10,
      padding: "2px 6px",
      borderRadius: 2,
      background: isOpen ? "rgba(124,255,178,0.1)" : "var(--bg-3)",
      border: `1px solid ${isOpen ? "rgba(124,255,178,0.3)" : "var(--line-2)"}`,
      color: isOpen ? "var(--signal-up)" : "var(--text-lo)"
    }
  }, status));
};
window.PipelineView = PipelineView;