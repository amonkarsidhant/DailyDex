"""Saved items, research packs, ignore/track routes."""

import json
import os

from flask import Blueprint, current_app, jsonify, request

saved_bp = Blueprint("saved", __name__)


def _db():
    return current_app.config.get("INTEL_DB")


def _research_pack_dir() -> str:
    return current_app.config["RESEARCH_PACK_DIR"]


# ── Save / CRUD ─────────────────────────────────────────────────────────────

@saved_bp.route("/api/save", methods=["POST"])
def api_save():
    """Save an item"""
    db = _db()
    if not db:
        return jsonify({"success": False, "error": "Database not available"})

    data = request.json
    existing = None
    item_url = data.get("url", "")
    if item_url:
        existing = next((item for item in db.get_saved_items() if item.get("url") == item_url), None)
    item_id = db.save_item({
        "title": data.get("title", ""),
        "url": data.get("url", ""),
        "source": data.get("source", ""),
        "source_type": data.get("source_type", ""),
        "category": data.get("category", ""),
        "signal_score": data.get("signal_score", 0),
        "creator_score": data.get("creator_score"),
        "pipeline_type": data.get("pipeline_type"),
        "status": data.get("status", "to_read"),
        "working_title": data.get("working_title"),
        "hook": data.get("hook"),
        "format": data.get("format") or data.get("recommended_content_format") or data.get("best_format"),
        "outline": data.get("outline") or data.get("three_key_points") or [],
        "sources": data.get("sources") or data.get("source_evidence") or [],
        "thumbnail_text": ", ".join(data.get("thumbnail_text", [])) if isinstance(data.get("thumbnail_text"), list) else data.get("thumbnail_text"),
        "notes": data.get("notes", ""),
        "tags": data.get("tags", []),
        "priority": data.get("priority"),
        "published_url": data.get("published_url"),
    })
    created = existing is None
    return jsonify({
        "success": True,
        "id": item_id,
        "created": created,
        "message": "Saved to your board." if created else "Already saved, updated timestamp.",
    })


@saved_bp.route("/api/saved/<int:item_id>", methods=["DELETE"])
def api_delete_saved(item_id):
    """Delete a saved item"""
    db = _db()
    if not db:
        return jsonify({"success": False, "error": "Database not available"})

    db.delete_item(item_id)
    return jsonify({"success": True, "message": "Saved item removed."})


@saved_bp.route("/api/saved/<int:item_id>/status", methods=["PUT"])
def api_update_status(item_id):
    """Update saved item status"""
    db = _db()
    if not db:
        return jsonify({"success": False, "error": "Database not available"})

    data = request.json
    status = data.get("status", "to_read")
    db.update_status(item_id, status)
    return jsonify({"success": True, "message": f"Status updated to {status}."})


@saved_bp.route("/api/saved/<int:item_id>/notes", methods=["PUT"])
def api_update_notes(item_id):
    """Update saved item notes and tags"""
    db = _db()
    if not db:
        return jsonify({"success": False, "error": "Database not available"})

    data = request.json
    updates = {}
    for key, default in [("notes", ""), ("tags", [])]:
        if key in data:
            updates[key] = data.get(key, default)
    for key in ["working_title", "hook", "format", "outline", "sources", "thumbnail_text", "priority", "published_url", "pipeline_type"]:
        if key in data:
            updates[key] = data.get(key)
    db.update_item(item_id, updates)
    return jsonify({"success": True, "message": "Notes and tags updated."})


@saved_bp.route("/api/saved/<int:item_id>/validate", methods=["POST"])
def api_saved_validate(item_id):
    db = _db()
    if db is None:
        return jsonify({"error": "no_db"}), 503
    item = db.get_saved_item(item_id)
    if not item:
        return jsonify({"error": "not_found"}), 404

    parts = [
        item.get("title") or "",
        item.get("url") or "",
        item.get("notes") or "",
    ]

    outline = item.get("outline")
    if isinstance(outline, str):
        try:
            outline_list = json.loads(outline)
            if isinstance(outline_list, list):
                parts.extend(outline_list)
            else:
                parts.append(outline)
        except Exception:
            parts.append(outline)
    elif isinstance(outline, list):
        parts.extend(outline)

    assets = item.get("production_assets")
    if isinstance(assets, str):
        try:
            assets = json.loads(assets)
        except Exception:
            pass
    if isinstance(assets, dict):
        for key, val in assets.items():
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                parts.extend(val)

    combined_text = "\n".join(str(p) for p in parts if p)

    from command_validator import validate_script_commands
    results = validate_script_commands(combined_text)

    return jsonify({
        "success": True,
        "item_id": item_id,
        "results": results,
    })


@saved_bp.route("/api/saved")
def api_get_saved():
    """Get all saved items"""
    db = _db()
    if not db:
        return jsonify({"items": []})

    status_filter = request.args.get("status")
    pipeline_type = request.args.get("pipeline_type")
    items = db.get_saved_items(pipeline_type=pipeline_type)

    if status_filter and status_filter != "all":
        items = [i for i in items if i.get("status") == status_filter]

    return jsonify({"items": items})


@saved_bp.route("/api/saved/export", methods=["GET"])
def api_export_saved():
    """Export saved items as JSON or markdown"""
    db = _db()
    if not db:
        return jsonify({"items": []})

    fmt = request.args.get("format", "json")
    status_filter = request.args.get("status")
    pipeline_type = request.args.get("pipeline_type")
    items = db.get_saved_items(pipeline_type=pipeline_type)

    if status_filter and status_filter != "all":
        items = [i for i in items if i.get("status") == status_filter]

    if fmt == "markdown" or fmt == "md":
        md = "# Saved Intelligence\n\n"
        for item in items:
            status_emoji = {"to_read": "\U0001f4d6", "to_test": "\U0001f9ea", "testing": "\u2699\ufe0f", "useful": "\u2705", "discarded": "\u274c"}.get(item.get("status", ""), "\U0001f4cc")
            md += f"## {status_emoji} {item.get('title', 'Untitled')}\n\n"
            md += f"- URL: {item.get('url', 'N/A')}\n"
            md += f"- Status: {item.get('status', 'unknown')}\n"
            if item.get("notes"):
                md += f"- Notes: {item['notes']}\n"
            if item.get("tags"):
                md += f"- Tags: {', '.join(item['tags'])}\n"
            md += "\n"
        return md, 200, {"Content-Type": "text/markdown"}

    return jsonify({"items": items})


# ── Research packs ──────────────────────────────────────────────────────────

@saved_bp.route("/api/research-pack", methods=["POST"])
def api_build_research_pack():
    """Build and save a creator research pack."""
    from creator_intelligence import build_research_pack

    payload = request.get_json() or {}
    path, content = build_research_pack(payload, _research_pack_dir())
    return jsonify({
        "success": True,
        "path": path,
        "content": content,
        "message": f"Research pack saved to {path}.",
    })


@saved_bp.route("/api/research-packs")
def api_list_research_packs():
    """List saved research packs."""
    from dashboard_new import list_research_packs

    return jsonify({"packs": list_research_packs()})


@saved_bp.route("/api/research-pack/<path:filename>", methods=["GET"])
def api_get_research_pack(filename):
    """Return the raw markdown content of a research pack."""
    path = os.path.join(_research_pack_dir(), os.path.basename(filename))
    if not os.path.isfile(path):
        return jsonify({"error": "Not found"}), 404
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return jsonify({"filename": filename, "content": content})


@saved_bp.route("/api/research-pack/<path:filename>", methods=["PUT"])
def api_update_research_pack(filename):
    """Save edited markdown content back to a research pack file."""
    path = os.path.join(_research_pack_dir(), os.path.basename(filename))
    if not os.path.isfile(path):
        return jsonify({"error": "Not found"}), 404
    data = request.get_json() or {}
    content = data.get("content", "")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return jsonify({"success": True})


@saved_bp.route("/api/research-pack/<path:filename>/send-to-pipeline", methods=["POST"])
def api_research_pack_to_pipeline(filename):
    """Create a content pipeline item from a research pack."""
    db = _db()
    if not db:
        return jsonify({"success": False, "error": "Database not available"})
    path = os.path.join(_research_pack_dir(), os.path.basename(filename))
    if not os.path.isfile(path):
        return jsonify({"error": "Not found"}), 404
    with open(path, encoding="utf-8") as f:
        content = f.read()
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    title = lines[0].lstrip("# ") if lines else filename
    excerpt = lines[1][:300] if len(lines) > 1 else ""
    data = request.get_json() or {}
    item_id = db.save_item({
        "title": title,
        "url": f"research-pack://{filename}",
        "source": "research-pack",
        "source_type": "research-pack",
        "category": data.get("category", "Research"),
        "signal_score": 0,
        "status": "researching",
        "working_title": title,
        "hook": excerpt,
        "notes": content,
        "pipeline_type": "creator",
    })
    return jsonify({"success": True, "id": item_id, "message": "Added to Content Pipeline."})


# ── Ignore / Track ──────────────────────────────────────────────────────────

@saved_bp.route("/api/ignore", methods=["POST"])
def api_ignore():
    """Ignore/hide an item"""
    db = _db()
    if not db:
        return jsonify({"success": False, "error": "Database not available"})

    data = request.json
    url = data.get("url", "")
    title = data.get("title", "")
    source_type = data.get("source_type", "")

    db.ignore_item(url, title, source_type)
    return jsonify({"success": True, "message": "Item ignored and hidden."})


@saved_bp.route("/api/ignore-topic", methods=["POST"])
def api_ignore_topic():
    """Ignore all items associated with a topic cluster"""
    db = _db()
    if not db:
        return jsonify({"success": False, "error": "Database not available"})

    data = request.json
    topic = data.get("topic", "")
    items = data.get("items", [])

    for item in items:
        url = item.get("url", "")
        title = item.get("title", "")
        source_type = item.get("source_type", "")
        if url:
            db.ignore_item(url, title, source_type)

    loader = current_app.config.get("SCORED_DATA_LOADER")
    try:
        if loader:
            loader(force=True)
    except Exception:
        pass

    return jsonify({"success": True, "message": f"Topic '{topic}' and all {len(items)} items ignored."})


@saved_bp.route("/api/ignored")
def api_get_ignored():
    """Get all ignored items"""
    db = _db()
    if not db:
        return jsonify({"items": []})

    return jsonify({"items": db.get_ignored_items()})


@saved_bp.route("/api/track", methods=["POST"])
def api_track():
    """Add a topic to track"""
    db = _db()
    if not db:
        return jsonify({"success": False, "error": "Database not available"})

    data = request.json
    topic = data.get("topic", "")
    reason = data.get("reason", "")

    if topic:
        existing_topics = {item.get("topic") for item in db.get_tracked_topics()}
        db.add_tracked_topic(topic, reason)
        return jsonify({
            "success": True,
            "created": topic not in existing_topics,
            "message": "Tracking topic." if topic not in existing_topics else "Topic already tracked.",
        })

    return jsonify({"success": False, "error": "No topic provided"})


@saved_bp.route("/api/track", methods=["GET"])
def api_get_tracked():
    """Get all tracked topics"""
    db = _db()
    if not db:
        return jsonify({"topics": []})

    return jsonify({"topics": db.get_tracked_topics()})


@saved_bp.route("/api/track/<int:topic_id>", methods=["DELETE"])
def api_delete_track(topic_id):
    """Remove a tracked topic"""
    db = _db()
    if not db:
        return jsonify({"success": False})

    db.remove_tracked_topic(topic_id)
    return jsonify({"success": True, "message": "Tracked topic removed."})