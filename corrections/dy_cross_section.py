
def dy_cross_section_calc(xs_cfg, dysf_cfg):
    """
    Calculates the new DY cross section factors for using multiple DY samples.
    Args:
    - xs_cfg expected to crossSections13p6TeV.yaml loaded as dict.
    - dysf_cfg expected to be dy_cross_section_stitching.yaml loaded as dict.
    Returns:
    - The overall scale factor
    - The selection-by-selection factors for different binnings
    """
    # Calculate the total cross-section scaling factor
    numer = dysf_cfg['totalCrossSectionScaling']['numerator']
    denom = dysf_cfg['totalCrossSectionScaling']['denominator']
    numer = xs_cfg[numer]['crossSec']
    denom = xs_cfg[denom]['crossSec']
    if isinstance(numer, str):
        numer = eval(numer)
    if isinstance(denom, str):
        denom = eval(denom)
    total_xs_scaling = numer/denom

    # Calculate the selection by selection cross-sections
    selection_bins = []
    for bin in dysf_cfg['bins']:
        subtotal = 0
        for entry in bin['crossSection']['add']:
            subtotal += xs_cfg[entry]['crossSec']
        for entry in bin['crossSection']['subtract']:
            subtotal -= xs_cfg[entry]['crossSec']
        selection_bins.append(subtotal)

    # Check the factor
    total_xs_from_bins = sum(selection_bins)
    expected_total_xs = dysf_cfg['totalCrossSectionScaling']['numerator']
    expected_total_xs = xs_cfg[expected_total_xs]['crossSec']
    diff = abs(total_xs_from_bins - expected_total_xs)/expected_total_xs
    # assert diff < 0.001

    return total_xs_scaling, selection_bins


def apply_dy_cross_section(df, weight_xs_name, xs_cfg, dysf_cfg, json_dict):
    """
    Redefines the weight_xs branch for DY samples.
    Args:
    - df is the working RDataFrame
    - xs_cfg expected to crossSections13p6TeV.yaml loaded as dict.
    - dysf_cfg_path is the .yaml file containing the DY stitching configuration
    Returns:
    - The updated RDataFrame
    """
    # Get needed values from dy_cross_section_calc.
    total_xs_scaling, selection_bins = dy_cross_section_calc(xs_cfg, dysf_cfg)
    print(total_xs_scaling)
    # Build the RDataFrame expression to assign new cross-section values
    xs_expr_list = []
    for entry, binned_xs in zip(dysf_cfg['bins'], selection_bins):
        ### sum of gen weigths
        if 'gen' not in json_dict_to_store.keys():
            json_dict_to_store['gen'] = {}
        if entry['name'] not in json_dict['gen'].keys():
            json_dict['gen'][entry['name']] = {}
        json_dict['gen'][entry['name']]['selection'] = entry['selection']
        json_dict['gen'][entry['name']]['value'] = df.Filter(entry['selection']).Sum("genWeight")
        ### sum of pu weights
        
        if entry['name'] not in json_dict['pu'].keys():
            json_dict['pu'][entry['name']] = {}
        json_dict['pu'][entry['name']]['selection'] = entry['selection']
        json_dict['pu'][entry['name']]['value'] = df.Filter(entry['selection']).Sum("weight_pu")
        for scale in ['up','down']:
            if f"weight_pu_{scale}" not in df.GetColumnNames(): continue
            if entry['name'] not in json_dict[f"pu_{scale}"].keys():
                json_dict[f"pu_{scale}"][entry['name']] = {}
            json_dict[f"pu_{scale}"][entry['name']]['selection'] = entry['selection']
            json_dict[f"pu_{scale}"][entry['name']]['value'] = df.Filter(entry['selection']).Sum(f"weight_pu_{scale}")

        xs = total_xs_scaling * binned_xs
        selection = entry['selection']
        sub_expr = f"if ({selection}) return {xs};"
        xs_expr_list.append(sub_expr)
    xs_expr_list.append('throw std::runtime_error("No bin matched in DY cross-sectioning bins.")')
    xs_expr = "\n".join(xs_expr_list)

    # Apply and return!
    df = df.Define(weight_xs_name, xs_expr)


    return df,json_dict
