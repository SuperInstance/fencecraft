"""
Rule definitions for Fencecraft fences.

Each rule type represents a conservation law:
  - BudgetRule   → total resource caps (💰)
  - RateRule     → throughput limits (⚡)
  - ScopeRule    → boundary/scope definitions (🎯)
  - DensityRule  → per-zone concentration limits (🏘️)
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class FenceRule:
    """Base class for all fence rules."""

    # Visual metadata
    rule_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    position: tuple[float, float] | None = None
    color: str | None = None
    icon: str | None = None
    shape: str | None = None

    # Each subclass defines its type string
    rule_type: ClassVar[str] = "base"

    def to_dict(self) -> dict[str, Any]:
        """Serialize this rule to a dictionary."""
        result: dict[str, Any] = {
            "rule_type": self.rule_type,
            "rule_id": self.rule_id,
        }
        if self.position is not None:
            result["position"] = list(self.position)
        if self.color is not None:
            result["color"] = self.color
        if self.icon is not None:
            result["icon"] = self.icon
        if self.shape is not None:
            result["shape"] = self.shape
        return result


# ---------------------------------------------------------------------------
# Budget Rule
# ---------------------------------------------------------------------------

VALID_WINDOWS = {"second", "minute", "hour", "daily", "weekly", "monthly", "total"}
VALID_BUDGET_ACTIONS = {"throttle", "block", "alert", "shed"}


@dataclass
class BudgetRule(FenceRule):
    """
    Cap total resource consumption over a time window.

    Args:
        resource: What is being budgeted (e.g. "tokens", "api-calls").
        limit: Maximum amount allowed.
        window: Time window — one of second/minute/hour/daily/weekly/monthly/total.
        on_exceed: Action when budget is exceeded — throttle/block/alert/shed.
    """

    resource: str = "tokens"
    limit: int = 0
    window: str = "daily"
    on_exceed: str = "block"

    rule_type: ClassVar[str] = "budget"

    def __post_init__(self) -> None:
        if self.limit < 0:
            raise ValueError(f"BudgetRule limit must be >= 0, got {self.limit}")
        if self.window not in VALID_WINDOWS:
            raise ValueError(
                f"BudgetRule window must be one of {VALID_WINDOWS}, got {self.window!r}"
            )
        if self.on_exceed not in VALID_BUDGET_ACTIONS:
            raise ValueError(
                f"BudgetRule on_exceed must be one of {VALID_BUDGET_ACTIONS}, "
                f"got {self.on_exceed!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update(
            resource=self.resource,
            limit=self.limit,
            window=self.window,
            on_exceed=self.on_exceed,
        )
        return d


# ---------------------------------------------------------------------------
# Rate Rule
# ---------------------------------------------------------------------------

@dataclass
class RateRule(FenceRule):
    """
    Token-bucket rate limiter.

    Args:
        resource: What is being rate-limited.
        max_per_second: Steady-state rate ceiling.
        burst: Maximum burst capacity (>= max_per_second).
    """

    resource: str = "requests"
    max_per_second: float = 1.0
    burst: float = 0.0

    rule_type: ClassVar[str] = "rate"

    def __post_init__(self) -> None:
        if self.max_per_second < 0:
            raise ValueError(
                f"RateRule max_per_second must be >= 0, got {self.max_per_second}"
            )
        effective_burst = self.burst or self.max_per_second
        if effective_burst < self.max_per_second:
            raise ValueError(
                f"RateRule burst ({effective_burst}) must be >= "
                f"max_per_second ({self.max_per_second})"
            )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update(
            resource=self.resource,
            max_per_second=self.max_per_second,
            burst=self.burst,
        )
        return d


# ---------------------------------------------------------------------------
# Scope Rule
# ---------------------------------------------------------------------------

_GLOB_RE = re.compile(r"^[a-zA-Z0-9.*?_-]+$")


@dataclass
class ScopeRule(FenceRule):
    """
    Define allowed and denied domains/patterns.

    Args:
        allowed_domains: Glob patterns for permitted scope.
        denied_patterns: Glob patterns for explicitly blocked scope.
        mode: Either "allowlist" (default deny) or "denylist" (default allow).
    """

    allowed_domains: list[str] = field(default_factory=list)
    denied_patterns: list[str] = field(default_factory=list)
    mode: str = "allowlist"

    rule_type: ClassVar[str] = "scope"

    def __post_init__(self) -> None:
        if self.mode not in ("allowlist", "denylist"):
            raise ValueError(
                f"ScopeRule mode must be 'allowlist' or 'denylist', got {self.mode!r}"
            )
        for pattern in (*self.allowed_domains, *self.denied_patterns):
            if not _GLOB_RE.match(pattern):
                raise ValueError(
                    f"ScopeRule contains invalid pattern: {pattern!r}"
                )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update(
            allowed_domains=list(self.allowed_domains),
            denied_patterns=list(self.denied_patterns),
            mode=self.mode,
        )
        return d


# ---------------------------------------------------------------------------
# Density Rule
# ---------------------------------------------------------------------------

@dataclass
class DensityRule(FenceRule):
    """
    Limit the concentration of items within a named zone.

    Args:
        zone: Zone name (must match a zone on the canvas or be free-form).
        max_per_zone: Maximum items/agents allowed concurrently.
        spill_action: What to do when density is exceeded — queue/reject/evict.
    """

    zone: str = "default"
    max_per_zone: int = 1
    spill_action: str = "queue"

    rule_type: ClassVar[str] = "density"

    _VALID_SPILL = {"queue", "reject", "evict"}

    def __post_init__(self) -> None:
        if self.max_per_zone < 1:
            raise ValueError(
                f"DensityRule max_per_zone must be >= 1, got {self.max_per_zone}"
            )
        if self.spill_action not in self._VALID_SPILL:
            raise ValueError(
                f"DensityRule spill_action must be one of {self._VALID_SPILL}, "
                f"got {self.spill_action!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update(
            zone=self.zone,
            max_per_zone=self.max_per_zone,
            spill_action=self.spill_action,
        )
        return d
