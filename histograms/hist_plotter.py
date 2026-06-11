#!/usr/bin/env python3

import ROOT
import sys
import os
import argparse
import time
import numpy as np
import matplotlib.pyplot as plt
import mplhep as hep

# =========================================================
# Global style
# =========================================================

plt.style.use(hep.style.CMS)

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import common.utilities as utilities
from common.helpers import *

HEADERS = ["analysis/AnalysisTools.h"]

for header in HEADERS:
    utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")


# =========================================================
# Sample helpers
# =========================================================

def normalize_sample_name(name):
    """
    Normalizza il nome del sample.

    Esempi:
      DY.root -> DY
      /path/to/TT.root -> TT
      DY -> DY
    """
    return os.path.splitext(os.path.basename(name))[0]


def classify_sample(sample_name, process_cfg):
    """
    Classifica il sample usando process_names.yaml.

    Regole:
      - is_data: True   -> data
      - is_signal: True -> signal
      - altrimenti      -> background
    """
    if sample_name not in process_cfg:
        return None

    cfg = process_cfg[sample_name]

    if cfg.get("skip_plotting", False):
        return None

    is_data = bool(cfg.get("is_data", False))
    is_signal = bool(cfg.get("is_signal", False))

    if is_data and is_signal:
        raise RuntimeError(
            f"Sample {sample_name} è marcato sia come data che come signal."
        )

    if is_data:
        sample_type = "data"
    elif is_signal:
        sample_type = "signal"
    else:
        sample_type = "background"

    return {
        "type": sample_type,
        "is_data": is_data,
        "is_signal": is_signal,
        "color": cfg.get(
            "color_mplhep",
            cfg.get("color", "black"),
        ),
        "name": cfg.get("name", sample_name),
    }


def expand_requested_samples(requested_samples, plot_groups_cfg):
    if requested_samples is None:
        return None

    expanded = set()
    background_groups = plot_groups_cfg.get("background_groups", {})

    for sample in requested_samples:
        if sample in background_groups:
            expanded.update(get_group_members(background_groups[sample]))
        else:
            expanded.add(sample)

    return expanded


def get_group_members(group_cfg):
    members = []

    for key in ("processes", "sub_processes", "datasets"):
        members.extend(group_cfg.get(key, []))

    return members


def get_group_color(group_cfg, fallback):
    return group_cfg.get("color_mplhep", group_cfg.get("color", fallback))


def make_group_process(group_name, group_cfg, members, input_processes):
    output_process = {
        "input": ",".join(input_processes[name]["input"] for name in members),
        "color": get_group_color(group_cfg, input_processes[members[0]]["color"]),
        "name": group_cfg.get("name", group_name),
        "is_data": False,
        "is_signal": False,
        "type": "background",
        "hists": {},
    }

    for member_name in members:
        member_info = input_processes[member_name]

        for category, hists in member_info["hists"].items():
            output_process["hists"].setdefault(category, {})

            for hist_name, hist in hists.items():
                group_hists = output_process["hists"][category]

                if hist_name not in group_hists:
                    clone_name = f"{group_name}_{category}_{hist_name}"
                    group_hists[hist_name] = clone_hist_for_group(hist, clone_name)
                else:
                    group_hists[hist_name].Add(hist)

    return output_process


def clone_hist_for_group(hist, name):
    safe_name = name.replace("/", "_").replace(" ", "_")
    cloned = hist.Clone(safe_name)
    cloned.SetDirectory(0)
    return cloned


def apply_signal_styles(input_processes, plot_groups_cfg):
    signal_styles = plot_groups_cfg.get("signal_styles", {})

    for process_name, style_cfg in signal_styles.items():
        if process_name not in input_processes:
            continue

        if "name" in style_cfg:
            input_processes[process_name]["name"] = style_cfg["name"]

        if "color" in style_cfg:
            input_processes[process_name]["color"] = style_cfg["color"]


def apply_background_groups(input_processes, plot_groups_cfg, active_group_names=None):
    """
    Merge background macro-samples into plotting groups.

    Processes not listed in config/plot/process_groups.yaml are kept unchanged.
    Data and signals are never merged here.
    """
    background_groups = plot_groups_cfg.get("background_groups", {})

    if active_group_names is not None:
        background_groups = {
            group_name: group_cfg
            for group_name, group_cfg in background_groups.items()
            if group_name in active_group_names
        }

    if not background_groups:
        return input_processes

    output_processes = {}
    grouped_processes = set()

    for group_name, group_cfg in background_groups.items():
        member_names = get_group_members(group_cfg)
        members = [
            name
            for name in member_names
            if name in input_processes
            and name not in grouped_processes
            and not input_processes[name].get("is_data", False)
            and not input_processes[name].get("is_signal", False)
        ]

        if len(members) == 0:
            continue

        grouped_processes.update(members)

        output_processes[group_name] = make_group_process(
            group_name,
            group_cfg,
            members,
            input_processes,
        )

    other_group_cfg = plot_groups_cfg.get("other_group", {})
    use_other_group = (
        active_group_names is None
        and other_group_cfg.get("enabled", True)
    )

    if use_other_group:
        other_name = other_group_cfg.get("key", "OTHER")
        other_members = [
            process_name
            for process_name, process_info in input_processes.items()
            if process_name not in grouped_processes
            and not process_info.get("is_data", False)
            and not process_info.get("is_signal", False)
        ]

        if len(other_members) > 0:
            grouped_processes.update(other_members)
            output_processes[other_name] = make_group_process(
                other_name,
                other_group_cfg,
                other_members,
                input_processes,
            )

    for process_name, process_info in input_processes.items():
        if process_name in grouped_processes:
            continue

        output_processes[process_name] = process_info

    return output_processes


def apply_plot_groups(input_processes, plot_groups_cfg, active_group_names=None):
    apply_signal_styles(input_processes, plot_groups_cfg)
    return apply_background_groups(
        input_processes,
        plot_groups_cfg,
        active_group_names=active_group_names,
    )


# =========================================================
# Helpers for histogram reading / blinding
# =========================================================

def get_available_histograms(root_file, region_path, isDY=False, recursive=True):
    """
    Returns:
        [(histogram, hist_name), ...]
    """
    output = []

    directory = root_file.Get(region_path)
    scale_factor_for_DY_XS = 2094.2 / (6688 / 3) if isDY else 1.0

    if not directory:
        return output

    def scan_dir(tdir, prefix=""):
        for key in tdir.GetListOfKeys():
            obj = key.ReadObj()
            name = key.GetName()

            if obj.InheritsFrom("TH1"):
                hist_name = f"{prefix}{name}" if prefix else name

                hist = obj.Clone(f"{hist_name}_clone")
                hist.SetDirectory(0)
                hist.Scale(scale_factor_for_DY_XS)

                output.append((hist, hist_name))

            elif recursive and obj.InheritsFrom("TDirectory"):
                new_prefix = f"{prefix}{name}/" if prefix else f"{name}/"
                scan_dir(obj, new_prefix)

    scan_dir(directory)

    return output


def get_bins_and_content(root_hist, want_overflow=True, divide_by_bin_width=False):
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

    sgn_vals = []
    sgn_colors = []
    sgn_labels = []

    data_vals = None
    data_errs = None
    data_label_legend = None

    bin_edges = None

    hist_entry = findBinEntry(config_page, variable)
    hist_cfg = config_page.get(hist_entry, {}) if hist_entry is not None else {}

    divide_by_bin_width = hist_cfg.get("divide_by_bin_width", False)
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
            want_overflow=True,
            divide_by_bin_width=divide_by_bin_width,
        )

        if bin_edges is None:
            bin_edges = edges

        hist_integral = root_hist.Integral()

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

            data_label_base = sample_info.get("name", "Data")

            if blind_range is not None and blind_mask is not None and np.any(blind_mask):
                data_label_legend = f"{data_label_base} [blinded]"
            else:
                data_label_legend = f"{data_label_base} [{hist_integral:.2f}]"

        elif sample_info["is_signal"]:

            sgn_vals.append(content)
            sgn_colors.append(sample_info["color"])
            sgn_labels.append(f"{sample_info['name']} [{hist_integral:.2f}]")

        else:

            mc_vals.append(content)
            mc_colors.append(sample_info["color"])
            mc_labels.append(f"{sample_info['name']} [{hist_integral:.2f}]")
            mc_integrals.append(hist_integral)

    if bin_edges is None:
        print(f"  [WARNING] Istogramma vuoto o mancante: {variable}")
        return

    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    # =====================================================
    # Sort backgrounds by yield
    # =====================================================

    if mc_vals:
        idx_sort = np.argsort(mc_integrals)

        mc_vals = [mc_vals[i] for i in idx_sort]
        mc_colors = [mc_colors[i] for i in idx_sort]
        mc_labels = [mc_labels[i] for i in idx_sort]

    # =====================================================
    # Canvas
    # =====================================================

    canvas_size = config_page["page_setup"].get("canvas_size", [900, 800])
    has_ratio = data_vals is not None and len(mc_vals) > 0

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

        hep.histplot(
            mc_vals,
            bins=bin_edges,
            stack=True,
            histtype="fill",
            color=mc_colors,
            label=mc_labels,
            edgecolor="black",
            linewidth=0.5,
            ax=ax,
        )

        for sample_id, sample_info in samples_dict.items():

            if sample_info["is_data"] or sample_info["is_signal"]:
                continue

            if category not in sample_info["hists"]:
                continue

            if variable not in sample_info["hists"][category]:
                continue

            h = sample_info["hists"][category][variable]

            _, c, e = get_bins_and_content(
                h,
                want_overflow=True,
                divide_by_bin_width=divide_by_bin_width,
            )

            total_mc_vals += c
            total_mc_errs2 += e ** 2

        total_mc_errs = np.sqrt(total_mc_errs2)

        hep.histplot(
            total_mc_vals,
            bins=bin_edges,
            histtype="step",
            color="black",
            linewidth=0.5,
            ax=ax,
        )

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

        y_ratio_up = 1.0 + mc_rel_unc
        y_ratio_dn = np.maximum(1.0 - mc_rel_unc, 0.0)

        rax.fill_between(
            bin_centers,
            y_ratio_dn,
            y_ratio_up,
            step="mid",
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

        rax.axhline(
            1.0,
            color="black",
            linestyle="--",
            linewidth=1.0,
        )

        finite_ratio = ratio[np.isfinite(ratio)]

        delta = np.abs(finite_ratio - 1.0).mean() if len(finite_ratio) else 0.4
        delta = max(delta, 0.1)

        rax.set_ylim(
            round(1 - delta, 2) * 0.9,
            round(1 + delta, 2) * 1.1,
        )

        rax.set_ylabel("Data/MC", fontsize=14)

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
        labelspacing=0.1,
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


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--era",
        required=True,
        type=str,
        help="Era, e.g. 2022, 2022EE, 2023, 2023BPix",
    )

    parser.add_argument(
        "--input",
        required=True,
        type=str,
        help="Directory contenente i file ROOT dei macro-samples",
    )

    parser.add_argument(
        "--output",
        default="plots_output",
        type=str,
        help="Output directory for plots",
    )

    parser.add_argument(
        "--region",
        default="Z_sideband_baseline",
        type=str,
        help="Region to plot",
    )

    parser.add_argument(
        "--samples",
        nargs="+",
        default=None,
        help=(
            "Lista di macro-samples da processare, es: "
            "DY TT SingleTop Data ggH. "
            "Il nome deve corrispondere al file ROOT senza .root, "
            "a una chiave in process_names.yaml, oppure a un gruppo "
            "in config/plot/process_groups.yaml."
        ),
    )

    parser.add_argument(
        "--systematics",
        action="store_true",
        help="Include systematic uncertainties",
    )

    parser.add_argument(
        "--wantData",
        action="store_true",
        help="Include data in plots and draw ratio",
    )

    parser.add_argument(
        "--wantLogY",
        action="store_true",
        help="Set y-axis to log scale",
    )

    parser.add_argument(
        "--rebin",
        action="store_true",
        help="Rebin histograms",
    )

    args = parser.parse_args()

    startTime = time.time()

    # =====================================================
    # Configs
    # =====================================================

    cfg_dir = os.path.join(
        os.environ["ANALYSIS_PATH"],
        "config",
        args.era,
    )

    main_cfg = utilities.get_config(
        os.path.join(cfg_dir, "maincfg.yaml")
    )

    process_cfg = utilities.get_config(
        os.path.join(cfg_dir, "process_names.yaml")
    )

    plot_groups_cfg = utilities.get_config(
        os.path.join(
            os.environ["ANALYSIS_PATH"],
            "config",
            "plot",
            "process_groups.yaml",
        )
    )

    sel_cfg = utilities.get_config(
        os.path.join(cfg_dir, "selections.yaml")
    )

    syst_cfg = utilities.get_config(
        os.path.join(cfg_dir, "systematics.yaml")
    )

    hist_cfg = utilities.get_config(
        os.path.join(
            os.environ["ANALYSIS_PATH"],
            "config",
            "plot",
            "histograms.yaml",
        )
    )

    additional_cfg = utilities.get_config(
        os.path.join(
            os.environ["ANALYSIS_PATH"],
            "config",
            "plot",
            f"{args.era}.yaml",
        )
    )

    page_cfg = utilities.get_config(
        os.path.join(
            os.environ["ANALYSIS_PATH"],
            "config",
            "plot",
            "cms_stacked.yaml",
        )
    )

    region_path = args.region

    config_setup = {
        **page_cfg,
        **additional_cfg,
        **hist_cfg,
    }

    config_setup["wantLogY"] = args.wantLogY

    # =====================================================
    # Requested samples
    # =====================================================

    requested_samples = None
    requested_plot_groups = None

    if args.samples is not None:

        requested_samples_raw = set(
            normalize_sample_name(s)
            for s in args.samples
        )

        requested_plot_groups = {
            sample
            for sample in requested_samples_raw
            if sample in plot_groups_cfg.get("background_groups", {})
        }

        requested_samples = expand_requested_samples(
            requested_samples_raw,
            plot_groups_cfg,
        )

        print("\nRequested macro-samples:")

        for sample in sorted(requested_samples_raw):

            if (
                sample not in process_cfg
                and sample not in plot_groups_cfg.get("background_groups", {})
            ):
                print(
                    f"  [WARNING] {sample} non è presente in process_names.yaml "
                    "o process_groups.yaml"
                )
                continue

            if sample in plot_groups_cfg.get("background_groups", {}):
                members = get_group_members(
                    plot_groups_cfg["background_groups"][sample]
                )
                print(f"  {sample}: background group ({', '.join(members)})")
                continue

            info = classify_sample(sample, process_cfg)

            if info is None:
                print(f"  [SKIP] {sample}")
            else:
                print(f"  {sample}: {info['type']}")

    # =====================================================
    # Read input ROOT files
    # =====================================================

    input_processes = {}
    all_found_variables = set()

    for indir, subdirs, infiles in os.walk(args.input):

        for inFile in sorted(infiles):
            if not inFile.endswith(".root"):
                continue

            full_path = os.path.join(indir, inFile)

            process_name = normalize_sample_name(inFile)

            if requested_samples is not None and process_name not in requested_samples:
                continue

            sample_info = classify_sample(process_name, process_cfg)

            if sample_info is None:
                print(
                    f"[WARNING] Sample {process_name} non configurato "
                    f"o skippato. File: {full_path}"
                )
                continue

            # print(
            #     f"[INFO] Loading {process_name} "
            #     f"as {sample_info['type']} from {full_path}"
            # )

            root_file = ROOT.TFile.Open(full_path, "READ")

            if not root_file or root_file.IsZombie():
                print(f"[WARNING] File ROOT non valido: {full_path}")
                continue

            input_processes[process_name] = {
                "input": full_path,
                "color": sample_info["color"],
                "name": sample_info["name"],
                "is_data": sample_info["is_data"],
                "is_signal": sample_info["is_signal"],
                "type": sample_info["type"],
                "hists": {
                    region_path: {},
                },
            }

            isDY = process_name == "DY"

            available_hists = get_available_histograms(
                root_file,
                region_path,
                isDY=isDY,
                recursive=True,
            )

            for available_hist, hist_name in available_hists:

                var_entry = findBinEntry(hist_cfg, hist_name)

                if var_entry is None or var_entry not in hist_cfg:
                    print(
                        f"[WARNING] Nessuna configurazione trovata "
                        f"per {hist_name}. Skip."
                    )
                    continue

                if "x_rebin" in hist_cfg[var_entry]:
                    bins_to_compute = findNewBins(
                        hist_cfg,
                        var_entry,
                        dir_name=region_path,
                    )
                    new_bins = getNewBins(bins_to_compute)
                else:
                    new_bins = hist_cfg[var_entry].get("x_bins", [])

                rebinned_hist = available_hist

                if args.rebin:
                    rebinned_hist = RebinHisto(
                        available_hist,
                        new_bins,
                        process_name,
                        wantOverflow=False,
                    )

                if rebinned_hist is None:
                    continue

                rebinned_hist.SetDirectory(0)

                if is_valid_histogram(rebinned_hist):
                    input_processes[process_name]["hists"][region_path][hist_name] = (
                        rebinned_hist
                    )
                    all_found_variables.add(hist_name)

            root_file.Close()

    input_processes = apply_plot_groups(
        input_processes,
        plot_groups_cfg,
        active_group_names=requested_plot_groups,
    )

    # =====================================================
    # Summary
    # =====================================================

    # print("\nLoaded samples:")

    # for sample, info in input_processes.items():
    #     n_hists = len(info["hists"].get(region_path, {}))
    #     print(
    #         f"  {sample:20s} "
    #         f"type={info['type']:10s} "
    #         f"n_hists={n_hists}"
    #     )

    # =====================================================
    # Produce plots
    # =====================================================

    if len(all_found_variables) == 0:

        print(
            f"[ERROR] Nessun istogramma valido trovato "
            f"per la regione {region_path}."
        )

    else:

        output_dir_path = os.path.join(
            args.output,
            args.era,
            region_path,
        )

        os.makedirs(output_dir_path, exist_ok=True)

        print(
            f"\n--> Generazione di {len(all_found_variables)} "
            f"plot strutturati in corso..."
        )

        for variable in sorted(all_found_variables):

            plot_base_path = os.path.join(
                output_dir_path,
                variable,
            )

            os.makedirs(
                os.path.dirname(plot_base_path),
                exist_ok=True,
            )

            make_stacked_plot(
                samples_dict=input_processes,
                config_page=config_setup,
                category=region_path,
                variable=variable,
                out_name=plot_base_path,
                want_data=args.wantData,
            )

    print(
        f"\n[SUCCESS] Elaborazione completata "
        f"in {time.time() - startTime:.2f} secondi."
    )


# #!/usr/bin/env python3

# import ROOT
# import sys
# import os
# import argparse
# import time
# import json
# import numpy as np
# import matplotlib.pyplot as plt
# import mplhep as hep

# # Configurazione dello stile CMS globale
# plt.style.use(hep.style.CMS)

# if __name__ == "__main__":
#     sys.path.append(os.environ["ANALYSIS_PATH"])

# import common.utilities as utilities
# from common.helpers import *

# HEADERS = ["analysis/AnalysisTools.h"]
# for header in HEADERS:
#     utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")


# # =========================================================
# # Helpers for histogram reading / blinding
# # =========================================================
# def get_available_histograms(root_file, region_path, isDY=False, recursive=True):
#     """
#     Returns:
#         [(histogram, hist_name), ...]
#     """
#     output = []

#     directory = root_file.Get(region_path)
#     scale_factor_for_DY_XS = 2094.2 / (6688 / 3) if isDY else 1.0

#     if not directory:
#         return output

#     def scan_dir(tdir, prefix=""):
#         for key in tdir.GetListOfKeys():
#             obj = key.ReadObj()
#             name = key.GetName()

#             if obj.InheritsFrom("TH1"):
#                 hist_name = f"{prefix}{name}" if prefix else name
#                 obj.Scale(scale_factor_for_DY_XS)
#                 output.append((obj, hist_name))

#             elif recursive and obj.InheritsFrom("TDirectory"):
#                 new_prefix = f"{prefix}{name}/" if prefix else f"{name}/"
#                 scan_dir(obj, new_prefix)

#     scan_dir(directory)
#     return output


# def get_bins_and_content(root_hist, want_overflow=True, divide_by_bin_width=False):
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
#         # Overflow nell'ultimo bin visibile
#         content[-1] += root_hist.GetBinContent(n_bins + 1)
#         errors[-1] = np.sqrt(errors[-1] ** 2 + root_hist.GetBinError(n_bins + 1) ** 2)

#         # Underflow nel primo bin visibile
#         content[0] += root_hist.GetBinContent(0)
#         errors[0] = np.sqrt(errors[0] ** 2 + root_hist.GetBinError(0) ** 2)

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


# def get_blind_range_for_category(hist_cfg, category):
#     """
#     Legge blind_range dalla configurazione dell'istogramma.

#     Supporta entrambi i formati:

#       mll:
#         blind_range: [115, 130]

#     oppure:

#       mll:
#         blind_range:
#           Signal_Fit: [115, 130]
#           Some_Other_Category: [100, 150]

#     Nel secondo caso applica il blinding solo se category matcha una chiave.
#     """
#     blind_range = hist_cfg.get("blind_range", None)

#     if blind_range is None:
#         return None

#     # Formato globale: blind_range: [xmin, xmax]
#     if isinstance(blind_range, (list, tuple)):
#         if len(blind_range) != 2:
#             print(f"  [WARNING] blind_range malformato: {blind_range}")
#             return None
#         return [float(blind_range[0]), float(blind_range[1])]

#     # Formato per categoria:
#     # blind_range:
#     #   Signal_Fit: [xmin, xmax]
#     if isinstance(blind_range, dict):
#         category_range = blind_range.get(category, None)
#         if category_range is None:
#             return None
#         if not isinstance(category_range, (list, tuple)) or len(category_range) != 2:
#             print(f"  [WARNING] blind_range malformato per categoria {category}: {category_range}")
#             return None
#         return [float(category_range[0]), float(category_range[1])]
#     print(blind_range)
#     print(f"  [WARNING] Tipo non supportato per blind_range: {type(blind_range)}")
#     return None


# def apply_blind_range(edges, content, errors, blind_range=None):
#     """
#     Applica il blinding ai bin il cui centro cade dentro blind_range = [xmin, xmax].
#     Usa NaN per il contenuto: matplotlib non disegna quei punti/bin nei dati.
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
#     Calcola il massimo ignorando NaN/inf su una lista di array.
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


# # =========================================================
# # Core Drawing Core (Matplotlib + mplhep)
# # =========================================================
# def make_stacked_plot(samples_dict, config_page, category, variable, out_name, want_data=True):
#     """
#     Genera uno stacked plot con:
#       - stack dei background
#       - segnali overlay
#       - dati opzionali
#       - ratio Data/MC opzionale
#       - blinding sui dati, se configurato per variabile/categoria
#     """
#     mc_vals, mc_colors, mc_labels, mc_integrals = [], [], [], []
#     sgn_vals, sgn_colors, sgn_labels = [], [], []
#     data_vals, data_errs = None, None
#     data_label_legend = None
#     bin_edges = None

#     hist_entry = findBinEntry(config_page, variable)
#     hist_cfg = config_page.get(hist_entry, {}) if hist_entry is not None else {}

#     divide_by_bin_width = hist_cfg.get("divide_by_bin_width", False)
#     blind_range = get_blind_range_for_category(hist_cfg, category)

#     if blind_range is not None:
#         print(f"  [BLIND] {variable} in category {category}: range {blind_range}")

#     # 1. Separazione campioni: data / signal / background
#     for sample_id, sample_info in samples_dict.items():
#         if category not in sample_info["hists"]:
#             continue
#         if variable not in sample_info["hists"][category]:
#             continue

#         root_hist = sample_info["hists"][category][variable]
#         edges, content, errors = get_bins_and_content(
#             root_hist,
#             want_overflow=True,
#             divide_by_bin_width=divide_by_bin_width,
#         )

#         if bin_edges is None:
#             bin_edges = edges

#         hist_integral = root_hist.Integral()

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

#             data_label_base = sample_info.get("name", "Data")
#             if blind_range is not None and blind_mask is not None and np.any(blind_mask):
#                 data_label_legend = f"{data_label_base} [blinded]"
#             else:
#                 data_label_legend = f"{data_label_base} [{hist_integral:.2f}]"

#         elif sample_info["is_signal"]:
#             sgn_vals.append(content)
#             sgn_colors.append(sample_info["color"])
#             sgn_labels.append(f"{sample_info['name']} [{hist_integral:.2f}]")

#         else:
#             mc_vals.append(content)
#             mc_colors.append(sample_info["color"])
#             mc_labels.append(f"{sample_info['name']} [{hist_integral:.2f}]")
#             mc_integrals.append(hist_integral)

#     if bin_edges is None:
#         print(f"  [WARNING] Istogramma vuoto o mancante per la variabile: {variable}")
#         return

#     bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

#     # 2. Ordinamento background per yield crescente
#     if mc_vals:
#         idx_sort = np.argsort(mc_integrals)
#         mc_vals = [mc_vals[i] for i in idx_sort]
#         mc_colors = [mc_colors[i] for i in idx_sort]
#         mc_labels = [mc_labels[i] for i in idx_sort]

#     # 3. Canvas: main pad + ratio pad se ci sono dati e MC
#     canvas_size = config_page["page_setup"].get("canvas_size", [900, 800])
#     has_ratio = data_vals is not None and len(mc_vals) > 0

#     if has_ratio:
#         fig, (ax, rax) = plt.subplots(
#             2,
#             1,
#             figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
#             sharex=True,
#             gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05},
#         )
#     else:
#         fig, ax = plt.subplots(
#             1,
#             1,
#             figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
#         )
#         rax = None

#     # 4. Stack dei background
#     total_mc_vals = np.zeros(len(bin_edges) - 1, dtype=float)
#     total_mc_errs2 = np.zeros(len(bin_edges) - 1, dtype=float)

#     if mc_vals:
#         hep.histplot(
#             mc_vals,
#             bins=bin_edges,
#             stack=True,
#             histtype="fill",
#             color=mc_colors,
#             label=mc_labels,
#             edgecolor="black",
#             linewidth=0.5,
#             ax=ax,
#         )

#         # Incertezza statistica MC totale, sommata in quadratura per bin
#         for sample_id, sample_info in samples_dict.items():
#             if sample_info["is_data"] or sample_info["is_signal"]:
#                 continue
#             if category not in sample_info["hists"]:
#                 continue
#             if variable not in sample_info["hists"][category]:
#                 continue

#             h = sample_info["hists"][category][variable]
#             _, c, e = get_bins_and_content(
#                 h,
#                 want_overflow=True,
#                 divide_by_bin_width=divide_by_bin_width,
#             )
#             total_mc_vals += c
#             total_mc_errs2 += e ** 2

#         total_mc_errs = np.sqrt(total_mc_errs2)

#         # Profilo dello stack totale
#         hep.histplot(
#             total_mc_vals,
#             bins=bin_edges,
#             histtype="step",
#             color="black",
#             linewidth=0.5,
#             ax=ax,
#         )

#         # Banda di incertezza background
#         bkg_unc_cfg = config_page.get("bkg_unc_hist", {})
#         unc_hatch = "//" if bkg_unc_cfg.get("fill_style") == 3013 else None
#         unc_alpha = bkg_unc_cfg.get("alpha", 0.35)

#         y_up = total_mc_vals + total_mc_errs
#         y_dn = np.maximum(total_mc_vals - total_mc_errs, 0.0)

#         ax.fill_between(
#             bin_edges[:-1],
#             y_dn,
#             y_up,
#             step="post",
#             facecolor="none",
#             edgecolor="black",
#             hatch=unc_hatch,
#             alpha=unc_alpha,
#             linewidth=0.8,
#             label=bkg_unc_cfg.get("legend_title", "Bkg. uncertainty"),
#         )

#     else:
#         total_mc_errs = np.zeros(len(bin_edges) - 1, dtype=float)

#     # 5. Segnali overlay
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

#     # 6. Dati, con eventuale blinding già applicato via NaN
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

#     # 7. Ratio Data/MC, robusto al blinding via NaN
#     if has_ratio:
#         valid_ratio = (
#             (total_mc_vals != 0)
#             & np.isfinite(total_mc_vals)
#             & np.isfinite(data_vals)
#             & np.isfinite(data_errs)
#         )

#         ratio = np.divide(
#             data_vals,
#             total_mc_vals,
#             out=np.full_like(data_vals, np.nan, dtype=float),
#             where=valid_ratio,
#         )

#         ratio_err = np.abs(np.divide(
#             data_errs,
#             total_mc_vals,
#             out=np.full_like(data_errs, np.nan, dtype=float),
#             where=valid_ratio,
#         ))

#         mc_rel_unc = np.divide(
#             total_mc_errs,
#             total_mc_vals,
#             out=np.zeros_like(total_mc_errs, dtype=float),
#             where=total_mc_vals != 0,
#         )

#         y_ratio_up = 1.0 + mc_rel_unc
#         y_ratio_dn = np.maximum(1.0 - mc_rel_unc, 0.0)

#         rax.fill_between(
#             bin_centers,
#             y_ratio_dn,
#             y_ratio_up,
#             step="mid",
#             facecolor="ghostwhite",
#             edgecolor="black",
#             hatch="//",
#             alpha=0.5,
#             zorder=1,
#         )

#         rax.errorbar(
#             bin_centers,
#             ratio,
#             yerr=ratio_err,
#             fmt=".",
#             color="black",
#             markersize=10,
#             zorder=2,
#         )
#         rax.axhline(1.0, color="black", linestyle="--", linewidth=1.0)

#         finite_ratio = ratio[np.isfinite(ratio)]
#         delta = np.abs(finite_ratio - 1.0).mean() if len(finite_ratio) else 0.4
#         delta = max(delta, 0.1)

#         rax.set_ylim(round(1 - delta, 2) * 0.9, round(1 + delta, 2) * 1.1)
#         rax.set_ylabel("Data/MC", fontsize=14)

#     # 8. Assi, titoli e scala
#     x_label = hist_cfg.get("x_title", variable)
#     for mu_idx in [1, 2]:
#         if f"mu{mu_idx}" in variable:
#             x_label = x_label.format(mu_idx=mu_idx)

#     if has_ratio:
#         rax.set_xlabel(x_label, fontsize=20)
#         ax.get_xaxis().set_visible(False)
#     else:
#         ax.set_xlabel(x_label, fontsize=20)

#     ax.set_ylabel(hist_cfg.get("y_title", "Events"), fontsize=20)
#     ax.set_xlim(bin_edges[0] * 0.99, bin_edges[-1] * 1.01)

#     want_log_y = config_page.get("wantLogY", False)
#     ax.set_yscale("log" if want_log_y else "linear")

#     # Limiti asse Y ignorando NaN dei dati blindati
#     visible_arrays = list(mc_vals)
#     if data_vals is not None:
#         visible_arrays.append(data_vals)
#     for s_val in sgn_vals:
#         visible_arrays.append(s_val)

#     y_max = safe_nanmax(visible_arrays, default=1.0)
#     max_factor = hist_cfg.get("max_y_sf", 1.2) if not want_log_y else (100 ** hist_cfg.get("max_y_sf", 1.0))

#     ax.set_ylim(top=y_max * max_factor)
#     if want_log_y:
#         ax.set_ylim(bottom=min(0.1, y_max * 1e-5))
#     else:
#         ax.set_ylim(bottom=0.0)

#     # 9. Legenda
#     legend_cfg = config_page.get("legend_mplhep", {})
#     ax.legend(
#         loc="upper right",
#         facecolor=legend_cfg.get("fill_color", "white"),
#         frameon=True,
#         fontsize=legend_cfg.get("text_size", 0.16) * 110,
#         framealpha=0.2,
#         ncol=legend_cfg.get("ncols", 2),
#         handleheight=1.4,
#         labelspacing=0.1,
#     )

#     # 10. Label CMS
#     lumi_val = config_page.get("lumi_text", {}).get("text", "1.0")
#     cms_tag = config_page.get("cms_label", {}).get("tag", "Preliminary")
#     cms_com = config_page.get("cms_label", {}).get("com", "13.6")

#     hep.cms.label(
#         ax=ax,
#         data=(data_vals is not None),
#         label=cms_tag,
#         lumi=float(lumi_val),
#         com=float(cms_com),
#         loc=0,
#     )

#     # Testo aggiuntivo della categoria/regione
#     ax.text(
#         0.22,
#         0.96,
#         " ".join(c for c in category.split("_")),
#         transform=ax.transAxes,
#         fontsize=12,
#         verticalalignment="top",
#         horizontalalignment="right",
#     )

#     # Salvataggio multi-formato
#     fig.savefig(f"{out_name}.png", bbox_inches="tight")
#     fig.savefig(f"{out_name}.pdf", bbox_inches="tight")
#     print(f"{out_name}.png")
#     plt.close(fig)


# # =========================================================
# # Main Execution Block
# # =========================================================
# if __name__ == "__main__":
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--era", required=True, type=str)
#     parser.add_argument("--input", required=True, type=str, help="ROOT file or dataset directory")
#     parser.add_argument("--output", default="plots_output", type=str, help="Output directory for plots")
#     parser.add_argument("--region", default="Z_sideband_baseline", type=str, help="Region to plot")
#     parser.add_argument("--systematics", action="store_true", help="Include systematic uncertainties")
#     parser.add_argument("--wantData", action="store_true", help="Include data in plots and draw ratio")
#     parser.add_argument("--wantLogY", action="store_true", help="Set y-axis to log scale")
#     parser.add_argument("--rebin", action="store_true", help="rebin histograms")
#     args = parser.parse_args()

#     startTime = time.time()

#     # Caricamento configurazioni YAML di analisi e di stile grafico
#     cfg_dir = os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era)

#     main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
#     process_cfg = utilities.get_config(os.path.join(cfg_dir, "process_names.yaml"))
#     sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
#     syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))

#     hist_cfg = utilities.get_config(
#         os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", "histograms.yaml")
#     )
#     additional_cfg = utilities.get_config(
#         os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", f"{args.era}.yaml")
#     )
#     page_cfg = utilities.get_config(
#         os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", "cms_stacked.yaml")
#     )

#     region_path = args.region

#     # Unione flessibile dei dizionari di configurazione e aggiunta dei flag CLI
#     config_setup = {**page_cfg, **additional_cfg, **hist_cfg}
#     config_setup["wantLogY"] = args.wantLogY

#     # Caricamento istogrammi ROOT ricorsivo
#     input_processes = {}
#     all_found_variables = set()

#     for indir, subdirs, infiles in os.walk(args.input):
#         for inFile in infiles:
#             if not inFile.endswith(".root"):
#                 continue

#             full_path = os.path.join(indir, inFile)
#             process_name = inFile.split(".")[0]

#             if process_name not in process_cfg.keys():
#                 continue

#             if process_cfg[process_name].get("skip_plotting", False):
#                 continue

#             root_file = ROOT.TFile.Open(full_path, "READ")
#             if not root_file or root_file.IsZombie():
#                 continue

#             input_processes[process_name] = {
#                 "input": full_path,
#                 "color": process_cfg[process_name].get(
#                     "color_mplhep",
#                     process_cfg[process_name].get("color", "black"),
#                 ),
#                 "name": process_cfg[process_name]["name"],
#                 "is_data": process_cfg[process_name].get("is_data", False),
#                 "is_signal": process_cfg[process_name].get("is_signal", False),
#                 "hists": {region_path: {}},
#             }

#             isDY = process_name == "DY"
#             available_hists = get_available_histograms(root_file, region_path, isDY)

#             for available_hist, hist_name in available_hists:
#                 var_entry = findBinEntry(hist_cfg, hist_name)

#                 if var_entry is None or var_entry not in hist_cfg:
#                     print(f"[WARNING] Nessuna configurazione trovata per {hist_name}. Skip.")
#                     continue

#                 if "x_rebin" in hist_cfg[var_entry]:
#                     bins_to_compute = findNewBins(hist_cfg, var_entry, dir_name=region_path)
#                     new_bins = getNewBins(bins_to_compute)
#                 else:
#                     new_bins = hist_cfg[var_entry].get("x_bins", [])
#                 rebinned_hist=available_hist
#                 if args.rebin:
#                     rebinned_hist = RebinHisto(
#                         available_hist,
#                         new_bins,
#                         process_name,
#                         wantOverflow=False,
#                     )

#                 if rebinned_hist is None:
#                     continue

#                 rebinned_hist.SetDirectory(0)

#                 if is_valid_histogram(rebinned_hist):
#                     input_processes[process_name]["hists"][region_path][hist_name] = rebinned_hist
#                     all_found_variables.add(hist_name)

#             root_file.Close()

#     # Produzione dei plot finali
#     if len(all_found_variables) == 0:
#         print(f"[ERROR] Nessun istogramma valido trovato per la regione {region_path}.")
#     else:
#         output_dir_path = os.path.join(args.output, args.era, region_path)
#         os.makedirs(output_dir_path, exist_ok=True)

#         print(f"\n--> Generazione di {len(all_found_variables)} plot strutturati in corso...")

#         for variable in sorted(all_found_variables):
#             # Se hist_name contiene '/', crea sottodirectory coerenti invece di fallire al savefig.
#             plot_base_path = os.path.join(output_dir_path, variable)
#             os.makedirs(os.path.dirname(plot_base_path), exist_ok=True)

#             make_stacked_plot(
#                 samples_dict=input_processes,
#                 config_page=config_setup,
#                 category=region_path,
#                 variable=variable,
#                 out_name=plot_base_path,
#                 want_data=args.wantData,
#             )

#     print(f"\n[SUCCESS] Elaborazione completata in {time.time() - startTime:.2f} secondi.")
