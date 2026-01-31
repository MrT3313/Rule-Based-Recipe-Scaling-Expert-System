class Ingredient:
    def __init__(self, name, amount, unit):
        self.ingredient_name = name.upper().replace(" ", "_").replace("-", "_")
        self.amount = amount
        self.unit = unit.upper().replace(" ", "_").replace("-", "_")

    def __repr__(self):
        return f"Ingredient('{self.ingredient_name}', {self.amount}, {self.unit})"