# SPDX-License-Identifier: Apache-2.0
"""Drop only the retailer->supplier confirmation hop and compare reality
(items the retailer actually received) with what the supplier can see
(delivered confirmations that make it back).

Per-link loss is not a supported scenario setting, so this drives the
Simulator directly with a custom drop rule. Extra investigation, not the
official one-setting experiment.
"""
import asyncio
import json
from pathlib import Path

import yaml

import nest_core
from nest_core.scenario import ScenarioConfig
from nest_core.scenarios_builtin.supply_chain import supply_chain_factory
from nest_core.sim.simulator import Simulator

SEEDS = range(1, 201)
ITEMS = 15.0
TRACE = Path("traces/_lasthop_tmp.jsonl")

yaml_path = Path(nest_core.__file__).parent / "scenarios_builtin" / "yaml" / "supply_chain.yaml"
config = ScenarioConfig(**yaml.safe_load(yaml_path.read_text()))


class LastHopLossySimulator(Simulator):
    last_hop_drop = 0.0

    def _should_drop(self, sender, target) -> bool:
        if str(sender) == "retailer-0":
            return self._failure_rng.random() < self.last_hop_drop
        return False


print(f"{'last-hop loss':>13s} | {'retailer got goods':>18s} | {'supplier sees delivered':>23s}")
for rate in (0.75, 0.50, 0.25, 0.05):
    goods = 0
    confirmations = 0
    for seed in SEEDS:
        LastHopLossySimulator.last_hop_drop = rate
        TRACE.parent.mkdir(exist_ok=True)
        sim = LastHopLossySimulator(seed=seed, trace_path=TRACE)
        agents = supply_chain_factory(config, {})
        for agent_id, agent in agents.items():
            sim.add_agent(agent_id, agent)
        asyncio.run(sim.run(max_ticks=config.get_max_ticks()))
        goods += agents["retailer-0"]._received
        for line in TRACE.read_text().splitlines():
            e = json.loads(line)
            if e["kind"] == "receive" and e["agent"] == "supplier-0":
                confirmations += 1

    n = len(list(SEEDS))
    print(f"{rate:>12.0%} | {goods / (ITEMS * n):>18.1%} | {confirmations / (ITEMS * n):>23.1%}")

TRACE.unlink(missing_ok=True)
