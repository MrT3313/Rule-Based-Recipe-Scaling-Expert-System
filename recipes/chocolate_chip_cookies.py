from classes.Recipe import Recipe
from classes.Ingredient import Ingredient

chocolate_chip_cookies_recipe = Recipe(
    name="chocolate_chip_cookies",
    ingredients=[
        Ingredient(name="all-purpose flour", amount=2.25, unit="cups"),
        Ingredient(name="butter",            amount=1,    unit="cups"),
        Ingredient(name="white sugar",       amount=0.75, unit="cups"),
        Ingredient(name="brown sugar",       amount=0.75, unit="cups"),
        Ingredient(name="eggs",              amount=2,    unit="whole"),
        Ingredient(name="vanilla extract",   amount=2,    unit="teaspoons"),
        Ingredient(name="baking soda",       amount=1,    unit="teaspoons"),
        Ingredient(name="salt",              amount=1,    unit="teaspoons"),
        Ingredient(name="chocolate chips",   amount=2,    unit="cups"),
    ]
)