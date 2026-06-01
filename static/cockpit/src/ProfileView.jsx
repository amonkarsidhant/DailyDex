// ProfileView.jsx — Creator Profile & Brand Voice Configuration Panel
// Allows creators to configure tone, audience, perspective, banned words, format boundaries, and schedule.

const { useState, useEffect } = React;

const ProfileView = () => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState({ text: "", ok: true });
  
  // Temporary state for tag lists and angle inputs
  const [newBanned, setNewBanned] = useState("");
  const [newPreferred, setNewPreferred] = useState("");
  const [newAngle, setNewAngle] = useState("");

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const res = await fetch("/api/profile");
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
      } else {
        setMsg({ text: "Failed to load creator profile from backend", ok: false });
      }
    } catch (e) {
      setMsg({ text: `Connection error: ${e.message}`, ok: false });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!profile) return;
    setSaving(true);
    setMsg({ text: "", ok: true });
    try {
      const res = await fetch("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      if (res.ok) {
        setMsg({ text: "✓ Brand profile updated and saved successfully", ok: true });
        // Also reload global window data if available
        if (window.DD_DATA) {
          window.DD_DATA.profile = profile;
        }
      } else {
        setMsg({ text: "Failed to update profile", ok: false });
      }
    } catch (e) {
      setMsg({ text: `Error saving: ${e.message}`, ok: false });
    } finally {
      setSaving(false);
    }
  };

  const updateField = (key, val) => {
    setProfile(p => ({ ...p, [key]: val }));
  };

  const updateNestedField = (parent, key, val) => {
    setProfile(p => ({
      ...p,
      [parent]: {
        ...p[parent],
        [key]: val
      }
    }));
  };

  // Add/Remove helper routines
  const addTag = (field, tag, setter) => {
    const trimmed = tag.trim().toLowerCase();
    if (!trimmed) return;
    if (profile[field].includes(trimmed)) {
      setter("");
      return;
    }
    updateField(field, [...profile[field], trimmed]);
    setter("");
  };

  const removeTag = (field, tag) => {
    updateField(field, profile[field].filter(t => t !== tag));
  };

  const addAngle = () => {
    const trimmed = newAngle.trim();
    if (!trimmed) return;
    if (profile.signature_angles.includes(trimmed)) {
      setNewAngle("");
      return;
    }
    updateField("signature_angles", [...profile.signature_angles, trimmed]);
    setNewAngle("");
  };

  const removeAngle = (angle) => {
    updateField("signature_angles", profile.signature_angles.filter(a => a !== angle));
  };

  const togglePublishDay = (day) => {
    const current = profile.schedule?.publish_days || [];
    const next = current.includes(day)
      ? current.filter(d => d !== day)
      : [...current, day];
    updateNestedField("schedule", "publish_days", next);
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh", color: "var(--text-mid)" }}>
        <div className="blink mono" style={{ fontSize: 13 }}>LOADING PROFILE SPECIFICATION...</div>
      </div>
    );
  }

  if (!profile) return null;

  const weekDays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div style={{ maxWidth: 840, margin: "0 auto", padding: "24px 20px", display: "flex", flexDirection: "column", gap: 24 }}>
      
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div>
          <div style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 20, letterSpacing: "-0.02em" }}>
            👤 Brand Identity & Profile
          </div>
          <div style={{ color: "var(--text-lo)", fontSize: 13, marginTop: 4, lineHeight: 1.4 }}>
            Fine-tune your channel identity, style templates, formatting guidelines, and scheduling rules. This configuration controls the tone and structure of all generated scripts.
          </div>
        </div>
        <button
          className="btn primary"
          onClick={handleSave}
          disabled={saving}
          style={{ flexShrink: 0, background: "linear-gradient(90deg, var(--signal), var(--signal-hot))", border: "none", color: "#1a1100", fontWeight: 700 }}
        >
          {saving ? "Saving Changes…" : "💾 Save Brand Profile"}
        </button>
      </div>

      {/* Message feedback */}
      {msg.text && (
        <div style={{
          padding: "10px 14px", borderRadius: 6,
          background: msg.ok ? "rgba(124,255,178,0.08)" : "rgba(255,100,100,0.08)",
          border: `1px solid ${msg.ok ? "rgba(124,255,178,0.3)" : "rgba(255,100,100,0.3)"}`,
          color: msg.ok ? "var(--signal-up)" : "var(--signal-down)",
          fontSize: 13,
        }}>
          {msg.text}
        </div>
      )}

      {/* Profile Sections */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20 }}>
        
        {/* Component 1: Brand & Bio */}
        <div className="panel" style={{ background: "var(--bg-1)", border: "1px solid var(--line)" }}>
          <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
            <div style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 14 }}>📡 Core Channel Meta</div>
            <div style={{ color: "var(--text-lo)", fontSize: 11.5, marginTop: 2 }}>Define the main name, target audience, and style positioning.</div>
          </div>
          <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Channel Name</label>
                <input
                  type="text"
                  value={profile.channel_name || ""}
                  onChange={e => updateField("channel_name", e.target.value)}
                  style={{ width: "100%", height: 36, padding: "0 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5 }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Niche Focus</label>
                <input
                  type="text"
                  value={profile.niche || ""}
                  onChange={e => updateField("niche", e.target.value)}
                  style={{ width: "100%", height: 36, padding: "0 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5 }}
                />
              </div>
            </div>
            <div>
              <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Target Audience Description</label>
              <textarea
                value={profile.audience || ""}
                onChange={e => updateField("audience", e.target.value)}
                rows={3}
                style={{ width: "100%", padding: "10px 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5, fontFamily: "var(--font-sans)", resize: "vertical" }}
              />
            </div>
            <div>
              <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Channel Tone & Personality</label>
              <textarea
                value={profile.tone || ""}
                onChange={e => updateField("tone", e.target.value)}
                rows={2}
                style={{ width: "100%", padding: "10px 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5, fontFamily: "var(--font-sans)", resize: "vertical" }}
              />
            </div>
            <div>
              <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Perspective (POV Structure)</label>
              <textarea
                value={profile.perspective || ""}
                onChange={e => updateField("perspective", e.target.value)}
                rows={2}
                style={{ width: "100%", padding: "10px 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5, fontFamily: "var(--font-sans)", resize: "vertical" }}
              />
            </div>
          </div>
        </div>

        {/* Component 2: Tone & Words filter */}
        <div className="panel" style={{ background: "var(--bg-1)", border: "1px solid var(--line)" }}>
          <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
            <div style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 14 }}>🛑 Word Filters & Vocabulary</div>
            <div style={{ color: "var(--text-lo)", fontSize: 11.5, marginTop: 2 }}>Keep scripts aligned with your brand vocabulary and ban generic marketing hype.</div>
          </div>
          <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: 16 }}>
            
            {/* Preferred Words */}
            <div>
              <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Preferred Brand Words</label>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <input
                  type="text"
                  placeholder="e.g. ship, local, self-host"
                  value={newPreferred}
                  onChange={e => setNewPreferred(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addTag("preferred_words", newPreferred, setNewPreferred); } }}
                  style={{ flex: 1, height: 36, padding: "0 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5 }}
                />
                <button className="btn" onClick={() => addTag("preferred_words", newPreferred, setNewPreferred)}>Add</button>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(profile.preferred_words || []).map(word => (
                  <span key={word} className="chip" style={{ color: "var(--signal-up)", borderColor: "rgba(124,255,178,0.2)", padding: "4px 10px", display: "inline-flex", alignItems: "center", gap: 6 }}>
                    {word}
                    <span onClick={() => removeTag("preferred_words", word)} style={{ cursor: "pointer", color: "var(--text-lo)", fontWeight: "bold" }}>×</span>
                  </span>
                ))}
                {(!profile.preferred_words || profile.preferred_words.length === 0) && (
                  <div style={{ fontSize: 11, color: "var(--text-lo)", fontStyle: "italic" }}>No preferred words defined</div>
                )}
              </div>
            </div>

            {/* Banned Phrases */}
            <div>
              <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Banned Phrases (Hype Filter)</label>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <input
                  type="text"
                  placeholder="e.g. game changer, mind-blowing, AI is taking over"
                  value={newBanned}
                  onChange={e => setNewBanned(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addTag("banned_phrases", newBanned, setNewBanned); } }}
                  style={{ flex: 1, height: 36, padding: "0 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5 }}
                />
                <button className="btn" onClick={() => addTag("banned_phrases", newBanned, setNewBanned)}>Add</button>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(profile.banned_phrases || []).map(phrase => (
                  <span key={phrase} className="chip" style={{ color: "var(--signal-down)", borderColor: "rgba(255,107,107,0.2)", padding: "4px 10px", display: "inline-flex", alignItems: "center", gap: 6 }}>
                    {phrase}
                    <span onClick={() => removeTag("banned_phrases", phrase)} style={{ cursor: "pointer", color: "var(--text-lo)", fontWeight: "bold" }}>×</span>
                  </span>
                ))}
                {(!profile.banned_phrases || profile.banned_phrases.length === 0) && (
                  <div style={{ fontSize: 11, color: "var(--text-lo)", fontStyle: "italic" }}>No banned phrases defined</div>
                )}
              </div>
            </div>

          </div>
        </div>

        {/* Component 3: Signature Angles */}
        <div className="panel" style={{ background: "var(--bg-1)", border: "1px solid var(--line)" }}>
          <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
            <div style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 14 }}>📐 Signature Editorial Angles</div>
            <div style={{ color: "var(--text-lo)", fontSize: 11.5, marginTop: 2 }}>Core structural lenses used to analyze stories and form script scripts.</div>
          </div>
          <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                placeholder="e.g. Does it actually run on a Pi 4? or Hype vs Real Benchmark"
                value={newAngle}
                onChange={e => setNewAngle(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addAngle(); } }}
                style={{ flex: 1, height: 36, padding: "0 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5 }}
              />
              <button className="btn" onClick={addAngle}>Add Angle</button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {(profile.signature_angles || []).map((angle, index) => (
                <div key={index} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, alignItems: "center", padding: "8px 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5 }}>
                  <span style={{ fontSize: 12.5, color: "var(--text-hi)" }}>{angle}</span>
                  <button className="btn ghost" onClick={() => removeAngle(angle)} style={{ padding: "2px 6px", border: "none", color: "var(--text-lo)" }}>✕</button>
                </div>
              ))}
              {(!profile.signature_angles || profile.signature_angles.length === 0) && (
                <div style={{ fontSize: 11, color: "var(--text-lo)", fontStyle: "italic", textAlign: "center", padding: "10px 0" }}>No signature angles specified.</div>
              )}
            </div>
          </div>
        </div>

        {/* Component 4: Format Limits & Schedule */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          
          <div className="panel" style={{ background: "var(--bg-1)", border: "1px solid var(--line)" }}>
            <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
              <div style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 14 }}>⚙ Format Boundaries</div>
            </div>
            <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, marginBottom: 4 }}>Title characters (Min / Max)</label>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <input
                    type="number"
                    value={profile.format_rules?.title_min_chars || 30}
                    onChange={e => updateNestedField("format_rules", "title_min_chars", parseInt(e.target.value) || 0)}
                    style={{ width: "100%", height: 32, padding: "0 8px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 4, color: "var(--text-hi)", fontFamily: "var(--font-mono)", fontSize: 12 }}
                  />
                  <span style={{ color: "var(--text-lo)" }}>—</span>
                  <input
                    type="number"
                    value={profile.format_rules?.title_max_chars || 60}
                    onChange={e => updateNestedField("format_rules", "title_max_chars", parseInt(e.target.value) || 0)}
                    style={{ width: "100%", height: 32, padding: "0 8px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 4, color: "var(--text-hi)", fontFamily: "var(--font-mono)", fontSize: 12 }}
                  />
                </div>
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, marginBottom: 4 }}>Hook character length (Max)</label>
                <input
                  type="number"
                  value={profile.format_rules?.hook_max_chars || 140}
                  onChange={e => updateNestedField("format_rules", "hook_max_chars", parseInt(e.target.value) || 0)}
                  style={{ width: "100%", height: 32, padding: "0 8px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 4, color: "var(--text-hi)", fontFamily: "var(--font-mono)", fontSize: 12 }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, marginBottom: 4 }}>Short Script seconds (Min / Max)</label>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <input
                    type="number"
                    value={profile.format_rules?.short_script_min_seconds || 25}
                    onChange={e => updateNestedField("format_rules", "short_script_min_seconds", parseInt(e.target.value) || 0)}
                    style={{ width: "100%", height: 32, padding: "0 8px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 4, color: "var(--text-hi)", fontFamily: "var(--font-mono)", fontSize: 12 }}
                  />
                  <span style={{ color: "var(--text-lo)" }}>—</span>
                  <input
                    type="number"
                    value={profile.format_rules?.short_script_max_seconds || 60}
                    onChange={e => updateNestedField("format_rules", "short_script_max_seconds", parseInt(e.target.value) || 0)}
                    style={{ width: "100%", height: 32, padding: "0 8px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 4, color: "var(--text-hi)", fontFamily: "var(--font-mono)", fontSize: 12 }}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="panel" style={{ background: "var(--bg-1)", border: "1px solid var(--line)" }}>
            <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
              <div style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 14 }}>📅 Publishing Calendar</div>
            </div>
            <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, marginBottom: 6, textTransform: "uppercase" }}>Publish Days</label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {weekDays.map(day => {
                    const isSelected = (profile.schedule?.publish_days || []).includes(day);
                    return (
                      <button
                        key={day}
                        onClick={() => togglePublishDay(day)}
                        style={{
                          padding: "6px 10px", borderRadius: 4,
                          background: isSelected ? "rgba(240,183,47,0.12)" : "var(--bg-0)",
                          border: `1px solid ${isSelected ? "var(--signal)" : "var(--line-2)"}`,
                          color: isSelected ? "var(--signal)" : "var(--text)",
                          cursor: "pointer", fontSize: 11, fontFamily: "var(--font-mono)",
                        }}
                      >
                        {day}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 4 }}>
                <div>
                  <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, marginBottom: 4 }}>Recording Window</label>
                  <input
                    type="text"
                    placeholder="e.g. 10:00-12:00"
                    value={profile.schedule?.preferred_record_window || ""}
                    onChange={e => updateNestedField("schedule", "preferred_record_window", e.target.value)}
                    style={{ width: "100%", height: 32, padding: "0 8px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 4, color: "var(--text-hi)", fontFamily: "var(--font-mono)", fontSize: 12 }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, marginBottom: 4 }}>Social Posting Time</label>
                  <input
                    type="text"
                    placeholder="e.g. 10:00"
                    value={profile.schedule?.linkedin_time || ""}
                    onChange={e => updateNestedField("schedule", "linkedin_time", e.target.value)}
                    style={{ width: "100%", height: 32, padding: "0 8px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 4, color: "var(--text-hi)", fontFamily: "var(--font-mono)", fontSize: 12 }}
                  />
                </div>
              </div>
            </div>
          </div>

        </div>

        {/* Component 5: AI Providers Unification */}
        <div className="panel" style={{ background: "var(--bg-1)", border: "1px solid var(--line)" }}>
          <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)", background: "var(--bg-2)" }}>
            <div style={{ color: "var(--text-hi)", fontWeight: 700, fontSize: 14 }}>🤖 Unified AI Copilot & Generation Provider</div>
            <div style={{ color: "var(--text-lo)", fontSize: 11.5, marginTop: 2 }}>Specify the provider and models used by both your Copilot strategist and content Factory script-writers.</div>
          </div>
          <div style={{ padding: "18px", display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Primary Provider</label>
                <select
                  value={profile.copilot?.provider || ""}
                  onChange={e => updateNestedField("copilot", "provider", e.target.value)}
                  style={{ width: "100%", height: 36, padding: "0 10px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5, fontFamily: "var(--font-mono)" }}
                >
                  <option value="gemini">gemini (Local CLI)</option>
                  <option value="claude">claude (Claude Code CLI)</option>
                  <option value="ollama">ollama (Local API)</option>
                  <option value="nvidia">nvidia (NVIDIA NIM)</option>
                  <option value="openai">openai (OpenAI API)</option>
                  <option value="anthropic">anthropic (Anthropic API)</option>
                  <option value="opencode">opencode (Free Models CLI)</option>
                </select>
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Primary Model</label>
                <input
                  type="text"
                  value={profile.copilot?.model || ""}
                  placeholder="e.g. stepfun-ai/step-3.5-flash or llama3"
                  onChange={e => updateNestedField("copilot", "model", e.target.value)}
                  style={{ width: "100%", height: 36, padding: "0 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5, fontFamily: "var(--font-mono)" }}
                />
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Fallback Model</label>
                <input
                  type="text"
                  value={profile.copilot?.fallback_model || ""}
                  placeholder="e.g. minimaxai/minimax-m2.7"
                  onChange={e => updateNestedField("copilot", "fallback_model", e.target.value)}
                  style={{ width: "100%", height: 36, padding: "0 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5, fontFamily: "var(--font-mono)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-mid)", fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>Max Context Tokens</label>
                <input
                  type="number"
                  value={profile.copilot?.max_tokens || 1000}
                  onChange={e => updateNestedField("copilot", "max_tokens", parseInt(e.target.value) || 1000)}
                  style={{ width: "100%", height: 36, padding: "0 12px", background: "var(--bg-0)", border: "1px solid var(--line-2)", borderRadius: 5, color: "var(--text-hi)", fontSize: 12.5, fontFamily: "var(--font-mono)" }}
                />
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

Object.assign(window, { ProfileView });
