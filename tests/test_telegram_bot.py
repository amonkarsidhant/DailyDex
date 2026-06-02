import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import telegram_bot

pytestmark = pytest.mark.asyncio

def test_url_hash():
    h = telegram_bot._url_hash("http://example.com")
    assert len(h) == 8

def test_store_and_resolve_url(tmp_path, monkeypatch):
    map_file = tmp_path / "map.json"
    monkeypatch.setattr(telegram_bot, "URL_MAP_FILE", str(map_file))
    
    h = telegram_bot._store_url("http://test.com")
    assert telegram_bot._resolve_url(h) == "http://test.com"
    
    # Store again merges
    h2 = telegram_bot._store_url("http://test2.com")
    assert telegram_bot._resolve_url(h) == "http://test.com"
    assert telegram_bot._resolve_url(h2) == "http://test2.com"

def test_get_top_items(tmp_path, monkeypatch):
    sf = tmp_path / "scored.json"
    sf.write_text(json.dumps({"github": [{"title": "Repo", "signal_score": 90, "url": "g"}]}))
    monkeypatch.setattr(telegram_bot, "DATA_SCORED_FILE", str(sf))
    
    items = telegram_bot.get_top_items(1)
    assert len(items) == 1
    assert items[0]["title"] == "Repo"

    monkeypatch.setattr(telegram_bot, "DATA_SCORED_FILE", "missing.json")
    monkeypatch.setattr(telegram_bot, "DATA_FILE", "missing2.json")
    assert telegram_bot.get_top_items() == []

@patch("telegram_bot.IntelligenceDB")
async def test_cmd_start(mock_db_cls):
    mock_db = MagicMock()
    mock_db_cls.return_value = mock_db
    
    update = MagicMock()
    update.effective_chat.id = 123
    update.effective_user.first_name = "Alice"
    update.message.reply_text = AsyncMock()
    
    await telegram_bot.cmd_start(update, None)
    mock_db.add_subscriber.assert_called_with(123, "Alice")
    update.message.reply_text.assert_called_once()

@patch("telegram_bot.IntelligenceDB")
async def test_cmd_stop(mock_db_cls):
    mock_db = MagicMock()
    mock_db_cls.return_value = mock_db
    
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    
    await telegram_bot.cmd_stop(update, None)
    mock_db.remove_subscriber.assert_called_with(123)
    update.message.reply_text.assert_called_once()

@patch("telegram_bot.get_top_items")
@patch("telegram_bot.IntelligenceDB")
async def test_cmd_digest(mock_db_cls, mock_get_top):
    # Empty case
    mock_get_top.return_value = []
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    await telegram_bot.cmd_digest(update, None)
    assert "No data yet" in update.message.reply_text.call_args[0][0]
    
    # Items exist
    mock_get_top.return_value = [{"title": "T", "url": "u", "source_type": "s", "signal_score": 50}]
    mock_db = MagicMock()
    mock_db.get_vote_count.return_value = 2
    mock_db_cls.return_value = mock_db
    
    update.message.reply_text.reset_mock()
    await telegram_bot.cmd_digest(update, None)
    
    # Called twice: once for header, once for item
    assert update.message.reply_text.call_count == 2

@patch("telegram_bot._resolve_url")
@patch("telegram_bot.IntelligenceDB")
async def test_handle_callback(mock_db_cls, mock_resolve):
    update = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    update.callback_query = query
    
    # Skip
    query.data = "skip"
    await telegram_bot.handle_callback(update, None)
    query.edit_message_reply_markup.assert_called_with(None)
    
    # Invalid
    query.data = "invalid"
    await telegram_bot.handle_callback(update, None)
    
    # Vote - unknown URL
    query.data = "v:hash"
    mock_resolve.return_value = ""
    await telegram_bot.handle_callback(update, None)
    assert "Could not find" in query.answer.call_args[0][0]
    
    # Vote - success
    mock_resolve.return_value = "http://u"
    mock_db = MagicMock()
    mock_db.vote_item.return_value = True  # new vote
    mock_db.get_vote_count.return_value = 3
    mock_db_cls.return_value = mock_db
    
    query.from_user.id = 123
    query.from_user.first_name = "Bob"
    
    await telegram_bot.handle_callback(update, None)
    mock_db.vote_item.assert_called_with("http://u", 123, "Bob")
    
    # Re-vote
    mock_db.vote_item.return_value = False
    await telegram_bot.handle_callback(update, None)

@patch("telegram_bot.get_top_items")
@patch("telegram_bot.IntelligenceDB")
async def test_broadcast_digest(mock_db_cls, mock_get_top):
    app = MagicMock()
    app.bot.send_message = AsyncMock()
    
    mock_db = MagicMock()
    mock_db_cls.return_value = mock_db
    
    # No items
    mock_get_top.return_value = []
    assert await telegram_bot.broadcast_digest(app) == 0
    
    # No subscribers
    mock_get_top.return_value = [{"title": "T"}]
    mock_db.get_subscribers.return_value = []
    assert await telegram_bot.broadcast_digest(app) == 0
    
    # Send
    mock_db.get_subscribers.return_value = [{"chat_id": 123}]
    assert await telegram_bot.broadcast_digest(app) == 1
    assert app.bot.send_message.call_count == 2 # header + 1 item

def test_build_application(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    telegram_bot.BOT_TOKEN = ""
    with pytest.raises(RuntimeError):
        telegram_bot.build_application()
    
    telegram_bot.BOT_TOKEN = "token"
    # Actually checking build logic requires mock
    with patch("telegram.ext.ApplicationBuilder") as builder:
        telegram_bot.build_application()
        assert builder.called
