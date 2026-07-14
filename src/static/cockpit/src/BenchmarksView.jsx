// BenchmarksView.jsx
// React hooks come from AppShell's shared destructure (single source to avoid duplicate const in shared script scope).

const BenchmarksView = () => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [preset, setPreset] = useState("all");
  const [minIntelligence, setMinIntelligence] = useState("");
  const [minSpeed, setMinSpeed] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [sortBy, setSortBy] = useState("intelligence");

  useEffect(() => {
    fetch("/api/benchmarks")
      .then(r => {
        if (!r.ok) throw new Error(`Request failed (${r.status})`);
        return r.json();
      })
      .then(d => {
        setBenchmarks(d.benchmarks || []);
        setLoading(false);
      })
      .catch(e => {
        console.error(e);
        setError(e.message || "Unable to load benchmarks");
        setLoading(false);
      });
  }, []);

  const presets = [
    { key: "all", label: "All models", test: () => true },
    { key: "frontier", label: "Frontier", hint: "40+ intelligence", test: b => b.intelligence_index >= 40 },
    { key: "fast", label: "Fast inference", hint: "150+ tok/s", test: b => b.speed_tokens_sec >= 150 },
    { key: "budget", label: "Budget", hint: "$1 or less", test: b => b.price_per_1m !== null && b.price_per_1m <= 1 },
    {
      key: "sweet",
      label: "Builder sweet spot",
      hint: "25+ IQ / 75+ tok/s / $3 max",
      test: b => b.intelligence_index >= 25 && b.speed_tokens_sec >= 75 && b.price_per_1m !== null && b.price_per_1m <= 3,
    },
    {
      key: "complete",
      label: "Complete data",
      hint: "No missing metrics",
      test: b => b.intelligence_index !== null && b.speed_tokens_sec !== null && b.price_per_1m !== null,
    },
  ];

  const activePreset = presets.find(p => p.key === preset) || presets[0];
  const asLimit = value => value === "" ? null : Number(value);
  const intelligenceLimit = asLimit(minIntelligence);
  const speedLimit = asLimit(minSpeed);
  const priceLimit = asLimit(maxPrice);
  const normalizedQuery = query.trim().toLowerCase();

  const rows = benchmarks
    .filter(b => {
      if (normalizedQuery && !b.model_name.toLowerCase().includes(normalizedQuery)) return false;
      if (!activePreset.test(b)) return false;
      if (intelligenceLimit !== null && (b.intelligence_index === null || b.intelligence_index < intelligenceLimit)) return false;
      if (speedLimit !== null && (b.speed_tokens_sec === null || b.speed_tokens_sec < speedLimit)) return false;
      if (priceLimit !== null && (b.price_per_1m === null || b.price_per_1m > priceLimit)) return false;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "speed") return (b.speed_tokens_sec ?? -1) - (a.speed_tokens_sec ?? -1);
      if (sortBy === "price") return (a.price_per_1m ?? Infinity) - (b.price_per_1m ?? Infinity);
      if (sortBy === "name") return a.model_name.localeCompare(b.model_name);
      return (b.intelligence_index ?? -1) - (a.intelligence_index ?? -1);
    });

  const hasFilters = query || preset !== "all" || minIntelligence || minSpeed || maxPrice || sortBy !== "intelligence";
  const resetFilters = () => {
    setQuery("");
    setPreset("all");
    setMinIntelligence("");
    setMinSpeed("");
    setMaxPrice("");
    setSortBy("intelligence");
  };

  const controlStyle = {
    width: "100%", boxSizing: "border-box", background: "var(--bg-3)",
    border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)",
    padding: "8px 10px", fontFamily: "var(--font-mono)", fontSize: 11, outline: "none",
  };

  return (
    <div style={{ padding: "24px clamp(14px, 3vw, 32px)", maxWidth: 1180, margin: "0 auto" }}>
      <div style={{ marginBottom: 20, display: "flex", justifyContent: "space-between", gap: 20, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div>
          <div className="micro" style={{ color: "var(--signal)", marginBottom: 6 }}>MODEL SELECTION MATRIX</div>
          <h1 style={{ fontSize: 24, fontWeight: 600, color: "var(--text-hi)", margin: 0 }}>AI Benchmarks</h1>
          <p style={{ color: "var(--text-mid)", fontSize: 13, margin: "7px 0 0" }}>
            Find the capability, latency, and cost envelope that fits your workload.
          </p>
        </div>
        <a href="https://artificialanalysis.ai/" target="_blank" rel="noreferrer"
           className="mono" style={{ color: "var(--text-lo)", fontSize: 10, textDecoration: "none" }}>
          DATA: ARTIFICIAL ANALYSIS -&gt;
        </a>
      </div>

      {loading ? (
        <div className="mono" style={{ color: "var(--text-lo)" }}>Loading benchmarks...</div>
      ) : error ? (
        <div style={{ padding: 18, border: "1px solid var(--signal-down)", borderRadius: 6, color: "var(--signal-down)", background: "var(--bg-1)" }}>
          Benchmark data unavailable: {error}
        </div>
      ) : (
        <>
          <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 8, marginBottom: 12, overflow: "hidden" }}>
            <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
              <div className="micro" style={{ marginBottom: 9 }}>QUICK CUTS</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
                {presets.map(option => {
                  const active = preset === option.key;
                  return (
                    <button key={option.key} onClick={() => setPreset(option.key)} title={option.hint || option.label}
                            style={{
                              background: active ? "rgba(240,183,47,0.12)" : "var(--bg-3)",
                              color: active ? "var(--signal)" : "var(--text-mid)",
                              border: `1px solid ${active ? "rgba(240,183,47,0.55)" : "var(--line-2)"}`,
                              borderRadius: 999, padding: "6px 10px", cursor: "pointer",
                              fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: active ? 600 : 500,
                            }}>
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div style={{ padding: 14, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 10 }}>
              <label>
                <span className="micro" style={{ display: "block", marginBottom: 6 }}>MODEL NAME</span>
                <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search Qwen, Claude..." style={controlStyle}/>
              </label>
              <label>
                <span className="micro" style={{ display: "block", marginBottom: 6 }}>MIN INTELLIGENCE</span>
                <input type="number" min="0" value={minIntelligence} onChange={e => setMinIntelligence(e.target.value)} placeholder="Any" style={controlStyle}/>
              </label>
              <label>
                <span className="micro" style={{ display: "block", marginBottom: 6 }}>MIN TOKENS / SEC</span>
                <input type="number" min="0" value={minSpeed} onChange={e => setMinSpeed(e.target.value)} placeholder="Any" style={controlStyle}/>
              </label>
              <label>
                <span className="micro" style={{ display: "block", marginBottom: 6 }}>MAX $ / 1M OUTPUT</span>
                <input type="number" min="0" step="0.1" value={maxPrice} onChange={e => setMaxPrice(e.target.value)} placeholder="Any" style={controlStyle}/>
              </label>
              <label>
                <span className="micro" style={{ display: "block", marginBottom: 6 }}>RANK BY</span>
                <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={controlStyle}>
                  <option value="intelligence">Intelligence: high to low</option>
                  <option value="speed">Speed: high to low</option>
                  <option value="price">Price: low to high</option>
                  <option value="name">Model name: A to Z</option>
                </select>
              </label>
            </div>

            <div style={{ padding: "9px 14px", borderTop: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <span className="mono tnum" style={{ fontSize: 10, color: "var(--text-lo)" }}>
                SHOWING <span style={{ color: "var(--signal)" }}>{rows.length}</span> OF {benchmarks.length} MODELS
                {activePreset.hint ? ` / ${activePreset.hint.toUpperCase()}` : ""}
              </span>
              <button className="btn ghost" disabled={!hasFilters} onClick={resetFilters}
                      style={{ opacity: hasFilters ? 1 : 0.4, cursor: hasFilters ? "pointer" : "default" }}>
                Reset filters
              </button>
            </div>
          </div>

          <div style={{ background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 8, overflow: "auto", maxHeight: "calc(100vh - 360px)", minHeight: 260 }}>
            <table style={{ width: "100%", minWidth: 720, borderCollapse: "collapse", textAlign: "left" }}>
              <thead style={{ position: "sticky", top: 0, zIndex: 2 }}>
                <tr style={{ background: "var(--bg-2)", borderBottom: "1px solid var(--line)" }}>
                  <th style={{ padding: "12px 16px", color: "var(--text-mid)", fontWeight: 600, fontSize: 12 }}>Model</th>
                  <th style={{ padding: "12px 16px", color: "var(--text-mid)", fontWeight: 600, fontSize: 12 }}>Intelligence Index</th>
                  <th style={{ padding: "12px 16px", color: "var(--text-mid)", fontWeight: 600, fontSize: 12 }}>Speed (Tok/s)</th>
                  <th style={{ padding: "12px 16px", color: "var(--text-mid)", fontWeight: 600, fontSize: 12 }}>Output / 1M Tok ($)</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((b, i) => (
                  <tr key={b.model_name} style={{ borderBottom: i < rows.length - 1 ? "1px solid var(--line)" : "none" }}>
                    <td style={{ padding: "12px 16px", color: "var(--text-hi)", fontWeight: 500, fontSize: 13 }}>{b.model_name}</td>
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className="mono tnum" style={{ color: "var(--text)", width: 40 }}>
                          {b.intelligence_index !== null ? b.intelligence_index.toFixed(1) : "N/A"}
                        </span>
                        {b.intelligence_index !== null && (
                          <div style={{ width: 100, height: 4, background: "var(--bg-3)", borderRadius: 2 }}>
                            <div style={{ width: `${Math.min(100, b.intelligence_index)}%`, height: "100%", background: "var(--signal)", borderRadius: 2 }} />
                          </div>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span className="mono tnum" style={{ color: "var(--text)" }}>{b.speed_tokens_sec !== null ? Math.round(b.speed_tokens_sec) : "N/A"}</span>
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span className="mono tnum" style={{ color: b.price_per_1m === 0 ? "var(--signal-up)" : "var(--text)" }}>
                        {b.price_per_1m !== null ? (b.price_per_1m === 0 ? "FREE" : `$${b.price_per_1m.toFixed(2)}`) : "N/A"}
                      </span>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan="4" style={{ padding: "36px 16px", textAlign: "center", color: "var(--text-lo)" }}>
                      No models match this filter stack. Loosen a requirement or reset filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

window.BenchmarksView = BenchmarksView;
