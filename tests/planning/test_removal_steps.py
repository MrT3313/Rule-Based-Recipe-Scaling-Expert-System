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


def _make_engine(*, ingredients, substeps, bowl_volume=4, bowl_volume_unit='QUARTS',
                 num_baking_sheets=2, num_ovens=0, oven_racks=2,
                 include_cook_step=False, cook_time=10, cook_time_unit='minutes',
                 include_removal_steps=False, include_item_transfer_steps=False):
    """Build a PlanningEngine with a MixingStep, TransferItem, and optionally Cook/Removal/Transfer steps."""
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

    if include_removal_steps or include_item_transfer_steps:
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='SURFACE',
            equipment_name='COUNTERTOP',
            equipment_id=1,
            state='AVAILABLE',
        ), silent=True)

    if include_item_transfer_steps:
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

    if include_removal_steps:
        steps.append(
            TransferEquipment(
                description='Remove baking sheets from oven to countertop',
                source_equipment_name='OVEN',
                target_equipment_name='COUNTERTOP',
                required_equipment=[],
            ),
        )

    if include_item_transfer_steps:
        steps.append(
            TransferItem(
                description='Transfer cookies from baking sheets to cooling rack',
                source_equipment_name='BAKING_SHEET',
                target_equipment_name='COOLING_RACK',
                scoop_size_amount=1,
                scoop_size_unit='WHOLE',
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
    """Full cookie recipe: produces 38 dough balls -> 5 sheets needed."""
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


class TestEquipmentRemovalPlanLength:
    def test_removal_plan_length_five_sheets_three_ovens(self):
        """5 sheets, 3 ovens (2 racks each), include cook + removal + item transfer steps.
        Existing plan: 1 MixingStep + 5 TransferItems + 3 CookSteps = 9
        Equipment removal: 3 cooking waits + 5 TransferEquipment + 5 TransferItem (DFS) = 13
        Total: 9 + 13 = 22"""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 22

        # Count removal TransferEquipment steps (description contains "Remove")
        removal_steps = [s for s in plan if isinstance(s, TransferEquipment) and 'Remove' in s.description]
        assert len(removal_steps) == 5

        # Count item transfer TransferItem steps (DFS-chained, description contains "COOLING_RACK")
        item_transfer_steps = [s for s in plan if isinstance(s, TransferItem) and 'COOLING_RACK' in s.description]
        assert len(item_transfer_steps) == 5

        # Verify interleaved order: each TransferEquipment removal is immediately followed by a TransferItem
        for i, step in enumerate(plan):
            if isinstance(step, TransferEquipment) and 'Remove' in step.description:
                assert i + 1 < len(plan), f"TransferEquipment at index {i} has no following step"
                next_step = plan[i + 1]
                assert isinstance(next_step, TransferItem) and 'COOLING_RACK' in next_step.description, (
                    f"Expected TransferItem to COOLING_RACK after removal at index {i}, "
                    f"got {type(next_step).__name__}: {next_step.description}"
                )

    def test_removal_plan_length_two_sheets_one_oven(self):
        """2 sheets, 1 oven (2 racks).
        Existing plan: 1 MixingStep + 2 TransferItems + 1 CookStep = 4
        Equipment removal: 1 cooking wait + 2 removal + 2 item transfer (DFS) = 5
        Total: 4 + 5 = 9"""
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
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        assert len(plan) == 9

        # Verify interleaved order
        for i, step in enumerate(plan):
            if isinstance(step, TransferEquipment) and 'Remove' in step.description:
                assert i + 1 < len(plan)
                next_step = plan[i + 1]
                assert isinstance(next_step, TransferItem) and 'COOLING_RACK' in next_step.description


class TestEquipmentRemovalPerTray:
    def test_one_removal_step_per_tray(self):
        """5 sheets, 3 ovens — exactly 5 TransferEquipment steps in the removal portion."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        # Removal steps come after CookSteps
        removal_steps = [s for s in plan if isinstance(s, TransferEquipment) and 'Remove' in s.description]
        assert len(removal_steps) == 5


class TestItemTransferPerSheet:
    def test_one_transfer_step_per_sheet(self):
        """5 sheets, 3 ovens — exactly 5 item transfer TransferItem steps (DFS-chained)."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        item_transfer_steps = [s for s in plan if isinstance(s, TransferItem) and 'COOLING_RACK' in s.description]
        assert len(item_transfer_steps) == 5


class TestEquipmentStateAfterRemoval:
    def test_ovens_available_after_removal(self):
        """After full run: all 3 ovens should be in AVAILABLE state."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        for oven_id in [1, 2, 3]:
            state = wm.query_equipment_state(equipment_name='OVEN', equipment_id=oven_id)
            assert state == 'AVAILABLE', f"OVEN #{oven_id} should be AVAILABLE but is {state}"

    def test_baking_sheets_dirty_after_transfer(self):
        """After full run: all 5 baking sheets should be in DIRTY state."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        for sheet_id in [1, 2, 3, 4, 5]:
            state = wm.query_equipment_state(equipment_name='BAKING_SHEET', equipment_id=sheet_id)
            assert state == 'DIRTY', f"BAKING_SHEET #{sheet_id} should be DIRTY but is {state}"


# ---------------------------------------------------------------------------
# Removal dispatch intermediate facts
# ---------------------------------------------------------------------------

class TestRemovalDispatchIntermediateFacts:
    def test_removal_initialized_fact(self):
        """removal_initialized has source='OVEN', target='COUNTERTOP'."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        success, _ = engine.run(recipe=recipe)
        assert success is True

        ri = wm.query_facts(fact_title='removal_initialized')
        assert len(ri) == 1
        assert ri[0].attributes['source_equipment_name'] == 'OVEN'
        assert ri[0].attributes['target_equipment_name'] == 'COUNTERTOP'

    def test_item_transfer_target_pre_asserted(self):
        """item_transfer_target with target='COOLING_RACK'."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        itt = wm.query_facts(fact_title='item_transfer_target')
        assert len(itt) >= 1
        assert itt[0].attributes['target_equipment_name'] == 'COOLING_RACK'

    def test_removal_slot_processed_facts_match_sheets(self):
        """N removal_slot_processed facts = N sheets (one per oven slot with a sheet)."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        rsp = wm.query_facts(fact_title='removal_slot_processed')
        assert len(rsp) == 5

    def test_oven_wait_completed_facts_match_ovens(self):
        """N oven_wait_completed facts = N ovens that had sheets."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        owc = wm.query_facts(fact_title='oven_wait_completed')
        oven_ids = {f.attributes['equipment_id'] for f in owc}
        assert oven_ids == {1, 2, 3}

    def test_removal_completed_fact(self):
        """1 removal_completed fact."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        rc = wm.query_facts(fact_title='removal_completed')
        assert len(rc) == 1

    def test_equipment_removal_completed_facts(self):
        """N equipment_removal_completed facts per sheet."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        erc = wm.query_facts(fact_title='equipment_removal_completed')
        assert len(erc) == 5

    def test_item_transfer_completed_from_dfs_chain(self):
        """N item_transfer_completed facts per sheet (DFS-chained from removal)."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        itc = wm.query_facts(fact_title='item_transfer_completed')
        assert len(itc) == 5


# ---------------------------------------------------------------------------
# Surface transfer dispatch intermediate facts
# ---------------------------------------------------------------------------

class TestSurfaceTransferDispatchFacts:
    def test_surface_transfer_completed_fact(self):
        """1 surface_transfer_completed fact."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        stc = wm.query_facts(fact_title='surface_transfer_completed')
        assert len(stc) == 1

    def test_step_request_equipment_removal_type(self):
        """TransferEquipment(source=OVEN) -> step_request(step_type='EQUIPMENT_REMOVAL')."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        sr = wm.query_facts(fact_title='step_request', step_type='EQUIPMENT_REMOVAL')
        assert len(sr) == 1

    def test_step_request_item_transfer_to_surface_type(self):
        """TransferItem(target=COOLING_RACK) -> step_request(step_type='ITEM_TRANSFER_TO_SURFACE')."""
        ingredients, substeps = _cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        engine.run(recipe=recipe)

        sr = wm.query_facts(fact_title='step_request', step_type='ITEM_TRANSFER_TO_SURFACE')
        assert len(sr) == 1


# ---------------------------------------------------------------------------
# Removal failure paths
# ---------------------------------------------------------------------------

class TestRemovalFailurePaths:
    def test_removal_with_no_cooking_started_facts(self):
        """Removal without cook step fails gracefully."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=2, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Mix')]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=2, num_ovens=1, oven_racks=2,
            include_cook_step=False,
            include_removal_steps=True, include_item_transfer_steps=False,
        )
        success, error = engine.run(recipe=recipe)
        assert success is False

    def test_removal_with_no_target_surface(self):
        """Removal with no COUNTERTOP surface fails."""
        wm = WorkingMemory()
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT', equipment_type='CONTAINER',
            equipment_name='BOWL', equipment_id=1, state='AVAILABLE',
            volume=4, volume_unit='QUARTS',
        ), silent=True)
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT', equipment_type='TRAY',
            equipment_name='BAKING_SHEET', equipment_id=1, state='AVAILABLE',
        ), silent=True)
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT', equipment_type='APPLIANCE',
            equipment_name='OVEN', equipment_id=1, state='IN_USE',
            number_of_racks=2,
        ), silent=True)
        # No COUNTERTOP or COOLING_RACK

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
        kb.add_reference_fact(fact=get_measurement_unit_conversion_facts())
        kb.add_reference_fact(fact=get_transfer_reference_facts())

        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]

        recipe = Recipe(
            name='Test Recipe',
            ingredients=ingredients,
            required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
            steps=[
                MixingStep(
                    description='Mix',
                    required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
                    substeps=[MixingSubstep(ingredient_ids=[1], description='Add butter')],
                ),
                TransferItem(
                    description='Scoop',
                    source_equipment_name='BOWL',
                    target_equipment_name='BAKING_SHEET',
                    scoop_size_amount=2, scoop_size_unit='TABLESPOONS',
                    required_equipment=[],
                ),
                CookStep(
                    description='Bake',
                    substeps=[
                        TransferEquipment(
                            description='Transfer to oven',
                            source_equipment_name='BAKING_SHEET',
                            target_equipment_name='OVEN',
                            required_equipment=[],
                        ),
                        WaitStep(
                            description='Bake',
                            equipment_name='OVEN',
                            duration=10, duration_unit='minutes',
                        ),
                    ],
                    required_equipment=[],
                ),
                TransferEquipment(
                    description='Remove from oven',
                    source_equipment_name='OVEN',
                    target_equipment_name='COUNTERTOP',
                    required_equipment=[],
                ),
            ],
        )

        engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
        success, error = engine.run(recipe=recipe)
        assert success is False

    def test_removal_with_empty_oven(self):
        """Removal with an oven that has no equipment_contents generates no removal steps."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Mix')]

        # 1 sheet, 1 oven (2 racks) — but we add a second oven that's empty
        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=1, num_ovens=1, oven_racks=2,
            include_cook_step=True, cook_time=10, cook_time_unit='minutes',
            include_removal_steps=True, include_item_transfer_steps=True,
        )
        success, plan = engine.run(recipe=recipe)
        assert success is True

        # Only 1 sheet was placed, so only 1 removal_slot_processed
        rsp = wm.query_facts(fact_title='removal_slot_processed')
        assert len(rsp) == 1
