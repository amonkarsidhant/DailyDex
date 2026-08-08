"""LinkedIn document posts — publishing a rendered carousel PDF.

LinkedIn treats a carousel as a *document* post, which is a three-step dance:

  1. POST /rest/documents?action=initializeUpload  -> an upload URL + document URN
  2. PUT the PDF bytes to that upload URL           -> no JSON body comes back
  3. POST /rest/posts referencing the document URN  -> the post goes live

Requires an app with the ``w_member_social`` scope. The author URN comes from
the OpenID ``userinfo`` endpoint, so the token also needs ``openid``/``profile``.

Nothing here is called by the orchestrator or the factory. Publishing is a
public, irreversible act and stays an explicit request.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

API_BASE = os.environ.get("LINKEDIN_API_BASE", "https://api.linkedin.com")
# LinkedIn pins behaviour to a dated version header and retires old ones, so
# this is configurable rather than baked in.
API_VERSION = os.environ.get("LINKEDIN_API_VERSION", "202405")
_USER_AGENT = "DailyDex/1.0"

# LinkedIn allows far more, but a rendered deck is a few hundred KB and the
# whole file is held in memory during upload on a box that also runs Chromium.
MAX_PDF_BYTES = int(os.environ.get("LINKEDIN_MAX_PDF_BYTES", 25 * 1024 * 1024))
MAX_COMMENTARY_CHARS = 3000

VALID_VISIBILITY = ("PUBLIC", "CONNECTIONS", "LOGGED_IN")


def _token() -> str:
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    if token:
        return token
    try:
        import settings_manager
        return settings_manager.get("linkedin_access_token") or ""
    except Exception:
        return ""


def _headers(token: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": API_VERSION,
        "User-Agent": _USER_AGENT,
    }
    if extra:
        headers.update(extra)
    return headers


class _StripAuthOnHostChange(urllib.request.HTTPRedirectHandler):
    """Drop the bearer token when a redirect leaves the original host.

    The upload step must send Authorization — LinkedIn requires it even though
    the upload URL is issued per-request — and urllib otherwise replays every
    header on a redirect, which would hand the token to whatever host it points
    at next.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        if urllib.parse.urlsplit(newurl).netloc.lower() != \
                urllib.parse.urlsplit(req.full_url).netloc.lower():
            for header in ("Authorization", "authorization"):
                new.headers.pop(header, None)
                new.unredirected_hdrs.pop(header, None)
        return new


_opener = urllib.request.build_opener(_StripAuthOnHostChange)


def _request(url: str, *, method: str = "GET", headers: Optional[Dict[str, str]] = None,
             data: Optional[bytes] = None, timeout: int = 60) -> Dict[str, Any]:
    """Return {"ok": True, "data": ..., "headers": ...} or {"ok": False, "error": ...}."""
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with _opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body) if body.strip() else {}
            except json.JSONDecodeError:
                parsed = {"raw": body}
            return {"ok": True, "data": parsed, "status": resp.status,
                    "headers": dict(resp.headers)}
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        try:
            detail = json.loads(raw)
        except Exception:
            detail = {"raw": raw[:400]}
        return {"ok": False, "error": detail, "status": exc.code}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"Connection error: {exc.reason}", "status": 0}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"Unexpected error: {exc}", "status": 0}


def get_author_urn(token: Optional[str] = None) -> Dict[str, Any]:
    """Resolve the posting member's URN via the OpenID userinfo endpoint."""
    token = token or _token()
    if not token:
        return {"ok": False, "error": "LINKEDIN_ACCESS_TOKEN is not set"}
    result = _request(f"{API_BASE}/v2/userinfo", headers=_headers(token))
    if not result["ok"]:
        return {"ok": False, "error": result["error"], "status": result.get("status")}
    subject = (result["data"] or {}).get("sub")
    if not subject:
        return {"ok": False, "error": "userinfo returned no 'sub'; token likely lacks openid scope"}
    return {"ok": True, "urn": f"urn:li:person:{subject}",
            "name": (result["data"] or {}).get("name", "")}


def _initialize_upload(token: str, author_urn: str) -> Dict[str, Any]:
    payload = json.dumps({"initializeUploadRequest": {"owner": author_urn}}).encode("utf-8")
    result = _request(
        f"{API_BASE}/rest/documents?action=initializeUpload",
        method="POST",
        headers=_headers(token, {"Content-Type": "application/json"}),
        data=payload,
    )
    if not result["ok"]:
        return {"ok": False, "error": result["error"], "status": result.get("status")}
    value = (result["data"] or {}).get("value") or {}
    upload_url, document_urn = value.get("uploadUrl"), value.get("document")
    if not upload_url or not document_urn:
        return {"ok": False, "error": f"unexpected initializeUpload response: {result['data']}"}
    return {"ok": True, "upload_url": upload_url, "document_urn": document_urn}


def _upload_pdf(token: str, upload_url: str, pdf_path: str, timeout: int = 300) -> Dict[str, Any]:
    data = Path(pdf_path).read_bytes()
    # LinkedIn requires the bearer token on this PUT even though the URL is
    # issued per-request; _opener strips it if a redirect leaves the host.
    # The upload returns no JSON body.
    result = _request(
        upload_url,
        method="PUT",
        headers=_headers(token, {"Content-Type": "application/octet-stream"}),
        data=data,
        timeout=timeout,
    )
    if not result["ok"]:
        return {"ok": False, "error": result["error"], "status": result.get("status")}
    return {"ok": True, "bytes": len(data)}


def publish_document_post(
    pdf_path: str,
    commentary: str,
    title: str = "",
    # Least public default. The route defaults the same way; a caller reaching
    # the public feed should have to say so.
    visibility: str = "CONNECTIONS",
    token: Optional[str] = None,
    author_urn: Optional[str] = None,
) -> Dict[str, Any]:
    """Publish a PDF as a LinkedIn document post.

    Returns ``{"ok": True, "post_urn": ..., "url": ...}`` or
    ``{"ok": False, "error": ..., "stage": ...}`` naming the step that failed,
    because a partial run can leave an uploaded document with no post.
    """
    token = token or _token()
    if not token:
        return {"ok": False, "stage": "auth", "error": "LINKEDIN_ACCESS_TOKEN is not set"}

    path = Path(pdf_path)
    if not path.is_file():
        return {"ok": False, "stage": "validate", "error": f"no such file: {pdf_path}"}
    size = path.stat().st_size
    if size == 0:
        return {"ok": False, "stage": "validate", "error": "PDF is empty"}
    if size > MAX_PDF_BYTES:
        return {"ok": False, "stage": "validate",
                "error": f"PDF is {size} bytes, over LinkedIn's {MAX_PDF_BYTES} limit"}
    if not commentary or not commentary.strip():
        return {"ok": False, "stage": "validate", "error": "commentary is required"}
    if visibility not in VALID_VISIBILITY:
        return {"ok": False, "stage": "validate",
                "error": f"visibility must be one of {', '.join(VALID_VISIBILITY)}"}

    commentary = commentary.strip()[:MAX_COMMENTARY_CHARS]

    if not author_urn:
        who = get_author_urn(token)
        if not who["ok"]:
            return {"ok": False, "stage": "author", "error": who["error"]}
        author_urn = who["urn"]

    init = _initialize_upload(token, author_urn)
    if not init["ok"]:
        return {"ok": False, "stage": "initialize_upload", "error": init["error"]}

    uploaded = _upload_pdf(token, init["upload_url"], str(path))
    if not uploaded["ok"]:
        return {"ok": False, "stage": "upload", "error": uploaded["error"],
                "document_urn": init["document_urn"]}

    body = json.dumps({
        "author": author_urn,
        "commentary": commentary,
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "media": {
                "id": init["document_urn"],
                # path.stem is a uuid ("carousel-8e68a848cee3") and viewers see
                # this on the document, so fall back to the commentary's opening.
                "title": (title or commentary.split("\n")[0])[:100],
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }).encode("utf-8")

    posted = _request(
        f"{API_BASE}/rest/posts",
        method="POST",
        headers=_headers(token, {"Content-Type": "application/json"}),
        data=body,
    )
    if not posted["ok"]:
        return {"ok": False, "stage": "create_post", "error": posted["error"],
                "document_urn": init["document_urn"]}

    # The post URN comes back in a header rather than the body.
    post_urn = (posted.get("headers") or {}).get("x-restli-id") \
        or (posted.get("headers") or {}).get("X-RestLi-Id") \
        or (posted["data"] or {}).get("id", "")
    return {
        "ok": True,
        "post_urn": post_urn,
        "document_urn": init["document_urn"],
        "url": f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else "",
        "bytes": uploaded["bytes"],
        "visibility": visibility,
    }
