#!/usr/bin/env python3
import requests
import json
import sys
import os
import re

# Ensure we can import from src directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_models import IntelligenceDB


def parse_benchmarks(html):
    """Extract model metrics from Artificial Analysis JSON-LD datasets."""
    matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    models = {}

    for match in matches:
        try:
            data = json.loads(match)
        except (TypeError, json.JSONDecodeError):
            continue
        if data.get("@type") != "Dataset":
            continue

        name = data.get("name")
        for item in data.get("data") or []:
            label = item.get("label")
            if not label:
                continue
            metrics = models.setdefault(label, {})

            if name == "Intelligence" and item.get("artificialAnalysisIntelligenceIndex") is not None:
                metrics["intelligence"] = float(item["artificialAnalysisIntelligenceIndex"])
            elif name == "Speed" and item.get("medianOutputSpeed") is not None:
                metrics["speed"] = float(item["medianOutputSpeed"])
            elif name == "Price" and item.get("pricePerMillionTokens") is not None:
                metrics["price"] = float(item["pricePerMillionTokens"])
            elif name == "Pricing: Cache Hit, Input, and Output":
                prices = {
                    value.get("name"): value.get("value")
                    for value in item.get("pricing") or []
                }
                if prices.get("outputPrice") is not None:
                    metrics["price"] = float(prices["outputPrice"])

    return models


def fetch_benchmarks(db=None):
    print("Fetching Artificial Analysis benchmarks...")
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0"}
    try:
        r = requests.get("https://artificialanalysis.ai/", headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return 0

    models = parse_benchmarks(r.text)
    if not models:
        print("No models found in JSON-LD.")
        return 0

    db = db or IntelligenceDB()
    count = 0
    for model_name, metrics in models.items():
        if "intelligence" in metrics or "speed" in metrics or "price" in metrics:
            db.upsert_ai_benchmark(
                model_name=model_name,
                intelligence=metrics.get("intelligence"),
                speed=metrics.get("speed"),
                price=metrics.get("price")
            )
            count += 1
            print(f"Upserted {model_name}: {metrics}")

    print(f"Successfully upserted {count} AI benchmarks.")
    return count

if __name__ == "__main__":
    fetch_benchmarks()
