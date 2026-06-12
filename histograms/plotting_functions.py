import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import mplhep as hep

from common.helpers import *

plt.style.use(hep.style.CMS)


def normalize_sample_name(name):
    return os.path.splitext(os.path.basename(name))[0]


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

        if ratio_reference in aliases or normalized_reference in aliases:
            return key

    return None


def set_ratio_axis_range(rax, ratio_arrays, ratio_unc_low=None, ratio_unc_high=None):
    ymin = 0.5
    ymax = 1.5

    rax.set_ylim(ymin, ymax)

    ticks = np.round(np.arange(ymin, ymax + 0.001, 0.2), 1)
    rax.yaxis.set_major_locator(mticker.FixedLocator(ticks))
    rax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    rax.grid(axis="y", which="major", linestyle=":", linewidth=0.6, alpha=0.5)


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
):
    """
    Genera uno stacked plot con:
      - background in stack
      - signal overlay
      - data opzionale
      - ratio Data/MC opzionale
      - blinding sui dati
    """
    mc_vals = []
    mc_colors = []
    mc_labels = []
    mc_integrals = []
    mc_errs = []
    mc_keys = []

    sgn_vals = []
    sgn_errs = []
    sgn_colors = []
    sgn_labels = []
    sgn_keys = []

    ratio_candidates = {}
    data_key = None

    data_vals = None
    data_errs = None
    data_label_legend = None

    bin_edges = None

    hist_entry = findBinEntry(config_page, variable)
    hist_cfg = config_page.get(hist_entry, {}) if hist_entry is not None else {}

    divide_by_bin_width = hist_cfg.get("divide_by_bin_width", False)
    include_overflow = hist_cfg.get("include_overflow", False)
    auto_trim_empty_edges = hist_cfg.get(
        "auto_trim_empty_edges",
        config_page.get("auto_trim_empty_edges", True),
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

        hist_integral = root_hist.Integral()
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
            data_key = sample_id

            ratio_candidates[sample_id] = {
                "name": sample_label,
                "values": content,
                "errors": errors,
                "color": "black",
                "is_data": True,
                "is_signal": False,
            }

            data_label_base = sample_label

            if blind_range is not None and blind_mask is not None and np.any(blind_mask):
                data_label_legend = f"{data_label_base} [blinded]"
            else:
                data_label_legend = f"{data_label_base} [{hist_integral:.2f}]"

        elif sample_info["is_signal"]:

            sgn_vals.append(content)
            sgn_errs.append(errors)
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
            }

    if bin_edges is None:
        print(f"  [WARNING] Istogramma vuoto o mancante: {variable}")
        return

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
    has_ratio = draw_ratio and (has_default_ratio or has_sample_ratio)

    if ratio_reference is not None and ratio_reference_key is None:
        print(
            f"  [WARNING] Ratio reference '{ratio_reference}' non trovato "
            f"per {variable}. Uso Data/MC se disponibile."
        )

    if has_ratio:
        fig, (ax, rax) = plt.subplots(
            2,
            1,
            figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
            sharex=True,
            gridspec_kw={
                "height_ratios": [3, 1],
                "hspace": 0.05,
            },
        )
    else:
        fig, ax = plt.subplots(
            1,
            1,
            figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
        )
        rax = None

    # =====================================================
    # Background stack
    # =====================================================

    total_mc_vals = np.zeros(len(bin_edges) - 1, dtype=float)
    total_mc_errs2 = np.zeros(len(bin_edges) - 1, dtype=float)

    if mc_vals:
        total_mc_vals = np.sum(mc_vals, axis=0)
        total_mc_errs2 = np.sum([err ** 2 for err in mc_errs], axis=0)
        total_mc_errs = np.sqrt(total_mc_errs2)

        if fill_hists:
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

        if do_stack:
            hep.histplot(
                total_mc_vals,
                bins=bin_edges,
                histtype="step",
                color="black",
                linewidth=0.5,
                ax=ax,
            )

        if do_stack:
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
                rax.legend(fontsize=9, frameon=False, ncol=2)

        else:
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

            mc_rel_unc = np.divide(
                total_mc_errs,
                total_mc_vals,
                out=np.zeros_like(total_mc_errs, dtype=float),
                where=total_mc_vals != 0,
            )

            ratio_unc_high = 1.0 + mc_rel_unc
            ratio_unc_low = np.maximum(1.0 - mc_rel_unc, 0.0)

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

            rax.errorbar(
                bin_centers,
                ratio,
                yerr=ratio_err,
                fmt=".",
                color="black",
                markersize=10,
                zorder=2,
            )

            ratio_arrays.append(ratio)
            ratio_arrays.append(ratio - ratio_err)
            ratio_arrays.append(ratio + ratio_err)
            rax.set_ylabel("Data/MC", fontsize=14)

        rax.axhline(
            1.0,
            color="black",
            linestyle="--",
            linewidth=1.0,
        )

        set_ratio_axis_range(
            rax,
            ratio_arrays,
            ratio_unc_low=ratio_unc_low,
            ratio_unc_high=ratio_unc_high,
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
        "Z_Sideband_baseline": "baseline Z",
        "Z_Sideband_ggF": "ggF Z",
        "Z_Sideband_VBF": "VBF Z",

        "Z_sideband_baseline": "baseline Z",
        "Z_sideband_ggF": "ggF Z",
        "Z_sideband_VBF": "VBF Z",

        "Signal_Fit_ggF": "ggF H",
        "Signal_Fit_VBF": "VBF H",
        "Signal_Fit_baseline": "baseline H",




        "mass_inclusive_baseline_lowPtTT": "baseline incl",
        "mass_inclusive_ggF_lowPtTT": "ggF incl",
        "mass_inclusive_VBF_lowPtTT": "VBF incl",
        "Z_Sideband_baseline_lowPtTT": "baseline Z",
        "Z_Sideband_ggF_lowPtTT": "ggF Z",
        "Z_Sideband_VBF_lowPtTT": "VBF Z",

        "Z_sideband_baseline_lowPtTT": "baseline Z",
        "Z_sideband_ggF_lowPtTT": "ggF Z",
        "Z_sideband_VBF_lowPtTT": "VBF Z",

        "Signal_Fit_ggF_lowPtTT": "ggF H",
        "Signal_Fit_VBF_lowPtTT": "VBF H",
        "Signal_Fit_baseline_lowPtTT": "baseline H",
    }
    lumi_val = config_page.get("lumi_text", {}).get("text", "1.0")
    cms_tag = f"Preliminary {category_names[category]}" # config_page.get("cms_label", {}).get("tag",
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



    # ax.text(
    #     0.22,
    #     0.96,
    #     category_names[category],
    #     # " ".join(c for c in category.split("_")),
    #     transform=ax.transAxes,
    #     fontsize=12,
    #     verticalalignment="top",
    #     horizontalalignment="right",
    # )

    # =====================================================
    # Save
    # =====================================================

    fig.savefig(f"{out_name}.png", bbox_inches="tight")
    fig.savefig(f"{out_name}.pdf", bbox_inches="tight")

    print(f"{out_name}.png")

    plt.close(fig)
