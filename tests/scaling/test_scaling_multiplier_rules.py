import pytest

from classes.Fact import Fact
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from scaling.engine import ScalingEngine
from scaling.facts.ingredient_classifications import get_ingredient_classification_facts
from scaling.facts.ingredient_classification_scale_factors import get_ingredient_classification_scale_factor_facts
from scaling.rules.ingredient_classifications import get_ingredient_classification_rules
from scaling.rules.ingredient_classification_scaling_multipliers import get_ingredient_classification_scaling_multiplier_rules


def _make_engine(*, ingredient_name, scale_factor=2.0,
                 amount=1, unit='TEASPOONS', measurement_category='VOLUME'):
    wm = WorkingMemory()
    kb = KnowledgeBase()

    kb.add_reference_facts(facts=get_ingredient_classification_facts())
    kb.add_reference_facts(facts=get_ingredient_classification_scale_factor_facts())
    kb.add_rules(rules=get_ingredient_classification_rules())
    kb.add_rules(rules=get_ingredient_classification_scaling_multiplier_rules())

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


def _get_multiplier(*, engine):
    facts = [f for f in engine.working_memory.facts if f.fact_title == 'ingredient_scaling_multiplier']
    assert len(facts) == 1
    return facts[0].attributes['scaling_multiplier']


# ── Multiplier calculations ──────────────────────────────────────────

class TestScalingMultiplierCalculation:
    def test_leavening_agent_multiplier(self):
        """LEAVENING_AGENT scale_factor=0.7, target=2.0 -> 1.4"""
        engine, trigger = _make_engine(ingredient_name='BAKING_SODA')
        engine._forward_chain(trigger_fact=trigger)
        assert _get_multiplier(engine=engine) == pytest.approx(1.4)

    def test_extract_multiplier(self):
        """EXTRACT scale_factor=0.6, target=2.0 -> 1.2"""
        engine, trigger = _make_engine(ingredient_name='VANILLA_EXTRACT', measurement_category='LIQUID')
        engine._forward_chain(trigger_fact=trigger)
        assert _get_multiplier(engine=engine) == pytest.approx(1.2)

    def test_seasoning_multiplier(self):
        """SEASONING scale_factor=0.8, target=2.0 -> 1.6"""
        engine, trigger = _make_engine(ingredient_name='SALT')
        engine._forward_chain(trigger_fact=trigger)
        assert _get_multiplier(engine=engine) == pytest.approx(1.6)
