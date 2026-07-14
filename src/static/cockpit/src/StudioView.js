// StudioView — Creator Central: autonomous, multi-format content factory.
// Reads window.DD_DATA.studio = { stories, providers, skills, run }.
//
// Fixes applied (Shark Tank review):
//   1. Scripts rendered as markdown (not <pre> mono blocks)
//   2. B-roll shot list and on-screen cues rendered inside each card
//   3. Analytics match uses story_key (slug) not raw topic title string
//   4. Short card shows estimated spoken duration with red/amber/green indicator
//   5. [studio_job.py] Parallel generation — see separate fix

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Render a markdown string safely using the globally-loaded marked lib. */
const renderMd = text => {
  return safeMarkdown(text);
};

/**
 * Estimate spoken duration of a script.
 * Average spoken English: ~140 words/min for scripted YouTube content.
 * Returns { words, seconds, label, status: "short"|"ok"|"long" }
 */
const estimateDuration = (text, targetMinSec = 0, targetMaxSec = Infinity) => {
  if (!text) return null;
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const seconds = Math.round(words / 140 * 60);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  const label = m > 0 ? `${m}m ${s}s` : `${s}s`;
  let status = "ok";
  if (targetMaxSec !== Infinity && seconds > targetMaxSec) status = "long";else if (targetMinSec > 0 && seconds < targetMinSec) status = "short";
  return {
    words,
    seconds,
    label,
    status
  };
};
const DURATION_COLOR = {
  ok: "var(--signal-up)",
  short: "var(--signal)",
  long: "var(--signal-down)"
};
const DURATION_TARGETS = {
  shorts: {
    min: 25,
    max: 60,
    label: "25–60s target"
  },
  video: {
    min: 420,
    max: 780,
    label: "7–13m target"
  },
  podcast: {
    min: 240,
    max: 360,
    label: "4–6m target"
  },
  blog: {
    min: 0,
    max: Infinity,
    label: ""
  }
};

// ── Elapsed timer ─────────────────────────────────────────────────────────────
const RunTimer = ({
  startMs
}) => {
  const [elapsed, setElapsed] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startMs) / 1000)), 1000);
    return () => clearInterval(id);
  }, [startMs]);
  const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const s = String(elapsed % 60).padStart(2, "0");
  return /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: "var(--signal)",
      letterSpacing: "0.06em"
    }
  }, "\u23F1 ", m, ":", s);
};

// ── Format meta ───────────────────────────────────────────────────────────────
const STUDIO_FMT_META = {
  shorts: {
    icon: "📱",
    label: "YouTube Short"
  },
  video: {
    icon: "🎬",
    label: "Long-form Video"
  },
  podcast: {
    icon: "🎙️",
    label: "Podcast Script"
  },
  blog: {
    icon: "📝",
    label: "Blog Post"
  }
};
const StudioStatusDot = ({
  status
}) => {
  const color = status === "ready" ? "var(--signal-up)" : status === "generating" ? "var(--signal)" : status === "failed" ? "var(--signal-down)" : "var(--text-lo)";
  return /*#__PURE__*/React.createElement("span", {
    style: {
      width: 7,
      height: 7,
      borderRadius: 999,
      background: color,
      display: "inline-block",
      animation: status === "generating" ? "pulse 1.4s infinite" : "none"
    }
  });
};

// ── Format card ───────────────────────────────────────────────────────────────
const StudioFormatCard = ({
  storyKey,
  topic,
  fmt,
  data,
  onRegen,
  busy,
  broll = [],
  cues = []
}) => {
  const [open, setOpen] = React.useState(false);
  const [brollOpen, setBrollOpen] = React.useState(false);
  const [publishingPlatform, setPublishingPlatform] = React.useState(null);
  const [syncingNotion, setSyncingNotion] = React.useState(false);
  const [localNotionUrl, setLocalNotionUrl] = React.useState(null);
  const meta = STUDIO_FMT_META[fmt] || {
    icon: "•",
    label: fmt
  };
  const body = data?.body || "";
  const getPipelineItem = () => {
    if (!window.DD_DATA?.pipeline) return null;
    for (const lane of Object.values(window.DD_DATA.pipeline)) {
      const found = (lane || []).find(item => item.url === storyKey || item.title === topic || String(item.id) === String(storyKey));
      if (found) return found;
    }
    return null;
  };
  const pipeItem = getPipelineItem();
  let notionUrl = null;
  if (pipeItem?.production_assets) {
    try {
      const assets = JSON.parse(pipeItem.production_assets);
      notionUrl = assets.notion_page_url;
    } catch (e) {}
  }
  const handleNotionSync = async () => {
    setSyncingNotion(true);
    try {
      const res = await window.DDX.syncNotion(storyKey);
      if (res.success) {
        setLocalNotionUrl(res.notion_url);
        if (window.DDX?.reload) await window.DDX.reload();
      } else {
        alert("Notion sync failed: " + (res.error || "Unknown error"));
      }
    } catch (e) {
      alert("Notion sync failed: " + e.message);
    } finally {
      setSyncingNotion(false);
    }
  };
  const targets = DURATION_TARGETS[fmt] || {
    min: 0,
    max: Infinity,
    label: ""
  };
  const dur = estimateDuration(body, targets.min, targets.max);
  const getPlatformsForFormat = f => {
    if (f === "video" || f === "shorts") return ["youtube", "linkedin"];
    if (f === "blog") return ["substack", "linkedin"];
    return [];
  };
  const platforms = getPlatformsForFormat(fmt);
  const handleDownload = () => {
    let content = `# Script: ${meta.label}\n\n${body}\n\n`;
    if (broll.length > 0) content += `## Suggested B-Roll\n` + broll.map((x, i) => `${i + 1}. ${x}`).join("\n") + "\n\n";
    if (cues.length > 0) content += `## On-Screen Cues\n` + cues.map(x => `- ${x}`).join("\n") + "\n\n";
    window.downloadScript(`${storyKey}-${fmt}.md`, content);
  };
  const handleCopyYouTube = () => {
    // Format as YouTube description-ready block
    const yt = `${body}\n\n---\n📌 Subscribe for daily AI creator updates.\n`;
    navigator.clipboard?.writeText(yt);
  };
  const handlePublish = async platform => {
    setPublishingPlatform(platform);
    try {
      // FIX 3: pass storyKey (slug) as item_id so DB match works
      const res = await window.DDX.publish(storyKey, platform);
      if (res.ok) await window.DDX?.reload();
    } catch (e) {
      alert("Failed to publish: " + e.message);
    } finally {
      setPublishingPlatform(null);
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      padding: 0,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "10px 14px",
      borderBottom: "1px solid var(--line)",
      background: "var(--bg-2)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 16
    }
  }, meta.icon), /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 700,
      color: "var(--text-hi)",
      fontSize: 13
    }
  }, meta.label), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), dur && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      fontFamily: "var(--font-mono)",
      color: DURATION_COLOR[dur.status],
      background: `${DURATION_COLOR[dur.status]}18`,
      border: `1px solid ${DURATION_COLOR[dur.status]}44`,
      padding: "2px 6px",
      borderRadius: 999
    },
    title: `${dur.words} words · ${targets.label}`
  }, "\u23F1 ", dur.label, dur.status === "long" && " ⚠", dur.status === "short" && " ↑"), /*#__PURE__*/React.createElement(StudioStatusDot, {
    status: data?.status
  }), data?.provider && /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      fontSize: 10
    }
  }, data.provider)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "14px 16px",
      flex: 1,
      overflow: "hidden"
    }
  }, body ? /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "briefing-markdown studio-script",
    style: {
      maxHeight: open ? "none" : 220,
      overflow: "hidden",
      fontSize: 13,
      lineHeight: 1.65,
      color: "var(--text)",
      // Fade bottom when collapsed
      maskImage: open ? "none" : "linear-gradient(to bottom, black 70%, transparent 100%)",
      WebkitMaskImage: open ? "none" : "linear-gradient(to bottom, black 70%, transparent 100%)"
    },
    dangerouslySetInnerHTML: {
      __html: renderMd(body)
    }
  })) : /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-lo)",
      fontStyle: "italic",
      fontSize: 12,
      padding: "8px 0"
    }
  }, data?.status === "generating" ? /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
    className: "blink",
    style: {
      color: "var(--signal)"
    }
  }, "\u258D"), " ", "Generating with ", data?.provider || "AI", "\u2026") : data?.error ? /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--signal-down)"
    }
  }, "\u26A0 ", data.error) : "Not generated yet — run the factory.")), body && (broll.length > 0 || cues.length > 0) && /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: "1px dashed var(--line)",
      background: "var(--bg-0)"
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setBrollOpen(o => !o),
    style: {
      width: "100%",
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "8px 14px",
      background: "none",
      border: "none",
      cursor: "pointer",
      textAlign: "left"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12
    }
  }, "\uD83C\uDFAC"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: "var(--text-mid)",
      fontWeight: 600
    }
  }, "Shot List & Cues"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      marginLeft: 4
    }
  }, broll.length, " shots \xB7 ", cues.length, " cues"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: "var(--text-lo)"
    }
  }, brollOpen ? "▲" : "▼")), brollOpen && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "0 14px 12px",
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 12
    }
  }, broll.length > 0 && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginBottom: 6,
      color: "var(--text-mid)"
    }
  }, "B-ROLL SHOTS"), /*#__PURE__*/React.createElement("ol", {
    style: {
      margin: 0,
      padding: "0 0 0 16px",
      display: "flex",
      flexDirection: "column",
      gap: 4
    }
  }, broll.map((shot, i) => /*#__PURE__*/React.createElement("li", {
    key: i,
    style: {
      fontSize: 11,
      color: "var(--text)",
      lineHeight: 1.35
    }
  }, shot)))), cues.length > 0 && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginBottom: 6,
      color: "var(--text-mid)"
    }
  }, "ON-SCREEN CUES"), /*#__PURE__*/React.createElement("ul", {
    style: {
      margin: 0,
      padding: "0 0 0 16px",
      display: "flex",
      flexDirection: "column",
      gap: 4
    }
  }, cues.map((cue, i) => /*#__PURE__*/React.createElement("li", {
    key: i,
    style: {
      fontSize: 11,
      color: "var(--text)",
      lineHeight: 1.35
    }
  }, cue)))))), body && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 14px",
      background: "var(--bg-2)",
      borderTop: "1px solid var(--line)",
      display: "flex",
      alignItems: "center",
      justifyItems: "space-between",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13
    }
  }, "\uD83D\uDCD3"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: "var(--text-mid)",
      fontWeight: 600
    }
  }, "Notion Workspace")), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), notionUrl || localNotionUrl ? /*#__PURE__*/React.createElement("a", {
    href: notionUrl || localNotionUrl,
    target: "_blank",
    rel: "noopener noreferrer",
    className: "mono",
    style: {
      fontSize: 11,
      color: "var(--signal-up)",
      textDecoration: "none"
    }
  }, "\u2705 Synced \u2197") : /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 10,
      padding: "2px 8px",
      textTransform: "none"
    },
    disabled: syncingNotion,
    onClick: handleNotionSync
  }, syncingNotion ? "Syncing…" : "Sync Outline")), body && platforms.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 14px",
      background: "var(--bg-2)",
      borderTop: "1px solid var(--line)",
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      color: "var(--text-mid)"
    }
  }, "Publishing & ROI Analytics"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6
    }
  }, platforms.map(platform => {
    const pubs = window.DD_DATA?.publications || [];
    // FIX 3: match by item_id (slug) AND platform, not by raw title string
    const pub = pubs.find(p => (p.item_id === storyKey || p.slug === storyKey) && p.platform === platform);
    if (pub) {
      const isPub = pub.status === "publishing";
      return /*#__PURE__*/React.createElement("div", {
        key: platform,
        style: {
          padding: "8px 10px",
          background: "var(--bg-3)",
          borderRadius: 5,
          border: "1px solid var(--line)",
          fontSize: 11
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          textTransform: "capitalize",
          fontWeight: 600,
          color: "var(--text-hi)"
        }
      }, platform), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          color: isPub ? "var(--signal)" : "var(--signal-up)",
          fontSize: 10,
          display: "flex",
          alignItems: "center",
          gap: 4
        }
      }, /*#__PURE__*/React.createElement("span", {
        className: isPub ? "blink" : "",
        style: {
          width: 6,
          height: 6,
          borderRadius: 999,
          background: isPub ? "var(--signal)" : "var(--signal-up)"
        }
      }), isPub ? "Publishing…" : pub.status === "completed" ? "Completed" : "Live")), !isPub && /*#__PURE__*/React.createElement("div", {
        style: {
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 4,
          textAlign: "center"
        }
      }, [{
        label: "Views",
        value: (pub.views || 0).toLocaleString()
      }, {
        label: "Imp.",
        value: (pub.impressions || 0).toLocaleString()
      }, {
        label: "CTR",
        value: `${((pub.ctr || 0) * 100).toFixed(1)}%`
      }, {
        label: "Eng.",
        value: `${((pub.engagement_rate || 0) * 100).toFixed(1)}%`
      }].map(({
        label,
        value
      }) => /*#__PURE__*/React.createElement("div", {
        key: label
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          color: "var(--text-lo)",
          fontSize: 9
        }
      }, label), /*#__PURE__*/React.createElement("div", {
        className: "mono tnum",
        style: {
          fontWeight: 600,
          fontSize: 12
        }
      }, value)))), pub.published_url && /*#__PURE__*/React.createElement("a", {
        href: pub.published_url,
        target: "_blank",
        rel: "noopener",
        style: {
          display: "block",
          marginTop: 6,
          fontSize: 10,
          color: "var(--signal)",
          textDecoration: "none"
        }
      }, "\u2197 View on ", platform));
    }
    return /*#__PURE__*/React.createElement("button", {
      key: platform,
      className: "btn ghost",
      style: {
        justifyContent: "center",
        fontSize: 11,
        padding: "5px 8px",
        textTransform: "none",
        letterSpacing: 0
      },
      disabled: publishingPlatform === platform,
      onClick: () => handlePublish(platform)
    }, "\uD83D\uDE80 ", publishingPlatform === platform ? "Publishing…" : `Publish to ${platform}`);
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      padding: "9px 12px",
      borderTop: "1px solid var(--line)",
      flexWrap: "wrap"
    }
  }, body && body.length > 300 && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11
    },
    onClick: () => setOpen(o => !o)
  }, open ? "Collapse" : "Expand"), body && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11
    },
    onClick: () => navigator.clipboard?.writeText(body),
    title: "Copy raw script"
  }, "Copy"), body && (fmt === "video" || fmt === "shorts") && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11
    },
    onClick: handleCopyYouTube,
    title: "Copy formatted for YouTube description"
  }, "\uD83D\uDCCB YT Format"), body && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11
    },
    onClick: handleDownload
  }, "\u2193 Download"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11
    },
    disabled: busy,
    onClick: () => onRegen(storyKey, fmt)
  }, busy ? /*#__PURE__*/React.createElement("span", {
    className: "blink"
  }, "\u2026") : "↺ Regen")));
};

// ── Main StudioView ───────────────────────────────────────────────────────────
const StudioView = ({
  onJump
}) => {
  const [studioData, setStudioData] = React.useState(window.DD_DATA.studio || {});
  const providers = studioData.providers || [];
  const skills = studioData.skills || [];
  const stories = studioData.stories || [];
  const running = studioData.run?.running;
  const [busyKey, setBusyKey] = React.useState(null);
  const [kicking, setKicking] = React.useState(false);
  const [lastRunMs, setLastRunMs] = React.useState(null);
  const [focusStory, setFocusStory] = React.useState(null); // for future focus mode
  const [logs, setLogs] = React.useState([]);
  const [streamConnected, setStreamConnected] = React.useState(false);
  React.useEffect(() => {
    if (!kicking && !running) {
      setStreamConnected(false);
      return;
    }
    setStreamConnected(true);
    const es = window.DDX.studioStream(data => {
      if (data && data.text) {
        setLogs(prev => {
          if (prev.includes(data.text)) return prev;
          return [...prev, data.text];
        });
      }
    });
    return () => {
      es.close();
    };
  }, [kicking, running]);
  const available = providers.filter(p => p.available);

  // Poll /api/studio while factory is running
  React.useEffect(() => {
    if (!kicking && !running) return;
    const id = setInterval(async () => {
      try {
        const r = await fetch("/api/studio");
        const data = await r.json();
        setStudioData(data);
        if (!data.run?.running) {
          clearInterval(id);
          setKicking(false);
          if (window.DDX) {
            const full = await window.DDX.reload();
            if (full?.studio) setStudioData(full.studio);
          }
        }
      } catch (_) {}
    }, 2500);
    return () => clearInterval(id);
  }, [kicking, running]);
  const [selectedSlugs, setSelectedSlugs] = React.useState([]);
  const [showSteering, setShowSteering] = React.useState(false);
  const runFactory = async () => {
    if (kicking || running) return;
    setKicking(true);
    setLastRunMs(Date.now());
    try {
      await window.DDX?.studioRun(0, selectedSlugs.length > 0 ? selectedSlugs : null);
    } catch (_) {
      setKicking(false);
    }
  };
  const regen = async (storyKey, fmt) => {
    setBusyKey(storyKey + ":" + fmt);
    try {
      await window.DDX?.studioRegenerate(storyKey, fmt);
    } catch (_) {}
    setBusyKey(null);
    try {
      const r = await fetch("/api/studio");
      const data = await r.json();
      setStudioData(data);
    } catch (_) {
      window.DDX?.reload();
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 18
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
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, (kicking || running) && lastRunMs && /*#__PURE__*/React.createElement(RunTimer, {
      startMs: lastRunMs
    }), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: async () => {
        try {
          const res = await window.DDX.simulateAnalytics();
          if (res.ok) await window.DDX.reload();
        } catch (e) {
          alert("Simulate failed: " + e.message);
        }
      }
    }, "\u26A1 Simulate 48h"), /*#__PURE__*/React.createElement("button", {
      className: `btn ${showSteering ? "primary" : "ghost"}`,
      onClick: () => setShowSteering(!showSteering)
    }, "\uD83C\uDFAF Steering ", selectedSlugs.length > 0 ? `(${selectedSlugs.length})` : ""), /*#__PURE__*/React.createElement("span", {
      className: "chip",
      style: {
        color: available.length ? "var(--signal-up)" : "var(--signal-down)"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 5,
        height: 5,
        borderRadius: 999,
        background: "currentColor",
        animation: kicking || running ? "pulse 1s infinite" : "none"
      }
    }), available.length > 0 ? `${available.length} provider${available.length > 1 ? "s" : ""} online` : "No providers — check Settings"), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      disabled: kicking || running,
      onClick: runFactory,
      style: {
        background: "linear-gradient(90deg, var(--signal), var(--signal-hot))",
        border: "none",
        color: "#1a1100",
        fontWeight: 700
      }
    }, kicking || running ? "Factory running…" : "▶ Run factory"))
  }, "Creator Central \xB7 autonomous content factory"), showSteering && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "14px 22px",
      borderBottom: "1px solid var(--line)",
      background: "var(--bg-0)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 10,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("span", null, "SELECT TOPICS TO RUN IN NEXT FACTORY PASS (LEAVE EMPTY TO AUTO-PICK TOP 2)"), selectedSlugs.length > 0 && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 9,
      padding: "2px 6px",
      textTransform: "none"
    },
    onClick: () => setSelectedSlugs([])
  }, "Clear Selection")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 10,
      maxHeight: 200,
      overflowY: "auto",
      paddingRight: 6
    }
  }, (window.DD_DATA.clusters || []).map(c => {
    const isSelected = selectedSlugs.includes(c.slug);
    const isGenerated = stories.some(s => s.story_key === c.slug);
    return /*#__PURE__*/React.createElement("label", {
      key: c.slug,
      style: {
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 12px",
        background: isSelected ? "rgba(240,183,47,0.06)" : "var(--bg-2)",
        border: `1px solid ${isSelected ? "var(--signal)" : "var(--line)"}`,
        borderRadius: 6,
        cursor: "pointer",
        transition: "all 120ms"
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: isSelected,
      onChange: () => {
        setSelectedSlugs(prev => prev.includes(c.slug) ? prev.filter(s => s !== c.slug) : [...prev, c.slug]);
      },
      style: {
        cursor: "pointer"
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        color: isSelected ? "var(--text-hi)" : "var(--text)",
        fontWeight: 600,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap"
      }
    }, c.topic), /*#__PURE__*/React.createElement("div", {
      className: "mono",
      style: {
        fontSize: 9.5,
        color: "var(--text-lo)",
        marginTop: 2
      }
    }, "Score: ", c.creator_score, " \xB7 Signal: ", c.average_signal_score, " \xB7 ", isGenerated ? "✅ Generated" : "⏳ Ready")));
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "14px 22px",
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 18
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 8
    }
  }, "Model CLIs detected"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexWrap: "wrap",
      gap: 6
    }
  }, providers.length === 0 && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: "var(--text-lo)"
    }
  }, "No providers found.", " ", /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 11,
      padding: "2px 6px"
    },
    onClick: () => window.__setView && window.__setView("settings")
  }, "\u2192 Configure in Settings")), providers.map(p => /*#__PURE__*/React.createElement("span", {
    key: p.name,
    className: "chip",
    style: {
      opacity: p.available ? 1 : 0.38,
      borderColor: p.available ? "var(--line-hi)" : "var(--line)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 5,
      height: 5,
      borderRadius: 999,
      background: p.available ? "var(--signal-up)" : "var(--text-lo)"
    }
  }), p.name, p.available && p.model ? ` · ${p.model.split("/").pop()}` : "")))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 8
    }
  }, "Generator skills"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexWrap: "wrap",
      gap: 6
    }
  }, skills.map(s => /*#__PURE__*/React.createElement("span", {
    key: s.format,
    className: "chip"
  }, s.icon, " ", s.label))), /*#__PURE__*/React.createElement("p", {
    style: {
      color: "var(--text-mid)",
      fontSize: 12,
      marginTop: 10,
      marginBottom: 0
    }
  }, "Top stories auto-researched \u2192 every format, unattended. Runs hourly; trigger above anytime."))), (kicking || running || logs.length > 0) && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "0 22px 14px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "label",
    style: {
      marginBottom: 6,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("span", null, "Live Factory Output Logs"), logs.length > 0 && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    style: {
      fontSize: 9,
      padding: "2px 6px",
      textTransform: "none"
    },
    onClick: () => setLogs([])
  }, "Clear Console")), /*#__PURE__*/React.createElement("div", {
    style: {
      background: "#05070a",
      border: "1px solid var(--line-2)",
      borderRadius: 6,
      padding: "10px 14px",
      maxHeight: 150,
      overflowY: "auto",
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      color: "#a9b1d6",
      lineHeight: 1.5,
      display: "flex",
      flexDirection: "column",
      gap: 2
    }
  }, logs.map((log, idx) => {
    let color = "inherit";
    if (log.includes("completed") || log.includes("succeeded")) color = "var(--signal-up)";else if (log.includes("failed") || log.includes("EXCEPTION") || log.includes("warn")) color = "var(--signal-down)";else if (log.includes("started") || log.includes("STORY")) color = "var(--signal)";
    return /*#__PURE__*/React.createElement("div", {
      key: idx,
      style: {
        color
      }
    }, log);
  }), (kicking || running) && /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-lo)",
      fontStyle: "italic"
    },
    className: "blink"
  }, "\u23F3 Waiting for next stdout event from worker thread...")))), stories.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "panel crosshair",
    style: {
      padding: "56px 22px",
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "ch-bl"
  }), /*#__PURE__*/React.createElement("span", {
    className: "ch-br"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 32,
      marginBottom: 12
    }
  }, "\uD83C\uDFED"), /*#__PURE__*/React.createElement("h1", {
    className: "serif",
    style: {
      fontSize: 22,
      color: "var(--text-hi)",
      margin: "0 0 10px",
      fontWeight: 600
    }
  }, "No content generated yet"), /*#__PURE__*/React.createElement("p", {
    style: {
      color: "var(--text-mid)",
      maxWidth: 420,
      margin: "0 auto 20px",
      fontSize: 13,
      lineHeight: 1.5
    }
  }, "Creator Central picks the top stories and writes Shorts, long-form video, podcast, and blog drafts \u2014 fully unattended."), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    disabled: kicking,
    onClick: runFactory,
    style: {
      background: "linear-gradient(90deg,var(--signal),var(--signal-hot))",
      border: "none",
      color: "#1a1100",
      fontWeight: 700
    }
  }, kicking ? "Starting…" : "▶ Run factory now")) : stories.map(story => {
    const opp = window.DD_DATA.opportunities?.find(o => o.slug === story.story_key || o.topic === story.topic);
    const broll = opp?.broll_list || [];
    const cues = opp?.on_screen_cues || [];

    // Count how many formats are ready
    const fmts = story.formats || {};
    const readyCount = Object.values(fmts).filter(f => f?.body).length;
    const totalCount = 4;
    return /*#__PURE__*/React.createElement("div", {
      key: story.story_key,
      className: "panel",
      style: {
        padding: 0,
        overflow: "hidden"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "14px 20px",
        borderBottom: "1px solid var(--line)",
        display: "flex",
        alignItems: "center",
        gap: 12,
        background: "linear-gradient(90deg, rgba(240,183,47,0.04) 0%, transparent 100%)"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("h2", {
      className: "serif",
      style: {
        fontSize: 18,
        color: "var(--text-hi)",
        margin: 0,
        fontWeight: 600,
        lineHeight: 1.2
      }
    }, story.topic), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 10,
        marginTop: 6,
        alignItems: "center"
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 10,
        color: "var(--text-lo)"
      }
    }, story.story_key), /*#__PURE__*/React.createElement("span", {
      className: "chip",
      style: {
        color: readyCount === totalCount ? "var(--signal-up)" : "var(--signal)",
        borderColor: readyCount === totalCount ? "rgba(124,255,178,0.3)" : "rgba(240,183,47,0.3)",
        background: readyCount === totalCount ? "rgba(124,255,178,0.06)" : "rgba(240,183,47,0.06)"
      }
    }, readyCount, "/", totalCount, " formats ready"), broll.length > 0 && /*#__PURE__*/React.createElement("span", {
      className: "chip",
      style: {
        fontSize: 10
      }
    }, "\uD83C\uDFAC ", broll.length, " shots"))), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      style: {
        fontSize: 11
      },
      onClick: () => onJump && onJump("research", story.story_key)
    }, "Research \u2197")), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: 16,
        display: "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap: 14
      }
    }, ["shorts", "video", "podcast", "blog"].map(fmt => /*#__PURE__*/React.createElement(StudioFormatCard, {
      key: fmt,
      storyKey: story.story_key,
      topic: story.topic,
      fmt: fmt,
      data: fmts[fmt],
      onRegen: regen,
      busy: busyKey === story.story_key + ":" + fmt,
      broll: broll,
      cues: cues
    }))));
  }));
};
Object.assign(window, {
  StudioView
});