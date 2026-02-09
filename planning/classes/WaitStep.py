from planning.classes.Step import Step


class WaitStep(Step):

    def __init__(self, *, description, required_equipment=[], substeps=[],
                 equipment_name, duration=None, duration_unit=None, equipment_id=None):
        super().__init__(description=description, required_equipment=required_equipment, substeps=substeps, is_passive=True)

        self.equipment_name = equipment_name
        self.equipment_id = equipment_id
        self.duration = duration
        self.duration_unit = duration_unit
