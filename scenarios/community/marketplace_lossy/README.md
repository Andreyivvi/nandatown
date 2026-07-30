# Marketplace under message loss: one dropped packet, nine lost deals

**Author:** Andrey (MIT AI Studio — NANDA Town task)
**Scenario:** [`marketplace_lossy.yaml`](marketplace_lossy.yaml) — the built-in `marketplace` scenario with exactly one setting changed.

## The change

```yaml
failures:
  message_drop: 0.0   # baseline
  message_drop: 0.15  # this experiment
```

Everything else (seed 42, 50 buyers / 50 sellers, 10 rounds, all 12 default layers) is identical to the bundled `marketplace` scenario.

## Why this setting

The baseline marketplace run is suspiciously perfect: 100% delivery, 100% success, zero drops, all three validators green. That says nothing about *resilience*, which is the point of a framework for validating distributed protocols. Message loss is the most fundamental distributed-systems failure, and 15% is high enough to hurt without collapsing everything — so we can observe *how* the protocol degrades, not just *that* it does.

## Hypothesis (written before running)

1. `delivery_rate` falls to ≈ 0.85, matching the drop probability directly.
2. Deal completion falls *more* than delivery, because a deal needs a multi-leg round trip — naive estimate ≈ 0.85³ ≈ 61% unless the protocol retries.
3. The `marketplace_all_responded` validator fails.
4. `dropped_count` > 0 and `deal_rate` falls below the baseline 0.532.

## Results

| Metric | Baseline | `message_drop: 0.15` |
|---|---|---|
| delivery_rate | 1.000 | **0.850** |
| success_rate | 1.000 | 0.850 |
| message sends | 1,000 | **300** |
| dropped_count | 0 | 45 |
| deal_rate | 0.532 | 0.524 |
| rejection_rate | 0.468 | 0.283 |
| completed sales | 266 | 87 |
| unique buyer–seller pairs | 467 | 157 |
| validators | 3/3 PASS | **`marketplace_all_responded` FAIL** (32 unanswered requests) |

Predictions 1, 3 and 4 held. Prediction 2 was wrong in an interesting way.

## The surprise, and the investigation

**Dropping 15% of messages destroyed 70% of all marketplace activity.** Total sends collapsed from 1,000 to 300 — far beyond any multiplicative estimate. Meanwhile `deal_rate` (deals per answered request) barely moved (0.532 → 0.524), so the negotiation logic itself was unaffected; the market simply *stopped happening*.

Reading `nest_core/scenarios_builtin/marketplace.py` explains it. A buyer only advances to its next round inside `on_message` — after receiving a `sold:` or `reject:` reply. There is **no timeout and no retry**. So if either leg of a round trip is dropped, that buyer silently stalls for the rest of the simulation. One lost packet doesn't cost one exchange; it costs every remaining round for that buyer.

This predicts geometric decay: each round survives with p = 0.85² = 0.7225, so a buyer's expected number of requests is Σ 0.7225^k (k = 0…9) ≈ **3.46**. A trace-analysis script (counting `send` events per buyer in the JSONL traces) measured **3.32** — and the per-buyer distribution is textbook geometric:

| requests sent before stalling | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| # of buyers (of 50) | 19 | 7 | 8 | 4 | 3 | 1 | 2 | 1 | 5 |

19 of 50 buyers died after their *first* message; only 5 completed all 10 rounds.

Two smaller findings from the same investigation:

- **`success_rate` is a delivery metric, not a business metric.** It came out exactly equal to `delivery_rate` (0.85). The baseline's "100% success" measures message delivery, not deals — worth knowing before quoting it.
- **The metrics can mask a dead market.** `deal_rate` looked healthy (0.524) while the market did one-third of its normal volume. Rate metrics need volume metrics next to them.

## Takeaway

The marketplace protocol is fire-and-forget: correct on a perfect network, but with no timeout/retry loop its effective throughput decays geometrically under even modest loss. A single retry-on-timeout in `BuyerAgent` (the codebase already has a `ctx.schedule` primitive) would change the failure mode from "permanent stall" to "one-round delay."

## Reproducing

```bash
pip install "nest-core[plugins]"
nest run marketplace                                      # baseline
nest run scenarios/community/marketplace_lossy/marketplace_lossy.yaml
nest report traces/marketplace_lossy.jsonl -o report.html
python -c "from pathlib import Path; from nest_core.validators import validate_trace; print(*validate_trace(Path('traces/marketplace_lossy.jsonl'), 'marketplace'), sep='\n')"
```

Tier 1 with a fixed seed, so runs are deterministic and these numbers reproduce exactly.

## Use of AI and other help

This experiment was done with Claude Code (Anthropic) driving the terminal: it ran the quickstart, copied and edited the scenario YAML, ran both simulations, and wrote the trace-analysis script and this README. The choice of setting, the hypothesis, and the stall-mechanism explanation were developed in conversation with it; the mechanism was verified by reading the installed `nest_core` source and confirmed quantitatively against the trace (predicted 3.46 vs measured 3.32 requests/buyer). No other outside help was used.
