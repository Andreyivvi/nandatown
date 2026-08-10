# Supply chain with lost messages: one unlucky run, and what it taught me

**Author:** Andrey (MIT AI Studio — NANDA Town task)
**Scenario:** [`supply_chain_lossy.yaml`](supply_chain_lossy.yaml) — the built-in `supply_chain` scenario with exactly one setting changed.

## What I changed, and why

The supply chain scenario has four stations: a supplier, a manufacturer, a distributor, and a retailer. The supplier sends 15 items down the line, station to station.

I changed one setting:

```yaml
failures:
  message_drop: 0.0   # original
  message_drop: 0.15  # my experiment
```

This gives every message a 15% chance of getting lost — like running the supply chain over bad Wi-Fi. I picked it because the normal run is perfect (all 60 messages arrive), so it shows nothing about how the system handles failure. Everything else stayed identical: seed 42, same stations, same 15 items.

## My hypothesis (written before running)

1. **No station freezes.** In this protocol nobody waits for a reply — the supplier just sends, and each station forwards whatever arrives. So a lost message should cost one item, never stop a station.
2. **Losses stack at each step.** An item must survive one lossy link to reach the manufacturer, two to reach the distributor, three to reach the retailer. Each link lets 85% through, so about 85% × 85% × 85% ≈ **61%** of items should reach the retailer, and about 52% of "delivered" confirmations should survive the extra fourth hop back to the supplier.

## What happened (the evidence)

| | Normal run | With 15% loss |
|---|---|---|
| messages sent | 60 | 32 |
| messages dropped | 0 | 12 |
| supplier sent | 15 of 15 | **15 of 15** — no freeze, prediction 1 ✓ |
| manufacturer received | 15 | 7 |
| distributor received | 15 | 6 |
| retailer received | 15 | **4 (27%)** — prediction said 61% ✗ |
| confirmations back | 15 | 3 |

Prediction 1 was right. Prediction 2 looked badly wrong: 27% instead of 61%. That gap is where the real work started.

## The surprise, and how I investigated it

I checked the trace to see *where* messages died. Almost all the loss was on the first link: **8 of the supplier's 15 messages vanished — a 53% loss rate on a link set to 15%.** The chance of that under a fair 15% setting is about 1 in 1600. My first thought: the simulator's failure injection is broken or biased.

So I checked, in two steps:

1. **Read the source code.** In `nest_core/sim/simulator.py`, `_should_drop()` gives every message one independent random roll from a dedicated random generator. The code looks fair.
2. **Test it empirically.** I ran the identical experiment 30 times with different random seeds ([`seed_sweep.py`](seed_sweep.py)) and counted every lost message per link:

| link (sender) | sent | dropped | rate |
|---|---|---|---|
| supplier | 450 | 73 | 16.2% |
| manufacturer | 377 | 56 | 14.9% |
| distributor | 321 | 61 | 19.0% |
| retailer | 260 | 35 | 13.5% |

Overall: **16.0% lost against the configured 15%** — the injection is fair. Across the 30 runs, 58% of items reached the retailer, right next to my predicted 61%. The math was fine all along.

**Conclusion:** seed 42 — the scenario's default — just happens to hit a genuine 1-in-1600 streak of bad luck. And because the seed is fixed for reproducibility, *everyone who runs the default settings replays that exact same fluke, every time.* The framework's default supply-chain run ships with a wildly unrepresentative result baked in.

**The lesson:** with only 15 messages on a link, a single run can show triple the configured loss rate. Never trust one run — repeat it with many seeds.

## Two follow-up experiments

Per-link loss isn't a supported setting, so these drive the simulator directly from Python with a custom drop rule (scripts included). They ask: does it matter *where* the loss happens?

**Only the first link is lossy** ([`hop1_experiment.py`](hop1_experiment.py), 200 runs per rate): the damage passes downstream completely flat — every station receives exactly the fraction that survived the one bad link (at 50% loss: 49.8%, 49.8%, 49.8%). One bad link sets a hard ceiling for the whole chain, but nothing stacks, because the survivors face no further risk.

**Only the last link is lossy** ([`lasthop_experiment.py`](lasthop_experiment.py)): the sneakiest case. That link only carries "delivered!" confirmations — the goods have already arrived. The retailer received 100% of items at every loss rate, while the supplier's view collapsed (at 75% loss it saw only 23.5% "delivered"). Everything was fine; only the good news got lost. From the sender's side, "the work failed" and "the confirmation failed" look identical — which is why real-world protocols resend and de-duplicate.

## How to reproduce

```bash
pip install "nest-core[plugins]"
nest run supply_chain                                                    # the perfect baseline
nest run scenarios/community/supply_chain_lossy/supply_chain_lossy.yaml  # the unlucky seed-42 run
nest inspect traces/supply_chain_lossy.jsonl
python scenarios/community/supply_chain_lossy/seed_sweep.py              # 30-seed fairness check
python scenarios/community/supply_chain_lossy/hop1_experiment.py         # first-link-only loss
python scenarios/community/supply_chain_lossy/lasthop_experiment.py     # confirmation-link loss
```

Seeds are fixed, so every number in this README reproduces exactly.

## Use of AI and other help

I worked with Claude Code (Anthropic's coding agent) driving my terminal: it ran the quickstart and all simulations, edited the scenario YAML, read the installed `nest_core` source to verify the drop logic, and wrote the analysis scripts and this README. Hypotheses and conclusions were developed in conversation with it; the "what if only one link is lossy" questions were mine. Documentation used: NANDA Town quickstart, writing-a-scenario guide, CONTRIBUTING.md. No other human help.
