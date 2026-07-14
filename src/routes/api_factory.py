"""Factory approval-queue routes: run, review, publish."""

from flask import Blueprint, current_app, jsonify, request

factory_bp = Blueprint("factory", __name__)

VALID_TRANSITIONS = {
    "approve": ("pending_review",),
    "reject": ("pending_review", "approved"),
}


def _db():
    return current_app.config["INTEL_DB"]


def _scored_data():
    loader = current_app.config.get("SCORED_DATA_LOADER")
    return loader() if loader else {}


@factory_bp.route("/api/factory/run", methods=["POST"])
def api_factory_run():
    import factory

    payload = request.get_json(silent=True) or {}
    limit = int(payload.get("limit", 3))
    started = factory.start_factory_run(_db(), _scored_data(), limit=limit)
    return jsonify({"status": "running", "started": started})


@factory_bp.route("/api/factory/status", methods=["GET"])
def api_factory_status():
    import factory

    return jsonify(factory.factory_status())


@factory_bp.route("/api/factory/queue", methods=["GET"])
def api_factory_queue():
    status = request.args.get("status")
    return jsonify({"items": _db().factory_list(status=status)})


@factory_bp.route("/api/factory/<int:row_id>/approve", methods=["POST"])
def api_factory_approve(row_id):
    row = _db().factory_get(row_id)
    if not row:
        return jsonify({"success": False, "error": "not found"}), 404
    if row["status"] not in VALID_TRANSITIONS["approve"]:
        return jsonify({"success": False, "error": f"cannot approve from '{row['status']}'"}), 400
    _db().factory_update_status(row_id, "approved")
    return jsonify({"success": True, "status": "approved"})


@factory_bp.route("/api/factory/<int:row_id>/reject", methods=["POST"])
def api_factory_reject(row_id):
    row = _db().factory_get(row_id)
    if not row:
        return jsonify({"success": False, "error": "not found"}), 404
    if row["status"] not in VALID_TRANSITIONS["reject"]:
        return jsonify({"success": False, "error": f"cannot reject from '{row['status']}'"}), 400
    _db().factory_update_status(row_id, "rejected")
    return jsonify({"success": True, "status": "rejected"})


@factory_bp.route("/api/factory/<int:row_id>/publish", methods=["POST"])
def api_factory_publish(row_id):
    """Upload an approved short to YouTube via the existing OAuth uploader."""
    row = _db().factory_get(row_id)
    if not row:
        return jsonify({"success": False, "error": "not found"}), 404
    if row["status"] != "approved":
        return jsonify({"success": False, "error": "only approved items can be published"}), 400
    if not row.get("video_path"):
        return jsonify({"success": False, "error": "no rendered video on this row"}), 400

    try:
        import youtube_oauth

        token = youtube_oauth._ensure_valid_token()
        if not token.get("ok"):
            return jsonify({"success": False, "error": token.get("error", "YouTube OAuth not configured")}), 400

        result = youtube_oauth.upload_video(
            access_token=token["access_token"],
            title=row["title"],
            description=row.get("hook", ""),
            file_path=row["video_path"],
            is_short=True,
        )
    except Exception as exc:
        _db().factory_update_status(row_id, "approved", error=str(exc))
        return jsonify({"success": False, "error": str(exc)}), 502

    if result.get("error"):
        _db().factory_update_status(row_id, "approved", error=result["error"])
        return jsonify({"success": False, "error": result["error"]}), 502

    url = result.get("url", "")
    _db().factory_update_status(row_id, "published", published_url=url)
    return jsonify({"success": True, "status": "published", "published_url": url})
