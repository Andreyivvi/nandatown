# SPDX-License-Identifier: Apache-2.0
"""Compare baseline vs lossy marketplace traces to explain the activity collapse."""
import json
from collections import Counter
from pathlib import Path


def load(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def analyze(path):
    events = load(path)
    sends = [e for e in events if e.get("kind") == "send"]
    drops = [e for e in events if e.get("kind") == "dropped"]
    buyer_sends = [e for e in sends if str(e.get("agent", "")).startswith("buyer")]
    seller_sends = [e for e in sends if str(e.get("agent", "")).startswith("seller")]

    per_buyer = Counter(str(e.get("agent")) for e in buyer_sends)
    dist = Counter(per_buyer.values())

    print(f"\n=== {path} ===")
    print(f"sends total: {len(sends)}  (buyers: {len(buyer_sends)}, sellers: {len(seller_sends)})")
    print(f"dropped: {len(drops)}")
    print("requests sent per buyer (count -> #buyers):", dict(sorted(dist.items())))
    stalled = 50 - len([b for b, n in per_buyer.items() if n == 10])
    print(f"buyers that never reached round 10: {stalled}/50")
    if len(buyer_sends):
        print(f"mean requests per buyer: {len(buyer_sends) / 50:.2f}")


analyze("traces/marketplace.jsonl")
analyze("traces/marketplace_lossy.jsonl")

# Theoretical prediction for the stall model: a buyer keeps going only while
# each 2-leg round trip survives (p = 0.85^2 = 0.7225 per round).
p = 0.85**2
expected_requests = sum(p**k for k in range(10))
print(f"\nStall-model prediction: mean requests per buyer = {expected_requests:.2f}"
      f"  -> total buyer sends ~= {50 * expected_requests:.0f}")
