from planning.classes.TransferStep import TransferStep


class TransferItem(TransferStep):
    """Transfer items between equipment (e.g., scoop dough onto sheet, cookies to cooling rack)."""
    def __init__(self, *, description, required_equipment=[], substeps=[], is_passive=False,
                 source_equipment_name, target_equipment_name,
                 scoop_size_amount, scoop_size_unit):
        super().__init__(description=description, required_equipment=required_equipment, substeps=substeps, is_passive=is_passive,
                         source_equipment_name=source_equipment_name, target_equipment_name=target_equipment_name)

        self.scoop_size_amount = scoop_size_amount
        self.scoop_size_unit = scoop_size_unit
