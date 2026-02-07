from planning.classes.WaitStep import WaitStep


class PreheatStep(WaitStep):
    def __init__(self, *, description, required_equipment=[], substeps=[],
                 temperature, temperature_unit="fahrenheit",
                 equipment_name='OVEN', equipment_id=None,
                 duration=None, duration_unit=None):
        super().__init__(
            description=description,
            required_equipment=required_equipment,
            substeps=substeps,
            equipment_name=equipment_name,
            equipment_id=equipment_id,
            duration=duration,
            duration_unit=duration_unit,
        )
        self.temperature = temperature
        self.temperature_unit = temperature_unit
