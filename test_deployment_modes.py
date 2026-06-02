import os
import json
import pytest
import shutil
import settings_manager
import cli_registry
import llm_summary

def test_settings_schema_extension(tmp_path, monkeypatch):
    # Use temporary settings file
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    
    # Verify default states
    assert settings_manager.get("deployment_mode") == ""
    assert settings_manager.get("kilocode_path") == ""
    
    # Update settings
    settings_manager.update({
        "deployment_mode": "api",
        "kilocode_path": "/custom/path/kilo",
        "agy_path": "/custom/path/agy",
        "llm_provider": "kilocode"
    })
    
    assert settings_manager.get("deployment_mode") == "api"
    assert settings_manager.get("kilocode_path") == "/custom/path/kilo"
    assert settings_manager.get("agy_path") == "/custom/path/agy"
    assert settings_manager.get("llm_provider") == "kilocode"

def test_cli_registry_path_override(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    
    # Override paths in settings
    settings_manager.update({
        "kilocode_path": "/nonexistent/kilo",
        "agy_path": "/nonexistent/agy"
    })
    
    # Verify path helper gets custom values
    assert cli_registry._get_bin("kilocode_path", "kilo") == "/nonexistent/kilo"
    assert cli_registry._get_bin("agy_path", "agy") == "/nonexistent/agy"
    
    # Verify detectors return False when binary doesn't exist at path
    assert cli_registry._kilocode_detect() is False
    assert cli_registry._agy_detect() is False

def test_cli_registry_api_mode_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    
    # Test CLI mode (default probe should include CLI providers if binaries exist)
    settings_manager.update({
        "deployment_mode": "cli"
    })
    
    res_cli = cli_registry.probe(force=True)
    # Providers with kind == "cli" should be present in the providers list
    cli_kinds = [p["kind"] for p in res_cli["providers"]]
    assert "cli" in cli_kinds
    
    # Switch to API mode
    settings_manager.update({
        "deployment_mode": "api"
    })
    
    res_api = cli_registry.probe(force=True)
    # Providers with kind == "cli" should be filtered out from the list completely
    cli_kinds_api = [p["kind"] for p in res_api["providers"]]
    assert "cli" not in cli_kinds_api

def test_llm_summary_dynamic_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    
    settings_manager.update({
        "llm_provider": "anthropic",
        "llm_model": "claude-test-model"
    })
    
    assert llm_summary.get_llm_setting("LLM_PROVIDER") == "anthropic"
    assert llm_summary.get_llm_setting("LLM_MODEL") == "claude-test-model"

def test_llm_summary_api_mode_fallback(tmp_path, monkeypatch, mock_response=None):
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    
    # Set provider to a CLI provider, but deployment mode to remote API
    settings_manager.update({
        "llm_provider": "gemini",
        "deployment_mode": "api",
        "llm_api_key": "test-api-key"
    })
    
    # Mock requests.post to verify direct HTTP API query instead of subprocess
    class MockResponse:
        def __init__(self):
            self.status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": '{"hook": "test"}'}}]}
            
    def mock_post(url, json, headers=None, timeout=None):
        return MockResponse()
        
    monkeypatch.setattr(llm_summary, "requests", type("MockRequests", (), {"post": mock_post}))
    
    # Verify that query_llm fallbacks to nvidia/anthropic API rather than gemini CLI
    res = llm_summary.query_llm("test prompt", "system prompt")
    assert res == '{"hook": "test"}'
