#!/usr/bin/env python3
"""Deterministic source-evidence fetcher for grounded script generation.

Given a signal item, pulls REAL material from its source so downstream
script generation can only cite things that exist:

- GitHub repo URL   -> repo metadata (stars, language) + README excerpt
- Hacker News item  -> points/comments + top real commenter quotes (Algolia)
- Anything else     -> fetched page text excerpt (tags stripped)

No LLM involved. Fails soft: on any error returns an empty evidence dict
so callers degrade to ungrounded-but-honest scripts rather than crashing.
"""

from __future__ import annotations

import html
import http.client
import ipaddress
import json
import re
import socket
import ssl
import urllib.parse
from typing import Any, Dict, List, Optional

_UA = "Mozilla/5.0 (DailyDex evidence fetcher)"
_TIMEOUT = 12
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024

def _empty(error: str = "") -> Dict[str, Any]:
    return {
        "url": "", "source_kind": "", "facts": [], "quotes": [], "excerpt": "",
        "error": error,
    }


def _validate_public_url(url: str):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP(S) evidence URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("Credentialed evidence URLs are not allowed")
    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(
                parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as exc:
        raise ValueError("Evidence host could not be resolved") from exc
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise ValueError("Private or reserved evidence hosts are not allowed")
    return parsed, sorted(addresses)[0]


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, pinned_ip: str, **kwargs):
        self._pinned_ip = pinned_ip
        super().__init__(host, **kwargs)

    def connect(self):
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, pinned_ip: str, **kwargs):
        self._pinned_ip = pinned_ip
        super().__init__(host, context=ssl.create_default_context(), **kwargs)

    def connect(self):
        raw_socket = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address,
        )
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _get(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    current_url = url
    for _ in range(5):
        parsed, pinned_ip = _validate_public_url(current_url)
        request_headers = {"User-Agent": _UA, "Accept-Encoding": "identity"}
        if headers:
            request_headers.update(headers)
        connection_class = _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
        connection = connection_class(
            parsed.hostname, pinned_ip, port=parsed.port, timeout=_TIMEOUT,
        )
        target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        try:
            connection.request("GET", target, headers=request_headers)
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Evidence redirect did not include a destination")
                current_url = urllib.parse.urljoin(current_url, location)
                continue
            if not 200 <= response.status < 300:
                raise ValueError(f"Evidence source returned HTTP {response.status}")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError("Evidence response exceeded the size limit")
            return raw.decode("utf-8", errors="ignore")
        finally:
            connection.close()
    raise ValueError("Evidence source exceeded the redirect limit")


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = html.unescape(raw)
    return re.sub(r"\s+", " ", text).strip()


def _github_evidence(url: str) -> Dict[str, Any]:
    m = re.search(r"github\.com/([\w.-]+)/([\w.-]+)", url)
    if not m:
        return _empty("Invalid GitHub repository URL")
    owner, repo = m.group(1), m.group(2).removesuffix(".git")

    facts: List[str] = []
    excerpt = ""
    api_headers = {"Accept": "application/vnd.github+json"}

    try:
        meta = json.loads(_get(f"https://api.github.com/repos/{owner}/{repo}", api_headers))
        if meta.get("description"):
            facts.append(f"Repo description: {meta['description']}")
        if meta.get("stargazers_count") is not None:
            facts.append(f"{meta['stargazers_count']} GitHub stars")
        if meta.get("language"):
            facts.append(f"Primary language: {meta['language']}")
        if meta.get("license", {}) and meta["license"].get("spdx_id") not in (None, "NOASSERTION"):
            facts.append(f"License: {meta['license']['spdx_id']}")
    except Exception as exc:
        metadata_error = str(exc)
    else:
        metadata_error = ""

    try:
        readme = json.loads(_get(f"https://api.github.com/repos/{owner}/{repo}/readme", api_headers))
        import base64

        raw = base64.b64decode(readme.get("content", "")).decode("utf-8", errors="ignore")
        # Drop badge/link noise lines, keep prose
        lines = [l.strip() for l in raw.splitlines()
                 if l.strip() and not l.strip().startswith(("[![", "![", "<", "|"))]
        excerpt = " ".join(lines)[:2500]
    except Exception as exc:
        readme_error = str(exc)
    else:
        readme_error = ""

    if not excerpt:
        try:
            page_text = _strip_html(_get(url))
            if len(page_text) >= 200:
                excerpt = page_text[:2500]
        except Exception as exc:
            page_error = str(exc)
        else:
            page_error = ""
    else:
        page_error = ""

    error = "" if facts or excerpt else metadata_error or readme_error or page_error or "GitHub evidence unavailable"
    return {"url": url, "source_kind": "github", "facts": facts, "quotes": [], "excerpt": excerpt, "error": error}


def _hackernews_evidence(url: str) -> Dict[str, Any]:
    m = re.search(r"id=(\d+)", url)
    if not m:
        return _empty("Invalid Hacker News URL")
    story_id = m.group(1)

    facts: List[str] = []
    quotes: List[str] = []
    excerpt = ""
    try:
        data = json.loads(_get(f"https://hn.algolia.com/api/v1/items/{story_id}"))
        points = data.get("points")
        if points is not None:
            facts.append(f"{points} points on Hacker News")
        children = data.get("children") or []
        facts.append(f"{len(children)} top-level comments")

        def _comment_texts(nodes, depth=0):
            for node in nodes:
                text = _strip_html(node.get("text") or "")
                if 80 <= len(text) <= 400:
                    yield text
                if depth < 1:
                    yield from _comment_texts(node.get("children") or [], depth + 1)

        quotes = list(_comment_texts(children))[:4]
        story_text = _strip_html(data.get("text") or "")
        if story_text:
            excerpt = story_text[:2000]
    except Exception as exc:
        fetch_error = str(exc)
    else:
        fetch_error = ""

    error = "" if facts or quotes or excerpt else fetch_error or "Hacker News evidence unavailable"
    return {"url": url, "source_kind": "hackernews", "facts": facts, "quotes": quotes, "excerpt": excerpt, "error": error}


def _article_evidence(url: str) -> Dict[str, Any]:
    try:
        text = _strip_html(_get(url))
    except Exception as exc:
        return _empty(str(exc)[:300])
    if len(text) < 200:
        return _empty("Evidence page did not contain enough readable text")
    return {"url": url, "source_kind": "article", "facts": [], "quotes": [], "excerpt": text[:2500], "error": ""}


def _youtube_evidence(url: str) -> Dict[str, Any]:
    try:
        raw = _get(url)
    except Exception as exc:
        return _empty(str(exc)[:300])

    def field(name: str) -> str:
        match = re.search(rf'"{name}":"((?:\\.|[^"\\])*)"', raw)
        if not match:
            return ""
        try:
            return json.loads(f'"{match.group(1)}"')
        except (TypeError, ValueError):
            return ""

    title = field("title")
    channel = field("ownerChannelName") or field("author")
    description = field("shortDescription")
    view_count = field("viewCount")
    facts = []
    if title:
        facts.append(f"Video title: {title}")
    if channel:
        facts.append(f"Published by: {channel}")
    if view_count.isdigit():
        facts.append(f"{int(view_count):,} YouTube views at fetch time")
    error = "" if facts or description else "YouTube did not expose readable video metadata"
    return {
        "url": url, "source_kind": "youtube", "facts": facts,
        "quotes": [], "excerpt": description[:2500], "error": error,
    }


def gather_evidence(item: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch real evidence for an item. Tries the external URL first, then the
    discussion URL (HN), so scripts can cite both the artifact and the debate."""
    urls = [u for u in (item.get("external_url"), item.get("url")) if u]
    if not urls:
        return _empty()

    merged = _empty()
    for url in urls:
        host = urllib.parse.urlparse(url).netloc.lower()
        if host == "github.com" or host.endswith(".github.com"):
            result = _github_evidence(url)
        elif "news.ycombinator.com" in host:
            result = _hackernews_evidence(url)
        elif host in {"youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be"}:
            result = _youtube_evidence(url)
        else:
            result = _article_evidence(url)

        merged["facts"].extend(result["facts"])
        merged["quotes"].extend(result["quotes"])
        if result["excerpt"] and not merged["excerpt"]:
            merged["excerpt"] = result["excerpt"]
            merged["source_kind"] = result["source_kind"]
            merged["url"] = result["url"]
        elif result["facts"] and not merged["url"]:
            merged["source_kind"] = result["source_kind"]
            merged["url"] = result["url"]

    if not (merged["facts"] or merged["quotes"] or merged["excerpt"]):
        merged["error"] = "No source could be retrieved safely"

    return merged
