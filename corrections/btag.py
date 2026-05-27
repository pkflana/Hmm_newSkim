import os
from enum import Enum
import ROOT
import json
from .general import pog_folder_names,period_names,periods

class WorkingPointsbTag(Enum):
    Loose = 1
    Medium = 2
    Tight = 3


# --- COSTANTI E CONFIGURAZIONI GLOBALI ---
JSON_PATH = "/cvmfs/cms-griddata.cern.ch/cat/metadata/BTV/{}/latest/btagging.json.gz"
ALTERNATIVE_JSON_PATH = "/cvmfs/cms-griddata.cern.ch/cat/metadata/BTV/{}/add_2025_b_and_c_WPs/btagging.json.gz"

UNC_SOURCE_BTAG_WP = [
    "btagSFbc_uncorrelated",
    "btagSFlight_uncorrelated",
    "btagSFbc_correlated",
    "btagSFlight_correlated",
]
UNC_SOURCES_BTAG_SHAPE_JES = [
    "Total", "FlavorQCD", "RelativeBal", "HF", "BBEC1", "EC2",
    "Absolute", "BBEC1_", "Absolute_", "EC2_", "HF_", "RelativeSample_"
]
UNC_SOURCES_BTAG_SHAPE_NORM = [
    "lf", "hf", "lfstats1", "lfstats2", "hfstats1", "hfstats2", "cferr1", "cferr2"
]

TAGGER_TO_BTAG_BRANCH = {
    "particleNet": "PNetB",
    "deepJet": "DeepFlavB",
    "UParTAK4": "UParTAK4B",
}


def generate_enum_class(cls):
    enum_string = "enum class {} : int {{\n".format(cls.__name__)
    for item in cls:
        enum_string += "    {} = {},\n".format(item.name, item.value)
    enum_string += "};"
    return enum_string


_BTAG_INITIALIZED = False
_SHAPE_APPLIERS = []

# --- FUNZIONE DI INIZIALIZZAZIONE ---
def initialize_btag_corrections(config):
    """Inizializza le librerie C++ di ROOT e i provider globali di correzione."""
    global _BTAG_INITIALIZED
    if _BTAG_INITIALIZED:
        return
    era = config.get("era")
    period_unc = period_names[era]
    tagger= config.get("bTagAlgo", "particleNet")


    pog_folder = pog_folder_names["BTV"][period_unc]
    json_file = JSON_PATH.format(pog_folder)
    if not os.path.exists(json_file):
        json_file = ALTERNATIVE_JSON_PATH.format(pog_folder)

    json_file_eff = "" # Gestisci qui l'efficienza se loadEfficiency=True (es. via env/parametri)

    headers_dir = os.path.dirname(os.path.abspath(__file__))
    ROOT.gInterpreter.Declare(f'#include "{os.path.join(headers_dir, "btagShape.h")}"')
    ROOT.gInterpreter.Declare(f"{generate_enum_class(WorkingPointsbTag)}")
    ROOT.gInterpreter.Declare(f'#include "{os.path.join(headers_dir, "btag.h")}"')

    ROOT.gInterpreter.ProcessLineSynch(
        f'::correction::bTagCorrProvider::Initialize("{json_file}", "{json_file_eff}", "{tagger}")'
    )
    ROOT.correction.bTagCorrProvider.getGlobal()

    want_shape_str =  "false" # "true" if want_shape else # LATER IT HAS TO BE INCLUDED!! by the time being
    ROOT.gInterpreter.ProcessLineSynch(
        f'::correction::bTagShapeCorrProvider::Initialize("{json_file}", "{periods[period_unc]}", "{tagger}", {want_shape_str})'
    )
    ROOT.correction.bTagShapeCorrProvider.getGlobal()

    ROOT.gInterpreter.Declare(r"""
    #include <map>
    #include <string>
    struct BTagMapApplier {
      std::map<std::string,float> corr;
      float operator()(float w, const std::string &key) const {
        auto it = corr.find(key);
        const float r = (it != corr.end()) ? it->second : 1.0;
        return w * r;
      }
    };
    """)

    _BTAG_INITIALIZED = True


# --- FUNZIONI DI CALCOLO CALLED ON DEMAND ---

def get_wp_values():
    """Ritorna un dizionario con i valori di Working Point."""
    wp_values = {}
    for wp in WorkingPointsbTag:
        root_wp = getattr(ROOT.WorkingPointsbTag, wp.name)
        wp_values[wp] = ROOT.correction.bTagCorrProvider.getGlobal().getWPvalue(root_wp)
    return wp_values


def get_wp_id(df, config):
    tagger=config.get("bTagAlgo", "particleNet")
    jet_collection=config.get("jetCollection_for_btag", "Jet")
    btag_branch = TAGGER_TO_BTAG_BRANCH[tagger]
    df = df.Define(
        f"{jet_collection}_idbtag{btag_branch}",
        f"::correction::bTagCorrProvider::getGlobal().getWPBranch({jet_collection}_btag{btag_branch})",
    )
    return df


# def get_btag_wp_sf(df, jet_collection, tagger="particleNet", return_variations=True, is_central=True):
#     """Calcola i Scale Factors (SF) per i Working Points."""
#     btag_branch = TAGGER_TO_BTAG_BRANCH[tagger]
#     sf_branches = []
#     sf_scales = [up, down] if return_variations else []

#     for source in [central] + UNC_SOURCE_BTAG_WP:
#         for scale in [central] + sf_scales:
#             if source == central and scale != central:
#                 continue
#             if not is_central and scale != central:
#                 continue

#             syst_name = source + scale
#             for wp in WorkingPointsbTag:
#                 branch_name = f"weight_bTagSF_{wp.name}_{syst_name}"
#                 branch_central = f"weight_bTagSF_{wp.name}_{source+central}"

#                 p4 = f"{jet_collection}_p4"
#                 hadron_flavour = f"{jet_collection}_hadronFlavour"
#                 btag_score = f"{jet_collection}_btag{btag_branch}"

#                 df = df.Define(
#                     f"{branch_name}_double",
#                     f""" ::correction::bTagCorrProvider::getGlobal().getSF(
#                             {p4}, {hadron_flavour}, {btag_score}, WorkingPointsbTag::{wp.name},
#                             ::correction::bTagCorrProvider::UncSource::{source}, ::correction::UncScale::{scale}) """,
#                 )

#                 if scale != central:
#                     branch_name_final = branch_name + "_rel"
#                     df = df.Define(branch_name_final, f"static_cast<float>({branch_name}_double/{branch_central})")
#                 else:
#                     branch_name_final = f"weight_bTagSF_{wp.name}_{central}" if source == central else branch_name
#                     df = df.Define(branch_name_final, f"static_cast<float>({branch_name}_double)")

#                 sf_branches.append(branch_name_final)
#     return df, sf_branches


# def get_btag_shape_sf(df, jet_collection, src_name, scale_name, is_central, return_variations, tagger="particleNet"):
#     """Calcola le variazioni di shape b-tagging SF."""
#     btag_branch = TAGGER_TO_BTAG_BRANCH[tagger]
#     sf_scales = [up, down] if return_variations else []
#     sf_branches = []
#     src_list = []
#     scale_list = []
#     force_name_as_central = False

#     if is_central and return_variations:
#         src_list = [central] + UNC_SOURCES_BTAG_SHAPE_NORM
#         scale_list = [central] + sf_scales

#     if not is_central:
#         if IsInJESList(src_name, UNC_SOURCES_BTAG_SHAPE_RE_JES): # Assicurati che IsInJESList sia definita esternamente
#             src_list = [f"jes{src_name}"]
#             scale_list = [scale_name]
#             force_name_as_central = True
#         else:
#             src_list = [central]
#             scale_list = [central]

#     for source in src_list:
#         for scale in scale_list:
#             if (source == central and scale != central) or (source != central and scale == central):
#                 continue

#             syst_name = getSystName(source, scale)
#             branch_name = f"weight_bTagShape_{syst_name}"
#             branch_central = f"weight_bTagShape_{central}"

#             p4 = f"{jet_collection}_p4"
#             hadron_flavour = f"{jet_collection}_hadronFlavour"
#             btag_score = f"{jet_collection}_btag{btag_branch}"

#             df = df.Define(
#                 f"{branch_name}_double",
#                 f"""::correction::bTagShapeCorrProvider::getGlobal().getBTagShapeSF(
#                 {p4}, {hadron_flavour}, {btag_score},
#                 ::correction::bTagShapeCorrProvider::UncSource::{source}, ::correction::UncScale::{scale}) """,
#             )

#             if scale != central and not force_name_as_central:
#                 branch_name_final = branch_name + "_rel"
#                 df = df.Define(branch_name_final, f"static_cast<float>({branch_name}_double/{branch_central})")
#             else:
#                 branch_name_final = f"weight_bTagShape_{central}" if (source == central or force_name_as_central) else branch_name
#                 df = df.Define(branch_name_final, f"static_cast<float>({branch_name}_double)")

#             sf_branches.append(branch_name_final)
#     return df, sf_branches


# # --- FUNZIONI DI SUPPORTO EX-CORRECTOR CLASS ---

# def _define_key_column(df, bins, keycol, syst):
#     """Funzione helper interna per definire le colonne delle categorie di bin."""
#     pieces = []
#     for bin_name, cut in bins.items():
#         pieces.append(f'({cut}) ? std::string("norm_{syst}_{bin_name}") : ')
#     key_expr = "".join(pieces) + 'std::string("__default__")'

#     cols = set(df.GetColumnNames())
#     return df.Redefine(keycol, key_expr) if keycol in cols else df.Define(keycol, key_expr)


# def update_btag_weight(df, norm_file_path, bins, unc_src, unc_scale, sf_branches):
#     """Applica il correttore di normalizzazione sulla shape direttamente sul DataFrame."""
#     global _SHAPE_APPLIERS

#     with open(norm_file_path, "r") as norm_file:
#         shape_weight_corr_dict = json.load(norm_file)

#     unc_src_scale = f"{unc_src}_{unc_scale}" if unc_src != unc_scale else unc_src
#     if unc_src_scale not in shape_weight_corr_dict:
#         raise KeyError(f"Key `{unc_src_scale}` not found in `{norm_file_path}`.")

#     systs = [b.split("_")[2] for b in sf_branches]

#     applier = ROOT.BTagMapApplier()
#     applier.corr["__default__"] = 1.0
#     for k, v in shape_weight_corr_dict[unc_src_scale].items():
#         applier.corr[k] = float(v)

#     # Mantieni il riferimento in memoria per evitare crash di ROOT
#     _SHAPE_APPLIERS.append(applier)

#     for syst in systs:
#         if syst == "Central":
#             continue
#         keycol = f"btag_shape_norm_key_{syst}"
#         df = _define_key_column(df, bins, keycol, syst)

#         branch_name = f"weight_bTagShape_{syst}_rel"
#         df = df.Redefine(branch_name, f"(float){branch_name} * weight_bTagShape_Central").Redefine(
#             branch_name, applier, [branch_name, keycol]
#         )

#     df = _define_key_column(df, bins, "btag_shape_norm_key_Central", "Central")
#     df = df.Redefine(
#         "weight_bTagShape_Central",
#         applier,
#         ["weight_bTagShape_Central", "btag_shape_norm_key_Central"],
#     )

#     for syst in systs:
#         if syst == "Central":
#             continue
#         branch_name = f"weight_bTagShape_{syst}_rel"
#         df = df.Redefine(branch_name, f"(float){branch_name} / weight_bTagShape_Central")

#     return df