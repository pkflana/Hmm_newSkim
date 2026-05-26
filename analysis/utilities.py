import yaml
def get_config(yaml_file):
    with open(yaml_file, "r") as f:
        config = yaml.safe_load(f)
    return config


def GetObservablesCols(obs_name, is_data, nano_version="v12"):
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
