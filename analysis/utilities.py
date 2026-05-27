import ast
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
