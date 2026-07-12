"""
Pre-built fence templates for common scenarios.

Usage::

    from fencecraft.templates import TEMPLATES
    fence = TEMPLATES["api-guardrail"].build()
    bytecode = fence.compile()
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from fencecraft import FenceBuilder
from fencecraft.rules import (
    BudgetRule,
    DensityRule,
    RateRule,
    ScopeRule,
)


@dataclass
class FenceTemplate:
    """
    A reusable fence template.

    Call ``.build()`` to get a FenceBuilder instance pre-populated with
    the template's rules. Pass overrides to customize::

        fence = TEMPLATES["api-guardrail"].build(
            budget_limit=500_000,
            rate=100,
        )
    """

    name: str
    description: str
    rules: list[dict[str, Any]] = field(default_factory=list)
    zones: list[dict[str, Any]] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)

    def build(self, **overrides: Any) -> FenceBuilder:
        """
        Instantiate a FenceBuilder from this template.

        Keyword overrides:
            budget_limit  — override the BudgetRule.limit
            rate          — override RateRule.max_per_second
            burst         — override RateRule.burst
            max_agents    — override DensityRule.max_per_zone
        """
        builder = FenceBuilder(
            name=self.name,
            description=self.description,
        )

        # Apply properties
        for key, value in self.properties.items():
            builder.set_property(key, value)

        # Add zones
        for zone_data in self.zones:
            builder.add_zone(zone_data["name"], zone_data.get("bounds"))

        # Add rules (deep-copy so templates are reusable)
        for rule_dict in copy.deepcopy(self.rules):
            rtype = rule_dict.pop("rule_type", None)
            # Apply overrides
            if rtype == "budget" and "budget_limit" in overrides:
                rule_dict["limit"] = overrides["budget_limit"]
            if rtype == "rate":
                if "rate" in overrides:
                    rule_dict["max_per_second"] = overrides["rate"]
                if "burst" in overrides:
                    rule_dict["burst"] = overrides["burst"]
            if rtype == "density" and "max_agents" in overrides:
                rule_dict["max_per_zone"] = overrides["max_agents"]

            rule = _build_rule(rtype, rule_dict)
            if rule:
                builder.add_rule(rule)

        return builder


def _build_rule(rtype: str | None, kwargs: dict[str, Any]) -> Any:
    """Dispatch to the correct rule constructor."""
    if rtype == "budget":
        return BudgetRule(**kwargs)
    if rtype == "rate":
        return RateRule(**kwargs)
    if rtype == "scope":
        return ScopeRule(**kwargs)
    if rtype == "density":
        return DensityRule(**kwargs)
    return None


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, FenceTemplate] = {

    "api-guardrail": FenceTemplate(
        name="api-guardrail",
        description=(
            "Production API guardrail — token budget, request rate limiting, "
            "and domain scoping."
        ),
        rules=[
            {
                "rule_type": "budget",
                "resource": "tokens",
                "limit": 100_000,
                "window": "daily",
                "on_exceed": "throttle",
            },
            {
                "rule_type": "rate",
                "resource": "requests",
                "max_per_second": 50,
                "burst": 100,
            },
            {
                "rule_type": "scope",
                "allowed_domains": ["api.example.com", "*.internal.dev"],
                "denied_patterns": ["*.prod.*"],
                "mode": "allowlist",
            },
        ],
        zones=[
            {"name": "ingress", "bounds": (0, 0, 600, 400)},
            {"name": "processing", "bounds": (600, 0, 1200, 400)},
        ],
        properties={"strict": True, "tags": ["production", "api"]},
    ),

    "cost-containment": FenceTemplate(
        name="cost-containment",
        description=(
            "Cost containment fence — strict spending caps with aggressive "
            "budget enforcement and low concurrency."
        ),
        rules=[
            {
                "rule_type": "budget",
                "resource": "dollars",
                "limit": 50,
                "window": "daily",
                "on_exceed": "block",
            },
            {
                "rule_type": "budget",
                "resource": "tokens",
                "limit": 10_000,
                "window": "hour",
                "on_exceed": "block",
            },
            {
                "rule_type": "density",
                "zone": "concurrent-agents",
                "max_per_zone": 3,
                "spill_action": "queue",
            },
        ],
        zones=[
            {"name": "budget-pool", "bounds": (0, 0, 800, 200)},
        ],
        properties={"strict": True, "tags": ["cost", "frugal"]},
    ),

    "sandbox": FenceTemplate(
        name="sandbox",
        description=(
            "Sandboxed execution boundary — tight scope restrictions, "
            "no network egress, low density."
        ),
        rules=[
            {
                "rule_type": "scope",
                "allowed_domains": ["localhost", "127.0.0.1"],
                "denied_patterns": ["*", "10.*", "192.168.*", "172.16.*"],
                "mode": "allowlist",
            },
            {
                "rule_type": "budget",
                "resource": "cpu-seconds",
                "limit": 30,
                "window": "total",
                "on_exceed": "block",
            },
            {
                "rule_type": "rate",
                "resource": "syscalls",
                "max_per_second": 100,
                "burst": 200,
            },
            {
                "rule_type": "density",
                "zone": "sandbox",
                "max_per_zone": 1,
                "spill_action": "reject",
            },
        ],
        zones=[
            {"name": "sandbox", "bounds": (0, 0, 400, 400)},
        ],
        properties={"strict": True, "tags": ["sandbox", "security"]},
    ),

    "multi-tenant": FenceTemplate(
        name="multi-tenant",
        description=(
            "Multi-tenant partition fence — per-tenant isolation with "
            "shared rate limits and density caps."
        ),
        rules=[
            {
                "rule_type": "budget",
                "resource": "tokens",
                "limit": 50_000,
                "window": "daily",
                "on_exceed": "throttle",
            },
            {
                "rule_type": "rate",
                "resource": "requests",
                "max_per_second": 20,
                "burst": 50,
            },
            {
                "rule_type": "density",
                "zone": "tenant-workers",
                "max_per_zone": 5,
                "spill_action": "queue",
            },
            {
                "rule_type": "density",
                "zone": "shared-cache",
                "max_per_zone": 2,
                "spill_action": "evict",
            },
            {
                "rule_type": "scope",
                "allowed_domains": ["tenant.*.internal"],
                "denied_patterns": ["tenant.*.admin"],
                "mode": "allowlist",
            },
        ],
        zones=[
            {"name": "tenant-a", "bounds": (0, 0, 400, 400)},
            {"name": "tenant-b", "bounds": (400, 0, 800, 400)},
            {"name": "shared", "bounds": (0, 400, 800, 600)},
        ],
        properties={"strict": True, "tags": ["multi-tenant", "isolation"]},
    ),
}
