#!/usr/bin/env python3
import requests
import json
import sys
import os
import re

from bs4 import BeautifulSoup

# Ensure we can import from src directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db_compat as sqlite3
from data_models import IntelligenceDB

BENCHMARK_URL = "https://artificialanalysis.ai/leaderboards/models"


def _as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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

            intelligence = _as_float(item.get("artificialAnalysisIntelligenceIndex"))
            speed = _as_float(item.get("medianOutputSpeed"))
            price = _as_float(item.get("pricePerMillionTokens"))
            if name == "Intelligence" and intelligence is not None:
                metrics["intelligence"] = intelligence
            elif name == "Speed" and speed is not None:
                metrics["speed"] = speed
            elif name == "Price" and price is not None:
                metrics["price"] = price
            elif name == "Pricing: Cache Hit, Input, and Output":
                prices = {
                    value.get("name"): value.get("value")
                    for value in item.get("pricing") or []
                }
                output_price = _as_float(prices.get("outputPrice"))
                if output_price is not None:
                    metrics["price"] = output_price

    return models


def parse_leaderboard_models(html):
    """Extract the complete active model catalog from the Next.js payload."""
    marker = '"models":'
    decoder = json.JSONDecoder()

    for script in BeautifulSoup(html, "html.parser").find_all("script"):
        content = script.string or script.get_text()
        if not content.startswith("self.__next_f.push("):
            continue
        try:
            payload = json.loads(content[len("self.__next_f.push("):-1])
        except (TypeError, json.JSONDecodeError):
            continue
        if len(payload) < 2 or not isinstance(payload[1], str):
            continue

        chunk = payload[1]
        start = chunk.find(marker)
        if start < 0:
            continue
        try:
            entries, _ = decoder.raw_decode(chunk, start + len(marker))
        except json.JSONDecodeError:
            continue
        if not entries or not isinstance(entries, list):
            continue
        if not isinstance(entries[0], dict) or "intelligenceIndex" not in entries[0]:
            continue

        models = {}
        for item in entries:
            if item.get("deprecated"):
                continue
            name = item.get("name")
            if not name:
                continue
            metrics = {}
            intelligence = _as_float(item.get("intelligenceIndex"))
            speed = _as_float(item.get("medianOutputTokensPerSecond"))
            price = _as_float(item.get("price1mOutputTokens"))
            if intelligence is not None:
                metrics["intelligence"] = intelligence
            if speed is not None:
                metrics["speed"] = speed
            if price is not None:
                metrics["price"] = price
            if metrics:
                models[name] = metrics
        return models

    return {}


def _prune_stale_benchmarks(db, model_names):
    placeholders = ",".join("?" for _ in model_names)
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute(
        f"DELETE FROM ai_benchmarks WHERE model_name NOT IN ({placeholders})",
        tuple(model_names),
    )
    conn.commit()
    conn.close()


def fetch_benchmarks(db=None):
    print("Fetching Artificial Analysis benchmarks...")
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0"}
    try:
        r = requests.get(BENCHMARK_URL, headers=headers, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return 0

    models = parse_leaderboard_models(r.text)
    complete_snapshot = bool(models)
    if not models:
        models = parse_benchmarks(r.text)
    if not models:
        print("No benchmark models found.")
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

    if complete_snapshot:
        _prune_stale_benchmarks(db, models.keys())

    print(f"Successfully upserted {count} AI benchmarks.")
    return count

if __name__ == "__main__":
    fetch_benchmarks()
