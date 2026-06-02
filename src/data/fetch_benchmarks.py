#!/usr/bin/env python3
import requests
import json
import sys
import os
import re

# Ensure we can import from src directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_models import IntelligenceDB

def fetch_benchmarks():
    print("Fetching Artificial Analysis benchmarks...")
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0"}
    try:
        r = requests.get("https://artificialanalysis.ai/", headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return

    # Use regex to find all JSON-LD blocks
    matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL)
    
    models = {}

    for match in matches:
        try:
            data = json.loads(match)
            if data.get("@type") == "Dataset" and "data" in data:
                name = data.get("name")
                for item in data["data"]:
                    label = item.get("label")
                    if not label:
                        continue
                    if label not in models:
                        models[label] = {}
                    
                    if name == "Intelligence" and "artificialAnalysisIntelligenceIndex" in item:
                        models[label]["intelligence"] = float(item["artificialAnalysisIntelligenceIndex"])
                    elif name == "Speed" and "medianOutputSpeed" in item:
                        models[label]["speed"] = float(item["medianOutputSpeed"])
                    elif name == "Price" and "pricePerMillionTokens" in item:
                        models[label]["price"] = float(item["pricePerMillionTokens"])
        except Exception:
            continue
            
    if not models:
        print("No models found in JSON-LD.")
        return
        
    db = IntelligenceDB()
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

if __name__ == "__main__":
    fetch_benchmarks()
