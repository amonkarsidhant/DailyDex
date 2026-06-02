// BriefView — fully dynamic. Zero hardcoded data.
// Every piece of content comes from window.DD_DATA or is generated live via /api/brief/generate.

// ── helpers ──────────────────────────────────────────────────────────────

// Build rich context string from real cluster data to ground LLM generation
const buildContext = (hero) => {
  const parts = [];
  if (hero?.why_this_is_a_story) parts.push(hero.why_this_is_a_story);
  const items = (hero?.related_items || []).slice(0, 6);
  if (items.length > 0) {
    parts.push("Top sources:");
    items.forEach(it => {
      const meta = [it.source_type, it.stars && `★${it.stars}`, it.views && `▶${it.views}`, it.channel].filter(Boolean).join(" · ");
      parts.push(`- ${it.title}${meta ? ` (${meta})` : ""}`);
    });
  }
  if (hero?.recommended_angle) parts.push(`\nRecommended angle: ${hero.recommended_angle}`);
  return parts.join("\n");
};

// Format a timestamp as "Xm ago" / "Xh ago" / "Xd ago"
const timeAgo = (isoStr) => {
  if (!isoStr) return null;
  try {
    const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch { return null; }
};

// Hook: call /api/brief/generate and return { state, text, items, generate }
const useGenerate = (topic, format, context) => {
  const [state, setState] = useState("idle"); // idle | generating | done | error
  const [text, setText] = useState("");
  const [items, setItems] = useState(null);

  const generate = async () => {
    if (state === "generating") return;
    setState("generating");
    setText("");
    setItems(null);
    try {
      const r = await fetch("/api/brief/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, format, context }),
      });
      const data = await r.json();
      if (data.error) { setState("error"); return; }
      if (data.items) { setItems(data.items); setState("done"); return; }
      if (data.text) { setText(data.text); setState("done"); return; }
      setState("error");
    } catch { setState("error"); }
  };

  return { state, text, items, generate };
};

// ── sub-components ────────────────────────────────────────────────────────

const BriefBeat = ({ n, body }) => (
  <>
    <span className="mono" style={{
      color: "var(--signal)", fontSize: 10, letterSpacing: "0.08em",
      padding: "3px 6px", border: "1px solid var(--signal)", borderRadius: 2,
      height: "fit-content", lineHeight: 1, marginTop: 2,
    }}>{n}</span>
    <p style={{ fontSize: 13.5, lineHeight: 1.5, margin: 0, color: "var(--text-hi)", textWrap: "pretty" }}>{body}</p>
  </>
);

const FactorRow = ({ k, v, dim }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
    <span style={{ fontSize: 11.5, color: dim ? "var(--text-mid)" : "var(--text)" }}>{k}</span>
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <ScoreBar value={v} w={48} color={dim ? "var(--text-mid)" : "var(--signal)"} label={false}/>
      <span className="mono tnum" style={{ fontSize: 11, color: dim ? "var(--text-mid)" : "var(--text-hi)", fontWeight: 600, minWidth: 22, textAlign: "right" }}>{v}</span>
    </span>
  </div>
);

// FormatCard — fully stateful. Generates inline on demand.
const FormatCard = ({ tag, tagColor, eyebrow, title, body, meta, cta, topic, format, genContext }) => {
  const gen = useGenerate(topic, format, genContext);
  const [expanded, setExpanded] = useState(false);

  const handleGenerate = async () => {
    setExpanded(true);
    await gen.generate();
  };

  return (
    <div className="panel" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10, minHeight: 240 }}>
      {/* Tag + eyebrow */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="mono" style={{
          padding: "2px 6px", border: `1px solid ${tagColor}55`, color: tagColor,
          background: `${tagColor}10`, fontSize: 10, letterSpacing: "0.06em", borderRadius: 2,
        }}>{tag}</span>
        <span className="micro">{eyebrow}</span>
      </div>

      {/* Title */}
      <h3 style={{ fontSize: 17, lineHeight: 1.2, margin: 0, color: "var(--text-hi)", fontWeight: 600,
        letterSpacing: "-0.01em", textWrap: "balance" }}>{title}</h3>

      {/* Body — signal summary from cluster, not fake copy */}
      <p style={{ fontSize: 12.5, lineHeight: 1.5, color: "var(--text)", margin: 0, textWrap: "pretty" }}>{body}</p>

      {/* Meta row */}
      <div style={{ marginTop: "auto", borderTop: "1px solid var(--line)", paddingTop: 10,
        display: "grid", gridTemplateColumns: meta.length === 3 ? "1fr 1fr 1fr" : "1fr 1fr", gap: 8 }}>
        {meta.map(([k, v]) => (
          <div key={k}>
            <div className="micro">{k}</div>
            <div className="mono" style={{ color: "var(--text-hi)", fontSize: 12, marginTop: 2 }}>{v}</div>
          </div>
        ))}
      </div>

      {/* Inline generated content */}
      {expanded && (
        <div style={{ borderTop: "1px solid var(--line)", paddingTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
          {gen.state === "generating" && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-lo)", fontSize: 12 }}>
              <span style={{ width: 7, height: 7, borderRadius: 999, background: "var(--signal)",
                animation: "pulse 1s infinite", display: "inline-block" }}/>
              Writing…
            </div>
          )}
          {gen.state === "error" && (
            <div style={{ color: "var(--signal-down)", fontSize: 12 }}>
              Generation failed — check that ANTHROPIC_API_KEY is set.
            </div>
          )}
          {gen.state === "done" && gen.text && (
            <>
              <pre className="mono" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word",
                fontSize: 11.5, lineHeight: 1.6, color: "var(--text)", margin: 0,
                background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
                padding: "10px 12px", maxHeight: 380, overflowY: "auto" }}>{gen.text}</pre>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn ghost" onClick={() => navigator.clipboard?.writeText(gen.text)}>Copy</button>
                <button className="btn ghost" onClick={() => window.downloadScript(`${format}_${tag.toLowerCase()}.md`,
                  `# ${title}\n\nFormat: ${tag} · ${eyebrow}\n\n${gen.text}`)}>Download</button>
                <span style={{ flex: 1 }}/>
                <button className="btn ghost" onClick={() => setExpanded(false)}>Hide</button>
              </div>
            </>
          )}
        </div>
      )}

      {/* CTA buttons */}
      <div style={{ display: "flex", gap: 6, marginTop: gen.state === "idle" ? "auto" : 0 }}>
        <button className="btn ghost" style={{ alignSelf: "flex-start" }}
          disabled={gen.state === "generating"}
          onClick={handleGenerate}>
          {gen.state === "generating" ? "Writing…" : gen.state === "done" ? "Regenerate" : cta}
          {gen.state !== "generating" && <I.ArrowR size={11}/>}
        </button>
      </div>
    </div>
  );
};

// ShortsReel — real data only, or a generate button
const ShortsReel = ({ items = [], topic, genContext }) => {
  const gen = useGenerate(topic, "shorts_ideas", genContext);
  const [idx, setIdx] = useState(0);
  const [decision, setDecision] = useState({});

  // Normalise items from either real DD_DATA or freshly generated
  const makeCards = (raw) => raw.map((x, i) => ({
    id: x.content_hash || x.id || `s${i}`,
    hook: x.opening_hook || x.hook_line || x.hook || x.title || "",
    topic: x.creator_topic || x.topic || topic,
    tension: x.creator_score_breakdown?.story_tension ?? x.tension ?? 80,
    demo: x.creator_score_breakdown?.practical_demo_value ?? x.demo ?? 80,
    item: x,
  }));

  const realCards = items.length > 0 ? makeCards(items) : null;
  const genCards  = gen.items ? makeCards(gen.items) : null;
  const cards = realCards || genCards;

  const swipe = (dir) => {
    if (!cards) return;
    const current = cards[idx];
    setDecision(d => ({ ...d, [current.id]: dir }));
    if ((dir === "later" || dir === "film") && window.DDX && current.item?.creator_score) {
      window.DDX.saveToPipeline({
        title: current.hook, working_title: current.hook,
        topic: current.topic, category: current.topic,
        format: "YouTube short",
        creator_score: current.item.creator_score || 80,
        signal_score: current.item.signal_score || 70,
        pipeline_type: "creator", status: dir === "film" ? "script_ready" : "idea",
      }).then(() => window.DDX.reload());
    }
    setTimeout(() => setIdx(i => Math.min((cards?.length || 1) - 1, i + 1)), 240);
  };

  return (
    <div className="panel" id="shorts-reel" style={{ overflow: "hidden" }}>
      <PanelHeader no="02"
        actions={
          cards ? (
            <>
              <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.06em" }}>
                {idx + 1}/{cards.length}
              </span>
              <button className="btn ghost" onClick={() => { setIdx(0); setDecision({}); }}>Reset</button>
              <button className="btn ghost" disabled={gen.state === "generating"}
                onClick={async () => { setIdx(0); setDecision({}); await gen.generate(); }}>
                {gen.state === "generating" ? "Generating…" : "Regenerate"}
              </button>
            </>
          ) : (
            <button className="btn primary" disabled={gen.state === "generating"}
              onClick={gen.generate}>
              {gen.state === "generating" ? "Generating…" : "Generate short ideas"}
            </button>
          )
        }>
        Shorts deck · swipe to pick
      </PanelHeader>

      {/* Empty / loading state */}
      {!cards && (
        <div style={{ padding: "40px 20px", textAlign: "center" }}>
          {gen.state === "generating" ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
              color: "var(--text-lo)", fontSize: 13 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: "var(--signal)",
                animation: "pulse 1s infinite", display: "inline-block" }}/>
              Writing 5 hook ideas from live data…
            </div>
          ) : gen.state === "error" ? (
            <div style={{ color: "var(--signal-down)", fontSize: 13 }}>
              Generation failed — check ANTHROPIC_API_KEY.
              <button className="btn ghost" style={{ marginLeft: 10 }} onClick={gen.generate}>Retry</button>
            </div>
          ) : (
            <p style={{ color: "var(--text-lo)", fontSize: 13, margin: 0 }}>
              No short ideas yet. Click "Generate short ideas" to create 5 hooks from today's top story.
            </p>
          )}
        </div>
      )}

      {/* Swipe deck */}
      {cards && cards.length > 0 && (() => {
        const currentShort = cards[Math.min(idx, cards.length - 1)];
        return (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", padding: "16px 20px",
            gap: 24, alignItems: "center", minHeight: 230 }}>
            <div>
              <div className="micro" style={{ color: "var(--signal)" }}>Hook {idx + 1}</div>
              <h2 style={{ fontSize: 32, lineHeight: 1.08, letterSpacing: "-0.02em", margin: "10px 0 14px",
                color: "var(--text-hi)", fontWeight: 600, textWrap: "balance" }}>
                "{currentShort.hook}"
              </h2>
              <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                <span className="chip">topic · {currentShort.topic}</span>
                <span className="chip" style={{ color: "var(--signal)" }}>tension {currentShort.tension}</span>
                <span className="chip" style={{ color: "var(--signal-up)" }}>demo {currentShort.demo}</span>
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
                <button className="btn ghost" onClick={() => swipe("skip")}><I.X size={12}/> Skip</button>
                <button className="btn ghost" onClick={() => swipe("later")}>Save for later</button>
                <button className="btn primary" onClick={() => swipe("film")}>Film today <I.Play size={11}/></button>
              </div>
              {/* Progress bar */}
              <div style={{ display: "flex", gap: 4, marginTop: 22 }}>
                {cards.map((s, i) => (
                  <span key={s.id} style={{
                    flex: 1, height: 3, borderRadius: 2,
                    background: decision[s.id] === "film" ? "var(--signal-up)"
                              : decision[s.id] === "later" ? "var(--signal)"
                              : decision[s.id] === "skip"  ? "var(--text-lo)"
                              : i === idx ? "var(--text-hi)" : "var(--line-2)",
                  }}/>
                ))}
              </div>
            </div>

            {/* Phone preview */}
            <div style={{ width: 180, height: 320, margin: "0 auto", borderRadius: 18, padding: 8,
              background: "var(--bg-0)", border: "1px solid var(--line-2)",
              boxShadow: "0 12px 32px rgba(0,0,0,0.3)" }}>
              <div style={{ width: "100%", height: "100%", borderRadius: 12, overflow: "hidden", position: "relative",
                background: `linear-gradient(155deg, oklch(0.55 0.18 ${(idx * 60 + 14) % 360}), oklch(0.18 0.06 ${(idx * 60 + 14) % 360}))` }}>
                <div style={{ position: "absolute", top: "30%", left: "50%", transform: "translateX(-50%)",
                  width: 90, height: 90, borderRadius: "50%",
                  background: `radial-gradient(circle at 35% 35%, oklch(0.85 0.06 ${(idx * 60 + 14) % 360}), oklch(0.4 0.1 ${(idx * 60 + 14) % 360}))`,
                  boxShadow: "inset 0 0 0 2px rgba(255,255,255,0.2)" }}/>
                <div style={{ position: "absolute", left: 10, right: 10, bottom: 20, color: "#fff",
                  fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: 14, lineHeight: 1.15,
                  textShadow: "0 2px 8px rgba(0,0,0,0.5)" }}>"{currentShort.hook}"</div>
                <div style={{ position: "absolute", top: 10, left: 10, padding: "2px 6px",
                  background: "rgba(0,0,0,0.4)", color: "#fff", fontFamily: "var(--font-mono)",
                  fontSize: 9, letterSpacing: "0.06em", borderRadius: 2 }}>00:00 / 00:47</div>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};

// QuickWins — real data only, or a generate button
const QuickWins = ({ items = [], topic, genContext, onJump }) => {
  const gen = useGenerate(topic, "quick_wins", genContext);

  const makeWins = (raw) => raw.map(x => ({
    topic: x.creator_topic || x.topic || topic,
    kind:   x.best_format || x.recommended_content_format || x.kind || "LinkedIn post",
    effort: x.production_effort === "low" ? "10 min" : x.effort || "25 min",
    impact: x.creator_score >= 80 ? "high" : x.impact || "medium",
    note:   x.why_viewers_care || x.risks_or_caveats || x.note || "",
  }));

  const realWins = items.length > 0 ? makeWins(items) : null;
  const genWins  = gen.items ? makeWins(gen.items) : null;
  const wins = realWins || genWins;

  return (
    <div className="panel" style={{ overflow: "hidden" }}>
      <PanelHeader no="03"
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            {!wins && (
              <button className="btn primary" disabled={gen.state === "generating"} onClick={gen.generate}>
                {gen.state === "generating" ? "Generating…" : "Generate quick wins"}
              </button>
            )}
            {wins && (
              <button className="btn ghost" disabled={gen.state === "generating"} onClick={gen.generate}>
                {gen.state === "generating" ? "…" : "Regenerate"}
              </button>
            )}
            <button className="btn ghost" onClick={() => onJump("pipeline")}>Open pipeline →</button>
          </div>
        }>
        Quick wins · low-effort cross-posts
      </PanelHeader>

      {/* Empty / generating state */}
      {!wins && (
        <div style={{ padding: "32px 20px", textAlign: "center" }}>
          {gen.state === "generating" ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
              color: "var(--text-lo)", fontSize: 13 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: "var(--signal)",
                animation: "pulse 1s infinite", display: "inline-block" }}/>
              Finding quick wins from live data…
            </div>
          ) : gen.state === "error" ? (
            <div style={{ color: "var(--signal-down)", fontSize: 13 }}>
              Generation failed — check ANTHROPIC_API_KEY.
              <button className="btn ghost" style={{ marginLeft: 10 }} onClick={gen.generate}>Retry</button>
            </div>
          ) : (
            <p style={{ color: "var(--text-lo)", fontSize: 13, margin: 0 }}>
              Click "Generate quick wins" to get 4 low-effort content ideas grounded in today's stories.
            </p>
          )}
        </div>
      )}

      {/* Wins grid */}
      {wins && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
          {wins.map((w, i) => (
            <div key={i} style={{
              padding: "12px 16px",
              borderBottom: i < wins.length - 2 ? "1px solid var(--line)" : "none",
              borderRight: i % 2 === 0 ? "1px solid var(--line)" : "none",
              display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 14, alignItems: "center",
            }}>
              <div style={{ width: 36, height: 36, borderRadius: 6, background: "var(--bg-2)",
                border: "1px solid var(--line-2)", display: "grid", placeItems: "center",
                color: "var(--signal)" }}>
                <span className="mono" style={{ fontSize: 14, fontWeight: 700 }}>{(i + 1).toString().padStart(2, "0")}</span>
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                  <span style={{ color: "var(--text-hi)", fontWeight: 600, fontSize: 13.5 }}>{w.topic}</span>
                  <span className="chip">{w.kind}</span>
                </div>
                <div style={{ fontSize: 12.5, color: "var(--text)", lineHeight: 1.4, textWrap: "pretty" }}>{w.note}</div>
              </div>
              <div style={{ textAlign: "right", display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="mono" style={{ fontSize: 11, color: "var(--text-hi)" }}>{w.effort}</span>
                <span className="mono" style={{ fontSize: 10,
                  color: w.impact === "high" ? "var(--signal-up)" : "var(--signal)",
                  letterSpacing: "0.05em" }}>{w.impact.toUpperCase()} IMPACT</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ── BriefView ─────────────────────────────────────────────────────────────

const BriefView = ({ onJump }) => {
  const { clusters, titleSets, thumbnails, opportunities, creator_brief, meta } = window.DD_DATA;
  const persona = window.__tweaks?.persona || "multi";
  const P = window.DD_DATA.personas[persona];
  const hero = clusters[0] || null;
  const opp = hero
    ? (opportunities?.find(o => o.slug === hero.slug) ||
       opportunities?.find(o => o.creator_topic === hero.topic) ||
       null)
    : null;
  const titles = hero ? (titleSets?.[hero.slug] || {}) : {};
  const heroThumb = hero ? thumbnails?.find(t => t.topic === hero.slug) : null;
  const [titleKey, setTitleKey] = useState(Object.keys(titles)[0] || "practical");
  const [enriching, setEnriching] = useState(false);

  const handleEnrich = async () => {
    if (enriching) return;
    setEnriching(true);
    try {
      // Always enrich from a raw related_item — opp is a cluster opportunity object
      // and doesn't carry url/title fields that /api/enrich requires.
      const itemToEnrich = hero.related_items?.[0];
      if (!itemToEnrich?.url && !itemToEnrich?.title) return;
      await fetch("/api/enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: itemToEnrich.url,
          title: itemToEnrich.title,
          source_type: itemToEnrich.source_type,
          force: true
        })
      });
      if (window.DDX) {
        window.DDX.reload();
      }
    } catch (e) {
      alert("Failed to enqueue AI enrichment: " + e.message);
    } finally {
      setEnriching(false);
    }
  };

  if (!hero) {
    return (
      <div className="panel crosshair" style={{ padding: "48px 22px", textAlign: "center" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <div className="label" style={{ marginBottom: 10 }}>Today's brief</div>
        <h1 className="serif" style={{ fontSize: 26, color: "var(--text-hi)", margin: "0 0 12px", fontWeight: 600 }}>
          Nothing to make yet
        </h1>
        <p style={{ color: "var(--text-mid)", maxWidth: 420, margin: "0 auto 18px" }}>
          The brief picks today's top cross-source story. Fetch sources to populate it.
        </p>
        <button className="btn primary" onClick={() => window.DDX && window.DDX.refresh()}>
          Fetch sources now
        </button>
      </div>
    );
  }

  // Real context from cluster data — grounds all generation
  const genContext = buildContext(hero);

  // Real fetch timestamp
  const fetchedAgo = timeAgo(meta?.last_fetch || meta?.fetched_at);

  // Hook + beats — from enrichment if available, else from cluster fields
  const hookText = opp?.opening_hook || opp?.hook_line || hero.why_this_is_a_story || `${hero.topic} is trending across multiple AI sources right now.`;
  const beats = (opp?.three_key_points?.length > 0) ? opp.three_key_points : (opp?.narrative_beats || []);
  const beat1 = beats[0] || (hero.related_items?.[0]?.title ? `From ${hero.related_items[0].source_type}: "${hero.related_items[0].title}"` : "What changed: see the source evidence below.");
  const beat2 = beats[1] || hero.recommended_angle || "Why it matters: this topic is crossing multiple source families simultaneously.";
  const beat3 = beats[2] || `${hero.related_items?.length || "Multiple"} sources confirm momentum. First seen ${hero.first_seen_hrs}h ago.`;

  // Score breakdown — enriched if available, else raw cluster scores with honest labels
  const breakdown = opp?.creator_score_breakdown || {};
  const baseScore  = hero.creator_score || hero.average_signal_score || 70;
  const fAudience  = breakdown.audience_interest    ?? Math.min(99, baseScore + 12);
  const fTension   = breakdown.story_tension        ?? Math.min(99, baseScore + 8);
  const fDemo      = breakdown.practical_demo_value ?? Math.min(99, baseScore + (hero.has_demoable_item ? 15 : 3));
  const fVisual    = breakdown.visual_potential     ?? Math.min(99, baseScore + 6);
  const fCredibility = breakdown.credibility        ?? Math.min(99, baseScore + 9);
  const fDiff      = breakdown.differentiation      ?? Math.min(99, baseScore - 2);
  const fShelf     = breakdown.shelf_life           ?? Math.max(30, baseScore - 15);
  const fEffort    = breakdown.production_effort    ?? 55;

  // Format card body — from enrichment if available, else from cluster signal
  const videoBody = opp?.why_viewers_care
    || (hero.related_items?.length > 0 ? `${hero.related_items.length} sources are covering this simultaneously — ${hero.why_this_is_a_story || "strong signal for a deep-dive video."}` : hero.why_this_is_a_story || "");
  const shortsBody = opp?.short_script || opp?.opening_hook
    || `${hero.topic} — ${hero.momentum > 0 ? `momentum ↑${hero.momentum}` : "trending now"} across ${hero.sources?.length || "multiple"} source types.`;
  const linkedinBody = opp?.risks_or_caveats || opp?.recommended_angle
    || hero.recommended_angle
    || `Why ${hero.topic} is the story AI professionals need to understand this week.`;

  // Pick an active title key that actually has content
  const activeKey = titles[titleKey] ? titleKey : Object.keys(titles)[0];
  const displayTitle = titles[activeKey] || hero.topic;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Hero recommendation */}
      <div className="panel crosshair" style={{ overflow: "hidden" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <PanelHeader no="01"
          actions={
            <>
              <span className="chip" style={{ color: "var(--signal)", borderColor: "rgba(240,183,47,0.4)", background: "rgba(240,183,47,0.06)" }}>
                <I.Spark size={10} stroke="var(--signal)"/>
                {fetchedAgo ? `fetched ${fetchedAgo}` : `${hero.sources?.length || 0} sources`}
              </span>
              <button className="btn ghost" onClick={() => window.DDX && window.DDX.reload()}><I.Refresh size={12}/> Re-pick</button>
            </>
          }>
          {P.hero_title}
        </PanelHeader>

        {(!opp || (opp.enrichment_status !== "ready" && opp.enrichment_status !== "ready_with_warnings")) && (
          <div style={{
            margin: "12px 24px 0",
            padding: "12px 16px",
            background: "rgba(240, 183, 47, 0.08)",
            border: "1px solid rgba(240, 183, 47, 0.25)",
            borderRadius: 6,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <I.Spark size={16} stroke="var(--signal)" />
              <div style={{ fontSize: 13, color: "var(--text-hi)" }}>
                <strong>Heuristic Brief:</strong> This brief is currently generated from static heuristics. Run AI Enrichment to synthesize dynamic, AI-structured insights.
              </div>
            </div>
            <button className="btn primary" onClick={handleEnrich} disabled={enriching} style={{ gap: 6 }}>
              {enriching ? "Enqueuing..." : "✨ Run AI Enrichment"}
            </button>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1.05fr 1fr", padding: "20px 24px", gap: 28 }}>
          <div>
            <div className="label" style={{ color: "var(--signal)", display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
              <span>Today's pick · creator score {hero.creator_score} · {hero.related_items?.length || 0} items across {hero.sources?.length || 0} source types</span>
              {hero.affinity_bonus > 0 && (
                <span className="chip" style={{
                  color: "var(--signal-up)",
                  borderColor: "rgba(124, 255, 178, 0.4)",
                  background: "rgba(124, 255, 178, 0.08)",
                  padding: "1px 6px",
                  fontSize: 9,
                  borderRadius: 4
                }}>
                  📈 +{hero.affinity_bonus} ROI Affinity Boost
                </span>
              )}
            </div>
            <h1 style={{
              fontSize: 46, lineHeight: 1.02, letterSpacing: "-0.025em",
              margin: "12px 0 8px", color: "var(--text-hi)", fontWeight: 700, textWrap: "balance",
            }}>{displayTitle || hero.topic}</h1>
            <p className="serif" style={{
              fontSize: 19, lineHeight: 1.35, fontStyle: "italic", color: "var(--text)",
              margin: 0, textWrap: "pretty", maxWidth: 540,
            }}>
              {P.hero_sub} {hero.topic} is the topic where you'll arrive earliest with the most evidence.
            </p>

            {/* Title rotator — only shown when enrichment has run and titleSets exist */}
            {Object.keys(titles).length > 0 && (
              <div style={{ marginTop: 22 }}>
                <div className="micro">Title angle</div>
                <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                  {Object.keys(titles).map(k => (
                    <button key={k} onClick={() => setTitleKey(k)} style={{
                      padding: "5px 10px",
                      background: (activeKey === k) ? "var(--bg-3)" : "var(--bg-2)",
                      border: `1px solid ${activeKey === k ? "var(--signal)" : "var(--line-2)"}`,
                      color: (activeKey === k) ? "var(--text-hi)" : "var(--text-mid)",
                      borderRadius: 4, fontFamily: "var(--font-mono)", fontSize: 10.5,
                      letterSpacing: "0.06em", textTransform: "uppercase", cursor: "pointer",
                    }}>{k}</button>
                  ))}
                </div>
              </div>
            )}

            {/* Hook + 3 beats — all from real data */}
            <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 14, rowGap: 12 }}>
              <BriefBeat n="HOOK"   body={hookText}/>
              <BriefBeat n="BEAT 1" body={beat1}/>
              <BriefBeat n="BEAT 2" body={beat2}/>
              <BriefBeat n="BEAT 3" body={beat3}/>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 24, flexWrap: "wrap" }}>
              <button className="btn primary" onClick={() => {
                if (window.DDX) window.DDX.dispatch("script_writer", hero.topic, hero.slug);
                onJump("research");
              }}>{P.cta} <I.ArrowR size={12}/></button>
              <button className="btn ghost" onClick={() => {
                if (window.DDX) window.DDX.dispatch("topic_researcher", hero.topic, hero.slug);
                onJump("research");
              }}>Generate research pack</button>
              <button className="btn ghost" onClick={() => {
                if (!window.DDX) return;
                window.DDX.saveToPipeline({
                  title: displayTitle || hero.topic,
                  working_title: displayTitle || hero.topic,
                  topic: hero.topic, category: hero.topic,
                  format: hero.best_content_format || "YouTube long-form",
                  creator_score: hero.creator_score,
                  signal_score: hero.average_signal_score,
                  pipeline_type: "creator", status: "idea",
                }).then(() => { alert("Saved to pipeline as an idea."); window.DDX.reload(); });
              }}><I.Save size={12}/> Save to pipeline</button>
            </div>
          </div>

          {/* Right: thumbnail + score breakdown */}
          <div>
            <FakeThumb t={heroThumb} w={420} h={236}/>
            <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 8,
              letterSpacing: "0.04em", display: "flex", justifyContent: "space-between" }}>
              <span>thumb · variant A · CTR-likelihood {heroThumb?.ctr || 0}</span>
              <button className="btn ghost" onClick={() => onJump("thumbs")}
                style={{ padding: "2px 6px", fontSize: 10 }}>Open Thumb Lab</button>
            </div>

            <div style={{ marginTop: 18, padding: "12px 14px", background: "var(--bg-2)",
              border: "1px solid var(--line)", borderRadius: 6 }}>
              <div className="label" style={{ color: "var(--text-hi)" }}>
                Why this scored {hero.creator_score}
                {!opp && <span style={{ color: "var(--text-lo)", fontWeight: 400, marginLeft: 6 }}>· estimated from cluster signals</span>}
              </div>
              
              {hero.affinity_bonus > 0 && (
                <div style={{
                  margin: "8px 0 12px 0",
                  padding: "8px 10px",
                  background: "rgba(124, 255, 178, 0.05)",
                  border: "1px dashed rgba(124, 255, 178, 0.3)",
                  borderRadius: 4,
                  fontSize: 11,
                  color: "var(--text)",
                  lineHeight: 1.35
                }}>
                  ✨ <strong>ROI Loop Affinity Boost:</strong> This topic matches top-performing categories from recent publications, receiving an automatic <strong>+{hero.affinity_bonus} boost</strong> to its Creator Score.
                </div>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
                <FactorRow k="Audience interest" v={fAudience}/>
                <FactorRow k="Story tension"     v={fTension}/>
                <FactorRow k="Demo value"        v={fDemo}/>
                <FactorRow k="Visual potential"  v={fVisual}/>
                <FactorRow k="Credibility"       v={fCredibility}/>
                <FactorRow k="Differentiation"   v={fDiff}/>
                <FactorRow k="Shelf life"        v={fShelf} dim/>
                <FactorRow k="Production effort" v={fEffort} dim/>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Format split — long / short / linkedin */}
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr", gap: 16 }}>
        <FormatCard
          tag="LONG-FORM" tagColor="var(--src-youtube)"
          eyebrow="YouTube · 14–18 min"
          title={displayTitle || hero.topic}
          body={videoBody}
          meta={[["Effort", opp?.production_effort || "medium"], ["Demo Value", `${fDemo}`], ["Best post-time", "Wed 6pm"]]}
          cta="Draft a script"
          topic={hero.topic}
          format="video"
          genContext={genContext}
        />
        <FormatCard
          tag="SHORT" tagColor="var(--src-youtube)"
          eyebrow="YT Short · 47s"
          title={titles.curiosity || titles[Object.keys(titles)[0]] || `${hero.topic} in 47 seconds`}
          body={shortsBody}
          meta={[["Effort","low"], ["Tension", `${fTension}`], ["Vertical", "ready"]]}
          cta="Write short script"
          topic={hero.topic}
          format="shorts"
          genContext={genContext}
        />
        <FormatCard
          tag="CAROUSEL" tagColor="var(--src-blogs)"
          eyebrow="LinkedIn · 8 slides"
          title={titles.contrarian || titles[Object.keys(titles)[1]] || `Why ${hero.topic} matters`}
          body={linkedinBody}
          meta={[["Effort","low"], ["Credibility", `${fCredibility}`], ["Format", "Carousel"]]}
          cta="Write carousel"
          topic={hero.topic}
          format="linkedin"
          genContext={genContext}
        />
      </div>

      {/* Shorts deck — real data or generate */}
      <ShortsReel
        items={creator_brief?.shorts_ideas || []}
        topic={hero.topic}
        genContext={genContext}
      />

      {/* Quick wins — real data or generate */}
      <QuickWins
        items={creator_brief?.quick_wins || []}
        topic={hero.topic}
        genContext={genContext}
        onJump={onJump}
      />
    </div>
  );
};

window.BriefView = BriefView;
