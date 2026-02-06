import pytest

from classes.Fact import Fact
from classes.Ingredient import Ingredient
from classes.KnowledgeBase import KnowledgeBase
from classes.Recipe import Recipe
from classes.WorkingMemory import WorkingMemory
from planning.classes.MixingStep import MixingStep
from planning.classes.MixingSubstep import MixingSubstep
from planning.engine import PlanningEngine
from planning.rules.equipment_status import get_equipment_status_rules
from planning.rules.ingredient_rules import get_ingredient_rules
from scaling.facts.measurement_unit_conversions import get_measurement_unit_conversion_facts


def _make_engine(*, bowl_volume=4, bowl_volume_unit='QUARTS', ingredients, substeps):
    """Build a PlanningEngine with one AVAILABLE BOWL and the given ingredients/substeps."""
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

    kb = KnowledgeBase()
    kb.add_rules(rules=get_equipment_status_rules())
    kb.add_rules(rules=get_ingredient_rules())
    kb.add_reference_fact(fact=get_measurement_unit_conversion_facts())

    recipe = Recipe(
        name='Test Recipe',
        ingredients=ingredients,
        required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
        steps=[
            MixingStep(
                description='Mix ingredients',
                required_equipment=[{'equipment_name': 'BOWL', 'required_count': 1}],
                substeps=substeps,
            ),
        ],
    )

    engine = PlanningEngine(wm=wm, kb=kb, verbose=False)
    return engine, wm, recipe


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestIngredientAdditionHappyPath:
    def test_single_volume_ingredient(self):
        """One cup of butter into a 4-quart bowl — should succeed."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add butter')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert len(contents) == 1
        assert contents[0].attributes['ingredient_name'] == 'BUTTER'
        # 1 cup = 48 tsp, 1 quart = 192 tsp → 48/192 = 0.25
        assert contents[0].attributes['volume_in_equipment_unit'] == pytest.approx(0.25)

    def test_single_whole_ingredient(self):
        """Whole items (eggs) occupy zero measurable volume."""
        ingredients = [
            Ingredient(id=1, name='eggs', amount=2, unit='whole', measurement_category='WHOLE'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add eggs')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert len(contents) == 1
        assert contents[0].attributes['volume_in_equipment_unit'] == 0

    def test_single_liquid_ingredient(self):
        """Liquid (vanilla extract) converts the same as volume through teaspoons base."""
        ingredients = [
            Ingredient(id=1, name='vanilla extract', amount=2, unit='teaspoons', measurement_category='LIQUID'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add vanilla')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert len(contents) == 1
        # 2 tsp / 192 tsp-per-quart ≈ 0.01042
        assert contents[0].attributes['volume_in_equipment_unit'] == pytest.approx(2 / 192)

    def test_multiple_ingredients_single_substep(self):
        """Three ingredients added in one substep — all fit."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='white sugar', amount=0.75, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=3, name='brown sugar', amount=0.75, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1, 2, 3], description='Cream butter and sugars')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert len(contents) == 3
        total = sum(c.attributes['volume_in_equipment_unit'] for c in contents)
        # (1 + 0.75 + 0.75) cups = 2.5 cups = 120 tsp → 120/192 = 0.625 quarts
        assert total == pytest.approx(0.625)

    def test_multiple_substeps(self):
        """Ingredients spread across two substeps — cumulative volume tracked."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='flour', amount=2.25, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1], description='Cream butter'),
            MixingSubstep(ingredient_ids=[2], description='Add flour'),
        ]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert len(contents) == 2
        total = sum(c.attributes['volume_in_equipment_unit'] for c in contents)
        # (1 + 2.25) cups = 3.25 * 48 / 192 = 0.8125 quarts
        assert total == pytest.approx(0.8125)

    def test_mixed_volume_whole_and_liquid(self):
        """A mix of VOLUME, WHOLE, and LIQUID ingredients all in one substep."""
        ingredients = [
            Ingredient(id=1, name='flour', amount=2, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='eggs', amount=3, unit='whole', measurement_category='WHOLE'),
            Ingredient(id=3, name='vanilla', amount=1, unit='tablespoons', measurement_category='LIQUID'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1, 2, 3], description='Mix all')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert len(contents) == 3

        volumes = {c.attributes['ingredient_name']: c.attributes['volume_in_equipment_unit'] for c in contents}
        assert volumes['FLOUR'] == pytest.approx(2 * 48 / 192)     # 0.5 quarts
        assert volumes['EGGS'] == 0                                  # whole
        assert volumes['VANILLA'] == pytest.approx(1 * 3 / 192)     # 1 tbsp = 3 tsp → 3/192

    def test_exact_capacity_fit(self):
        """Ingredients that fill the bowl exactly to capacity should succeed."""
        # 4 quarts = 4 * 192 = 768 tsp → 768/48 = 16 cups exactly
        ingredients = [
            Ingredient(id=1, name='flour', amount=16, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add flour')]

        engine, wm, recipe = _make_engine(bowl_volume=4, ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert contents[0].attributes['volume_in_equipment_unit'] == pytest.approx(4.0)

    def test_small_unit_teaspoons(self):
        """Small amounts in teaspoons convert correctly."""
        ingredients = [
            Ingredient(id=1, name='salt', amount=1, unit='teaspoons', measurement_category='VOLUME'),
            Ingredient(id=2, name='baking soda', amount=1, unit='teaspoons', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1, 2], description='Add leavening')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        total = sum(c.attributes['volume_in_equipment_unit'] for c in contents)
        # 2 tsp / 192 tsp-per-quart
        assert total == pytest.approx(2 / 192)

    def test_ingredient_added_facts_derived(self):
        """The rule should derive ingredient_added consequent facts."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='eggs', amount=2, unit='whole', measurement_category='WHOLE'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1, 2], description='Add all')]

        engine, wm, recipe = _make_engine(ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        added_facts = wm.query_facts(fact_title='ingredient_added')
        assert len(added_facts) == 2
        names = {f.attributes['ingredient_name'] for f in added_facts}
        assert names == {'BUTTER', 'EGGS'}


# ---------------------------------------------------------------------------
# Capacity-exceeded failure tests
# ---------------------------------------------------------------------------

class TestIngredientAdditionCapacityFailure:
    def test_single_ingredient_exceeds_capacity(self):
        """One ingredient larger than the bowl — should fail."""
        ingredients = [
            Ingredient(id=1, name='flour', amount=4, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add flour')]

        # 0.5 quarts = 2 cups capacity; 4 cups won't fit
        engine, wm, recipe = _make_engine(bowl_volume=0.5, ingredients=ingredients, substeps=substeps)
        success, error = engine.run(recipe=recipe)

        assert success is False
        assert 'capacity_exceeded' in error
        assert 'FLOUR' in error

    def test_cumulative_overflow_within_substep(self):
        """First ingredient fits, second pushes over capacity in the same substep."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='sugar', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1, 2], description='Cream')]

        # 0.375 quarts = 1.5 cups; butter (1 cup) fits, sugar (1 cup) overflows
        engine, wm, recipe = _make_engine(bowl_volume=0.375, ingredients=ingredients, substeps=substeps)
        success, error = engine.run(recipe=recipe)

        assert success is False
        assert 'capacity_exceeded' in error
        assert 'SUGAR' in error

    def test_cumulative_overflow_across_substeps(self):
        """Ingredients fit in substep 1, but substep 2 pushes over capacity."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='flour', amount=2, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1], description='Cream butter'),
            MixingSubstep(ingredient_ids=[2], description='Add flour'),
        ]

        # 0.5 quarts = 2 cups; butter (1 cup) fits, flour (2 cups) overflows
        engine, wm, recipe = _make_engine(bowl_volume=0.5, ingredients=ingredients, substeps=substeps)
        success, error = engine.run(recipe=recipe)

        assert success is False
        assert 'capacity_exceeded' in error
        assert 'FLOUR' in error

    def test_tiny_bowl_fails_immediately(self):
        """A very small bowl (1 tablespoon = 0.015625 quarts) can't hold 1 cup."""
        ingredients = [
            Ingredient(id=1, name='butter', amount=1, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add butter')]

        # 1 tablespoon = 3 tsp; 1 cup = 48 tsp → way over
        engine, wm, recipe = _make_engine(bowl_volume=0.015625, ingredients=ingredients, substeps=substeps)
        success, error = engine.run(recipe=recipe)

        assert success is False
        assert 'capacity_exceeded' in error

    def test_whole_items_dont_cause_overflow(self):
        """Even many WHOLE items shouldn't overflow since they have volume=0."""
        ingredients = [
            Ingredient(id=1, name='eggs', amount=100, unit='whole', measurement_category='WHOLE'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add eggs')]

        # Tiny bowl — but whole items don't count toward volume
        engine, wm, recipe = _make_engine(bowl_volume=0.01, ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True

    def test_overflow_after_exact_fill(self):
        """Fill bowl exactly to capacity, then one more teaspoon overflows."""
        # 1 quart bowl = 192 tsp = 4 cups
        ingredients = [
            Ingredient(id=1, name='flour', amount=4, unit='cups', measurement_category='VOLUME'),
            Ingredient(id=2, name='salt', amount=1, unit='teaspoons', measurement_category='VOLUME'),
        ]
        substeps = [
            MixingSubstep(ingredient_ids=[1], description='Add flour'),
            MixingSubstep(ingredient_ids=[2], description='Add salt'),
        ]

        engine, wm, recipe = _make_engine(bowl_volume=1, ingredients=ingredients, substeps=substeps)
        success, error = engine.run(recipe=recipe)

        assert success is False
        assert 'capacity_exceeded' in error
        assert 'SALT' in error

    def test_no_equipment_contents_asserted_on_failure(self):
        """When capacity is exceeded, no equipment_contents fact should exist for the failing ingredient."""
        ingredients = [
            Ingredient(id=1, name='flour', amount=20, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add flour')]

        engine, wm, recipe = _make_engine(bowl_volume=0.5, ingredients=ingredients, substeps=substeps)
        success, error = engine.run(recipe=recipe)

        assert success is False
        # The failing ingredient should NOT have an equipment_contents fact
        contents = wm.query_facts(fact_title='equipment_contents', ingredient_id=1)
        assert len(contents) == 0

    def test_no_ingredient_added_derived_on_failure(self):
        """When capacity is exceeded, no ingredient_added consequent should be derived."""
        ingredients = [
            Ingredient(id=1, name='flour', amount=20, unit='cups', measurement_category='VOLUME'),
        ]
        substeps = [MixingSubstep(ingredient_ids=[1], description='Add flour')]

        engine, wm, recipe = _make_engine(bowl_volume=0.5, ingredients=ingredients, substeps=substeps)
        success, error = engine.run(recipe=recipe)

        assert success is False
        added = wm.query_facts(fact_title='ingredient_added')
        assert len(added) == 0


# ---------------------------------------------------------------------------
# Full recipe integration test
# ---------------------------------------------------------------------------

class TestFullRecipeSubsteps:
    def test_chocolate_chip_cookies_all_substeps(self):
        """All 8 cookie ingredients across 3 substeps fit in a 4-quart bowl."""
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
            MixingSubstep(ingredient_ids=[1, 7, 8], description='Mix in flour, baking soda, and salt'),
        ]

        engine, wm, recipe = _make_engine(bowl_volume=4, ingredients=ingredients, substeps=substeps)
        success, result = engine.run(recipe=recipe)

        assert success is True
        contents = wm.query_facts(fact_title='equipment_contents', equipment_name='BOWL', equipment_id=1)
        assert len(contents) == 8

        total = sum(c.attributes['volume_in_equipment_unit'] for c in contents)
        # Volume ingredients: 1 + 0.75 + 0.75 + 2.25 cups = 4.75 cups = 228 tsp
        # Plus: 2 tsp (vanilla) + 1 tsp (baking soda) + 1 tsp (salt) = 4 tsp
        # Eggs = 0 (WHOLE). Total = 232 tsp / 192 tsp-per-quart
        expected = (4.75 * 48 + 4) / 192
        assert total == pytest.approx(expected)

    def test_chocolate_chip_cookies_overflow_small_bowl(self):
        """Same recipe in a 0.5-quart bowl — should fail partway through substep 1."""
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
            MixingSubstep(ingredient_ids=[1, 7, 8], description='Mix in flour, baking soda, and salt'),
        ]

        engine, wm, recipe = _make_engine(bowl_volume=0.5, ingredients=ingredients, substeps=substeps)
        success, error = engine.run(recipe=recipe)

        assert success is False
        assert 'capacity_exceeded' in error
        # Butter (0.25) + white sugar (0.1875) = 0.4375; brown sugar (0.1875) overflows 0.5
        assert 'BROWN_SUGAR' in error
