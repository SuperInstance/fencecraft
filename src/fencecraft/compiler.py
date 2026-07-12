"""
FLUX bytecode compiler for Fencecraft.

Transforms visual FenceBuilder rules into linear FLUX instructions:

    PUSH        fence.<name>
    SET_BUDGET  <resource> <limit> <window> <action>
    ENFORCE_RATE <resource> <rate> <burst>
    DEFINE_SCOPE allow|deny [<patterns>]
    LIMIT_DENSITY <zone> <max>
    BIND_FENCE
    HALT

Each instruction is a tuple of (opcode, *operands). The compiled
``FluxBytecode`` object can dump human-readable listings or return
the raw instruction list for a virtual machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fencecraft.rules import (
    BudgetRule,
    DensityRule,
    FenceRule,
    RateRule,
    ScopeRule,
)


@dataclass
class Instruction:
    """A single FLUX bytecode instruction."""

    opcode: str
    operands: tuple[Any, ...] = ()

    def __repr__(self) -> str:
        parts = " ".join(str(o) for o in self.operands)
        return f"{self.opcode:<16} {parts}".rstrip()

    def to_tuple(self) -> tuple[str, ...]:
        return (self.opcode, *(str(o) for o in self.operands))


@dataclass
class FluxBytecode:
    """Compiled FLUX bytecode for a fence."""

    fence_name: str
    instructions: list[Instruction] = field(default_factory=list)

    def dump(self) -> str:
        """Return a human-readable bytecode listing."""
        width = max(
            (len(f"{i}  {ins.opcode}") for i, ins in enumerate(self.instructions)),
            default=0,
        )
        lines = [
            f'FLUX BYTECODE — fence "{self.fence_name}"',
            "═" * 48,
        ]
        for i, ins in enumerate(self.instructions):
            operand_str = " ".join(str(o) for o in ins.operands)
            if operand_str:
                lines.append(f"{i:<2} {ins.opcode:<16} {operand_str}")
            else:
                lines.append(f"{i:<2} {ins.opcode}")
        lines.append("═" * 48)
        return "\n".join(lines)

    def to_list(self) -> list[list[str]]:
        """Return instructions as a list of [opcode, *operand_strings]."""
        return [list(ins.to_tuple()) for ins in self.instructions]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fence_name": self.fence_name,
            "instructions": self.to_list(),
        }


class FluxCompiler:
    """
    Compiles a FenceBuilder's rules into FLUX bytecode.

    Rule compilation order:
      1. Budget rules (foundational caps)
      2. Rate rules (throughput enforcement)
      3. Scope rules (boundary definitions)
      4. Density rules (concentration limits)

    The compiler always emits BIND_FENCE and HALT as terminators.
    """

    def compile(self, builder: Any) -> FluxBytecode:
        """
        Compile a FenceBuilder into FluxBytecode.

        Args:
            builder: A FenceBuilder instance with rules.

        Returns:
            FluxBytecode with the compiled instruction stream.
        """
        # Import here to avoid circular import at module level
        rules: list[FenceRule] = builder.rules
        bytecode = FluxBytecode(fence_name=builder.name)

        # PUSH fence context
        bytecode.instructions.append(
            Instruction("PUSH", (f"fence.{builder.name}",))
        )

        # Compile rules in canonical order
        order = [
            (BudgetRule, self._compile_budget),
            (RateRule, self._compile_rate),
            (ScopeRule, self._compile_scope),
            (DensityRule, self._compile_density),
        ]

        for rule_cls, compile_fn in order:
            for rule in rules:
                if isinstance(rule, rule_cls):
                    compile_fn(rule, bytecode.instructions)

        # Terminators
        bytecode.instructions.append(Instruction("BIND_FENCE"))
        bytecode.instructions.append(Instruction("HALT"))

        return bytecode

    # ------------------------------------------------------------------
    # Per-type compilers
    # ------------------------------------------------------------------

    @staticmethod
    def _compile_budget(rule: BudgetRule, instructions: list[Instruction]) -> None:
        instructions.append(
            Instruction(
                "SET_BUDGET",
                (rule.resource, rule.limit, rule.window, rule.on_exceed),
            )
        )

    @staticmethod
    def _compile_rate(rule: RateRule, instructions: list[Instruction]) -> None:
        burst = rule.burst or rule.max_per_second
        instructions.append(
            Instruction(
                "ENFORCE_RATE",
                (rule.resource, rule.max_per_second, burst),
            )
        )

    @staticmethod
    def _compile_scope(rule: ScopeRule, instructions: list[Instruction]) -> None:
        if rule.allowed_domains:
            instructions.append(
                Instruction(
                    "DEFINE_SCOPE",
                    ("allow", f"[{', '.join(rule.allowed_domains)}]"),
                )
            )
        if rule.denied_patterns:
            instructions.append(
                Instruction(
                    "DEFINE_SCOPE",
                    ("deny", f"[{', '.join(rule.denied_patterns)}]"),
                )
            )
        # If neither is set, emit a scope mode marker
        if not rule.allowed_domains and not rule.denied_patterns:
            instructions.append(
                Instruction("DEFINE_SCOPE", (rule.mode, "[]"))
            )

    @staticmethod
    def _compile_density(rule: DensityRule, instructions: list[Instruction]) -> None:
        instructions.append(
            Instruction(
                "LIMIT_DENSITY",
                (rule.zone, rule.max_per_zone),
            )
        )
