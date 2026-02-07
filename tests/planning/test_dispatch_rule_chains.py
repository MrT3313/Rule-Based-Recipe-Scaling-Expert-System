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
# Mixing rule chain: M1 -> M2 -> M2b -> M3
# ---------------------------------------------------------------------------

class TestMixingRuleChain:
    def test_m1_m2_m2b_m3_full_chain_single_ingredient(self):
        """Single ingredient: all 9 intermediate fact types are asserted."""
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

        # M1: step_request(MIXING)
        sr = wm.query_facts(fact_title='step_request', step_type='MIXING')
        assert len(sr) == 1

        # M1: mixing_initialized
        mi = wm.query_facts(fact_title='mixing_initialized')
        assert len(mi) == 1
        assert mi[0].attributes['equipment_name'] == 'BOWL'
        assert mi[0].attributes['equipment_id'] == 1

        # M1: pending_ingredient
        pi = wm.query_facts(fact_title='pending_ingredient')
        assert len(pi) == 1
        assert pi[0].attributes['ingredient_name'] == 'BUTTER'

        # M2: ingredient_addition_request
        iar = wm.query_facts(fact_title='ingredient_addition_request')
        assert len(iar) == 1
        assert iar[0].attributes['equipment_name'] == 'BOWL'

        # Lower-level: equipment_contents
        ec = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert len(ec) >= 1

        # Lower-level: ingredient_added
        ia = wm.query_facts(fact_title='ingredient_added')
        assert len(ia) == 1

        # M2b: ingredient_processed
        ip = wm.query_facts(fact_title='ingredient_processed')
        assert len(ip) == 1

        # M3: mixing_completed
        mc = wm.query_facts(fact_title='mixing_completed')
        assert len(mc) == 1

        # Lower-level: mixed_contents
        mx = wm.query_facts(fact_title='mixed_contents')
        assert len(mx) == 1

    def test_m1_m2_m2b_m3_full_chain_three_ingredients(self):
        """Three ingredients: 3 pending_ingredient, 3 ingredient_processed, 1 mixing_completed."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='sugar', amount=0.75, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=3, name='eggs', amount=2, unit='whole', measurement_category='WHOLE'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1, 2], description='Cream'),
            MixingSubstep(ingredient_ids=[3], description='Add eggs'),
        ]

        engine, wm, recipe = _make_full_pipeline_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=2, num_ovens=1,
        )
        success, plan = engine.run(recipe=recipe)
        assert success is True

        pi = wm.query_facts(fact_title='pending_ingredient')
        assert len(pi) == 3

        ip = wm.query_facts(fact_title='ingredient_processed')
        assert len(ip) == 3

        mc = wm.query_facts(fact_title='mixing_completed')
        assert len(mc) == 1


# ---------------------------------------------------------------------------
# Transfer rule chain: T1 -> T2 -> T3
# ---------------------------------------------------------------------------

class TestTransferRuleChain:
    def test_t1_t2_t3_full_chain_single_sheet(self):
        """1 sheet: all transfer intermediate facts are asserted."""
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

        # T1: transfer_source_started
        tss = wm.query_facts(fact_title='transfer_source_started')
        assert len(tss) == 1
        assert tss[0].attributes['source_equipment_name'] == 'BOWL'

        # T1: transfer_step_info
        tsi = wm.query_facts(fact_title='transfer_step_info')
        assert len(tsi) == 1

        # T1: transfer_planning_request
        tpr = wm.query_facts(fact_title='transfer_planning_request')
        assert len(tpr) == 1

        # Lower-level: transfer_plan
        tp = wm.query_facts(fact_title='transfer_plan')
        assert len(tp) == 1

        # T2: transfer_completed
        tc = wm.query_facts(fact_title='transfer_completed')
        assert len(tc) == 1

        # T2: all_sheets_transferred
        ast = wm.query_facts(fact_title='all_sheets_transferred')
        assert len(ast) == 1

        # T3: transfer_source_processed
        tsp = wm.query_facts(fact_title='transfer_source_processed')
        assert len(tsp) == 1

    def test_t1_t2_t3_full_chain_multiple_sheets(self):
        """2 sheets: 2 transfer_completed, transfer_plan(num_sheets_needed=2)."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=2, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add butter')]

        engine, wm, recipe = _make_full_pipeline_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=2, num_ovens=1,
        )
        success, plan = engine.run(recipe=recipe)
        assert success is True

        tc = wm.query_facts(fact_title='transfer_completed')
        assert len(tc) == 2

        tp = wm.query_facts(fact_title='transfer_plan', first=True)
        assert tp.attributes['num_sheets_needed'] == 2


# ---------------------------------------------------------------------------
# Cook rule chain: C1 -> C2 -> C3
# ---------------------------------------------------------------------------

class TestCookRuleChain:
    def test_c1_c2_c3_full_chain_one_sheet_one_oven(self):
        """1 sheet, 1 oven: cook_initialized, pending_cook_placement, cook_placement_completed,
        cooking_started, cook_completed all asserted."""
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

        # C1: cook_initialized
        ci = wm.query_facts(fact_title='cook_initialized')
        assert len(ci) == 1
        assert ci[0].attributes['source_equipment_name'] == 'BAKING_SHEET'
        assert ci[0].attributes['target_equipment_name'] == 'OVEN'

        # C1: pending_cook_placement
        pcp = wm.query_facts(fact_title='pending_cook_placement')
        assert len(pcp) == 1

        # C2: cook_placement_completed
        cpc = wm.query_facts(fact_title='cook_placement_completed')
        assert len(cpc) == 1

        # Lower-level: cooking_started
        cs = wm.query_facts(fact_title='cooking_started')
        assert len(cs) == 1

        # C3: cook_completed
        cc = wm.query_facts(fact_title='cook_completed')
        assert len(cc) == 1


# ---------------------------------------------------------------------------
# Removal rule chain: R1 -> R2 -> R3
# ---------------------------------------------------------------------------

class TestRemovalRuleChain:
    def test_r1_r2_r3_full_chain_one_sheet(self):
        """1 sheet: removal_initialized, removal_slot_processed, equipment_removal_completed,
        removal_completed all asserted."""
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

        # R1: removal_initialized
        ri = wm.query_facts(fact_title='removal_initialized')
        assert len(ri) == 1
        assert ri[0].attributes['source_equipment_name'] == 'OVEN'

        # R1: item_transfer_target
        itt = wm.query_facts(fact_title='item_transfer_target')
        assert len(itt) >= 1

        # R2: removal_slot_processed
        rsp = wm.query_facts(fact_title='removal_slot_processed')
        assert len(rsp) >= 1

        # R2: oven_wait_completed
        owc = wm.query_facts(fact_title='oven_wait_completed')
        assert len(owc) >= 1

        # Lower-level: equipment_removal_completed
        erc = wm.query_facts(fact_title='equipment_removal_completed')
        assert len(erc) >= 1

        # R3: removal_completed
        rc = wm.query_facts(fact_title='removal_completed')
        assert len(rc) == 1


# ---------------------------------------------------------------------------
# Surface transfer rule chain: ITS1
# ---------------------------------------------------------------------------

class TestSurfaceTransferRuleChain:
    def test_its1_full_chain_one_sheet(self):
        """1 sheet: step_request(ITEM_TRANSFER_TO_SURFACE), surface_transfer_completed asserted."""
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

        # ITS1: step_request(ITEM_TRANSFER_TO_SURFACE)
        sr = wm.query_facts(fact_title='step_request', step_type='ITEM_TRANSFER_TO_SURFACE')
        assert len(sr) == 1

        # ITS1: surface_transfer_completed
        stc = wm.query_facts(fact_title='surface_transfer_completed')
        assert len(stc) == 1


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
    def _classify(self, step):
        """Build a minimal engine, run _build_step_request, return the step_type."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
        req = engine._build_step_request(step, 0, [])
        return req.attributes['step_type']

    def test_mixing_step_gets_mixing_type(self):
        step = MixingStep(description='Mix', substeps=[])
        assert self._classify(step) == 'MIXING'

    def test_transfer_item_gets_transfer_item_type(self):
        step = TransferItem(
            description='Scoop', source_equipment_name='BOWL',
            target_equipment_name='BAKING_SHEET',
            scoop_size_amount=2, scoop_size_unit='TABLESPOONS',
        )
        assert self._classify(step) == 'TRANSFER_ITEM'

    def test_transfer_item_to_cooling_rack_gets_surface_type(self):
        step = TransferItem(
            description='Transfer', source_equipment_name='BAKING_SHEET',
            target_equipment_name='COOLING_RACK',
            scoop_size_amount=1, scoop_size_unit='WHOLE',
        )
        assert self._classify(step) == 'ITEM_TRANSFER_TO_SURFACE'

    def test_transfer_equipment_baking_sheet_gets_transfer_type(self):
        step = TransferEquipment(
            description='Transfer', source_equipment_name='BAKING_SHEET',
            target_equipment_name='OVEN',
        )
        assert self._classify(step) == 'TRANSFER_EQUIPMENT'

    def test_transfer_equipment_oven_gets_removal_type(self):
        step = TransferEquipment(
            description='Remove', source_equipment_name='OVEN',
            target_equipment_name='COUNTERTOP',
        )
        assert self._classify(step) == 'EQUIPMENT_REMOVAL'

    def test_cook_step_gets_cook_type(self):
        step = CookStep(description='Bake', substeps=[])
        assert self._classify(step) == 'COOK'

    def test_generic_step_gets_generic_type(self):
        step = Step(description='Do something')
        assert self._classify(step) == 'GENERIC'

    def test_wait_step_gets_generic_type(self):
        step = WaitStep(description='Wait', equipment_name='OVEN')
        assert self._classify(step) == 'GENERIC'
