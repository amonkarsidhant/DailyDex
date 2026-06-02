from flask import Blueprint, jsonify, request
import os
import json

settings_bp = Blueprint("settings", __name__)

# Import settings dependencies
try:
    import settings_manager as _settings_mgr
    HAS_SETTINGS_MGR = True
except ImportError:
    HAS_SETTINGS_MGR = False

def _load_creator_profile_safe():
    profile_path = os.environ.get(
        "CREATOR_PROFILE_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "creator_profile.json")
    )
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

@settings_bp.route("/api/settings", methods=["GET"])
def api_settings_get():
    """Return current settings with secrets masked."""
    if not HAS_SETTINGS_MGR:
        return jsonify({"error": "settings_manager not available"}), 503
    return jsonify(_settings_mgr.get_for_api())

@settings_bp.route("/api/settings", methods=["POST"])
def api_settings_update():
    if not HAS_SETTINGS_MGR:
        return jsonify({"error": "settings_manager not available"}), 503
    body = request.get_json(silent=True) or {}
    _settings_mgr.update(body)
    return jsonify({"ok": True, "settings": _settings_mgr.get_for_api()})

@settings_bp.route("/api/settings/<key>", methods=["DELETE"])
def api_settings_delete(key):
    if not HAS_SETTINGS_MGR:
        return jsonify({"error": "settings_manager not available"}), 503
    _settings_mgr.delete(key)
    return jsonify({"ok": True})

@settings_bp.route("/api/settings/validate/youtube", methods=["POST"])
def api_settings_validate_youtube():
    if not HAS_SETTINGS_MGR:
        return jsonify({"error": "settings_manager not available"}), 503
    body = request.get_json(silent=True) or {}
    api_key = body.get("api_key", "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "api_key is required"}), 400
    result = _settings_mgr.validate_youtube_key(api_key)
    return jsonify(result)

@settings_bp.route("/api/settings/validate/fal", methods=["POST"])
def api_settings_validate_fal():
    if not HAS_SETTINGS_MGR:
        return jsonify({"error": "settings_manager not available"}), 503
    body = request.get_json(silent=True) or {}
    api_key = body.get("api_key", "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "api_key is required"}), 400
    result = _settings_mgr.validate_fal_key(api_key)
    return jsonify(result)

@settings_bp.route("/api/settings/provider-info", methods=["GET"])
def api_settings_provider_info():
    try:
        import llm_summary as _llm
        provider = _llm.get_llm_setting("LLM_PROVIDER", "gemini")
        deployment_mode = _llm.get_llm_setting("DEPLOYMENT_MODE", "cli")
        
        resolved_provider = provider
        if deployment_mode == "api" and provider not in ("nvidia", "openai", "anthropic", "ollama"):
            resolved_provider = "nvidia" if _llm.get_llm_setting("NVIDIA_API_KEY") else "anthropic"
            
        model_info = {
            "gemini": {"model": _llm.get_llm_setting("GEMINI_MODEL", "") or "default", "note": "Uses local gemini CLI"},
            "claude": {"model": _llm.get_llm_setting("CLAUDE_MODEL", "") or "claude-sonnet-4-6", "note": "Uses local claude CLI"},
            "opencode": {"model": _llm.get_llm_setting("LLM_MODEL", "") or "deepseek-v4-flash-free", "note": "Uses local opencode CLI"},
            "hermes": {"model": _llm.get_llm_setting("LLM_MODEL", "") or "default", "note": "Uses local hermes CLI"},
            "kilocode": {"model": _llm.get_llm_setting("LLM_MODEL", "") or "default", "note": "Uses local kilocode CLI"},
            "agy": {"model": _llm.get_llm_setting("LLM_MODEL", "") or "default", "note": "Uses local agy CLI"},
            "ollama": {"model": _llm.get_llm_setting("OLLAMA_MODEL", "phi3:mini"), "note": f"URL: {_llm.get_llm_setting('OLLAMA_URL', 'http://localhost:11434')}"},
            "nvidia": {"model": _llm.get_llm_setting("LLM_MODEL", "") or "minimaxai/minimax-m2.7", "note": "NVIDIA NIM API"},
            "openai": {"model": _llm.get_llm_setting("LLM_MODEL", "gpt-4o-mini"), "note": "OpenAI/Compatible API"},
            "anthropic": {"model": _llm.get_llm_setting("LLM_MODEL", "claude-3-5-sonnet-latest"), "note": "Anthropic API"},
        }.get(resolved_provider, {"model": "unknown", "note": ""})
        
        has_key = False
        if resolved_provider in ("nvidia", "openai", "anthropic"):
            has_key = bool(_llm.get_llm_setting("LLM_API_KEY") or _llm.get_llm_setting("NVIDIA_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
            
        return jsonify({
            "provider": resolved_provider,
            "model": model_info["model"],
            "note": model_info["note"] + (" (Cloud API Mode Fallback)" if resolved_provider != provider else ""),
            "has_key": has_key,
            "api_mode": deployment_mode == "api"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@settings_bp.route("/api/onboarding/submit", methods=["POST"])
def api_onboarding_submit():
    if not HAS_SETTINGS_MGR:
        return jsonify({"error": "settings_manager not available"}), 503
    body = request.get_json(silent=True) or {}
    identity = body.get("identity") or {}
    profile_data = body.get("profile") or {}
    keys = body.get("keys") or {}

    try:
        _settings_mgr.update(keys)
    except Exception as e:
        print(f"Error updating settings during onboarding: {e}")

    profile = _load_creator_profile_safe()
    profile["creator_identity"] = {
        "provider": identity.get("provider", "local"),
        "name": identity.get("name", "Local Creator"),
        "email": identity.get("email", ""),
        "avatar": identity.get("avatar", ""),
        "channel_id": identity.get("channel_id", ""),
        "onboarding_completed": True
    }

    if "channel_name" in profile_data:
        profile["channel_name"] = profile_data["channel_name"]
    if "niche" in profile_data:
        profile["niche"] = profile_data["niche"]
    if "tone" in profile_data:
        profile["tone"] = profile_data["tone"]
    if "persona" in profile_data:
        profile["persona"] = profile_data["persona"]

    try:
        profile_path = os.environ.get(
            "CREATOR_PROFILE_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "creator_profile.json")
        )
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
    except Exception as e:
        return jsonify({"error": f"Failed to save profile: {e}"}), 500

    return jsonify({"success": True})

@settings_bp.route("/api/onboarding/reset", methods=["POST"])
def api_onboarding_reset():
    profile = _load_creator_profile_safe()
    profile.pop("creator_identity", None)

    try:
        profile_path = os.environ.get(
            "CREATOR_PROFILE_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "creator_profile.json")
        )
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
    except Exception as e:
        return jsonify({"error": f"Failed to reset profile: {e}"}), 500

    return jsonify({"success": True})
