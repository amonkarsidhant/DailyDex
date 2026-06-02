import json
import traceback
from unittest.mock import MagicMock, patch

import pytest

import refresh_job

@patch.object(refresh_job, "fetch_all")
@patch.object(refresh_job.dd, "load_scored_data")
@patch.object(refresh_job, "snapshot_clusters")
def test_main_success(mock_snapshot, mock_load, mock_fetch, capsys):
    mock_load.return_value = {
        "github": [{}, {}],
        "huggingface": [{}],
        "youtube": [],
        "blogs": [{}],
        "papers": [],
        "hackernews": [{}, {}]
    }
    
    # Fake DB
    refresh_job.dd.intel_db = MagicMock()
    
    exit_code = refresh_job.main()
    
    # Assert successful orchestration
    assert exit_code == 0
    mock_fetch.assert_called_once()
    mock_load.assert_called_with(force=True)
    mock_snapshot.assert_called_once_with(mock_load.return_value, refresh_job.dd.intel_db)
    
    # Assert logs
    captured = capsys.readouterr()
    assert "[refresh_job] start" in captured.out
    assert "[refresh_job] cluster snapshot written" in captured.out
    assert "done — 6 scored items" in captured.out

@patch.object(refresh_job, "fetch_all")
def test_main_failure(mock_fetch, capsys):
    mock_fetch.side_effect = Exception("Fetch completely broke")
    
    exit_code = refresh_job.main()
    
    # Assert handles exception gracefully returning 1
    assert exit_code == 1
    mock_fetch.assert_called_once()
    
    # Assert logs
    captured = capsys.readouterr()
    assert "[refresh_job] FAILED:" in captured.out
    assert "Fetch completely broke" in captured.out
