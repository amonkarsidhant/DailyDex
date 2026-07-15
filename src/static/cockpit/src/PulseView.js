// TodayView - the action-first home for deciding what to make next.

const todayOpportunityFor = (opportunities, cluster) => {
  if (!cluster) return null;
  return (opportunities || []).find(o => o.cluster_slug === cluster.slug || o.slug === cluster.slug || o.creator_topic === cluster.topic || o.topic === cluster.topic) || null;
};
const todayRelativeTime = value => {
  if (!value) return "Not fetched yet";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Fetch time unavailable";
  const minutes = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 60000));
  if (minutes < 1) return "Updated just now";
  if (minutes < 60) return `Updated ${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Updated ${hours}h ago`;
  return `Updated ${Math.floor(hours / 24)}d ago`;
};
const TodaySourceStrip = () => {
  const {
    SOURCES = {},
    sourceHealth = {}
  } = window.DD_DATA;
  return /*#__PURE__*/React.createElement("div", {
    className: "today-source-strip",
    "aria-label": "Source freshness"
  }, Object.keys(SOURCES).map(key => {
    const source = SOURCES[key];
    const health = sourceHealth[key] || {};
    const hasIssue = !!health.error || health.status === "failed" || health.using_cache || health.last_fetch_min != null && !health.fresh;
    const age = health.last_fetch_min == null ? "not fetched" : `${health.last_fetch_min}m ago`;
    return /*#__PURE__*/React.createElement("div", {
      className: `today-source${hasIssue ? " today-source--issue" : ""}`,
      key: key,
      title: health.error || `${health.item_count || 0} items in latest fetch`
    }, /*#__PURE__*/React.createElement("span", {
      className: "today-source__dot",
      style: {
        background: hasIssue ? "var(--signal-down)" : health.last_fetch_min == null ? "var(--text-lo)" : source.color
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "today-source__abbr"
    }, source.abbr), /*#__PURE__*/React.createElement("span", {
      className: "today-source__age"
    }, age));
  }));
};
const TodayActionQueue = ({
  onJump
}) => {
  const {
    factory_queue = [],
    pipeline = {},
    sourceHealth = {},
    SOURCES = {},
    stats = {}
  } = window.DD_DATA;
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState("");
  const allScripts = pipeline.script_ready || [];
  const scripts = allScripts.slice(0, 3);
  const allSourceIssues = Object.entries(sourceHealth).filter(([, health]) => health.error || health.status === "failed" || health.using_cache || health.last_fetch_min != null && !health.fresh);
  const sourceIssues = allSourceIssues.slice(0, 3);
  const sourceValues = Object.values(sourceHealth);
  const hasKnownSources = sourceValues.some(health => health.last_fetch_min != null);
  const allSourcesCurrent = Object.keys(SOURCES).length > 0 && Object.keys(SOURCES).every(key => sourceHealth[key]?.fresh === true);
  const reviewFactoryItem = async (item, action) => {
    setBusyId(`${item.id}:${action}`);
    setMessage("");
    try {
      const response = await fetch(`/api/factory/${item.id}/${action}`, {
        method: "POST"
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `${action} failed`);
      setMessage(action === "approve" ? "Short approved for publishing." : "Short rejected.");
      if (window.DDX) await window.DDX.reload();
    } catch (error) {
      setMessage(error.message || "Could not update the review item.");
    } finally {
      setBusyId(null);
    }
  };
  const count = (stats.approval_count ?? factory_queue.length) + allScripts.length + allSourceIssues.length;
  return /*#__PURE__*/React.createElement("section", {
    className: "panel today-attention",
    "aria-labelledby": "attention-title"
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "02",
    actions: /*#__PURE__*/React.createElement("span", {
      className: "today-count"
    }, count, " open")
  }, /*#__PURE__*/React.createElement("span", {
    id: "attention-title"
  }, "Needs attention")), /*#__PURE__*/React.createElement("div", {
    className: "today-attention__body"
  }, factory_queue.map(item => /*#__PURE__*/React.createElement("div", {
    className: "today-action",
    key: `review-${item.id}`
  }, /*#__PURE__*/React.createElement("span", {
    className: "today-action__marker today-action__marker--review"
  }), /*#__PURE__*/React.createElement("div", {
    className: "today-action__copy"
  }, /*#__PURE__*/React.createElement("span", {
    className: "today-action__type"
  }, "Review ready"), /*#__PURE__*/React.createElement("strong", null, item.title || item.topic), /*#__PURE__*/React.createElement("span", null, item.virality_score ? `Virality score ${Math.round(item.virality_score)}` : "Rendered short awaiting a decision"), /*#__PURE__*/React.createElement("video", {
    controls: true,
    preload: "metadata",
    src: `/api/videos/${item.topic ? item.topic.replace(/[^a-zA-Z0-9]/g, "-").toLowerCase() : item.id}.mp4`,
    style: {
      width: "100%",
      maxHeight: 200,
      borderRadius: 6,
      marginTop: 6
    },
    onError: e => {
      e.target.style.display = "none";
    }
  })), /*#__PURE__*/React.createElement("div", {
    className: "today-action__controls"
  }, /*#__PURE__*/React.createElement("a", {
    className: "btn ghost",
    href: `/api/videos/${item.topic ? item.topic.replace(/[^a-zA-Z0-9]/g, "-").toLowerCase() : item.id}.mp4`,
    target: "_blank",
    rel: "noopener noreferrer",
    download: true,
    style: {
      textDecoration: "none"
    }
  }, "Download"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    disabled: busyId != null,
    onClick: () => reviewFactoryItem(item, "reject")
  }, "Reject"), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    disabled: busyId != null,
    onClick: () => reviewFactoryItem(item, "approve")
  }, busyId === `${item.id}:approve` ? "Approving..." : "Approve")))), scripts.map(item => /*#__PURE__*/React.createElement("button", {
    className: "today-action today-action--button",
    key: `script-${item.id}`,
    onClick: () => onJump("pipeline")
  }, /*#__PURE__*/React.createElement("span", {
    className: "today-action__marker today-action__marker--ready"
  }), /*#__PURE__*/React.createElement("span", {
    className: "today-action__copy"
  }, /*#__PURE__*/React.createElement("span", {
    className: "today-action__type"
  }, "Ready to record"), /*#__PURE__*/React.createElement("strong", null, item.working_title || item.topic || "Untitled script"), /*#__PURE__*/React.createElement("span", null, item.format || "Script ready")), /*#__PURE__*/React.createElement(I.ArrowR, {
    size: 13
  }))), sourceIssues.map(([key, health]) => {
    const source = window.DD_DATA.SOURCES[key];
    return /*#__PURE__*/React.createElement("div", {
      className: "today-action",
      key: `source-${key}`
    }, /*#__PURE__*/React.createElement("span", {
      className: "today-action__marker today-action__marker--issue"
    }), /*#__PURE__*/React.createElement("div", {
      className: "today-action__copy"
    }, /*#__PURE__*/React.createElement("span", {
      className: "today-action__type"
    }, health.error || health.using_cache ? "Source issue" : "Source stale"), /*#__PURE__*/React.createElement("strong", null, source?.label || key), /*#__PURE__*/React.createElement("span", null, health.error || (health.using_cache ? "Using cached data" : `Last fetched ${health.last_fetch_min}m ago`))), /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => window.DDX && window.DDX.refresh()
    }, "Retry"));
  }), count > factory_queue.length + scripts.length + sourceIssues.length && /*#__PURE__*/React.createElement("div", {
    className: "today-inline-message"
  }, "Additional review or source items are not shown in this compact list."), count === 0 && /*#__PURE__*/React.createElement("div", {
    className: "today-clear"
  }, /*#__PURE__*/React.createElement("span", {
    className: "today-clear__mark"
  }, "OK"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", null, "No queued actions"), /*#__PURE__*/React.createElement("span", null, allSourcesCurrent ? "Nothing needs review and all sources are current." : hasKnownSources ? "No review items are queued; some sources are still awaiting a current fetch." : "Source status will appear after the first fetch."))), message && /*#__PURE__*/React.createElement("div", {
    className: "today-inline-message",
    role: "status"
  }, message)));
};
const TodayChanges = ({
  clusters,
  selectedSlug,
  onSelect,
  onJump
}) => {
  const changed = [...clusters].sort((a, b) => Math.abs(b.momentum || 0) - Math.abs(a.momentum || 0) || b.source_count - a.source_count).slice(0, 4);
  return /*#__PURE__*/React.createElement("section", {
    className: "panel today-changes",
    "aria-labelledby": "changes-title"
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "03",
    actions: /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => onJump("clusters", selectedSlug)
    }, "Open Discover")
  }, /*#__PURE__*/React.createElement("span", {
    id: "changes-title"
  }, "What changed")), /*#__PURE__*/React.createElement("div", {
    className: "today-changes__list"
  }, changed.map(cluster => {
    const note = cluster.changelog?.[0]?.message || "No measured change since the previous snapshot.";
    return /*#__PURE__*/React.createElement("button", {
      key: cluster.slug,
      className: `today-change${selectedSlug === cluster.slug ? " today-change--active" : ""}`,
      onClick: () => onSelect(cluster.slug)
    }, /*#__PURE__*/React.createElement("span", {
      className: "today-change__topic"
    }, cluster.topic), /*#__PURE__*/React.createElement(Momentum, {
      delta: cluster.momentum
    }), /*#__PURE__*/React.createElement("span", {
      className: "today-change__note"
    }, note), /*#__PURE__*/React.createElement("span", {
      className: "today-change__sources"
    }, cluster.source_count, " sources"));
  })));
};
const TodayProduction = ({
  onJump
}) => {
  const {
    pipeline = {},
    calendar = [],
    agents = []
  } = window.DD_DATA;
  const lanes = [["researching", "Researching"], ["script_ready", "Script ready"], ["recording", "Recording"]];
  const nextDay = calendar.find(day => (day.items || []).length > 0);
  return /*#__PURE__*/React.createElement("section", {
    className: "panel today-production",
    "aria-labelledby": "production-title"
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "04",
    actions: /*#__PURE__*/React.createElement("button", {
      className: "btn ghost",
      onClick: () => onJump("pipeline")
    }, "Open Publish")
  }, /*#__PURE__*/React.createElement("span", {
    id: "production-title"
  }, "Production now")), /*#__PURE__*/React.createElement("div", {
    className: "today-production__body"
  }, /*#__PURE__*/React.createElement("div", {
    className: "today-production__lanes"
  }, lanes.map(([key, label]) => /*#__PURE__*/React.createElement("button", {
    key: key,
    onClick: () => onJump("pipeline"),
    className: "today-lane"
  }, /*#__PURE__*/React.createElement("span", null, label), /*#__PURE__*/React.createElement("strong", null, (pipeline[key] || []).length)))), /*#__PURE__*/React.createElement("div", {
    className: "today-production__next"
  }, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Next scheduled"), nextDay ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, nextDay.day, " ", nextDay.date), /*#__PURE__*/React.createElement("span", null, nextDay.items.length, " production event", nextDay.items.length === 1 ? "" : "s")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, "Calendar open"), /*#__PURE__*/React.createElement("span", null, "No production events scheduled in the next seven days."))), /*#__PURE__*/React.createElement("div", {
    className: "today-production__agents"
  }, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Agents"), agents.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, agents.length, " active"), /*#__PURE__*/React.createElement("span", null, agents.slice(0, 2).map(agent => agent.name).join(" + "))) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, "Idle"), /*#__PURE__*/React.createElement("span", null, "Dispatch work from the recommendation when you are ready.")))));
};
const TodayGoldenPath = ({
  onJump,
  clusters,
  pipeline,
  factory_queue
}) => {
  const hasClusters = clusters.length > 0;
  const hasPipeline = Object.values(pipeline || {}).flat().length > 0;
  const hasFactory = (factory_queue || []).length > 0;
  if (hasFactory) return null;
  const steps = [{
    done: hasClusters,
    label: "Sources fetched",
    action: "Refresh sources",
    onAction: () => window.DDX && window.DDX.refresh()
  }, {
    done: hasPipeline,
    label: "Story saved to pipeline",
    action: "Save a story",
    onAction: null
  }, {
    done: false,
    label: "Render your first short",
    action: "Click Render short",
    onAction: null
  }, {
    done: false,
    label: "Review and approve",
    action: "Check Needs attention",
    onAction: null
  }];
  const completed = steps.filter(s => s.done).length;
  if (completed >= 2) return null;
  return /*#__PURE__*/React.createElement("section", {
    className: "panel today-golden-path",
    "aria-labelledby": "golden-path-title"
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "01"
  }, /*#__PURE__*/React.createElement("span", {
    id: "golden-path-title"
  }, "Get started")), /*#__PURE__*/React.createElement("div", {
    className: "today-golden-path__body"
  }, steps.map((step, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: `today-golden-path__step${step.done ? " today-golden-path__step--done" : ""}`
  }, /*#__PURE__*/React.createElement("span", {
    className: "today-golden-path__check"
  }, step.done ? "\u2713" : i + 1), /*#__PURE__*/React.createElement("span", null, step.label), !step.done && step.onAction && /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: step.onAction
  }, step.action)))));
};
const TodayView = ({
  onJump,
  selectedClusterSlug,
  setSelectedClusterSlug
}) => {
  const {
    clusters = [],
    opportunities = [],
    titleSets = {},
    meta = {},
    pipeline = {},
    factory_queue = []
  } = window.DD_DATA;
  const fallbackSlug = clusters[0]?.slug || null;
  const selectedSlug = clusters.some(cluster => cluster.slug === selectedClusterSlug) ? selectedClusterSlug : fallbackSlug;
  const cluster = clusters.find(item => item.slug === selectedSlug) || clusters[0] || null;
  const opportunity = todayOpportunityFor(opportunities, cluster);
  const titles = cluster ? titleSets[cluster.slug] || opportunity?.suggested_titles || {} : {};
  const recommendationTitle = titles.practical || titles.curiosity || opportunity?.title || cluster?.topic || "";
  const isTopRecommendation = cluster.slug === clusters[0]?.slug;
  const hook = opportunity?.opening_hook || opportunity?.hook_line || cluster?.recommended_angle || "";
  const saved = Object.values(pipeline).flat().some(item => item.topic === cluster?.topic || item.working_title === recommendationTitle);
  const [saving, setSaving] = useState(false);
  const [researching, setResearching] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderMsg, setRenderMsg] = useState("");
  const selectCluster = slug => {
    if (setSelectedClusterSlug) setSelectedClusterSlug(slug);
  };
  const saveRecommendation = async () => {
    if (!cluster || !window.DDX || saved || saving) return;
    setSaving(true);
    try {
      await window.DDX.saveToPipeline({
        title: recommendationTitle,
        working_title: recommendationTitle,
        topic: cluster.topic,
        category: cluster.topic,
        format: opportunity?.best_format || cluster.best_content_format || "YouTube long-form",
        creator_score: cluster.creator_score,
        signal_score: cluster.average_signal_score,
        pipeline_type: "creator",
        status: "idea"
      });
      await window.DDX.reload();
    } finally {
      setSaving(false);
    }
  };
  const startResearch = async () => {
    if (!cluster || !window.DDX || researching) return;
    setResearching(true);
    try {
      await window.DDX.dispatch("topic_researcher", cluster.topic, cluster.slug);
      onJump("research", cluster.slug);
    } finally {
      setResearching(false);
    }
  };
  const renderShort = async () => {
    if (!cluster || !window.DDX || rendering) return;
    setRendering(true);
    setRenderMsg("Rendering vertical short with Remotion...");
    try {
      const res = await window.DDX.factoryRun(1);
      if (res.started) {
        setRenderMsg("Factory started. The short will appear in Needs attention when ready.");
        const poll = setInterval(async () => {
          try {
            const status = await window.DDX.factoryStatus();
            if (!status.running) {
              clearInterval(poll);
              setRendering(false);
              setRenderMsg(status.result?.queued?.length ? "Short rendered! Review it in Needs attention." : "Factory finished. Check the queue.");
              if (window.DDX) await window.DDX.reload();
            }
          } catch (_) {
            clearInterval(poll);
            setRendering(false);
          }
        }, 3000);
      } else {
        setRenderMsg("Factory is already running.");
        setRendering(false);
      }
    } catch (e) {
      setRenderMsg("Failed to start render: " + (e.message || "unknown error"));
      setRendering(false);
    }
  };
  if (!cluster) {
    return /*#__PURE__*/React.createElement("div", {
      className: "panel today-empty"
    }, /*#__PURE__*/React.createElement("span", {
      className: "micro"
    }, "Today"), /*#__PURE__*/React.createElement("h1", null, "No recommendation yet"), /*#__PURE__*/React.createElement("p", null, "Fetch sources to build the first cross-source story recommendation."), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      onClick: () => window.DDX && window.DDX.refresh()
    }, "Fetch sources"));
  }
  return /*#__PURE__*/React.createElement("div", {
    className: "today-view"
  }, /*#__PURE__*/React.createElement("section", {
    className: "panel crosshair today-hero",
    "aria-labelledby": "today-title"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ch-bl"
  }), /*#__PURE__*/React.createElement("span", {
    className: "ch-br"
  }), /*#__PURE__*/React.createElement("div", {
    className: "today-hero__topline"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "today-eyebrow"
  }, isTopRecommendation ? "Make this next" : "Selected story"), /*#__PURE__*/React.createElement("span", {
    className: "today-freshness"
  }, todayRelativeTime(meta.last_updated || meta.fetched_at))), /*#__PURE__*/React.createElement(TodaySourceStrip, null)), /*#__PURE__*/React.createElement("div", {
    className: "today-hero__grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "today-recommendation"
  }, /*#__PURE__*/React.createElement("div", {
    className: "today-recommendation__meta"
  }, /*#__PURE__*/React.createElement(FormatBadge, {
    format: opportunity?.best_format || cluster.best_content_format
  }), /*#__PURE__*/React.createElement("span", {
    className: "chip"
  }, "Creator score ", cluster.creator_score), /*#__PURE__*/React.createElement("span", {
    className: "chip"
  }, cluster.source_count, " source families"), /*#__PURE__*/React.createElement(Momentum, {
    delta: cluster.momentum,
    big: true
  })), /*#__PURE__*/React.createElement("h1", {
    id: "today-title"
  }, recommendationTitle), /*#__PURE__*/React.createElement("p", {
    className: "today-recommendation__why"
  }, cluster.why_this_is_a_story), hook && /*#__PURE__*/React.createElement("div", {
    className: "today-hook"
  }, /*#__PURE__*/React.createElement("span", null, "Opening angle"), /*#__PURE__*/React.createElement("p", null, hook)), /*#__PURE__*/React.createElement("div", {
    className: "today-recommendation__actions"
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn primary today-primary-action",
    onClick: () => onJump("brief", cluster.slug)
  }, "Open production brief ", /*#__PURE__*/React.createElement(I.ArrowR, {
    size: 13
  })), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    disabled: rendering,
    onClick: renderShort,
    style: rendering ? {
      borderColor: "var(--signal)",
      color: "var(--signal)"
    } : {}
  }, rendering ? "Rendering..." : "Render short"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    disabled: researching,
    onClick: startResearch
  }, researching ? "Dispatching..." : "Build research pack"), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    disabled: saved || saving,
    onClick: saveRecommendation
  }, saved ? "In pipeline" : saving ? "Saving..." : "Save idea")), renderMsg && /*#__PURE__*/React.createElement("div", {
    className: "today-inline-message",
    role: "status"
  }, renderMsg)), /*#__PURE__*/React.createElement("aside", {
    className: "today-evidence",
    "aria-label": "Recommendation evidence"
  }, /*#__PURE__*/React.createElement("div", {
    className: "today-evidence__header"
  }, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Evidence behind the pick"), /*#__PURE__*/React.createElement("button", {
    className: "text-button",
    onClick: () => onJump("clusters", cluster.slug)
  }, "Inspect cluster")), /*#__PURE__*/React.createElement("div", {
    className: "today-evidence__list"
  }, (cluster.related_items || []).slice(0, 4).map((item, index) => /*#__PURE__*/React.createElement("a", {
    key: `${item.url || item.title}-${index}`,
    href: item.url || undefined,
    target: item.url ? "_blank" : undefined,
    rel: "noopener noreferrer",
    className: "today-evidence__item"
  }, /*#__PURE__*/React.createElement(SourceChip, {
    src: item.source_type
  }), /*#__PURE__*/React.createElement("span", null, item.title), /*#__PURE__*/React.createElement("strong", null, item.signal_score)))), /*#__PURE__*/React.createElement("div", {
    className: "today-evidence__angle"
  }, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Recommended angle"), /*#__PURE__*/React.createElement("p", null, cluster.recommended_angle))))), /*#__PURE__*/React.createElement(TodayGoldenPath, {
    onJump: onJump,
    clusters: clusters,
    pipeline: pipeline,
    factory_queue: factory_queue
  }), /*#__PURE__*/React.createElement("div", {
    className: "today-work-grid"
  }, /*#__PURE__*/React.createElement(TodayActionQueue, {
    onJump: onJump
  }), /*#__PURE__*/React.createElement(EditorialBoard, null)), /*#__PURE__*/React.createElement(TodayChanges, {
    clusters: clusters,
    selectedSlug: selectedSlug,
    onSelect: selectCluster,
    onJump: onJump
  }), /*#__PURE__*/React.createElement(TodayProduction, {
    onJump: onJump
  }));
};
window.TodayView = TodayView;
window.PulseView = TodayView;