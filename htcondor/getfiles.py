import os
import yaml

# voms-proxy-init --voms cms --valid 192:00

# =========================================================
# Base paths
# =========================================================

ANALYSIS_PATH = os.environ.get("ANALYSIS_PATH")

if ANALYSIS_PATH is None:
    raise RuntimeError("Environment variable ANALYSIS_PATH is not set")

CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")

# =========================================================
# Load skim configuration
# =========================================================
era = "Run3_2022EE"
skim_cfg_path = os.path.join(
    CONFIG_PATH,
    era,
    "skim_cfg.yaml"
)

with open(skim_cfg_path, "r") as skimconfig:
    skim_config = yaml.safe_load(skimconfig)


# =========================================================
# Load samples and process definitions
# =========================================================

samples_yaml = os.path.join(CONFIG_PATH, era, "samples.yaml")
process_yaml = os.path.join(CONFIG_PATH, era, "process_names.yaml")

with open(samples_yaml, "r") as samples_config:
    data = yaml.safe_load(samples_config)

with open(process_yaml, "r") as process_names:
    processes = yaml.safe_load(process_names)

# =========================================================
# Build dataset list
# =========================================================

datasetlist = []

for key in processes.keys():

    if "datasets" in processes[key]:
        datasetlist.extend(processes[key]["datasets"])

    else:
        print(f"{key} has no datasets in process_names.yaml")

# =========================================================
# Add filelists
# =========================================================

nanoaod = "nanoAOD"
istance = None

for key in data.keys():

    if key not in datasetlist:
        continue

    if nanoaod not in data[key]:
        print(f"Missing nanoAOD for {key} in samples.yaml")
        continue

    dataset = data[key][nanoaod]


    query = f'dasgoclient --query="file dataset={dataset}"'
    if data[key].Get("instance", None):
        istance= data[key].Get("instance", None)
        query += f" istance={istance}"
    filelist = os.popen(query).read().splitlines()

    resolved_files = []

    for filepath in filelist:

        eos_path = f"/eos/cms/{filepath}"

        if os.path.exists(eos_path):
            resolved_files.append(eos_path)

        else:
            resolved_files.append(
                f"root://cms-xrd-global.cern.ch/{filepath}"
            )

    data[key]["filelist"] = resolved_files

# =========================================================
# Write output
# =========================================================

output_yaml = os.path.join(
    CONFIG_PATH,
    era,
    f"samples_withfiles.yaml"
)

with open(output_yaml, "w") as outfile:
    yaml.dump(
        data,
        outfile,
        default_flow_style=False,
        sort_keys=False
    )

print(f"Saved output to {output_yaml}")

# import yaml
# import os
# #voms-proxy-init --voms cms --valid 192:00
# skimconfig = open("/afs/cern.ch/work/v/vdamante/Hmm_newSkim/config/Run3_2022/skim_cfg.yaml")
# skim_config = yaml.safe_load(skimconfig)
# base_path = os.popen("pwd").read().split('\n')[0]
# samples_config = open(base_path.replace("htcondor","config")+"/"+skim_config['era']+"/samples.yaml",'r')
# data = yaml.safe_load(samples_config)
# process_names = open(base_path.replace("htcondor","config")+"/"+skim_config['era']+"/process_names.yaml",'r')
# processes = yaml.safe_load(process_names)
# datasetlist = []
# for key in processes.keys():
#     if 'datasets' in processes[key].keys():
#         for dataset in processes[key]['datasets']:
#             datasetlist.append(dataset)
#     else:
#         print(key,"has no datasets in process_names.yaml")
# nanoaod = 'nanoAOD'
# for key in data.keys():
#     if key not in datasetlist:
#         continue
#     if nanoaod not in data[key].keys():
#         print("Missing nanoAOD for",key,"in samples.yaml")
#         continue
#     filelist = os.popen(f'dasgoclient --query "file dataset={data[key][nanoaod]}"').read().split('\n')[:-1]
#     for i in range(len(filelist)):
#         if os.path.exists("/eos/cms/"+filelist[i]):
#             filelist[i] = "/eos/cms/"+filelist[i]
#         else:
#             filelist[i] = "root://cms-xrd-global.cern.ch/"+filelist[i]
#     data[key]['filelist'] = filelist
# with open(skim_config['era']+'withfiles.yaml', 'w') as file:
#     yaml.dump(data, file)