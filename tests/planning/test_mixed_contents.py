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
from planning.classes.Step import Step
from planning.engine import PlanningEngine
from planning.rules.equipment_status import get_equipment_status_rules
from planning.rules.ingredient_rules import get_ingredient_rules
from planning.rules.transfer_rules import get_transfer_rules
from planning.rules.equipment_transfer_rules import get_equipment_transfer_rules
from scaling.facts.measurement_unit_conversions import get_measurement_unit_conversion_facts
from planning.facts.transfer_reference_facts import get_transfer_reference_facts


def _make_engine(*, ingredients, substeps, bowl_volume=4, bowl_volume_unit='QUARTS',
                 num_baking_sheets=2, include_transfer=True,
                 num_ovens=0, oven_racks=2, include_equipment_transfer=False):
    """Build a PlanningEngine with a MixingStep and optionally a TransferStep."""
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
        # First oven starts IN_USE (simulates PreheatStep having already run)
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
    if include_equipment_transfer:
        kb.add_rules(rules=get_equipment_transfer_rules())
    kb.add_reference_fact(fact=get_measurement_unit_conversion_facts())
    kb.add_reference_fact(fact=get_transfer_reference_facts())

    steps = [
        MixingStep(
            description='Mix ingredients',
            required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
            substeps=substeps,
        ),
    ]

    if include_transfer:
        steps.append(
            TransferItem(
                description='Scoop dough onto baking sheets',
                source_equipment_name='BOWL',
                target_equipment_name='BAKING_SHEET',
                scoop_size_amount=2,
                scoop_size_unit='TABLESPOONS',
                required_equipment=[],
            ),
        )

    if include_equipment_transfer:
        steps.append(
            TransferEquipment(
                description='Transfer baking sheets to oven racks',
                source_equipment_name='BAKING_SHEET',
                target_equipment_name='OVEN',
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


def _make_two_bowl_engine(*, ingredients, substeps_bowl1, substeps_bowl2,
                          bowl_volume=4, num_baking_sheets=6):
    """Build a PlanningEngine with two BOWLs, two MixingSteps, and a TransferStep."""
    wm = WorkingMemory()
    for bowl_id in [1, 2]:
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='CONTAINER',
            equipment_name='BOWL',
            equipment_id=bowl_id,
            state='AVAILABLE',
            volume=bowl_volume,
            volume_unit='QUARTS',
        ), silent=True)

    for i in range(num_baking_sheets):
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='TRAY',
            equipment_name='BAKING_SHEET',
            equipment_id=i + 1,
            state='AVAILABLE',
        ), silent=True)

    kb = KnowledgeBase()
    kb.add_rules(rules=get_equipment_status_rules())
    kb.add_rules(rules=get_ingredient_rules())
    kb.add_rules(rules=get_transfer_rules())
    kb.add_reference_fact(fact=get_measurement_unit_conversion_facts())
    kb.add_reference_fact(fact=get_transfer_reference_facts())

    steps = [
        MixingStep(
            description='Mix in bowl 1',
            required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
            substeps=substeps_bowl1,
        ),
        MixingStep(
            description='Mix in bowl 2',
            required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
            substeps=substeps_bowl2,
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

    recipe = Recipe(
        name='Test Recipe (2 bowls)',
        ingredients=ingredients,
        required_equipment=[{'equipment_name': 'BOWL', 'required_count': 2}],
        steps=steps,
    )

    engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
    return engine, wm, recipe


# ---------------------------------------------------------------------------
# Happy path: mixed_contents derivation
# ---------------------------------------------------------------------------

class TestMixedContentsDerived:
    def test_mixing_completed_asserted(self):
        """After MixingStep substeps succeed, a mixing_completed trigger fact is asserted."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add butter')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps, include_transfer=False)
        success, _ = engine.run(recipe=recipe)

        assert success is True
        triggers = wm.query_facts(fact_title='mixing_completed')
        assert len(triggers) == 1
        assert triggers[0].attributes['equipment_name'] == 'BOWL'
        assert triggers[0].attributes['equipment_id'] == 1

    def test_mixed_contents_fact_derived(self):
        """summarize_mixed_contents rule fires and derives a mixed_contents fact."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add butter')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps, include_transfer=False)
        success, _ = engine.run(recipe=recipe)

        assert success is True
        mixed = wm.query_facts(fact_title='mixed_contents')
        assert len(mixed) == 1
        assert mixed[0].attributes['equipment_name'] == 'BOWL'
        assert mixed[0].attributes['equipment_id'] == 1
        assert mixed[0].attributes['volume_unit'] == 'QUARTS'

    def test_mixed_contents_total_volume_single_ingredient(self):
        """mixed_contents total_volume equals the single ingredient's volume."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add butter')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps, include_transfer=False)
        engine.run(recipe=recipe)

        mixed = wm.query_facts(fact_title='mixed_contents', first=True)
        # 1 cup = 48 tsp, 1 quart = 192 tsp -> 48/192 = 0.25 quarts
        assert mixed.attributes['total_volume'] == pytest.approx(0.25)

    def test_mixed_contents_total_volume_multiple_ingredients(self):
        """mixed_contents total_volume sums across all ingredients (excluding WHOLE)."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='sugar', amount=0.75, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=3, name='eggs', amount=2, unit='whole', measurement_category='WHOLE'),
            Ingredient(id=4, name='vanilla', amount=2, unit='teaspoons', measurement_category='LIQUID'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1, 2], description='Cream'),
            MixingSubstep(ingredient_ids=[3, 4], description='Add wet'),
        ]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps, include_transfer=False)
        engine.run(recipe=recipe)

        mixed = wm.query_facts(fact_title='mixed_contents', first=True)
        # butter: 1 cup = 0.25 quarts
        # sugar: 0.75 cups = 0.1875 quarts
        # eggs: 0 (WHOLE)
        # vanilla: 2 tsp / 192 tsp-per-quart
        expected = (1 * 48 + 0.75 * 48 + 0 + 2) / 192
        assert mixed.attributes['total_volume'] == pytest.approx(expected)

    def test_no_mixed_contents_when_substeps_fail(self):
        """If substeps fail (capacity exceeded), no mixing_completed or mixed_contents is asserted."""
        ingredients = [
            Ingredient(id=1, name='flour', amount=20, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add flour')]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            bowl_volume=0.5, include_transfer=False,
        )
        success, _ = engine.run(recipe=recipe)

        assert success is False
        assert wm.query_facts(fact_title='mixing_completed') == []
        assert wm.query_facts(fact_title='mixed_contents') == []


# ---------------------------------------------------------------------------
# Happy path: TransferStep discovers source via mixed_contents
# ---------------------------------------------------------------------------

class TestTransferDiscovery:
    def test_transfer_discovers_bowl_from_mixed_contents(self):
        """TransferStep queries mixed_contents to find source BOWL — no hardcoded id."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='flour', amount=2.25, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1], description='Cream'),
            MixingSubstep(ingredient_ids=[2], description='Add flour'),
        ]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        # transfer_plan should exist
        transfer_plan = wm.query_facts(fact_title='transfer_plan', first=True)
        assert transfer_plan is not None
        assert transfer_plan.attributes['num_dough_balls'] > 0
        # 1 MixingStep + 4 TransferSteps (26 balls / 8 per sheet = 4 sheets)
        assert len(plan) == 5

    def test_transfer_creates_transfer_completed_facts(self):
        """Transfer execution creates transfer_completed facts for each sheet."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Cream')]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        completed = wm.query_facts(fact_title='transfer_completed')
        assert len(completed) >= 1
        # All completed facts should reference BOWL #1 as source
        for fact in completed:
            assert fact.attributes['source_equipment_name'] == 'BOWL'
            assert fact.attributes['source_equipment_id'] == 1
        # 1 MixingStep + 1 TransferStep (8 balls / 8 per sheet)
        assert len(plan) == 2

    def test_source_bowl_marked_dirty_after_transfer(self):
        """After transfer completes, source BOWL is marked DIRTY."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Cream')]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        bowl = wm.query_equipment(equipment_name='BOWL', equipment_id=1, first=True)
        assert bowl.attributes['state'] == 'DIRTY'
        # 1 MixingStep + 1 TransferStep (8 balls / 8 per sheet)
        assert len(plan) == 2

    def test_transfer_plan_dough_ball_count(self):
        """Dough ball count = total_volume (in base units) / scoop_size (in base units)."""
        # 1 cup butter = 48 tsp; scoop = 2 tablespoons = 6 tsp; 48/6 = 8 dough balls
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Cream')]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        transfer_plan = wm.query_facts(fact_title='transfer_plan', first=True)
        assert transfer_plan.attributes['num_dough_balls'] == 8
        # 1 MixingStep + 1 TransferStep (8 balls / 8 per sheet)
        assert len(plan) == 2


# ---------------------------------------------------------------------------
# Happy path: two bowls (multi-source transfer)
# ---------------------------------------------------------------------------

class TestMultiBowlTransfer:
    def test_two_bowls_both_produce_mixed_contents(self):
        """Two MixingSteps on two BOWLs produce two mixed_contents facts."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='flour', amount=1, unit='cups', measurement_category='VOLUME'),
        ]

        engine, wm, recipe = _make_two_bowl_engine(
            ingredients=ingredients,
            substeps_bowl1=[MixingSubstep(ingredient_ids=[1], description='Bowl 1')],
            substeps_bowl2=[MixingSubstep(ingredient_ids=[2], description='Bowl 2')],
        )
        success, _ = engine.run(recipe=recipe)

        assert success is True
        mixed = wm.query_facts(fact_title='mixed_contents')
        assert len(mixed) == 2
        ids = {m.attributes['equipment_id'] for m in mixed}
        assert ids == {1, 2}

    def test_two_bowls_transfer_processes_both(self):
        """TransferStep processes dough from both bowls onto sheets."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='flour', amount=1, unit='cups', measurement_category='VOLUME'),
        ]

        engine, wm, recipe = _make_two_bowl_engine(
            ingredients=ingredients,
            substeps_bowl1=[MixingSubstep(ingredient_ids=[1], description='Bowl 1')],
            substeps_bowl2=[MixingSubstep(ingredient_ids=[2], description='Bowl 2')],
            num_baking_sheets=6,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        completed = wm.query_facts(fact_title='transfer_completed')
        # Both bowls should have transfer_completed facts
        source_ids = {f.attributes['source_equipment_id'] for f in completed}
        assert source_ids == {1, 2}
        # 2 MixingSteps + 2 TransferSteps (8 balls each = 1 sheet each)
        assert len(plan) == 4

    def test_two_bowls_both_marked_dirty(self):
        """After transfer, both source BOWLs are DIRTY."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='flour', amount=1, unit='cups', measurement_category='VOLUME'),
        ]

        engine, wm, recipe = _make_two_bowl_engine(
            ingredients=ingredients,
            substeps_bowl1=[MixingSubstep(ingredient_ids=[1], description='Bowl 1')],
            substeps_bowl2=[MixingSubstep(ingredient_ids=[2], description='Bowl 2')],
            num_baking_sheets=6,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True
        bowl1 = wm.query_equipment(equipment_name='BOWL', equipment_id=1, first=True)
        bowl2 = wm.query_equipment(equipment_name='BOWL', equipment_id=2, first=True)
        assert bowl1.attributes['state'] == 'DIRTY'
        assert bowl2.attributes['state'] == 'DIRTY'
        # 2 MixingSteps + 2 TransferSteps (8 balls each = 1 sheet each)
        assert len(plan) == 4


# ---------------------------------------------------------------------------
# Plan structure: one TransferStep per sheet
# ---------------------------------------------------------------------------

class TestPlanTransferStepsPerSheet:
    def test_plan_contains_one_transfer_step_per_sheet(self):
        """Each baking sheet gets its own TransferStep in the plan with a unique description."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='flour', amount=2.25, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1], description='Cream'),
            MixingSubstep(ingredient_ids=[2], description='Add flour'),
        ]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        transfer_steps = [s for s in plan if isinstance(s, TransferItem)]
        # 26 dough balls / 8 per sheet = 4 sheets
        assert len(transfer_steps) == 4

        # Each TransferStep is a distinct instance with a unique description referencing its sheet id
        descriptions = [s.description for s in transfer_steps]
        assert len(set(descriptions)) == len(descriptions), "Each TransferStep should have a unique description"

        for desc in descriptions:
            assert 'BAKING_SHEET #' in desc
            assert 'dough balls' in desc


# ---------------------------------------------------------------------------
# Failure states
# ---------------------------------------------------------------------------

class TestTransferFailures:
    def test_no_mixed_contents_for_source_equipment(self):
        """TransferStep fails when no mixed_contents fact exists for the source equipment."""
        wm = WorkingMemory()
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='CONTAINER',
            equipment_name='BOWL',
            equipment_id=1,
            state='AVAILABLE',
            volume=4,
            volume_unit='QUARTS',
        ), silent=True)
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='TRAY',
            equipment_name='BAKING_SHEET',
            equipment_id=1,
            state='AVAILABLE',
        ), silent=True)

        kb = KnowledgeBase()
        kb.add_rules(rules=get_equipment_status_rules())
        kb.add_rules(rules=get_ingredient_rules())
        kb.add_rules(rules=get_transfer_rules())
        kb.add_reference_fact(fact=get_measurement_unit_conversion_facts())
        kb.add_reference_fact(fact=get_transfer_reference_facts())

        # Recipe with ONLY a TransferStep — no MixingStep to produce mixed_contents
        recipe = Recipe(
            name='Test Recipe',
            ingredients=[],
            required_equipment=[],
            steps=[
                TransferItem(
                    description='Scoop dough',
                    source_equipment_name='BOWL',
                    target_equipment_name='BAKING_SHEET',
                    scoop_size_amount=2,
                    scoop_size_unit='TABLESPOONS',
                    required_equipment=[],
                ),
            ],
        )

        engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
        success, error = engine.run(recipe=recipe)

        assert success is False
        assert 'No mixed_contents' in error
        assert 'BOWL' in error

    def test_not_enough_baking_sheets(self):
        """Transfer fails when there aren't enough BAKING_SHEETs for the dough."""
        # 2.25 cups flour = 108 tsp; scoop = 6 tsp -> 18 dough balls
        # capacity_per_sheet = 8; needs 3 sheets, only 1 available
        ingredients = [
            Ingredient(id=1, name='flour', amount=2.25, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add flour')]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=1,
        )
        success, error = engine.run(recipe=recipe)

        assert success is False
        assert 'BAKING_SHEET' in error

    def test_transfer_step_no_source_equipment_id_attribute(self):
        """TransferStep no longer has a source_equipment_id attribute."""
        step = TransferItem(
            description='Scoop dough',
            source_equipment_name='BOWL',
            target_equipment_name='BAKING_SHEET',
            scoop_size_amount=2,
            scoop_size_unit='TABLESPOONS',
        )
        assert not hasattr(step, 'source_equipment_id')


# ---------------------------------------------------------------------------
# Full recipe integration
# ---------------------------------------------------------------------------

class TestFullRecipeWithTransfer:
    def test_chocolate_chip_cookies_mix_and_transfer(self):
        """Full cookie recipe: mix all ingredients, then transfer to sheets."""
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

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        # mixed_contents derived with correct total
        mixed = wm.query_facts(fact_title='mixed_contents', first=True)
        assert mixed is not None
        # Volume: (1+0.75+0.75+2.25) cups + (2+1+1) tsp = 4.75*48 + 4 = 232 tsp / 192
        expected_volume = (4.75 * 48 + 4) / 192
        assert mixed.attributes['total_volume'] == pytest.approx(expected_volume)

        # transfer_plan: 232 tsp / 6 tsp per scoop = 38 dough balls
        transfer_plan = wm.query_facts(fact_title='transfer_plan', first=True)
        assert transfer_plan.attributes['num_dough_balls'] == 38
        assert transfer_plan.attributes['capacity_per_sheet'] == 8
        assert transfer_plan.attributes['num_sheets_needed'] == 5

        # All 5 sheets have transfer_completed facts
        completed = wm.query_facts(fact_title='transfer_completed')
        assert len(completed) == 5

        # Source bowl is DIRTY
        bowl = wm.query_equipment(equipment_name='BOWL', equipment_id=1, first=True)
        assert bowl.attributes['state'] == 'DIRTY'

        # 1 MixingStep + 5 TransferSteps (38 balls / 8 per sheet = 5 sheets)
        assert len(plan) == 6


# ---------------------------------------------------------------------------
# Equipment transfer (baking sheets → oven racks) with preheat waits
# ---------------------------------------------------------------------------

class TestEquipmentTransferPlanLength:
    """Verify plan includes preheat wait steps for all ovens (including on-demand ones)."""

    def _cookie_ingredients_and_substeps(self):
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

    def test_five_sheets_three_ovens(self):
        """5 sheets, 3 ovens (2 racks each) → 3 preheat waits + 5 rack placements."""
        ingredients, substeps = self._cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=3, oven_racks=2,
            include_equipment_transfer=True,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        # 1 MixingStep + 5 TransferSteps + 3 preheat waits + 5 TransferEquipments = 14
        assert len(plan) == 14

        preheat_steps = [s for s in plan if s.description.startswith('Wait for OVEN')]
        assert len(preheat_steps) == 3
        assert 'OVEN #1' in preheat_steps[0].description
        assert 'OVEN #2' in preheat_steps[1].description
        assert 'OVEN #3' in preheat_steps[2].description

        equip_transfer_steps = [s for s in plan if isinstance(s, TransferEquipment)]
        assert len(equip_transfer_steps) == 5

    def test_two_sheets_one_oven(self):
        """2 sheets (small recipe), 1 oven (2 racks) → 1 preheat wait + 2 rack placements."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1], description='Mix butter'),
        ]
        # 1 cup butter = 48 tsp / 6 tsp per scoop = 8 dough balls / 8 per sheet = 1 sheet
        # Need more: 2 cups → 96 tsp / 6 = 16 balls / 8 = 2 sheets
        ingredients = [
            Ingredient(id=1, name='butter', amount=2, unit='cups', measurement_category='VOLUME'),
        ]

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=2, num_ovens=1, oven_racks=2,
            include_equipment_transfer=True,
        )
        success, plan = engine.run(recipe=recipe)

        assert success is True

        # 1 MixingStep + 2 TransferSteps + 1 preheat wait + 2 TransferEquipments = 6
        assert len(plan) == 6

        preheat_steps = [s for s in plan if s.description.startswith('Wait for OVEN')]
        assert len(preheat_steps) == 1

        equip_transfer_steps = [s for s in plan if isinstance(s, TransferEquipment)]
        assert len(equip_transfer_steps) == 2

    def test_not_enough_ovens_fails(self):
        """5 sheets but only 2 ovens (4 rack slots) → should fail."""
        ingredients, substeps = self._cookie_ingredients_and_substeps()

        engine, wm, recipe = _make_engine(
            ingredients=ingredients, substeps=substeps,
            num_baking_sheets=5, num_ovens=2, oven_racks=2,
            include_equipment_transfer=True,
        )
        success, result = engine.run(recipe=recipe)

        assert success is False
