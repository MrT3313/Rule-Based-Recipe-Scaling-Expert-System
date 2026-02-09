from planning.classes.TransferStep import TransferStep


class TransferEquipment(TransferStep):
    """Transfer one piece of equipment into/onto another (e.g., sheet -> oven, oven -> countertop)."""
    step_type = 'TRANSFER_EQUIPMENT'
