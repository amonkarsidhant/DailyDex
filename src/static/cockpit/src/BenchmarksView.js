// BenchmarksView.jsx
// React hooks come from AppShell's shared destructure (single source to avoid duplicate const in shared script scope).

const BenchmarksView = () => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch("/api/benchmarks").then(r => r.json()).then(d => {
      setBenchmarks(d.benchmarks || []);
      setLoading(false);
    }).catch(e => {
      console.error(e);
      setLoading(false);
    });
  }, []);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "24px 32px",
      maxWidth: 1000,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 24,
      fontWeight: 600,
      color: "var(--text-hi)"
    }
  }, "AI Benchmarks"), /*#__PURE__*/React.createElement("p", {
    style: {
      color: "var(--text-mid)",
      fontSize: 14,
      marginTop: 8
    }
  }, "Live LLM capabilities scraped from Artificial Analysis, used for autonomous model routing.")), loading ? /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      color: "var(--text-lo)"
    }
  }, "Loading benchmarks...") : /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--bg-1)",
      border: "1px solid var(--line)",
      borderRadius: 8,
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("table", {
    style: {
      width: "100%",
      borderCollapse: "collapse",
      textAlign: "left"
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    style: {
      background: "var(--bg-2)",
      borderBottom: "1px solid var(--line)"
    }
  }, /*#__PURE__*/React.createElement("th", {
    style: {
      padding: "12px 16px",
      color: "var(--text-mid)",
      fontWeight: 600,
      fontSize: 12
    }
  }, "Model"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: "12px 16px",
      color: "var(--text-mid)",
      fontWeight: 600,
      fontSize: 12
    }
  }, "Intelligence Index"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: "12px 16px",
      color: "var(--text-mid)",
      fontWeight: 600,
      fontSize: 12
    }
  }, "Speed (Tok/s)"), /*#__PURE__*/React.createElement("th", {
    style: {
      padding: "12px 16px",
      color: "var(--text-mid)",
      fontWeight: 600,
      fontSize: 12
    }
  }, "Price / 1M Tok ($)"))), /*#__PURE__*/React.createElement("tbody", null, benchmarks.map((b, i) => /*#__PURE__*/React.createElement("tr", {
    key: b.model_name,
    style: {
      borderBottom: i < benchmarks.length - 1 ? "1px solid var(--line)" : "none"
    }
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      padding: "12px 16px",
      color: "var(--text-hi)",
      fontWeight: 500,
      fontSize: 14
    }
  }, b.model_name), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: "12px 16px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      color: "var(--text)",
      width: 40
    }
  }, b.intelligence_index?.toFixed(1) || "N/A"), b.intelligence_index && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 100,
      height: 4,
      background: "var(--bg-3)",
      borderRadius: 2
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${Math.min(100, b.intelligence_index / 100 * 100)}%`,
      height: "100%",
      background: "var(--signal)",
      borderRadius: 2
    }
  })))), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: "12px 16px"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      color: "var(--text)"
    }
  }, b.speed_tokens_sec ? Math.round(b.speed_tokens_sec) : "N/A")), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: "12px 16px"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono tnum",
    style: {
      color: "var(--text)"
    }
  }, b.price_per_1m !== null ? `$${b.price_per_1m.toFixed(2)}` : "N/A")))), benchmarks.length === 0 && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
    colSpan: "4",
    style: {
      padding: "24px 16px",
      textAlign: "center",
      color: "var(--text-lo)"
    }
  }, "No benchmarks available. Run the fetcher script."))))));
};
window.BenchmarksView = BenchmarksView;