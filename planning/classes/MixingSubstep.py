class MixingSubstep:
    def __init__(self, *, ingredient_ids, description):
        self.ingredient_ids = ingredient_ids
        self.description = description

    def __repr__(self):
        return f"MixingSubstep({self.ingredient_ids}, '{self.description}')"
