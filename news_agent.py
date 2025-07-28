#!/usr/bin/env python3
"""
Minimal fetch → classify → output script.
Add/remove feeds or keyword lists in config.yml
"""
import json, re, sys, argparse, datetime as dt, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any

### ---------- config helpers ----------
def load_cfg(path="config.yml") -> Dict[str, Any]:
    import yaml  # PyYAML is pre‑installed in GitHub Actions runner
    with open(path, "r", encoding="utf‑8") as f:
        return yaml.safe_load(f)

CFG = load_cfg()

### ---------- feed fetch ----------
UA = ("Mozilla/5.0 (+https://github.com/yourhandle/news-agent)"
      " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User‑Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def parse(xml_bytes: bytes) -> List[Dict[str, str]]:
    # crude RSS/Atom support – good enough for news headlines
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        def txt(tag, default=""):
            el = item.find(tag) or item.find(f"{{*}}{tag}")
            return el.text.strip() if el is not None and el.text else default
        items.append({
            "title":   txt("title"),
            "link":    txt("link"),
            "summary": txt("description") or txt("summary"),
            "date":    txt("pubDate") or txt("updated")
        })
    return items

### ---------- classification ----------
KW = CFG["keywords"]

def classify(entry: Dict[str, str]) -> Dict[str, str]:
    text = f'{entry["title"].lower()} {entry["summary"].lower()}'
    def hit(cat): return any(k in text for k in KW[cat])
    if hit("macro"):    cat = "Macro"
    elif hit("earn"):   cat = "Earnings"
    elif hit("tech"):   cat = "Tech/Trend"
    elif hit("meme"):   cat = "Meme/Sentiment"
    else:               cat = "Other"
    urgency = "High" if hit("high") else "Medium"
    return {"category": cat, "urgency": urgency}

### ---------- main ----------
def main(max_items: int, json_out: str):
    out: List[Dict[str, str]] = []
    for url in CFG["feeds"]:
        try:
            for e in parse(fetch(url))[:max_items]:
                e.update(classify(e))
                out.append(e)
        except Exception as ex:
            print(f"Feed {url} failed: {ex}", file=sys.stderr)
    # sort by newest first
    out.sort(key=lambda x: x["date"], reverse=True)
    Path(json_out).write_text(json.dumps(out, indent=2))
    print(f"Wrote {len(out)} items to {json_out}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--max-items", type=int, default=10)
    p.add_argument("--json-out", default="output/latest.json")
    args = p.parse_args()
    Path("output").mkdir(exist_ok=True)
    main(args.max_items, args.json_out)
