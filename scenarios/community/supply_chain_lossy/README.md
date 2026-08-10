# Supply chain under message loss: one unlucky seed, and what a lossy link really does

**Author:** Andrey (MIT AI Studio — NANDA Town task)
**Scenario:** [`supply_chain_lossy.yaml`](supply_chain_lossy.yaml) — the built-in `supply_chain` scenario with exactly one setting changed.

## The change

```yaml
failures:
  message_drop: 0.0   # baseline
  message_drop: 0.15  # this experiment
```

Everything else is identical to the bundled `supply_chain` scenario: seed 42, four stations (supplier → manufacturer → distributor → retailer), 15 items (3 per round × 5 rounds), all 12 default layers.

## Why this scenario and this setting

The baseline is a perfect conveyor belt — 60 messages sent, 60 received, every station handling exactly 15 items, zero loss. That reveals nothing about resilience. Message loss is the most fundamental distributed-systems failure, and the chain topology makes a sharp quantitative prediction possible: an item must survive one hop per stage, so losses should compound multiplicatively with depth. A linear pipeline is the cleanest possible testbed for that hypothesis.

## Hypothesis (written before running)

1. **No station stalls.** The protocol is fire-and-forget: the supplier emits all 15 items in `on_start`, and every downstream stage just reacts to what arrives — nobody waits for a reply. A lost message should cost exactly one item, never freeze an agent.
2. **Losses compound multiplicatively.** Each hop survives with p = 0.85, so ≈ 0.85³ ≈ 61% of items reach the retailer and ≈ 0.85⁴ ≈ 52% of "delivered" confirmations make it back to the supplier.
3. `dropped_count` becomes nonzero.

## Results (seed 42)

| | Baseline | `message_drop: 0.15` |
|---|---|---|
| messages sent | 60 | 32 |
| dropped | 0 | 12 |
| supplier sent | 15 | **15** (no stall — prediction 1 ✓) |
| manufacturer received | 15 | **7 (47%)** |
| distributor received | 15 | 6 |
| retailer received | 15 | **4 (27%)** — prediction said 61% |
| confirmations back to supplier | 15 | 3 |

Prediction 1 held perfectly. Prediction 2 failed badly — and that's where it got interesting.

## The surprise, and the investigation

**The first hop lost 8 of 15 messages — a 53% loss rate on a link configured for 15%.** Attributing every `dropped` event in the trace to its sender showed the loss was concentrated there (hop 1: 8, hop 2: 1, hop 3: 2, hop 4: 1). Under a fair 15% Bernoulli drop, losing ≥8 of 15 has probability ≈ 6×10⁻⁴ — roughly 1 in 1600.

First suspicion: biased failure injection. Reading `nest_core/sim/simulator.py` showed `_should_drop()` makes one independent draw per message from a dedicated failure RNG — it *looks* fair. So the claim became testable: sweep 30 seeds ([`seed_sweep.py`](seed_sweep.py)) and tally every drop per hop.

| hop (sender) | sent | dropped | rate |
|---|---|---|---|
| supplier | 450 | 73 | 0.162 |
| manufacturer | 377 | 56 | 0.149 |
| distributor | 321 | 61 | 0.190 |
| retailer | 260 | 35 | 0.135 |

Overall: 225/1408 = **16.0%** against the configured 15%, every hop within sampling noise, and hop-1 drops per seed were mostly 1–3 (max 6). The injection is fair; **seed 42 is simply a legitimate ~1-in-1600 outlier that the fixed default seed happens to hit.** Across the sweep, 58% of items reached the retailer — matching the multiplicative prediction (0.85³ ≈ 61%, or 59% at the observed 16% rate).

**Lesson:** with only 15 messages on a link, a single seeded run can show triple the configured failure rate. Small-sample scenario results need either many seeds or many messages before they mean anything.

## Follow-up experiments: where the loss sits matters

Per-link loss is not a supported setting, so these drive the `Simulator` directly with a custom drop rule (scripts included). They answer: *does a bad link hurt downstream stations more than itself?*

**Loss on the first hop only** ([`hop1_experiment.py`](hop1_experiment.py), 200 seeds per rate): the damage passes through **exactly flat** — every downstream station receives precisely the fraction that survived the bad link, at every rate tested:

| first-hop loss | manufacturer | distributor | retailer |
|---|---|---|---|
| 75% | 23.5% | 23.5% | 23.5% |
| 50% | 49.8% | 49.8% | 49.8% |
| 25% | 75.6% | 75.6% | 75.6% |
| 5% | 95.4% | 95.4% | 95.4% |

With no retries there is no recovery, and with no waiting there is no amplification: one bad link sets a hard, flat ceiling for the whole downstream chain. (Global loss is different — at `message_drop: 0.5` on every hop, receipt compounds 50% → 25% → 12%, matching 0.5ⁿ.)

**Loss on the confirmation hop only** ([`lasthop_experiment.py`](lasthop_experiment.py)): the most deceptive case. The goods all arrive — the retailer received 100% of items at every loss rate — but the supplier's view collapses to the link's survival rate (at 75% loss it sees only 23.5% "delivered"). The failure is purely informational: from the sender's side, "the work failed" and "the acknowledgment failed" are indistinguishable, which is exactly why real protocols pair retries with idempotency.

## Takeaway

A fire-and-forget pipeline degrades gracefully and predictably — multiplicative in depth, flat pass-through from a single bad link, no stalls. But the same missing ingredient (no acknowledgment/retry loop) means it can neither recover lost items nor tell real loss from lost feedback. (For contrast: the same `message_drop: 0.15` applied to the request-reply `marketplace` scenario collapses 70% of all activity, because agents there wait forever on lost replies.)

## Reproducing

```bash
pip install "nest-core[plugins]"
nest run supply_chain                                                    # baseline
nest run scenarios/community/supply_chain_lossy/supply_chain_lossy.yaml  # seed-42 outlier run
nest inspect traces/supply_chain_lossy.jsonl
python scenarios/community/supply_chain_lossy/seed_sweep.py              # fairness check, 30 seeds
python scenarios/community/supply_chain_lossy/hop1_experiment.py         # first-hop-only sweep
python scenarios/community/supply_chain_lossy/lasthop_experiment.py      # confirmation-hop loss
```

Tier 1 with fixed seeds, so every number above reproduces exactly.

## Use of AI and other help

This work was done with Claude Code (Anthropic) driving the terminal: it ran the quickstart, edited the scenario YAML, ran all simulations and sweeps, read the installed `nest_core` source to verify the drop logic and agent behavior, and wrote the analysis scripts and this README. Hypotheses and interpretation were developed in conversation; the first-hop and confirmation-hop questions were the author's. Documentation used: NANDA Town quickstart, writing-a-scenario guide, CONTRIBUTING.md. No other outside help.
