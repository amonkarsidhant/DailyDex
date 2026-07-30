from datetime import datetime, timedelta, timezone

from rescue_engine import evaluate_performance_status, generate_rescue_pack


OLD_PUBLICATION = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()


def test_evaluate_performance_status_healthy():
    res = evaluate_performance_status(
        ctr=0.05, views=500, channel_median_ctr=0.045,
        impressions=5000, published_at=OLD_PUBLICATION,
    )
    assert res["status"] == "healthy"
    assert res["needs_rescue"] is False


def test_evaluate_performance_status_low_ctr():
    res = evaluate_performance_status(
        ctr=0.02, views=300, channel_median_ctr=0.045,
        impressions=5000, published_at=OLD_PUBLICATION,
    )
    assert res["status"] == "low_ctr"
    assert res["needs_rescue"] is True


def test_evaluate_performance_status_outlier():
    res = evaluate_performance_status(
        ctr=0.08, views=2000, channel_median_ctr=0.045,
        impressions=5000, published_at=OLD_PUBLICATION,
    )
    assert res["status"] == "outlier"
    assert res["needs_rescue"] is False


def test_evaluate_performance_waits_for_real_evidence():
    assert evaluate_performance_status(ctr=None, views=500)["reason"] == "insufficient_ctr_evidence"
    recent = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    result = evaluate_performance_status(0.02, 500, impressions=5000, published_at=recent)
    assert result["status"] == "pending"
    assert result["reason"] == "awaiting_48h_window"


def test_generate_rescue_pack_success(monkeypatch):
    monkeypatch.setattr(
        "rescue_engine.query_llm",
        lambda *_args, **_kwargs: '{"titles":["Title A","Title B","Title C"],"thumbnail_prompts":["Prompt A","Prompt B"]}',
    )
    res = generate_rescue_pack("How to Build AI Agents", summary="Tutorial on local agents")
    assert res["ok"] is True
    assert res["original_title"] == "How to Build AI Agents"
    assert len(res["titles"]) == 3
    assert len(res["thumbnail_prompts"]) == 2


def test_generate_rescue_pack_rejects_malformed_model_shape(monkeypatch):
    monkeypatch.setattr("rescue_engine.query_llm", lambda *_args, **_kwargs: '{"titles":"not a list"}')
    result = generate_rescue_pack("A valid original title")
    assert result["ok"] is True
    assert len(result["titles"]) == 3
