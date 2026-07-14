// ResearchView — research pack viewer with live agent synthesis
// React hooks come from AppShell's shared destructure (single source to avoid duplicate const in shared script scope).

const ResearchView = ({
  onJump,
  selectedClusterSlug,
  setSelectedClusterSlug
}) => {
  const {
    clusters,
    research_packs
  } = window.DD_DATA;
  const packs = research_packs || [];
  const [topic, setTopic] = useState(selectedClusterSlug || clusters[0] && clusters[0].slug || "");
  const cluster = clusters.find(c => c.slug === topic) || clusters[0];
  const streamRef = useRef(null);
  const pollRef = useRef(null);
  const stopWatchingRun = () => {
    if (streamRef.current) streamRef.current.close();
    if (pollRef.current) clearInterval(pollRef.current);
    streamRef.current = null;
    pollRef.current = null;
  };
  useEffect(() => {
    if (selectedClusterSlug && clusters.some(item => item.slug === selectedClusterSlug)) {
      setTopic(selectedClusterSlug);
    }
  }, [selectedClusterSlug]);
  const selectTopic = slug => {
    stopWatchingRun();
    setTopic(slug);
    setDispatched(false);
    if (setSelectedClusterSlug) setSelectedClusterSlug(slug);
  };
  const slugify = text => text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  const matchingPack = cluster ? packs.find(p => {
    const slug = slugify(cluster.topic);
    return new RegExp(`^\\d{4}-\\d{2}-\\d{2}-${slug}\\.md$`).test(p.filename);
  }) : null;
  const [packContent, setPackContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [dispatched, setDispatched] = useState(false);
  useEffect(() => () => stopWatchingRun(), []);
  useEffect(() => {
    if (!matchingPack) {
      setPackContent("");
      return;
    }
    setLoading(true);
    const controller = new AbortController();
    fetch(`/api/research-pack/${encodeURIComponent(matchingPack.filename)}`, {
      signal: controller.signal
    }).then(res => res.json()).then(data => {
      setPackContent(data.content || "");
      setLoading(false);
    }).catch(error => {
      if (error.name === "AbortError") return;
      setPackContent("");
      setLoading(false);
    });
    return () => controller.abort();
  }, [matchingPack?.filename, matchingPack?.revision]);
  const parsed = useMemo(() => {
    if (!packContent) return null;
    try {
      const markdown = packContent;
      const sections = {};
      const leadsMatch = markdown.match(/## Leads\s*([\s\S]*?)(?=\n##|$)/);
      sections.leads = leadsMatch ? leadsMatch[1].trim() : "";
      const titleMatch = markdown.match(/\*\*Strategic title:\*\*\s*(.*?)\n/);
      sections.strategicTitle = titleMatch ? titleMatch[1].trim() : "";
      const shiftMatch = markdown.match(/\*\*Shift:\*\*\s*(.*?)\n/);
      sections.shift = shiftMatch ? shiftMatch[1].trim() : "";
      const superpowerMatch = markdown.match(/\*\*Superpower:\*\*\s*(.*?)\n/);
      sections.superpower = superpowerMatch ? superpowerMatch[1].trim() : "";
      const inversionMatch = markdown.match(/\*\*Munger Inversion:\*\*\s*(.*?)\n/);
      sections.inversion = inversionMatch ? inversionMatch[1].trim() : "";
      const contrarianMatch = markdown.match(/- Contrarian:\s*(.*?)\n/);
      sections.hookContrarian = contrarianMatch ? contrarianMatch[1].trim() : "";
      const speedMatch = markdown.match(/- Speed-to-Value:\s*(.*?)\n/);
      sections.hookSpeed = speedMatch ? speedMatch[1].trim() : "";
      const beatsMatch = markdown.match(/## Narrative Beats:\s*([\s\S]*?)(?=\n##|$)/);
      if (beatsMatch) {
        sections.beats = beatsMatch[1].split("\n").map(line => line.replace(/^-\s*/, "").trim()).filter(Boolean);
      } else {
        sections.beats = [];
      }
      const thumbsMatch = markdown.match(/## Thumbnail Visuals:\s*([\s\S]*?)(?=\n##|$)/);
      if (thumbsMatch) {
        sections.thumbs = thumbsMatch[1].split("\n").map(line => line.replace(/^-\s*/, "").trim()).filter(Boolean);
      } else {
        sections.thumbs = [];
      }
      return sections;
    } catch (e) {
      return null;
    }
  }, [packContent]);
  if (!cluster) {
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
    }, "Research"), /*#__PURE__*/React.createElement("h1", {
      className: "serif",
      style: {
        fontSize: 26,
        color: "var(--text-hi)",
        margin: "0 0 12px",
        fontWeight: 600
      }
    }, "No research packs yet"), /*#__PURE__*/React.createElement("p", {
      style: {
        color: "var(--text-mid)",
        maxWidth: 420,
        margin: "0 auto 18px"
      }
    }, "Packs are built from clusters. Fetch sources to populate topics, then dispatch the researcher."), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      onClick: () => window.DDX && window.DDX.refresh()
    }, "Fetch sources now"));
  }
  const buildMD = (c, pData) => {
    if (!c) return "";
    const ev = (c.related_items || []).map((it, i) => `${i + 1}. **${it.title}** — ${it.source_type} · signal ${it.signal_score}${it.url && it.url !== "#" ? ` — ${it.url}` : ""}`).join("\n");
    return [`# Research Pack — ${c.topic}`, "", `Creator score: ${c.creator_score} · Signal: ${c.average_signal_score} · Momentum: ${c.momentum}% · Sources: ${(c.sources || []).join(", ")}`, "", pData ? `## Core Claim\n${pData.leads}\n` : "", pData ? `## Strategic Title\n${pData.strategicTitle}\n` : "", pData ? `## Shift\n${pData.shift}\n` : "", pData ? `## Superpower\n${pData.superpower}\n` : "", pData ? `## Munger Inversion\n${pData.inversion}\n` : "", `## Source evidence`, ev || "_none_", ""].join("\n");
  };
  const exportMD = () => {
    const blob = new Blob([buildMD(cluster, parsed)], {
      type: "text/markdown"
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${cluster ? cluster.slug : "research"}-pack.md`;
    a.click();
  };
  const openFile = () => {
    const blob = new Blob([buildMD(cluster, parsed)], {
      type: "text/markdown"
    });
    window.open(URL.createObjectURL(blob), "_blank");
  };
  const runResearcher = async () => {
    if (cluster && window.DDX) {
      setDispatched(true);
      try {
        const result = await window.DDX.dispatch("topic_researcher", cluster.topic, cluster.slug);
        if (!result?.run_id) throw new Error("No run identifier returned");
        stopWatchingRun();
        let completed = false;
        const finish = () => {
          if (completed) return;
          completed = true;
          stopWatchingRun();
          setDispatched(false);
          window.DDX.reload();
        };
        streamRef.current = window.DDX.agentStream(event => {
          const runId = event.run_id || event.run?.id;
          const finished = event.type === "done" || event.status === "done" || event.status === "error";
          if (runId !== result.run_id || !finished) return;
          finish();
        });
        pollRef.current = setInterval(async () => {
          try {
            const snapshot = await window.DDX.agents();
            if ((snapshot.recent_done || []).some(run => run.id === result.run_id)) finish();
          } catch (_) {}
        }, 1000);
      } catch (error) {
        alert(`Failed to dispatch Topic Researcher: ${error.message}`);
        setDispatched(false);
      }
    }
  };
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
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, matchingPack && /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: exportMD
    }, /*#__PURE__*/React.createElement(I.Doc, {
      size: 12
    }), " Export MD"), matchingPack && /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: openFile
    }, "Open file"), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      disabled: dispatched,
      onClick: runResearcher
    }, /*#__PURE__*/React.createElement(I.Spark, {
      size: 11
    }), " ", matchingPack ? "Re-research" : "Start Research"))
  }, "Research pack \xB7 ", matchingPack ? `data/research_packs/${matchingPack.filename}` : "No pack generated yet"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "240px 1fr",
      minHeight: 580
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      borderRight: "1px solid var(--line)",
      padding: "12px 0",
      overflowY: "auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      padding: "0 14px 8px"
    }
  }, "Today"), clusters.slice(0, 4).map(c => {
    const hasFile = packs.some(p => p.filename.includes(slugify(c.topic)));
    return /*#__PURE__*/React.createElement(PackRow, {
      key: c.slug,
      c: c,
      active: topic === c.slug,
      hasFile: hasFile,
      onClick: () => selectTopic(c.slug)
    });
  }), /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      padding: "12px 14px 8px"
    }
  }, "Yesterday"), clusters.slice(4).map(c => {
    const hasFile = packs.some(p => p.filename.includes(slugify(c.topic)));
    return /*#__PURE__*/React.createElement(PackRow, {
      key: c.slug,
      c: c,
      active: topic === c.slug,
      hasFile: hasFile,
      onClick: () => selectTopic(c.slug)
    });
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      overflowY: "auto",
      padding: "20px 28px"
    }
  }, loading ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      placeItems: "center",
      height: "100%",
      color: "var(--text-mid)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "blink"
  }, "Loading research pack...")) : !matchingPack ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: "100%",
      padding: "40px 20px",
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 48,
      height: 48,
      borderRadius: 24,
      background: "rgba(240,183,47,0.06)",
      border: "1px dashed var(--signal)",
      display: "grid",
      placeItems: "center",
      color: "var(--signal)",
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(I.Spark, {
    size: 20
  })), /*#__PURE__*/React.createElement("h3", {
    className: "serif",
    style: {
      fontSize: 22,
      color: "var(--text-hi)",
      margin: "0 0 8px",
      fontWeight: 600
    }
  }, "No Research Pack Created"), /*#__PURE__*/React.createElement("p", {
    style: {
      color: "var(--text-mid)",
      maxWidth: 360,
      fontSize: 13,
      lineHeight: 1.4,
      margin: "0 0 16px"
    }
  }, "There is no strategic brief or research documentation compiled for ", /*#__PURE__*/React.createElement("strong", null, "\"", cluster.topic, "\""), " yet."), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    disabled: dispatched,
    onClick: runResearcher
  }, dispatched ? "Researcher Dispatched..." : "Run Topic Researcher Agent")) : parsed ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      padding: "3px 8px",
      border: "1px solid var(--signal)",
      color: "var(--signal)",
      background: "rgba(240,183,47,0.06)",
      borderRadius: 3,
      fontSize: 10.5,
      letterSpacing: "0.06em"
    }
  }, "RESEARCH PACK \xB7 ACTIVE"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: "var(--text-lo)"
    }
  }, "Generated dynamically by Topic Researcher")), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 34,
      lineHeight: 1.1,
      letterSpacing: "-0.02em",
      margin: "12px 0 6px",
      color: "var(--text-hi)",
      fontWeight: 700,
      textWrap: "balance"
    }
  }, cluster.topic), parsed.strategicTitle && /*#__PURE__*/React.createElement("p", {
    className: "serif",
    style: {
      fontSize: 18,
      fontStyle: "italic",
      lineHeight: 1.4,
      color: "var(--text)",
      margin: 0,
      textWrap: "pretty",
      maxWidth: 720
    }
  }, "\"", parsed.strategicTitle, "\""), /*#__PURE__*/React.createElement(Divider, null), parsed.leads && /*#__PURE__*/React.createElement(Section, {
    title: "Core Claim / Leads",
    no: "01"
  }, /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 13.5,
      lineHeight: 1.55,
      color: "var(--text)",
      margin: 0,
      textWrap: "pretty",
      whiteSpace: "pre-wrap"
    }
  }, parsed.leads)), /*#__PURE__*/React.createElement(Section, {
    title: "Key evidence",
    no: "02"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, cluster.related_items.map((it, i) => /*#__PURE__*/React.createElement(EvidenceRow, {
    key: i,
    idx: i + 1,
    it: it
  })))), parsed.inversion && /*#__PURE__*/React.createElement(Section, {
    title: "Counterpoints & Munger Inversion",
    no: "03"
  }, /*#__PURE__*/React.createElement("ul", {
    style: {
      margin: 0,
      paddingLeft: 0,
      listStyle: "none",
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Counter, {
    pt: parsed.inversion,
    src: "Inversion Analysis"
  }))), (parsed.shift || parsed.superpower) && /*#__PURE__*/React.createElement(Section, {
    title: "Strategic Context",
    no: "04"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 12
    }
  }, parsed.shift && /*#__PURE__*/React.createElement(StatCard, {
    big: "THE SHIFT",
    small: parsed.shift
  }), parsed.superpower && /*#__PURE__*/React.createElement(StatCard, {
    big: "SUPERPOWER",
    small: parsed.superpower
  }))), (parsed.hookContrarian || parsed.hookSpeed) && /*#__PURE__*/React.createElement(Section, {
    title: "Creative Hook Angles",
    no: "05"
  }, /*#__PURE__*/React.createElement("ol", {
    style: {
      margin: 0,
      paddingLeft: 20,
      fontSize: 13.5,
      lineHeight: 1.7,
      color: "var(--text)"
    }
  }, parsed.hookContrarian && /*#__PURE__*/React.createElement("li", null, /*#__PURE__*/React.createElement("strong", null, "Contrarian Angle:"), " ", parsed.hookContrarian), parsed.hookSpeed && /*#__PURE__*/React.createElement("li", null, /*#__PURE__*/React.createElement("strong", null, "Speed Angle:"), " ", parsed.hookSpeed))), parsed.beats && parsed.beats.length > 0 && /*#__PURE__*/React.createElement(Section, {
    title: "Suggested Narrative Beats",
    no: "06"
  }, parsed.beats.map((beat, idx) => /*#__PURE__*/React.createElement(BeatRow, {
    key: idx,
    n: `Beat ${idx + 1}`,
    t: beat
  }))), parsed.thumbs && parsed.thumbs.length > 0 && /*#__PURE__*/React.createElement(Section, {
    title: "Thumbnail Visual Directions",
    no: "07"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
      gap: 10
    }
  }, parsed.thumbs.map((thumb, idx) => /*#__PURE__*/React.createElement("div", {
    key: idx,
    style: {
      padding: "10px 12px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 4,
      fontSize: 12,
      lineHeight: 1.4,
      color: "var(--text)"
    }
  }, /*#__PURE__*/React.createElement("strong", null, "Variant ", idx + 1, ":"), " ", thumb)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: () => onJump("brief", cluster.slug)
  }, /*#__PURE__*/React.createElement(I.Brief, {
    size: 12
  }), " Open in brief"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: () => {
      if (!cluster || !window.DDX) return;
      window.DDX.saveToPipeline({
        title: parsed.strategicTitle || cluster.topic,
        working_title: parsed.strategicTitle || cluster.topic,
        topic: cluster.topic,
        category: cluster.topic,
        format: cluster.best_content_format,
        creator_score: cluster.creator_score,
        signal_score: cluster.average_signal_score,
        pipeline_type: "creator",
        status: "researching"
      }).then(() => {
        alert("Sent to pipeline (researching).");
        window.DDX.reload();
      });
    }
  }, /*#__PURE__*/React.createElement(I.Save, {
    size: 12
  }), " Send to pipeline"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: () => onJump("thumbs", cluster.slug)
  }, /*#__PURE__*/React.createElement(I.Thumb, {
    size: 12
  }), " Generate thumbnails"))) : /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      placeItems: "center",
      height: "100%",
      color: "var(--text-mid)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "Failed to parse research pack content. Click Re-research to regenerate."))))));
};
const PackRow = ({
  c,
  active,
  hasFile,
  onClick
}) => {
  const S = window.DD_DATA.SOURCES;
  return /*#__PURE__*/React.createElement("button", {
    onClick: onClick,
    style: {
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      gap: 10,
      width: "100%",
      padding: "8px 14px",
      textAlign: "left",
      background: active ? "var(--bg-2)" : "transparent",
      borderLeft: `2px solid ${active ? "var(--signal)" : "transparent"}`,
      border: "none",
      cursor: "pointer",
      color: "var(--text)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: 999,
      background: S[c.sources[0]]?.color || "var(--signal)",
      marginTop: 6
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      lineHeight: 1.2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      color: active ? "var(--text-hi)" : "var(--text)",
      fontSize: 12.5,
      fontWeight: active ? 600 : 500,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, c.topic), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      display: "block",
      fontSize: 10,
      color: "var(--text-lo)",
      marginTop: 2,
      letterSpacing: "0.04em"
    }
  }, c.source_count, "\xD7 \xB7 score ", c.creator_score)), hasFile && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9,
      color: "var(--signal-up)",
      padding: "1px 4px",
      border: "1px solid rgba(124,255,178,0.2)",
      borderRadius: 2,
      alignSelf: "center",
      background: "rgba(124,255,178,0.04)"
    }
  }, "READY"));
};
const Divider = () => /*#__PURE__*/React.createElement("div", {
  style: {
    height: 1,
    background: "var(--line)",
    margin: "20px 0"
  }
});
const Section = ({
  title,
  no,
  children
}) => /*#__PURE__*/React.createElement("section", {
  style: {
    marginTop: 22
  }
}, /*#__PURE__*/React.createElement("div", {
  style: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 10
  }
}, /*#__PURE__*/React.createElement("span", {
  className: "mono",
  style: {
    color: "var(--text-lo)",
    fontSize: 10,
    letterSpacing: "0.08em"
  }
}, no), /*#__PURE__*/React.createElement("h3", {
  className: "label",
  style: {
    color: "var(--text-hi)",
    fontWeight: 600,
    margin: 0
  }
}, title), /*#__PURE__*/React.createElement("span", {
  style: {
    flex: 1,
    height: 1,
    background: "var(--line)"
  }
})), children);
const EvidenceRow = ({
  idx,
  it
}) => /*#__PURE__*/React.createElement("div", {
  style: {
    display: "grid",
    gridTemplateColumns: "26px auto 1fr auto auto",
    gap: 12,
    alignItems: "center",
    padding: "10px 12px",
    background: "var(--bg-2)",
    border: "1px solid var(--line)",
    borderRadius: 4
  }
}, /*#__PURE__*/React.createElement("span", {
  className: "mono",
  style: {
    color: "var(--text-lo)",
    fontSize: 10.5,
    letterSpacing: "0.05em"
  }
}, String(idx).padStart(2, "0")), /*#__PURE__*/React.createElement(SourceChip, {
  src: it.source_type
}), /*#__PURE__*/React.createElement("div", {
  style: {
    minWidth: 0
  }
}, /*#__PURE__*/React.createElement("div", {
  style: {
    color: "var(--text-hi)",
    fontSize: 13,
    fontWeight: 500
  }
}, it.title), /*#__PURE__*/React.createElement("div", {
  className: "mono",
  style: {
    fontSize: 10.5,
    color: "var(--text-lo)",
    marginTop: 2
  }
}, [it.stars && `★ ${it.stars}`, it.downloads && `↓ ${it.downloads}`, it.views && `▶ ${it.views}`, it.citations, it.source, it.channel].filter(Boolean).join(" · "), it.delta && /*#__PURE__*/React.createElement("span", {
  style: {
    color: "var(--signal-up)",
    marginLeft: 6
  }
}, it.delta))), /*#__PURE__*/React.createElement(ScoreBar, {
  value: it.signal_score,
  w: 56,
  label: false
}), /*#__PURE__*/React.createElement("span", {
  className: "mono tnum",
  style: {
    fontSize: 11,
    color: "var(--text-hi)",
    fontWeight: 600,
    minWidth: 24,
    textAlign: "right"
  }
}, it.signal_score));
const Counter = ({
  pt,
  src
}) => /*#__PURE__*/React.createElement("li", {
  style: {
    display: "grid",
    gridTemplateColumns: "auto 1fr auto",
    gap: 10,
    alignItems: "baseline"
  }
}, /*#__PURE__*/React.createElement("span", {
  style: {
    color: "var(--signal-down)"
  }
}, "\u2014"), /*#__PURE__*/React.createElement("span", {
  style: {
    fontSize: 13,
    color: "var(--text)",
    lineHeight: 1.5,
    textWrap: "pretty"
  }
}, pt), /*#__PURE__*/React.createElement("span", {
  className: "mono",
  style: {
    fontSize: 10,
    color: "var(--text-lo)",
    letterSpacing: "0.04em"
  }
}, src));
const StatCard = ({
  big,
  small
}) => /*#__PURE__*/React.createElement("div", {
  style: {
    padding: "12px 14px",
    background: "var(--bg-2)",
    border: "1px solid var(--line)",
    borderRadius: 4
  }
}, /*#__PURE__*/React.createElement("div", {
  className: "mono",
  style: {
    color: "var(--signal)",
    fontWeight: 700,
    fontSize: 12,
    letterSpacing: "0.08em"
  }
}, big), /*#__PURE__*/React.createElement("div", {
  style: {
    fontSize: 13,
    color: "var(--text-hi)",
    marginTop: 6,
    lineHeight: 1.45
  }
}, small));
const BeatRow = ({
  n,
  t
}) => /*#__PURE__*/React.createElement("div", {
  style: {
    display: "grid",
    gridTemplateColumns: "60px 1fr",
    gap: 12,
    alignItems: "baseline",
    padding: "5px 0",
    borderBottom: "1px dashed var(--line)"
  }
}, /*#__PURE__*/React.createElement("span", {
  className: "mono tnum",
  style: {
    color: "var(--signal)",
    fontSize: 11,
    letterSpacing: "0.04em"
  }
}, n), /*#__PURE__*/React.createElement("span", {
  style: {
    fontSize: 13,
    color: "var(--text)",
    lineHeight: 1.45
  }
}, t));
window.ResearchView = ResearchView;