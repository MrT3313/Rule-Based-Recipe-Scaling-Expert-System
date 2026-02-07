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


def _make_engine(*, ingredients, scale_factor=2.0):
    """Build a fully-wired ScalingEngine with all rules and reference facts.
    `ingredients` is a list of dicts with keys: name, amount, unit, measurement_category."""
    wm = WorkingMemory()
    kb = KnowledgeBase()

    kb.add_reference_fact(fact=get_ingredient_classification_facts())
    kb.add_reference_fact(fact=get_ingredient_classification_scale_factor_facts())
    kb.add_reference_fact(fact=get_measurement_unit_conversion_facts())
    kb.add_rules(rules=get_ingredient_classification_rules())
    kb.add_rules(rules=get_ingredient_classification_scaling_multiplier_rules())
    kb.add_rules(rules=get_scaled_ingredient_rules())
    kb.add_rules(rules=get_optimal_unit_conversion_rules())

    wm.add_fact(fact=Fact(
        fact_title='target_recipe_scale_factor',
        target_recipe_scale_factor=scale_factor,
    ), silent=True)

    for ing in ingredients:
        wm.add_fact(fact=Fact(
            fact_title='recipe_ingredient',
            ingredient_name=ing['name'],
            amount=ing['amount'],
            unit=ing['unit'],
            measurement_category=ing['measurement_category'],
        ), silent=True)

    return ScalingEngine(wm=wm, kb=kb, verbose=False)


def _count_facts(engine, title):
    return len([f for f in engine.working_memory.facts if f.fact_title == title])


def _get_fact(engine, title, ingredient_name):
    matches = [
        f for f in engine.working_memory.facts
        if f.fact_title == title and f.attributes.get('ingredient_name') == ingredient_name
    ]
    assert len(matches) == 1, f"Expected 1 {title} for {ingredient_name}, got {len(matches)}"
    return matches[0]


# ── Single ingredient pipeline ───────────────────────────────────────

class TestFullPipelineSingleIngredient:
    def test_all_four_derived_facts(self):
        """A single ingredient produces exactly 4 derived facts."""
        engine = _make_engine(ingredients=[
            {'name': 'SALT', 'amount': 1, 'unit': 'TEASPOONS', 'measurement_category': 'VOLUME'},
        ])
        engine.run()
        assert _count_facts(engine, 'classified_ingredient') == 1
        assert _count_facts(engine, 'ingredient_scaling_multiplier') == 1
        assert _count_facts(engine, 'scaled_ingredient') == 1
        assert _count_facts(engine, 'optimally_scaled_ingredient') == 1

    def test_classified_values(self):
        engine = _make_engine(ingredients=[
            {'name': 'SALT', 'amount': 1, 'unit': 'TEASPOONS', 'measurement_category': 'VOLUME'},
        ])
        engine.run()
        fact = _get_fact(engine, 'classified_ingredient', 'SALT')
        assert fact.attributes['classification'] == 'SEASONING'

    def test_multiplier_values(self):
        engine = _make_engine(ingredients=[
            {'name': 'SALT', 'amount': 1, 'unit': 'TEASPOONS', 'measurement_category': 'VOLUME'},
        ])
        engine.run()
        fact = _get_fact(engine, 'ingredient_scaling_multiplier', 'SALT')
        assert fact.attributes['scaling_multiplier'] == pytest.approx(1.6)

    def test_scaled_values(self):
        engine = _make_engine(ingredients=[
            {'name': 'SALT', 'amount': 1, 'unit': 'TEASPOONS', 'measurement_category': 'VOLUME'},
        ])
        engine.run()
        fact = _get_fact(engine, 'scaled_ingredient', 'SALT')
        assert fact.attributes['scaled_amount'] == pytest.approx(1.6)
        assert fact.attributes['original_amount'] == 1

    def test_optimal_values(self):
        engine = _make_engine(ingredients=[
            {'name': 'SALT', 'amount': 1, 'unit': 'TEASPOONS', 'measurement_category': 'VOLUME'},
        ])
        engine.run()
        fact = _get_fact(engine, 'optimally_scaled_ingredient', 'SALT')
        assert fact.attributes['components'] is not None
        assert len(fact.attributes['components']) >= 1


# ── Multiple ingredients ─────────────────────────────────────────────

FULL_RECIPE = [
    {'name': 'ALL_PURPOSE_FLOUR', 'amount': 2.25, 'unit': 'CUPS', 'measurement_category': 'VOLUME'},
    {'name': 'BUTTER',            'amount': 1,    'unit': 'CUPS', 'measurement_category': 'VOLUME'},
    {'name': 'WHITE_SUGAR',       'amount': 0.75, 'unit': 'CUPS', 'measurement_category': 'VOLUME'},
    {'name': 'BROWN_SUGAR',       'amount': 0.75, 'unit': 'CUPS', 'measurement_category': 'VOLUME'},
    {'name': 'EGGS',              'amount': 2,    'unit': 'WHOLE', 'measurement_category': 'WHOLE'},
    {'name': 'VANILLA_EXTRACT',   'amount': 2,    'unit': 'TEASPOONS', 'measurement_category': 'LIQUID'},
    {'name': 'BAKING_SODA',       'amount': 1,    'unit': 'TEASPOONS', 'measurement_category': 'VOLUME'},
    {'name': 'SALT',              'amount': 1,    'unit': 'TEASPOONS', 'measurement_category': 'VOLUME'},
    {'name': 'CHOCOLATE_CHIPS',   'amount': 2,    'unit': 'CUPS', 'measurement_category': 'VOLUME'},
]


class TestFullPipelineMultipleIngredients:
    def test_nine_classified(self):
        engine = _make_engine(ingredients=FULL_RECIPE)
        engine.run()
        assert _count_facts(engine, 'classified_ingredient') == 9

    def test_nine_multipliers(self):
        engine = _make_engine(ingredients=FULL_RECIPE)
        engine.run()
        assert _count_facts(engine, 'ingredient_scaling_multiplier') == 9

    def test_nine_scaled(self):
        engine = _make_engine(ingredients=FULL_RECIPE)
        engine.run()
        assert _count_facts(engine, 'scaled_ingredient') == 9

    def test_nine_optimal(self):
        engine = _make_engine(ingredients=FULL_RECIPE)
        engine.run()
        assert _count_facts(engine, 'optimally_scaled_ingredient') == 9

    def test_total_facts(self):
        """1 scale_factor + 9 ingredients + 9*4 derived = 46 total."""
        engine = _make_engine(ingredients=FULL_RECIPE)
        engine.run()
        assert len(engine.working_memory.facts) == 46


# ── Known vs default multipliers ─────────────────────────────────────

class TestFullPipelineKnownVsDefault:
    def test_known_ingredients_non_unit_multiplier(self):
        """Known ingredients (SALT, BAKING_SODA, VANILLA_EXTRACT) get non-1.0 scale factor."""
        engine = _make_engine(ingredients=FULL_RECIPE)
        engine.run()

        salt_mult = _get_fact(engine, 'ingredient_scaling_multiplier', 'SALT')
        assert salt_mult.attributes['scaling_multiplier'] != pytest.approx(2.0)

        soda_mult = _get_fact(engine, 'ingredient_scaling_multiplier', 'BAKING_SODA')
        assert soda_mult.attributes['scaling_multiplier'] != pytest.approx(2.0)

        vanilla_mult = _get_fact(engine, 'ingredient_scaling_multiplier', 'VANILLA_EXTRACT')
        assert vanilla_mult.attributes['scaling_multiplier'] != pytest.approx(2.0)

    def test_default_ingredients_unit_multiplier(self):
        """Default ingredients get multiplier = target_scale * 1.0."""
        engine = _make_engine(ingredients=FULL_RECIPE)
        engine.run()

        for name in ['ALL_PURPOSE_FLOUR', 'BUTTER', 'WHITE_SUGAR', 'BROWN_SUGAR', 'EGGS', 'CHOCOLATE_CHIPS']:
            mult = _get_fact(engine, 'ingredient_scaling_multiplier', name)
            assert mult.attributes['scaling_multiplier'] == pytest.approx(2.0), f"{name} should have 2.0"


# ── Scale factor 1.0 (identity) ─────────────────────────────────────

class TestFullPipelineScaleFactorOne:
    def test_identity_scaling(self):
        """scale_factor=1.0 -> all DEFAULT ingredients have multiplier=1.0, scaled_amount=original."""
        engine = _make_engine(ingredients=[
            {'name': 'BUTTER', 'amount': 1, 'unit': 'CUPS', 'measurement_category': 'VOLUME'},
        ], scale_factor=1.0)
        engine.run()
        scaled = _get_fact(engine, 'scaled_ingredient', 'BUTTER')
        assert scaled.attributes['scaled_amount'] == pytest.approx(1.0)
        assert scaled.attributes['original_amount'] == 1


# ── Scale factor 0.5 (halving) ──────────────────────────────────────

class TestFullPipelineScaleFactorHalf:
    def test_half_scaling(self):
        engine = _make_engine(ingredients=[
            {'name': 'BUTTER', 'amount': 2, 'unit': 'CUPS', 'measurement_category': 'VOLUME'},
        ], scale_factor=0.5)
        engine.run()
        scaled = _get_fact(engine, 'scaled_ingredient', 'BUTTER')
        assert scaled.attributes['scaled_amount'] == pytest.approx(1.0)

    def test_half_scaling_known_ingredient(self):
        """SALT: SEASONING*0.8 * 0.5 = 0.4 multiplier, 1 tsp * 0.4 = 0.4 tsp."""
        engine = _make_engine(ingredients=[
            {'name': 'SALT', 'amount': 1, 'unit': 'TEASPOONS', 'measurement_category': 'VOLUME'},
        ], scale_factor=0.5)
        engine.run()
        scaled = _get_fact(engine, 'scaled_ingredient', 'SALT')
        assert scaled.attributes['scaled_amount'] == pytest.approx(0.4)


# ── Trigger chaining verification ────────────────────────────────────

class TestFullPipelineTriggerChaining:
    def test_single_forward_chain_propagates_full_pipeline(self):
        """A single _forward_chain call on a recipe_ingredient should derive all 4 facts."""
        engine = _make_engine(ingredients=[
            {'name': 'BUTTER', 'amount': 1, 'unit': 'CUPS', 'measurement_category': 'VOLUME'},
        ])
        triggers = [f for f in engine.working_memory.facts if f.fact_title == 'recipe_ingredient']
        assert len(triggers) == 1

        rule_fired, last_derived = engine._forward_chain(triggers[0])
        assert rule_fired is True
        assert _count_facts(engine, 'classified_ingredient') == 1
        assert _count_facts(engine, 'ingredient_scaling_multiplier') == 1
        assert _count_facts(engine, 'scaled_ingredient') == 1
        assert _count_facts(engine, 'optimally_scaled_ingredient') == 1

    def test_run_matches_manual_forward_chain(self):
        """engine.run() should produce the same results as manual per-ingredient forward_chain."""
        engine_run = _make_engine(ingredients=FULL_RECIPE)
        engine_run.run()

        engine_manual = _make_engine(ingredients=FULL_RECIPE)
        triggers = [f for f in engine_manual.working_memory.facts if f.fact_title == 'recipe_ingredient']
        for t in triggers:
            engine_manual._forward_chain(t)

        # Both should have same number of facts
        assert len(engine_run.working_memory.facts) == len(engine_manual.working_memory.facts)

        # Both should have same derived fact counts
        for title in ['classified_ingredient', 'ingredient_scaling_multiplier',
                      'scaled_ingredient', 'optimally_scaled_ingredient']:
            assert _count_facts(engine_run, title) == _count_facts(engine_manual, title)
