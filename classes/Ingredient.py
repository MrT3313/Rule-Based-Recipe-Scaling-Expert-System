class Ingredient:
    def __init__(self, *, name, amount, unit, measurement_category):
        self.ingredient_name = name.upper().replace(" ", "_").replace("-", "_")
        self.amount = amount
        self.unit = unit.upper().replace(" ", "_").replace("-", "_")
        self.measurement_category = measurement_category.upper().replace(" ", "_").replace("-", "_")

    def __repr__(self):
        return f"Ingredient('{self.ingredient_name}', {self.amount}, {self.unit}, {self.measurement_category})"