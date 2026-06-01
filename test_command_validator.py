from command_validator import parse_commands, validate_script_commands

def test_parse_commands():
    text = """
    First, let's clone the repository:
    $ git clone https://github.com/docmost/docmost.git
    
    Then run Docker:
    ```bash
    docker run -d -p 8000:8000 --name docmost docmost/docmost:latest
    ```
    
    Or install via Python/NPM:
    pip install django request-missing-package-invalid
    npm install express-dummy-invalid-pkg
    
    And run a dangerous command:
    sudo rm -rf /tmp/test-dir
    """
    
    parsed = parse_commands(text)
    commands_map = {cmd['command']: cmd['type'] for cmd in parsed}
    
    assert "git clone https://github.com/docmost/docmost.git" in commands_map
    assert commands_map["git clone https://github.com/docmost/docmost.git"] == "git"
    
    assert "docker run -d -p 8000:8000 --name docmost docmost/docmost:latest" in commands_map
    assert commands_map["docker run -d -p 8000:8000 --name docmost docmost/docmost:latest"] == "docker"
    
    assert "pip install django request-missing-package-invalid" in commands_map
    assert commands_map["pip install django request-missing-package-invalid"] == "pip"
    
    assert "npm install express-dummy-invalid-pkg" in commands_map
    assert commands_map["npm install express-dummy-invalid-pkg"] == "npm"
    
    # Dangerous commands
    assert "sudo rm -rf /tmp/test-dir" in commands_map
    assert commands_map["sudo rm -rf /tmp/test-dir"] == "security_warning"


def test_validate_script_commands(monkeypatch):
    # Mock urllib.request.urlopen to prevent network hits during tests
    class MockResponse:
        def __init__(self, status):
            self.status = status
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, 'full_url') else req
        if "github.com/docmost/docmost" in url:
            return MockResponse(200)
        if "repositories/docmost/docmost" in url:
            return MockResponse(200)
        if "pypi.org/pypi/django" in url:
            return MockResponse(200)
        if "pypi.org/pypi/request-missing-package-invalid" in url:
            raise Exception("404 Not Found")
        if "registry.npmjs.org/express" in url:
            return MockResponse(200)
        raise Exception("Host not resolved or missing URL mock")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    script = """
    $ git clone https://github.com/docmost/docmost.git
    $ docker run -d -p 8000:8000 docmost/docmost
    $ pip install django request-missing-package-invalid
    $ sudo rm -rf /tmp/dangerous-clean
    """
    
    results = validate_script_commands(script)
    results_map = {res['command']: res for res in results}
    
    # Git Clone Check
    assert results_map["git clone https://github.com/docmost/docmost.git"]["status"] == "verified"
    
    # Docker Run Check
    assert results_map["docker run -d -p 8000:8000 docmost/docmost"]["status"] == "verified"
    
    # PyPI Check (one valid, one invalid -> should fail aggregate)
    assert results_map["pip install django request-missing-package-invalid"]["status"] == "failed"
    assert "request-missing-package-invalid" in results_map["pip install django request-missing-package-invalid"]["message"]

    
    # Security Check
    assert results_map["sudo rm -rf /tmp/dangerous-clean"]["status"] == "danger"
