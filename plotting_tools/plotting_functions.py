"""Reusable ROOT-to-matplotlib plotting functions."""

import os

os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join("/tmp", os.environ.get("USER", "user"), "matplotlib"),
)

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import mplhep as hep
import numpy as np
import ROOT

from common.jet_component_splitting import pu_hard_component_style
from common.rdf_utilities import findBinEntry

plt.style.use(hep.style.CMS)


def normalize_sample_name(name):
    return os.path.splitext(os.path.basename(name))[0]


def get_total_hist_integral(root_hist):
    return root_hist.Integral(0, root_hist.GetNbinsX() + 1)


def parse_sample_targets(target_spec):
    if target_spec is None:
        return []

    if isinstance(target_spec, (list, tuple, set)):
        raw_items = target_spec
    else:
        raw_items = str(target_spec).replace(",", " ").split()

    return [item.strip() for item in raw_items if item and item.strip()]


def starts_with_dy(candidate):
    return normalize_sample_name(candidate).lower().startswith("dy")


def resolve_background_targets(target_spec, ratio_candidates, mc_keys):
    targets = []

    for target in parse_sample_targets(target_spec):
        target_key = resolve_ratio_reference(target, ratio_candidates)

        if target_key is not None and target_key in mc_keys and target_key not in targets:
            targets.append(target_key)

    requested_targets = parse_sample_targets(target_spec)

    if (
        not targets
        and len(requested_targets) == 1
        and normalize_sample_name(requested_targets[0]).lower() == "dy"
    ):
        for sample_key in mc_keys:
            candidate = ratio_candidates[sample_key]
            if starts_with_dy(sample_key) or starts_with_dy(candidate.get("name", "")):
                targets.append(sample_key)

    return targets


def get_bins_and_content(root_hist, want_overflow=False, divide_by_bin_width=False):
    """
    Estrae bin edges, contenuti ed errori da un TH1.
    Se richiesto, somma underflow/overflow al primo/ultimo bin visibile.
    """
    n_bins = root_hist.GetNbinsX()

    edges = np.array(
        [root_hist.GetBinLowEdge(i) for i in range(1, n_bins + 2)],
        dtype=float,
    )

    content = np.array(
        [root_hist.GetBinContent(i) for i in range(1, n_bins + 1)],
        dtype=float,
    )

    errors = np.array(
        [root_hist.GetBinError(i) for i in range(1, n_bins + 1)],
        dtype=float,
    )

    if want_overflow and n_bins > 0:
        content[-1] += root_hist.GetBinContent(n_bins + 1)
        errors[-1] = np.sqrt(
            errors[-1] ** 2 + root_hist.GetBinError(n_bins + 1) ** 2
        )

        content[0] += root_hist.GetBinContent(0)
        errors[0] = np.sqrt(
            errors[0] ** 2 + root_hist.GetBinError(0) ** 2
        )

    if divide_by_bin_width:
        widths = np.diff(edges)

        content = np.divide(
            content,
            widths,
            out=np.zeros_like(content),
            where=widths != 0,
        )

        errors = np.divide(
            errors,
            widths,
            out=np.zeros_like(errors),
            where=widths != 0,
        )

    return edges, content, errors


def trim_empty_edge_bins(
    bin_edges,
    value_arrays,
    min_empty_edge_bins=2,
    keep_edge_bins=0,
):
    n_bins = len(bin_edges) - 1

    if n_bins <= 0:
        return bin_edges, value_arrays

    occupied = np.zeros(n_bins, dtype=bool)

    for values in value_arrays:
        if values is None:
            continue

        arr = np.asarray(values, dtype=float)

        if len(arr) != n_bins:
            continue

        occupied |= np.isfinite(arr) & (np.abs(arr) > 0.0)

    if not np.any(occupied):
        return bin_edges, value_arrays

    occupied_bins = np.where(occupied)[0]
    first_nonempty = int(occupied_bins[0])
    last_nonempty = int(occupied_bins[-1])

    leading_empty = first_nonempty
    trailing_empty = n_bins - last_nonempty - 1

    trim_first = 0
    trim_last = n_bins - 1

    if leading_empty >= min_empty_edge_bins:
        trim_first = max(first_nonempty - keep_edge_bins, 0)

    if trailing_empty >= min_empty_edge_bins:
        trim_last = min(last_nonempty + keep_edge_bins, n_bins - 1)

    if trim_first == 0 and trim_last == n_bins - 1:
        return bin_edges, value_arrays

    trimmed_edges = bin_edges[trim_first:trim_last + 2]
    trimmed_arrays = []

    for values in value_arrays:
        if values is None:
            trimmed_arrays.append(None)
            continue

        arr = np.asarray(values)

        if len(arr) != n_bins:
            trimmed_arrays.append(values)
        else:
            trimmed_arrays.append(arr[trim_first:trim_last + 1])

    return trimmed_edges, trimmed_arrays


def get_blind_range_for_category(hist_cfg, category):
    """
    Supporta:

      blind_range: [115, 130]

    oppure:

      blind_range:
        Signal_Fit: [115, 130]
    """
    blind_range = hist_cfg.get("blind_range", None)

    if blind_range is None:
        return None

    if isinstance(blind_range, (list, tuple)):
        if len(blind_range) != 2:
            print(f"  [WARNING] blind_range malformato: {blind_range}")
            return None

        return [float(blind_range[0]), float(blind_range[1])]

    if isinstance(blind_range, dict):
        category_range = blind_range.get(category, None)

        if category_range is None:
            return None

        if not isinstance(category_range, (list, tuple)) or len(category_range) != 2:
            print(
                f"  [WARNING] blind_range malformato "
                f"per categoria {category}: {category_range}"
            )
            return None

        return [float(category_range[0]), float(category_range[1])]

    print(f"  [WARNING] Tipo non supportato per blind_range: {type(blind_range)}")

    return None


def apply_blind_range(edges, content, errors, blind_range=None):
    """
    Applica il blinding ai dati.
    Usa NaN per non disegnare quei punti.
    """
    if blind_range is None:
        return content, errors, None

    xmin, xmax = blind_range

    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    blind_mask = (bin_centers >= xmin) & (bin_centers <= xmax)

    if not np.any(blind_mask):
        return content, errors, blind_mask

    blinded_content = content.copy()
    blinded_errors = errors.copy()

    blinded_content[blind_mask] = np.nan
    blinded_errors[blind_mask] = np.nan

    return blinded_content, blinded_errors, blind_mask


def safe_nanmax(arrays, default=1.0):
    """
    Massimo robusto ignorando NaN e inf.
    """
    finite_values = []

    for arr in arrays:
        if arr is None:
            continue

        arr = np.asarray(arr, dtype=float)
        finite = arr[np.isfinite(arr)]

        if len(finite):
            finite_values.append(np.max(finite))

    if not finite_values:
        return default

    return max(finite_values)


def safe_nanmin(arrays, default=0.0):
    """
    Minimo robusto ignorando NaN e inf.
    """
    finite_values = []

    for arr in arrays:
        if arr is None:
            continue

        arr = np.asarray(arr, dtype=float)
        finite = arr[np.isfinite(arr)]

        if len(finite):
            finite_values.append(np.min(finite))

    if not finite_values:
        return default

    return min(finite_values)


def resolve_ratio_reference(ratio_reference, ratio_candidates):
    if ratio_reference is None:
        return None

    normalized_reference = normalize_sample_name(ratio_reference)

    for key, candidate in ratio_candidates.items():
        aliases = {
            key,
            normalize_sample_name(key),
            candidate.get("name", key),
            normalize_sample_name(candidate.get("name", key)),
        }
        for alias in candidate.get("aliases", []):
            aliases.add(alias)
            aliases.add(normalize_sample_name(alias))

        if ratio_reference in aliases or normalized_reference in aliases:
            return key

    return None


def set_ratio_axis_range(
    rax,
    ratio_arrays,
    ratio_unc_low=None,
    ratio_unc_high=None,
    log_scale=False,
):
    if log_scale:
        arrays = list(ratio_arrays)
        if ratio_unc_low is not None:
            arrays.append(ratio_unc_low)
        if ratio_unc_high is not None:
            arrays.append(ratio_unc_high)
        positive = [
            values[np.isfinite(values) & (values > 0)]
            for values in (np.asarray(array) for array in arrays)
        ]
        positive = [values for values in positive if values.size]
        if positive:
            ymin = max(min(float(np.min(values)) for values in positive) / 1.25, 1e-3)
            ymax = max(max(float(np.max(values)) for values in positive) * 1.25, 1.1)
        else:
            ymin, ymax = 0.1, 10.0
        rax.set_yscale("log")
        rax.set_ylim(ymin, ymax)
        rax.yaxis.set_major_locator(mticker.LogLocator(base=10.0))
        rax.yaxis.set_minor_locator(
            mticker.LogLocator(base=10.0, subs=np.arange(2, 10) * 0.1)
        )
        rax.grid(axis="y", which="both", linestyle=":", linewidth=0.6, alpha=0.5)
        return

    ymin = 0
    ymax = 2

    rax.set_ylim(ymin, ymax)

    ticks = np.round(np.arange(ymin, ymax + 0.001, 0.5), 1)
    rax.yaxis.set_major_locator(mticker.FixedLocator(ticks))
    rax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    rax.grid(axis="y", which="major", linestyle=":", linewidth=0.6, alpha=0.5)


# =============================================================================
# Systematic uncertainty bands for the Data/MC ratio panel
#
# Histogram naming convention (written by hist_maker.py):
#   {variable}_CMS_{fragment}_{era}Up
#   {variable}_CMS_{fragment}_{era}Down
#
# Example: m_mumu_CMS_res_j_2022Up
#
# SYST_GROUPS maps each display group to the list of CMS nuisance name
# fragments that belong to it.  Fragments that share a group are combined
# by taking the envelope (most extreme deviation from 1.0) across all
# fragments in each bin before the group band is drawn.
#
# For each group the band is drawn as two step lines:
#   MC_shifted_up   / MC_nominal  (upper line)
#   MC_shifted_down / MC_nominal  (lower line)
# where MC_shifted is the sum over ALL background samples of the shifted
# histogram, and MC_nominal is the sum of the nominal histograms.
# =============================================================================

# Entries are full nuisance names; era-dependent names use ``{era}``.
# Each group gets a distinct, colorblind-friendly color.
SYST_GROUPS = {
    "Jet Res": (["CMS_res_j_{era}"], "#0072B2"),
    "Jet Scale": (["CMS_scale_j_{era}"], "#E69F00"),
    "Muon Eff.": (
        [
            "CMS_eff_m_iso_{era}",
            "CMS_eff_m_trigger_{era}",
            "CMS_eff_m_id_{era}",
        ],
        "#009E73",
    ),
    "Muon Res": (["CMS_res_m_{era}"], "#D55E00"),
    "Muon Scale": (["CMS_scale_m_{era}"], "#CC79A7"),
    "EWKZ PS": (["CMS_hmm_EWKZ_partonShower_{era}"], "#8C564B"),
    "QCD Scale": (
        [
            "QCD_fac_scale_V",
            "QCD_fac_scale_VH",
            "QCD_fac_scale_VV",
            "QCD_fac_scale_VVV",
            "QCD_fac_scale_qqH",
            "QCD_fac_scale_ttbar",
            "QCD_ren_scale_V",
            "QCD_ren_scale_VH",
            "QCD_ren_scale_VV",
            "QCD_ren_scale_VVV",
            "QCD_ren_scale_qqH",
            "QCD_ren_scale_ttbar",
        ],
        "#F0E442",
    ),
    "PDF": (
        [
            "pdf_Higgs_VH",
            "pdf_Higgs_qqH",
            "pdf_gg",
            "pdf_gq",
            "pdf_qqbar",
        ],
        "#56B4E9",
    ),
}


def _hist_content(th1, bin_edges):
    """
    Extract bin contents from th1 for exactly the bins whose
    low edges match the (possibly trimmed) bin_edges array.
    Falls back to positional slicing if edges don't match.
    """
    n_bins = len(bin_edges) - 1
    out = np.zeros(n_bins, dtype=float)
    
    for i, (lo, hi) in enumerate(zip(bin_edges[:-1], bin_edges[1:])):
        # find the ROOT bin whose low edge matches
        mid = 0.5 * (lo + hi)
        root_bin = th1.FindBin(mid)
        out[i] = th1.GetBinContent(root_bin)
    
    return out


def build_syst_ratio_bands(
    samples_dict,
    category,
    variable,
    mc_keys,
    bin_edges,
    era,
    systematic_groups=None,
):
    n_bins=len(bin_edges) - 1
    """
    Compute per-group systematic ratio bands for the Data/MC ratio panel.

    For each systematic group defined in SYST_GROUPS:
      1. For every nuisance fragment in the group, look for histogram keys
             {variable}_CMS_{fragment}_{era}Up
             {variable}_CMS_{fragment}_{era}Down
         inside each MC background sample's hists dict.
      2. Sum the shifted bin contents across ALL MC background samples
         to get total MC_up and MC_down per nuisance.
      3. Compute ratio_up = MC_up / MC_nominal and ratio_dn = MC_dn / MC_nominal.
      4. When a group has multiple fragments (e.g. Muon combines eff_m_iso,
         eff_m_trigger, eff_m_id) take the envelope: the deviation furthest
         from 1.0 wins in each bin.

    Parameters
    ----------
    samples_dict : dict
        Full samples dict as built by hist_plotter.py after apply_plot_groups().
    category : str
        Region key, e.g. "Z_sideband_VBF".
    variable : str
        Nominal histogram name, e.g. "m_mumu".
    mc_keys : list of str
        Background sample keys to sum over (already sorted by yield).
    n_bins : int
        Number of visible bins (after any trimming).
    era : str
        Era string, e.g. "Run3_2022". "Run3_" is stripped to give "2022".

    Returns
    -------
    dict : {group_label: (ratio_up, ratio_dn, color)}
        ratio_up and ratio_dn are np.ndarray of shape (n_bins,).
        Values above/below 1.0 show upward/downward MC shifts.
    """
    era_short = era.removeprefix("Run3_")

    # ------------------------------------------------------------------
    # Nominal MC total — sum nominal histograms across all MC samples
    # ------------------------------------------------------------------
    nominal_total = np.zeros(len(bin_edges) - 1, dtype=float)
    for key in mc_keys:
        h = samples_dict[key]["hists"].get(category, {}).get(variable)
        if h is not None:
            nominal_total += _hist_content(h, bin_edges)

    result = {}

    requested_groups = set(systematic_groups or SYST_GROUPS)
    unknown_groups = requested_groups.difference(SYST_GROUPS)
    if unknown_groups:
        available = ", ".join(SYST_GROUPS)
        unknown = ", ".join(sorted(unknown_groups))
        raise ValueError(
            f"Unknown systematic group(s): {unknown}. Available groups: {available}"
        )

    for group_label, (fragments, color) in SYST_GROUPS.items():
        if group_label not in requested_groups:
            continue
        # Envelope accumulators — start at nominal (ratio = 1.0)
        group_ratio_up = np.ones(len(bin_edges) - 1, dtype=float)
        group_ratio_dn = np.ones(len(bin_edges) - 1, dtype=float)
        group_found = False

        for fragment in fragments:
            if era == "Run3_2022_25" and "{era}" in fragment:
                delta_up2 = np.zeros(len(bin_edges) - 1, dtype=float)
                delta_dn2 = np.zeros(len(bin_edges) - 1, dtype=float)
                combined_found = False
                for subera in ("2022", "2022EE", "2023", "2023BPix", "2024", "2025"):
                    era_delta_up = np.zeros(len(bin_edges) - 1, dtype=float)
                    era_delta_dn = np.zeros(len(bin_edges) - 1, dtype=float)
                    nuisance_name = fragment.format(era=subera)
                    up_key = f"{variable}_{nuisance_name}Up"
                    dn_key = f"{variable}_{nuisance_name}Down"
                    era_found = False
                    for key in mc_keys:
                        for merged_path in samples_dict[key].get("input", "").split(","):
                            merged_path = merged_path.strip()
                            if not merged_path:
                                continue
                            source_path = os.path.join(
                                os.path.dirname(os.path.dirname(merged_path)),
                                f"Run3_{subera}",
                                os.path.basename(merged_path),
                            )
                            if not os.path.isfile(source_path):
                                continue
                            try:
                                source_file = ROOT.TFile.Open(source_path)
                            except OSError:
                                print(
                                    f"  [WARNING] Cannot open optional "
                                    f"era source: {source_path}"
                                )
                                continue
                            if not source_file or source_file.IsZombie():
                                continue
                            source_dir = source_file.Get(category)
                            h_nom = source_dir.Get(variable) if source_dir else None
                            h_up = source_dir.Get(up_key) if source_dir else None
                            h_dn = source_dir.Get(dn_key) if source_dir else None
                            if h_nom and h_up and h_dn:
                                nom = _hist_content(h_nom, bin_edges)
                                era_delta_up += _hist_content(h_up, bin_edges) - nom
                                era_delta_dn += _hist_content(h_dn, bin_edges) - nom
                                era_found = True
                            source_file.Close()
                    if era_found:
                        delta_up2 += era_delta_up ** 2
                        delta_dn2 += era_delta_dn ** 2
                        combined_found = True

                if combined_found:
                    ratio_up = np.divide(
                        nominal_total + np.sqrt(delta_up2),
                        nominal_total,
                        out=np.ones_like(nominal_total),
                        where=nominal_total > 0,
                    )
                    ratio_dn = np.divide(
                        nominal_total - np.sqrt(delta_dn2),
                        nominal_total,
                        out=np.ones_like(nominal_total),
                        where=nominal_total > 0,
                    )
                    group_found = True
                    group_ratio_up = np.where(
                        np.abs(ratio_up - 1.0) > np.abs(group_ratio_up - 1.0),
                        ratio_up,
                        group_ratio_up,
                    )
                    group_ratio_dn = np.where(
                        np.abs(ratio_dn - 1.0) > np.abs(group_ratio_dn - 1.0),
                        ratio_dn,
                        group_ratio_dn,
                    )
                    print(
                        f"  [SYST] {group_label}: combined decorrelated "
                        "2022--2025 variations in quadrature"
                    )
                continue

            nuisance_name = fragment.format(era=era_short)
            up_key = f"{variable}_{nuisance_name}Up"
            dn_key = f"{variable}_{nuisance_name}Down"

            mc_up = np.zeros(len(bin_edges) - 1, dtype=float)
            mc_dn = np.zeros(len(bin_edges) - 1, dtype=float)
            frag_found = False

            for key in mc_keys:
                hists = samples_dict[key]["hists"].get(category, {})
                h_nom = hists.get(variable)
                h_up  = hists.get(up_key)
                h_dn  = hists.get(dn_key)

                print(f"  [DEBUG] {key}: nom={h_nom is not None}, up={h_up is not None}, dn={h_dn is not None}")

                if h_nom is None:
                    continue

                nom = _hist_content(h_nom, bin_edges)

                if h_up is not None and h_dn is not None:
                    mc_up += _hist_content(h_up, bin_edges)
                    mc_dn += _hist_content(h_dn, bin_edges)
                    frag_found = True
                else:
                    # Sample unaffected by this fragment — contributes
                    # nominally so its bins cancel in the ratio
                    mc_up += nom
                    mc_dn += nom

            if not frag_found:
                continue

            group_found = True

            ratio_up = np.where(nominal_total > 0, mc_up / nominal_total, 1.0)
            ratio_dn = np.where(nominal_total > 0, mc_dn / nominal_total, 1.0)

            print(f"    [{fragment}] ratio_up min/max: {np.nanmin(ratio_up):.3f}/{np.nanmax(ratio_up):.3f}  "
                f"at bins {np.nanargmin(ratio_up)}/{np.nanargmax(ratio_up)}")
            print(f"    nominal_total at those bins: {nominal_total[np.nanargmin(ratio_up)]:.4g} / "
                f"{nominal_total[np.nanargmax(ratio_up)]:.4g}")

            # Envelope: keep whichever fragment deviates most from 1.0
            group_ratio_up = np.where(
                np.abs(ratio_up - 1.0) > np.abs(group_ratio_up - 1.0),
                ratio_up,
                group_ratio_up,
            )
            group_ratio_dn = np.where(
                np.abs(ratio_dn - 1.0) > np.abs(group_ratio_dn - 1.0),
                ratio_dn,
                group_ratio_dn,
            )

        if group_found:
            empty_nominal = nominal_total <= 0
            group_ratio_up = np.where(empty_nominal, np.nan, group_ratio_up)
            group_ratio_dn = np.where(empty_nominal, np.nan, group_ratio_dn)
            result[group_label] = (group_ratio_up, group_ratio_dn, color)
            print(
                f"  [SYST] {group_label}: "
                f"mean |up-1|={np.nanmean(np.abs(group_ratio_up - 1.0)):.4f}  "
                f"mean |dn-1|={np.nanmean(np.abs(group_ratio_dn - 1.0)):.4f}"
            )
        else:
            print(f"  [SYST] {group_label}: no histograms found, skipping")

    return result


# =========================================================
# Plotting
# =========================================================

def make_stacked_plot(
    samples_dict,
    config_page,
    category,
    variable,
    out_name,
    want_data=True,
    do_stack=True,
    fill_hists=True,
    ratio_reference=None,
    normalize_dy_to_data=False,
    normalize_mc_to_data=False,
    dy_normalization_sample="DY",
    era="",
    dy_composition=False,
    show_systematics=False,
    systematic_groups=None,
    overlay_systematic=False,
    log_uncertainties=False,
    include_total_systematics=False,
    show_mc_stat_uncertainty=True,
):
    """
    Genera uno stacked plot con:
      - background in stack
      - signal overlay
      - data opzionale
      - ratio Data/MC opzionale
      - blinding sui dati
      - per-systematic step-line bands in the ratio panel
    """
    mc_vals = []
    mc_colors = []
    mc_labels = []
    mc_integrals = []
    mc_errs = []
    mc_keys = []

    sgn_vals = []
    sgn_errs = []
    sgn_integrals = []
    sgn_colors = []
    sgn_labels = []
    sgn_keys = []

    ratio_candidates = {}
    data_key = None

    data_vals = None
    data_errs = None
    data_integral_total = None
    data_label_legend = None

    bin_edges = None

    hist_entry = findBinEntry(config_page, variable)
    hist_cfg = config_page.get(hist_entry, {}) if hist_entry is not None else {}

    divide_by_bin_width = hist_cfg.get("divide_by_bin_width", False)
    include_overflow = False # hist_cfg.get("include_overflow", False)
    auto_trim_empty_edges = hist_cfg.get(
        "auto_trim_empty_edges",
        config_page.get("auto_trim_empty_edges", False),
    )
    auto_trim_min_empty_edge_bins = hist_cfg.get(
        "auto_trim_min_empty_edge_bins",
        config_page.get("auto_trim_min_empty_edge_bins", 2),
    )
    auto_trim_keep_edge_bins = hist_cfg.get(
        "auto_trim_keep_edge_bins",
        config_page.get("auto_trim_keep_edge_bins", 0),
    )
    blind_range = get_blind_range_for_category(hist_cfg, category)

    if blind_range is not None:
        print(f"  [BLIND] {variable} in category {category}: range {blind_range}")

    # =====================================================
    # Split samples by type
    # =====================================================

    for sample_id, sample_info in samples_dict.items():

        if category not in sample_info["hists"]:
            continue

        if variable not in sample_info["hists"][category]:
            continue

        root_hist = sample_info["hists"][category][variable]

        edges, content, errors = get_bins_and_content(
            root_hist,
            want_overflow=include_overflow,
            divide_by_bin_width=divide_by_bin_width,
        )

        if bin_edges is None:
            bin_edges = edges

        hist_integral = get_total_hist_integral(root_hist)
        sample_label = sample_info.get("name", sample_id)

        if sample_info["is_data"]:

            if not want_data:
                continue

            content, errors, blind_mask = apply_blind_range(
                edges,
                content,
                errors,
                blind_range=blind_range,
            )

            data_vals = content
            data_errs = errors
            data_integral_total = hist_integral
            data_key = sample_id

            ratio_candidates[sample_id] = {
                "name": sample_label,
                "values": content,
                "errors": errors,
                "color": "black",
                "is_data": True,
                "is_signal": False,
                "aliases": sample_info.get("aliases", []),
            }

            data_label_base = sample_label

            if blind_range is not None and blind_mask is not None and np.any(blind_mask):
                data_label_legend = f"{data_label_base} [blinded]"
            else:
                data_label_legend = f"{data_label_base} [{hist_integral:.2f}]"

        elif sample_info["is_signal"]:

            sgn_vals.append(content)
            sgn_errs.append(errors)
            sgn_integrals.append(hist_integral)
            sgn_colors.append(sample_info["color"])
            sgn_labels.append(f"{sample_label} [{hist_integral:.2f}]")
            sgn_keys.append(sample_id)
            ratio_candidates[sample_id] = {
                "name": sample_label,
                "values": content,
                "errors": errors,
                "color": sample_info["color"],
                "is_data": False,
                "is_signal": True,
                "aliases": sample_info.get("aliases", []),
            }

        else:

            mc_vals.append(content)
            mc_colors.append(sample_info["color"])
            mc_labels.append(f"{sample_label} [{hist_integral:.2f}]")
            mc_integrals.append(hist_integral)
            mc_errs.append(errors)
            mc_keys.append(sample_id)
            ratio_candidates[sample_id] = {
                "name": sample_label,
                "values": content,
                "errors": errors,
                "color": sample_info["color"],
                "is_data": False,
                "is_signal": False,
                "aliases": sample_info.get("aliases", []),
            }

    if bin_edges is None:
        print(f"  [WARNING] Istogramma vuoto o mancante: {variable}")
        return

    # A systematic overlay is a shape diagnostic, not a physics stack. Treat
    # selected signals like the selected MC backgrounds so the same nominal /
    # Up / Down machinery works for qqH, ggH, and background processes.
    if overlay_systematic and sgn_vals:
        mc_vals.extend(sgn_vals)
        mc_errs.extend(sgn_errs)
        mc_integrals.extend(sgn_integrals)
        mc_colors.extend(sgn_colors)
        mc_labels.extend(sgn_labels)
        mc_keys.extend(sgn_keys)
        sgn_vals = []
        sgn_errs = []
        sgn_integrals = []
        sgn_colors = []
        sgn_labels = []
        sgn_keys = []

    # Legend yields must describe the input histograms (including their ROOT
    # under/overflow bins), before any plot-only normalization is applied.
    mc_integrals_before_normalization = list(mc_integrals)

    if normalize_mc_to_data:
        if data_vals is None:
            print(
                f"  [WARNING] MC normalization requested for {variable}, "
                "but data is not available."
            )
        elif not mc_vals:
            print(
                f"  [WARNING] MC normalization requested for {variable}, "
                "but no background MC is available."
            )
        else:
            data_integral = data_integral_total
            mc_integral = np.sum(mc_integrals)

            if mc_integral <= 0:
                print(
                    f"  [WARNING] MC normalization skipped for {variable}: "
                    f"MC integral is {mc_integral:.6g}."
                )
            else:
                mc_scale = data_integral / mc_integral

                for idx, sample_key in enumerate(mc_keys):
                    mc_vals[idx] = mc_vals[idx] * mc_scale
                    mc_errs[idx] = mc_errs[idx] * mc_scale
                    mc_integrals[idx] = mc_integrals[idx] * mc_scale

                    sample_label = ratio_candidates[sample_key]["name"]
                    input_yield = mc_integrals_before_normalization[idx]
                    mc_labels[idx] = f"{sample_label} [{input_yield:.2f}]"
                    ratio_candidates[sample_key]["values"] = mc_vals[idx]
                    ratio_candidates[sample_key]["errors"] = mc_errs[idx]

                print(
                    f"  [MC NORM] {variable}: "
                    f"scale all backgrounds by {mc_scale:.6g} "
                    f"({mc_integral:.6g} -> {data_integral:.6g})"
                )

    if normalize_dy_to_data:
        if data_vals is None:
            print(
                f"  [WARNING] DY normalization requested for {variable}, "
                "but data is not available."
            )
        else:
            dy_keys = resolve_background_targets(
                dy_normalization_sample,
                ratio_candidates,
                mc_keys,
            )

            if not dy_keys:
                print(
                    f"  [WARNING] DY normalization sample "
                    f"'{dy_normalization_sample}' not found among backgrounds "
                    f"for {variable}."
                )
            else:
                data_integral = float(data_integral_total)
                dy_indices = [mc_keys.index(dy_key) for dy_key in dy_keys]
                dy_index_set = set(dy_indices)

                dy_integral = float(
                    np.sum([mc_integrals[idx] for idx in dy_indices])
                )
                other_mc_integral = float(
                    np.sum(
                        [
                            mc_integrals[idx]
                            for idx in range(len(mc_integrals))
                            if idx not in dy_index_set
                        ]
                    )
                )
                target_dy_integral = data_integral - other_mc_integral

                if dy_integral <= 0:
                    print(
                        f"  [WARNING] DY normalization skipped for {variable}: "
                        f"DY integral is {dy_integral:.6g}."
                    )
                elif target_dy_integral <= 0:
                    print(
                        f"  [WARNING] DY normalization skipped for {variable}: "
                        f"Data - OtherMC = {target_dy_integral:.6g} <= 0 "
                        f"(Data={data_integral:.6g}, "
                        f"OtherMC={other_mc_integral:.6g})."
                    )
                else:
                    dy_scale = target_dy_integral / dy_integral

                    for dy_idx in dy_indices:
                        dy_key = mc_keys[dy_idx]
                        mc_vals[dy_idx] = mc_vals[dy_idx] * dy_scale
                        mc_errs[dy_idx] = mc_errs[dy_idx] * dy_scale
                        mc_integrals[dy_idx] = mc_integrals[dy_idx] * dy_scale

                        dy_label = ratio_candidates[dy_key]["name"]
                        input_yield = mc_integrals_before_normalization[dy_idx]
                        mc_labels[dy_idx] = f"{dy_label} [{input_yield:.2f}]"
                        ratio_candidates[dy_key]["values"] = mc_vals[dy_idx]
                        ratio_candidates[dy_key]["errors"] = mc_errs[dy_idx]

                    print(
                        f"  [DY NORM] {variable}: "
                        f"Data={data_integral:.6g}, "
                        f"OtherMC={other_mc_integral:.6g}, "
                        f"target DY={target_dy_integral:.6g}, "
                        f"unscaled DY={dy_integral:.6g}, "
                        f"scale={dy_scale:.6g}"
                    )

    # =====================================================
    # Sort backgrounds by yield
    # =====================================================

    if mc_vals:
        idx_sort = np.argsort(mc_integrals)

        mc_vals = [mc_vals[i] for i in idx_sort]
        mc_errs = [mc_errs[i] for i in idx_sort]
        mc_colors = [mc_colors[i] for i in idx_sort]
        mc_labels = [mc_labels[i] for i in idx_sort]
        mc_keys = [mc_keys[i] for i in idx_sort]

    if auto_trim_empty_edges:
        trim_values = (
            mc_vals
            + sgn_vals
            + ([data_vals] if data_vals is not None else [])
        )
        trim_arrays = (
            mc_vals
            + mc_errs
            + sgn_vals
            + sgn_errs
            + ([data_vals, data_errs] if data_vals is not None else [])
        )

        trimmed_edges, trimmed_arrays = trim_empty_edge_bins(
            bin_edges,
            trim_arrays,
            min_empty_edge_bins=auto_trim_min_empty_edge_bins,
            keep_edge_bins=auto_trim_keep_edge_bins,
        )

        if len(trimmed_edges) != len(bin_edges):
            n_mc = len(mc_vals)
            n_mc_err = len(mc_errs)
            n_sgn = len(sgn_vals)

            bin_edges = trimmed_edges
            mc_vals = trimmed_arrays[:n_mc]
            mc_errs = trimmed_arrays[n_mc:n_mc + n_mc_err]
            sgn_start = n_mc + n_mc_err
            sgn_vals = trimmed_arrays[sgn_start:sgn_start + n_sgn]
            sgn_errs = trimmed_arrays[sgn_start + n_sgn:sgn_start + 2 * n_sgn]

            if data_vals is not None:
                data_start = sgn_start + 2 * n_sgn
                data_vals = trimmed_arrays[data_start]
                data_errs = trimmed_arrays[data_start + 1]

            print(
                f"  [AUTO BINNING] {variable}: trimmed empty edge bins "
                f"from {len(trim_values[0]) if trim_values else 0} "
                f"to {len(bin_edges) - 1} bins"
            )

            for idx, sample_key in enumerate(mc_keys):
                ratio_candidates[sample_key]["values"] = mc_vals[idx]
                ratio_candidates[sample_key]["errors"] = mc_errs[idx]

            for idx, sample_key in enumerate(sgn_keys):
                ratio_candidates[sample_key]["values"] = sgn_vals[idx]
                ratio_candidates[sample_key]["errors"] = sgn_errs[idx]

            if data_key is not None:
                ratio_candidates[data_key]["values"] = data_vals
                ratio_candidates[data_key]["errors"] = data_errs

    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    bin_half_widths = 0.5 * (bin_edges[1:] - bin_edges[:-1])

    # =====================================================
    # Canvas
    # =====================================================

    canvas_size = config_page["page_setup"].get("canvas_size", [900, 800])
    draw_ratio = config_page.get("page_setup", {}).get(
        "draw_ratio",
        config_page.get("draw_ratio", True),
    )
    ratio_reference_key = resolve_ratio_reference(ratio_reference, ratio_candidates)
    has_default_ratio = data_vals is not None and len(mc_vals) > 0
    has_sample_ratio = ratio_reference is not None and ratio_reference_key is not None
    if overlay_systematic:
        show_systematics = True
    has_systematics_ratio = show_systematics and not want_data and len(mc_vals) > 0
    has_ratio = draw_ratio and (
        has_default_ratio or has_sample_ratio or has_systematics_ratio
    )

    if ratio_reference is not None and ratio_reference_key is None:
        print(
            f"  [WARNING] Ratio reference '{ratio_reference}' non trovato "
            f"per {variable}. Uso Data/MC se disponibile."
        )

    composition_groups = {}
    composition_payload = {}
    if dy_composition:
        component_info = {
            idx: pu_hard_component_style(key)
            for idx, key in enumerate(mc_keys)
            if pu_hard_component_style(key) is not None
        }
        component_families = list(dict.fromkeys(
            info[0] for info in component_info.values()
        ))
        for family in component_families:
            indices = [
                idx
                for idx, info in component_info.items()
                if info[0] == family
            ]
            if len(indices) >= 2:
                composition_groups[family] = indices
                composition_payload[family] = {
                    "values": [mc_vals[idx] for idx in indices],
                    "colors": [mc_colors[idx] for idx in indices],
                    "labels": [
                        component_info[idx][1]
                        for idx in indices
                    ],
                }
            elif indices:
                print(
                    f"  [WARNING] {family} composition skipped for {variable}: "
                    "fewer than two jet-component samples were found."
                )

        # Jet components are diagnostic inputs for the percentage panels. The
        # upper physics stack must contain the inclusive DY/EWK processes only.
        component_index_set = {
            idx for indices in composition_groups.values() for idx in indices
        }
        if component_index_set:
            for key in [mc_keys[idx] for idx in sorted(component_index_set)]:
                ratio_candidates.pop(key, None)
            keep_indices = [
                idx for idx in range(len(mc_keys)) if idx not in component_index_set
            ]
            mc_vals = [mc_vals[idx] for idx in keep_indices]
            mc_colors = [mc_colors[idx] for idx in keep_indices]
            mc_labels = [mc_labels[idx] for idx in keep_indices]
            mc_integrals = [mc_integrals[idx] for idx in keep_indices]
            mc_errs = [mc_errs[idx] for idx in keep_indices]
            mc_keys = [mc_keys[idx] for idx in keep_indices]
    has_composition = bool(composition_groups)
    if dy_composition and not has_composition:
        print(
            f"  [WARNING] DY/EWK composition skipped for {variable}: "
            "fewer than two jet-component samples were found."
        )

    composition_families = list(composition_groups)
    n_composition_panels = len(composition_families)

    if has_ratio or has_composition:
        n_panels = 1 + n_composition_panels + int(has_ratio)
        axes = plt.subplots(
            n_panels,
            1,
            figsize=(canvas_size[0] / 80, canvas_size[1] / 85),
            sharex=True,
            gridspec_kw={
                "height_ratios": [3] + [1] * (n_panels - 1),
                "hspace": 0.05,
            },
        )
        fig, panel_axes = axes
        panel_axes = np.atleast_1d(panel_axes)
        ax = panel_axes[0]
        composition_axes = {
            family: panel_axes[index + 1]
            for index, family in enumerate(composition_families)
        }
        rax = panel_axes[-1] if has_ratio else None
    else:
        fig, ax = plt.subplots(
            1,
            1,
            figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
        )
        rax = None
        composition_axes = {}

    # =====================================================
    # Background stack
    # =====================================================

    total_mc_vals = np.zeros(len(bin_edges) - 1, dtype=float)
    total_mc_errs2 = np.zeros(len(bin_edges) - 1, dtype=float)

    if mc_vals:
        total_mc_vals = np.sum(mc_vals, axis=0)
        total_mc_errs2 = np.sum([err ** 2 for err in mc_errs], axis=0)
        total_mc_errs = np.sqrt(total_mc_errs2)

        syst_bands = {}
        if show_systematics and era:
            syst_bands = build_syst_ratio_bands(
                samples_dict=samples_dict,
                category=category,
                variable=variable,
                mc_keys=mc_keys,
                bin_edges=bin_edges,
                era=era,
                systematic_groups=systematic_groups,
            )
        if overlay_systematic and not syst_bands:
            print(
                f"  [SKIP] No requested systematic shapes found for {variable}"
            )
            plt.close(fig)
            return

        if overlay_systematic:
            ax.errorbar(
                bin_centers,
                total_mc_vals,
                xerr=bin_half_widths,
                yerr=total_mc_errs,
                fmt="o",
                color="black",
                markersize=3,
                linewidth=1.0,
                label="Nominal",
                zorder=3,
            )
            for group_label, (ratio_up, ratio_dn, _) in syst_bands.items():
                ax.errorbar(
                    bin_centers,
                    ratio_up * total_mc_vals,
                    xerr=bin_half_widths,
                    fmt="o",
                    color="red",
                    markersize=3,
                    linewidth=1.2,
                    label=f"{group_label} Up",
                )
                ax.errorbar(
                    bin_centers,
                    ratio_dn * total_mc_vals,
                    xerr=bin_half_widths,
                    fmt="s",
                    color="blue",
                    markersize=3,
                    linewidth=1.2,
                    label=f"{group_label} Down",
                )
        elif fill_hists:
            hep.histplot(
                mc_vals,
                bins=bin_edges,
                stack=do_stack,
                histtype="fill",
                color=mc_colors,
                label=mc_labels,
                edgecolor="black",
                linewidth=0.5,
                alpha=1.0 if do_stack else 0.45,
                ax=ax,
            )
        else:
            hep.histplot(
                mc_vals,
                bins=bin_edges,
                stack=do_stack,
                histtype="step",
                color=mc_colors,
                label=mc_labels,
                linewidth=1.3,
                ax=ax,
            )

        if do_stack and not overlay_systematic:
            hep.histplot(
                total_mc_vals,
                bins=bin_edges,
                histtype="step",
                color="black",
                linewidth=0.5,
                ax=ax,
            )

        if do_stack and not overlay_systematic:
            bkg_unc_cfg = config_page.get("bkg_unc_hist", {})
            unc_hatch = "//" if bkg_unc_cfg.get("fill_style") == 3013 else None
            unc_alpha = bkg_unc_cfg.get("alpha", 0.35)

            y_up = total_mc_vals + total_mc_errs
            y_dn = np.maximum(total_mc_vals - total_mc_errs, 0.0)

            ax.fill_between(
                bin_edges[:-1],
                y_dn,
                y_up,
                step="post",
                facecolor="none",
                edgecolor="black",
                hatch=unc_hatch,
                alpha=unc_alpha,
                linewidth=0.8,
                label=bkg_unc_cfg.get("legend_title", "Bkg. uncertainty"),
            )

    else:
        total_mc_errs = np.zeros(len(bin_edges) - 1, dtype=float)

    # =====================================================
    # Signals
    # =====================================================

    for s_val, s_col, s_lab in zip(sgn_vals, sgn_colors, sgn_labels):
        hep.histplot(
            s_val,
            bins=bin_edges,
            histtype="step",
            color=s_col,
            label=s_lab,
            linestyle="--",
            linewidth=1.5,
            ax=ax,
        )

    # =====================================================
    # Data
    # =====================================================

    if data_vals is not None:
        ax.errorbar(
            bin_centers,
            data_vals,
            yerr=data_errs,
            fmt="o",
            color="black",
            markersize=5,
            label=data_label_legend,
        )

    # =====================================================
    # DY/EWK jet composition
    # =====================================================

    for family, payload in composition_payload.items():
        composition_ax = composition_axes[family]
        component_vals = payload["values"]
        component_colors = payload["colors"]
        component_total = np.sum(component_vals, axis=0)
        fractions = [
            np.divide(
                values,
                component_total,
                out=np.zeros_like(values, dtype=float),
                where=component_total != 0,
            )
            for values in component_vals
        ]
        hep.histplot(
            fractions,
            bins=bin_edges,
            stack=True,
            histtype="fill",
            color=component_colors,
            label=payload["labels"],
            edgecolor="none",
            ax=composition_ax,
        )
        composition_ax.set_ylim(0.0, 1.0)
        # Avoid overlapping 100%/0% labels at the shared boundary between
        # adjacent composition panels. The limits still represent 0--100%,
        # while only internal percentage ticks receive labels.
        composition_ax.yaxis.set_major_locator(
            mticker.FixedLocator([0.25, 0.5, 0.75])
        )
        composition_ax.yaxis.set_major_formatter(
            mticker.PercentFormatter(xmax=1.0, decimals=0)
        )
        composition_ax.set_ylabel(f"{family}\nComp.", fontsize=12)
        composition_ax.grid(axis="y", linestyle=":", linewidth=0.5, alpha=0.5)
        composition_ax.legend(
            fontsize=7,
            frameon=True,
            ncol=min(3, len(payload["labels"])),
            loc="upper center",
        )

    # =====================================================
    # Ratio
    # =====================================================

    if has_ratio:
        ratio_arrays = []
        ratio_unc_low = None
        ratio_unc_high = None

        if has_sample_ratio:
            denominator = ratio_candidates[ratio_reference_key]
            denom_vals = denominator["values"]
            denom_errs = denominator["errors"]

            denom_rel_unc = np.divide(
                denom_errs,
                denom_vals,
                out=np.zeros_like(denom_errs, dtype=float),
                where=denom_vals != 0,
            )
            ratio_unc_high = 1.0 + denom_rel_unc
            ratio_unc_low = np.maximum(1.0 - denom_rel_unc, 0.0)

            rax.fill_between(
                bin_edges,
                np.r_[ratio_unc_low, ratio_unc_low[-1]],
                np.r_[ratio_unc_high, ratio_unc_high[-1]],
                step="post",
                facecolor="ghostwhite",
                edgecolor="black",
                hatch="//",
                alpha=0.5,
                zorder=1,
            )

            for sample_key, numerator in ratio_candidates.items():
                if sample_key == ratio_reference_key:
                    continue

                num_vals = numerator["values"]
                num_errs = numerator["errors"]
                valid_ratio = (
                    (denom_vals != 0)
                    & np.isfinite(denom_vals)
                    & np.isfinite(num_vals)
                    & np.isfinite(num_errs)
                )

                ratio = np.divide(
                    num_vals,
                    denom_vals,
                    out=np.full_like(num_vals, np.nan, dtype=float),
                    where=valid_ratio,
                )
                ratio_err = np.abs(
                    np.divide(
                        num_errs,
                        denom_vals,
                        out=np.full_like(num_errs, np.nan, dtype=float),
                        where=valid_ratio,
                    )
                )

                ratio_arrays.append(ratio)
                ratio_arrays.append(ratio - ratio_err)
                ratio_arrays.append(ratio + ratio_err)
                draw_style = "--" if numerator.get("is_signal", False) else "-"

                rax.errorbar(
                    bin_centers,
                    ratio,
                    yerr=ratio_err,
                    fmt=".",
                    color=numerator["color"],
                    markersize=7,
                    linestyle=draw_style,
                    linewidth=1.0,
                    label=numerator["name"],
                    zorder=2,
                )

            rax.set_ylabel(f"/ {denominator['name']}", fontsize=14)

            if len(ratio_arrays) > 1:
                rax.legend(fontsize=9, frameon=True, ncol=2)

        else:
            # ----------------------------------------------------------
            # Default Data/MC ratio branch
            # ----------------------------------------------------------
            ratio = None
            ratio_err = None
            if data_vals is not None:
                valid_ratio = (
                    (total_mc_vals != 0)
                    & np.isfinite(total_mc_vals)
                    & np.isfinite(data_vals)
                    & np.isfinite(data_errs)
                )

                ratio = np.divide(
                    data_vals,
                    total_mc_vals,
                    out=np.full_like(data_vals, np.nan, dtype=float),
                    where=valid_ratio,
                )

                ratio_err = np.abs(
                    np.divide(
                        data_errs,
                        total_mc_vals,
                        out=np.full_like(data_errs, np.nan, dtype=float),
                        where=valid_ratio,
                    )
                )

            # MC stat uncertainty — used for ratio_unc_low/high passed to
            # set_ratio_axis_range; drawn as a light gray band behind syst lines
            mc_rel_unc = np.divide(
                total_mc_errs,
                total_mc_vals,
                out=np.zeros_like(total_mc_errs, dtype=float),
                where=total_mc_vals != 0,
            )
            if show_mc_stat_uncertainty:
                ratio_unc_high = 1.0 + mc_rel_unc
                ratio_unc_low = np.maximum(1.0 - mc_rel_unc, 0.0)

                rax.fill_between(
                    bin_edges,
                    np.r_[ratio_unc_low, ratio_unc_low[-1]],
                    np.r_[ratio_unc_high, ratio_unc_high[-1]],
                    step="post",
                    facecolor="white",
                    edgecolor="gray",
                    hatch="//",
                    linewidth=2,
                    alpha=1.0,
                    zorder=1,
                    label="MC stat. uncertainty",
                )

            # Per-systematic step-line bands
            n_bins = len(bin_centers)
            if show_systematics and era and mc_keys:
                # Computed once above so the main-panel overlay and ratio use
                # exactly the same nuisance envelope.

                for group_label, (ratio_up, ratio_dn, color) in syst_bands.items():
                    ratio_arrays.extend([ratio_up, ratio_dn])
                    if overlay_systematic:
                        rax.errorbar(
                            bin_centers,
                            ratio_up,
                            xerr=bin_half_widths,
                            fmt="o",
                            color="red",
                            markersize=3,
                            linewidth=1.2,
                            zorder=2,
                            label=f"{group_label} Up",
                        )
                        rax.errorbar(
                            bin_centers,
                            ratio_dn,
                            xerr=bin_half_widths,
                            fmt="s",
                            color="blue",
                            markersize=3,
                            linewidth=1.2,
                            zorder=2,
                            label=f"{group_label} Down",
                        )
                    else:
                        # Up line carries the group label; Down uses the same
                        # color without adding a duplicate legend entry.
                        rax.step(
                            bin_edges,
                            np.r_[ratio_up, ratio_up[-1]],
                            where="post",
                            color=color,
                            linewidth=2,
                            zorder=2,
                            label=group_label,
                        )
                        rax.step(
                            bin_edges,
                            np.r_[ratio_dn, ratio_dn[-1]],
                            where="post",
                            color=color,
                            linewidth=2,
                            zorder=2,
                        )

                if include_total_systematics and syst_bands:
                    sq_up = np.zeros(n_bins, dtype=float)
                    sq_dn = np.zeros(n_bins, dtype=float)
                    for ratio_up, ratio_dn, _ in syst_bands.values():
                        sq_up += (ratio_up - 1.0) ** 2
                        sq_dn += (ratio_dn - 1.0) ** 2
                    total_up = 1.0 + np.sqrt(sq_up)
                    total_dn = 1.0 - np.sqrt(sq_dn)
                    ratio_arrays.extend([total_up, total_dn])
                    rax.step(
                        bin_edges,
                        np.r_[total_up, total_up[-1]],
                        where="post",
                        color="black",
                        linewidth=3,
                        zorder=2,
                        label="Syst. total",
                    )
                    rax.step(
                        bin_edges,
                        np.r_[total_dn, total_dn[-1]],
                        where="post",
                        color="black",
                        linewidth=3,
                        zorder=2,
                    )
            # Data points on top of all bands, when requested.
            if ratio is not None:
                rax.errorbar(
                    bin_centers,
                    ratio,
                    yerr=ratio_err,
                    fmt=".",
                    color="black",
                    markersize=10,
                    zorder=3,
                )

                ratio_arrays.append(ratio)
                ratio_arrays.append(ratio - ratio_err)
                ratio_arrays.append(ratio + ratio_err)

            rax.legend(
                fontsize=7,
                frameon=True,
                framealpha=0.8,
                loc="upper center",
                bbox_to_anchor=(0.5, 0.99),
                ncol=4,
                handlelength=1.5,
                labelspacing=0.25,
            )

            rax.set_ylabel(
                "Data/MC" if ratio is not None else "Variation/Nominal",
                fontsize=14,
            )

        rax.axhline(
            1.0,
            color="black",
            linestyle="--",
            linewidth=2.0,
        )

        set_ratio_axis_range(
            rax,
            ratio_arrays,
            ratio_unc_low=ratio_unc_low,
            ratio_unc_high=ratio_unc_high,
            log_scale=log_uncertainties,
        )
        if (
            has_systematics_ratio
            and not has_default_ratio
            and not has_sample_ratio
            and not log_uncertainties
        ):
            finite_ratio_values = [
                values[np.isfinite(values)]
                for values in (np.asarray(array) for array in ratio_arrays)
            ]
            finite_ratio_values = [
                values for values in finite_ratio_values if values.size
            ]
            if finite_ratio_values:
                max_deviation = max(
                    float(np.max(np.abs(values - 1.0)))
                    for values in finite_ratio_values
                )
                # Keep the axis centred on the nominal and leave 20% headroom.
                # A small floor avoids a degenerate range for unity variations.
                half_range = max(1.2 * max_deviation, 0.01)
            else:
                half_range = 0.05
            rax.set_ylim(1.0 - half_range, 1.0 + half_range)
            rax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=5))
            ratio_decimals = 3 if half_range < 0.05 else 2
            rax.yaxis.set_major_formatter(
                mticker.FormatStrFormatter(f"%.{ratio_decimals}f")
            )

    # =====================================================
    # Axes
    # =====================================================

    x_label = hist_cfg.get("x_title", variable)

    for mu_idx in [1, 2]:
        if f"mu{mu_idx}" in variable:
            x_label = x_label.format(mu_idx=mu_idx)
    for jet_idx in [1, 2]:
        if f"vbfjet{jet_idx}" in variable:
            x_label = x_label.format(jet_idx=jet_idx)
    if variable.split("_")[0] == "leadingjet":
        x_label = x_label.format(jname="leading j")
    if variable.split("_")[0] == "subleadingjet":
        x_label = x_label.format(jname="subleading j")
    if variable.split("_")[0] == "thirdjet":
        x_label = x_label.format(jname="third j")
    if variable.split("_")[0] == "fourthjet":
        x_label = x_label.format(jname="fourth j")
    if has_ratio:
        rax.set_xlabel(x_label, fontsize=20)
        ax.get_xaxis().set_visible(False)
        for composition_ax in composition_axes.values():
            composition_ax.get_xaxis().set_visible(False)
    elif has_composition:
        last_composition_ax = composition_axes[composition_families[-1]]
        last_composition_ax.set_xlabel(x_label, fontsize=20)
        for composition_ax in list(composition_axes.values())[:-1]:
            composition_ax.get_xaxis().set_visible(False)
        ax.get_xaxis().set_visible(False)
    else:
        ax.set_xlabel(x_label, fontsize=20)

    ax.set_ylabel(hist_cfg.get("y_title", "Events"), fontsize=20)
    ax.set_xlim(bin_edges[0] * 0.99, bin_edges[-1] * 1.01)

    want_log_y = config_page.get("wantLogY", False)
    ax.set_yscale("log" if want_log_y else "linear")

    visible_arrays = list(mc_vals)

    if data_vals is not None:
        visible_arrays.append(data_vals)

    for s_val in sgn_vals:
        visible_arrays.append(s_val)

    y_max = safe_nanmax(visible_arrays, default=1.0)

    max_factor = (
        hist_cfg.get("max_y_sf", 1.2)
        if not want_log_y
        else 100 ** hist_cfg.get("max_y_sf", 1.0)
    )

    ax.set_ylim(top=y_max * max_factor)

    if want_log_y:
        ax.set_ylim(bottom=min(0.1, y_max * 1e-5))
    else:
        ax.set_ylim(bottom=0.0)

    # =====================================================
    # Legend
    # =====================================================

    legend_cfg = config_page.get("legend_mplhep", {})

    ax.legend(
        loc="upper right",
        facecolor=legend_cfg.get("fill_color", "white"),
        frameon=True,
        fontsize=legend_cfg.get("text_size", 0.16) * 110,
        framealpha=0.2,
        ncol=legend_cfg.get("ncols", 2),
        handleheight=1.4,
        labelspacing=0.2,
    )

    # =====================================================
    # CMS label
    # =====================================================
    category_names = {
        "mass_inclusive_baseline": "baseline incl",
        "mass_inclusive_ggF": "ggF incl",
        "mass_inclusive_VBF": "VBF incl",
        "Z_sideband_baseline": "baseline Z",
        "Z_sideband_ggF": "ggF Z",
        "Z_sideband_VBF": "VBF Z",

        "H_sideband_baseline": "baseline H SB",
        "H_sideband_ggF": "ggF H SB",
        "H_sideband_VBF": "VBF H SB",

        "Signal_Fit_ggF": "ggF H",
        "Signal_Fit_VBF": "VBF H",
        "Signal_Fit_baseline": "baseline H",

        "mass_inclusive_baseline_lowPtTT": "baseline incl",
        "mass_inclusive_ggF_lowPtTT": "ggF incl",
        "mass_inclusive_VBF_lowPtTT": "VBF incl",
        "Z_sideband_baseline_lowPtTT": "baseline Z",
        "Z_sideband_ggF_lowPtTT": "ggF Z",
        "Z_sideband_VBF_lowPtTT": "VBF Z",

        "Z_sideband_baseline_lowPtTT": "baseline Z",
        "Z_sideband_ggF_lowPtTT": "ggF Z",
        "Z_sideband_VBF_lowPtTT": "VBF Z",

        "Signal_Fit_ggF_lowPtTT": "ggF H",
        "Signal_Fit_VBF_lowPtTT": "VBF H",
        "Signal_Fit_baseline_lowPtTT": "baseline H",

        "Signal_Fit_VBF/incl": "VBF H",
        "Signal_Fit_VBF/CC": "VBF H CC",
        "Signal_Fit_VBF/CF": "VBF H CF",
        "Signal_Fit_VBF/FF": "VBF H FF",

        "Z_sideband_VBF/incl": "VBF Z",
        "Z_sideband_VBF/CC": "VBF Z CC",
        "Z_sideband_VBF/CF": "VBF Z CF",
        "Z_sideband_VBF/FF": "VBF Z FF",

        "H_sideband_VBF/incl": "VBF H sideband",
        "H_sideband_VBF/CC": "VBF H sideband CC",
        "H_sideband_VBF/CF": "VBF H sideband CF",
        "H_sideband_VBF/FF": "VBF H sideband FF",           
    }

    lumi_val = config_page.get("lumi_text", {}).get("text", "1.0")
    cms_tag = f"Preliminary {category_names[category]}"
    category_label = category_names.get(category, category.replace("/incl", ""))
    cms_tag = f"Preliminary {category_label}" # config_page.get("cms_label", {}).get("tag",
    cms_com = config_page.get("cms_label", {}).get("com", "13.6")

    hep.cms.label(
        ax=ax,
        data=(data_vals is not None),
        label=cms_tag,
        lumi=float(lumi_val),
        com=float(cms_com),
        loc=0,
        fontsize=20,
    )

    # =====================================================
    # Save
    # =====================================================

    fig.savefig(f"{out_name}.png", bbox_inches="tight")
    fig.savefig(f"{out_name}.pdf", bbox_inches="tight")

    print(f"{out_name}.png")

    plt.close(fig)

# import os

# os.environ.setdefault(
#     "MPLCONFIGDIR",
#     os.path.join("/tmp", os.environ.get("USER", "user"), "matplotlib"),
# )

# import matplotlib.pyplot as plt
# import matplotlib.ticker as mticker
# import mplhep as hep
# import numpy as np

# from common.helpers import findBinEntry

# plt.style.use(hep.style.CMS)


# def normalize_sample_name(name):
#     return os.path.splitext(os.path.basename(name))[0]


# def get_total_hist_integral(root_hist):
#     return root_hist.Integral(0, root_hist.GetNbinsX() + 1)


# def parse_sample_targets(target_spec):
#     if target_spec is None:
#         return []

#     if isinstance(target_spec, (list, tuple, set)):
#         raw_items = target_spec
#     else:
#         raw_items = str(target_spec).replace(",", " ").split()

#     return [item.strip() for item in raw_items if item and item.strip()]


# def starts_with_dy(candidate):
#     return normalize_sample_name(candidate).lower().startswith("dy")


# def resolve_background_targets(target_spec, ratio_candidates, mc_keys):
#     targets = []

#     for target in parse_sample_targets(target_spec):
#         target_key = resolve_ratio_reference(target, ratio_candidates)

#         if target_key is not None and target_key in mc_keys and target_key not in targets:
#             targets.append(target_key)

#     requested_targets = parse_sample_targets(target_spec)

#     if (
#         not targets
#         and len(requested_targets) == 1
#         and normalize_sample_name(requested_targets[0]).lower() == "dy"
#     ):
#         for sample_key in mc_keys:
#             candidate = ratio_candidates[sample_key]
#             if starts_with_dy(sample_key) or starts_with_dy(candidate.get("name", "")):
#                 targets.append(sample_key)

#     return targets


# def get_bins_and_content(root_hist, want_overflow=False, divide_by_bin_width=False):
#     """
#     Estrae bin edges, contenuti ed errori da un TH1.
#     Se richiesto, somma underflow/overflow al primo/ultimo bin visibile.
#     """
#     n_bins = root_hist.GetNbinsX()

#     edges = np.array(
#         [root_hist.GetBinLowEdge(i) for i in range(1, n_bins + 2)],
#         dtype=float,
#     )

#     content = np.array(
#         [root_hist.GetBinContent(i) for i in range(1, n_bins + 1)],
#         dtype=float,
#     )

#     errors = np.array(
#         [root_hist.GetBinError(i) for i in range(1, n_bins + 1)],
#         dtype=float,
#     )

#     if want_overflow and n_bins > 0:
#         content[-1] += root_hist.GetBinContent(n_bins + 1)
#         errors[-1] = np.sqrt(
#             errors[-1] ** 2 + root_hist.GetBinError(n_bins + 1) ** 2
#         )

#         content[0] += root_hist.GetBinContent(0)
#         errors[0] = np.sqrt(
#             errors[0] ** 2 + root_hist.GetBinError(0) ** 2
#         )

#     if divide_by_bin_width:
#         widths = np.diff(edges)

#         content = np.divide(
#             content,
#             widths,
#             out=np.zeros_like(content),
#             where=widths != 0,
#         )

#         errors = np.divide(
#             errors,
#             widths,
#             out=np.zeros_like(errors),
#             where=widths != 0,
#         )

#     return edges, content, errors


# def trim_empty_edge_bins(
#     bin_edges,
#     value_arrays,
#     min_empty_edge_bins=2,
#     keep_edge_bins=0,
# ):
#     n_bins = len(bin_edges) - 1

#     if n_bins <= 0:
#         return bin_edges, value_arrays

#     occupied = np.zeros(n_bins, dtype=bool)

#     for values in value_arrays:
#         if values is None:
#             continue

#         arr = np.asarray(values, dtype=float)

#         if len(arr) != n_bins:
#             continue

#         occupied |= np.isfinite(arr) & (np.abs(arr) > 0.0)

#     if not np.any(occupied):
#         return bin_edges, value_arrays

#     occupied_bins = np.where(occupied)[0]
#     first_nonempty = int(occupied_bins[0])
#     last_nonempty = int(occupied_bins[-1])

#     leading_empty = first_nonempty
#     trailing_empty = n_bins - last_nonempty - 1

#     trim_first = 0
#     trim_last = n_bins - 1

#     if leading_empty >= min_empty_edge_bins:
#         trim_first = max(first_nonempty - keep_edge_bins, 0)

#     if trailing_empty >= min_empty_edge_bins:
#         trim_last = min(last_nonempty + keep_edge_bins, n_bins - 1)

#     if trim_first == 0 and trim_last == n_bins - 1:
#         return bin_edges, value_arrays

#     trimmed_edges = bin_edges[trim_first:trim_last + 2]
#     trimmed_arrays = []

#     for values in value_arrays:
#         if values is None:
#             trimmed_arrays.append(None)
#             continue

#         arr = np.asarray(values)

#         if len(arr) != n_bins:
#             trimmed_arrays.append(values)
#         else:
#             trimmed_arrays.append(arr[trim_first:trim_last + 1])

#     return trimmed_edges, trimmed_arrays


# def get_blind_range_for_category(hist_cfg, category):
#     """
#     Supporta:

#       blind_range: [115, 130]

#     oppure:

#       blind_range:
#         Signal_Fit: [115, 130]
#     """
#     blind_range = hist_cfg.get("blind_range", None)

#     if blind_range is None:
#         return None

#     if isinstance(blind_range, (list, tuple)):
#         if len(blind_range) != 2:
#             print(f"  [WARNING] blind_range malformato: {blind_range}")
#             return None

#         return [float(blind_range[0]), float(blind_range[1])]

#     if isinstance(blind_range, dict):
#         category_range = blind_range.get(category, None)

#         if category_range is None:
#             return None

#         if not isinstance(category_range, (list, tuple)) or len(category_range) != 2:
#             print(
#                 f"  [WARNING] blind_range malformato "
#                 f"per categoria {category}: {category_range}"
#             )
#             return None

#         return [float(category_range[0]), float(category_range[1])]

#     print(f"  [WARNING] Tipo non supportato per blind_range: {type(blind_range)}")

#     return None


# def apply_blind_range(edges, content, errors, blind_range=None):
#     """
#     Applica il blinding ai dati.
#     Usa NaN per non disegnare quei punti.
#     """
#     if blind_range is None:
#         return content, errors, None

#     xmin, xmax = blind_range

#     bin_centers = 0.5 * (edges[:-1] + edges[1:])
#     blind_mask = (bin_centers >= xmin) & (bin_centers <= xmax)

#     if not np.any(blind_mask):
#         return content, errors, blind_mask

#     blinded_content = content.copy()
#     blinded_errors = errors.copy()

#     blinded_content[blind_mask] = np.nan
#     blinded_errors[blind_mask] = np.nan

#     return blinded_content, blinded_errors, blind_mask


# def safe_nanmax(arrays, default=1.0):
#     """
#     Massimo robusto ignorando NaN e inf.
#     """
#     finite_values = []

#     for arr in arrays:
#         if arr is None:
#             continue

#         arr = np.asarray(arr, dtype=float)
#         finite = arr[np.isfinite(arr)]

#         if len(finite):
#             finite_values.append(np.max(finite))

#     if not finite_values:
#         return default

#     return max(finite_values)


# def safe_nanmin(arrays, default=0.0):
#     """
#     Minimo robusto ignorando NaN e inf.
#     """
#     finite_values = []

#     for arr in arrays:
#         if arr is None:
#             continue

#         arr = np.asarray(arr, dtype=float)
#         finite = arr[np.isfinite(arr)]

#         if len(finite):
#             finite_values.append(np.min(finite))

#     if not finite_values:
#         return default

#     return min(finite_values)


# def resolve_ratio_reference(ratio_reference, ratio_candidates):
#     if ratio_reference is None:
#         return None

#     normalized_reference = normalize_sample_name(ratio_reference)

#     for key, candidate in ratio_candidates.items():
#         aliases = {
#             key,
#             normalize_sample_name(key),
#             candidate.get("name", key),
#             normalize_sample_name(candidate.get("name", key)),
#         }
#         for alias in candidate.get("aliases", []):
#             aliases.add(alias)
#             aliases.add(normalize_sample_name(alias))

#         if ratio_reference in aliases or normalized_reference in aliases:
#             return key

#     return None


# def set_ratio_axis_range(rax, ratio_arrays, ratio_unc_low=None, ratio_unc_high=None):
#     ymin = 0.5
#     ymax = 1.5

#     rax.set_ylim(ymin, ymax)

#     ticks = np.round(np.arange(ymin, ymax + 0.001, 0.2), 1)
#     rax.yaxis.set_major_locator(mticker.FixedLocator(ticks))
#     rax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
#     rax.grid(axis="y", which="major", linestyle=":", linewidth=0.6, alpha=0.5)


# # =========================================================
# # Plotting
# # =========================================================

# def make_stacked_plot(
#     samples_dict,
#     config_page,
#     category,
#     variable,
#     out_name,
#     want_data=True,
#     do_stack=True,
#     fill_hists=True,
#     ratio_reference=None,
#     normalize_dy_to_data=False,
#     normalize_mc_to_data=False,
#     dy_normalization_sample="DY",
# ):
#     """
#     Genera uno stacked plot con:
#       - background in stack
#       - signal overlay
#       - data opzionale
#       - ratio Data/MC opzionale
#       - blinding sui dati
#     """
#     mc_vals = []
#     mc_colors = []
#     mc_labels = []
#     mc_integrals = []
#     mc_errs = []
#     mc_keys = []

#     sgn_vals = []
#     sgn_errs = []
#     sgn_colors = []
#     sgn_labels = []
#     sgn_keys = []

#     ratio_candidates = {}
#     data_key = None

#     data_vals = None
#     data_errs = None
#     data_integral_total = None
#     data_label_legend = None

#     bin_edges = None

#     hist_entry = findBinEntry(config_page, variable)
#     hist_cfg = config_page.get(hist_entry, {}) if hist_entry is not None else {}

#     divide_by_bin_width = hist_cfg.get("divide_by_bin_width", False)
#     include_overflow = True # hist_cfg.get("include_overflow", False)
#     auto_trim_empty_edges = hist_cfg.get(
#         "auto_trim_empty_edges",
#         config_page.get("auto_trim_empty_edges", False),
#     )
#     auto_trim_min_empty_edge_bins = hist_cfg.get(
#         "auto_trim_min_empty_edge_bins",
#         config_page.get("auto_trim_min_empty_edge_bins", 2),
#     )
#     auto_trim_keep_edge_bins = hist_cfg.get(
#         "auto_trim_keep_edge_bins",
#         config_page.get("auto_trim_keep_edge_bins", 0),
#     )
#     blind_range = get_blind_range_for_category(hist_cfg, category)

#     if blind_range is not None:
#         print(f"  [BLIND] {variable} in category {category}: range {blind_range}")

#     # =====================================================
#     # Split samples by type
#     # =====================================================

#     for sample_id, sample_info in samples_dict.items():

#         if category not in sample_info["hists"]:
#             continue

#         if variable not in sample_info["hists"][category]:
#             continue

#         root_hist = sample_info["hists"][category][variable]

#         edges, content, errors = get_bins_and_content(
#             root_hist,
#             want_overflow=include_overflow,
#             divide_by_bin_width=divide_by_bin_width,
#         )

#         if bin_edges is None:
#             bin_edges = edges

#         hist_integral = get_total_hist_integral(root_hist)
#         sample_label = sample_info.get("name", sample_id)

#         if sample_info["is_data"]:

#             if not want_data:
#                 continue

#             content, errors, blind_mask = apply_blind_range(
#                 edges,
#                 content,
#                 errors,
#                 blind_range=blind_range,
#             )

#             data_vals = content
#             data_errs = errors
#             data_integral_total = hist_integral
#             data_key = sample_id

#             ratio_candidates[sample_id] = {
#                 "name": sample_label,
#                 "values": content,
#                 "errors": errors,
#                 "color": "black",
#                 "is_data": True,
#                 "is_signal": False,
#                 "aliases": sample_info.get("aliases", []),
#             }

#             data_label_base = sample_label

#             if blind_range is not None and blind_mask is not None and np.any(blind_mask):
#                 data_label_legend = f"{data_label_base} [blinded]"
#             else:
#                 data_label_legend = f"{data_label_base} [{hist_integral:.2f}]"

#         elif sample_info["is_signal"]:

#             sgn_vals.append(content)
#             sgn_errs.append(errors)
#             sgn_colors.append(sample_info["color"])
#             sgn_labels.append(f"{sample_label} [{hist_integral:.2f}]")
#             sgn_keys.append(sample_id)
#             ratio_candidates[sample_id] = {
#                 "name": sample_label,
#                 "values": content,
#                 "errors": errors,
#                 "color": sample_info["color"],
#                 "is_data": False,
#                 "is_signal": True,
#                 "aliases": sample_info.get("aliases", []),
#             }

#         else:

#             mc_vals.append(content)
#             mc_colors.append(sample_info["color"])
#             mc_labels.append(f"{sample_label} [{hist_integral:.2f}]")
#             mc_integrals.append(hist_integral)
#             mc_errs.append(errors)
#             mc_keys.append(sample_id)
#             ratio_candidates[sample_id] = {
#                 "name": sample_label,
#                 "values": content,
#                 "errors": errors,
#                 "color": sample_info["color"],
#                 "is_data": False,
#                 "is_signal": False,
#                 "aliases": sample_info.get("aliases", []),
#             }

#     if bin_edges is None:
#         print(f"  [WARNING] Istogramma vuoto o mancante: {variable}")
#         return

#     if normalize_mc_to_data:
#         if data_vals is None:
#             print(
#                 f"  [WARNING] MC normalization requested for {variable}, "
#                 "but data is not available."
#             )
#         elif not mc_vals:
#             print(
#                 f"  [WARNING] MC normalization requested for {variable}, "
#                 "but no background MC is available."
#             )
#         else:
#             data_integral = data_integral_total
#             mc_integral = np.sum(mc_integrals)

#             if mc_integral <= 0:
#                 print(
#                     f"  [WARNING] MC normalization skipped for {variable}: "
#                     f"MC integral is {mc_integral:.6g}."
#                 )
#             else:
#                 mc_scale = data_integral / mc_integral

#                 for idx, sample_key in enumerate(mc_keys):
#                     mc_vals[idx] = mc_vals[idx] * mc_scale
#                     mc_errs[idx] = mc_errs[idx] * mc_scale
#                     mc_integrals[idx] = mc_integrals[idx] * mc_scale

#                     sample_label = ratio_candidates[sample_key]["name"]
#                     mc_labels[idx] = f"{sample_label} [{mc_integrals[idx]:.2f}]"
#                     ratio_candidates[sample_key]["values"] = mc_vals[idx]
#                     ratio_candidates[sample_key]["errors"] = mc_errs[idx]

#                 print(
#                     f"  [MC NORM] {variable}: "
#                     f"scale all backgrounds by {mc_scale:.6g} "
#                     f"({mc_integral:.6g} -> {data_integral:.6g})"
#                 )

#     if normalize_dy_to_data:
#         if data_vals is None:
#             print(
#                 f"  [WARNING] DY normalization requested for {variable}, "
#                 "but data is not available."
#             )
#         else:
#             dy_keys = resolve_background_targets(
#                 dy_normalization_sample,
#                 ratio_candidates,
#                 mc_keys,
#             )

#             if not dy_keys:
#                 print(
#                     f"  [WARNING] DY normalization sample "
#                     f"'{dy_normalization_sample}' not found among backgrounds "
#                     f"for {variable}."
#                 )
#             else:
#                 data_integral = data_integral_total
#                 dy_indices = [mc_keys.index(dy_key) for dy_key in dy_keys]
#                 dy_integral = np.sum([mc_integrals[dy_idx] for dy_idx in dy_indices])

#                 if dy_integral <= 0:
#                     print(
#                         f"  [WARNING] DY normalization skipped for {variable}: "
#                         f"DY integral is {dy_integral:.6g}."
#                     )
#                 else:
#                     dy_scale = data_integral / dy_integral

#                     for dy_idx in dy_indices:
#                         dy_key = mc_keys[dy_idx]
#                         mc_vals[dy_idx] = mc_vals[dy_idx] * dy_scale
#                         mc_errs[dy_idx] = mc_errs[dy_idx] * dy_scale
#                         mc_integrals[dy_idx] = mc_integrals[dy_idx] * dy_scale

#                         dy_label = ratio_candidates[dy_key]["name"]
#                         mc_labels[dy_idx] = (
#                             f"{dy_label} [{mc_integrals[dy_idx]:.2f}]"
#                             f" x {dy_scale:.4g}"
#                         )
#                         ratio_candidates[dy_key]["values"] = mc_vals[dy_idx]
#                         ratio_candidates[dy_key]["errors"] = mc_errs[dy_idx]

#                     print(
#                         f"  [DY NORM] {variable}: "
#                         f"scale {', '.join(dy_keys)} by {dy_scale:.6g} "
#                         f"({dy_integral:.6g} -> {data_integral:.6g})"
#                     )

#     # =====================================================
#     # Sort backgrounds by yield
#     # =====================================================

#     if mc_vals:
#         idx_sort = np.argsort(mc_integrals)

#         mc_vals = [mc_vals[i] for i in idx_sort]
#         mc_errs = [mc_errs[i] for i in idx_sort]
#         mc_colors = [mc_colors[i] for i in idx_sort]
#         mc_labels = [mc_labels[i] for i in idx_sort]
#         mc_keys = [mc_keys[i] for i in idx_sort]

#     if auto_trim_empty_edges:
#         trim_values = (
#             mc_vals
#             + sgn_vals
#             + ([data_vals] if data_vals is not None else [])
#         )
#         trim_arrays = (
#             mc_vals
#             + mc_errs
#             + sgn_vals
#             + sgn_errs
#             + ([data_vals, data_errs] if data_vals is not None else [])
#         )

#         trimmed_edges, trimmed_arrays = trim_empty_edge_bins(
#             bin_edges,
#             trim_arrays,
#             min_empty_edge_bins=auto_trim_min_empty_edge_bins,
#             keep_edge_bins=auto_trim_keep_edge_bins,
#         )

#         if len(trimmed_edges) != len(bin_edges):
#             n_mc = len(mc_vals)
#             n_mc_err = len(mc_errs)
#             n_sgn = len(sgn_vals)

#             bin_edges = trimmed_edges
#             mc_vals = trimmed_arrays[:n_mc]
#             mc_errs = trimmed_arrays[n_mc:n_mc + n_mc_err]
#             sgn_start = n_mc + n_mc_err
#             sgn_vals = trimmed_arrays[sgn_start:sgn_start + n_sgn]
#             sgn_errs = trimmed_arrays[sgn_start + n_sgn:sgn_start + 2 * n_sgn]

#             if data_vals is not None:
#                 data_start = sgn_start + 2 * n_sgn
#                 data_vals = trimmed_arrays[data_start]
#                 data_errs = trimmed_arrays[data_start + 1]

#             print(
#                 f"  [AUTO BINNING] {variable}: trimmed empty edge bins "
#                 f"from {len(trim_values[0]) if trim_values else 0} "
#                 f"to {len(bin_edges) - 1} bins"
#             )

#             for idx, sample_key in enumerate(mc_keys):
#                 ratio_candidates[sample_key]["values"] = mc_vals[idx]
#                 ratio_candidates[sample_key]["errors"] = mc_errs[idx]

#             for idx, sample_key in enumerate(sgn_keys):
#                 ratio_candidates[sample_key]["values"] = sgn_vals[idx]
#                 ratio_candidates[sample_key]["errors"] = sgn_errs[idx]

#             if data_key is not None:
#                 ratio_candidates[data_key]["values"] = data_vals
#                 ratio_candidates[data_key]["errors"] = data_errs

#     bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

#     # =====================================================
#     # Canvas
#     # =====================================================

#     canvas_size = config_page["page_setup"].get("canvas_size", [900, 800])
#     draw_ratio = config_page.get("page_setup", {}).get(
#         "draw_ratio",
#         config_page.get("draw_ratio", True),
#     )
#     # print(ratio_candidates)
#     # print(ratio_reference)
#     ratio_reference_key = resolve_ratio_reference(ratio_reference, ratio_candidates)
#     has_default_ratio = data_vals is not None and len(mc_vals) > 0
#     has_sample_ratio = ratio_reference is not None and ratio_reference_key is not None
#     has_ratio = draw_ratio and (has_default_ratio or has_sample_ratio)

#     if ratio_reference is not None and ratio_reference_key is None:
#         print(
#             f"  [WARNING] Ratio reference '{ratio_reference}' non trovato "
#             f"per {variable}. Uso Data/MC se disponibile."
#         )

#     if has_ratio:
#         fig, (ax, rax) = plt.subplots(
#             2,
#             1,
#             figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
#             sharex=True,
#             gridspec_kw={
#                 "height_ratios": [3, 1],
#                 "hspace": 0.05,
#             },
#         )
#     else:
#         fig, ax = plt.subplots(
#             1,
#             1,
#             figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
#         )
#         rax = None

#     # =====================================================
#     # Background stack
#     # =====================================================

#     total_mc_vals = np.zeros(len(bin_edges) - 1, dtype=float)
#     total_mc_errs2 = np.zeros(len(bin_edges) - 1, dtype=float)

#     if mc_vals:
#         total_mc_vals = np.sum(mc_vals, axis=0)
#         total_mc_errs2 = np.sum([err ** 2 for err in mc_errs], axis=0)
#         total_mc_errs = np.sqrt(total_mc_errs2)

#         if fill_hists:
#             hep.histplot(
#                 mc_vals,
#                 bins=bin_edges,
#                 stack=do_stack,
#                 histtype="fill",
#                 color=mc_colors,
#                 label=mc_labels,
#                 edgecolor="black",
#                 linewidth=0.5,
#                 alpha=1.0 if do_stack else 0.45,
#                 ax=ax,
#             )
#         else:
#             hep.histplot(
#                 mc_vals,
#                 bins=bin_edges,
#                 stack=do_stack,
#                 histtype="step",
#                 color=mc_colors,
#                 label=mc_labels,
#                 linewidth=1.3,
#                 ax=ax,
#             )

#         if do_stack:
#             hep.histplot(
#                 total_mc_vals,
#                 bins=bin_edges,
#                 histtype="step",
#                 color="black",
#                 linewidth=0.5,
#                 ax=ax,
#             )

#         if do_stack:
#             bkg_unc_cfg = config_page.get("bkg_unc_hist", {})
#             unc_hatch = "//" if bkg_unc_cfg.get("fill_style") == 3013 else None
#             unc_alpha = bkg_unc_cfg.get("alpha", 0.35)

#             y_up = total_mc_vals + total_mc_errs
#             y_dn = np.maximum(total_mc_vals - total_mc_errs, 0.0)

#             ax.fill_between(
#                 bin_edges[:-1],
#                 y_dn,
#                 y_up,
#                 step="post",
#                 facecolor="none",
#                 edgecolor="black",
#                 hatch=unc_hatch,
#                 alpha=unc_alpha,
#                 linewidth=0.8,
#                 label=bkg_unc_cfg.get("legend_title", "Bkg. uncertainty"),
#             )

#     else:
#         total_mc_errs = np.zeros(len(bin_edges) - 1, dtype=float)

#     # =====================================================
#     # Signals
#     # =====================================================

#     for s_val, s_col, s_lab in zip(sgn_vals, sgn_colors, sgn_labels):
#         hep.histplot(
#             s_val,
#             bins=bin_edges,
#             histtype="step",
#             color=s_col,
#             label=s_lab,
#             linestyle="--",
#             linewidth=1.5,
#             ax=ax,
#         )

#     # =====================================================
#     # Data
#     # =====================================================

#     if data_vals is not None:
#         ax.errorbar(
#             bin_centers,
#             data_vals,
#             yerr=data_errs,
#             fmt="o",
#             color="black",
#             markersize=5,
#             label=data_label_legend,
#         )

#     # =====================================================
#     # Ratio
#     # =====================================================

#     if has_ratio:
#         ratio_arrays = []
#         ratio_unc_low = None
#         ratio_unc_high = None

#         if has_sample_ratio:
#             denominator = ratio_candidates[ratio_reference_key]
#             denom_vals = denominator["values"]
#             denom_errs = denominator["errors"]

#             denom_rel_unc = np.divide(
#                 denom_errs,
#                 denom_vals,
#                 out=np.zeros_like(denom_errs, dtype=float),
#                 where=denom_vals != 0,
#             )
#             ratio_unc_high = 1.0 + denom_rel_unc
#             ratio_unc_low = np.maximum(1.0 - denom_rel_unc, 0.0)

#             rax.fill_between(
#                 bin_edges,
#                 np.r_[ratio_unc_low, ratio_unc_low[-1]],
#                 np.r_[ratio_unc_high, ratio_unc_high[-1]],
#                 step="post",
#                 facecolor="ghostwhite",
#                 edgecolor="black",
#                 hatch="//",
#                 alpha=0.5,
#                 zorder=1,
#             )

#             for sample_key, numerator in ratio_candidates.items():
#                 if sample_key == ratio_reference_key:
#                     continue

#                 num_vals = numerator["values"]
#                 num_errs = numerator["errors"]
#                 valid_ratio = (
#                     (denom_vals != 0)
#                     & np.isfinite(denom_vals)
#                     & np.isfinite(num_vals)
#                     & np.isfinite(num_errs)
#                 )

#                 ratio = np.divide(
#                     num_vals,
#                     denom_vals,
#                     out=np.full_like(num_vals, np.nan, dtype=float),
#                     where=valid_ratio,
#                 )
#                 ratio_err = np.abs(
#                     np.divide(
#                         num_errs,
#                         denom_vals,
#                         out=np.full_like(num_errs, np.nan, dtype=float),
#                         where=valid_ratio,
#                     )
#                 )

#                 ratio_arrays.append(ratio)
#                 ratio_arrays.append(ratio - ratio_err)
#                 ratio_arrays.append(ratio + ratio_err)
#                 draw_style = "--" if numerator.get("is_signal", False) else "-"

#                 rax.errorbar(
#                     bin_centers,
#                     ratio,
#                     yerr=ratio_err,
#                     fmt=".",
#                     color=numerator["color"],
#                     markersize=7,
#                     linestyle=draw_style,
#                     linewidth=1.0,
#                     label=numerator["name"],
#                     zorder=2,
#                 )

#             rax.set_ylabel(f"/ {denominator['name']}", fontsize=14)

#             if len(ratio_arrays) > 1:
#                 rax.legend(fontsize=9, frameon=False, ncol=2)

#         else:
#             valid_ratio = (
#                 (total_mc_vals != 0)
#                 & np.isfinite(total_mc_vals)
#                 & np.isfinite(data_vals)
#                 & np.isfinite(data_errs)
#             )

#             ratio = np.divide(
#                 data_vals,
#                 total_mc_vals,
#                 out=np.full_like(data_vals, np.nan, dtype=float),
#                 where=valid_ratio,
#             )

#             ratio_err = np.abs(
#                 np.divide(
#                     data_errs,
#                     total_mc_vals,
#                     out=np.full_like(data_errs, np.nan, dtype=float),
#                     where=valid_ratio,
#                 )
#             )

#             mc_rel_unc = np.divide(
#                 total_mc_errs,
#                 total_mc_vals,
#                 out=np.zeros_like(total_mc_errs, dtype=float),
#                 where=total_mc_vals != 0,
#             )

#             ratio_unc_high = 1.0 + mc_rel_unc
#             ratio_unc_low = np.maximum(1.0 - mc_rel_unc, 0.0)

#             rax.fill_between(
#                 bin_edges,
#                 np.r_[ratio_unc_low, ratio_unc_low[-1]],
#                 np.r_[ratio_unc_high, ratio_unc_high[-1]],
#                 step="post",
#                 facecolor="ghostwhite",
#                 edgecolor="black",
#                 hatch="//",
#                 alpha=0.5,
#                 zorder=1,
#             )

#             rax.errorbar(
#                 bin_centers,
#                 ratio,
#                 yerr=ratio_err,
#                 fmt=".",
#                 color="black",
#                 markersize=10,
#                 zorder=2,
#             )

#             ratio_arrays.append(ratio)
#             ratio_arrays.append(ratio - ratio_err)
#             ratio_arrays.append(ratio + ratio_err)
#             rax.set_ylabel("Data/MC", fontsize=14)

#         rax.axhline(
#             1.0,
#             color="black",
#             linestyle="--",
#             linewidth=1.0,
#         )

#         set_ratio_axis_range(
#             rax,
#             ratio_arrays,
#             ratio_unc_low=ratio_unc_low,
#             ratio_unc_high=ratio_unc_high,
#         )

#     # =====================================================
#     # Axes
#     # =====================================================

#     x_label = hist_cfg.get("x_title", variable)

#     for mu_idx in [1, 2]:
#         if f"mu{mu_idx}" in variable:
#             x_label = x_label.format(mu_idx=mu_idx)
#     for jet_idx in [1, 2]:
#         if f"vbfjet{jet_idx}" in variable:
#             x_label = x_label.format(jet_idx=jet_idx)
#     if variable.split("_")[0] == "leadingjet":
#         x_label = x_label.format(jname="leading j")
#     if variable.split("_")[0] == "subleadingjet":
#         x_label = x_label.format(jname="subleading j")
#     if variable.split("_")[0] == "thirdjet":
#         x_label = x_label.format(jname="third j")
#     if variable.split("_")[0] == "fourthjet":
#         x_label = x_label.format(jname="fourth j")
#     if has_ratio:
#         rax.set_xlabel(x_label, fontsize=20)
#         ax.get_xaxis().set_visible(False)
#     else:
#         ax.set_xlabel(x_label, fontsize=20)

#     ax.set_ylabel(hist_cfg.get("y_title", "Events"), fontsize=20)
#     ax.set_xlim(bin_edges[0] * 0.99, bin_edges[-1] * 1.01)

#     want_log_y = config_page.get("wantLogY", False)
#     ax.set_yscale("log" if want_log_y else "linear")

#     visible_arrays = list(mc_vals)

#     if data_vals is not None:
#         visible_arrays.append(data_vals)

#     for s_val in sgn_vals:
#         visible_arrays.append(s_val)

#     y_max = safe_nanmax(visible_arrays, default=1.0)

#     max_factor = (
#         hist_cfg.get("max_y_sf", 1.2)
#         if not want_log_y
#         else 100 ** hist_cfg.get("max_y_sf", 1.0)
#     )

#     ax.set_ylim(top=y_max * max_factor)

#     if want_log_y:
#         ax.set_ylim(bottom=min(0.1, y_max * 1e-5))
#     else:
#         ax.set_ylim(bottom=0.0)

#     # =====================================================
#     # Legend
#     # =====================================================

#     legend_cfg = config_page.get("legend_mplhep", {})

#     ax.legend(
#         loc="upper right",
#         facecolor=legend_cfg.get("fill_color", "white"),
#         frameon=True,
#         fontsize=legend_cfg.get("text_size", 0.16) * 110,
#         framealpha=0.2,
#         ncol=legend_cfg.get("ncols", 2),
#         handleheight=1.4,
#         labelspacing=0.2,
#     )

#     # =====================================================
#     # CMS label
#     # =====================================================
#     category_names = {
#         "mass_inclusive_baseline": "baseline incl",
#         "mass_inclusive_ggF": "ggF incl",
#         "mass_inclusive_VBF": "VBF incl",
#         "Z_Sideband_baseline": "baseline Z",
#         "Z_Sideband_ggF": "ggF Z",
#         "Z_Sideband_VBF": "VBF Z",

#         "Z_sideband_baseline": "baseline Z",
#         "Z_sideband_ggF": "ggF Z",
#         "Z_sideband_VBF": "VBF Z",

#         "Signal_Fit_ggF": "ggF H",
#         "Signal_Fit_VBF": "VBF H",
#         "Signal_Fit_baseline": "baseline H",




#         "mass_inclusive_baseline_lowPtTT": "baseline incl",
#         "mass_inclusive_ggF_lowPtTT": "ggF incl",
#         "mass_inclusive_VBF_lowPtTT": "VBF incl",
#         "Z_Sideband_baseline_lowPtTT": "baseline Z",
#         "Z_Sideband_ggF_lowPtTT": "ggF Z",
#         "Z_Sideband_VBF_lowPtTT": "VBF Z",

#         "Z_sideband_baseline_lowPtTT": "baseline Z",
#         "Z_sideband_ggF_lowPtTT": "ggF Z",
#         "Z_sideband_VBF_lowPtTT": "VBF Z",

#         "Signal_Fit_ggF_lowPtTT": "ggF H",
#         "Signal_Fit_VBF_lowPtTT": "VBF H",
#         "Signal_Fit_baseline_lowPtTT": "baseline H",
#     }
#     lumi_val = config_page.get("lumi_text", {}).get("text", "1.0")
#     cms_tag = f"Preliminary {category_names[category]}" # config_page.get("cms_label", {}).get("tag",
#     cms_com = config_page.get("cms_label", {}).get("com", "13.6")

#     hep.cms.label(
#         ax=ax,
#         data=(data_vals is not None),
#         label=cms_tag,
#         lumi=float(lumi_val),
#         com=float(cms_com),
#         loc=0,
#         fontsize=20,
#     )



#     # ax.text(
#     #     0.22,
#     #     0.96,
#     #     category_names[category],
#     #     # " ".join(c for c in category.split("_")),
#     #     transform=ax.transAxes,
#     #     fontsize=12,
#     #     verticalalignment="top",
#     #     horizontalalignment="right",
#     # )

#     # =====================================================
#     # Save
#     # =====================================================

#     fig.savefig(f"{out_name}.png", bbox_inches="tight")
#     fig.savefig(f"{out_name}.pdf", bbox_inches="tight")

#     print(f"{out_name}.png")

#     plt.close(fig)
