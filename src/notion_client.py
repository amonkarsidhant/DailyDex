#!/usr/bin/env python3
"""
notion_client.py — Real Notion API Integration
------------------------------------------------
Creates pages in a Notion database from DailyDex saved items.
Replaces the mock URL generation in api_integrations.py.

Requires:
  - Notion Integration Token (create at notion.so/my-integrations)
  - A shared Notion database (share it with the integration)
  - Database ID (from the database URL)

API Reference: https://developers.notion.com/reference
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

# ── Notion API constants ─────────────────────────────────────────────────────

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Pipeline status → Notion select color mapping
STATUS_COLORS = {
    "idea": "gray",
    "researching": "blue",
    "script_ready": "yellow",
    "recording": "orange",
    "published": "green",
    "archived": "default",
}


# ── Key resolution ────────────────────────────────────────────────────────────

def _get_notion_token() -> str:
    """Resolve Notion integration token: env var > settings file."""
    env_key = os.environ.get("NOTION_API_TOKEN", "")
    if env_key:
        return env_key
    try:
        from settings_manager import get as settings_get
        return settings_get("notion_api_token") or ""
    except Exception:
        return ""


def _get_notion_database_id() -> str:
    """Resolve Notion database ID: env var > settings file."""
    env_key = os.environ.get("NOTION_DATABASE_ID", "")
    if env_key:
        return env_key
    try:
        from settings_manager import get as settings_get
        return settings_get("notion_database_id") or ""
    except Exception:
        return ""


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _notion_request(
    method: str,
    path: str,
    token: str,
    body: Optional[Dict] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Make an authenticated Notion API request."""
    url = f"{NOTION_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
        "User-Agent": "DailyDex/1.0",
    }

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        try:
            error_data = json.loads(error_body)
            msg = error_data.get("message", str(e))
        except Exception:
            msg = error_body or str(e)
        return {"error": msg, "status": e.code}
    except Exception as e:
        return {"error": str(e)}


# ── Public API ────────────────────────────────────────────────────────────────

def validate_notion_token(token: str) -> Dict[str, Any]:
    """
    Validate a Notion integration token by calling the /users/me endpoint.
    Returns {"valid": True, "bot_name": "..."} or {"valid": False, "error": "..."}.
    """
    if not token:
        return {"valid": False, "error": "No token provided"}

    result = _notion_request("GET", "/users/me", token)

    if "error" in result:
        return {"valid": False, "error": result["error"]}

    return {
        "valid": True,
        "bot_name": result.get("name", "Unknown"),
        "bot_id": result.get("id", ""),
    }


def sync_to_notion(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a Notion page from a DailyDex saved item.

    Args:
        item: A saved item dict with keys like title, url, status, score,
              notes, category, production_assets, etc.

    Returns:
        {"success": True, "notion_url": "<real_page_url>"}
        or {"error": "<message>"}
    """
    token = _get_notion_token()
    if not token:
        return {"error": "Notion API token not configured. Add it in Settings → Notion."}

    database_id = _get_notion_database_id()
    if not database_id:
        return {"error": "Notion database ID not configured. Add it in Settings → Notion."}

    # Extract item fields
    title = item.get("working_title") or item.get("title") or "Untitled"
    url = item.get("url") or ""
    status = item.get("status") or "idea"
    creator_score = item.get("creator_score") or 0
    signal_score = item.get("signal_score") or item.get("score") or 0
    fmt = item.get("format") or ""
    notes = item.get("notes") or ""
    category = item.get("category") or ""
    source = item.get("source") or item.get("source_type") or ""
    hook = item.get("hook") or ""

    # Parse production_assets if present
    assets = item.get("production_assets")
    if isinstance(assets, str):
        try:
            assets = json.loads(assets)
        except Exception:
            assets = {}
    elif not isinstance(assets, dict):
        assets = {}

    # Build Notion page properties
    properties = {
        "Title": {
            "title": [{"text": {"content": title[:2000]}}]
        },
    }

    # URL property (only if it's a valid http/https URL)
    if url and url.startswith(("http://", "https://")):
        properties["URL"] = {"url": url}

    # Status as select
    status_map = {
        "to_read": "Idea", "to_test": "Researching", "testing": "Researching",
        "researching": "Researching", "script_ready": "Script Ready",
        "recording": "Recording", "published": "Published", "archived": "Archived",
        "useful": "Published", "discarded": "Archived",
    }
    status_label = status_map.get(status, status.replace("_", " ").title())
    properties["Status"] = {
        "select": {"name": status_label},
    }

    # Format as select
    format_map = {
        "video": "YouTube Long", "short": "YouTube Short", "youtube_short": "YouTube Short",
        "podcast": "Podcast", "blog": "Blog", "newsletter": "Newsletter",
    }
    if fmt:
        fmt_label = format_map.get(fmt, fmt)
        properties["Format"] = {
            "select": {"name": fmt_label},
        }

    # Scores as separate numbers
    if signal_score:
        properties["Signal Score"] = {"number": float(signal_score)}
    if creator_score:
        properties["Creator Score"] = {"number": float(creator_score)}

    # Source as rich text
    if source:
        properties["Source"] = {"rich_text": [{"text": {"content": source[:2000]}}]}

    # Hook as rich text
    if hook:
        properties["Hook"] = {"rich_text": [{"text": {"content": hook[:2000]}}]}

    # Category as multi-select
    if category:
        categories = [c.strip() for c in category.split(",") if c.strip()]
        properties["Category"] = {
            "multi_select": [{"name": c[:100]} for c in categories[:5]]
        }

    # Notes as rich text
    if notes:
        properties["Notes"] = {
            "rich_text": [{"text": {"content": notes[:2000]}}]
        }

    # Build page body (content blocks)
    children = []

    # Header block
    children.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "📋 DailyDex Brief"}}]
        }
    })

    # Source link (only for valid URLs)
    if url and url.startswith(("http://", "https://")):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "Source: "}},
                    {"type": "text", "text": {"content": url, "link": {"url": url}}},
                ]
            }
        })
    elif url:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"Source: {url}"}},
                ]
            }
        })

    # Production assets content
    if assets:
        # Hook
        hook = assets.get("hook") or assets.get("hooks")
        if hook:
            children.append(_callout_block("🎣 Hook", hook if isinstance(hook, str) else str(hook)))

        # Key points
        key_points = assets.get("key_points") or assets.get("talking_points")
        if key_points:
            if isinstance(key_points, list):
                children.append(_heading_block("💡 Key Points"))
                for point in key_points[:10]:
                    children.append(_bullet_block(str(point)))
            elif isinstance(key_points, str):
                children.append(_callout_block("💡 Key Points", key_points))

        # Script / narrative beats
        script = assets.get("script") or assets.get("narrative_beats")
        if script:
            if isinstance(script, list):
                children.append(_heading_block("🎬 Narrative Beats"))
                for beat in script[:10]:
                    children.append(_numbered_block(str(beat)))
            elif isinstance(script, str):
                children.append(_heading_block("🎬 Script"))
                # Split long text into chunks (Notion max 2000 chars per block)
                for chunk in _chunk_text(script, 1900):
                    children.append(_paragraph_block(chunk))

        # Thumbnail concepts
        thumb = assets.get("thumbnail_text") or assets.get("thumbnail_visuals")
        if thumb:
            children.append(_callout_block("🖼️ Thumbnail", str(thumb)[:2000]))

        # Titles
        titles = assets.get("titles") or assets.get("title_variants")
        if titles:
            if isinstance(titles, list):
                children.append(_heading_block("📝 Title Variants"))
                for t in titles[:6]:
                    children.append(_bullet_block(str(t)))
            elif isinstance(titles, str):
                children.append(_callout_block("📝 Titles", titles))

    # Metadata footer
    children.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })
    children.append(_paragraph_block(
        f"Synced from DailyDex • Signal: {signal_score} • Creator: {creator_score} • Status: {status}"
    ))

    # Create the page
    page_body = {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": children[:100],  # Notion max 100 blocks per create
    }

    result = _notion_request("POST", "/pages", token, body=page_body)

    if "error" in result:
        return {"error": f"Notion API error: {result['error']}"}

    notion_url = result.get("url", "")
    page_id = result.get("id", "")

    if not notion_url:
        return {"error": "Notion page created but no URL returned"}

    return {
        "success": True,
        "notion_url": notion_url,
        "page_id": page_id,
    }


# ── Block builder helpers ─────────────────────────────────────────────────────

def _heading_block(text: str) -> Dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        }
    }


def _paragraph_block(text: str) -> Dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        }
    }


def _bullet_block(text: str) -> Dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        }
    }


def _numbered_block(text: str) -> Dict:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        }
    }


def _callout_block(title: str, content: str) -> Dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [
                {"type": "text", "text": {"content": f"{title}\n{content[:1900]}"}}
            ],
            "icon": {"type": "emoji", "emoji": title[0] if title else "📌"},
        }
    }


def _chunk_text(text: str, max_len: int = 1900) -> list:
    """Split text into chunks that fit within Notion's block text limit."""
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split at a sentence boundary
        split_at = text.rfind(". ", 0, max_len)
        if split_at < max_len // 2:
            split_at = text.rfind("\n", 0, max_len)
        if split_at < max_len // 2:
            split_at = max_len
        chunks.append(text[:split_at + 1])
        text = text[split_at + 1:].lstrip()
    return chunks
