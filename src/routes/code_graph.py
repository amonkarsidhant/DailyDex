"""Codebase graph (Understand Anything) routes.

Serves the prebuilt dashboard bundle plus the project's generated graph JSON.
Paths are env-overridable so the app still boots on machines/containers that
don't have the Understand Anything plugin installed.
"""
import os

from flask import Blueprint, jsonify, redirect, request, send_from_directory

code_graph_bp = Blueprint("code_graph", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UA_DIR = os.environ.get("UA_DIR", os.path.join(BASE_DIR, ".understand-anything"))
UA_DASHBOARD_DIST = os.environ.get(
    "UA_DASHBOARD_DIST",
    os.path.expanduser(
        "~/.understand-anything/repo/understand-anything-plugin/packages/dashboard/dist"
    ),
)
CODE_GRAPH_TOKEN = os.environ.get("CODE_GRAPH_TOKEN", "daily-dex-code-graph")


@code_graph_bp.route("/code-graph")
@code_graph_bp.route("/code-graph/")
def route_code_graph():
    token = request.args.get("token")
    if not token:
        return redirect(f"/code-graph/?token={CODE_GRAPH_TOKEN}")
    if not os.path.isdir(UA_DASHBOARD_DIST):
        return jsonify({"error": "code-graph dashboard not installed"}), 404
    return send_from_directory(UA_DASHBOARD_DIST, "index.html")


@code_graph_bp.route("/assets/<path:path>")
def route_code_graph_assets(path):
    assets_dir = os.path.join(UA_DASHBOARD_DIST, "assets")
    if not os.path.isdir(assets_dir):
        return "", 404
    return send_from_directory(assets_dir, path)


@code_graph_bp.route("/favicon.svg")
def route_code_graph_favicon():
    if os.path.exists(os.path.join(UA_DASHBOARD_DIST, "favicon.svg")):
        return send_from_directory(UA_DASHBOARD_DIST, "favicon.svg")
    return "", 404


@code_graph_bp.route("/meta.json")
@code_graph_bp.route("/config.json")
@code_graph_bp.route("/knowledge-graph.json")
@code_graph_bp.route("/diff-overlay.json")
@code_graph_bp.route("/domain-graph.json")
def route_code_graph_json():
    # Only allow validated token
    token = request.args.get("token")
    if token != CODE_GRAPH_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    filename = request.path.lstrip("/")
    file_path = os.path.join(UA_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({}), 404
    return send_from_directory(UA_DIR, filename)


@code_graph_bp.route("/file-content.json")
def route_code_graph_file_content():
    token = request.args.get("token")
    if token != CODE_GRAPH_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    file_path = request.args.get("path")
    if not file_path:
        return jsonify({"error": "Path parameter required"}), 400

    abs_path = os.path.abspath(os.path.join(BASE_DIR, file_path))
    if not abs_path.startswith(BASE_DIR):
        return jsonify({"error": "Access denied"}), 403

    if not os.path.exists(abs_path) or os.path.isdir(abs_path):
        return jsonify({"error": "File not found"}), 404

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return jsonify({"error": f"Failed to read file: {str(e)}"}), 500

    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    lang_map = {
        "py": "python",
        "js": "javascript",
        "jsx": "jsx",
        "ts": "typescript",
        "tsx": "tsx",
        "html": "html",
        "css": "css",
        "json": "json",
        "sh": "bash",
        "md": "markdown",
        "sql": "sql"
    }
    language = lang_map.get(ext, "text")

    return jsonify({
        "path": file_path,
        "language": language,
        "content": content,
        "sizeBytes": os.path.getsize(abs_path),
        "lineCount": len(content.splitlines())
    })
