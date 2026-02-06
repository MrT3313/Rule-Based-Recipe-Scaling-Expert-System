from planning.classes.Step import Step


class CleaningStep(Step):
    def __init__(self, *, equipment_name, equipment_id):
        self.equipment_name = equipment_name
        self.equipment_id = equipment_id
        super().__init__(
            description=f"Clean {equipment_name} #{equipment_id}",
        )
