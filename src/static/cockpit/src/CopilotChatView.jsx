// React hooks come from AppShell's shared destructure (single source to avoid duplicate const in shared script scope).

const CopilotChatView = () => {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hello! I am your DailyDex Strategist Copilot. Ask me anything about the active trends, pipeline, or today's top picks. I have direct access to our live crawled data."
    }
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  // Auto-scroll chat history
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const presetQuestions = [
    "What are the top 3 highest-momentum trends today?",
    "Generate a structured script outline for the top cluster",
    "Compare the star/view counts of github and youtube evidence",
    "Identify contrarian angles for the Coding AI trend"
  ];

  const submitQuestion = async (qText) => {
    const q = (qText || input) ? (qText || input).trim() : "";
    if (!q || busy) return;
    
    // Add user message
    const userMsg = { role: "user", text: q };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setBusy(true);

    try {
      const topSlug = (window.DD_DATA.clusters[0] || {}).slug;
      const res = await window.DDX.copilot("copilot_chat", q, { focused_cluster: topSlug });
      setMessages(prev => [...prev, {
        role: "assistant",
        text: res.answer || "No response.",
        model: res.model
      }]);
    } catch (e) {
      setMessages(prev => [...prev, {
        role: "assistant",
        text: "Error calling Copilot. Make sure the backend Flask server is running and a CLI provider is configured.",
        isError: true
      }]);
    } finally {
      setBusy(false);
    }
  };

  const topPick = window.DD_DATA.clusters[0] || null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16, height: "calc(100vh - 120px)" }}>
      {/* Left Column: Chat Area */}
      <div className="panel" style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
        <PanelHeader no="CO" actions={
          <span className="mono" style={{ fontSize: 9, color: "var(--text-lo)" }}>
            DAILYDEX COPILOT ENGINE · ACTIVE
          </span>
        }>
          AI Strategist Chat
        </PanelHeader>

        {/* Chat History */}
        <div style={{ flex: 1, padding: 16, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }} ref={scrollRef}>
          {messages.map((m, i) => (
            <div key={i} style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "80%",
              display: "flex",
              flexDirection: "column",
              alignItems: m.role === "user" ? "flex-end" : "flex-start"
            }}>
              <div
                className={m.role === "user" ? "" : "markdown-content"}
                style={{
                  padding: "10px 14px",
                  borderRadius: 8,
                  background: m.role === "user" ? "var(--bg-3)" : "rgba(22, 22, 26, 0.85)",
                  border: `1px solid ${m.role === "user" ? "var(--signal)" : "var(--line-2)"}`,
                  color: m.isError ? "var(--signal-down)" : "var(--text-hi)",
                  fontSize: 13,
                  lineHeight: 1.5,
                  whiteSpace: m.role === "user" ? "pre-wrap" : "normal",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                  backdropFilter: m.role === "user" ? "none" : "blur(8px)"
                }}
                {...(m.role === "user" ? { children: m.text } : { dangerouslySetInnerHTML: { __html: window.marked ? window.marked.parse(m.text) : m.text } })}
              />
              {m.model && (
                <span className="mono" style={{ fontSize: 8.5, color: "var(--text-lo)", marginTop: 4 }}>
                  via {m.model.toUpperCase()}
                </span>
              )}
            </div>
          ))}
          {busy && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-lo)", fontSize: 12, paddingLeft: 6 }}>
              <span className="blink" style={{ width: 6, height: 6, borderRadius: 999, background: "var(--signal)" }}/>
              Thinking...
            </div>
          )}
        </div>

        {/* Preset suggestions */}
        <div style={{ padding: "8px 12px", borderTop: "1px solid var(--line)", background: "var(--bg-2)", display: "flex", gap: 6, overflowX: "auto" }}>
          {presetQuestions.map((q, idx) => (
            <button key={idx} className="btn ghost" style={{ textTransform: "none", fontSize: 10.5, letterSpacing: 0, flexShrink: 0 }}
                    onClick={() => submitQuestion(q)} disabled={busy}>
              {q}
            </button>
          ))}
        </div>

        {/* Input box */}
        <div style={{ padding: 12, borderTop: "1px solid var(--line)", display: "grid", gridTemplateColumns: "1fr auto", gap: 10 }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") submitQuestion(); }}
            placeholder="Type your content strategy question here..."
            disabled={busy}
            style={{
              height: 38,
              padding: "0 12px",
              background: "var(--bg-2)",
              border: "1px solid var(--line-2)",
              borderRadius: 6,
              color: "var(--text-hi)",
              fontSize: 13,
              outline: "none"
            }}
          />
          <button className="btn primary" onClick={() => submitQuestion()} disabled={busy || !input.trim()} style={{ height: 38 }}>
            Send <I.Send size={12} stroke="#1A1100" strokeWidth={1.8}/>
          </button>
        </div>
      </div>

      {/* Right Column: Strategic Context */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Active Context */}
        <div className="panel" style={{ padding: 16 }}>
          <div className="micro" style={{ marginBottom: 12 }}>Active Context</div>
          {topPick ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontSize: 11, color: "var(--text-lo)" }}>TOP PICK OF THE DAY</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "var(--signal)" }}>{topPick.topic}</div>
              <p style={{ fontSize: 12.5, color: "var(--text)", margin: "4px 0 0", lineHeight: 1.4 }}>
                {topPick.why_this_is_a_story}
              </p>
              <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                <span className="chip">{topPick.source_count} sources</span>
                <span className="chip" style={{ color: "var(--signal-up)" }}>+{topPick.momentum}%</span>
                <span className="chip">Score {topPick.creator_score}</span>
              </div>
            </div>
          ) : (
            <div className="mono" style={{ fontSize: 11, color: "var(--text-lo)" }}>No active pick today.</div>
          )}
        </div>

        {/* System Diagnostics */}
        <div className="panel" style={{ padding: 16, flex: 1, overflowY: "auto" }}>
          <div className="micro" style={{ marginBottom: 12 }}>Active Trends list ({window.DD_DATA.clusters.length})</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {window.DD_DATA.clusters.slice(0, 8).map((c, idx) => (
              <div key={idx} style={{ padding: "6px 8px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 4, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-hi)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.topic}</div>
                  <div className="mono" style={{ fontSize: 9.5, color: "var(--text-lo)", marginTop: 2 }}>{c.sources.join(", ")}</div>
                </div>
                <span className="mono" style={{ fontSize: 11, color: "var(--signal)" }}>{c.creator_score}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

window.CopilotChatView = CopilotChatView;
