// BriefView — "What to make today" across long-form + shorts + LinkedIn + newsletter
// Persona switches the emphasis.

const BriefView = ({ onJump }) => {
  const { clusters, titleSets, thumbnails, opportunities, creator_brief } = window.DD_DATA;
  const persona = window.__tweaks?.persona || "multi";
  const P = window.DD_DATA.personas[persona];
  const hero = clusters[0] || null; // Computer Use Agents
  const opp = hero ? (opportunities?.find(o => o.slug === hero.slug) || opportunities?.find(o => o.creator_topic === hero.topic) || hero) : null;
  const titles = hero ? (titleSets[hero.slug] || {}) : {};
  const heroThumb = hero ? thumbnails.find(t => t.topic === hero.slug) : null;

  const [titleKey, setTitleKey] = useState("practical");

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

  const hookText = opp?.opening_hook || opp?.hook_line || "No hook generated yet.";
  const beats = opp?.three_key_points || [];
  const beat1 = beats[0] || "Explore the setup and evidence.";
  const beat2 = beats[1] || "Evaluate what works and what breaks.";
  const beat3 = beats[2] || "Formulate actionable takeaways.";

  const breakdown = opp?.creator_score_breakdown || {};
  const fAudience = breakdown.audience_interest ?? 92;
  const fTension = breakdown.story_tension ?? 88;
  const fDemo = breakdown.practical_demo_value ?? 94;
  const fVisual = breakdown.visual_potential ?? 86;
  const fCredibility = breakdown.credibility ?? 89;
  const fDiff = breakdown.differentiation ?? 78;
  const fShelf = breakdown.shelf_life ?? 62;
  const fEffort = breakdown.production_effort ?? 55;

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
                AI · drafted 4m ago
              </span>
              <button className="btn ghost" onClick={() => window.DDX && window.DDX.reload()}><I.Refresh size={12}/> Re-pick</button>
            </>
          }>
          {P.hero_title}
        </PanelHeader>

        <div style={{ display: "grid", gridTemplateColumns: "1.05fr 1fr", padding: "20px 24px", gap: 28 }}>
          <div>
            <div className="label" style={{ color: "var(--signal)" }}>Today's pick · creator score {hero.creator_score}</div>
            <h1 style={{
              fontSize: 46, lineHeight: 1.02, letterSpacing: "-0.025em",
              margin: "12px 0 8px", color: "var(--text-hi)", fontWeight: 700,
              textWrap: "balance",
            }}>{titles[titleKey]}</h1>
            <p className="serif" style={{
              fontSize: 19, lineHeight: 1.35, fontStyle: "italic", color: "var(--text)",
              margin: 0, textWrap: "pretty", maxWidth: 540,
            }}>
              {P.hero_sub} {hero.topic} is the topic where you'll arrive earliest with the most evidence.
            </p>

            {/* Title rotator */}
            <div style={{ marginTop: 22 }}>
              <div className="micro">Title angle</div>
              <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                {Object.keys(titles).map(k => (
                  <button key={k}
                    onClick={() => setTitleKey(k)}
                    style={{
                      padding: "5px 10px",
                      background: titleKey === k ? "var(--bg-3)" : "var(--bg-2)",
                      border: `1px solid ${titleKey === k ? "var(--signal)" : "var(--line-2)"}`,
                      color: titleKey === k ? "var(--text-hi)" : "var(--text-mid)",
                      borderRadius: 4,
                      fontFamily: "var(--font-mono)", fontSize: 10.5, letterSpacing: "0.06em", textTransform: "uppercase",
                      cursor: "pointer",
                    }}>{k}</button>
                ))}
              </div>
            </div>

            {/* Hook + 3 beats */}
            <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 14, rowGap: 12 }}>
              <BriefBeat n="HOOK" body={hookText}/>
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
                  title: titles[titleKey] || hero.topic,
                  working_title: titles[titleKey] || hero.topic,
                  topic: hero.topic, category: hero.topic,
                  format: hero.best_content_format || "YouTube long-form", creator_score: hero.creator_score,
                  signal_score: hero.average_signal_score,
                  pipeline_type: "creator", status: "idea",
                }).then(() => { alert("Saved to pipeline as an idea."); window.DDX.reload(); });
              }}><I.Save size={12}/> Save to pipeline</button>
            </div>
          </div>

          {/* Right column: thumbnail + meta */}
          <div>
            <FakeThumb t={heroThumb} w={420} h={236}/>
            <div className="mono" style={{ fontSize: 10, color: "var(--text-lo)", marginTop: 8, letterSpacing: "0.04em", display: "flex", justifyContent: "space-between" }}>
              <span>thumb · variant A · CTR-likelihood {heroThumb?.ctr || 0}</span>
              <button className="btn ghost" onClick={() => onJump("thumbs")} style={{ padding: "2px 6px", fontSize: 10 }}>Open Thumb Lab</button>
            </div>

            {/* Score breakdown */}
            <div style={{ marginTop: 18, padding: "12px 14px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6 }}>
              <div className="label" style={{ color: "var(--text-hi)" }}>Why this scored {hero.creator_score}</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
                <FactorRow k="Audience interest" v={fAudience}/>
                <FactorRow k="Story tension" v={fTension}/>
                <FactorRow k="Demo value" v={fDemo}/>
                <FactorRow k="Visual potential" v={fVisual}/>
                <FactorRow k="Credibility" v={fCredibility}/>
                <FactorRow k="Differentiation" v={fDiff}/>
                <FactorRow k="Shelf life" v={fShelf} dim/>
                <FactorRow k="Production effort" v={fEffort} dim/>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Format split — long / short / linkedin / newsletter */}
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr", gap: 16 }}>
        <FormatCard
          tag="LONG-FORM" tagColor="var(--src-youtube)"
          eyebrow="YouTube · 14–18 min"
          title={titles[titleKey] || titles.practical}
          body={opp?.why_viewers_care || "Explore this hot AI update."}
          meta={[["Effort", opp?.production_effort || "medium"], ["Demo Value", `${fDemo}`], ["Best post-time", "Wed 6pm"]]}
          cta="Draft a script"
          onJump={onJump}
          action={() => { if (window.DDX) window.DDX.dispatch("script_writer", hero.topic, hero.slug); alert("Script Writer dispatched — see the agent rail."); }}
          broll={opp?.broll_list || []}
          cues={opp?.on_screen_cues || []}
        />
        <FormatCard
          tag="SHORT" tagColor="var(--src-youtube)"
          eyebrow="YT Short · 47s"
          title={titles.curiosity || "Short Form Angle"}
          body={opp?.short_script || opp?.opening_hook || "Vertical short script placeholder."}
          meta={[["Effort","low"], ["Tension", `${fTension}`], ["Vertical", "ready"]]}
          cta="Preview shorts deck"
          action={() => { const el = document.getElementById("shorts-reel"); if (el) el.scrollIntoView({ behavior: "smooth" }); }}
          broll={opp?.broll_list || []}
          cues={opp?.on_screen_cues || []}
        />
        <FormatCard
          tag="CAROUSEL" tagColor="var(--src-blogs)"
          eyebrow="LinkedIn · 8 slides"
          title={titles.contrarian || "LinkedIn Angle"}
          body={opp?.risks_or_caveats || "Why this trend matters for developers."}
          meta={[["Effort","low"], ["Credibility", `${fCredibility}`], ["Format", "Carousel"]]}
          cta="Build carousel"
          action={() => { if (window.DDX) window.DDX.dispatch("cross_poster", hero.topic, hero.slug); alert("Cross-Poster dispatched — see the agent rail."); }}
          broll={opp?.broll_list || []}
          cues={opp?.on_screen_cues || []}
        />
      </div>

      {/* Shorts deck */}
      <ShortsReel items={creator_brief?.shorts_ideas}/>

      {/* Quick wins */}
      <QuickWins items={creator_brief?.quick_wins} onJump={onJump}/>
    </div>
  );
};

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

const FormatCard = ({ tag, tagColor, eyebrow, title, body, meta, cta, onJump, action }) => (
  <div className="panel" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10, minHeight: 240 }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span className="mono" style={{
        padding: "2px 6px", border: `1px solid ${tagColor}55`, color: tagColor,
        background: `${tagColor}10`, fontSize: 10, letterSpacing: "0.06em", borderRadius: 2,
      }}>{tag}</span>
      <span className="micro">{eyebrow}</span>
    </div>
    <h3 style={{ fontSize: 17, lineHeight: 1.2, margin: 0, color: "var(--text-hi)", fontWeight: 600, letterSpacing: "-0.01em", textWrap: "balance" }}>{title}</h3>
    <p style={{ fontSize: 12.5, lineHeight: 1.5, color: "var(--text)", margin: 0, textWrap: "pretty" }}>{body}</p>
    <div style={{ marginTop: "auto", borderTop: "1px solid var(--line)", paddingTop: 10, display: "grid", gridTemplateColumns: meta.length === 3 ? "1fr 1fr 1fr" : "1fr 1fr", gap: 8 }}>
      {meta.map(([k, v]) => (
        <div key={k}>
          <div className="micro">{k}</div>
          <div className="mono" style={{ color: "var(--text-hi)", fontSize: 12, marginTop: 2 }}>{v}</div>
        </div>
      ))}
    </div>
    <div style={{ display: "flex", gap: 6, marginTop: "auto" }}>
      <button className="btn ghost" style={{ alignSelf: "flex-start" }} onClick={action}>{cta} <I.ArrowR size={11}/></button>
      <button className="btn ghost" onClick={() => {
        const content = `# Brief: ${title}\n\nFormat: ${tag} (${eyebrow})\n\n${body}\n\n## Metadata\n` + meta.map(([k,v]) => `- ${k}: ${v}`).join("\n");
        window.downloadScript(`${tag.toLowerCase()}_brief.md`, content);
      }}>Download</button>
    </div>
  </div>
);

// Shorts reel — swipe-deck for hook ideas
const SHORTS = [
  { id: "s1", hook: "Anthropic shipped this. Open-source caught up in 8 days.",   topic: "Computer Use Agents", tension: 91, demo: 88 },
  { id: "s2", hook: "A $35 Raspberry Pi just solved an Olympic math problem.",     topic: "On-Device Reasoning", tension: 86, demo: 94 },
  { id: "s3", hook: "I raced four open reasoners. The slowest one won. Here's why.", topic: "Open-Source o1",      tension: 84, demo: 79 },
  { id: "s4", hook: "Sesame's voice agent interrupts you mid-sentence. That's the breakthrough.", topic: "Voice Agents", tension: 89, demo: 72 },
  { id: "s5", hook: "Your RAG stack is already obsolete. Memory replaces retrieval.", topic: "Memory Systems", tension: 78, demo: 65 },
];

const ShortsReel = ({ items = [] }) => {
  const [idx, setIdx] = useState(0);
  const [decision, setDecision] = useState({});
 
  const rawShorts = items.length > 0 ? items.map((x, i) => ({
    id: x.content_hash || `s${i}`,
    hook: x.opening_hook || x.hook_line || x.title,
    topic: x.creator_topic || x.topic,
    tension: x.creator_score_breakdown?.story_tension || 80,
    demo: x.creator_score_breakdown?.practical_demo_value || 80,
    item: x
  })) : SHORTS;
 
  const swipe = (dir) => {
    const current = rawShorts[idx];
    setDecision(d => ({ ...d, [current.id]: dir }));
    if ((dir === "later" || dir === "film") && window.DDX && current.item) {
      window.DDX.saveToPipeline({
        title: current.hook,
        working_title: current.hook,
        topic: current.topic,
        category: current.topic,
        format: "YouTube short",
        creator_score: current.item.creator_score || 80,
        signal_score: current.item.signal_score || 70,
        pipeline_type: "creator",
        status: dir === "film" ? "script_ready" : "idea",
      }).then(() => { window.DDX.reload(); });
    }
    setTimeout(() => setIdx(i => Math.min(rawShorts.length - 1, i + 1)), 240);
  };
 
  if (rawShorts.length === 0) return null;
  const currentShort = rawShorts[idx] || rawShorts[0];
 
  return (
    <div className="panel" id="shorts-reel" style={{ overflow: "hidden" }}>
      <PanelHeader no="02"
        actions={
          <>
            <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.06em" }}>
              {idx + 1}/{rawShorts.length}
            </span>
            <button className="btn ghost" onClick={() => { setIdx(0); setDecision({}); }}>Reset</button>
          </>
        }>
        Shorts deck · swipe to pick
      </PanelHeader>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", padding: "16px 20px", gap: 24, alignItems: "center", minHeight: 230 }}>
        <div>
          <div className="micro" style={{ color: "var(--signal)" }}>Hook {idx + 1}</div>
          <h2 style={{
            fontSize: 32, lineHeight: 1.08, letterSpacing: "-0.02em", margin: "10px 0 14px",
            color: "var(--text-hi)", fontWeight: 600, textWrap: "balance",
          }}>"{currentShort.hook}"</h2>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <span className="chip">topic · {currentShort.topic}</span>
            <span className="chip" style={{ color: "var(--signal)" }}>tension {currentShort.tension}</span>
            <span className="chip" style={{ color: "var(--signal-up)" }}>demo {currentShort.demo}</span>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
            <button className="btn ghost" onClick={() => swipe("skip")}>
              <I.X size={12}/> Skip
            </button>
            <button className="btn ghost" onClick={() => swipe("later")}>Save for later</button>
            <button className="btn primary" onClick={() => swipe("film")}>Film today <I.Play size={11}/></button>
          </div>
 
          {/* Mini deck progress */}
          <div style={{ display: "flex", gap: 4, marginTop: 22 }}>
            {rawShorts.map((s, i) => (
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
 
        {/* Vertical phone-shaped preview */}
        <div style={{
          width: 180, height: 320, margin: "0 auto",
          borderRadius: 18, padding: 8,
          background: "var(--bg-0)", border: "1px solid var(--line-2)",
          boxShadow: "0 12px 32px rgba(0,0,0,0.3)",
          position: "relative",
        }}>
          <div style={{
            width: "100%", height: "100%", borderRadius: 12, overflow: "hidden", position: "relative",
            background: `linear-gradient(155deg, oklch(0.55 0.18 ${(idx * 60 + 14) % 360}), oklch(0.18 0.06 ${(idx * 60 + 14) % 360}))`,
          }}>
            {/* face circle */}
            <div style={{
              position: "absolute", top: "30%", left: "50%", transform: "translateX(-50%)",
              width: 90, height: 90, borderRadius: "50%",
              background: `radial-gradient(circle at 35% 35%, oklch(0.85 0.06 ${(idx * 60 + 14) % 360}), oklch(0.4 0.1 ${(idx * 60 + 14) % 360}))`,
              boxShadow: "inset 0 0 0 2px rgba(255,255,255,0.2)",
            }}/>
            <div style={{
              position: "absolute", left: 10, right: 10, bottom: 20,
              color: "#fff", fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: 14, lineHeight: 1.15,
              textShadow: "0 2px 8px rgba(0,0,0,0.5)",
            }}>"{currentShort.hook}"</div>
            <div style={{
              position: "absolute", top: 10, left: 10,
              padding: "2px 6px", background: "rgba(0,0,0,0.4)", color: "#fff",
              fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.06em", borderRadius: 2,
            }}>00:00 / 00:47</div>
          </div>
        </div>
      </div>
    </div>
  );
};

const QuickWins = ({ items = [], onJump }) => {
  const rawWins = items.length > 0 ? items.map((x, i) => ({
    topic: x.creator_topic || x.topic,
    kind: x.best_format || x.recommended_content_format || "LinkedIn post",
    effort: x.production_effort === "low" ? "10 min" : "25 min",
    impact: x.creator_score >= 80 ? "high" : "medium",
    note: x.why_viewers_care || x.risks_or_caveats || "Low-effort cross-post candidate."
  })) : [
    { topic: "Cheap Inference",        kind: "LinkedIn chart",    effort: "10 min", impact: "high",   note: "Price-per-token graph, 18mo. The carousel-of-the-week candidate." },
    { topic: "Memory Systems",         kind: "Newsletter intro",  effort: "25 min", impact: "medium", note: "Open with mem0 → letta → zep timeline. Two sources already drafted." },
    { topic: "Voice Agents",           kind: "X/Twitter thread",  effort: "15 min", impact: "high",   note: "Sesame demo + your 90-second take. Already has 412k views." },
    { topic: "Agent Frameworks",       kind: "Comment-bait reply",effort: "5 min",  impact: "medium", note: "On Greg Kamradt's video — your CrewAI take." },
  ];
  return (
    <div className="panel" style={{ overflow: "hidden" }}>
      <PanelHeader no="03"
        actions={<button className="btn ghost" onClick={() => onJump("pipeline")}>Open pipeline →</button>}>
        Quick wins · low-effort cross-posts
      </PanelHeader>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
        {rawWins.map((w, i) => (
          <div key={i} style={{
            padding: "12px 16px",
            borderBottom: i < 2 ? "1px solid var(--line)" : "none",
            borderRight: i % 2 === 0 ? "1px solid var(--line)" : "none",
            display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 14, alignItems: "center",
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 6,
              background: "var(--bg-2)", border: "1px solid var(--line-2)",
              display: "grid", placeItems: "center", color: "var(--signal)",
            }}>
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
              <span className="mono" style={{ fontSize: 10, color: w.impact === "high" ? "var(--signal-up)" : "var(--signal)", letterSpacing: "0.05em" }}>
                {w.impact.toUpperCase()} IMPACT
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

window.BriefView = BriefView;
