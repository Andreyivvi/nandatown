# SPDX-License-Identifier: Apache-2.0
"""Run supply_chain_lossy across 30 seeds and tally the drop rate per hop.

Used to investigate a suspicious single-seed result (8/15 drops on the first
hop at a configured 15% rate) and verify the failure injection is fair.
Run from the repository root: python scenarios/community/supply_chain_lossy/seed_sweep.py
"""
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

YAML = Path("scenarios/community/supply_chain_lossy/supply_chain_lossy.yaml")
TRACE = Path("traces/supply_chain_lossy.jsonl")

base = YAML.read_text()
sent_by = Counter()
dropped_on_hop = Counter()
hop1_drops_per_seed = []

for seed in range(1, 31):
    YAML.write_text(re.sub(r"seed: \d+", f"seed: {seed}", base))
    subprocess.run(["nest", "run", str(YAML)], capture_output=True, check=True)
    events = [json.loads(l) for l in TRACE.read_text().splitlines() if l.strip()]
    h1 = 0
    for e in events:
        if e["kind"] == "send":
            sent_by[e["agent"]] += 1
        elif e["kind"] == "dropped":
            dropped_on_hop[e["from"]] += 1
            if e["from"] == "supplier-0":
                h1 += 1
    hop1_drops_per_seed.append(h1)

YAML.write_text(base)

print("hop (sender)          sent  dropped  rate")
for hop in ["supplier-0", "manufacturer-0", "distributor-0", "retailer-0"]:
    s, d = sent_by[hop], dropped_on_hop[hop]
    print(f"{hop:20s} {s:5d} {d:8d}  {d / s if s else 0:.3f}")

total_s, total_d = sum(sent_by.values()), sum(dropped_on_hop.values())
print(f"\noverall: {total_d}/{total_s} = {total_d / total_s:.3f}  (configured 0.15)")
print("hop-1 drops per seed (of 15):", hop1_drops_per_seed)
