import ast
import os
import sys
from pathlib import Path
import ROOT
import yaml

from enum import Enum
class WorkingPointsbTag(Enum):
    Loose = 1
    Medium = 2
    Tight = 3

def generate_enum_class(cls):
    enum_string = "enum class {} : int {{\n".format(cls.__name__)
    for item in cls:
        enum_string += "    {} = {},\n".format(item.name, item.value)
    enum_string += "};"
    return enum_string

def SaveReport(report, reportName="Report", verbose=0):
    cuts = [c for c in report]
    hist = ROOT.TH1D(reportName, reportName, len(cuts) + 1, 0, len(cuts) + 1)
    if len(cuts) > 0:
        hist.GetXaxis().SetBinLabel(1, "Initial")
        hist.SetBinContent(1, cuts[0].GetAll())
        for c_id, cut in enumerate(cuts):
            hist.SetBinContent(c_id + 2, cut.GetPass())
            hist.GetXaxis().SetBinLabel(c_id + 2, cut.GetName())
            if verbose > 0:
                print(
                    f"for the cut {cut.GetName()} there are {cut.GetPass()} events passed over {cut.GetAll()}, resulting in an efficiency of {cut.GetEff()}"
                )
    return hist



def _column_names(df):
    return {str(col) for col in df.GetColumnNames()}

def _has_column(df, column):
    return column in _column_names(df)

def _define_if_missing(df, name, expression):
    if _has_column(df, name):
        return df
    return df.Define(name, expression)

def _resolve_config_path(yaml_file):
    path = Path(yaml_file)
    if path.exists() or path.is_absolute():
        return path
    return Path(__file__).resolve().parents[1] / path


def get_config(yaml_file):
    yaml_path = _resolve_config_path(yaml_file)
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)
    return config

def process_from_dataset(process_cfg, dataset_name):
    """
    Iterates over process_names.yaml to find which process a dataset name belongs to.
    """
    for process, entry in process_cfg.items():
        if dataset_name in entry['datasets']:
            return process
    return None

def GetObservablesCols(obs_name, is_data, nano_version="v12"):
    col_to_save_path = _resolve_config_path("config/col_to_save.yaml")
    with open(col_to_save_path, "r") as f:
        config_text = f.read()
    columns_literal = config_text.split("\ndef GetObservablesCols", 1)[0].strip()
    observables = ast.literal_eval(columns_literal)
    obs_to_store = []
    if obs_name not in observables.keys():
        raise RuntimeError(f"Invalid observable name, not found in keys {obs_name}")
    obs_dict = observables[obs_name]
    if "base" not in obs_dict.keys():
        raise RuntimeError(f"base key not found in {obs_dict}")
    obs_to_store.extend(obs_dict["base"])
    if nano_version in obs_dict.keys():
        obs_to_store.extend(obs_dict[nano_version])
    if not is_data and "MC" in obs_dict.keys():
        obs_to_store.extend(obs_dict["MC"])
    if "additional" in obs_dict.keys():
        obs_to_store.extend(obs_dict["additional"])
    return obs_to_store



def ListToVector(list, type="string"):
    vec = ROOT.std.vector(type)()
    for item in list:
        vec.push_back(item)
    return vec


def mkdir_recursive(root_file, dir_path):
    if dir_path == "":
        return root_file
    current = root_file
    for folder in dir_path.split("/"):
        if not current.GetDirectory(folder):
            current.mkdir(folder)
        current = current.GetDirectory(folder)
    return current


def mkdir(file, path):
    dir_names = path.split("/")
    current_dir = file
    for n, dir_name in enumerate(dir_names):
        dir_obj = current_dir.Get(dir_name)
        full_name = f"{file.GetPath()}" + "/".join(dir_names[:n])
        if dir_obj:
            if not dir_obj.IsA().InheritsFrom(ROOT.TDirectory.Class()):
                raise RuntimeError(
                    f"{dir_name} already exists in {full_name} and it is not a directory"
                )
        else:
            dir_obj = current_dir.mkdir(dir_name)
            if not dir_obj:

                raise RuntimeError(f"Failed to create {dir_name} in {full_name}")
        current_dir = dir_obj
    return current_dir

rootAnaPathSet = False
def DeclareHeader(header, verbose=0):
    global rootAnaPathSet
    if not rootAnaPathSet:
        if verbose > 0:
            print(f'Adding "{os.environ["ANALYSIS_PATH"]}" to the ROOT include path')
        ROOT.gROOT.ProcessLine(".include " + os.environ["ANALYSIS_PATH"])
        rootAnaPathSet = True
    if verbose > 0:
        print(f'Including "{header}"')
    if not os.path.exists(header):
        raise RuntimeError(f'"{header}" does not exist')
    if not ROOT.gInterpreter.Declare(f'#include "{header}"'):
        raise RuntimeError(f"Failed to include {header}")
    if verbose > 0:
        print(f'Successfully included "{header}"')