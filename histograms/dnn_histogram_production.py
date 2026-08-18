"""DNN-specific dataframe transformations used while producing histograms.

Keep mass remapping and DNN reevaluation here: the generic histogram maker
should only decide which dataframe and output column to book.
"""

from __future__ import annotations


SIDEBAND_PAYLOADS = {
    "Z_sideband": "DNNZSidebandMassShift",
    "H_sideband": "DNNHSidebandMassShift",
}

DNN_OUTPUT_VARIABLE = "DNN_NNOutput"


def needs_sideband_mass_shift(mass_region, variable):
    """Return whether *variable* needs a sideband-specific DNN evaluation."""
    return mass_region in SIDEBAND_PAYLOADS and variable == DNN_OUTPUT_VARIABLE


def sideband_mass_expression(mass_region): 
    if mass_region == "Z_sideband":
        return "static_cast<float>(115.0 + 0.5 * (m_mumu - 70.0))"
    if mass_region == "H_sideband":
        return (
            "static_cast<float>(m_mumu < 115.0 ? "
            "115.0 + (m_mumu - 110.0) : 120.0 + (m_mumu - 135.0))"
        )
    raise ValueError(f"Unsupported DNN mass-shift region: {mass_region}")


def shifted_output_column(mass_region):
    """Name of the DNN output produced for a shifted sideband."""
    try:
        return f"{SIDEBAND_PAYLOADS[mass_region]}_NNOutput"
    except KeyError as error:
        raise ValueError(
            f"Unsupported DNN mass-shift region: {mass_region}"
        ) from error


def apply_sideband_mass_shifted_dnn(
    rdf, mass_region, *, btag_algo, era, model_set
):
    """Remap ``m_mumu`` and evaluate only the sideband-specific DNN payload."""
    from common.dnn_application import ApplyDNN

    shifted_rdf = rdf.Redefine("m_mumu", sideband_mass_expression(mass_region))
    return ApplyDNN(
        shifted_rdf,
        [SIDEBAND_PAYLOADS[mass_region]],
        btag_algo=btag_algo,
        era=era,
        model_set=model_set,
    )
