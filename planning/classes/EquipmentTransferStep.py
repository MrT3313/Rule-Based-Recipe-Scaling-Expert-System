from planning.classes.Step import Step


class EquipmentTransferStep(Step):
    def __init__(self, *, description, required_equipment=[], substeps=[], is_passive=False,
                 source_equipment_name, target_equipment_name):
        super().__init__(description=description, required_equipment=required_equipment, substeps=substeps, is_passive=is_passive)

        self.source_equipment_name = source_equipment_name
        self.target_equipment_name = target_equipment_name
