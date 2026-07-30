// TodayView - a live research desk that compiles only after creator selection.

const deskRelativeTime = value => {
  if (!value) return "Not fetched yet";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Fetch time unavailable";
  const minutes = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
};
const DeskSourceStrip = () => {
  const {
    SOURCES = {},
    sourceHealth = {}
  } = window.DD_DATA;
  return /*#__PURE__*/React.createElement("div", {
    className: "desk-source-strip",
    "aria-label": "Source freshness"
  }, Object.keys(SOURCES).map(key => {
    const source = SOURCES[key];
    const health = sourceHealth[key] || {};
    const issue = !!health.error || health.status === "failed" || health.using_cache;
    return /*#__PURE__*/React.createElement("span", {
      className: `desk-source${issue ? " desk-source--issue" : ""}`,
      key: key,
      title: health.error || `${health.item_count || 0} current items`
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        background: issue ? "var(--signal-down)" : source.color
      }
    }), source.abbr);
  }));
};
const SignalQueue = ({
  clusters,
  selectedSlug,
  onSelect
}) => /*#__PURE__*/React.createElement("aside", {
  className: "signal-queue",
  "aria-label": "Current story signals"
}, /*#__PURE__*/React.createElement("div", {
  className: "signal-queue__header"
}, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
  className: "micro"
}, "Current signals"), /*#__PURE__*/React.createElement("strong", null, "Pick what deserves a desk")), /*#__PURE__*/React.createElement("span", {
  className: "signal-queue__count mono"
}, clusters.length)), /*#__PURE__*/React.createElement("div", {
  className: "signal-queue__list"
}, clusters.map((cluster, index) => /*#__PURE__*/React.createElement("button", {
  key: cluster.slug,
  className: `signal-row${selectedSlug === cluster.slug ? " signal-row--selected" : ""}`,
  onClick: () => onSelect(cluster.slug),
  "aria-pressed": selectedSlug === cluster.slug
}, /*#__PURE__*/React.createElement("span", {
  className: "signal-row__rank mono"
}, String(index + 1).padStart(2, "0")), /*#__PURE__*/React.createElement("span", {
  className: "signal-row__body"
}, /*#__PURE__*/React.createElement("strong", null, cluster.topic), /*#__PURE__*/React.createElement("span", {
  className: "signal-row__sources"
}, (cluster.sources || []).slice(0, 4).map(source => /*#__PURE__*/React.createElement(SourceChip, {
  key: source,
  src: source
})))), /*#__PURE__*/React.createElement("span", {
  className: "signal-row__metrics"
}, /*#__PURE__*/React.createElement("b", null, Math.round(cluster.creator_score || cluster.average_signal_score || 0)), /*#__PURE__*/React.createElement(Momentum, {
  delta: cluster.momentum
}), /*#__PURE__*/React.createElement("small", null, cluster.source_count, " families"))))));
const EvidenceCitation = ({
  ids,
  evidence
}) => /*#__PURE__*/React.createElement("span", {
  className: "desk-citations"
}, (ids || []).map(id => {
  const source = evidence.find(record => record.id === id);
  return source?.url ? /*#__PURE__*/React.createElement("a", {
    key: id,
    href: source.url,
    target: "_blank",
    rel: "noopener noreferrer",
    title: source.title
  }, id) : /*#__PURE__*/React.createElement("span", {
    key: id
  }, id);
}));
const CompiledBrief = ({
  result,
  evidence,
  onSteer
}) => /*#__PURE__*/React.createElement("div", {
  className: "desk-brief"
}, /*#__PURE__*/React.createElement("header", {
  className: "desk-brief__header"
}, /*#__PURE__*/React.createElement("span", {
  className: "micro"
}, "Fresh editorial brief"), /*#__PURE__*/React.createElement("h1", null, result.story_title, " ", /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: result.story_title_evidence_ids,
  evidence: evidence
})), /*#__PURE__*/React.createElement("p", null, result.editorial_thesis, " ", /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: result.editorial_thesis_evidence_ids,
  evidence: evidence
}))), /*#__PURE__*/React.createElement("div", {
  className: "desk-brief__lead"
}, /*#__PURE__*/React.createElement("div", {
  className: "desk-hook-card"
}, /*#__PURE__*/React.createElement("span", null, "Opening line"), /*#__PURE__*/React.createElement("blockquote", null, result.hook, " ", /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: result.hook_evidence_ids,
  evidence: evidence
}))), /*#__PURE__*/React.createElement("div", {
  className: "desk-payoff-card"
}, /*#__PURE__*/React.createElement("span", null, "Audience payoff"), /*#__PURE__*/React.createElement("p", null, result.audience_payoff, " ", /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: result.audience_payoff_evidence_ids,
  evidence: evidence
})))), /*#__PURE__*/React.createElement("section", {
  className: "desk-section"
}, /*#__PURE__*/React.createElement("div", {
  className: "desk-section__heading"
}, /*#__PURE__*/React.createElement("span", {
  className: "micro"
}, "Three ways into the story"), /*#__PURE__*/React.createElement("small", null, "Choose one to brief the desk again")), /*#__PURE__*/React.createElement("div", {
  className: "desk-angle-grid"
}, (result.angles || []).map((angle, index) => /*#__PURE__*/React.createElement("button", {
  key: `${angle.name}-${index}`,
  className: "desk-angle",
  onClick: () => onSteer(`Develop the ${angle.name} angle. Keep it evidence-led and make the editorial take sharper.`)
}, /*#__PURE__*/React.createElement("span", {
  className: "mono"
}, "0", index + 1), /*#__PURE__*/React.createElement("strong", null, angle.name), /*#__PURE__*/React.createElement("p", null, angle.take), /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: angle.evidence_ids,
  evidence: evidence
}))))), /*#__PURE__*/React.createElement("div", {
  className: "desk-brief__split"
}, /*#__PURE__*/React.createElement("section", {
  className: "desk-section desk-format-card"
}, /*#__PURE__*/React.createElement("span", {
  className: "micro"
}, "Best treatment"), /*#__PURE__*/React.createElement("strong", null, result.recommended_format), /*#__PURE__*/React.createElement("p", null, result.format_reason, " ", /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: result.format_reason_evidence_ids,
  evidence: evidence
})), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", null, "Concrete demo"), /*#__PURE__*/React.createElement("p", null, result.demo_idea, " ", /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: result.demo_evidence_ids,
  evidence: evidence
})))), /*#__PURE__*/React.createElement("section", {
  className: "desk-section desk-titles-card"
}, /*#__PURE__*/React.createElement("span", {
  className: "micro"
}, "Working titles"), (result.titles || []).map((title, index) => /*#__PURE__*/React.createElement("button", {
  key: index,
  onClick: () => navigator.clipboard?.writeText(title)
}, /*#__PURE__*/React.createElement("span", {
  className: "mono"
}, index + 1), title)), /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: result.titles_evidence_ids,
  evidence: evidence
}))), /*#__PURE__*/React.createElement("section", {
  className: "desk-section desk-facts"
}, /*#__PURE__*/React.createElement("div", {
  className: "desk-section__heading"
}, /*#__PURE__*/React.createElement("span", {
  className: "micro"
}, "Claims the sources support"), /*#__PURE__*/React.createElement("small", null, "Every claim links back to evidence")), (result.key_facts || []).map((fact, index) => /*#__PURE__*/React.createElement("div", {
  key: index
}, /*#__PURE__*/React.createElement("span", {
  className: "desk-facts__mark"
}, "+"), /*#__PURE__*/React.createElement("p", null, fact.claim), /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: fact.evidence_ids,
  evidence: evidence
})))), !!result.caveats?.length && /*#__PURE__*/React.createElement("section", {
  className: "desk-caveats"
}, /*#__PURE__*/React.createElement("span", {
  className: "micro"
}, "What the desk would not claim yet ", /*#__PURE__*/React.createElement(EvidenceCitation, {
  ids: result.caveats_evidence_ids,
  evidence: evidence
})), result.caveats.map((caveat, index) => /*#__PURE__*/React.createElement("p", {
  key: index
}, caveat))));
const LiveResearchDesk = ({
  cluster
}) => {
  const [desk, setDesk] = useState({
    phase: "idle",
    message: "",
    evidence: [],
    draft: "",
    result: null,
    error: "",
    cacheHit: false,
    model: "",
    generatedAt: null,
    lockedUntil: null
  });
  const [instruction, setInstruction] = useState("");
  const requestRef = useRef(0);
  const abortRef = useRef(null);
  const compile = requestInstruction => {
    if (!cluster || !window.DDX) return;
    const requestId = ++requestRef.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setDesk({
      phase: "starting",
      message: "Opening the live research desk...",
      evidence: [],
      draft: "",
      result: null,
      error: "",
      cacheHit: false,
      model: "",
      generatedAt: null,
      lockedUntil: null
    });
    window.DDX.compile(cluster.slug, requestInstruction || "", event => {
      if (requestRef.current !== requestId) return;
      if (event.type === "status") {
        setDesk(current => ({
          ...current,
          phase: event.phase,
          message: event.message || current.message
        }));
      } else if (event.type === "cache") {
        setDesk(current => ({
          ...current,
          phase: "cached",
          cacheHit: true,
          model: event.model || "",
          generatedAt: event.generated_at,
          lockedUntil: event.locked_until,
          message: "Today's desk brief is already compiled. Replaying the cited work."
        }));
      } else if (event.type === "evidence") {
        setDesk(current => {
          const remaining = current.evidence.filter(record => record.id !== event.record.id);
          return {
            ...current,
            evidence: [...remaining, event.record].sort((a, b) => a.id.localeCompare(b.id))
          };
        });
      } else if (event.type === "draft_reset") {
        setDesk(current => ({
          ...current,
          draft: ""
        }));
      } else if (event.type === "token") {
        setDesk(current => ({
          ...current,
          phase: "compiling",
          draft: (current.draft + event.token).slice(-50000)
        }));
      } else if (event.type === "result") {
        setDesk(current => ({
          ...current,
          phase: "done",
          result: event.result,
          draft: "",
          error: "",
          cacheHit: !!event.cache_hit,
          model: event.model || "",
          generatedAt: event.generated_at,
          lockedUntil: event.locked_until,
          message: event.cache_hit ? "Replayed today's compiled desk brief." : "Fresh desk brief compiled from live evidence."
        }));
      } else if (event.type === "error") {
        setDesk(current => ({
          ...current,
          phase: "error",
          error: event.message || "The desk could not compile this story."
        }));
      }
    }, controller.signal).catch(error => {
      if (requestRef.current !== requestId || error.name === "AbortError") return;
      setDesk(current => ({
        ...current,
        phase: "error",
        error: error.message || "The research desk is unavailable."
      }));
    });
  };
  useEffect(() => {
    setInstruction("");
    compile("");
    return () => abortRef.current?.abort();
  }, [cluster?.slug]);
  const submit = event => {
    event.preventDefault();
    if (!instruction.trim()) return;
    compile(instruction.trim());
  };
  const isWorking = ["starting", "waiting", "evidence", "compiling", "repairing"].includes(desk.phase);
  const lockText = desk.lockedUntil ? `Daily brief locked until ${new Date(desk.lockedUntil * 1000).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  })}` : "One fresh default brief per signal every 24 hours";
  return /*#__PURE__*/React.createElement("main", {
    className: "research-desk",
    "aria-live": "polite"
  }, /*#__PURE__*/React.createElement("header", {
    className: "research-desk__topbar"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Live research desk"), /*#__PURE__*/React.createElement("strong", null, cluster.topic)), /*#__PURE__*/React.createElement("div", {
    className: "research-desk__meta"
  }, /*#__PURE__*/React.createElement("span", null, desk.cacheHit ? "24H REPLAY" : isWorking ? "COMPILING LIVE" : "SOURCE-BACKED"), /*#__PURE__*/React.createElement("small", null, lockText))), /*#__PURE__*/React.createElement("div", {
    className: "research-desk__signal"
  }, /*#__PURE__*/React.createElement("span", null, "Creator fit ", /*#__PURE__*/React.createElement("b", null, Math.round(cluster.creator_score || 0))), /*#__PURE__*/React.createElement("span", null, "Signal ", /*#__PURE__*/React.createElement("b", null, Math.round(cluster.average_signal_score || 0))), /*#__PURE__*/React.createElement("span", null, "Coverage ", /*#__PURE__*/React.createElement("b", null, cluster.source_count)), /*#__PURE__*/React.createElement(Momentum, {
    delta: cluster.momentum,
    big: true
  })), isWorking && /*#__PURE__*/React.createElement("section", {
    className: "desk-working"
  }, /*#__PURE__*/React.createElement("div", {
    className: "desk-working__pulse"
  }, /*#__PURE__*/React.createElement("i", null), /*#__PURE__*/React.createElement("i", null), /*#__PURE__*/React.createElement("i", null)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", null, desk.message), /*#__PURE__*/React.createElement("span", null, desk.evidence.length, " source", desk.evidence.length === 1 ? "" : "s", " read")), desk.phase === "compiling" && desk.draft && /*#__PURE__*/React.createElement("pre", null, desk.draft.slice(-900))), desk.error && /*#__PURE__*/React.createElement("div", {
    className: "desk-error"
  }, /*#__PURE__*/React.createElement("strong", null, "Compile stopped"), /*#__PURE__*/React.createElement("span", null, desk.error), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: () => compile(instruction)
  }, "Try again")), desk.result && /*#__PURE__*/React.createElement(CompiledBrief, {
    result: desk.result,
    evidence: desk.evidence,
    onSteer: value => {
      setInstruction(value);
      compile(value);
    }
  }), !!desk.evidence.length && /*#__PURE__*/React.createElement("section", {
    className: "desk-evidence-ledger"
  }, /*#__PURE__*/React.createElement("div", {
    className: "desk-section__heading"
  }, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Evidence ledger"), /*#__PURE__*/React.createElement("small", null, "Read live when this brief was compiled")), /*#__PURE__*/React.createElement("div", null, desk.evidence.map(record => /*#__PURE__*/React.createElement("a", {
    key: record.id,
    href: record.url || undefined,
    target: record.url ? "_blank" : undefined,
    rel: "noopener noreferrer"
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, record.id), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("strong", null, record.title), /*#__PURE__*/React.createElement("small", null, record.source_type, " \xB7 ", record.facts?.length || 0, " facts \xB7 ", record.quotes?.length || 0, " quotes")), /*#__PURE__*/React.createElement(I.ArrowR, {
    size: 12
  }))))), /*#__PURE__*/React.createElement("form", {
    className: "desk-prompt",
    onSubmit: submit
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Direct the desk"), /*#__PURE__*/React.createElement("small", null, "Each distinct request gets its own 24-hour cited brief.")), /*#__PURE__*/React.createElement("div", {
    className: "desk-prompt__input"
  }, /*#__PURE__*/React.createElement("input", {
    value: instruction,
    onChange: event => setInstruction(event.target.value),
    placeholder: "Focus on the cost, the technical trade-off, or the audience debate...",
    maxLength: 500
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    disabled: isWorking || !instruction.trim()
  }, isWorking ? "Working..." : "Compile")), /*#__PURE__*/React.createElement("div", {
    className: "desk-prompt__suggestions"
  }, ["Find the skeptical angle", "Make this practical for builders", "Focus on what the sources disagree about"].map(value => /*#__PURE__*/React.createElement("button", {
    type: "button",
    key: value,
    onClick: () => {
      setInstruction(value);
      compile(value);
    },
    disabled: isWorking
  }, value)))));
};
const TodayView = ({
  selectedClusterSlug,
  setSelectedClusterSlug
}) => {
  const {
    clusters = [],
    meta = {}
  } = window.DD_DATA;
  const [activeSlug, setActiveSlug] = useState(null);
  const cluster = clusters.find(item => item.slug === activeSlug) || null;
  useEffect(() => {
    if (activeSlug && !clusters.some(item => item.slug === activeSlug)) setActiveSlug(null);
  }, [activeSlug, clusters]);
  if (!clusters.length) {
    return /*#__PURE__*/React.createElement("div", {
      className: "panel today-empty"
    }, /*#__PURE__*/React.createElement("span", {
      className: "micro"
    }, "Research desk"), /*#__PURE__*/React.createElement("h1", null, "No current signals"), /*#__PURE__*/React.createElement("p", null, "Fetch sources, then select a signal for a fresh creator-specific compile."), /*#__PURE__*/React.createElement("button", {
      className: "btn primary",
      onClick: () => window.DDX?.refresh()
    }, "Fetch sources"));
  }
  return /*#__PURE__*/React.createElement("div", {
    className: "today-view live-desk-view"
  }, /*#__PURE__*/React.createElement("header", {
    className: "live-desk-header"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "DailyDex research room"), /*#__PURE__*/React.createElement("h1", null, "Choose a signal. Get a fresh desk brief."), /*#__PURE__*/React.createElement("p", null, "No generic angles. The desk reads the sources and writes for your audience when you select.")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(DeskSourceStrip, null), /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, "signals updated ", deskRelativeTime(meta.last_updated || meta.fetched_at)))), /*#__PURE__*/React.createElement("div", {
    className: "live-desk-layout"
  }, /*#__PURE__*/React.createElement(SignalQueue, {
    clusters: clusters,
    selectedSlug: activeSlug,
    onSelect: slug => {
      setActiveSlug(slug);
      setSelectedClusterSlug?.(slug);
    }
  }), cluster ? /*#__PURE__*/React.createElement(LiveResearchDesk, {
    key: cluster.slug,
    cluster: cluster
  }) : /*#__PURE__*/React.createElement("main", {
    className: "research-desk desk-unselected"
  }, /*#__PURE__*/React.createElement("span", {
    className: "micro"
  }, "Desk closed"), /*#__PURE__*/React.createElement("h2", null, "Select a current signal"), /*#__PURE__*/React.createElement("p", null, "Nothing compiles until you choose the story that deserves deeper research."))));
};
window.TodayView = TodayView;
window.PulseView = TodayView;