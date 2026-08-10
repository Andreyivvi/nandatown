# SPDX-License-Identifier: Apache-2.0
"""Sweep first-hop-only loss rates (75/50/25/5%) and check whether the damage
passes through unchanged to every downstream station.

Per-link loss is not a supported scenario setting, so this drives the
Simulator directly with a custom drop rule. Extra investigation, not the
official one-setting experiment.
"""
import asyncio
from pathlib import Path

import yaml

import nest_core
from nest_core.scenario import ScenarioConfig
from nest_core.scenarios_builtin.supply_chain import supply_chain_factory
from nest_core.sim.simulator import Simulator

SEEDS = range(1, 201)
ITEMS = 15.0

yaml_path = Path(nest_core.__file__).parent / "scenarios_builtin" / "yaml" / "supply_chain.yaml"
config = ScenarioConfig(**yaml.safe_load(yaml_path.read_text()))


class FirstHopLossySimulator(Simulator):
    first_hop_drop = 0.0

    def _should_drop(self, sender, target) -> bool:
        if str(sender) == "supplier-0":
            return self._failure_rng.random() < self.first_hop_drop
        return False


print(f"{'first-hop loss':>14s} | {'survives':>8s} | {'manufacturer':>12s} | {'distributor':>11s} | {'retailer':>8s}")
for rate in (0.75, 0.50, 0.25, 0.05):
    totals = {"manufacturer-0": 0, "distributor-0": 0, "retailer-0": 0}
    for seed in SEEDS:
        FirstHopLossySimulator.first_hop_drop = rate
        sim = FirstHopLossySimulator(seed=seed)
        agents = supply_chain_factory(config, {})
        for agent_id, agent in agents.items():
            sim.add_agent(agent_id, agent)
        asyncio.run(sim.run(max_ticks=config.get_max_ticks()))
        totals["manufacturer-0"] += agents["manufacturer-0"]._produced
        totals["distributor-0"] += agents["distributor-0"]._forwarded
        totals["retailer-0"] += agents["retailer-0"]._received

    n = len(list(SEEDS))
    m, d, r = (totals[k] / (ITEMS * n) for k in ("manufacturer-0", "distributor-0", "retailer-0"))
    print(f"{rate:>13.0%} | {1 - rate:>8.0%} | {m:>12.1%} | {d:>11.1%} | {r:>8.1%}")
