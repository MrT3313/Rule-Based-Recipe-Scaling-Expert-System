import pytest

from classes.Fact import Fact
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from scaling.engine import ScalingEngine
from scaling.facts.ingredient_classifications import get_ingredient_classification_facts
from scaling.facts.ingredient_classification_scale_factors import get_ingredient_classification_scale_factor_facts
from scaling.rules.ingredient_classifications import get_ingredient_classification_rules


def _make_engine(*, ingredient_name, amount=1, unit='TEASPOONS', measurement_category='VOLUME'):
    wm = WorkingMemory()
    kb = KnowledgeBase()

    kb.add_reference_facts(facts=get_ingredient_classification_facts())
    kb.add_reference_facts(facts=get_ingredient_classification_scale_factor_facts())
    kb.add_rules(rules=get_ingredient_classification_rules())

    wm.add_fact(fact=Fact(
        fact_title='target_recipe_scale_factor',
        target_recipe_scale_factor=2.0,
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


# ── Known ingredient classification ──────────────────────────────────

class TestClassifyKnownIngredient:
    def test_baking_soda_is_leavening_agent(self):
        engine, trigger = _make_engine(ingredient_name='BAKING_SODA')
        engine._forward_chain(trigger_fact=trigger)
        classified = [f for f in engine.working_memory.facts if f.fact_title == 'classified_ingredient']
        assert len(classified) == 1
        assert classified[0].attributes['classification'] == 'LEAVENING_AGENT'

    def test_salt_is_seasoning(self):
        engine, trigger = _make_engine(ingredient_name='SALT')
        engine._forward_chain(trigger_fact=trigger)
        classified = [f for f in engine.working_memory.facts if f.fact_title == 'classified_ingredient']
        assert len(classified) == 1
        assert classified[0].attributes['classification'] == 'SEASONING'

    def test_vanilla_extract_is_extract(self):
        engine, trigger = _make_engine(ingredient_name='VANILLA_EXTRACT', measurement_category='LIQUID')
        engine._forward_chain(trigger_fact=trigger)
        classified = [f for f in engine.working_memory.facts if f.fact_title == 'classified_ingredient']
        assert len(classified) == 1
        assert classified[0].attributes['classification'] == 'EXTRACT'


# ── Idempotency ──────────────────────────────────────────────────────

class TestClassificationIdempotency:
    def test_no_duplicate_classification(self):
        engine, trigger = _make_engine(ingredient_name='SALT')
        engine._forward_chain(trigger_fact=trigger)
        engine._forward_chain(trigger_fact=trigger)
        classified = [f for f in engine.working_memory.facts if f.fact_title == 'classified_ingredient']
        assert len(classified) == 1

    def test_negated_fact_prevents_reclassification(self):
        """Even with WM changes, the NegatedFact guard blocks a second classified_ingredient."""
        engine, trigger = _make_engine(ingredient_name='BUTTER', unit='CUPS')
        engine._forward_chain(trigger_fact=trigger)
        # Add a spurious fact to change WM
        engine.working_memory.add_fact(
            fact=Fact(fact_title='dummy', val=1), silent=True
        )
        engine._forward_chain(trigger_fact=trigger)
        classified = [f for f in engine.working_memory.facts if f.fact_title == 'classified_ingredient']
        assert len(classified) == 1
