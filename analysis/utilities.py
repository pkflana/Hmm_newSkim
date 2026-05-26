import yaml
def get_config(yaml_file):
    with open(yaml_file, "r") as f:
        config = yaml.safe_load(f)
    return config
