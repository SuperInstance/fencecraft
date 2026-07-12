"""Tests for fencecraft — visual fence builder."""

from __future__ import annotations

import pytest

from fencecraft import FenceBuilder, Canvas, Zone
from fencecraft.rules import BudgetRule, RateRule, ScopeRule, DensityRule
from fencecraft.compiler import FluxBytecode, FluxCompiler, Instruction
from fencecraft.templates import TEMPLATES, FenceTemplate


# ---------------------------------------------------------------------------
# Rule tests
# ---------------------------------------------------------------------------

class TestBudgetRule:
    def test_basic_creation(self):
        rule = BudgetRule(resource="tokens", limit=1000, window="daily")
        assert rule.resource == "tokens"
        assert rule.limit == 1000
        assert rule.window == "daily"
        assert rule.on_exceed == "block"  # default
        assert rule.rule_type == "budget"

    def test_all_actions(self):
        for action in ("throttle", "block", "alert", "shed"):
            rule = BudgetRule(limit=100, on_exceed=action)
            assert rule.on_exceed == action

    def test_invalid_window(self):
        with pytest.raises(ValueError, match="window"):
            BudgetRule(limit=100, window="fortnight")

    def test_invalid_action(self):
        with pytest.raises(ValueError, match="on_exceed"):
            BudgetRule(limit=100, on_exceed="explode")

    def test_negative_limit(self):
        with pytest.raises(ValueError, match="limit"):
            BudgetRule(limit=-1)

    def test_serialization(self):
        rule = BudgetRule(resource="dollars", limit=500, window="monthly", on_exceed="alert")
        d = rule.to_dict()
        assert d["resource"] == "dollars"
        assert d["limit"] == 500
        assert d["window"] == "monthly"
        assert d["on_exceed"] == "alert"
        assert d["rule_type"] == "budget"


class TestRateRule:
    def test_basic_creation(self):
        rule = RateRule(resource="requests", max_per_second=100, burst=200)
        assert rule.max_per_second == 100
        assert rule.burst == 200

    def test_burst_defaults_to_rate(self):
        rule = RateRule(max_per_second=50)
        assert rule.burst == 0.0  # stored as 0, compiler uses max_per_second

    def test_negative_rate(self):
        with pytest.raises(ValueError, match="max_per_second"):
            RateRule(max_per_second=-1)

    def test_burst_less_than_rate(self):
        with pytest.raises(ValueError, match="burst"):
            RateRule(max_per_second=100, burst=50)

    def test_serialization(self):
        rule = RateRule(resource="rpc", max_per_second=10, burst=30)
        d = rule.to_dict()
        assert d["max_per_second"] == 10
        assert d["burst"] == 30


class TestScopeRule:
    def test_basic_creation(self):
        rule = ScopeRule(
            allowed_domains=["api.example.com", "*.dev"],
            denied_patterns=["*.evil.com"],
        )
        assert len(rule.allowed_domains) == 2
        assert len(rule.denied_patterns) == 1
        assert rule.mode == "allowlist"

    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="mode"):
            ScopeRule(mode="whitelist")

    def test_invalid_pattern(self):
        with pytest.raises(ValueError, match="pattern"):
            ScopeRule(allowed_domains=["valid.com", "bad pattern!"])

    def test_serialization(self):
        rule = ScopeRule(allowed_domains=["a.com"], denied_patterns=["b.com"])
        d = rule.to_dict()
        assert d["allowed_domains"] == ["a.com"]
        assert d["denied_patterns"] == ["b.com"]


class TestDensityRule:
    def test_basic_creation(self):
        rule = DensityRule(zone="workers", max_per_zone=4)
        assert rule.zone == "workers"
        assert rule.max_per_zone == 4
        assert rule.spill_action == "queue"

    def test_zero_density(self):
        with pytest.raises(ValueError, match="max_per_zone"):
            DensityRule(max_per_zone=0)

    def test_invalid_spill(self):
        with pytest.raises(ValueError, match="spill_action"):
            DensityRule(spill_action="explode")

    def test_serialization(self):
        rule = DensityRule(zone="cache", max_per_zone=2, spill_action="evict")
        d = rule.to_dict()
        assert d["zone"] == "cache"
        assert d["max_per_zone"] == 2
        assert d["spill_action"] == "evict"


# ---------------------------------------------------------------------------
# FenceBuilder tests
# ---------------------------------------------------------------------------

class TestFenceBuilder:
    def test_empty_builder(self):
        builder = FenceBuilder(name="test")
        assert builder.name == "test"
        assert len(builder.rules) == 0

    def test_add_rule_auto_visuals(self):
        builder = FenceBuilder(name="test")
        rule = builder.add_rule(BudgetRule(limit=100))
        assert rule.color is not None
        assert rule.icon is not None
        assert rule.shape is not None

    def test_add_multiple_rules(self):
        builder = FenceBuilder(name="test")
        builder.add_rule(BudgetRule(limit=100))
        builder.add_rule(RateRule(max_per_second=50))
        builder.add_rule(ScopeRule(allowed_domains=["*"]))
        builder.add_rule(DensityRule(max_per_zone=3))
        assert len(builder.rules) == 4

    def test_remove_rule(self):
        builder = FenceBuilder(name="test")
        rule = builder.add_rule(BudgetRule(limit=100))
        assert builder.remove_rule(rule.rule_id) is True
        assert len(builder.rules) == 0
        assert builder.remove_rule("nonexistent") is False

    def test_get_rule(self):
        builder = FenceBuilder(name="test")
        rule = builder.add_rule(BudgetRule(limit=100))
        found = builder.get_rule(rule.rule_id)
        assert found is rule
        assert builder.get_rule("nope") is None

    def test_add_zone(self):
        builder = FenceBuilder(name="test")
        zone = builder.add_zone("ingress", (0, 0, 100, 200))
        assert zone.name == "ingress"
        assert len(builder.canvas.zones) == 1

    def test_set_property(self):
        builder = FenceBuilder(name="test")
        builder.set_property("custom", "value")
        assert builder.get_property("custom") == "value"
        assert builder.get_property("missing", "default") == "default"

    def test_repr(self):
        builder = FenceBuilder(name="my-fence")
        builder.add_rule(BudgetRule(limit=10))
        assert "my-fence" in repr(builder)
        assert "rules=1" in repr(builder)

    def test_serialization_roundtrip(self):
        builder = FenceBuilder(name="roundtrip", description="test fence")
        builder.add_rule(BudgetRule(resource="tokens", limit=500, window="hour"))
        builder.add_rule(RateRule(max_per_second=25, burst=50))
        builder.add_rule(ScopeRule(allowed_domains=["api.dev"]))
        builder.add_rule(DensityRule(zone="workers", max_per_zone=3))
        builder.add_zone("main", (0, 0, 400, 400))

        data = builder.to_dict()
        restored = FenceBuilder.from_dict(data)

        assert restored.name == "roundtrip"
        assert len(restored.rules) == 4
        assert isinstance(restored.rules[0], BudgetRule)
        assert isinstance(restored.rules[1], RateRule)
        assert isinstance(restored.rules[2], ScopeRule)
        assert isinstance(restored.rules[3], DensityRule)
        assert restored.rules[0].limit == 500


# ---------------------------------------------------------------------------
# Compiler tests
# ---------------------------------------------------------------------------

class TestFluxCompiler:
    def test_compile_empty_fence(self):
        builder = FenceBuilder(name="empty")
        compiler = FluxCompiler()
        bytecode = compiler.compile(builder)
        assert isinstance(bytecode, FluxBytecode)
        # PUSH + BIND_FENCE + HALT = 3 instructions minimum
        assert len(bytecode.instructions) == 3
        assert bytecode.instructions[0].opcode == "PUSH"
        assert bytecode.instructions[-2].opcode == "BIND_FENCE"
        assert bytecode.instructions[-1].opcode == "HALT"

    def test_compile_budget(self):
        builder = FenceBuilder(name="budget-test")
        builder.add_rule(BudgetRule(resource="tokens", limit=1000, window="daily", on_exceed="throttle"))
        bytecode = builder.compile()

        budget_instr = [i for i in bytecode.instructions if i.opcode == "SET_BUDGET"]
        assert len(budget_instr) == 1
        assert budget_instr[0].operands == ("tokens", 1000, "daily", "throttle")

    def test_compile_rate(self):
        builder = FenceBuilder(name="rate-test")
        builder.add_rule(RateRule(resource="req", max_per_second=50, burst=100))
        bytecode = builder.compile()

        rate_instr = [i for i in bytecode.instructions if i.opcode == "ENFORCE_RATE"]
        assert len(rate_instr) == 1
        assert rate_instr[0].operands == ("req", 50, 100)

    def test_compile_scope(self):
        builder = FenceBuilder(name="scope-test")
        builder.add_rule(ScopeRule(
            allowed_domains=["api.com", "*.dev"],
            denied_patterns=["*.evil"],
        ))
        bytecode = builder.compile()

        scope_instr = [i for i in bytecode.instructions if i.opcode == "DEFINE_SCOPE"]
        assert len(scope_instr) == 2
        assert scope_instr[0].operands[0] == "allow"
        assert scope_instr[1].operands[0] == "deny"

    def test_compile_density(self):
        builder = FenceBuilder(name="density-test")
        builder.add_rule(DensityRule(zone="workers", max_per_zone=5))
        bytecode = builder.compile()

        density_instr = [i for i in bytecode.instructions if i.opcode == "LIMIT_DENSITY"]
        assert len(density_instr) == 1
        assert density_instr[0].operands == ("workers", 5)

    def test_compile_ordering(self):
        """Rules should compile in canonical order: budget → rate → scope → density."""
        builder = FenceBuilder(name="order-test")
        # Add in reverse order
        builder.add_rule(DensityRule(max_per_zone=1))
        builder.add_rule(ScopeRule(allowed_domains=["*"]))
        builder.add_rule(RateRule(max_per_second=1))
        builder.add_rule(BudgetRule(limit=1))

        bytecode = builder.compile()
        opcodes = [i.opcode for i in bytecode.instructions if i.opcode != "PUSH"
                   and i.opcode not in ("BIND_FENCE", "HALT")]
        assert opcodes == ["SET_BUDGET", "ENFORCE_RATE", "DEFINE_SCOPE", "LIMIT_DENSITY"]

    def test_dump_is_string(self):
        builder = FenceBuilder(name="dump-test")
        builder.add_rule(BudgetRule(limit=100))
        bytecode = builder.compile()
        listing = bytecode.dump()
        assert isinstance(listing, str)
        assert "dump-test" in listing
        assert "SET_BUDGET" in listing
        assert "BIND_FENCE" in listing

    def test_to_list(self):
        builder = FenceBuilder(name="list-test")
        builder.add_rule(BudgetRule(limit=100, window="daily"))
        bytecode = builder.compile()
        lst = bytecode.to_list()
        assert isinstance(lst, list)
        assert lst[0][0] == "PUSH"
        # Each element is [opcode, *operands]
        assert all(isinstance(row, list) for row in lst)


# ---------------------------------------------------------------------------
# Canvas tests
# ---------------------------------------------------------------------------

class TestCanvas:
    def test_default_canvas(self):
        canvas = Canvas()
        assert canvas.width == 1200.0
        assert canvas.height == 800.0
        assert len(canvas.zones) == 0

    def test_add_zone(self):
        canvas = Canvas()
        zone = Zone(name="test")
        canvas.add_zone(zone)
        assert len(canvas.zones) == 1
        assert canvas.to_dict()["zones"][0]["name"] == "test"

    def test_zone_defaults(self):
        zone = Zone(name="default")
        assert zone.bounds == (0.0, 0.0, 800.0, 600.0)
        assert zone.zone_id  # auto-generated


# ---------------------------------------------------------------------------
# Template tests
# ---------------------------------------------------------------------------

class TestTemplates:
    def test_template_registry_has_all(self):
        assert "api-guardrail" in TEMPLATES
        assert "cost-containment" in TEMPLATES
        assert "sandbox" in TEMPLATES
        assert "multi-tenant" in TEMPLATES

    def test_build_api_guardrail(self):
        template = TEMPLATES["api-guardrail"]
        fence = template.build()
        assert fence.name == "api-guardrail"
        assert len(fence.rules) == 3  # budget + rate + scope

    def test_build_with_overrides(self):
        fence = TEMPLATES["api-guardrail"].build(
            budget_limit=500_000,
            rate=100,
            burst=200,
        )
        budget = [r for r in fence.rules if r.rule_type == "budget"][0]
        assert budget.limit == 500_000
        rate = [r for r in fence.rules if r.rule_type == "rate"][0]
        assert rate.max_per_second == 100
        assert rate.burst == 200

    def test_build_sandbox(self):
        fence = TEMPLATES["sandbox"].build()
        scope = [r for r in fence.rules if r.rule_type == "scope"][0]
        assert "localhost" in scope.allowed_domains

    def test_build_multi_tenant(self):
        fence = TEMPLATES["multi-tenant"].build()
        density_rules = [r for r in fence.rules if r.rule_type == "density"]
        assert len(density_rules) == 2  # tenant-workers + shared-cache

    def test_build_cost_containment(self):
        fence = TEMPLATES["cost-containment"].build()
        budgets = [r for r in fence.rules if r.rule_type == "budget"]
        assert len(budgets) == 2  # dollars + tokens

    def test_template_build_compiles(self):
        """Every template should compile without errors."""
        for name, template in TEMPLATES.items():
            fence = template.build()
            bytecode = fence.compile()
            assert len(bytecode.instructions) > 2, f"{name} compiled to too few instructions"

    def test_template_is_reusable(self):
        """Building twice should give independent fences."""
        template = TEMPLATES["api-guardrail"]
        fence1 = template.build()
        fence2 = template.build()
        fence1.add_rule(DensityRule(max_per_zone=1))
        assert len(fence1.rules) != len(fence2.rules)
