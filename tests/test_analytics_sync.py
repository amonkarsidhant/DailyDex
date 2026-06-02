from analytics_sync import get_youtube_views, sync_publication_metrics

def test_scrape_youtube_views(monkeypatch):
    class MockResponse:
        def __init__(self, html):
            self.html = html
        def read(self):
            return self.html.encode('utf-8')
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    # Ensure no API key is found so it falls back to the HTML scraper we are testing
    monkeypatch.setenv("YOUTUBE_API_KEY", "")

    # 1. Test standard schema interactionCount pattern
    dummy_html_1 = '<html><head><meta itemprop="interactionCount" content="45678"></head></html>'
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: MockResponse(dummy_html_1))
    assert get_youtube_views("https://www.youtube.com/watch?v=mock1") == 45678

    # 2. Test alternative JSON-LD viewCount pattern
    dummy_html_2 = '<html><body><script>var yt = {"viewCount":"89012"};</script></body></html>'
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: MockResponse(dummy_html_2))
    assert get_youtube_views("https://www.youtube.com/watch?v=mock2") == 89012


def test_sync_publication_metrics(monkeypatch):
    class MockResponse:
        def __init__(self, html):
            self.html = html
        def read(self):
            return self.html.encode('utf-8')
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_html = '<html><head><meta itemprop="interactionCount" content="15000"></head></html>'
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: MockResponse(dummy_html))

    pub = {
        "item_id": 1,
        "platform": "youtube",
        "published_url": "https://www.youtube.com/watch?v=test"
    }

    res = sync_publication_metrics(pub)
    assert res is not None
    assert res["views"] == 15000
    assert res["impressions"] == 15000 * 12
    assert res["ctr"] == round(15000 / (15000 * 12), 4)
    assert res["status"] == "live"

    # Test completed limit > 25000
    dummy_html_completed = '<html><head><meta itemprop="interactionCount" content="30000"></head></html>'
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: MockResponse(dummy_html_completed))
    res_completed = sync_publication_metrics(pub)
    assert res_completed["status"] == "completed"
