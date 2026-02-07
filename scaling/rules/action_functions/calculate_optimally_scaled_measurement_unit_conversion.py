TOLERANCE = 0.0001
SMALL_UNITS = {'PINCH', 'DASH'}


def _find_smallest_unit(*, units_sorted):
    return next(
        (f for f in reversed(units_sorted) if f.attributes['unit'] not in SMALL_UNITS),
        units_sorted[-1]
    )


def is_quarter_increment(*, value):
    remainder = (value * 4) % 1
    return abs(remainder) < TOLERANCE or abs(remainder - 1) < TOLERANCE


def is_clean_value(*, value):
    return abs(value - round(value)) < TOLERANCE or is_quarter_increment(value=value)


def break_down_to_clean_units(*, base_amount, unit_conversions, measurement_type):
    units_sorted = sorted(
        [f for f in unit_conversions if f.attributes.get('measurement_type') == measurement_type],
        key=lambda f: f.attributes['to_base'],
        reverse=True
    )

    base_unit = units_sorted[0].attributes['base_unit']
    base_to_base = next(f.attributes['to_base'] for f in units_sorted
                        if f.attributes['unit'] == base_unit)

    for unit_fact in units_sorted:
        unit_name = unit_fact.attributes['unit']
        to_base_value = unit_fact.attributes['to_base']

        if unit_name in SMALL_UNITS:
            continue

        if to_base_value == base_to_base:
            continue

        amount_in_unit = base_amount / to_base_value

        if amount_in_unit >= 1.0 and is_clean_value(value=amount_in_unit):
            return [{'amount': round(amount_in_unit * 4) / 4, 'unit': unit_name}]

    components = []
    remaining = base_amount

    for unit_fact in units_sorted:
        unit_name = unit_fact.attributes['unit']
        to_base_value = unit_fact.attributes['to_base']

        if unit_name in SMALL_UNITS:
            continue

        if remaining >= to_base_value:
            whole_part = int(remaining / to_base_value)
            if whole_part > 0:
                components.append({'amount': float(whole_part), 'unit': unit_name})
                remaining = remaining - (whole_part * to_base_value)

        if remaining < TOLERANCE:
            break

    if remaining > TOLERANCE:
        smallest_unit = _find_smallest_unit(units_sorted=units_sorted)
        smallest_to_base = smallest_unit.attributes['to_base']
        final_amount = remaining / smallest_to_base

        if is_clean_value(value=final_amount):
            final_amount = round(final_amount * 4) / 4

        components.append({'amount': final_amount, 'unit': smallest_unit.attributes['unit']})

    if not components:
        smallest_unit = _find_smallest_unit(units_sorted=units_sorted)
        return [{'amount': 0.0, 'unit': smallest_unit.attributes['unit']}]

    all_clean = all(is_clean_value(value=c['amount']) for c in components)
    if len(components) > 1 and all_clean:
        return components
    elif len(components) == 1:
        return components
    else:
        total_in_base = sum(
            c['amount'] * next(f.attributes['to_base'] for f in units_sorted
                             if f.attributes['unit'] == c['unit'])
            for c in components
        )
        smallest_unit = _find_smallest_unit(units_sorted=units_sorted)
        simple_amount = total_in_base / smallest_unit.attributes['to_base']

        return [{'amount': simple_amount, 'unit': smallest_unit.attributes['unit']}]


def calculate_optimal_unit(*, bindings, wm, kb):
    scaled_amount = bindings['?scaled_amount']
    current_unit = bindings['?unit']
    current_to_base = bindings['?current_to_base']
    measurement_type = bindings['?measurement_category']

    if current_unit in SMALL_UNITS:
        return {
            **bindings,
            '?optimal_components': [{'amount': scaled_amount, 'unit': current_unit}],
            '?original_amount': scaled_amount
        }

    base_amount = scaled_amount * current_to_base

    all_facts = kb.reference_facts + wm.facts
    unit_conversions = [
        fact for fact in all_facts
        if fact.fact_title == 'unit_conversion'
    ]

    components = break_down_to_clean_units(base_amount=base_amount, unit_conversions=unit_conversions, measurement_type=measurement_type)

    return {
        **bindings,
        '?optimal_components': components,
        '?original_amount': scaled_amount
    }
