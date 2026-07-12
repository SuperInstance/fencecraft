"""
Fencecraft — Visual fence builder for Working Animal Architecture.

Design conservation-law fences visually and compile them to FLUX bytecode.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any

from fencecraft.rules import (
    BudgetRule,
    DensityRule,
    FenceRule,
    RateRule,
    ScopeRule,
)
from fencecraft.compiler import FluxBytecode, FluxCompiler

__version__ = "0.1.0"
__all__ = [
    "FenceBuilder",
    "Canvas",
    "Zone",
    "FenceRule",
    "BudgetRule",
    "RateRule",
    "ScopeRule",
    "DensityRule",
    "FluxBytecode",
    "FluxCompiler",
]

# Default visual palette for rule types
_DEFAULT_COLORS = {
    "budget": "#4CAF50",
    "rate": "#FF9800",
    "scope": "#2196F3",
    "density": "#9C27B0",
}

_DEFAULT_ICONS = {
    "budget": "💰",
    "rate": "⚡",
    "scope": "🎯",
    "density": "🏘️",
}

_DEFAULT_SHAPES = {
    "budget": "rect",
    "rate": "diamond",
    "scope": "hex",
    "density": "rect",
}


@dataclass
class Zone:
    """A canvas zone that can contain rules."""

    name: str
    bounds: tuple[float, float, float, float] = (0.0, 0.0, 800.0, 600.0)
    color: str = "#E0E0E0"
    zone_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.zone_id,
            "name": self.name,
            "bounds": list(self.bounds),
            "color": self.color,
        }


@dataclass
class Canvas:
    """Visual canvas metadata for a fence designer GUI."""

    width: float = 1200.0
    height: float = 800.0
    background: str = "#FAFAFA"
    zones: list[Zone] = field(default_factory=list)
    grid_enabled: bool = True
    grid_size: float = 40.0

    def add_zone(self, zone: Zone) -> None:
        self.zones.append(zone)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "background": self.background,
            "grid": {"enabled": self.grid_enabled, "size": self.grid_size},
            "zones": [z.to_dict() for z in self.zones],
        }


class FenceBuilder:
    """
    Visual builder for conservation-law fences.

    Rules are added as visual cards on a canvas and compiled to FLUX bytecode.

    Example::

        fence = FenceBuilder(name="api-guardrail")
        fence.add_rule(BudgetRule(resource="tokens", limit=100_000, window="daily"))
        bytecode = fence.compile()
    """

    def __init__(
        self,
        name: str = "unnamed-fence",
        description: str = "",
        canvas: Canvas | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.canvas = canvas or Canvas()
        self._rules: list[FenceRule] = []
        self._properties: dict[str, Any] = {
            "version": "0.1.0",
            "strict": True,
        }

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: FenceRule) -> FenceRule:
        """Add a rule to the fence. Returns the rule for chaining."""
        # Auto-assign visual defaults if not set
        rule_type = rule.rule_type
        if rule.color is None:
            rule.color = _DEFAULT_COLORS.get(rule_type, "#607D8B")
        if rule.icon is None:
            rule.icon = _DEFAULT_ICONS.get(rule_type, "📌")
        if rule.shape is None:
            rule.shape = _DEFAULT_SHAPES.get(rule_type, "rect")
        self._rules.append(rule)
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by its ID. Returns True if found."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def get_rule(self, rule_id: str) -> FenceRule | None:
        """Retrieve a rule by ID."""
        for r in self._rules:
            if r.rule_id == rule_id:
                return r
        return None

    @property
    def rules(self) -> list[FenceRule]:
        """All rules in this fence."""
        return list(self._rules)

    # ------------------------------------------------------------------
    # Zone management
    # ------------------------------------------------------------------

    def add_zone(self, name: str, bounds: tuple[float, float, float, float] | None = None) -> Zone:
        """Add a canvas zone."""
        zone = Zone(
            name=name,
            bounds=bounds or (0.0, 0.0, self.canvas.width, self.canvas.height),
        )
        self.canvas.add_zone(zone)
        return zone

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def set_property(self, key: str, value: Any) -> None:
        """Set a fence metadata property."""
        self._properties[key] = value

    def get_property(self, key: str, default: Any = None) -> Any:
        return self._properties.get(key, default)

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------

    def compile(self) -> FluxBytecode:
        """Compile visual rules into FLUX bytecode."""
        compiler = FluxCompiler()
        return compiler.compile(self)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the fence to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "properties": copy.deepcopy(self._properties),
            "canvas": self.canvas.to_dict(),
            "rules": [r.to_dict() for r in self._rules],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FenceBuilder:
        """Deserialize from a dictionary."""
        canvas_data = data.get("canvas", {})
        canvas = Canvas(
            width=canvas_data.get("width", 1200.0),
            height=canvas_data.get("height", 800.0),
        )
        builder = cls(
            name=data.get("name", "unnamed-fence"),
            description=data.get("description", ""),
            canvas=canvas,
        )
        builder._properties = data.get("properties", {"version": "0.1.0"})
        for rule_data in data.get("rules", []):
            rule = _deserialize_rule(rule_data)
            if rule:
                builder._rules.append(rule)
        return builder

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"FenceBuilder(name={self.name!r}, "
            f"rules={len(self._rules)})"
        )


# ---------------------------------------------------------------------------
# Rule deserialization helper
# ---------------------------------------------------------------------------

_RULE_CLASSES: dict[str, type[FenceRule]] = {
    "budget": BudgetRule,
    "rate": RateRule,
    "scope": ScopeRule,
    "density": DensityRule,
}


def _deserialize_rule(data: dict[str, Any]) -> FenceRule | None:
    """Reconstruct a rule from its serialized dict."""
    rtype = data.get("rule_type")
    cls = _RULE_CLASSES.get(rtype)
    if cls is None:
        return None
    # Build kwargs from data, excluding the rule_type
    kwargs = {k: v for k, v in data.items() if k != "rule_type"}
    try:
        return cls(**kwargs)
    except TypeError:
        # Forward-compat: ignore unknown keys
        import inspect

        sig = inspect.signature(cls)
        known = set(sig.parameters)
        clean = {k: v for k, v in kwargs.items() if k in known}
        return cls(**clean)
