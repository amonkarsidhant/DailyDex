#!/usr/bin/env python3
"""Smoke tests for DailyDex"""

import sys
import os
import json

import pytest

pytestmark = pytest.mark.skip(reason="Legacy manual smoke checks are covered by the pytest suite.")

# Determine the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "src"))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

# Add the dashboard directory to path
sys.path.insert(0, SCRIPT_DIR)

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        import scoring_engine
        import data_models
        import digest_generator
        print("  - All modules import OK")
        return True
    except Exception as e:
        print(f"  - Import failed: {e}")
        return False

def test_config():
    """Test config loading"""
    print("Testing config...")
    try:
        config_path = os.path.join(SCRIPT_DIR, "config.json")
        with open(config_path) as f:
            config = json.load(f)
        print(f"  - Config loaded: {len(config)} keys")
        return True
    except Exception as e:
        print(f"  - Config failed: {e}")
        return False

def test_scoring():
    """Test scoring engine"""
    print("Testing scoring engine...")
    try:
        from scoring_engine import SignalScorer
        scorer = SignalScorer()
        
        # Test GitHub repo scoring
        repo = {'title': 'test-agent', 'description': 'AI coding agent tool', 'stars': '5000', 'url': 'https://github.com/test/repo'}
        result = scorer.score_github_repo(repo)
        
        assert 'signal_score' in result
        assert 'action' in result
        assert 'score_breakdown' in result
        
        # Check breakdown has all required fields
        breakdown = result.get('score_breakdown', {})
        required_fields = ['recency', 'popularity', 'agentic', 'local', 'pi_suitability', 'developer_productivity', 'trust']
        missing = [f for f in required_fields if f not in breakdown]
        if missing:
            print(f"  - WARNING: Missing breakdown fields: {missing}")
        
        print(f"  - Scored repo: {result['signal_score']}, action: {result['action']}")
        print(f"  - Breakdown: {result.get('score_breakdown', {})}")
        print(f"  - score_label: {result.get('score_label', 'N/A')}")
        print(f"  - score_reason: {result.get('score_reason', 'N/A')}")
        return True
    except Exception as e:
        print(f"  - Scoring failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database():
    """Test database operations"""
    print("Testing database...")
    try:
        from data_models import IntelligenceDB
        
        # Use temp file for testing
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        db = IntelligenceDB(tmp_path)
        
        # Test save item
        test_item = {
            'title': 'Test Repo',
            'url': 'https://github.com/test/repo',
            'source': 'test',
            'source_type': 'github',
            'signal_score': 85
        }
        item_id = db.save_item(test_item)
        print(f"  - Saved item ID: {item_id}")
        
        # Test get saved items
        items = db.get_saved_items()
        print(f"  - Retrieved {len(items)} saved items")
        
        # Test ignore item
        db.ignore_item('https://github.com/ignored/repo', 'Ignored Repo', 'github')
        ignored = db.is_ignored('https://github.com/ignored/repo')
        print(f"  - Ignored item check: {ignored}")
        
        # Test tracked topics
        db.add_tracked_topic('agents', 'testing')
        topics = db.get_tracked_topics()
        print(f"  - Tracked topics: {len(topics)}")
        
        # Test source health with extended fields
        db.update_source_health('github', True, item_count=10)
        health = db.get_source_health()
        print(f"  - Source health entries: {len(health)}")
        
        # Verify extended fields
        if health:
            h = health[0]
            print(f"  - Source health: {h.get('source_name')}, items: {h.get('item_count', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"  - Database failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_routes():
    """Test Flask routes using test client"""
    print("Testing Flask routes...")
    try:
        from dashboard_new import app
        
        client = app.test_client()
        
        # Test health endpoint
        rv = client.get('/health')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['status'] == 'ok'
        print("  - /health OK")
        
        # Test GET /api/saved
        rv = client.get('/api/saved')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'items' in data
        print("  - GET /api/saved OK")
        
        # Test POST /api/save
        rv = client.post('/api/save', 
                        json={'title': 'Test', 'url': 'http://x.com', 'source_type': 'github', 'signal_score': 50},
                        content_type='application/json')
        assert rv.status_code == 200
        print("  - POST /api/save OK")
        
        # Test PUT /api/saved/<id>/status
        rv = client.put('/api/saved/1/status', 
                       json={'status': 'testing'},
                       content_type='application/json')
        assert rv.status_code == 200
        print("  - PUT /api/saved/<id>/status OK")
        
        # Test DELETE /api/saved/<id>
        rv = client.delete('/api/saved/1')
        assert rv.status_code == 200
        print("  - DELETE /api/saved/<id> OK")
        
        # Test GET /api/track
        rv = client.get('/api/track')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'topics' in data
        print("  - GET /api/track OK")
        
        # Test POST /api/track
        rv = client.post('/api/track',
                        json={'topic': 'test-topic', 'reason': 'testing'},
                        content_type='application/json')
        assert rv.status_code == 200
        print("  - POST /api/track OK")
        
        # Test DELETE /api/track/<id>
        rv = client.delete('/api/track/1')
        assert rv.status_code == 200
        print("  - DELETE /api/track/<id> OK")
        
        # Test GET /api/source-health
        rv = client.get('/api/source-health')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'sources' in data
        print("  - GET /api/source-health OK")
        
        return True
    except Exception as e:
        print(f"  - Routes failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_digest():
    """Test digest generation"""
    print("Testing digest generator...")
    try:
        from digest_generator import DailyDigestGenerator
        generator = DailyDigestGenerator()
        
        # Test with sample data
        test_data = {
            'github': [{'title': 'Test', 'signal_score': 80, 'stars': '1000'}],
            'huggingface': [],
            'youtube': [],
            'blogs': [],
            'papers': []
        }
        
        digest = generator.generate_digest(test_data)
        print(f"  - Generated digest: {len(digest)} chars")
        return True
    except Exception as e:
        print(f"  - Digest failed: {e}")
        return False

def test_flask_app():
    """Test Flask app can be created"""
    print("Testing Flask app...")
    try:
        # Just check imports work, don't start server
        from flask import Flask
        app = Flask(__name__)
        print("  - Flask app creation OK")
        return True
    except Exception as e:
        print(f"  - Flask failed: {e}")
        return False

def test_data_file():
    """Test data file exists and is valid"""
    print("Testing data file...")
    try:
        data_path = os.path.join(SCRIPT_DIR, "data.json")
        if not os.path.exists(data_path):
            print("  - Data file not found (optional)")
            return True  # Make this optional
        with open(data_path) as f:
            data = json.load(f)
        print(f"  - Data file OK: {len(data)} top-level keys")
        for key in ['github', 'huggingface', 'youtube', 'blogs', 'papers']:
            if key in data:
                print(f"    - {key}: {len(data[key])} items")
        return True
    except Exception as e:
        print(f"  - Data file failed: {e}")
        return False

if __name__ == "__main__":
    import json
    
    print("=" * 50)
    print("DailyDex - Smoke Tests")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Config", test_config),
        ("Data File", test_data_file),
        ("Scoring", test_scoring),
        ("Database", test_database),
        ("Routes", test_routes),
        ("Digest", test_digest),
        ("Flask", test_flask_app),
    ]
    
    results = []
    for name, test_fn in tests:
        print(f"\n[{name}]")
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  - Test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    passed = sum(1 for _, r in results if r)
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {name}")
    print(f"\nTotal: {passed}/{len(results)} passed")
    print("=" * 50)
    
    sys.exit(0 if passed == len(results) else 1)
