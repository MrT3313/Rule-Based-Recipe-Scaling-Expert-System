from planning.classes.Step import Step

class PreparationStep(Step):
    def __init__(self, *, description, required_equipment=[], substeps=[], is_passive=False):
        super().__init__(description=description, required_equipment=required_equipment, substeps=substeps, is_passive=is_passive)

class PreheatStep(PreparationStep):
    def __init__(self, *, description, required_equipment=[], substeps=[], temperature, temperature_unit="fahrenheit", is_passive=True):
        super().__init__(description=description, required_equipment=required_equipment, substeps=substeps, is_passive=is_passive)

        self.temperature = temperature
        self.temperature_unit = temperature_unit