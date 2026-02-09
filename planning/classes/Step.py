class Step:
    def __init__(self, *, description, required_equipment=[], substeps=[], is_passive=False):
        self.description = description
        self.required_equipment = required_equipment
        self.substeps = substeps
        self.is_passive = is_passive
