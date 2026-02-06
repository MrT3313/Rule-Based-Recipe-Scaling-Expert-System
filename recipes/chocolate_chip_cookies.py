from classes.Recipe import Recipe
from classes.Ingredient import Ingredient
from planning.classes.PreparationStep import PreheatStep

chocolate_chip_cookies_recipe = Recipe(
    name="chocolate_chip_cookies",
    ingredients=[
        Ingredient(name="all-purpose flour", amount=2.25, unit="cups", measurement_category="VOLUME"),
        Ingredient(name="butter",            amount=1,    unit="cups", measurement_category="VOLUME"),
        Ingredient(name="white sugar",       amount=0.75, unit="cups", measurement_category="VOLUME"),
        Ingredient(name="brown sugar",       amount=0.75, unit="cups", measurement_category="VOLUME"),
        Ingredient(name="eggs",              amount=2,    unit="whole", measurement_category="WHOLE"),
        Ingredient(name="vanilla extract",   amount=2,    unit="teaspoons", measurement_category="LIQUID"),
        Ingredient(name="baking soda",       amount=1,    unit="teaspoons", measurement_category="VOLUME"),
        Ingredient(name="salt",              amount=1,    unit="teaspoons", measurement_category="VOLUME"),
        Ingredient(name="chocolate chips",   amount=2,    unit="cups", measurement_category="VOLUME"),
    ],
    required_equipment=[
        {
            'equipment_name': 'OVEN',
            'required_count': 1,
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
        )
    ],
)