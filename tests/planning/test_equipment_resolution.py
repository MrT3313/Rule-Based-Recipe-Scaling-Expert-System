import pytest

from classes.Fact import Fact
from classes.KnowledgeBase import KnowledgeBase
from classes.Recipe import Recipe
from classes.WorkingMemory import WorkingMemory
from planning.classes.CleaningStep import CleaningStep
from planning.classes.Step import Step
from planning.engine import PlanningEngine
from planning.rules.equipment_status import get_equipment_status_rules
from planning.rules.step_dispatch_rules import get_step_dispatch_rules


def _make_oven_engine(state):
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
    kb.add_rules(rules=get_step_dispatch_rules())

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
        engine, wm, recipe = _make_oven_engine('AVAILABLE')
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 1
        # State changed to IN_USE
        assert wm.facts[0].attributes['state'] == 'IN_USE'

    def test_oven_in_use(self):
        engine, wm, recipe = _make_oven_engine('IN_USE')
        success, error_message = engine.run(recipe=recipe)

        assert success is False
        assert 'OVEN' in error_message

    def test_oven_dirty(self):
        engine, wm, recipe = _make_oven_engine('DIRTY')
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 2
        assert isinstance(plan[0], CleaningStep)
        assert plan[0].equipment_name == 'OVEN'
        # State mutated to IN_USE (cleaned, reserved, then in-use)
        assert wm.facts[0].attributes['state'] == 'IN_USE'


def _make_bowl_engine(states):
    """Build a PlanningEngine with N BOWLs in the given states, needing len(states) BOWLs."""
    wm = WorkingMemory()
    for i, state in enumerate(states):
        wm.add_fact(
            fact=Fact(
                fact_title='EQUIPMENT',
                equipment_name='BOWL',
                equipment_id=i + 1,
                state=state,
            ),
            silent=True,
        )

    kb = KnowledgeBase()
    kb.add_rules(rules=get_equipment_status_rules())
    kb.add_rules(rules=get_step_dispatch_rules())

    recipe = Recipe(
        name='Test Recipe',
        ingredients=[],
        required_equipment=['BOWL'],
        steps=[
            Step(
                description='Mix ingredients',
                required_equipment=[{'equipment_name': 'BOWL', 'required_count': len(states)}],
            ),
        ],
    )

    engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
    return engine, wm, recipe


class TestMultiEquipmentResolution:
    def test_two_bowls_both_available(self):
        engine, wm, recipe = _make_bowl_engine(['AVAILABLE', 'AVAILABLE'])
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 1
        assert wm.facts[0].attributes['state'] == 'IN_USE'
        assert wm.facts[1].attributes['state'] == 'IN_USE'

    def test_two_bowls_one_dirty_one_available(self):
        engine, wm, recipe = _make_bowl_engine(['DIRTY', 'AVAILABLE'])
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 2
        assert isinstance(plan[0], CleaningStep)
        assert wm.facts[0].attributes['state'] == 'IN_USE'
        assert wm.facts[1].attributes['state'] == 'IN_USE'

    def test_two_bowls_both_dirty(self):
        engine, wm, recipe = _make_bowl_engine(['DIRTY', 'DIRTY'])
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 3
        assert all(isinstance(s, CleaningStep) for s in plan[:2])
        assert wm.facts[0].attributes['state'] == 'IN_USE'
        assert wm.facts[1].attributes['state'] == 'IN_USE'

    def test_two_bowls_one_in_use(self):
        engine, wm, recipe = _make_bowl_engine(['AVAILABLE', 'IN_USE'])
        success, error_message = engine.run(recipe=recipe)

        assert success is False
        assert 'BOWL' in error_message
