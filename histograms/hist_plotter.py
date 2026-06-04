#!/usr/bin/env python3

import ROOT
import sys
import os
import argparse
import time
import json
import numpy as np
import matplotlib.pyplot as plt
import mplhep as hep

# Configurazione dello stile CMS globale
plt.style.use(hep.style.CMS)

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import common.utilities as utilities
from common.helpers import *

HEADERS = ["analysis/AnalysisTools.h"]
for header in HEADERS:
    utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")


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
                obj.Scale(scale_factor_for_DY_XS)
                output.append((obj, hist_name))

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
        # Overflow nell'ultimo bin visibile
        content[-1] += root_hist.GetBinContent(n_bins + 1)
        errors[-1] = np.sqrt(errors[-1] ** 2 + root_hist.GetBinError(n_bins + 1) ** 2)

        # Underflow nel primo bin visibile
        content[0] += root_hist.GetBinContent(0)
        errors[0] = np.sqrt(errors[0] ** 2 + root_hist.GetBinError(0) ** 2)

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
    Legge blind_range dalla configurazione dell'istogramma.

    Supporta entrambi i formati:

      mll:
        blind_range: [115, 130]

    oppure:

      mll:
        blind_range:
          Signal_Fit: [115, 130]
          Some_Other_Category: [100, 150]

    Nel secondo caso applica il blinding solo se category matcha una chiave.
    """
    blind_range = hist_cfg.get("blind_range", None)

    if blind_range is None:
        return None

    # Formato globale: blind_range: [xmin, xmax]
    if isinstance(blind_range, (list, tuple)):
        if len(blind_range) != 2:
            print(f"  [WARNING] blind_range malformato: {blind_range}")
            return None
        return [float(blind_range[0]), float(blind_range[1])]

    # Formato per categoria:
    # blind_range:
    #   Signal_Fit: [xmin, xmax]
    if isinstance(blind_range, dict):
        category_range = blind_range.get(category, None)
        if category_range is None:
            return None
        if not isinstance(category_range, (list, tuple)) or len(category_range) != 2:
            print(f"  [WARNING] blind_range malformato per categoria {category}: {category_range}")
            return None
        return [float(category_range[0]), float(category_range[1])]
    print(blind_range)
    print(f"  [WARNING] Tipo non supportato per blind_range: {type(blind_range)}")
    return None


def apply_blind_range(edges, content, errors, blind_range=None):
    """
    Applica il blinding ai bin il cui centro cade dentro blind_range = [xmin, xmax].
    Usa NaN per il contenuto: matplotlib non disegna quei punti/bin nei dati.
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
    Calcola il massimo ignorando NaN/inf su una lista di array.
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
# Core Drawing Core (Matplotlib + mplhep)
# =========================================================
def make_stacked_plot(samples_dict, config_page, category, variable, out_name, want_data=True):
    """
    Genera uno stacked plot con:
      - stack dei background
      - segnali overlay
      - dati opzionali
      - ratio Data/MC opzionale
      - blinding sui dati, se configurato per variabile/categoria
    """
    mc_vals, mc_colors, mc_labels, mc_integrals = [], [], [], []
    sgn_vals, sgn_colors, sgn_labels = [], [], []
    data_vals, data_errs = None, None
    data_label_legend = None
    bin_edges = None

    hist_entry = findBinEntry(config_page, variable)
    hist_cfg = config_page.get(hist_entry, {}) if hist_entry is not None else {}

    divide_by_bin_width = hist_cfg.get("divide_by_bin_width", False)
    blind_range = get_blind_range_for_category(hist_cfg, category)

    if blind_range is not None:
        print(f"  [BLIND] {variable} in category {category}: range {blind_range}")

    # 1. Separazione campioni: data / signal / background
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
        print(f"  [WARNING] Istogramma vuoto o mancante per la variabile: {variable}")
        return

    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    # 2. Ordinamento background per yield crescente
    if mc_vals:
        idx_sort = np.argsort(mc_integrals)
        mc_vals = [mc_vals[i] for i in idx_sort]
        mc_colors = [mc_colors[i] for i in idx_sort]
        mc_labels = [mc_labels[i] for i in idx_sort]

    # 3. Canvas: main pad + ratio pad se ci sono dati e MC
    canvas_size = config_page["page_setup"].get("canvas_size", [900, 800])
    has_ratio = data_vals is not None and len(mc_vals) > 0

    if has_ratio:
        fig, (ax, rax) = plt.subplots(
            2,
            1,
            figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05},
        )
    else:
        fig, ax = plt.subplots(
            1,
            1,
            figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
        )
        rax = None

    # 4. Stack dei background
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

        # Incertezza statistica MC totale, sommata in quadratura per bin
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

        # Profilo dello stack totale
        hep.histplot(
            total_mc_vals,
            bins=bin_edges,
            histtype="step",
            color="black",
            linewidth=0.5,
            ax=ax,
        )

        # Banda di incertezza background
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

    # 5. Segnali overlay
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

    # 6. Dati, con eventuale blinding già applicato via NaN
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

    # 7. Ratio Data/MC, robusto al blinding via NaN
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

        ratio_err = np.abs(np.divide(
            data_errs,
            total_mc_vals,
            out=np.full_like(data_errs, np.nan, dtype=float),
            where=valid_ratio,
        ))

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
        rax.axhline(1.0, color="black", linestyle="--", linewidth=1.0)

        finite_ratio = ratio[np.isfinite(ratio)]
        delta = np.abs(finite_ratio - 1.0).mean() if len(finite_ratio) else 0.4
        delta = max(delta, 0.1)

        rax.set_ylim(round(1 - delta, 2) * 0.9, round(1 + delta, 2) * 1.1)
        rax.set_ylabel("Data/MC", fontsize=14)

    # 8. Assi, titoli e scala
    x_label = hist_cfg.get("x_title", variable)
    for mu_idx in [1, 2]:
        if f"mu{mu_idx}" in variable:
            x_label = x_label.format(mu_idx=mu_idx)

    if has_ratio:
        rax.set_xlabel(x_label, fontsize=20)
        ax.get_xaxis().set_visible(False)
    else:
        ax.set_xlabel(x_label, fontsize=20)

    ax.set_ylabel(hist_cfg.get("y_title", "Events"), fontsize=20)
    ax.set_xlim(bin_edges[0] * 0.99, bin_edges[-1] * 1.01)

    want_log_y = config_page.get("wantLogY", False)
    ax.set_yscale("log" if want_log_y else "linear")

    # Limiti asse Y ignorando NaN dei dati blindati
    visible_arrays = list(mc_vals)
    if data_vals is not None:
        visible_arrays.append(data_vals)
    for s_val in sgn_vals:
        visible_arrays.append(s_val)

    y_max = safe_nanmax(visible_arrays, default=1.0)
    max_factor = hist_cfg.get("max_y_sf", 1.2) if not want_log_y else (100 ** hist_cfg.get("max_y_sf", 1.0))

    ax.set_ylim(top=y_max * max_factor)
    if want_log_y:
        ax.set_ylim(bottom=min(0.1, y_max * 1e-5))
    else:
        ax.set_ylim(bottom=0.0)

    # 9. Legenda
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

    # 10. Label CMS
    lumi_val = config_page.get("lumi_text", {}).get("text", "1.0")
    cms_tag = config_page.get("cms_label", {}).get("tag", "Preliminary")
    cms_com = config_page.get("cms_label", {}).get("com", "13.6")

    hep.cms.label(
        ax=ax,
        data=(data_vals is not None),
        label=cms_tag,
        lumi=float(lumi_val),
        com=float(cms_com),
        loc=0,
    )

    # Testo aggiuntivo della categoria/regione
    ax.text(
        0.22,
        0.96,
        " ".join(c for c in category.split("_")),
        transform=ax.transAxes,
        fontsize=12,
        verticalalignment="top",
        horizontalalignment="right",
    )

    # Salvataggio multi-formato
    fig.savefig(f"{out_name}.png", bbox_inches="tight")
    fig.savefig(f"{out_name}.pdf", bbox_inches="tight")
    print(f"{out_name}.png")
    plt.close(fig)


# =========================================================
# Main Execution Block
# =========================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True, type=str)
    parser.add_argument("--input", required=True, type=str, help="ROOT file or dataset directory")
    parser.add_argument("--output", default="plots_output", type=str, help="Output directory for plots")
    parser.add_argument("--region", default="Z_sideband_baseline", type=str, help="Region to plot")
    parser.add_argument("--systematics", action="store_true", help="Include systematic uncertainties")
    parser.add_argument("--wantData", action="store_true", help="Include data in plots and draw ratio")
    parser.add_argument("--wantLogY", action="store_true", help="Set y-axis to log scale")
    args = parser.parse_args()

    startTime = time.time()

    # Caricamento configurazioni YAML di analisi e di stile grafico
    cfg_dir = os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era)

    main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
    process_cfg = utilities.get_config(os.path.join(cfg_dir, "process_names.yaml"))
    sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
    syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))

    hist_cfg = utilities.get_config(
        os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", "histograms.yaml")
    )
    additional_cfg = utilities.get_config(
        os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", f"{args.era}.yaml")
    )
    page_cfg = utilities.get_config(
        os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", "cms_stacked.yaml")
    )

    region_path = args.region

    # Unione flessibile dei dizionari di configurazione e aggiunta dei flag CLI
    config_setup = {**page_cfg, **additional_cfg, **hist_cfg}
    config_setup["wantLogY"] = args.wantLogY

    # Caricamento istogrammi ROOT ricorsivo
    input_processes = {}
    all_found_variables = set()

    for indir, subdirs, infiles in os.walk(args.input):
        for inFile in infiles:
            if not inFile.endswith(".root"):
                continue

            full_path = os.path.join(indir, inFile)
            process_name = inFile.split(".")[0]

            if process_name not in process_cfg.keys():
                continue

            if process_cfg[process_name].get("skip_plotting", False):
                continue

            root_file = ROOT.TFile.Open(full_path, "READ")
            if not root_file or root_file.IsZombie():
                continue

            input_processes[process_name] = {
                "input": full_path,
                "color": process_cfg[process_name].get(
                    "color_mplhep",
                    process_cfg[process_name].get("color", "black"),
                ),
                "name": process_cfg[process_name]["name"],
                "is_data": process_cfg[process_name].get("is_data", False),
                "is_signal": process_cfg[process_name].get("is_signal", False),
                "hists": {region_path: {}},
            }

            isDY = process_name == "DY"
            available_hists = get_available_histograms(root_file, region_path, isDY)

            for available_hist, hist_name in available_hists:
                var_entry = findBinEntry(hist_cfg, hist_name)

                if var_entry is None or var_entry not in hist_cfg:
                    print(f"[WARNING] Nessuna configurazione trovata per {hist_name}. Skip.")
                    continue

                if "x_rebin" in hist_cfg[var_entry]:
                    bins_to_compute = findNewBins(hist_cfg, var_entry, dir_name=region_path)
                    new_bins = getNewBins(bins_to_compute)
                else:
                    new_bins = hist_cfg[var_entry].get("x_bins", [])

                rebinned_hist = RebinHisto(
                    available_hist,
                    new_bins,
                    process_name,
                    wantOverflow=True,
                )

                if rebinned_hist is None:
                    continue

                rebinned_hist.SetDirectory(0)

                if is_valid_histogram(rebinned_hist):
                    input_processes[process_name]["hists"][region_path][hist_name] = rebinned_hist
                    all_found_variables.add(hist_name)

            root_file.Close()

    # Produzione dei plot finali
    if len(all_found_variables) == 0:
        print(f"[ERROR] Nessun istogramma valido trovato per la regione {region_path}.")
    else:
        output_dir_path = os.path.join(args.output, args.era, region_path)
        os.makedirs(output_dir_path, exist_ok=True)

        print(f"\n--> Generazione di {len(all_found_variables)} plot strutturati in corso...")

        for variable in sorted(all_found_variables):
            # Se hist_name contiene '/', crea sottodirectory coerenti invece di fallire al savefig.
            plot_base_path = os.path.join(output_dir_path, variable)
            os.makedirs(os.path.dirname(plot_base_path), exist_ok=True)

            make_stacked_plot(
                samples_dict=input_processes,
                config_page=config_setup,
                category=region_path,
                variable=variable,
                out_name=plot_base_path,
                want_data=args.wantData,
            )

    print(f"\n[SUCCESS] Elaborazione completata in {time.time() - startTime:.2f} secondi.")


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
# # Core Drawing Core (Matplotlib + Mplhep Freedom)
# # =========================================================
# def get_available_histograms(root_file, region_path, isDY=False, recursive=True):
#     """
#     Returns:
#         [(histogram, hist_name), ...]
#     """

#     output = []

#     directory = root_file.Get(region_path)
#     scale_factor_for_DY_XS = 2094.2/(6688/3) if isDY else 1.
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
#     Estrae binedges, contenuti ed errori da un TH1D C++.
#     Include nativamente l'overflow e l'underflow se richiesto per preservare gli yield.
#     """
#     n_bins = root_hist.GetNbinsX()
#     edges = np.array([root_hist.GetBinLowEdge(i) for i in range(1, n_bins + 2)])
#     content = np.array([root_hist.GetBinContent(i) for i in range(1, n_bins + 1)])
#     errors = np.array([root_hist.GetBinError(i) for i in range(1, n_bins + 1)])

#     if want_overflow and n_bins > 0:
#         # Aggiunge l'overflow all'ultimo bin visibile per uniformità con RebinHisto
#         content[-1] += root_hist.GetBinContent(n_bins + 1)
#         errors[-1] = np.sqrt(errors[-1]**2 + root_hist.GetBinError(n_bins + 1)**2)
#         # Aggiunge l'underflow al primo bin
#         content[0] += root_hist.GetBinContent(0)
#         errors[0] = np.sqrt(errors[0]**2 + root_hist.GetBinError(0)**2)

#     if divide_by_bin_width:
#         widths = np.diff(edges)
#         content = np.divide(content, widths, out=np.zeros_like(content), where=widths != 0)
#         errors = np.divide(errors, widths, out=np.zeros_like(errors), where=widths != 0)

#     return edges, content, errors


# def make_stacked_plot(samples_dict, config_page, category, variable, out_name, want_data=True):
#     """
#     Genera uno stacked plot avanzato che riproduce la logica e la libertà
#     delle funzioni di disegno di riferimento di produzione.
#     """
#     mc_vals, mc_colors, mc_labels, mc_integrals = [], [], [], []
#     sgn_vals, sgn_colors, sgn_labels = [], [], []
#     data_vals, data_errs = None, None
#     bin_edges = None
#     hist_cfg = config_page.get(findBinEntry(config_page, variable), {})
#     divide_by_bin_width = hist_cfg.get("divide_by_bin_width", False)

#     # 1. Separazione e parsing strutturato dei campioni dal dizionario principale
#     for sample_id, sample_info in samples_dict.items():
#         if category not in sample_info["hists"] or variable not in sample_info["hists"][category]:
#             continue

#         root_hist = sample_info["hists"][category][variable]
#         edges, content, errors = get_bins_and_content(root_hist, want_overflow=True, divide_by_bin_width=divide_by_bin_width)

#         if bin_edges is None:
#             bin_edges = edges

#         # Recupera l'integrale pulito (yield) dell'istogramma nativo ROOT
#         hist_integral = root_hist.Integral()

#         if sample_info["is_data"]:
#             if want_data:
#                 data_vals = content
#                 data_errs = errors
#                 data_label_base = sample_info.get("name", "Data")
#                 data_legend_label = f"{data_label_base} [{hist_integral:.2f}]"
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

#     # 2. Ordinamento dinamico delle componenti di Background basato sui yield totali (Ascending)
#     if mc_vals:
#         idx_sort = np.argsort(mc_integrals)
#         mc_vals = [mc_vals[i] for i in idx_sort]
#         mc_colors = [mc_colors[i] for i in idx_sort]
#         mc_labels = [mc_labels[i] for i in idx_sort]

#     # 3. Setup della Canvas multifrnzione (Main Pad + Ratio)
#     # 3. Setup della Canvas multifunzione (Main Pad + Ratio)
#     canvas_size = config_page["page_setup"].get("canvas_size", [900, 800])
#     has_ratio = (data_vals is not None and len(mc_vals) > 0)

#     if has_ratio:
#         fig, (ax, rax) = plt.subplots(
#             2, 1,
#             figsize=(canvas_size[0] / 80, canvas_size[1] / 100),
#             sharex=True,
#             gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05}
#         )
#     else:
#         fig, ax = plt.subplots(
#             1, 1,
#             figsize=(canvas_size[0] / 80, canvas_size[1] / 100)
#         )
#         rax = None

#     # 4. Disegno dello Stack dei Background (Nativo mplhep)
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
#             ax=ax
#         )

#         # Calcolo dell'incertezza statistica MC totale sommando in quadratura l'errore di ogni bin
#         for sample_id, sample_info in samples_dict.items():
#             if not sample_info["is_data"] and not sample_info["is_signal"]:
#                 if category in sample_info["hists"] and variable in sample_info["hists"][category]:
#                     h = sample_info["hists"][category][variable]
#                     _, c, e = get_bins_and_content(h, want_overflow=True, divide_by_bin_width=divide_by_bin_width)
#                     total_mc_vals += c
#                     total_mc_errs2 += e ** 2

#         total_mc_errs = np.sqrt(total_mc_errs2)

#         # Disegno del profilo continuo dello stack totale (linea nera sottile di chiusura)
#         hep.histplot(total_mc_vals, bins=bin_edges, histtype="step", color="black", linewidth=0.5, ax=ax)

#         # Disegno della banda di incertezza del Background (Hatch pattern)
#         bkg_unc_cfg = config_page.get("bkg_unc_hist", {})
#         unc_hatch = "//" if bkg_unc_cfg.get("fill_style") == 3013 else None
#         unc_alpha = bkg_unc_cfg.get("alpha", 0.35)

#         y_up = total_mc_vals + total_mc_errs
#         y_dn = np.maximum(total_mc_vals - total_mc_errs, 0.0)

#         ax.fill_between(
#             bin_edges[:-1], y_dn, y_up,
#             step="post",
#             facecolor="none",
#             edgecolor="black",
#             hatch=unc_hatch,
#             alpha=unc_alpha,
#             linewidth=0.8,
#             label=bkg_unc_cfg.get("legend_title", "Bkg. uncertainty")
#         )

#     # 5. Disegno dei Segnali sovrapposti (Linee tratteggiate non-stacked)
#     for s_val, s_col, s_lab in zip(sgn_vals, sgn_colors, sgn_labels):
#         hep.histplot(
#             s_val,
#             bins=bin_edges,
#             histtype="step",
#             color=s_col,
#             label=s_lab,
#             linestyle="--",
#             linewidth=1.5,
#             ax=ax
#         )

#     # 6. Disegno dei Dati sperimentali
#     if data_vals is not None:
#         bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
#         ax.errorbar(
#             bin_centers,
#             data_vals,
#             yerr=data_errs,
#             fmt="o",
#             color="black",
#             markersize=5,
#             label=data_legend_label
#         )

#     # 7. Logica del pannello inferiore: Data / MC Ratio Pad
#     if has_ratio:
#         ratio = np.divide(data_vals, total_mc_vals, out=np.zeros_like(data_vals), where=total_mc_vals != 0)
#         ratio_err = np.abs(np.divide(data_errs, total_mc_vals, out=np.zeros_like(data_errs), where=total_mc_vals != 0))
#         mc_rel_unc = np.divide(total_mc_errs, total_mc_vals, out=np.zeros_like(total_mc_errs), where=total_mc_vals != 0)

#         y_ratio_up = 1.0 + mc_rel_unc
#         y_ratio_dn = np.maximum(1.0 - mc_rel_unc, 0.0)

#         # Banda di incertezza MC sul ratio
#         rax.fill_between(
#             bin_centers, y_ratio_dn, y_ratio_up,
#             step="mid",
#             facecolor="ghostwhite",
#             edgecolor="black",
#             hatch="//",
#             alpha=0.5,
#             zorder=1
#         )

#         # Punti sperimentali del rapporto
#         rax.errorbar(bin_centers, ratio, yerr=ratio_err, fmt=".", color="black", markersize=10, zorder=2)
#         rax.axhline(1.0, color="black", linestyle="--", linewidth=1.0)

#         # Calcolo della coordinata Y dinamica per adattarsi ai punti del ratio (come da drawing functions)
#         delta = np.abs(ratio - 1).mean() if len(ratio) else 0.4
#         rax.set_ylim(round(1 - delta, 2) * 0.9, round(1 + delta, 2) * 1.1)
#         rax.set_ylabel("Data/MC", fontsize=14)

#     # 8. Gestione assi, titoli e scalatura
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

#     # Log/Linear Scala
#     want_log_y = args.wantLogY
#     ax.set_yscale("log" if want_log_y else "linear")

#     # Limiti asse Y dinamici condizionati dalla presenza o meno del Log
#     if mc_vals or data_vals is not None:
#         all_maxes = [np.max(c) for c in mc_vals] + ([np.max(data_vals)] if data_vals is not None else [])
#         y_max = np.max(all_maxes) if all_maxes else 1.0
#         max_factor = hist_cfg.get("max_y_sf", 1.2) if not want_log_y else (100 ** hist_cfg.get("max_y_sf", 1.0))
#         ax.set_ylim(top=y_max * max_factor)
#         if want_log_y:
#             ax.set_ylim(bottom=min(0.1, y_max * 1e-5))
#         else:
#             ax.set_ylim(bottom=0.0)

#     # 9. Legenda ad alta leggibilità regolata dal dizionario yaml
#     legend_cfg = config_page.get("legend_mplhep", {})
#     ax.legend(
#         loc="upper right",
#         facecolor=legend_cfg.get("fill_color", "white"),
#         frameon=True,
#         fontsize=legend_cfg.get("text_size", 0.16) * 110,
#         framealpha=0.2,
#         ncol=legend_cfg.get("ncols", 2),
#         handleheight=1.4,
#         labelspacing=0.1
#     )

#     # 10. Label ed intestazioni ufficiali CMS / TeX
#     lumi_val = config_page.get("lumi_text", {}).get("text", "1.0")
#     cms_tag = config_page.get("cms_label", {}).get("tag", "Preliminary")
#     cms_com = config_page.get("cms_label", {}).get("com", "13.6")

#     hep.cms.label(
#         ax=ax,
#         data=(data_vals is not None),
#         label=cms_tag,
#         lumi=float(lumi_val),
#         com=float(cms_com),
#         loc=0
#     )

#     # Testo aggiuntivo della categoria/regione
#     ax.text(0.22, 0.96, ' '.join(c for c in category.split('_')), transform=ax.transAxes, fontsize=12, verticalalignment="top", horizontalalignment="right")

#     # Salvataggio multi-formato
#     # plt.tight_layout()
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
#     parser.add_argument("--wantData", action="store_true", help="Include data in plots (and draw ratio)")
#     parser.add_argument("--wantLogY", action="store_true", help="Set y-axis to log scale")
#     args = parser.parse_args()

#     startTime = time.time()

#     # Caricamento configurazioni YAML di analisi e di stile grafico
#     cfg_dir = os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era)
#     main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
#     process_cfg = utilities.get_config(os.path.join(cfg_dir, "process_names.yaml"))
#     sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
#     syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))
#     hist_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", "histograms.yaml"))
#     additional_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", f"{args.era}.yaml"))
#     page_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", "cms_stacked.yaml"))

#     region_path = args.region

#     # Unione flessibile dei dizionari di configurazione e aggiunta dei flag da linea di comando
#     config_setup = {**page_cfg, **additional_cfg, **hist_cfg}
#     config_setup["wantLogY"] = args.wantLogY

#     # Caricamento Istogrammi ROOT ricorsivo
#     input_processes = {}
#     all_found_variables = set()

#     for indir, subdirs, infiles in os.walk(args.input):
#         for inFile in infiles:
#             if inFile.endswith(".root"):
#                 full_path = os.path.join(indir, inFile)
#                 process_name = inFile.split(".")[0]
#                 if process_name not in process_cfg.keys():
#                     continue

#                 root_file = ROOT.TFile.Open(full_path, 'READ')
#                 if not root_file or root_file.IsZombie():
#                     continue
#                 if process_cfg[process_name].get('skip_plotting', False): continue

#                 input_processes[process_name] = {
#                     'input': full_path,
#                     'color': process_cfg[process_name].get('color_mplhep', process_cfg[process_name].get('color', 'black')),
#                     'name': process_cfg[process_name]['name'],
#                     'is_data': process_cfg[process_name].get('is_data', False),
#                     'is_signal': process_cfg[process_name].get('is_signal', False),
#                     'hists': {region_path: {}}
#                 }
#                 isDY = process_name == "DY"
#                 # print(process_name)
#                 available_hists = get_available_histograms(root_file, region_path, isDY)
#                 for available_hist, hist_name in available_hists:
#                     var_entry = findBinEntry(hist_cfg, hist_name)
#                     # print(var_entry)
#                     if "x_rebin" in hist_cfg[var_entry]:
#                         bins_to_compute = findNewBins(hist_cfg, var_entry, dir_name=region_path)
#                         new_bins = getNewBins(bins_to_compute)
#                     else:
#                         new_bins = hist_cfg[var_entry].get('x_bins', [])
#                     rebinned_hist = RebinHisto(available_hist, new_bins, process_name,
#                                                 wantOverflow=True)
#                     rebinned_hist.SetDirectory(0)
#                     if rebinned_hist is not None and is_valid_histogram(rebinned_hist):
#                         input_processes[process_name]['hists'][region_path][hist_name] = rebinned_hist
#                         all_found_variables.add(hist_name)
#                 root_file.Close()

#     # Ciclo di produzione dei file grafici finali
#     if len(all_found_variables) == 0:
#         print(f"[ERROR] Nessun istogramma valido trovato per la regione {region_path}.")
#     else:
#         output_dir_path = os.path.join(args.output, args.era, region_path)
#         os.makedirs(output_dir_path, exist_ok=True)

#         print(f"\n--> Generazione di {len(all_found_variables)} plot strutturati in corso...")
#         for variable in all_found_variables:
#             plot_base_path = os.path.join(output_dir_path, variable)

#             make_stacked_plot(
#                 samples_dict=input_processes,
#                 config_page=config_setup,
#                 category=region_path,
#                 variable=variable,
#                 out_name=plot_base_path,
#                 want_data=args.wantData
#             )

#     print(f"\n[SUCCESS] Elaborazione completata in {time.time() - startTime:.2f} secondi.")
