"""Thumbnail routes: image generation (fal.ai), variant CRUD, pick."""

from flask import Blueprint, current_app, jsonify, request

thumbnails_bp = Blueprint("thumbnails", __name__)

try:
    import thumbnail_generator as _thumb_gen
    HAS_THUMB_GEN = True
except Exception as _e:
    print(f"Warning: thumbnail_generator not available: {_e}")
    HAS_THUMB_GEN = False


def _db():
    return current_app.config.get("INTEL_DB")


# ── Image generation (Flux via fal.ai) ──────────────────────────────────────

@thumbnails_bp.route("/api/thumbnails/generate-image", methods=["POST"])
def api_generate_thumbnail_image():
    """Generate a real thumbnail image using Flux via fal.ai."""
    if not HAS_THUMB_GEN:
        return jsonify({"error": "thumbnail_generator not available"}), 503

    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    variant_id = body.get("variant_id")
    if not topic:
        return jsonify({"error": "topic is required"}), 400

    style = body.get("style", "dark_tech")
    extra_context = body.get("extra_context")
    num_variants = min(int(body.get("num_variants", 1)), 4)

    results = _thumb_gen.generate_thumbnail(
        topic=topic,
        style=style,
        extra_context=extra_context,
        num_variants=num_variants,
    )

    any_ok = any(r.get("url") for r in results)
    db = _db()
    if any_ok and variant_id and db is not None:
        first_url = next(r.get("url") for r in results if r.get("url"))
        db.update_thumbnail_variant(variant_id, image_path=first_url)

    return jsonify({
        "ok": any_ok,
        "results": results,
        "has_key": bool(_thumb_gen._get_fal_key()),
    }), (200 if any_ok else 422)


@thumbnails_bp.route("/api/thumbnails/styles", methods=["GET"])
def api_thumbnail_style():
    """List available image generation style presets."""
    if not HAS_THUMB_GEN:
        return jsonify([])
    return jsonify([
        {"key": k, "description": v[:80] + "..."}
        for k, v in _thumb_gen.STYLE_PRESETS.items()
    ])


# ── Variant CRUD ─────────────────────────────────────────────────────────────

@thumbnails_bp.route("/api/thumbnails/generate", methods=["POST"])
def api_thumbnails_generate():
    db = _db()
    if db is None:
        return jsonify({"error": "db unavailable"}), 503
    from creator_intelligence import generate_thumbnail_variants

    body = request.get_json(silent=True) or {}
    content_hash = body.get("content_hash")
    if not content_hash:
        return jsonify({"error": "content_hash required"}), 400
    count = int(body.get("count", 6))
    variants = generate_thumbnail_variants(
        db, content_hash, topic=body.get("topic"),
        count=count, base_item=body.get("item"),
    )
    return jsonify(variants), 201


@thumbnails_bp.route("/api/thumbnails/<content_hash>")
def api_thumbnails_get(content_hash):
    db = _db()
    if db is None:
        return jsonify([])
    from creator_intelligence import serialize_thumbnail_variant

    rows = db.get_thumbnail_variants(content_hash)
    return jsonify([serialize_thumbnail_variant(r) for r in rows])


@thumbnails_bp.route("/api/thumbnails/<variant_id>", methods=["PUT"])
def api_thumbnails_update(variant_id):
    db = _db()
    if db is None:
        return jsonify({"error": "db unavailable"}), 503
    from creator_intelligence import serialize_thumbnail_variant

    body = request.get_json(silent=True) or {}
    fields = {}
    if "text" in body:
        fields["text_primary"] = body["text"]
    if "subtext" in body:
        fields["text_secondary"] = body["subtext"]
    for k in ("hue", "kind", "ctr_pred"):
        if k in body:
            fields[k] = body[k]
    ok = db.update_thumbnail_variant(variant_id, **fields)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify(serialize_thumbnail_variant(db.get_thumbnail_variant(variant_id)))


@thumbnails_bp.route("/api/thumbnails/<variant_id>", methods=["DELETE"])
def api_thumbnails_delete(variant_id):
    db = _db()
    if db is None:
        return jsonify({"error": "db unavailable"}), 503
    return jsonify({"success": db.delete_thumbnail_variant(variant_id)})


@thumbnails_bp.route("/api/thumbnails/<variant_id>/pick", methods=["POST"])
def api_thumbnails_pick(variant_id):
    db = _db()
    if db is None:
        return jsonify({"error": "db unavailable"}), 503
    ok = db.pick_thumbnail_variant(variant_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"success": True})