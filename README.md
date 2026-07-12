# Fencecraft

> Visual fence builder for **Working Animal Architecture**

In the Working Animal Architecture paradigm, **fences** are conservation laws that keep computational animals bounded — resource limits, rate caps, scope boundaries, and density constraints. Fencecraft lets you **design fences visually** instead of hand-writing FLUX bytecode.

## Quick Start

```bash
pip install fencecraft
```

```python
from fencecraft import FenceBuilder
from fencecraft.rules import BudgetRule, RateRule, ScopeRule, DensityRule

# Build a fence visually
fence = FenceBuilder(name="api-guardrail")

fence.add_rule(BudgetRule(
    resource="tokens",
    limit=100_000,
    window="daily",
    on_exceed="throttle",
))

fence.add_rule(RateRule(
    resource="requests",
    max_per_second=50,
    burst=100,
))

fence.add_rule(ScopeRule(
    allowed_domains=["api.example.com", "*.internal.dev"],
    denied_patterns=["*.prod.*"],
))

fence.add_rule(DensityRule(
    zone="concurrent-agents",
    max_per_zone=8,
))

# Compile to FLUX bytecode
bytecode = fence.compile()
print(bytecode.dump())
```

Output:

```
FLUX BYTECODE — fence "api-guardrail"
═══════════════════════════════════════
 0  PUSH           fence.api-guardrail
 1  SET_BUDGET     tokens 100000 daily throttle
 2  ENFORCE_RATE   requests 50 100
 3  DEFINE_SCOPE   allow [api.example.com, *.internal.dev]
 4  DEFINE_SCOPE   deny [*.prod.*]
 5  LIMIT_DENSITY  concurrent-agents 8
 6  BIND_FENCE
 7  HALT
═══════════════════════════════════════
```

## Rule Types

| Rule | Icon | Purpose |
|------|------|---------|
| **BudgetRule** | 💰 | Cap total resource consumption over a window |
| **RateRule** | ⚡ | Limit throughput (requests/sec with burst) |
| **ScopeRule** | 🎯 | Define allowed/denied domains & patterns |
| **DensityRule** | 🏘️ | Limit concentration per zone |

## Templates

Fencecraft ships with pre-built fence templates:

```python
from fencecraft.templates import TEMPLATES

# Production API guardrail
fence = TEMPLATES["api-guardrail"].build()

# Cost containment fence
fence = TEMPLATES["cost-containment"].build()

# Sandboxed execution boundary
fence = TEMPLATES["sandbox"].build()

# Multi-tenant partition fence
fence = TEMPLATES["multi-tenant"].build()
```

## Visual Canvas

FenceBuilder tracks visual metadata so a GUI designer can render rules as draggable cards on a canvas:

```python
fence.canvas.to_dict()
# {
#   "zones": [...],
#   "rules": [
#     {"id": "r1", "type": "budget", "position": [120, 80], "color": "#4CAF50", ...},
#     ...
#   ],
#   "connections": [...]
# }
```

Each rule has:
- **position** — `[x, y]` canvas coordinates
- **color** — hex color for the rule card
- **icon** — emoji/symbol for visual identification
- **shape** — card shape (`"rect"`, `"diamond"`, `"hex"`)

## FLUX Bytecode

The compiler transforms visual rules into linear FLUX instructions:

| Opcode | Arguments | Effect |
|--------|-----------|--------|
| `PUSH` | label | Push fence context |
| `SET_BUDGET` | resource, limit, window, action | Enforce budget cap |
| `ENFORCE_RATE` | resource, rate, burst | Token-bucket rate limit |
| `DEFINE_SCOPE` | mode, patterns | Allow/deny scope |
| `LIMIT_DENSITY` | zone, max | Per-zone density cap |
| `BIND_FENCE` | — | Activate fence |
| `HALT` | — | End fence definition |

## API Reference

### `FenceBuilder(name=..., description=...)`

- `.add_rule(rule)` — Add a fence rule
- `.remove_rule(rule_id)` — Remove by ID
- `.add_zone(name, bounds)` — Define a canvas zone
- `.set_property(key, value)` — Set fence metadata
- `.compile()` — Returns `FluxBytecode`
- `.to_dict()` / `.from_dict()` — Serialize/deserialize
- `.canvas` — `Canvas` object with visual metadata

### Rule Classes

All rules extend `FenceRule` and accept `rule_id`, `position`, `color`, `icon`, `shape` as optional visual kwargs.

## License

MIT
