from classes.Recipe import Recipe
from classes.Ingredient import Ingredient
from planning.classes.PreparationStep import PreheatStep
from planning.classes.MixingStep import MixingStep
from planning.classes.MixingSubstep import MixingSubstep
from planning.classes.TransferEquipment import TransferEquipment
from planning.classes.TransferItem import TransferItem
from planning.classes.CookStep import CookStep
from planning.classes.WaitStep import WaitStep

chocolate_chip_cookies_recipe = Recipe(
    name="chocolate_chip_cookies",
    ingredients=[
        Ingredient(id=1 ,name="all-purpose flour", amount=2.25, unit="cups", measurement_category="VOLUME"),
        Ingredient(id=2 ,name="butter",            amount=1,    unit="cups", measurement_category="VOLUME"),
        Ingredient(id=3 ,name="white sugar",       amount=0.75, unit="cups", measurement_category="VOLUME"),
        Ingredient(id=4 ,name="brown sugar",       amount=0.75, unit="cups", measurement_category="VOLUME"),
        Ingredient(id=5 ,name="eggs",              amount=2,    unit="whole", measurement_category="WHOLE"),
        Ingredient(id=6 ,name="vanilla extract",   amount=2,    unit="teaspoons", measurement_category="LIQUID"),
        Ingredient(id=7 ,name="baking soda",       amount=1,    unit="teaspoons", measurement_category="VOLUME"),
        Ingredient(id=8 ,name="salt",              amount=1,    unit="teaspoons", measurement_category="VOLUME"),
        Ingredient(id=9 ,name="chocolate chips",   amount=2,    unit="cups", measurement_category="VOLUME"),
    ],
    required_equipment=[
        {
            'equipment_name': 'OVEN',
            'required_count': 1,
        },
        {
            'equipment_name': 'BOWL',
            'required_count': 2,
        }
    ],
    steps=[
        PreheatStep(
            description="Preheat the oven to 350 degrees F",
            required_equipment=[
                {
                    'equipment_name': 'OVEN',
                    'required_count': 1,
                }
            ],
            temperature=350,
            temperature_unit="fahrenheit",
        ),
        MixingStep(
            description="Mix the ingredients",
            required_equipment=[
                {
                    'equipment_name': 'BOWL',
                    'required_count': 1,
                }
            ],
            substeps=[
                MixingSubstep(ingredient_ids=[2, 3, 4], description="Cream butter and sugars"),
                MixingSubstep(ingredient_ids=[5, 6], description="Beat in eggs and vanilla"),
                MixingSubstep(ingredient_ids=[1, 7, 8], description="Mix in flour, baking soda, and salt"),
            ]
        ),
        TransferItem(
            description="Scoop dough onto baking sheets",
            source_equipment_name='BOWL',
            target_equipment_name='BAKING_SHEET',
            scoop_size_amount=2,
            scoop_size_unit='TABLESPOONS',
            required_equipment=[],
        ),
        CookStep(
            description="Bake the cookies",
            substeps=[
                TransferEquipment(
                    description="Transfer baking sheets to oven racks",
                    source_equipment_name='BAKING_SHEET',
                    target_equipment_name='OVEN',
                    required_equipment=[],
                ),
                WaitStep(
                    description="Wait for cookies to bake",
                    equipment_name='OVEN',
                    duration=10,
                    duration_unit='minutes',
                ),
            ],
            required_equipment=[],
        ),
        TransferEquipment(
            description="Remove baking sheets from oven to countertop",
            source_equipment_name='OVEN',
            target_equipment_name='COUNTERTOP',
            required_equipment=[],
        ),
        TransferItem(
            description="Transfer cookies from baking sheets to cooling rack",
            source_equipment_name='BAKING_SHEET',
            target_equipment_name='COOLING_RACK',
            scoop_size_amount=1,
            scoop_size_unit='WHOLE',
            required_equipment=[],
        ),
    ],
)
