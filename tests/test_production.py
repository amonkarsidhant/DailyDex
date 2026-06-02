#!/usr/bin/env python3
"""Legacy production hardening tests for v0.4."""

import os
import sys
import json
import tempfile
import shutil
import unittest

import pytest

pytestmark = pytest.mark.skip(reason="Superseded by the dedicated pytest v0.5 test suite.")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from data_models import IntelligenceDB


class TestFetchNews(unittest.TestCase):
    """Test that fetch_news.py creates/updates data.json"""
    
    def test_fetch_creates_data_json(self):
        """Running fetch_news.py must create data.json"""
        import subprocess
        
        # Use temp directory for isolation
        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = os.path.join(tmpdir, "data.json")
            cache_dir = os.path.join(tmpdir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            # Run fetch_news with temp paths
            env = os.environ.copy()
            env["DATA_FILE"] = data_file
            env["CACHE_DIR"] = cache_dir
            
            result = subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "fetch_news.py")],
                capture_output=True,
                text=True,
                timeout=120,
                env=env
            )
            
            # Should complete without error (or use cache if network fails)
            self.assertIn(result.returncode, [0, 1], f"fetch_news.py failed: {result.stderr}")
            
            # Must create data.json
            self.assertTrue(os.path.exists(data_file), "data.json was not created")
            
            # Must be valid JSON with expected keys
            with open(data_file) as f:
                data = json.load(f)
            
            self.assertIn("last_updated", data)
            expected_sources = ["youtube", "github", "huggingface", "blogs", "papers"]
            for source in expected_sources:
                self.assertIn(source, data, f"Missing {source} in data.json")


class TestDigestGenerator(unittest.TestCase):
    """Test that digest_generator.py is available"""
    
    def test_digest_generator_exists(self):
        """digest_generator.py must be importable"""
        try:
            from digest_generator import DailyDigestGenerator
            generator = DailyDigestGenerator()
            self.assertIsNotNone(generator)
        except ImportError as e:
            self.fail(f"Cannot import digest_generator.py: {e}")


class TestSavedItemDedup(unittest.TestCase):
    """Test that saving same URL twice does not create duplicates"""
    
    def test_save_duplicate_url_updates(self):
        """Saving same URL should update existing item, not create duplicate"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = IntelligenceDB(db_path=db_path)
            
            item = {
                "title": "Test Item",
                "url": "https://example.com/test",
                "source": "test",
                "source_type": "news",
                "category": "AI",
                "status": "to_read",
                "signal_score": 75
            }
            
            # Save first time
            first_id = db.save_item(item)
            self.assertIsNotNone(first_id)
            
            # Get count
            items = db.get_saved_items()
            self.assertEqual(len(items), 1, "Should have exactly 1 item after first save")
            
            # Save same URL again with different title/status
            item["title"] = "Updated Title"
            item["status"] = "useful"
            second_id = db.save_item(item)
            
            # Should return same ID
            self.assertEqual(first_id, second_id, "Second save should return same ID (update, not insert)")
            
            # Should still have only 1 item
            items = db.get_saved_items()
            self.assertEqual(len(items), 1, "Should still have exactly 1 item (no duplicate)")
            
            # Title should be updated
            self.assertEqual(items[0]["title"], "Updated Title", "Title should be updated")
            self.assertEqual(items[0]["status"], "useful", "Status should be updated")
    
    def test_unique_index_exists(self):
        """Database should have unique index on saved_items.url"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = IntelligenceDB(db_path=db_path)
            
            # Check index exists
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_saved_items_url'")
            result = cursor.fetchone()
            conn.close()
            
            self.assertIsNotNone(result, "Unique index on url should exist")


class TestDockerPaths(unittest.TestCase):
    """Test Docker path configuration"""
    
    def test_dockerfile_has_data_dir(self):
        """Dockerfile should copy data directory"""
        dockerfile_path = os.path.join(os.path.dirname(__file__), "Dockerfile")
        with open(dockerfile_path) as f:
            content = f.read()
        
        self.assertIn("data/", content, "Dockerfile should copy data directory")
        self.assertIn("ENV DATA_DIR", content, "Dockerfile should set DATA_DIR env var")
        self.assertIn("/app/data", content, "Dockerfile should use /app/data paths")


if __name__ == "__main__":
    unittest.main(verbosity=2)
