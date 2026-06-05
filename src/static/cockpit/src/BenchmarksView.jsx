// BenchmarksView.jsx
// React hooks come from AppShell's shared destructure (single source to avoid duplicate const in shared script scope).

const BenchmarksView = () => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/benchmarks")
      .then(r => r.json())
      .then(d => {
        setBenchmarks(d.benchmarks || []);
        setLoading(false);
      })
      .catch(e => {
        console.error(e);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1000, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, color: "var(--text-hi)" }}>AI Benchmarks</h1>
        <p style={{ color: "var(--text-mid)", fontSize: 14, marginTop: 8 }}>
          Live LLM capabilities scraped from Artificial Analysis, used for autonomous model routing.
        </p>
      </div>
      
      {loading ? (
        <div className="mono" style={{ color: "var(--text-lo)" }}>Loading benchmarks...</div>
      ) : (
        <div style={{
          background: "var(--bg-1)", 
          border: "1px solid var(--line)", 
          borderRadius: 8,
          overflow: "hidden"
        }}>
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead>
              <tr style={{ background: "var(--bg-2)", borderBottom: "1px solid var(--line)" }}>
                <th style={{ padding: "12px 16px", color: "var(--text-mid)", fontWeight: 600, fontSize: 12 }}>Model</th>
                <th style={{ padding: "12px 16px", color: "var(--text-mid)", fontWeight: 600, fontSize: 12 }}>Intelligence Index</th>
                <th style={{ padding: "12px 16px", color: "var(--text-mid)", fontWeight: 600, fontSize: 12 }}>Speed (Tok/s)</th>
                <th style={{ padding: "12px 16px", color: "var(--text-mid)", fontWeight: 600, fontSize: 12 }}>Price / 1M Tok ($)</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((b, i) => (
                <tr key={b.model_name} style={{ borderBottom: i < benchmarks.length - 1 ? "1px solid var(--line)" : "none" }}>
                  <td style={{ padding: "12px 16px", color: "var(--text-hi)", fontWeight: 500, fontSize: 14 }}>{b.model_name}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className="mono tnum" style={{ color: "var(--text)", width: 40 }}>{b.intelligence_index?.toFixed(1) || "N/A"}</span>
                      {b.intelligence_index && (
                        <div style={{ width: 100, height: 4, background: "var(--bg-3)", borderRadius: 2 }}>
                          <div style={{ width: `${Math.min(100, (b.intelligence_index / 100) * 100)}%`, height: "100%", background: "var(--signal)", borderRadius: 2 }} />
                        </div>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span className="mono tnum" style={{ color: "var(--text)" }}>{b.speed_tokens_sec ? Math.round(b.speed_tokens_sec) : "N/A"}</span>
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span className="mono tnum" style={{ color: "var(--text)" }}>{b.price_per_1m !== null ? `$${b.price_per_1m.toFixed(2)}` : "N/A"}</span>
                  </td>
                </tr>
              ))}
              {benchmarks.length === 0 && (
                <tr>
                  <td colSpan="4" style={{ padding: "24px 16px", textAlign: "center", color: "var(--text-lo)" }}>No benchmarks available. Run the fetcher script.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

window.BenchmarksView = BenchmarksView;
