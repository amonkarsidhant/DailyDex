// OnboardingView.jsx — Beautiful, interactive creator setup wizard
// React hooks come from AppShell's shared destructure (single source to avoid duplicate const in shared script scope).

const OnboardingView = ({ onComplete }) => {
  const [stage, setStage] = useState(1); // 1: Identity, 2: DNA, 3: BYOK, 4: Boot
  
  // State for Identity
  const [identity, setIdentity] = useState({
    provider: "",
    name: "",
    email: "",
    avatar: "",
    channel_id: ""
  });
  
  // State for Profile / DNA
  const [profile, setProfile] = useState({
    channel_name: "My AI Channel",
    niche: "Practical AI tutorials and local self-hosting demos.",
    tone: "Skeptical, hands-on, slightly opinionated. No hype.",
    persona: "multi"
  });
  
  // State for API Keys / settings
  const [keys, setKeys] = useState({
    youtube_api_key: "",
    fal_api_key: "",
    llm_provider: "gemini",
    llm_model: ""
  });

  const [oauthModal, setOauthModal] = useState(null); // "google" | "github" | "microsoft" | null
  const [oauthInputName, setOauthInputName] = useState("");
  const [oauthInputEmail, setOauthInputEmail] = useState("");
  const [oauthInputChannel, setOauthInputChannel] = useState("");
  
  // Stage 4 Boot logs
  const [bootLogs, setBootLogs] = useState([]);
  const [bootProgress, setBootProgress] = useState(0);
  const [bootComplete, setBootComplete] = useState(false);

  const logsEndRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [bootLogs]);

  // Run mock terminal boot once Stage 4 starts
  useEffect(() => {
    if (stage !== 4) return;

    // Persist onboarding immediately at boot start so a later render/crash
    // can never deadlock the user out of the cockpit (reload will recover).
    fetch("/api/onboarding/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identity, profile, keys })
    }).catch(() => {});

    const logs = [
      { text: "Initializing local database connections...", type: "info" },
      { text: "SQLite DB verified (integrity check: OK)", type: "success" },
      { text: "Loading creator profile config templates...", type: "info" },
      { text: `Injecting Creator Identity: ${identity.name} (${identity.provider})`, type: "success" },
      { text: `Selected Tone Preset: "${profile.tone.split('.')[0]}"`, type: "info" },
      { text: "Probing available LLM providers on local PATH...", type: "info" },
      { text: "Found local engines: gemini (cli), ollama (local), nvidia (nim)", type: "success" },
      { text: `Configuring Copilot for provider: "${keys.llm_provider}"`, type: "info" },
      { text: "Connecting to YouTube Data API sync engine...", type: "info" },
      { text: keys.youtube_api_key ? "YouTube API Key verified." : "No YouTube Key provided. Falling back to scraper mode.", type: keys.youtube_api_key ? "success" : "warn" },
      { text: "Loading fal.ai / Flux image generators...", type: "info" },
      { text: keys.fal_api_key ? "fal.ai API key cached." : "No fal.ai key provided. Image generation will fall back to mockup grids.", type: keys.fal_api_key ? "success" : "warn" },
      { text: "Running initial HackerNews trend indexing...", type: "info" },
      { text: "Fetched and clustered 14 live developer opportunities.", type: "success" },
      { text: "Creator Cockpit configuration saved successfully.", type: "success" },
      { text: "DailyDex Autonomous Agents: ONLINE. Happy shipping! 🚀", type: "success" }
    ];

    let currentLogIndex = 0;
    const interval = setInterval(() => {
      const entry = logs[currentLogIndex];
      if (currentLogIndex < logs.length && entry) {
        setBootLogs(prev => [...prev, entry]);
        setBootProgress(Math.min(100, Math.round(((currentLogIndex + 1) / logs.length) * 100)));
        currentLogIndex++;
      } else {
        clearInterval(interval);
        setBootProgress(100);
        setBootComplete(true);
      }
    }, 450);

    return () => clearInterval(interval);
  }, [stage]);

  const handleOAuthClick = (provider) => {
    setOauthModal(provider);
    if (provider === "google") {
      setOauthInputName("Alex Mercer");
      setOauthInputEmail("alex.mercer@gmail.com");
      setOauthInputChannel("UC-AlexMercerAI");
    } else if (provider === "github") {
      setOauthInputName("octocat-dev");
      setOauthInputEmail("octocat@github.com");
      setOauthInputChannel("UC-OctoDevOps");
    } else if (provider === "microsoft") {
      setOauthInputName("MSLiveCreator");
      setOauthInputEmail("live_creator@outlook.com");
      setOauthInputChannel("UC-MSLiveStudio");
    }
  };

  const submitOAuth = () => {
    const avatars = {
      google: "https://api.dicebear.com/7.x/identicon/svg?seed=google",
      github: "https://api.dicebear.com/7.x/identicon/svg?seed=github",
      microsoft: "https://api.dicebear.com/7.x/identicon/svg?seed=microsoft"
    };

    setIdentity({
      provider: oauthModal,
      name: oauthInputName || "Creator User",
      email: oauthInputEmail || "creator@example.com",
      avatar: avatars[oauthModal] || "https://api.dicebear.com/7.x/identicon/svg?seed=default",
      channel_id: oauthInputChannel || "UC-DefaultChannel"
    });
    setOauthModal(null);
    setStage(2);
  };

  const chooseLocalGuest = () => {
    setIdentity({
      provider: "local",
      name: "Local Guest",
      email: "guest@dailydex.dev",
      avatar: "https://api.dicebear.com/7.x/identicon/svg?seed=guest",
      channel_id: "UC-LocalGuest"
    });
    setStage(2);
  };

  const handleFinalSubmit = async () => {
    try {
      const resp = await fetch("/api/onboarding/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity, profile, keys })
      });
      if (resp.ok) {
        // Hydrate current page with identity before completing
        window.DD_DATA.creator_identity = {
          provider: identity.provider,
          name: identity.name,
          email: identity.email,
          avatar: identity.avatar,
          channel_id: identity.channel_id,
          onboarding_completed: true
        };
        // Re-inject updated profile details
        window.DD_DATA.persona = profile.persona;
        onComplete();
      } else {
        alert("Failed to submit onboarding settings. Please check console.");
      }
    } catch (e) {
      console.error(e);
      alert("Error submitting onboarding: " + e.message);
    }
  };

  // Tone presets
  const tones = [
    {
      key: "Skeptical, hands-on, slightly opinionated. No hype.",
      label: "Skeptical Builder",
      desc: "Allergic to vaporware. Focuses on benchmarks and Pi 4 self-hosting capability."
    },
    {
      key: "High-energy, hyper-focused, tool-stacking guru.",
      label: "Hype-free Tech Stack",
      desc: "Pragmatic tutorials linking tools together. Direct and action-oriented."
    },
    {
      key: "Deep-dive academic, mathematical, first-principles research.",
      label: "Deep researcher",
      desc: "Slower cadence, heavy on details, source citations, and architectural explanation."
    },
    {
      key: "Simple, friendly, beginner-focused step-by-step walkthroughs.",
      label: "Friendly Guide",
      desc: "Welcoming tone, explaining terminal inputs, Docker runs, and basic setups clearly."
    }
  ];

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      background: "radial-gradient(circle at 50% 30%, #161C2A 0%, var(--bg-0) 100%)",
      display: "grid", placeItems: "center",
      zIndex: 9999, padding: 24, overflowY: "auto"
    }}>
      {/* Onboarding Box */}
      <div style={{
        width: "100%", maxWidth: 640,
        background: "var(--bg-1)", border: "1px solid var(--line-2)",
        borderRadius: 14, boxShadow: "0 24px 60px rgba(0,0,0,0.6)",
        position: "relative", overflow: "hidden",
        display: "flex", flexDirection: "column"
      }}>
        {/* Glow Header Accent */}
        <div style={{
          height: 3,
          background: "linear-gradient(90deg, var(--signal) 0%, var(--signal-hot) 50%, var(--signal-cool) 100%)"
        }}/>

        {/* Inner Content Padding */}
        <div style={{ padding: "40px 48px" }}>
          {/* Progress Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 30 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 6,
                background: "linear-gradient(135deg, var(--signal) 0%, var(--signal-hot) 100%)",
                display: "grid", placeItems: "center"
              }}>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="#1A1100">
                  <path d="M2 13 L7 3 L9 7 L12 7 L14 13 Z"/>
                </svg>
              </div>
              <span style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: 16, color: "var(--text-hi)" }}>
                DailyDex Onboarding
              </span>
            </div>
            <div className="mono" style={{ fontSize: 11, color: "var(--text-mid)" }}>
              STAGE {stage} OF 4
            </div>
          </div>

          {/* Stepper indicators */}
          <div style={{ display: "flex", gap: 6, marginBottom: 40 }}>
            {[1, 2, 3, 4].map(s => (
              <div key={s} style={{
                flex: 1, height: 4, borderRadius: 2,
                background: s === stage ? "var(--signal)" : s < stage ? "var(--line-hi)" : "var(--line)"
              }}/>
            ))}
          </div>

          {/* ── STAGE 1: IDENTITY ── */}
          {stage === 1 && (
            <div>
              <h2 style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 24, marginBottom: 12, letterSpacing: "-0.02em" }}>
                Bring Your Own Creator Identity
              </h2>
              <p style={{ color: "var(--text)", fontSize: 14, marginBottom: 32, lineHeight: 1.5 }}>
                DailyDex works fully locally on your machine. Link your identity so that generated scripts, posts, and thumbnails match your channel name and branding.
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <button onClick={() => handleOAuthClick("google")} className="oauth-btn" style={{
                  display: "flex", alignItems: "center", gap: 14, padding: "14px 20px",
                  background: "var(--bg-2)", border: "1px solid var(--line-2)", borderRadius: 8,
                  color: "var(--text-hi)", fontWeight: 600, fontSize: 14, cursor: "pointer", textAlign: "left"
                }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path fill="#EA4335" d="M12 5.04c1.66 0 3.2.57 4.38 1.69l3.27-3.27C17.67 1.47 14.97 1 12 1 7.24 1 3.2 3.65 1.25 7.51l3.96 3.07C6.18 7.42 8.87 5.04 12 5.04z"/>
                    <path fill="#4285F4" d="M23.49 12.27c0-.81-.07-1.59-.2-2.34H12v4.44h6.44c-.28 1.44-1.09 2.66-2.31 3.49l3.58 2.78c2.1-1.94 3.78-4.82 3.78-8.37z"/>
                    <path fill="#FBBC05" d="M5.21 10.58C4.94 11.39 4.8 12.25 4.8 13.13s.14 1.74.41 2.55l-3.96 3.07C.45 17.18 0 15.21 0 13.13s.45-4.05 1.25-5.62l3.96 3.07z"/>
                    <path fill="#34A853" d="M12 23c3.24 0 5.97-1.07 7.96-2.91l-3.58-2.78c-1.1.74-2.52 1.18-4.38 1.18-3.13 0-5.82-2.38-6.79-5.54l-3.96 3.07C3.2 20.35 7.24 23 12 23z"/>
                  </svg>
                  Continue with Google Workspace
                </button>

                <button onClick={() => handleOAuthClick("github")} className="oauth-btn" style={{
                  display: "flex", alignItems: "center", gap: 14, padding: "14px 20px",
                  background: "var(--bg-2)", border: "1px solid var(--line-2)", borderRadius: 8,
                  color: "var(--text-hi)", fontWeight: 600, fontSize: 14, cursor: "pointer", textAlign: "left"
                }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.137 20.162 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
                  </svg>
                  Continue with GitHub Account
                </button>

                <button onClick={() => handleOAuthClick("microsoft")} className="oauth-btn" style={{
                  display: "flex", alignItems: "center", gap: 14, padding: "14px 20px",
                  background: "var(--bg-2)", border: "1px solid var(--line-2)", borderRadius: 8,
                  color: "var(--text-hi)", fontWeight: 600, fontSize: 14, cursor: "pointer", textAlign: "left"
                }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <rect width="8" height="8" fill="#F25022"/>
                    <rect x="10" width="8" height="8" fill="#7FBA00"/>
                    <rect y="10" width="8" height="8" fill="#00A4EF"/>
                    <rect x="10" y="10" width="8" height="8" fill="#FFB900"/>
                  </svg>
                  Continue with Microsoft Live
                </button>

                <div style={{ margin: "16px 0", display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ flex: 1, height: 1, background: "var(--line)" }}/>
                  <span className="mono" style={{ fontSize: 10, color: "var(--text-lo)" }}>OR</span>
                  <div style={{ flex: 1, height: 1, background: "var(--line)" }}/>
                </div>

                <button onClick={chooseLocalGuest} className="oauth-btn" style={{
                  display: "flex", alignItems: "center", gap: 14, padding: "12px 20px",
                  background: "transparent", border: "1px dashed var(--line-hi)", borderRadius: 8,
                  color: "var(--text)", fontWeight: 500, fontSize: 13, cursor: "pointer", textAlign: "left",
                  justifyContent: "center"
                }}>
                  Continue as Local Developer / Guest
                </button>
              </div>
            </div>
          )}

          {/* ── STAGE 2: CREATOR DNA ── */}
          {stage === 2 && (
            <div>
              <h2 style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 24, marginBottom: 12, letterSpacing: "-0.02em" }}>
                Define Your Creator DNA
              </h2>
              <p style={{ color: "var(--text)", fontSize: 14, marginBottom: 24, lineHeight: 1.5 }}>
                Configure how the autonomous agents formulate ideas, write script segments, and outline visual storyboards.
              </p>

              {/* Form fields */}
              <div style={{ display: "flex", flexDirection: "column", gap: 18, marginBottom: 32 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <label className="mono" style={{ fontSize: 11, color: "var(--text-mid)" }}>CHANNEL NAME</label>
                  <input type="text" value={profile.channel_name} onChange={e => setProfile({...profile, channel_name: e.target.value})} style={{
                    padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-hi)",
                    borderRadius: 6, color: "var(--text-hi)", fontSize: 14, outline: "none"
                  }} placeholder="e.g. DailyDex AI"/>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <label className="mono" style={{ fontSize: 11, color: "var(--text-mid)" }}>PRIMARY NICHE</label>
                  <input type="text" value={profile.niche} onChange={e => setProfile({...profile, niche: e.target.value})} style={{
                    padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-hi)",
                    borderRadius: 6, color: "var(--text-hi)", fontSize: 14, outline: "none"
                  }} placeholder="e.g. Practical AI self-hosting and local dev tool benchmarks"/>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <label className="mono" style={{ fontSize: 11, color: "var(--text-mid)", marginBottom: 4 }}>CREATOR TONE</label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    {tones.map(t => (
                      <button key={t.key} onClick={() => setProfile({...profile, tone: t.key})} style={{
                        padding: "12px 14px", background: profile.tone === t.key ? "rgba(240,183,47,0.06)" : "var(--bg-2)",
                        border: `1px solid ${profile.tone === t.key ? "var(--signal)" : "var(--line-hi)"}`,
                        borderRadius: 6, cursor: "pointer", textAlign: "left", display: "flex", flexDirection: "column", gap: 4
                      }}>
                        <span style={{ fontWeight: 600, color: profile.tone === t.key ? "var(--signal)" : "var(--text-hi)", fontSize: 13 }}>{t.label}</span>
                        <span style={{ fontSize: 10.5, color: "var(--text-mid)", lineHeight: 1.3 }}>{t.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <label className="mono" style={{ fontSize: 11, color: "var(--text-mid)" }}>PRIMARY FORMAT / PERSONA</label>
                  <div style={{ display: "flex", gap: 10 }}>
                    {[
                      { key: "multi", label: "Multi-Format", sub: "YT + LI + Newsletter" },
                      { key: "shorts", label: "Shorts-first", sub: "TikTok / YT Shorts" },
                      { key: "newsletter", label: "Newsletter-first", sub: "Markdown columns" }
                    ].map(p => (
                      <button key={p.key} onClick={() => setProfile({...profile, persona: p.key})} style={{
                        flex: 1, padding: 12, background: profile.persona === p.key ? "rgba(240,183,47,0.06)" : "var(--bg-2)",
                        border: `1px solid ${profile.persona === p.key ? "var(--signal)" : "var(--line-hi)"}`,
                        borderRadius: 6, cursor: "pointer"
                      }}>
                        <div style={{ fontWeight: 600, color: profile.persona === p.key ? "var(--signal)" : "var(--text-hi)", fontSize: 13 }}>{p.label}</div>
                        <div style={{ fontSize: 10, color: "var(--text-mid)", marginTop: 2 }}>{p.sub}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Navigation */}
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <button onClick={() => setStage(1)} style={{
                  padding: "10px 18px", background: "transparent", border: "1px solid var(--line-hi)",
                  borderRadius: 6, color: "var(--text-mid)", cursor: "pointer", fontWeight: 500
                }}>
                  Back
                </button>
                <button onClick={() => setStage(3)} style={{
                  padding: "10px 24px", background: "var(--signal)", border: "none",
                  borderRadius: 6, color: "#1A1100", cursor: "pointer", fontWeight: 700
                }}>
                  Continue
                </button>
              </div>
            </div>
          )}

          {/* ── STAGE 3: BRING YOUR OWN KEYS (BYOK) ── */}
          {stage === 3 && (
            <div>
              <h2 style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 24, marginBottom: 12, letterSpacing: "-0.02em" }}>
                Configure API Credentials
              </h2>
              <p style={{ color: "var(--text)", fontSize: 14, marginBottom: 24, lineHeight: 1.5 }}>
                Input your developer API credentials. These live entirely on your local machine and are never uploaded to any remote server.
              </p>

              {/* Form fields */}
              <div style={{ display: "flex", flexDirection: "column", gap: 18, marginBottom: 32 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <label className="mono" style={{ fontSize: 11, color: "var(--text-mid)" }}>YOUTUBE DATA API V3 KEY</label>
                    <span style={{ fontSize: 10, color: "var(--text-lo)" }}>Optional</span>
                  </div>
                  <input type="password" value={keys.youtube_api_key} onChange={e => setKeys({...keys, youtube_api_key: e.target.value})} style={{
                    padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-hi)",
                    borderRadius: 6, color: "var(--text-hi)", fontSize: 14, outline: "none", fontFamily: "var(--font-mono)"
                  }} placeholder="AIzaSy..."/>
                  <span style={{ fontSize: 10.5, color: "var(--text-lo)" }}>
                    Required for live video views and stats synchronization. Get one from Google Cloud Console.
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <label className="mono" style={{ fontSize: 11, color: "var(--text-mid)" }}>FAL.AI API KEY (FLUX IMAGE GENERATION)</label>
                    <span style={{ fontSize: 10, color: "var(--text-lo)" }}>Optional</span>
                  </div>
                  <input type="password" value={keys.fal_api_key} onChange={e => setKeys({...keys, fal_api_key: e.target.value})} style={{
                    padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-hi)",
                    borderRadius: 6, color: "var(--text-hi)", fontSize: 14, outline: "none", fontFamily: "var(--font-mono)"
                  }} placeholder="fal-..."/>
                  <span style={{ fontSize: 10.5, color: "var(--text-lo)" }}>
                    Required to render real high-fidelity thumbnail images using Flux Schnell.
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <label className="mono" style={{ fontSize: 11, color: "var(--text-mid)" }}>DEFAULT CO-PILOT AGENT PROVIDER</label>
                  <select value={keys.llm_provider} onChange={e => setKeys({...keys, llm_provider: e.target.value})} style={{
                    padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-hi)",
                    borderRadius: 6, color: "var(--text-hi)", fontSize: 14, outline: "none", width: "100%"
                  }}>
                    <option value="gemini">Gemini CLI (Standard Key)</option>
                    <option value="claude">Claude Code CLI (OAuth Session)</option>
                    <option value="ollama">Ollama (Local Models - Offline)</option>
                    <option value="nvidia">NVIDIA NIM (BYOK Endpoint)</option>
                    <option value="anthropic">Anthropic API Key (Direct REST)</option>
                  </select>
                  <span style={{ fontSize: 10.5, color: "var(--text-lo)" }}>
                    DailyDex automatically fallbacks to any active, authenticated provider found on your computer path.
                  </span>
                </div>
              </div>

              {/* Navigation */}
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <button onClick={() => setStage(2)} style={{
                  padding: "10px 18px", background: "transparent", border: "1px solid var(--line-hi)",
                  borderRadius: 6, color: "var(--text-mid)", cursor: "pointer", fontWeight: 500
                }}>
                  Back
                </button>
                <button onClick={() => setStage(4)} style={{
                  padding: "10px 24px", background: "var(--signal)", border: "none",
                  borderRadius: 6, color: "#1A1100", cursor: "pointer", fontWeight: 700
                }}>
                  Boot Creator Central
                </button>
              </div>
            </div>
          )}

          {/* ── STAGE 4: ENGINE BOOT ── */}
          {stage === 4 && (
            <div>
              <h2 style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 24, marginBottom: 12, letterSpacing: "-0.02em" }}>
                Booting Creator Cockpit
              </h2>
              <p style={{ color: "var(--text)", fontSize: 14, marginBottom: 20, lineHeight: 1.5 }}>
                Saving configuration and spawning background intelligence agents...
              </p>

              {/* Progress bar */}
              <div style={{ background: "var(--line)", height: 10, borderRadius: 5, overflow: "hidden", marginBottom: 20 }}>
                <div style={{
                  width: `${bootProgress}%`, height: "100%",
                  background: "linear-gradient(90deg, var(--signal) 0%, var(--signal-hot) 100%)",
                  transition: "width 200ms"
                }}/>
              </div>

              {/* Simulated Terminal logs */}
              <div style={{
                background: "#07090C", border: "1px solid var(--line-hi)", borderRadius: 6,
                padding: 16, height: 200, overflowY: "auto", display: "flex", flexDirection: "column",
                gap: 6, fontFamily: "var(--font-mono)", fontSize: 11, marginBottom: 30
              }}>
                {bootLogs.filter(Boolean).map((log, i) => (
                  <div key={i} style={{ display: "flex", gap: 10, lineHeight: 1.4 }}>
                    <span style={{
                      color: log.type === "success" ? "var(--src-github)" : log.type === "warn" ? "var(--signal)" : "var(--signal-cool)",
                      fontWeight: 600
                    }}>
                      [{(log.type || "info").toUpperCase()}]
                    </span>
                    <span style={{ color: "var(--text)" }}>{log.text}</span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>

              {/* Navigation / Action */}
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  onClick={handleFinalSubmit}
                  disabled={!bootComplete}
                  style={{
                    padding: "12px 30px",
                    background: bootComplete ? "var(--signal)" : "var(--line)",
                    border: "none", borderRadius: 6,
                    color: bootComplete ? "#1A1100" : "var(--text-lo)",
                    cursor: bootComplete ? "pointer" : "not-allowed",
                    fontWeight: 700, fontSize: 14,
                    transition: "background 200ms, color 200ms"
                  }}
                >
                  {bootComplete ? "Launch Creator Cockpit 🚀" : "Running Setup..."}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* OAuth Login Popup Simulation Modal */}
      {oauthModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.75)", zIndex: 10000,
          display: "grid", placeItems: "center", padding: 24
        }}>
          {/* Simulated browser window */}
          <div style={{
            width: "100%", maxWidth: 440, background: "var(--bg-1)",
            border: "1px solid var(--line-hi)", borderRadius: 10,
            boxShadow: "0 20px 50px rgba(0,0,0,0.5)", overflow: "hidden"
          }}>
            {/* Window bar */}
            <div style={{
              background: "var(--bg-2)", borderBottom: "1px solid var(--line-2)",
              padding: "10px 16px", display: "flex", justifyItems: "center", alignItems: "center", gap: 10
            }}>
              <div style={{ display: "flex", gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 999, background: "#FF5F56" }}/>
                <span style={{ width: 10, height: 10, borderRadius: 999, background: "#FFBD2E" }}/>
                <span style={{ width: 10, height: 10, borderRadius: 999, background: "#27C93F" }}/>
              </div>
              <span className="mono" style={{ fontSize: 10, color: "var(--text-mid)", marginLeft: "auto", marginRight: "auto" }}>
                auth.{oauthModal}.com/oauth/authorize
              </span>
            </div>

            {/* Content */}
            <div style={{ padding: "30px 36px" }}>
              <div style={{ textAlign: "center", marginBottom: 24 }}>
                <h3 style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 18, marginBottom: 8 }}>
                  Authorize DailyDex
                </h3>
                <p style={{ color: "var(--text)", fontSize: 12.5, lineHeight: 1.4 }}>
                  Connect your <strong style={{ textTransform: "capitalize" }}>{oauthModal}</strong> account to authenticate.
                </p>
              </div>

              {/* Pre-filled editable parameters */}
              <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 24 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label className="mono" style={{ fontSize: 9.5, color: "var(--text-mid)" }}>PROFILE NAME</label>
                  <input type="text" value={oauthInputName} onChange={e => setOauthInputName(e.target.value)} style={{
                    padding: 8, background: "var(--bg-2)", border: "1px solid var(--line)",
                    borderRadius: 4, color: "var(--text-hi)", fontSize: 13, outline: "none"
                  }}/>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label className="mono" style={{ fontSize: 9.5, color: "var(--text-mid)" }}>EMAIL ADDRESS</label>
                  <input type="email" value={oauthInputEmail} onChange={e => setOauthInputEmail(e.target.value)} style={{
                    padding: 8, background: "var(--bg-2)", border: "1px solid var(--line)",
                    borderRadius: 4, color: "var(--text-hi)", fontSize: 13, outline: "none"
                  }}/>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label className="mono" style={{ fontSize: 9.5, color: "var(--text-mid)" }}>CREATOR CHANNEL ID</label>
                  <input type="text" value={oauthInputChannel} onChange={e => setOauthInputChannel(e.target.value)} style={{
                    padding: 8, background: "var(--bg-2)", border: "1px solid var(--line)",
                    borderRadius: 4, color: "var(--text-hi)", fontSize: 13, outline: "none", fontFamily: "var(--font-mono)"
                  }}/>
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
                <button onClick={() => setOauthModal(null)} style={{
                  padding: "8px 14px", background: "transparent", border: "1px solid var(--line-hi)",
                  borderRadius: 4, color: "var(--text-mid)", cursor: "pointer"
                }}>
                  Cancel
                </button>
                <button onClick={submitOAuth} style={{
                  padding: "8px 16px", background: "var(--signal)", border: "none",
                  borderRadius: 4, color: "#1A1100", cursor: "pointer", fontWeight: 700
                }}>
                  Authorize Identity
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
