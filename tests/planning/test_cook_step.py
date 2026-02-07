import pytest

from classes.Fact import Fact
from classes.Ingredient import Ingredient
from classes.KnowledgeBase import KnowledgeBase
from classes.Recipe import Recipe
from classes.WorkingMemory import WorkingMemory
from planning.classes.MixingStep import MixingStep
from planning.classes.MixingSubstep import MixingSubstep
from planning.classes.TransferItem import TransferItem
from planning.classes.TransferEquipment import TransferEquipment
from planning.classes.CookStep import CookStep
from planning.classes.WaitStep import WaitStep
from planning.engine import PlanningEngine
from planning.rules.equipment_status import get_equipment_status_rules
from planning.rules.ingredient_rules import get_ingredient_rules
from planning.rules.transfer_rules import get_transfer_rules
from planning.rules.equipment_transfer_rules import get_equipment_transfer_rules
from planning.rules.cooking_rules import get_cooking_rules
from planning.rules.step_dispatch_rules import get_step_dispatch_rules
from scaling.facts.measurement_unit_conversions import get_measurement_unit_conversion_facts
from planning.facts.transfer_reference_facts import get_transfer_reference_facts


def _make_engine(*, ingredients, substeps, bowl_volume=4, bowl_volume_unit='QUARTS',
                 num_baking_sheets=2, num_ovens=0, oven_racks=2,
                 include_cook_step=False, cook_time=10, cook_time_unit='minutes'):
    """Build a PlanningEngine with a MixingStep, TransferStep, and optionally a CookStep."""
    wm = WorkingMemory()
    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT',
        equipment_type='CONTAINER',
        equipment_name='BOWL',
        equipment_id=1,
        state='AVAILABLE',
        volume=bowl_volume,
        volume_unit=bowl_volume_unit,
    ), silent=True)

    for i in range(num_baking_sheets):
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='TRAY',
            equipment_name='BAKING_SHEET',
            equipment_id=i + 1,
            state='AVAILABLE',
        ), silent=True)

    for i in range(num_ovens):
        state = 'IN_USE' if i == 0 else 'AVAILABLE'
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='APPLIANCE',
            equipment_name='OVEN',
            equipment_id=i + 1,
            state=state,
            number_of_racks=oven_racks,
        ), silent=True)

    kb = KnowledgeBase()
    kb.add_rules(rules=get_equipment_status_rules())
    kb.add_rules(rules=get_ingredient_rules())
    kb.add_rules(rules=get_transfer_rules())
    kb.add_rules(rules=get_equipment_transfer_rules())
    kb.add_rules(rules=get_cooking_rules())
    kb.add_rules(rules=get_step_dispatch_rules())
    kb.add_reference_fact(fact=get_measurement_unit_conversion_facts())
    kb.add_reference_fact(fact=get_transfer_reference_facts())

    steps = [
        MixingStep(
            description='Mix ingredients',
            required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
            substeps=substeps,
        ),
        TransferItem(
            description='Scoop dough onto baking sheets',
            source_equipment_name='BOWL',
            target_equipment_name='BAKING_SHEET',
            scoop_size_amount=2,
            scoop_size_unit='TABLESPOONS',
            required_equipment=[],
        ),
    ]

    if include_cook_step:
        steps.append(
            CookStep(
                description='Bake the cookies',
                substeps=[
                    TransferEquipment(
                        description='Transfer baking sheets to oven racks',
                        source_equipment_name='BAKING_SHEET',
                        target_equipment_name='OVEN',
                        required_equipment=[],
                    ),
                    WaitStep(
                        description='Wait for cookies to bake',
                        equipment_name='OVEN',
                        duration=cook_time,
                        duration_unit=cook_time_unit,
                    ),
                ],
                required_equipment=[],
            ),
        )

    recipe = Recipe(
        name='Test Recipe',
        ingredients=ingredients,
        required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
        steps=steps,
    )

    engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
    return engine, wm, recipe


def _cookie_ingredients_and_substeps():
    """Full cookie recipe: produces 38 dough balls → 5 sheets needed."""
    ingredients = [
        Ingredient(id=1, name='all-purpose flour', amount=2.25, unit='cups', measurement_category='VOLUME'),
        Ingredient(id=2, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        Ingredient(id=3, name='white sugar', amount=0.75, unit='cups', measurement_category='VOLUME'),
        Ingredient(id=4, name='brown sugar', amount=0.75, unit='cups', measurement_category='VOLUME'),
        Ingredient(id=5, name='eggs', amount=2, unit='whole', measurement_category='WHOLE'),
        Ingredient(id=6, name='vanilla extract', amount=2, unit='teaspoons', measurement_category='LIQUID'),
        Ingredient(id=7, name='baking soda', amount=1, unit='teaspoons', measurement_category='VOLUME'),
        Ingredient(id=8, name='salt', amount=1, unit='teaspoons', measurement_category='VOLUME'),
    ]
    substeps = [
        MixingSubstep(ingredient_ids=[2, 3, 4], description='Cream butter and sugars'),
        MixingSubstep(ingredient_ids=[5, 6], description='Beat in eggs and vanilla'),
        MixingSubstep(ingredient_ids=[1, 7, 8], description='Mix in flour, baking soda, salt'),
    ]
    return ingredients, substeps


class TestCookStepPlanLength:
    def test_cook_step_plan_length_five_sheets_three_ovens(self):
        """5 sheets, 3 ovens (2 racks each).
        Plan: 1 MixingStep + 5 TransferSteps + 3 CookSteps = 9
        Oven 1 substeps: preheat + 2 transfers + wait = 4
        Oven 2 substeps: preheat + 2 transfers + wait = 4
        Oven 3 substeps: preheat + 1 transfer + wait = 3"""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 9

        cook_steps = [s for s in plan if isinstance(s, CookStep)]
        assert len(cook_steps) == 3

        # Oven 1: preheat + 2 transfers + wait = 4
        assert len(cook_steps[0].substeps) == 4
        # Oven 2: preheat + 2 transfers + wait = 4
        assert len(cook_steps[1].substeps) == 4
        # Oven 3: preheat + 1 transfer + wait = 3
        assert len(cook_steps[2].substeps) == 3

        # Total across all CookSteps
        all_substeps = [s for cs in cook_steps for s in cs.substeps]
        cooking_waits = [s for s in all_substeps if isinstance(s, WaitStep) and s.duration is not None]
        assert len(cooking_waits) == 3

        equip_transfer_steps = [s for s in all_substeps if isinstance(s, TransferEquipment)]
        assert len(equip_transfer_steps) == 5

        preheat_steps = [s for s in all_substeps if isinstance(s, WaitStep) and 'preheat' in s.description]
        assert len(preheat_steps) == 3

    def test_cook_step_plan_length_two_sheets_one_oven(self):
        """2 sheets, 1 oven (2 racks).
        Plan: 1 MixingStep + 2 TransferSteps + 1 CookStep = 4
        CookStep.substeps: 1 preheat + 2 EquipmentTransferSteps + 1 WaitStep = 4"""
        ingredients = [
            Ingredient(id=1, name='butter', amount=2, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1], description='Mix butter'),
        ]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=2, num_ovens=1, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 4

        assert isinstance(plan[-1], CookStep)
        cook_step = plan[-1]
        assert len(cook_step.substeps) == 4

        cooking_waits = [s for s in cook_step.substeps if isinstance(s, WaitStep) and s.duration is not None]
        assert len(cooking_waits) == 1

        equip_transfer_steps = [s for s in cook_step.substeps if isinstance(s, TransferEquipment)]
        assert len(equip_transfer_steps) == 2


class TestWaitStepAttributes:
    def test_wait_step_has_correct_duration(self):
        """WaitStep instances across all CookSteps have correct duration and duration_unit."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=12, cook_time_unit='minutes',
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        cook_steps = [s for s in plan if isinstance(s, CookStep)]
        assert len(cook_steps) == 3

        cooking_waits = [s for cs in cook_steps for s in cs.substeps if isinstance(s, WaitStep) and s.duration is not None]
        assert len(cooking_waits) == 3

        for ws in cooking_waits:
            assert ws.duration == 12
            assert ws.duration_unit == 'minutes'
            assert ws.is_passive is True

    def test_wait_step_fires_when_no_remaining_sheets(self):
        """1 sheet, 1 oven (2 racks) → oven not full but no more sheets → WaitStep fires.
        Plan: 1 MixingStep + 1 TransferStep + 1 CookStep = 3
        CookStep.substeps: 1 preheat + 1 EquipmentTransferStep + 1 WaitStep = 3"""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1], description='Mix butter'),
        ]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=1, num_ovens=1, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 3

        assert isinstance(plan[-1], CookStep)
        cook_step = plan[-1]
        assert len(cook_step.substeps) == 3

        cooking_waits = [s for s in cook_step.substeps if isinstance(s, WaitStep) and s.duration is not None]
        assert len(cooking_waits) == 1


class TestCookingStartedFact:
    def test_cooking_started_fact_asserted(self):
        """cooking_started facts are asserted in WM with correct equipment_id, duration, duration_unit."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        cooking_started_facts = wm.query_facts(fact_title='cooking_started')
        assert len(cooking_started_facts) == 3

        oven_ids = {f.attributes['equipment_id'] for f in cooking_started_facts}
        assert oven_ids == {1, 2, 3}

        for fact in cooking_started_facts:
            assert fact.attributes['duration'] == 10
            assert fact.attributes['duration_unit'] == 'minutes'


class TestCookStepFailure:
    def test_not_enough_ovens_fails(self):
        """5 sheets but only 2 ovens (4 rack slots) → should fail."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=2, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
        )
        success, result = engine.run(recipe=recipe)

        assert success is False
