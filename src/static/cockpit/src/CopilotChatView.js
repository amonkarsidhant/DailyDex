function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// React hooks come from AppShell's shared destructure (single source to avoid duplicate const in shared script scope).

const CopilotChatView = ({
  selectedClusterSlug
}) => {
  const [messages, setMessages] = useState([{
    role: "assistant",
    text: "Hello! I am your DailyDex Strategist Copilot. Ask me anything about the active trends, pipeline, or today's top picks. I have direct access to our live crawled data."
  }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  // Auto-scroll chat history
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);
  const presetQuestions = ["What are the top 3 highest-momentum trends today?", "Generate a structured script outline for the top cluster", "Compare the star/view counts of github and youtube evidence", "Identify contrarian angles for the Coding AI trend"];
  const submitQuestion = async qText => {
    const q = qText || input ? (qText || input).trim() : "";
    if (!q || busy) return;

    // Add user message
    const userMsg = {
      role: "user",
      text: q
    };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setBusy(true);
    try {
      const res = await window.DDX.copilot("copilot_chat", q, {
        focused_cluster: selectedClusterSlug
      });
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
  const topPick = window.DD_DATA.clusters.find(cluster => cluster.slug === selectedClusterSlug) || window.DD_DATA.clusters[0] || null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 340px",
      gap: 16,
      height: "calc(100vh - 120px)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      display: "flex",
      flexDirection: "column",
      height: "100%",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    no: "CO",
    actions: /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 9,
        color: "var(--text-lo)"
      }
    }, "DAILYDEX COPILOT ENGINE \xB7 ACTIVE")
  }, "AI Strategist Chat"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      padding: 16,
      overflowY: "auto",
      display: "flex",
      flexDirection: "column",
      gap: 12
    },
    ref: scrollRef
  }, messages.map((m, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      alignSelf: m.role === "user" ? "flex-end" : "flex-start",
      maxWidth: "80%",
      display: "flex",
      flexDirection: "column",
      alignItems: m.role === "user" ? "flex-end" : "flex-start"
    }
  }, /*#__PURE__*/React.createElement("div", _extends({
    className: m.role === "user" ? "" : "markdown-content",
    style: {
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
    }
  }, m.role === "user" ? {
    children: m.text
  } : {
    dangerouslySetInnerHTML: {
      __html: safeMarkdown(m.text)
    }
  })), m.model && /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 8.5,
      color: "var(--text-lo)",
      marginTop: 4
    }
  }, "via ", m.model.toUpperCase()))), busy && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      color: "var(--text-lo)",
      fontSize: 12,
      paddingLeft: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "blink",
    style: {
      width: 6,
      height: 6,
      borderRadius: 999,
      background: "var(--signal)"
    }
  }), "Thinking...")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "8px 12px",
      borderTop: "1px solid var(--line)",
      background: "var(--bg-2)",
      display: "flex",
      gap: 6,
      overflowX: "auto"
    }
  }, presetQuestions.map((q, idx) => /*#__PURE__*/React.createElement("button", {
    key: idx,
    className: "btn ghost",
    style: {
      textTransform: "none",
      fontSize: 10.5,
      letterSpacing: 0,
      flexShrink: 0
    },
    onClick: () => submitQuestion(q),
    disabled: busy
  }, q))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 12,
      borderTop: "1px solid var(--line)",
      display: "grid",
      gridTemplateColumns: "1fr auto",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("input", {
    value: input,
    onChange: e => setInput(e.target.value),
    onKeyDown: e => {
      if (e.key === "Enter") submitQuestion();
    },
    placeholder: "Type your content strategy question here...",
    disabled: busy,
    style: {
      height: 38,
      padding: "0 12px",
      background: "var(--bg-2)",
      border: "1px solid var(--line-2)",
      borderRadius: 6,
      color: "var(--text-hi)",
      fontSize: 13,
      outline: "none"
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: () => submitQuestion(),
    disabled: busy || !input.trim(),
    style: {
      height: 38
    }
  }, "Send ", /*#__PURE__*/React.createElement(I.Send, {
    size: 12,
    stroke: "#1A1100",
    strokeWidth: 1.8
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginBottom: 12
    }
  }, "Active Context"), topPick ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "var(--text-lo)"
    }
  }, "TOP PICK OF THE DAY"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 16,
      fontWeight: 700,
      color: "var(--signal)"
    }
  }, topPick.topic), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 12.5,
      color: "var(--text)",
      margin: "4px 0 0",
      lineHeight: 1.4
    }
  }, topPick.why_this_is_a_story), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      marginTop: 4,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "chip"
  }, topPick.source_count, " sources"), /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      color: "var(--signal-up)"
    }
  }, "+", topPick.momentum, "%"), /*#__PURE__*/React.createElement("span", {
    className: "chip"
  }, "Score ", topPick.creator_score))) : /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 11,
      color: "var(--text-lo)"
    }
  }, "No active pick today.")), /*#__PURE__*/React.createElement("div", {
    className: "panel",
    style: {
      padding: 16,
      flex: 1,
      overflowY: "auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "micro",
    style: {
      marginBottom: 12
    }
  }, "Active Trends list (", window.DD_DATA.clusters.length, ")"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, window.DD_DATA.clusters.slice(0, 8).map((c, idx) => /*#__PURE__*/React.createElement("div", {
    key: idx,
    style: {
      padding: "6px 8px",
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      borderRadius: 4,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 600,
      color: "var(--text-hi)",
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
  }, c.sources.join(", "))), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: "var(--signal)"
    }
  }, c.creator_score)))))));
};
window.CopilotChatView = CopilotChatView;