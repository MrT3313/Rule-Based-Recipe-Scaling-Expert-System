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
from planning.classes.Step import Step
from planning.engine import PlanningEngine
from planning.rules.equipment_status import get_equipment_status_rules
from planning.rules.ingredient_rules import get_ingredient_rules
from planning.rules.transfer_rules import get_transfer_rules
from planning.rules.equipment_transfer_rules import get_equipment_transfer_rules
from planning.rules.cooking_rules import get_cooking_rules
from planning.rules.removal_rules import get_removal_rules
from planning.rules.step_dispatch_rules import get_step_dispatch_rules
from planning.rules.mixing_dispatch_rules import get_mixing_dispatch_rules
from planning.rules.transfer_dispatch_rules import get_transfer_dispatch_rules
from planning.rules.removal_dispatch_rules import get_removal_dispatch_rules
from planning.rules.surface_transfer_dispatch_rules import get_surface_transfer_dispatch_rules
from planning.rules.equipment_transfer_dispatch_rules import get_equipment_transfer_dispatch_rules
from planning.rules.cook_dispatch_rules import get_cook_dispatch_rules
from scaling.facts.measurement_unit_conversions import get_measurement_unit_conversion_facts
from planning.facts.transfer_reference_facts import get_transfer_reference_facts


def _make_full_pipeline_engine(*, ingredients, substeps,
                                bowl_volume=4, bowl_volume_unit='QUARTS',
                                num_baking_sheets=2, num_ovens=1, oven_racks=2,
                                cook_time=10, cook_time_unit='minutes'):
    """Build a complete Mix->Transfer->Cook->Removal->ItemTransfer pipeline
    with all 8 dispatch + 5 lower-level rule modules."""
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

    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT',
        equipment_type='SURFACE',
        equipment_name='COUNTERTOP',
        equipment_id=1,
        state='AVAILABLE',
    ), silent=True)

    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT',
        equipment_type='SURFACE',
        equipment_name='COOLING_RACK',
        equipment_id=1,
        state='AVAILABLE',
    ), silent=True)

    kb = KnowledgeBase()
    kb.add_rules(rules=get_equipment_status_rules())
    kb.add_rules(rules=get_ingredient_rules())
    kb.add_rules(rules=get_transfer_rules())
    kb.add_rules(rules=get_equipment_transfer_rules())
    kb.add_rules(rules=get_cooking_rules())
    kb.add_rules(rules=get_removal_rules())
    kb.add_rules(rules=get_step_dispatch_rules())
    kb.add_rules(rules=get_mixing_dispatch_rules())
    kb.add_rules(rules=get_transfer_dispatch_rules())
    kb.add_rules(rules=get_removal_dispatch_rules())
    kb.add_rules(rules=get_surface_transfer_dispatch_rules())
    kb.add_rules(rules=get_equipment_transfer_dispatch_rules())
    kb.add_rules(rules=get_cook_dispatch_rules())
    kb.add_reference_facts(facts=get_measurement_unit_conversion_facts())
    kb.add_reference_facts(facts=get_transfer_reference_facts())

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
        TransferEquipment(
            description='Remove baking sheets from oven to countertop',
            source_equipment_name='OVEN',
            target_equipment_name='COUNTERTOP',
            required_equipment=[],
        ),
        TransferItem(
            description='Transfer cookies from baking sheets to cooling rack',
            source_equipment_name='BAKING_SHEET',
            target_equipment_name='COOLING_RACK',
            scoop_size_amount=1,
            scoop_size_unit='WHOLE',
            required_equipment=[],
        ),
    ]

    recipe = Recipe(
        name='Test Recipe',
        ingredients=ingredients,
        required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
        steps=steps,
    )

    engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
    return engine, wm, recipe


# ---------------------------------------------------------------------------
# End-to-end equipment states
# ---------------------------------------------------------------------------

class TestEndToEndEquipmentStates:
    def test_full_pipeline_one_sheet(self):
        """1 sheet, 1 oven: BOWL->DIRTY, SHEET->DIRTY, OVEN->AVAILABLE,
        COUNTERTOP->AVAILABLE, COOLING_RACK->AVAILABLE."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add butter')]

        engine, wm, recipe = _make_full_pipeline_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=1, num_ovens=1,
        )
        success, plan = engine.run(recipe=recipe)
        assert success is True

        assert wm.query_equipment_state(equipment_name='BOWL', equipment_id=1) == 'DIRTY'
        assert wm.query_equipment_state(equipment_name='BAKING_SHEET', equipment_id=1) == 'DIRTY'
        assert wm.query_equipment_state(equipment_name='OVEN', equipment_id=1) == 'AVAILABLE'
        assert wm.query_equipment_state(equipment_name='COUNTERTOP', equipment_id=1) == 'AVAILABLE'
        assert wm.query_equipment_state(equipment_name='COOLING_RACK', equipment_id=1) == 'AVAILABLE'

    def test_full_pipeline_five_sheets_three_ovens(self):
        """5 sheets, 3 ovens: same state pattern at scale."""
        ingredients = [
            Ingredient(id=1, name='flour', amount=2.25, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=3, name='white sugar', amount=0.75, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=4, name='brown sugar', amount=0.75, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=5, name='eggs', amount=2, unit='whole', measurement_category='WHOLE'),
            Ingredient(id=6, name='vanilla', amount=2, unit='teaspoons', measurement_category='LIQUID'),
            Ingredient(id=7, name='baking soda', amount=1, unit='teaspoons', measurement_category='VOLUME'),
            Ingredient(id=8, name='salt', amount=1, unit='teaspoons', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[2, 3, 4], description='Cream'),
            MixingSubstep(ingredient_ids=[5, 6], description='Wet'),
            MixingSubstep(ingredient_ids=[1, 7, 8], description='Dry'),
        ]

        engine, wm, recipe = _make_full_pipeline_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3,
        )
        success, plan = engine.run(recipe=recipe)
        assert success is True

        assert wm.query_equipment_state(equipment_name='BOWL', equipment_id=1) == 'DIRTY'
        for i in range(1, 6):
            assert wm.query_equipment_state(equipment_name='BAKING_SHEET', equipment_id=i) == 'DIRTY'
        for i in range(1, 4):
            assert wm.query_equipment_state(equipment_name='OVEN', equipment_id=i) == 'AVAILABLE'
        assert wm.query_equipment_state(equipment_name='COUNTERTOP', equipment_id=1) == 'AVAILABLE'
        assert wm.query_equipment_state(equipment_name='COOLING_RACK', equipment_id=1) == 'AVAILABLE'


# ---------------------------------------------------------------------------
# Step request type classification
# ---------------------------------------------------------------------------

class TestStepRequestTypeClassification:
    def _classify(self, *, step):
        """Build a minimal engine, run _build_step_request, return the step_type."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
        req = engine._build_step_request(step=step, step_idx=0, resolved_equipment=[])
        return req.attributes['step_type']

    def test_transfer_equipment_oven_gets_removal_type(self):
        step = TransferEquipment(
            description='Remove', source_equipment_name='OVEN',
            target_equipment_name='COUNTERTOP',
        )
        assert self._classify(step=step) == 'EQUIPMENT_REMOVAL'

    def test_transfer_item_to_cooling_rack_gets_surface_type(self):
        step = TransferItem(
            description='Transfer', source_equipment_name='BAKING_SHEET',
            target_equipment_name='COOLING_RACK',
            scoop_size_amount=1, scoop_size_unit='WHOLE',
        )
        assert self._classify(step=step) == 'ITEM_TRANSFER_TO_SURFACE'

    def test_generic_step_gets_generic_type(self):
        step = Step(description='Do something')
        assert self._classify(step=step) == 'GENERIC'
