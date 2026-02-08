# classes
from planning.classes.MixingStep import MixingStep
from planning.classes.CookStep import CookStep
from planning.classes.WaitStep import WaitStep
from planning.classes.TransferItem import TransferItem
from planning.classes.TransferEquipment import TransferEquipment
from planning.classes.MixingSubstep import MixingSubstep

def print_plan(plan):
    print("")
    print("=" * 70)
    print("EXECUTION PLAN")
    print("=" * 70)
    print("")

    for idx, step in enumerate(plan, start=1):
        _print_step(step, str(idx))
        print("")

    print("=" * 70)

def _step_label(step):
    if isinstance(step, MixingStep):
        return "MIX"
    elif isinstance(step, CookStep):
        return "COOK"
    elif isinstance(step, WaitStep):
        return "WAIT"
    elif isinstance(step, TransferItem):
        return "TRANSFER"
    elif isinstance(step, TransferEquipment):
        return "MOVE"
    return "STEP"

def _print_step(step, number, indent=0):
    prefix = "  " * indent
    label = _step_label(step)
    passive_marker = " (passive)" if step.is_passive else ""
    print(f"{prefix}{number}. [{label}] {step.description}{passive_marker}")

    if isinstance(step, MixingStep) and step.substeps:
        for sub_idx, substep in enumerate(step.substeps, start=1):
            sub_number = f"{number}.{sub_idx}"
            if isinstance(substep, MixingSubstep):
                print(f"{prefix}  {sub_number}. {substep.description}")
            else:
                _print_step(substep, sub_number, indent=indent + 1)
    elif step.substeps:
        for sub_idx, substep in enumerate(step.substeps, start=1):
            sub_number = f"{number}.{sub_idx}"
            _print_step(substep, sub_number, indent=indent + 1)