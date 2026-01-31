class Recipe:
    """Represents a recipe"""
    def __init__(self, name, ingredients):
        self.name = name
        self.ingredients = ingredients

    def __repr__(self):
        return f"Recipe('{self.name}', {self.ingredients})"