import pytest

from classes.Fact import Fact
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from scaling.engine import ScalingEngine
from scaling.facts.ingredient_classifications import get_ingredient_classification_facts
from scaling.facts.ingredient_classification_scale_factors import get_ingredient_classification_scale_factor_facts
from scaling.facts.measurement_unit_conversions import get_measurement_unit_conversion_facts
from scaling.rules.ingredient_classifications import get_ingredient_classification_rules
from scaling.rules.ingredient_classification_scaling_multipliers import get_ingredient_classification_scaling_multiplier_rules
from scaling.rules.scaled_ingredients import get_scaled_ingredient_rules
from scaling.rules.optimally_scaled_measurement_unit_conversions import get_optimal_unit_conversion_rules


def _make_engine(*, ingredient_name, amount, unit='CUPS',
                 measurement_category='VOLUME', scale_factor=2.0):
    wm = WorkingMemory()
    kb = KnowledgeBase()

    kb.add_reference_facts(facts=get_ingredient_classification_facts())
    kb.add_reference_facts(facts=get_ingredient_classification_scale_factor_facts())
    kb.add_reference_facts(facts=get_measurement_unit_conversion_facts())
    kb.add_rules(rules=get_ingredient_classification_rules())
    kb.add_rules(rules=get_ingredient_classification_scaling_multiplier_rules())
    kb.add_rules(rules=get_scaled_ingredient_rules())
    kb.add_rules(rules=get_optimal_unit_conversion_rules())

    wm.add_fact(fact=Fact(
        fact_title='target_recipe_scale_factor',
        target_recipe_scale_factor=scale_factor,
    ), silent=True)

    trigger = Fact(
        fact_title='recipe_ingredient',
        ingredient_name=ingredient_name,
        amount=amount,
        unit=unit,
        measurement_category=measurement_category,
    )
    wm.add_fact(fact=trigger, silent=True)

    engine = ScalingEngine(wm=wm, kb=kb, verbose=False)
    return engine, trigger


def _get_optimal(*, engine):
    facts = [f for f in engine.working_memory.facts if f.fact_title == 'optimally_scaled_ingredient']
    assert len(facts) == 1
    return facts[0]


# ── No conversion needed ─────────────────────────────────────────────

class TestOptimalUnitNoConversion:
    def test_teaspoons_no_conversion(self):
        """2.4 teaspoons stays as teaspoons (not cleanly convertible)."""
        engine, trigger = _make_engine(
            ingredient_name='VANILLA_EXTRACT', amount=2,
            unit='TEASPOONS', measurement_category='LIQUID',
        )
        engine._forward_chain(trigger_fact=trigger)
        optimal = _get_optimal(engine=engine)
        components = optimal.attributes['components']
        assert len(components) == 1
        assert components[0]['unit'] == 'TEASPOONS'


# ── Up-conversion ────────────────────────────────────────────────────

class TestOptimalUnitUpConversion:
    def test_cups_to_pints(self):
        """2 cups -> scaled 4 cups -> should convert to higher unit."""
        engine, trigger = _make_engine(ingredient_name='CHOCOLATE_CHIPS', amount=2)
        engine._forward_chain(trigger_fact=trigger)
        optimal = _get_optimal(engine=engine)
        components = optimal.attributes['components']
        # 4 cups = 1 quart
        total_tsp = sum(
            c['amount'] * (48 if c['unit'] == 'CUPS' else
                          192 if c['unit'] == 'QUARTS' else
                          96 if c['unit'] == 'PINTS' else 1)
            for c in components
        )
        assert total_tsp == pytest.approx(192)  # 4 cups = 192 tsp

    def test_butter_cups_to_pints(self):
        """1 cup * 2.0 = 2 cups -> 1 pint."""
        engine, trigger = _make_engine(ingredient_name='BUTTER', amount=1)
        engine._forward_chain(trigger_fact=trigger)
        optimal = _get_optimal(engine=engine)
        components = optimal.attributes['components']
        assert len(components) == 1
        assert components[0]['unit'] == 'PINTS'
        assert components[0]['amount'] == pytest.approx(1.0)


# ── Multi-component ──────────────────────────────────────────────────

class TestOptimalUnitMultiComponent:
    def test_flour_multi_component(self):
        """2.25 cups * 2.0 = 4.5 cups -> might decompose to multi-component."""
        engine, trigger = _make_engine(
            ingredient_name='ALL_PURPOSE_FLOUR', amount=2.25
        )
        engine._forward_chain(trigger_fact=trigger)
        optimal = _get_optimal(engine=engine)
        components = optimal.attributes['components']
        # 4.5 cups = 216 tsp, verify total volume is preserved
        conversion = {'TEASPOONS': 1, 'TABLESPOONS': 3, 'CUPS': 48, 'PINTS': 96, 'QUARTS': 192}
        total_tsp = sum(c['amount'] * conversion.get(c['unit'], 1) for c in components)
        assert total_tsp == pytest.approx(216)


# ── PINCH pass-through ───────────────────────────────────────────────

class TestOptimalUnitPinchDash:
    def test_pinch_passes_through(self):
        """PINCH measurements should pass through unchanged."""
        engine, trigger = _make_engine(
            ingredient_name='NUTMEG', amount=1,
            unit='PINCH', measurement_category='VOLUME',
            scale_factor=2.0,
        )
        engine._forward_chain(trigger_fact=trigger)
        optimal = _get_optimal(engine=engine)
        components = optimal.attributes['components']
        assert len(components) == 1
        assert components[0]['unit'] == 'PINCH'


# ── Weight measurements ──────────────────────────────────────────────

class TestOptimalUnitWeightMeasurements:
    def test_ounces(self):
        engine, trigger = _make_engine(
            ingredient_name='CREAM_CHEESE', amount=8,
            unit='OUNCES', measurement_category='WEIGHT',
        )
        engine._forward_chain(trigger_fact=trigger)
        optimal = _get_optimal(engine=engine)
        components = optimal.attributes['components']
        # 8 oz * 2.0 = 16 oz = 1 lb
        assert len(components) == 1
        assert components[0]['unit'] == 'POUNDS'
        assert components[0]['amount'] == pytest.approx(1.0)


# ── Whole measurements ───────────────────────────────────────────────

class TestOptimalUnitWholeMeasurements:
    def test_whole_eggs(self):
        engine, trigger = _make_engine(
            ingredient_name='EGGS', amount=2,
            unit='WHOLE', measurement_category='WHOLE',
        )
        engine._forward_chain(trigger_fact=trigger)
        optimal = _get_optimal(engine=engine)
        components = optimal.attributes['components']
        # 2 * 2.0 = 4 whole
        assert len(components) == 1
        assert components[0]['unit'] == 'WHOLE'
        assert components[0]['amount'] == pytest.approx(4.0)
