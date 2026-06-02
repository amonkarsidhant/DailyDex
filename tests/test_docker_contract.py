from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent.parent


def test_dockerfile_packages_runtime_files():
    dockerfile = (REPO_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY src ./src" in dockerfile
    assert "COPY config ./config" in dockerfile
    assert "COPY requirements.txt ./" in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert "COPY data/" not in dockerfile
    assert "COPY data.json" not in dockerfile
    assert "COPY data_scored.json" not in dockerfile


def test_readme_uses_data_volume_and_env_vars():
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    assert "-v $(pwd)/data:/app/data" in readme
    assert "-e DATA_DIR=/app/data" in readme
    assert "-e DB_PATH=/app/data/intelligence.db" in readme
    assert "-e CACHE_DIR=/app/data/cache" in readme
    assert "-e DIGEST_DIR=/app/data/digests" in readme
    assert "-e DATA_FILE=/app/data/data.json" in readme
    assert "-e SCORED_DATA_FILE=/app/data/data_scored.json" in readme


def test_no_personal_hardcoded_paths_remain():
    needle = "/home/" + "sidhant"
    offenders = []
    for path in REPO_DIR.rglob("*"):
        if ".git" in path.parts or path.is_dir():
            continue
        if path.suffix.lower() not in {".py", ".md", ".txt", ".json", ""}:
            continue
        if path.name in {"AGENTS.md", "README.md"}:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if needle in content:
            offenders.append(str(path.relative_to(REPO_DIR)))
    assert offenders == []
