class Recipe:
    """Represents a recipe"""
    def __init__(self, *, name, ingredients, required_equipment, steps):
        self.name = name
        self.ingredients = ingredients
        self.required_equipment = required_equipment
        self.steps = steps

    def __repr__(self):
        return f"Recipe('{self.name}', {self.ingredients})"