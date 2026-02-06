def _normalize(text):
    return text.upper().replace(" ", "_").replace("-", "_")


class Ingredient:
    def __init__(self, *, id, name, amount, unit, measurement_category):
        self.id = id
        self.ingredient_name = _normalize(name)
        self.amount = amount
        self.unit = _normalize(unit)
        self.measurement_category = _normalize(measurement_category)

    def __repr__(self):
        return f"Ingredient('{self.ingredient_name}', {self.amount}, {self.unit}, {self.measurement_category})"