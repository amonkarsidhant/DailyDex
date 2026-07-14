"""Tests for Artificial Analysis benchmark ingestion."""

import json

from data.fetch_benchmarks import (
    fetch_benchmarks,
    parse_benchmarks,
    parse_leaderboard_models,
)
from data_models import IntelligenceDB


def _dataset(name, data):
    payload = json.dumps({"@type": "Dataset", "name": name, "data": data})
    return f'<script nonce="test" type="application/ld+json">{payload}</script>'


def _next_payload(models):
    chunk = f'1:["$",{{"models":{json.dumps(models)}}}]'
    payload = json.dumps([1, chunk])
    return f"<script>self.__next_f.push({payload})</script>"


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


def test_parse_leaderboard_models_returns_all_active_models():
    html = _next_payload([
        {
            "name": "Model A",
            "deprecated": False,
            "intelligenceIndex": 42.5,
            "medianOutputTokensPerSecond": 123.4,
            "price1mOutputTokens": 1.25,
        },
        {
            "name": "Old Model",
            "deprecated": True,
            "intelligenceIndex": 10,
            "medianOutputTokensPerSecond": 20,
            "price1mOutputTokens": 3,
        },
        {
            "name": "Model B",
            "deprecated": False,
            "intelligenceIndex": 12,
            "medianOutputTokensPerSecond": "$undefined",
            "price1mOutputTokens": "$undefined",
        },
    ])

    assert parse_leaderboard_models(html) == {
        "Model A": {"intelligence": 42.5, "speed": 123.4, "price": 1.25},
        "Model B": {"intelligence": 12.0},
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


def test_complete_fetch_prunes_stale_models(tmp_path, monkeypatch):
    html = _next_payload([{
        "name": "Current Model",
        "deprecated": False,
        "intelligenceIndex": 42.5,
        "medianOutputTokensPerSecond": 123.4,
        "price1mOutputTokens": 1.25,
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
    db.upsert_ai_benchmark("Stale Model", intelligence=1)

    assert fetch_benchmarks(db=db) == 1
    assert [row["model_name"] for row in db.get_ai_benchmarks()] == ["Current Model"]
