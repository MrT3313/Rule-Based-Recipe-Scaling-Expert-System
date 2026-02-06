import pytest

from classes.Fact import Fact
from classes.KnowledgeBase import KnowledgeBase
from classes.Recipe import Recipe
from classes.WorkingMemory import WorkingMemory
from planning.classes.CleaningStep import CleaningStep
from planning.classes.Step import Step
from planning.engine import PlanningEngine
from planning.rules.equipment_status import get_equipment_status_rules


def _make_engine(state):
    """Build a minimal PlanningEngine with one OVEN in the given state."""
    wm = WorkingMemory()
    wm.add_fact(
        fact=Fact(
            fact_title='EQUIPMENT',
            equipment_name='OVEN',
            equipment_id=1,
            state=state,
        ),
        silent=True,
    )

    kb = KnowledgeBase()
    kb.add_rules(rules=get_equipment_status_rules())

    recipe = Recipe(
        name='Test Recipe',
        ingredients=[],
        required_equipment=['OVEN'],
        steps=[
            Step(
                description='Bake the item',
                required_equipment=[{'equipment_name': 'OVEN'}],
            ),
        ],
    )

    engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
    return engine, wm, recipe


class TestEquipmentResolution:
    def test_oven_available(self):
        engine, wm, recipe = _make_engine('AVAILABLE')
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert plan == []
        # State unchanged
        assert wm.facts[0].attributes['state'] == 'AVAILABLE'

    def test_oven_in_use(self):
        engine, wm, recipe = _make_engine('IN_USE')
        success, error_message = engine.run(recipe=recipe)

        assert success is False
        assert 'OVEN' in error_message

    def test_oven_dirty(self):
        engine, wm, recipe = _make_engine('DIRTY')
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 1
        assert isinstance(plan[0], CleaningStep)
        assert plan[0].equipment_name == 'OVEN'
        # State mutated to AVAILABLE
        assert wm.facts[0].attributes['state'] == 'AVAILABLE'
