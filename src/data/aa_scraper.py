import requests
import json
import re
import os
import sys

# Ensure DailyDex path is in sys.path to import db
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_models import IntelligenceDB

def extract_jsonld_blocks(html: str) -> list:
    """Extracts all JSON-LD blocks from HTML."""
    matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    blocks = []
    for match in matches:
        try:
            data = json.loads(match)
            if "@type" in data and data["@type"] == "Dataset":
                blocks.append(data)
        except json.JSONDecodeError:
            pass
    return blocks

def scrape_aa_route(url: str, db: IntelligenceDB) -> int:
    """Fetches a specific URL, extracts datasets, and upserts to DB."""
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return 0

    blocks = extract_jsonld_blocks(r.text)
    saved = 0
    for block in blocks:
        name = block.get("name")
        if name:
            db.upsert_aa_dataset(name, url, block)
            saved += 1
    return saved

def scrape_all():
    db = IntelligenceDB()
    db._init_db()
    routes = [
        "https://artificialanalysis.ai/",
        "https://artificialanalysis.ai/trends",
        "https://artificialanalysis.ai/models",
        "https://artificialanalysis.ai/agents",
        "https://artificialanalysis.ai/benchmarks/hardware",
        "https://artificialanalysis.ai/evaluations/artificial-analysis-intelligence-index"
    ]
    total_saved = 0
    for route in routes:
        print(f"Scraping {route}...")
        saved = scrape_aa_route(route, db)
        print(f" -> Saved {saved} datasets.")
        total_saved += saved
    print(f"Scraping complete. Total datasets saved: {total_saved}")

if __name__ == "__main__":
    scrape_all()
