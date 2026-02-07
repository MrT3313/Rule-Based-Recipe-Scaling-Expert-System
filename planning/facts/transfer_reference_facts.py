from classes.Fact import Fact


def get_transfer_reference_facts():
    facts = []

    facts.append(Fact(
        fact_title='baking_sheet_dimensions',
        width=13,
        length=18,
        area=234,
        unit='inches',
    ))

    facts.append(Fact(
        fact_title='cookie_specifications',
        diameter=2,
        spacing=2,
        scoop_amount=2,
        scoop_unit='TABLESPOONS',
        unit='inches',
    ))

    facts.append(Fact(
        fact_title='baking_sheet_margin',
        edge_margin=1,
        unit='inches',
    ))

    return facts
