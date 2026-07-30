#!/usr/bin/env python3
"""
youtube_oauth.py — YouTube OAuth2 Integration
-----------------------------------------------
Real Google OAuth2 flow for DailyDex, enabling channel-owner operations
that require user consent (uploads, analytics, Studio features).

Uses urllib exclusively (no requests library) — matches project conventions.

OAuth2 endpoints:
  Authorization:  https://accounts.google.com/o/oauth2/v2/auth
  Token exchange: https://oauth2.googleapis.com/token
  User info:      https://www.googleapis.com/oauth2/v2/userinfo

Required scopes:
  - openid email profile
  - youtube.readonly   (channel info)
  - youtube.upload     (video uploads)
  - yt-analytics.readonly (video analytics)

Keys stored via settings_manager:
  google_client_id, google_client_secret   → user-provided
  google_access_token, google_refresh_token, google_token_expiry → auto-managed
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

# ── Constants ─────────────────────────────────────────────────────────────────

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_YT_DATA_BASE = "https://www.googleapis.com/youtube/v3"
_YT_ANALYTICS_BASE = "https://youtubeanalytics.googleapis.com/v2/reports"
_YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

_DEFAULT_REDIRECT_URI = "http://localhost:8888/api/integrations/youtube/callback"

_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
])

_USER_AGENT = "DailyDex/1.0"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_setting(key: str) -> str:
    """Resolve a setting value: env var > settings file."""
    env_map = {
        "google_client_id": "GOOGLE_CLIENT_ID",
        "google_client_secret": "GOOGLE_CLIENT_SECRET",
        "google_access_token": "GOOGLE_ACCESS_TOKEN",
        "google_refresh_token": "GOOGLE_REFRESH_TOKEN",
        "google_token_expiry": "GOOGLE_TOKEN_EXPIRY",
    }
    env_val = os.environ.get(env_map.get(key, ""), "")
    if env_val:
        return env_val
    try:
        from settings_manager import get as settings_get
        return settings_get(key)
    except Exception:
        return ""


def _http_request(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """
    Make an HTTP request with urllib, return parsed JSON.
    Returns {"ok": True, "data": ...} or {"ok": False, "error": ..., "status": ...}.
    """
    hdrs = {"User-Agent": _USER_AGENT}
    if headers:
        hdrs.update(headers)

    req = urllib.request.Request(url, method=method, headers=hdrs, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body}
            return {"ok": True, "data": parsed, "status": resp.status}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        try:
            err_data = json.loads(body)
        except Exception:
            err_data = {"raw": body}
        return {"ok": False, "error": err_data, "status": e.code}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"Connection error: {e.reason}", "status": 0}
    except Exception as e:
        return {"ok": False, "error": f"Unexpected error: {e}", "status": 0}


def _form_post(url: str, params: Dict[str, str], timeout: int = 15) -> Dict[str, Any]:
    """POST application/x-www-form-urlencoded — used for token endpoints."""
    encoded = urllib.parse.urlencode(params).encode("utf-8")
    return _http_request(
        url,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=encoded,
        timeout=timeout,
    )


def _is_token_expired() -> bool:
    """Check whether the stored access token has expired (with 60s buffer)."""
    expiry_str = _get_setting("google_token_expiry")
    if not expiry_str:
        return True
    try:
        return time.time() >= (float(expiry_str) - 60)
    except (ValueError, TypeError):
        return True


def _ensure_valid_token(access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Ensure we have a valid access token. If the current one is expired,
    attempt a refresh. Returns {"ok": True, "access_token": ...} or error dict.
    """
    token = access_token or _get_setting("google_access_token")
    if not token:
        return {"ok": False, "error": "No Google access token configured. Complete the OAuth flow first."}

    if access_token:
        # Caller supplied an explicit token — trust it
        return {"ok": True, "access_token": token}

    if not _is_token_expired():
        return {"ok": True, "access_token": token}

    # Token expired → try refresh
    refresh_tok = _get_setting("google_refresh_token")
    if not refresh_tok:
        return {"ok": False, "error": "Access token expired and no refresh token available. Re-authenticate."}

    result = refresh_access_token(refresh_tok)
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    return {"ok": True, "access_token": result["access_token"]}


def _authed_request(
    url: str,
    access_token: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Make an authenticated API request with Bearer token."""
    hdrs = {"Authorization": f"Bearer {access_token}"}
    if headers:
        hdrs.update(headers)
    return _http_request(url, method=method, headers=hdrs, data=data, timeout=timeout)


# ── Public API — OAuth2 flow ──────────────────────────────────────────────────

def get_auth_url(
    provider: str = "google",
    *,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
) -> str:
    """
    Returns the OAuth2 authorization URL for Google.

    The user should be redirected to this URL. After consent, Google redirects
    back to the callback URI with an authorization code.

    Parameters
    ----------
    provider : str
        Only ``"google"`` is currently supported.

    Returns
    -------
    str
        The full authorization URL, or an error message string starting with
        ``"error:"``.
    """
    if provider != "google":
        return f"error: Unsupported provider '{provider}'. Only 'google' is supported."

    client_id = _get_setting("google_client_id")
    if not client_id:
        return "error: google_client_id not configured. Set it in Settings → Google OAuth."

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri or os.environ.get("GOOGLE_REDIRECT_URI", _DEFAULT_REDIRECT_URI),
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",       # Request refresh_token
        "prompt": "consent",            # Force consent to always get refresh_token
        "include_granted_scopes": "true",
    }
    if state:
        params["state"] = state
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, *, redirect_uri: Optional[str] = None) -> dict:
    """
    Exchange an authorization code for access + refresh tokens.

    Parameters
    ----------
    code : str
        The authorization code from the OAuth callback.

    Returns
    -------
    dict
        ``{"access_token": ..., "refresh_token": ..., "expires_in": ..., "token_type": ...}``
        on success, or ``{"error": "..."}`` on failure.
    """
    if not code:
        return {"error": "Authorization code is required."}

    client_id = _get_setting("google_client_id")
    client_secret = _get_setting("google_client_secret")

    if not client_id or not client_secret:
        return {"error": "google_client_id and google_client_secret must be configured."}

    result = _form_post(_TOKEN_URL, {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri or os.environ.get("GOOGLE_REDIRECT_URI", _DEFAULT_REDIRECT_URI),
        "grant_type": "authorization_code",
    })

    if not result["ok"]:
        err = result.get("error", {})
        if isinstance(err, dict):
            detail = err.get("error_description", err.get("error", str(err)))
        else:
            detail = str(err)
        return {"error": f"Token exchange failed: {detail}"}

    data = result["data"]
    access_token = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")
    expires_in = data.get("expires_in", 3600)

    if not access_token:
        return {"error": "Token exchange succeeded without an access token."}

    try:
        from settings_manager import update as settings_update
        token_updates = {
            "google_access_token": access_token,
            "google_token_expiry": str(int(time.time()) + int(expires_in)),
        }
        if refresh_token:
            token_updates["google_refresh_token"] = refresh_token
        settings_update(token_updates)
    except Exception as exc:
        return {"error": f"Could not persist OAuth tokens: {exc}"}

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "token_type": data.get("token_type", "Bearer"),
    }


def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh an expired access token using a refresh token.

    Parameters
    ----------
    refresh_token : str
        The stored refresh token.

    Returns
    -------
    dict
        ``{"access_token": ..., "expires_in": ..., "token_type": ...}``
        on success, or ``{"error": "..."}`` on failure.
    """
    if not refresh_token:
        return {"error": "Refresh token is required."}

    client_id = _get_setting("google_client_id")
    client_secret = _get_setting("google_client_secret")

    if not client_id or not client_secret:
        return {"error": "google_client_id and google_client_secret must be configured."}

    result = _form_post(_TOKEN_URL, {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    })

    if not result["ok"]:
        err = result.get("error", {})
        if isinstance(err, dict):
            detail = err.get("error_description", err.get("error", str(err)))
        else:
            detail = str(err)
        return {"error": f"Token refresh failed: {detail}"}

    data = result["data"]
    access_token = data.get("access_token", "")
    expires_in = data.get("expires_in", 3600)

    # Persist new access token and expiry
    try:
        from settings_manager import update as settings_update
        settings_update({
            "google_access_token": access_token,
            "google_token_expiry": str(int(time.time()) + int(expires_in)),
        })
    except Exception as exc:
        return {"error": f"Could not persist refreshed OAuth token: {exc}"}

    return {
        "access_token": access_token,
        "expires_in": expires_in,
        "token_type": data.get("token_type", "Bearer"),
    }


# ── Public API — User & channel info ─────────────────────────────────────────

def get_user_info(access_token: str) -> dict:
    """
    Get the authenticated Google user's profile.

    Parameters
    ----------
    access_token : str
        A valid Google OAuth2 access token.

    Returns
    -------
    dict
        ``{"name": ..., "email": ..., "picture": ...}`` on success,
        or ``{"error": "..."}`` on failure.
    """
    token_check = _ensure_valid_token(access_token)
    if not token_check.get("ok"):
        return {"error": token_check.get("error", "Token validation failed.")}
    token = token_check["access_token"]

    result = _authed_request(_USERINFO_URL, token)
    if not result["ok"]:
        return {"error": f"Failed to fetch user info (HTTP {result['status']}): {result.get('error')}"}

    data = result["data"]
    return {
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "picture": data.get("picture", ""),
        "id": data.get("id", ""),
        "verified_email": data.get("verified_email", False),
    }


def get_channel_info(access_token: str) -> dict:
    """
    Get the authenticated user's YouTube channel info.

    Uses ``channels.list?part=snippet,statistics&mine=true``.

    Parameters
    ----------
    access_token : str
        A valid Google OAuth2 access token with ``youtube.readonly`` scope.

    Returns
    -------
    dict
        ``{"channel_name": ..., "channel_id": ..., "subscriber_count": ...,
        "video_count": ..., "thumbnail": ..., "description": ...}``
        on success, or ``{"error": "..."}`` on failure.
    """
    token_check = _ensure_valid_token(access_token)
    if not token_check.get("ok"):
        return {"error": token_check.get("error", "Token validation failed.")}
    token = token_check["access_token"]

    url = f"{_YT_DATA_BASE}/channels?part=snippet,statistics&mine=true"
    result = _authed_request(url, token)

    if not result["ok"]:
        return {"error": f"Failed to fetch channel info (HTTP {result['status']}): {result.get('error')}"}

    data = result["data"]
    items = data.get("items", [])
    if not items:
        return {"error": "No YouTube channel found for this account."}

    channel = items[0]
    snippet = channel.get("snippet", {})
    stats = channel.get("statistics", {})

    return {
        "channel_name": snippet.get("title", ""),
        "channel_id": channel.get("id", ""),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "view_count": int(stats.get("viewCount", 0)),
        "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
        "description": snippet.get("description", ""),
        "custom_url": snippet.get("customUrl", ""),
    }


# ── Public API — Video analytics ─────────────────────────────────────────────

def get_video_analytics(access_token: Optional[str], video_id: str) -> dict:
    """
    Get real analytics from the YouTube Analytics API for a specific video.

    Fetches the metrics supported by the targeted YouTube Analytics API.
    Thumbnail impressions and CTR are intentionally returned as unavailable;
    Google exposes those through asynchronous bulk Reporting API reports.

    Parameters
    ----------
    access_token : str
        A valid Google OAuth2 access token with ``yt-analytics.readonly`` scope.
    video_id : str
        The YouTube video ID (11-char string).

    Returns
    -------
    dict
        ``{"video_id": ..., "impressions": ..., "ctr": ...,
        "average_view_duration_seconds": ..., "average_view_percentage": ...,
        "views": ..., "likes": ..., "comments": ...}``
        on success, or ``{"error": "..."}`` on failure.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        return {"error": "video_id is required."}

    token_check = _ensure_valid_token(access_token)
    if not token_check.get("ok"):
        return {"error": token_check.get("error", "Token validation failed.")}
    token = token_check["access_token"]

    # YouTube Analytics API requires a date range — use a wide window
    params = urllib.parse.urlencode({
        "ids": "channel==MINE",
        "startDate": "2000-01-01",
        "endDate": time.strftime("%Y-%m-%d"),
        "metrics": "views,likes,comments,averageViewDuration,averageViewPercentage",
        "dimensions": "video",
        "filters": f"video=={video_id}",
    })
    url = f"{_YT_ANALYTICS_BASE}?{params}"
    result = _authed_request(url, token)

    if not result["ok"]:
        err = result.get("error", {})
        if isinstance(err, dict):
            reason = err.get("error", {}).get("message", str(err)) if isinstance(err.get("error"), dict) else str(err)
        else:
            reason = str(err)
        return {"error": f"Analytics API error (HTTP {result['status']}): {reason}"}

    data = result["data"]
    rows = data.get("rows", [])
    headers = [h.get("name", "") for h in data.get("columnHeaders", [])]

    if not rows:
        return {
            "video_id": video_id,
            "impressions": None,
            "ctr": None,
            "average_view_duration_seconds": 0,
            "average_view_percentage": 0.0,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "note": "No analytics data available yet — data may take 48-72h to appear.",
        }

    # Map column headers to row values
    row = rows[0]
    col_map = {}
    for i, header_name in enumerate(headers):
        if i < len(row):
            col_map[header_name] = row[i]

    return {
        "video_id": video_id,
        "views": int(col_map.get("views", 0)),
        "likes": int(col_map.get("likes", 0)),
        "comments": int(col_map.get("comments", 0)),
        "impressions": None,
        "ctr": None,
        "average_view_duration_seconds": int(col_map.get("averageViewDuration", 0)),
        "average_view_percentage": round(float(col_map.get("averageViewPercentage", 0)), 2),
    }


# ── Public API — Video upload ────────────────────────────────────────────────

def upload_video(
    access_token: str,
    title: str,
    description: str,
    file_path: str,
    privacy: str = "unlisted",
    is_short: bool = False,
) -> dict:
    """
    Upload a video to YouTube using the resumable upload protocol.

    Parameters
    ----------
    access_token : str
        A valid Google OAuth2 access token with ``youtube.upload`` scope.
    title : str
        Video title (max 100 chars).
    description : str
        Video description (max 5000 chars).
    file_path : str
        Absolute path to the video file.
    privacy : str
        Privacy status: ``"public"``, ``"unlisted"``, or ``"private"``.
    is_short : bool
        If True, adds ``#Shorts`` to the title (if not already present).

    Returns
    -------
    dict
        ``{"video_id": ..., "url": ...}`` on success,
        or ``{"error": "..."}`` on failure.
    """
    # ── Validate inputs ──────────────────────────────────────────────────
    if not title:
        return {"error": "Video title is required."}

    video_path = Path(file_path)
    if not video_path.exists():
        return {"error": f"Video file not found: {file_path}"}
    if not video_path.is_file():
        return {"error": f"Path is not a file: {file_path}"}

    file_size = video_path.stat().st_size
    if file_size == 0:
        return {"error": "Video file is empty."}
    # YouTube max: 256 GB, but urllib can't reasonably handle that
    if file_size > 64 * 1024 * 1024 * 1024:  # 64 GB practical limit
        return {"error": "Video file exceeds 64 GB limit."}

    if privacy not in ("public", "unlisted", "private"):
        return {"error": f"Invalid privacy setting: '{privacy}'. Use public, unlisted, or private."}

    token_check = _ensure_valid_token(access_token)
    if not token_check.get("ok"):
        return {"error": token_check.get("error", "Token validation failed.")}
    token = token_check["access_token"]

    # ── Prepare metadata ─────────────────────────────────────────────────
    if is_short and "#Shorts" not in title:
        title = f"{title} #Shorts"

    # Clamp lengths
    title = title[:100]
    description = (description or "")[:5000]

    mime_type = mimetypes.guess_type(str(video_path))[0] or "video/mp4"

    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22",  # People & Blogs (safe default)
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    # ── Step 1: Initiate resumable upload ────────────────────────────────
    init_url = (
        f"{_YT_UPLOAD_URL}"
        f"?uploadType=resumable"
        f"&part=snippet,status"
    )
    metadata_bytes = json.dumps(metadata).encode("utf-8")
    init_req = urllib.request.Request(
        init_url,
        method="POST",
        data=metadata_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(file_size),
            "X-Upload-Content-Type": mime_type,
            "User-Agent": _USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(init_req, timeout=30) as resp:
            upload_url = resp.headers.get("Location")
            if not upload_url:
                return {"error": "Resumable upload initiation failed — no upload URL returned."}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        return {"error": f"Upload initiation failed (HTTP {e.code}): {body[:300]}"}
    except Exception as e:
        return {"error": f"Upload initiation error: {e}"}

    # ── Step 2: Upload the file content ──────────────────────────────────
    # Read the entire file into memory — acceptable for most creator videos
    # (typically < 2 GB). For very large files a chunked approach is needed.
    try:
        file_data = video_path.read_bytes()
    except Exception as e:
        return {"error": f"Could not read video file: {e}"}

    upload_req = urllib.request.Request(
        upload_url,
        method="PUT",
        data=file_data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": mime_type,
            "Content-Length": str(file_size),
            "User-Agent": _USER_AGENT,
        },
    )

    try:
        # Upload timeout scales with file size (1 MB/s minimum assumed)
        upload_timeout = max(300, file_size // (1024 * 1024) * 5)
        with urllib.request.urlopen(upload_req, timeout=upload_timeout) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            try:
                resp_data = json.loads(resp_body)
            except json.JSONDecodeError:
                return {"error": f"Upload succeeded but response was not JSON: {resp_body[:200]}"}

            vid_id = resp_data.get("id", "")
            return {
                "video_id": vid_id,
                "url": f"https://www.youtube.com/watch?v={vid_id}" if vid_id else "",
                "title": resp_data.get("snippet", {}).get("title", title),
                "privacy": resp_data.get("status", {}).get("privacyStatus", privacy),
            }
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        return {"error": f"Video upload failed (HTTP {e.code}): {body[:300]}"}
    except Exception as e:
        return {"error": f"Video upload error: {e}"}


def update_video_title(
    access_token: Optional[str],
    video_id: str,
    new_title: str,
) -> dict:
    """
    Update a video's title on YouTube using YouTube Data API v3 (videos.update).
    Requires 'youtube' or 'youtube.force-ssl' scope.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or "") or not new_title:
        return {"error": "video_id and new_title are required."}

    token_check = _ensure_valid_token(access_token)
    if not token_check.get("ok"):
        return {"error": token_check.get("error", "Token validation failed.")}
    token = token_check["access_token"]

    current_url = f"{_YT_DATA_BASE}/videos?part=snippet&id={urllib.parse.quote(video_id)}"
    current = _authed_request(current_url, token)
    if not current.get("ok"):
        return {"error": f"Could not load current video metadata: {current.get('error')}"}
    items = current.get("data", {}).get("items", [])
    if len(items) != 1:
        return {"error": "Video was not found on the connected YouTube channel."}

    existing = items[0].get("snippet") or {}
    snippet = {
        "title": new_title.strip()[:100],
        "categoryId": existing.get("categoryId"),
        "description": existing.get("description", ""),
    }
    for key in ("tags", "defaultLanguage"):
        if key in existing:
            snippet[key] = existing[key]
    if not snippet["categoryId"]:
        return {"error": "Current video metadata did not include a category."}

    url = f"{_YT_DATA_BASE}/videos?part=snippet"
    payload = {
        "id": video_id,
        "snippet": snippet,
    }

    req_data = json.dumps(payload).encode("utf-8")
    resp = _http_request(
        url,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        data=req_data,
    )

    if not resp.get("ok"):
        return {"error": f"Failed to update title: {resp.get('error')}"}

    data = resp.get("data", {})
    return {
        "ok": True,
        "video_id": data.get("id", video_id),
        "title": data.get("snippet", {}).get("title", new_title),
    }
