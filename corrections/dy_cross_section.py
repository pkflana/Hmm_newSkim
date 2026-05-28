
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
    total_xs_from_bins = sum(bins)
    expected_total_xs = dysf_cfg['totalCrossSectionScaling']['numerator']
    expected_total_xs = xs_cfg[expected_total_xs]['crossSec']
    diff = abs(total_xs_from_bins - expected_total_xs)/expected_total_xs
    assert diff < 0.001

    return total_xs_scaling, selection_bins


def apply_dy_cross_section(df, weight_xs_name, xs_cfg, dysf_cfg):
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
    
    # Build the RDataFrame expression to assign new cross-section values
    xs_expr_list = []
    for entry, binned_xs in zip(dysf_cfg['bins'], selection_bins):
        xs = total_xs_scaling * binned_xs
        selection = entry['selection']
        sub_expr = f"if ({selection}) return {xs};"
        xs_expr_list.append(sub_expr)
    xs_expr_list.append('throw std::runtime_error("No bin matched in DY cross-sectioning bins.")')
    xs_expr = "\n".join(xs_expr_list)

    # Apply and return!
    df = df.Define(weight_xs_name, xs_expr)        
    return df
