import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import fetch_news


def test_cache_save_load_and_stale_detection(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(fetch_news, "CACHE_DIR", str(cache_dir))

    items = [{"title": "cached item", "url": "https://example.com/cached"}]
    fetch_news.save_source_cache("github", items)

    loaded_items, is_fresh = fetch_news.load_source_cache("github")
    assert loaded_items == items
    assert is_fresh is True

    stale_file = cache_dir / "blogs.json"
    stale_file.write_text(
        json.dumps({"items": items, "cached_at": "2020-01-01T00:00:00"}),
        encoding="utf-8",
    )
    stale_items, stale_fresh = fetch_news.load_source_cache("blogs")
    assert stale_items == items
    assert stale_fresh is False


def test_fetch_news_main_writes_data_file(tmp_path):
    repo_dir = Path(__file__).resolve().parent
    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    (stub_dir / "requests.py").write_text(
        """
class Response:
    def __init__(self, text='', json_data=None, status_code=200):
        self.text = text
        self._json = json_data
        self.status_code = status_code
    def raise_for_status(self):
        return None
    def json(self):
        return self._json

def get(url, headers=None, timeout=None):
    if 'huggingface.co/api/models' in url:
        return Response(json_data=[{'id': 'acme/model', 'downloads': 123, 'likes': 4}])
    if 'hacker-news.firebaseio.com' in url:
        if 'topstories.json' in url:
            return Response(json_data=[101, 102])
        elif 'item/101.json' in url:
            return Response(json_data={'id': 101, 'type': 'story', 'title': 'Show HN: LLM agent framework', 'url': 'https://github.com/agent', 'score': 150, 'time': 1779830000})
        elif 'item/102.json' in url:
            return Response(json_data={'id': 102, 'type': 'story', 'title': 'Unrelated story', 'url': 'https://example.com', 'score': 10, 'time': 1779830000})
        return Response(json_data=None, status_code=404)
    return Response(text='<article class="Box-row"><h2><a class="Link" href="/acme/repo">acme/repo</a></h2><p>AI repo</p><a class="Link--muted">123 stars today</a><span itemprop="programmingLanguage">Python</span></article>')
""",
        encoding="utf-8",
    )
    (stub_dir / "feedparser.py").write_text(
        """
class Entry(dict):
    __getattr__ = dict.get

class Author:
    def __init__(self, name):
        self.name = name

class Tag:
    def __init__(self, term):
        self.term = term

class Feed:
    def __init__(self, entries):
        self.entries = entries

def parse(url):
    if 'arxiv' in url:
        return Feed([Entry({
            'link': 'https://arxiv.org/abs/1234.5678',
            'title': 'Agent Paper',
            'published': '2026-04-28T00:00:00',
            'summary': 'Agentic workflows paper',
            'authors': [Author('A. Researcher')],
            'tags': [Tag('cs.AI')],
        })])
    return Feed([Entry({
        'title': 'Blog Post',
        'link': 'https://example.com/post',
        'published': '2026-04-28T00:00:00',
    })])
""",
        encoding="utf-8",
    )
    (stub_dir / "yt_dlp.py").write_text(
        """
class YoutubeDL:
    def __init__(self, opts):
        self.opts = opts
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def extract_info(self, url, download=False):
        return {'entries': [{'id': 'abc123', 'title': 'Agent Video', 'description': 'Practical agent workflow'}]}
""",
        encoding="utf-8",
    )

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "youtube": {"channels": [{"name": "Test", "url": "https://youtube.com/@test"}]},
                "github": {"url": "https://github.com/trending?since=weekly", "limit": 1},
                "huggingface": {"limit": 1},
                "blogs": [{"name": "Test Blog", "url": "https://example.com/feed"}],
                "arxiv": {"limit": 1},
            }
        ),
        encoding="utf-8",
    )

    data_dir = tmp_path / "data"
    cache_dir = data_dir / "cache"
    data_dir.mkdir()
    cache_dir.mkdir()
    data_file = data_dir / "data.json"
    db_path = data_dir / "intelligence.db"

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": os.pathsep.join([str(stub_dir), str(repo_dir)]),
            "CONFIG_FILE": str(config_path),
            "DATA_DIR": str(data_dir),
            "CACHE_DIR": str(cache_dir),
            "DATA_FILE": str(data_file),
            "DB_PATH": str(db_path),
        }
    )

    result = subprocess.run(
        [sys.executable, str(repo_dir / "fetch_news.py")],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert data_file.exists()

    data = json.loads(data_file.read_text(encoding="utf-8"))
    assert len(data["youtube"]) == 1
    assert len(data["github"]) == 1
    assert len(data["huggingface"]) == 1
    assert len(data["blogs"]) == 1
    assert len(data["papers"]) == 1
    assert len(data["hackernews"]) == 1

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM source_health").fetchone()[0]
    conn.close()
    assert count == 6
