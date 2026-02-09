import pytest

from classes.Fact import Fact
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from scaling.engine import ScalingEngine
from scaling.facts.ingredient_classifications import get_ingredient_classification_facts
from scaling.facts.ingredient_classification_scale_factors import get_ingredient_classification_scale_factor_facts
from scaling.rules.ingredient_classifications import get_ingredient_classification_rules
from scaling.rules.ingredient_classification_scaling_multipliers import get_ingredient_classification_scaling_multiplier_rules
from scaling.rules.scaled_ingredients import get_scaled_ingredient_rules


def _make_engine(*, ingredient_name, amount, unit='CUPS',
                 measurement_category='VOLUME', scale_factor=2.0):
    wm = WorkingMemory()
    kb = KnowledgeBase()

    kb.add_reference_facts(facts=get_ingredient_classification_facts())
    kb.add_reference_facts(facts=get_ingredient_classification_scale_factor_facts())
    kb.add_rules(rules=get_ingredient_classification_rules())
    kb.add_rules(rules=get_ingredient_classification_scaling_multiplier_rules())
    kb.add_rules(rules=get_scaled_ingredient_rules())

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


def _get_scaled(*, engine):
    facts = [f for f in engine.working_memory.facts if f.fact_title == 'scaled_ingredient']
    assert len(facts) == 1
    return facts[0]


# ── Scaling amount ───────────────────────────────────────────────────

class TestScaleIngredientAmount:
    def test_known_ingredient_scaled(self):
        """SALT 1 tsp, scale=2.0, SEASONING*0.8 -> multiplier=1.6, scaled=1.6"""
        engine, trigger = _make_engine(ingredient_name='SALT', amount=1, unit='TEASPOONS')
        engine._forward_chain(trigger_fact=trigger)
        scaled = _get_scaled(engine=engine)
        assert scaled.attributes['scaled_amount'] == pytest.approx(1.6)


# ── Fractional amounts ───────────────────────────────────────────────

class TestScaleIngredientFractionalAmounts:
    def test_quarter_teaspoon(self):
        """0.25 tsp BAKING_SODA * 1.4 = 0.35"""
        engine, trigger = _make_engine(
            ingredient_name='BAKING_SODA', amount=0.25, unit='TEASPOONS'
        )
        engine._forward_chain(trigger_fact=trigger)
        scaled = _get_scaled(engine=engine)
        assert scaled.attributes['scaled_amount'] == pytest.approx(0.35)
