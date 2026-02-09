from planning.classes.Step import Step

class MixingStep(Step):
    step_type = 'MIXING'

    def __init__(self, *, description, required_equipment=[], substeps=[], is_passive=False):
        super().__init__(description=description, required_equipment=required_equipment, substeps=substeps, is_passive=is_passive)