import os
import yaml
import htcondor

# =========================================================
# Environment
# =========================================================

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_PATH = os.path.abspath(os.path.join(BASE_PATH, ".."))


print(f"Environment variable ANALYSIS_PATH is not set, using {ANALYSIS_PATH} as default")
# if ANALYSIS_PATH is None:
    # raise RuntimeError("Environment variable ANALYSIS_PATH is not set")

HTCONDOR_PATH = os.path.join(ANALYSIS_PATH, "htcondor")
CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")
EOS_PATH = "/eos/user/v/vdamante/condor_logs_hmm/"

# =========================================================
# Load skim configuration
# =========================================================

era = "Run3_2022"
skim_cfg_path = os.path.join(
    CONFIG_PATH,
    era,
    "skim_cfg.yaml"
)

with open(skim_cfg_path, "r") as skimconfig:
    skim_config = yaml.safe_load(skimconfig)


# =========================================================
# HTCondor setup
# =========================================================

schedd = htcondor.Schedd()
col = htcondor.Collector()
credd = htcondor.Credd()

credd.add_user_cred(htcondor.CredTypes.Kerberos, None)

# =========================================================
# Load datasets
# =========================================================

processes_yaml = os.path.join(
    CONFIG_PATH,
    era,
    f"process_names.yaml"
)
with open(processes_yaml, "r") as processes_config:
    processes_cfg = yaml.safe_load(processes_config)
# print(processes_cfg)
samples_yaml = os.path.join(
    CONFIG_PATH,
    era,
    f"samples_withfiles.yaml"
)


with open(samples_yaml, "r") as samples_config:
    data = yaml.safe_load(samples_config)

# =========================================================
# Configuration
# =========================================================

flavour = skim_config["job_flavour"]
cpus = skim_config["request_cpus"]
memory = skim_config["request_memory"]
disk = skim_config["request_disk"]

max_files = skim_config["max_files"]
chunk_size = skim_config["chunk_size"]

output_directory = skim_config["output_dir"]
proxy_location = skim_config["proxy_location"]

output_directory = os.path.abspath(output_directory)

# =========================================================
# Submit jobs
# =========================================================

for process in skim_config["process_to_select"]:
    for dataset in processes_cfg[process].get("datasets", [])+processes_cfg[process].get("sub_processes", []):
        if "filelist" not in data[dataset]:
            print(f"You don't have the filelist for: {dataset}")
            continue

        condorinputs = []
        filecounter = 0

        filelist = data[dataset]["filelist"]

        for i in range(0, len(filelist), chunk_size):

            input_files = []
            output_files = []

            chunk = filelist[i:i + chunk_size]

            for infile in chunk:

                output_file = (
                    os.path.basename(infile)
                    .replace(".root", "_skim.root")
                )

                outfile = os.path.join(
                    output_directory,
                    era,
                    dataset,
                    output_file
                )

                input_files.append(infile)
                output_files.append(outfile)

                filecounter += 1

                # if max_files > 0 and filecounter >= max_files:
                #     break

            if len(input_files) == 0:
                continue

            input_list = ",".join(input_files)
            output_list = ",".join(output_files)

            arguments = (
                f"{proxy_location} "
                f"{ANALYSIS_PATH} "
                f"{era} "
                f"{input_list} "
                f"{dataset} "
                f"{output_list}"
            )

            condorinputs.append({
                "arguments": arguments,
                "filename": os.path.basename(
                    input_files[0].replace(".root", "")
                ),
                "logpath": f"{dataset}/"
            })

            # if filecounter >= max_files:
            #     break

        # =====================================================
        # Create log directories
        # =====================================================

        if filecounter > 0:

            for dirname in ["output", "error", "log"]:

                path = os.path.join(
                    HTCONDOR_PATH,
                    era,
                    dirname,
                    dataset
                )

                os.makedirs(path, exist_ok=True)

            output_dataset_dir = os.path.join(
                output_directory,
                era,
                dataset
            )

            os.makedirs(output_dataset_dir, exist_ok=True)

        # =====================================================
        # Submit description
        # =====================================================

        executable_path = os.path.join(
            HTCONDOR_PATH,
            "run_skim.sh"
        )

        log_path = f"{HTCONDOR_PATH}/{era}/log/{dataset}"
        error_path = f"{HTCONDOR_PATH}/{era}/error/{dataset}"
        output_path = f"{HTCONDOR_PATH}/{era}/output/{dataset}"
        job = htcondor.Submit({

            "executable": executable_path,

            "arguments": "$(arguments)",

            "output":
                os.path.join(
                    output_path,
                    "$(logpath)$(filename).$(ClusterId).$(ProcId).out"
                ),

            "error":
                os.path.join(
                    error_path,
                    "$(logpath)$(filename).$(ClusterId).$(ProcId).out"
                ),

            "log":
                os.path.join(
                    log_path,
                    "$(logpath)$(filename).$(ClusterId).$(ProcId).out"
                ),

            "universe": "vanilla",

            "Requirements":
                '(OpSysAndVer =?= "AlmaLinux9")',

            "+JobFlavour": flavour,

            "RequestCpus": cpus,

            "request_memory": memory,

            "request_disk": disk,

            "max_retries": "1",

            "batch_name": dataset
        })

        job["MY.SendCredential"] = "true"

        # =====================================================
        # Submit
        # =====================================================

        if len(condorinputs) > 0:

            print(
                f"Submitting {len(condorinputs)} jobs "
                f"for dataset {dataset}"
            )

            if skim_config["submit"]:

                submit_result = schedd.submit(
                    job,
                    itemdata=iter(condorinputs)
                )

# import htcondor
# import yaml
# import os
# base_path = os.popen("pwd").read().split('\n')[0]
# skimconfig = open("skim_cfg.yaml")
# skim_config = yaml.safe_load(skimconfig)
# era = skim_config['era']
# schedd = htcondor.Schedd()
# col = htcondor.Collector()
# credd = htcondor.Credd()
# credd.add_user_cred(htcondor.CredTypes.Kerberos, None)
# samples_config = open(era+"withfiles.yaml",'r')
# data = yaml.safe_load(samples_config)
# flavour = skim_config['job_flavour']
# cpus = skim_config['request_cpus']
# memory = skim_config['request_memory']
# disk = skim_config['request_disk']
# max_files = skim_config['max_files']
# output_directory = skim_config['output_dir']
# proxy_location = skim_config['proxy_location']
# chunk_size = skim_config['chunk_size']
# if output_directory[-1]!='/':
#     output_directory+='/'
# for dataset in skim_config['processes']:
#     if 'filelist' in data[dataset].keys():
#         condorinputs = []
#         filecounter = 0
#         for i in range(0,len(data[dataset]['filelist']),chunk_size):
#             input_files = []
#             output_files = []
#             for j in range(chunk_size):
#                 output_file = data[dataset]['filelist'][i+j].replace(".root","skim.root").split("/")[-1]
#                 input_files.append(data[dataset]['filelist'][i+j])
#                 output_files.append(output_directory+"/"+era+"/"+dataset+"/"+output_file)
#                 filecounter += 1
#                 if filecounter==max_files:
#                     break
#             input_list = ",".join(input_files)
#             output_list = ",".join(output_files)
#             condorinputs.append({"arguments":f'''{proxy_location} {base_path.replace("htcondor","")} {era} {input_list} {dataset} {output_list}''',"filename":input_files[0].replace(".root",""),"logpath":dataset+"/"})
#             if filecounter==max_files:
#                 break
#         if not os.path.exists(base_path+"/output/"+dataset) and filecounter>0:
#             os.makedirs(base_path+"/output/"+dataset)
#             os.makedirs(base_path+"/error/"+dataset)
#             os.makedirs(base_path+"/log/"+dataset)
#         if not os.path.exists(output_directory+"/"+era+"/"+dataset) and filecounter > 0:
#             os.makedirs(output_directory+"/"+era+"/"+dataset)
#         job = htcondor.Submit({
#             "executable": "run_skim.sh",
#             "arguments": "$(arguments)",
#             "output": "output/$(logpath)$(filename).$(ClusterId).$(ProcId).out",
#             "error": "error/$(logpath)$(filename).$(ClusterId).$(ProcId).err",
#             "log": "log/$(logpath)$(filename).$(ClusterId).$(ProcId).log",
#             "universe": "vanilla",
#             "Requirements": '(OpSysAndVer =?= "AlmaLinux9")',
#             "+JobFlavour": flavour,
#             "RequestCpus": cpus,
#             "request_memory": memory,
#             "request_disk": disk,
#             "max_retries": "1",
#             "batch_name": dataset
#         })
#         job['MY.SendCredential'] = "true"
#         # print(condorinputs)
#         if (len(condorinputs))>0:
#             if skim_config['submit']:
#                 submit_result = schedd.submit(job,itemdata = iter(condorinputs))
#     else:
#         print("you don't have the filelist for:",dataset)
