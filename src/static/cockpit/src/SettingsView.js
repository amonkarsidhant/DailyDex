// SettingsView.jsx — BYOK Settings Panel
// Lets creators plug in their own API keys for YouTube analytics and Flux image gen.
// LLM provider configuration (gemini / claude / ollama / openai / nvidia).
// Keys are stored locally on the server (never shipped to any cloud).

const SettingsView = () => {
  const [schema, setSchema] = React.useState({});
  const [values, setValues] = React.useState({});
  const [draft, setDraft] = React.useState({});
  const [saving, setSaving] = React.useState(false);
  const [validating, setValidating] = React.useState({});
  const [validation, setValidation] = React.useState({});
  const [providerInfo, setProviderInfo] = React.useState(null);
  const [msg, setMsg] = React.useState({
    text: "",
    ok: true
  });
  const [showSecret, setShowSecret] = React.useState({});
  const [identity, setIdentity] = React.useState(window.DD_DATA?.creator_identity || {});
  const handleResetOnboarding = async () => {
    if (!confirm("Are you sure you want to sign out and reset your creator onboarding? This will clear your linked identity and restart the wizard.")) return;
    try {
      const resp = await fetch("/api/onboarding/reset", {
        method: "POST"
      });
      if (resp.ok) {
        window.location.reload();
      } else {
        alert("Failed to reset onboarding");
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  };
  React.useEffect(() => {
    loadSettings();
    loadProviderInfo();
  }, []);
  const loadSettings = async () => {
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const data = await res.json();
        setSchema(data.schema || {});
        setValues(data.values || {});
      }
    } catch (e) {
      console.error("Failed to load settings", e);
    }
  };
  const loadProviderInfo = async () => {
    try {
      const res = await fetch("/api/settings/provider-info");
      if (res.ok) setProviderInfo(await res.json());
    } catch (_) {}
  };
  const handleChange = (key, val) => {
    setDraft(d => ({
      ...d,
      [key]: val
    }));
    setValidation(v => ({
      ...v,
      [key]: null
    }));
  };
  const handleSave = async () => {
    if (!Object.keys(draft).length) return;
    setSaving(true);
    setMsg({
      text: "",
      ok: true
    });
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(draft)
      });
      if (res.ok) {
        const data = await res.json();
        setValues(data.settings?.values || {});
        setDraft({});
        setMsg({
          text: "✓ Settings saved to ~/.dailydex/settings.json",
          ok: true
        });
      } else {
        setMsg({
          text: "Failed to save settings",
          ok: false
        });
      }
    } catch (e) {
      setMsg({
        text: `Error: ${e.message}`,
        ok: false
      });
    } finally {
      setSaving(false);
    }
  };
  const handleValidate = async type => {
    const keyName = type === "youtube" ? "youtube_api_key" : "fal_api_key";
    const apiKey = draft[keyName] || "";
    if (!apiKey || apiKey.startsWith("****")) {
      setMsg({
        text: `Enter a new ${type} key before validating`,
        ok: false
      });
      return;
    }
    setValidating(v => ({
      ...v,
      [type]: true
    }));
    setValidation(v => ({
      ...v,
      [keyName]: null
    }));
    try {
      const res = await fetch(`/api/settings/validate/${type}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          api_key: apiKey
        })
      });
      const result = await res.json();
      setValidation(v => ({
        ...v,
        [keyName]: result
      }));
    } catch (e) {
      setValidation(v => ({
        ...v,
        [keyName]: {
          ok: false,
          error: e.message
        }
      }));
    } finally {
      setValidating(v => ({
        ...v,
        [type]: false
      }));
    }
  };
  const handleDelete = async key => {
    if (!confirm(`Remove saved "${schema[key]?.label}" key? (env var override will still apply)`)) return;
    try {
      await fetch(`/api/settings/${key}`, {
        method: "DELETE"
      });
      await loadSettings();
      setMsg({
        text: `✓ "${schema[key]?.label}" removed from local settings`,
        ok: true
      });
    } catch (e) {
      setMsg({
        text: `Error removing key: ${e.message}`,
        ok: false
      });
    }
  };
  const toggleShow = key => setShowSecret(s => ({
    ...s,
    [key]: !s[key]
  }));
  const hasDraft = Object.keys(draft).length > 0;

  // Group keys by schema group
  const groups = {};
  Object.entries(schema).forEach(([key, meta]) => {
    const g = meta.group || "other";
    if (!groups[g]) groups[g] = [];
    groups[g].push({
      key,
      meta
    });
  });
  const GROUP_META = {
    youtube: {
      label: "YouTube Analytics",
      icon: "▶",
      color: "#FF0000",
      desc: "Connect your YouTube Data API v3 key to pull real view counts instead of HTML scraping. Free: 10,000 units/day."
    },
    image_gen: {
      label: "Image Generation (Flux)",
      icon: "🖼",
      color: "#8B5CF6",
      desc: "Connect your fal.ai key to generate real thumbnail JPEGs instead of text descriptions. ~$0.003/image via Flux Schnell."
    },
    llm: {
      label: "LLM Provider (AI Engine)",
      icon: "⚡",
      color: "var(--signal)",
      desc: "Configure which AI model powers your creator agents. BYOK: OpenAI, Anthropic, NVIDIA NIM, or use free local options (Gemini CLI, Claude CLI, Ollama)."
    }
  };
  const LLM_PROVIDER_DOCS = {
    gemini: {
      free: true,
      note: "Requires `gemini` CLI installed. Uses your Google account.",
      setup: "Install: https://github.com/google-gemini/gemini-cli"
    },
    claude: {
      free: true,
      note: "Requires `claude` CLI (Claude Code) installed. Uses your Anthropic account.",
      setup: "Install: npm install -g @anthropic-ai/claude-code"
    },
    opencode: {
      free: true,
      note: "Requires `opencode` CLI installed.",
      setup: "Install: https://opencode.dev"
    },
    hermes: {
      free: true,
      note: "Requires `hermes` CLI installed.",
      setup: "Install: hermes binary"
    },
    kilocode: {
      free: true,
      note: "Requires Kilocode CLI (kilo) installed.",
      setup: "Install: npm install -g @kilocode/cli"
    },
    agy: {
      free: true,
      note: "Requires Google Antigravity CLI (agy) installed.",
      setup: "Install: agy install"
    },
    ollama: {
      free: true,
      note: "Requires Ollama running locally. 100% private, no API costs.",
      setup: "Install: https://ollama.ai → pull phi3:mini or llama3"
    },
    nvidia: {
      free: false,
      note: "NVIDIA NIM API (build.nvidia.com). Requires API key.",
      setup: "Get key: https://build.nvidia.com"
    },
    openai: {
      free: false,
      note: "OpenAI API. Requires API key (sk-...).",
      setup: "Get key: https://platform.openai.com/api-keys"
    },
    anthropic: {
      free: false,
      note: "Anthropic API. Requires API key.",
      setup: "Get key: https://console.anthropic.com"
    }
  };
  const currentProvider = draft["llm_provider"] || values["llm_provider"]?.value || "gemini";
  const currentMode = draft["deployment_mode"] || values["deployment_mode"]?.value || "cli";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 780,
      margin: "0 auto",
      padding: "24px 20px",
      display: "flex",
      flexDirection: "column",
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-start",
      justifyContent: "space-between",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontWeight: 700,
      fontSize: 20,
      letterSpacing: "-0.02em"
    }
  }, "\uD83D\uDD11 Creator Settings"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-lo)",
      fontSize: 13,
      marginTop: 4,
      lineHeight: 1.4
    }
  }, "Bring your own keys. Stored locally in ", /*#__PURE__*/React.createElement("code", {
    style: {
      background: "var(--bg-2)",
      padding: "1px 5px",
      borderRadius: 3,
      fontSize: 11
    }
  }, "~/.dailydex/settings.json"), " \u2014 never sent to any cloud.")), hasDraft && /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: handleSave,
    disabled: saving,
    style: {
      flexShrink: 0,
      background: "linear-gradient(90deg, var(--signal), var(--signal-hot))",
      border: "none",
      color: "#1a1100",
      fontWeight: 700
    }
  }, saving ? "Saving…" : "💾 Save Changes")), msg.text && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 14px",
      borderRadius: 6,
      background: msg.ok ? "rgba(124,255,178,0.08)" : "rgba(255,100,100,0.08)",
      border: `1px solid ${msg.ok ? "rgba(124,255,178,0.3)" : "rgba(255,100,100,0.3)"}`,
      color: msg.ok ? "var(--signal-up)" : "var(--signal-down)",
      fontSize: 13
    }
  }, msg.text), providerInfo && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "12px 16px",
      background: "linear-gradient(135deg, rgba(240,183,47,0.06) 0%, rgba(20,15,10,0.4) 100%)",
      border: "1px solid rgba(240,183,47,0.2)",
      borderRadius: 8,
      display: "flex",
      alignItems: "center",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 20
    }
  }, "\u26A1"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--text-lo)"
    }
  }, "Currently active AI engine"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontWeight: 600,
      fontSize: 14,
      marginTop: 2
    }
  }, providerInfo.provider?.toUpperCase(), " \xB7 ", providerInfo.model || "default"), providerInfo.note && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "var(--text-lo)",
      marginTop: 2
    }
  }, providerInfo.note)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "4px 10px",
      borderRadius: 999,
      fontSize: 11,
      fontFamily: "var(--font-mono)",
      background: providerInfo.has_key ? "rgba(124,255,178,0.1)" : "rgba(240,183,47,0.1)",
      color: providerInfo.has_key ? "var(--signal-up)" : "var(--signal)",
      border: `1px solid ${providerInfo.has_key ? "rgba(124,255,178,0.3)" : "rgba(240,183,47,0.3)"}`
    }
  }, providerInfo.has_key ? "API key set" : "No key / CLI mode")), identity && identity.onboarding_completed && /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--bg-1)",
      border: "1px solid var(--line)",
      borderRadius: 10,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "14px 18px",
      background: "var(--bg-2)",
      borderBottom: "1px solid var(--line)",
      display: "flex",
      alignItems: "center",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 20
    }
  }, "\uD83D\uDC64"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontWeight: 700,
      fontSize: 14
    }
  }, "Linked Identity"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-lo)",
      fontSize: 12,
      marginTop: 3
    }
  }, "The active profile parameters matching this DailyDex session."))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "16px 18px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: identity.avatar || "https://api.dicebear.com/7.x/identicon/svg?seed=default",
    alt: "avatar",
    style: {
      width: 44,
      height: 44,
      borderRadius: "50%",
      border: "2px solid var(--line-hi)",
      background: "var(--bg-2)"
    }
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-hi)",
      fontWeight: 600,
      fontSize: 14,
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, identity.name, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 9.5,
      padding: "1px 6px",
      borderRadius: 999,
      background: identity.provider === "local" ? "rgba(240,183,47,0.1)" : "rgba(98,168,255,0.1)",
      color: identity.provider === "local" ? "var(--signal)" : "var(--signal-cool)",
      border: `1px solid ${identity.provider === "local" ? "rgba(240,183,47,0.3)" : "rgba(98,168,255,0.3)"}`,
      textTransform: "uppercase"
    }
  }, identity.provider)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--text-lo)",
      marginTop: 2
    }
  }, identity.email || "No email linked"), identity.channel_id && /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: "var(--text-lo)",
      marginTop: 4
    }
  }, "Channel ID: ", identity.channel_id))), /*#__PURE__*/React.createElement("button", {
    className: "btn danger",
    onClick: handleResetOnboarding,
    style: {
      background: "rgba(255,107,107,0.1)",
      border: "1px solid rgba(255,107,107,0.3)",
      color: "var(--signal-down)",
      cursor: "pointer",
      padding: "8px 14px",
      borderRadius: 6,
      fontWeight: 600,
      transition: "background 150ms"
    },
    onMouseEnter: e => e.currentTarget.style.background = "rgba(255,107,107,0.18)",
    onMouseLeave: e => e.currentTarget.style.background = "rgba(255,107,107,0.1)"
  }, "Sign Out & Reset"))), Object.entries(groups).map(([group, keys]) => {
    const gm = GROUP_META[group] || {
      label: group,
      icon: "⚙",
      color: "var(--text-mid)",
      desc: ""
    };
    return /*#__PURE__*/React.createElement("div", {
      key: group,
      style: {
        background: "var(--bg-1)",
        border: "1px solid var(--line)",
        borderRadius: 10,
        overflow: "hidden"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "14px 18px",
        background: "var(--bg-2)",
        borderBottom: "1px solid var(--line)",
        display: "flex",
        alignItems: "flex-start",
        gap: 12
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 20,
        lineHeight: 1
      }
    }, gm.icon), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        color: "var(--text-hi)",
        fontWeight: 700,
        fontSize: 14
      }
    }, gm.label), /*#__PURE__*/React.createElement("div", {
      style: {
        color: "var(--text-lo)",
        fontSize: 12,
        marginTop: 3,
        lineHeight: 1.4
      }
    }, gm.desc)), group === "youtube" && /*#__PURE__*/React.createElement("a", {
      href: "https://console.cloud.google.com/apis/library/youtube.googleapis.com",
      target: "_blank",
      rel: "noopener",
      style: {
        fontSize: 11,
        color: "var(--signal)",
        textDecoration: "none",
        padding: "4px 8px",
        border: "1px solid rgba(240,183,47,0.3)",
        borderRadius: 4
      }
    }, "Get Key \u2197"), group === "image_gen" && /*#__PURE__*/React.createElement("a", {
      href: "https://fal.ai",
      target: "_blank",
      rel: "noopener",
      style: {
        fontSize: 11,
        color: "var(--signal)",
        textDecoration: "none",
        padding: "4px 8px",
        border: "1px solid rgba(240,183,47,0.3)",
        borderRadius: 4
      }
    }, "fal.ai \u2197")), group === "llm" && /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "16px 18px",
        borderBottom: "1px solid var(--line)"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "var(--text-lo)",
        marginBottom: 12,
        fontWeight: 600,
        letterSpacing: "0.05em"
      }
    }, "DEPLOYMENT MODE"), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap: 12,
        marginBottom: 20
      }
    }, /*#__PURE__*/React.createElement("button", {
      onClick: () => {
        handleChange("deployment_mode", "cli");
        handleChange("llm_provider", "gemini");
      },
      style: {
        padding: "14px 16px",
        borderRadius: 8,
        background: currentMode === "cli" ? "rgba(240,183,47,0.08)" : "var(--bg-2)",
        border: `1px solid ${currentMode === "cli" ? "rgba(240,183,47,0.5)" : "var(--line)"}`,
        cursor: "pointer",
        textAlign: "left",
        transition: "all 120ms"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 18
      }
    }, "\uD83D\uDCBB"), /*#__PURE__*/React.createElement("span", {
      style: {
        color: currentMode === "cli" ? "var(--signal)" : "var(--text-hi)",
        fontWeight: 700,
        fontSize: 14
      }
    }, "Self-hosted CLI")), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "var(--text-lo)",
        lineHeight: 1.4
      }
    }, "Onboard local AI CLIs running directly on your machine.")), /*#__PURE__*/React.createElement("button", {
      onClick: () => {
        handleChange("deployment_mode", "api");
        handleChange("llm_provider", "nvidia");
      },
      style: {
        padding: "14px 16px",
        borderRadius: 8,
        background: currentMode === "api" ? "rgba(240,183,47,0.08)" : "var(--bg-2)",
        border: `1px solid ${currentMode === "api" ? "rgba(240,183,47,0.5)" : "var(--line)"}`,
        cursor: "pointer",
        textAlign: "left",
        transition: "all 120ms"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 18
      }
    }, "\u2601\uFE0F"), /*#__PURE__*/React.createElement("span", {
      style: {
        color: currentMode === "api" ? "var(--signal)" : "var(--text-hi)",
        fontWeight: 700,
        fontSize: 14
      }
    }, "Cloud VM / VPC API")), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "var(--text-lo)",
        lineHeight: 1.4
      }
    }, "Deploy on a cloud VM/container and link remote HTTP APIs."))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "var(--text-lo)",
        marginBottom: 10,
        fontWeight: 600,
        letterSpacing: "0.05em"
      }
    }, "CHOOSE YOUR AI PROVIDER"), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 8
      }
    }, Object.entries(LLM_PROVIDER_DOCS).filter(([p, info]) => {
      if (currentMode === "cli") {
        return ["gemini", "claude", "opencode", "hermes", "kilocode", "agy", "ollama"].includes(p);
      } else {
        return ["anthropic", "nvidia", "openai"].includes(p);
      }
    }).map(([p, info]) => {
      const isActive = currentProvider === p;
      return /*#__PURE__*/React.createElement("button", {
        key: p,
        onClick: () => handleChange("llm_provider", p),
        style: {
          padding: "10px 12px",
          borderRadius: 7,
          background: isActive ? "rgba(240,183,47,0.12)" : "var(--bg-2)",
          border: `1px solid ${isActive ? "rgba(240,183,47,0.5)" : "var(--line)"}`,
          cursor: "pointer",
          textAlign: "left",
          transition: "all 120ms"
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 4
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          color: isActive ? "var(--signal)" : "var(--text-hi)",
          fontWeight: 700,
          fontSize: 13,
          fontFamily: "var(--font-mono)",
          textTransform: "uppercase"
        }
      }, p), info.free && /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 9,
          padding: "1px 5px",
          borderRadius: 999,
          background: "rgba(124,255,178,0.1)",
          color: "var(--signal-up)",
          border: "1px solid rgba(124,255,178,0.3)"
        }
      }, "FREE")), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 10,
          color: "var(--text-lo)",
          lineHeight: 1.3
        }
      }, info.note));
    })), currentProvider && LLM_PROVIDER_DOCS[currentProvider] && /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 10,
        padding: "8px 12px",
        background: "var(--bg-0)",
        borderRadius: 5,
        border: "1px solid var(--line)",
        fontSize: 11,
        color: "var(--text-lo)"
      }
    }, "\uD83D\uDCD6 Setup: ", /*#__PURE__*/React.createElement("a", {
      href: LLM_PROVIDER_DOCS[currentProvider].setup,
      target: "_blank",
      rel: "noopener",
      style: {
        color: "var(--signal)",
        textDecoration: "none"
      }
    }, LLM_PROVIDER_DOCS[currentProvider].setup))), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "6px 0"
      }
    }, keys.filter(({
      key
    }) => {
      // For LLM group, only show relevant fields
      if (group !== "llm") return true;
      if (key === "llm_provider" || key === "deployment_mode") return false; // rendered above

      // Show CLI path overrides only when in selfhosted mode and relevant provider is active
      if (key === "gemini_path") return currentMode === "cli" && currentProvider === "gemini";
      if (key === "claude_path") return currentMode === "cli" && currentProvider === "claude";
      if (key === "opencode_path") return currentMode === "cli" && currentProvider === "opencode";
      if (key === "hermes_path") return currentMode === "cli" && currentProvider === "hermes";
      if (key === "kilocode_path") return currentMode === "cli" && currentProvider === "kilocode";
      if (key === "agy_path") return currentMode === "cli" && currentProvider === "agy";
      if (key === "ollama_url" || key === "ollama_model") return currentMode === "cli" && currentProvider === "ollama";
      if (key === "llm_api_key") return currentMode === "api" && ["nvidia", "openai", "anthropic"].includes(currentProvider);
      if (key === "llm_base_url") return currentMode === "api" && ["openai", "nvidia"].includes(currentProvider);
      return true;
    }).map(({
      key,
      meta
    }) => {
      const vdata = values[key] || {};
      const isEnvOverride = vdata.env_override;
      const hasValue = vdata.has_value;
      const currentVal = draft[key] !== undefined ? draft[key] : vdata.value || "";
      const isSecret = meta.secret;
      const valResult = validation[key];
      return /*#__PURE__*/React.createElement("div", {
        key: key,
        style: {
          padding: "14px 18px",
          borderBottom: "1px solid var(--line)"
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 6
        }
      }, /*#__PURE__*/React.createElement("label", {
        style: {
          color: "var(--text-hi)",
          fontSize: 13,
          fontWeight: 600
        }
      }, meta.label), isEnvOverride && /*#__PURE__*/React.createElement("span", {
        title: "Set via environment variable \u2014 takes priority over settings file",
        style: {
          fontSize: 10,
          padding: "1px 6px",
          borderRadius: 999,
          background: "rgba(100,120,255,0.1)",
          color: "#8899FF",
          border: "1px solid rgba(100,120,255,0.3)"
        }
      }, "\uD83D\uDD12 env var"), hasValue && !isEnvOverride && /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 10,
          padding: "1px 6px",
          borderRadius: 999,
          background: "rgba(124,255,178,0.08)",
          color: "var(--signal-up)",
          border: "1px solid rgba(124,255,178,0.25)"
        }
      }, "\u2713 saved")), meta.help && /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "var(--text-lo)",
          marginBottom: 8,
          lineHeight: 1.4
        }
      }, meta.help), meta.options ? /*#__PURE__*/React.createElement("select", {
        value: currentVal,
        onChange: e => handleChange(key, e.target.value),
        disabled: isEnvOverride,
        style: {
          width: "100%",
          height: 36,
          padding: "0 10px",
          background: "var(--bg-0)",
          border: "1px solid var(--line-2)",
          borderRadius: 5,
          color: "var(--text-hi)",
          fontFamily: "var(--font-mono)",
          fontSize: 13,
          cursor: isEnvOverride ? "not-allowed" : "pointer",
          opacity: isEnvOverride ? 0.6 : 1
        }
      }, /*#__PURE__*/React.createElement("option", {
        value: ""
      }, "-- select --"), meta.options.map(o => /*#__PURE__*/React.createElement("option", {
        key: o,
        value: o
      }, o))) :
      /*#__PURE__*/
      /* Text/password input */
      React.createElement("div", {
        style: {
          display: "flex",
          gap: 8
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          flex: 1,
          position: "relative"
        }
      }, /*#__PURE__*/React.createElement("input", {
        type: isSecret && !showSecret[key] ? "password" : "text",
        value: currentVal,
        onChange: e => handleChange(key, e.target.value),
        placeholder: isEnvOverride ? "(set via env var)" : meta.placeholder || "",
        disabled: isEnvOverride,
        style: {
          width: "100%",
          height: 36,
          padding: "0 36px 0 10px",
          background: "var(--bg-0)",
          border: `1px solid ${valResult ? valResult.ok ? "rgba(124,255,178,0.5)" : "rgba(255,100,100,0.5)" : "var(--line-2)"}`,
          borderRadius: 5,
          color: "var(--text-hi)",
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          boxSizing: "border-box",
          opacity: isEnvOverride ? 0.6 : 1,
          cursor: isEnvOverride ? "not-allowed" : "text",
          outline: "none",
          transition: "border-color 150ms"
        }
      }), isSecret && /*#__PURE__*/React.createElement("button", {
        onClick: () => toggleShow(key),
        style: {
          position: "absolute",
          right: 8,
          top: "50%",
          transform: "translateY(-50%)",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--text-lo)",
          fontSize: 13,
          padding: 0
        }
      }, showSecret[key] ? "🙈" : "👁")), key === "youtube_api_key" && /*#__PURE__*/React.createElement("button", {
        className: "btn ghost",
        onClick: () => handleValidate("youtube"),
        disabled: validating["youtube"],
        style: {
          flexShrink: 0,
          fontSize: 12
        }
      }, validating["youtube"] ? "Testing…" : "Test Key"), key === "fal_api_key" && /*#__PURE__*/React.createElement("button", {
        className: "btn ghost",
        onClick: () => handleValidate("fal"),
        disabled: validating["fal"],
        style: {
          flexShrink: 0,
          fontSize: 12
        }
      }, validating["fal"] ? "Testing…" : "Test Key"), hasValue && !isEnvOverride && /*#__PURE__*/React.createElement("button", {
        onClick: () => handleDelete(key),
        title: "Remove saved key",
        style: {
          flexShrink: 0,
          background: "none",
          border: "1px solid var(--line)",
          borderRadius: 5,
          cursor: "pointer",
          padding: "0 10px",
          color: "var(--text-lo)",
          fontSize: 13
        }
      }, "\u2715")), valResult && /*#__PURE__*/React.createElement("div", {
        style: {
          marginTop: 6,
          fontSize: 11,
          padding: "6px 10px",
          borderRadius: 4,
          background: valResult.ok ? "rgba(124,255,178,0.06)" : "rgba(255,100,100,0.06)",
          color: valResult.ok ? "var(--signal-up)" : "var(--signal-down)",
          border: `1px solid ${valResult.ok ? "rgba(124,255,178,0.2)" : "rgba(255,100,100,0.2)"}`
        }
      }, valResult.ok ? `✓ ${valResult.quota_info || "Key is valid"}` : `✗ ${valResult.error}`));
    })));
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "12px 16px",
      borderRadius: 8,
      background: "var(--bg-2)",
      border: "1px solid var(--line)",
      fontSize: 12,
      color: "var(--text-lo)",
      lineHeight: 1.5
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: "var(--text-mid)",
      marginBottom: 4
    }
  }, "\uD83D\uDD12 Privacy Note"), "Keys are stored at ", /*#__PURE__*/React.createElement("code", {
    style: {
      background: "var(--bg-0)",
      padding: "1px 4px",
      borderRadius: 3,
      fontSize: 11
    }
  }, "~/.dailydex/settings.json"), " on your local machine. They are ", /*#__PURE__*/React.createElement("strong", {
    style: {
      color: "var(--text-hi)"
    }
  }, "never"), " sent to any cloud or third-party server by DailyDex itself. Environment variables in ", /*#__PURE__*/React.createElement("code", {
    style: {
      background: "var(--bg-0)",
      padding: "1px 4px",
      borderRadius: 3,
      fontSize: 11
    }
  }, ".env"), " always take priority over saved settings."), hasDraft && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "sticky",
      bottom: 16,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "12px 18px",
      background: "var(--bg-1)",
      border: "1px solid rgba(240,183,47,0.35)",
      borderRadius: 10,
      boxShadow: "0 8px 32px rgba(0,0,0,0.4)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--text-mid)"
    }
  }, "You have unsaved changes."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: () => {
      setDraft({});
      setMsg({
        text: "",
        ok: true
      });
    }
  }, "Discard"), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: handleSave,
    disabled: saving,
    style: {
      background: "linear-gradient(90deg, var(--signal), var(--signal-hot))",
      border: "none",
      color: "#1a1100",
      fontWeight: 700
    }
  }, saving ? "Saving…" : "💾 Save Changes"))));
};
Object.assign(window, {
  SettingsView
});