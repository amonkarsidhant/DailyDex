"""Tests for Artificial Analysis benchmark ingestion."""

import json

from data.fetch_benchmarks import fetch_benchmarks, parse_benchmarks
from data_models import IntelligenceDB


def _dataset(name, data):
    payload = json.dumps({"@type": "Dataset", "name": name, "data": data})
    return f'<script nonce="test" type="application/ld+json">{payload}</script>'


def test_parse_benchmarks_current_artificial_analysis_payload():
    html = "".join([
        _dataset("Intelligence", [{
            "label": "Model A",
            "artificialAnalysisIntelligenceIndex": 42.5,
        }]),
        _dataset("Speed", [{
            "label": "Model A",
            "medianOutputSpeed": 123.4,
        }]),
        _dataset("Pricing: Cache Hit, Input, and Output", [{
            "label": "Model A",
            "pricing": [
                {"name": "inputPrice", "value": 0.5},
                {"name": "outputPrice", "value": 1.25},
            ],
        }]),
    ])

    assert parse_benchmarks(html) == {
        "Model A": {"intelligence": 42.5, "speed": 123.4, "price": 1.25}
    }


def test_fetch_benchmarks_persists_to_supplied_database(tmp_path, monkeypatch):
    html = _dataset("Intelligence", [{
        "label": "Model A",
        "artificialAnalysisIntelligenceIndex": 42.5,
    }])

    class Response:
        text = html

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "data.fetch_benchmarks.requests.get",
        lambda *args, **kwargs: Response(),
    )
    db = IntelligenceDB(str(tmp_path / "benchmarks.db"))

    assert fetch_benchmarks(db=db) == 1
    assert db.get_ai_benchmarks()[0]["model_name"] == "Model A"
