// ResearchView — research pack viewer with live agent synthesis

const ResearchView = ({ onJump }) => {
  const { clusters } = window.DD_DATA;
  const [topic, setTopic] = useState((clusters[0] && clusters[0].slug) || "");
  const cluster = clusters.find(c => c.slug === topic) || clusters[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel crosshair" style={{ overflow: "hidden" }}>
        <span className="ch-bl"/><span className="ch-br"/>
        <PanelHeader no="01"
          actions={
            <>
              <button className="btn ghost"><I.Doc size={12}/> Export MD</button>
              <button className="btn ghost">Open file</button>
              <button className="btn primary"><I.Spark size={11}/> Re-research</button>
            </>
          }>
          Research pack · data/research_packs/2026-05-22-{topic}.md
        </PanelHeader>

        <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", minHeight: 580 }}>
          {/* Sidebar — pack list */}
          <div style={{ borderRight: "1px solid var(--line)", padding: "12px 0", overflowY: "auto" }}>
            <div className="micro" style={{ padding: "0 14px 8px" }}>Today</div>
            {clusters.slice(0, 4).map(c => (
              <PackRow key={c.slug} c={c} active={topic === c.slug} onClick={() => setTopic(c.slug)} when="today" />
            ))}
            <div className="micro" style={{ padding: "12px 14px 8px" }}>Yesterday</div>
            {clusters.slice(4).map(c => (
              <PackRow key={c.slug} c={c} active={topic === c.slug} onClick={() => setTopic(c.slug)} when="yesterday" />
            ))}
          </div>

          {/* Pack content */}
          <div style={{ overflowY: "auto", padding: "20px 28px" }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <span className="mono" style={{
                padding: "3px 8px", border: "1px solid var(--signal)", color: "var(--signal)",
                background: "rgba(240,183,47,0.06)", borderRadius: 3,
                fontSize: 10.5, letterSpacing: "0.06em",
              }}>RESEARCH PACK · v3</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--text-lo)" }}>last refreshed 12m ago by Topic Researcher</span>
            </div>
            <h1 style={{
              fontSize: 36, lineHeight: 1.06, letterSpacing: "-0.02em",
              margin: "12px 0 6px", color: "var(--text-hi)", fontWeight: 700, textWrap: "balance",
            }}>{cluster.topic}</h1>
            <p className="serif" style={{
              fontSize: 19, fontStyle: "italic", lineHeight: 1.4, color: "var(--text)",
              margin: 0, textWrap: "pretty", maxWidth: 720,
            }}>{cluster.recommended_angle}</p>

            <Divider/>

            <Section title="Core claim" no="01">
              <p style={{ fontSize: 14, lineHeight: 1.55, color: "var(--text)", margin: 0, textWrap: "pretty" }}>
                Open-source computer-use agents have closed the gap with Anthropic's October release in roughly 8 days.
                Five source families confirm independent reproductions, with at least one (browser-use) running fully local.
                The story is the <span style={{ color: "var(--text-hi)", fontWeight: 600 }}>speed of catch-up</span>, not the absolute capability.
              </p>
            </Section>

            <Section title="Key evidence" no="02">
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {cluster.related_items.map((it, i) => (
                  <EvidenceRow key={i} idx={i + 1} it={it} />
                ))}
              </div>
            </Section>

            <Section title="Counterpoints" no="03">
              <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 8 }}>
                <Counter pt="Browser-use v0.9 still fails on dynamic forms (~38% drop vs Claude)." src="github · #1247"/>
                <Counter pt="xLAM-2 requires 7B at FP16 — not laptop-friendly without quantization." src="HF discussions"/>
                <Counter pt="Reproducibility is single-task; nobody has run the full WebArena benchmark on these yet." src="papers · open issue"/>
              </ul>
            </Section>

            <Section title="Stats worth quoting" no="04">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                <StatCard big="8 days" small="from Anthropic ship → first open implementation"/>
                <StatCard big="9.4k ★" small="browser-use stars (+1.2k in 24h)"/>
                <StatCard big="412k ▶" small="AI Jason's reaction video, 4 days"/>
                <StatCard big="5/5" small="source families reporting"/>
                <StatCard big="184k ↓" small="xLAM-2-Computer-Use downloads"/>
                <StatCard big="$0" small="local-runnable cost on M-series Mac"/>
              </div>
            </Section>

            <Section title="Demo recipe" no="05">
              <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13.5, lineHeight: 1.7, color: "var(--text)" }}>
                <li>Set up 3 agents: browser-use (local), xLAM-2 (local), Claude Computer Use (API).</li>
                <li>Give each the same 5 tasks: book a flight, fill a form, scrape a table, write a tweet, search a codebase.</li>
                <li>10-minute time budget, no human help, screen-record.</li>
                <li>Score: success y/n, time, intervention count.</li>
                <li>Decision tree as the closing graphic — viewers screenshot this.</li>
              </ol>
            </Section>

            <Section title="Suggested outline" no="06">
              <BeatRow n="00:00" t="Hook: 'Anthropic shipped this in October. Eight days later, the open-source version is free.'"/>
              <BeatRow n="00:25" t="The bet: same tasks, three agents, ten minutes each."/>
              <BeatRow n="02:10" t="Demo 1 — browser-use crushes a flight booking."/>
              <BeatRow n="05:40" t="Demo 2 — xLAM-2 nails the file system."/>
              <BeatRow n="09:00" t="Demo 3 — Claude wins on multi-step reasoning."/>
              <BeatRow n="12:20" t="Decision tree + repo dump."/>
              <BeatRow n="14:30" t="Closing: 'The interesting question isn't who's best — it's how fast the gap closes.'"/>
            </Section>

            <div style={{ display: "flex", gap: 8, marginTop: 24 }}>
              <button className="btn primary" onClick={() => onJump("brief")}><I.Brief size={12}/> Open in brief</button>
              <button className="btn ghost"><I.Save size={12}/> Send to pipeline</button>
              <button className="btn ghost" onClick={() => onJump("thumbs")}><I.Thumb size={12}/> Generate thumbnails</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const PackRow = ({ c, active, onClick, when }) => {
  const S = window.DD_DATA.SOURCES;
  return (
    <button onClick={onClick} style={{
      display: "grid", gridTemplateColumns: "auto 1fr", gap: 10,
      width: "100%", padding: "8px 14px", textAlign: "left",
      background: active ? "var(--bg-2)" : "transparent",
      borderLeft: `2px solid ${active ? "var(--signal)" : "transparent"}`,
      border: "none", cursor: "pointer", color: "var(--text)",
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: S[c.sources[0]].color, marginTop: 6 }}/>
      <span style={{ lineHeight: 1.2 }}>
        <span style={{ display: "block", color: active ? "var(--text-hi)" : "var(--text)", fontSize: 12.5, fontWeight: active ? 600 : 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.topic}</span>
        <span className="mono" style={{ display: "block", fontSize: 10, color: "var(--text-lo)", marginTop: 2, letterSpacing: "0.04em" }}>
          {c.source_count}× · score {c.creator_score}
        </span>
      </span>
    </button>
  );
};

const Divider = () => <div style={{ height: 1, background: "var(--line)", margin: "20px 0" }}/>;

const Section = ({ title, no, children }) => (
  <section style={{ marginTop: 22 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
      <span className="mono" style={{ color: "var(--text-lo)", fontSize: 10, letterSpacing: "0.08em" }}>{no}</span>
      <h3 className="label" style={{ color: "var(--text-hi)", fontWeight: 600, margin: 0 }}>{title}</h3>
      <span style={{ flex: 1, height: 1, background: "var(--line)" }}/>
    </div>
    {children}
  </section>
);

const EvidenceRow = ({ idx, it }) => (
  <div style={{
    display: "grid", gridTemplateColumns: "26px auto 1fr auto auto", gap: 12, alignItems: "center",
    padding: "10px 12px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4,
  }}>
    <span className="mono" style={{ color: "var(--text-lo)", fontSize: 10.5, letterSpacing: "0.05em" }}>{String(idx).padStart(2, "0")}</span>
    <SourceChip src={it.source_type}/>
    <div style={{ minWidth: 0 }}>
      <div style={{ color: "var(--text-hi)", fontSize: 13, fontWeight: 500 }}>{it.title}</div>
      <div className="mono" style={{ fontSize: 10.5, color: "var(--text-lo)", marginTop: 2 }}>
        {[it.stars && `★ ${it.stars}`, it.downloads && `↓ ${it.downloads}`, it.views && `▶ ${it.views}`, it.citations, it.source, it.channel].filter(Boolean).join(" · ")}
        {it.delta && <span style={{ color: "var(--signal-up)", marginLeft: 6 }}>{it.delta}</span>}
      </div>
    </div>
    <ScoreBar value={it.signal_score} w={56} label={false}/>
    <span className="mono tnum" style={{ fontSize: 11, color: "var(--text-hi)", fontWeight: 600, minWidth: 24, textAlign: "right" }}>{it.signal_score}</span>
  </div>
);

const Counter = ({ pt, src }) => (
  <li style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 10, alignItems: "baseline" }}>
    <span style={{ color: "var(--signal-down)" }}>—</span>
    <span style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5, textWrap: "pretty" }}>{pt}</span>
    <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)", letterSpacing: "0.04em" }}>{src}</span>
  </li>
);

const StatCard = ({ big, small }) => (
  <div style={{ padding: "12px 14px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4 }}>
    <div className="mono tnum" style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 22, letterSpacing: "-0.01em" }}>{big}</div>
    <div style={{ fontSize: 11.5, color: "var(--text-mid)", marginTop: 4, lineHeight: 1.35 }}>{small}</div>
  </div>
);

const BeatRow = ({ n, t }) => (
  <div style={{ display: "grid", gridTemplateColumns: "60px 1fr", gap: 12, alignItems: "baseline", padding: "5px 0", borderBottom: "1px dashed var(--line)" }}>
    <span className="mono tnum" style={{ color: "var(--signal)", fontSize: 11, letterSpacing: "0.04em" }}>{n}</span>
    <span style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.45 }}>{t}</span>
  </div>
);

window.ResearchView = ResearchView;
