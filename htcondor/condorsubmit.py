import htcondor
import yaml
import os
base_path = os.popen("pwd").read().split('\n')[0]
skimconfig = open("skim_cfg.yaml")
skim_config = yaml.safe_load(skimconfig)
era = skim_config['era']
schedd = htcondor.Schedd()
col = htcondor.Collector()
credd = htcondor.Credd()
credd.add_user_cred(htcondor.CredTypes.Kerberos, None)
samples_config = open(era+"withfiles.yaml",'r')
data = yaml.safe_load(samples_config)
flavour = skim_config['job_flavour']
cpus = skim_config['request_cpus']
memory = skim_config['request_memory']
disk = skim_config['request_disk']
max_files = skim_config['max_files']
output_directory = skim_config['output_dir']
proxy_location = skim_config['proxy_location']
chunk_size = skim_config['chunk_size']
if output_directory[-1]!='/':
    output_directory+='/'
for dataset in skim_config['processes']:
    if 'filelist' in data[dataset].keys():
        condorinputs = []
        filecounter = 0
        for i in range(0,len(data[dataset]['filelist']),chunk_size):
            input_files = []
            output_files = []
            for j in range(chunk_size):
                output_file = data[dataset]['filelist'][i+j].replace(".root","skim.root").split("/")[-1]
                input_files.append(data[dataset]['filelist'][i+j])
                output_files.append(output_directory+"/"+era+"/"+dataset+"/"+output_file)
                filecounter += 1
                if filecounter==max_files:
                    break
            input_list = ",".join(input_files)
            output_list = ",".join(output_files)
            condorinputs.append({"arguments":f'''{proxy_location} {base_path.replace("htcondor","")} {era} {input_list} {dataset} {output_list}''',"filename":input_files[0].replace(".root",""),"logpath":dataset+"/"})
            if filecounter==max_files:
                break
        if not os.path.exists(base_path+"/output/"+dataset) and filecounter>0:
            os.makedirs(base_path+"/output/"+dataset)
            os.makedirs(base_path+"/error/"+dataset)
            os.makedirs(base_path+"/log/"+dataset)
        if not os.path.exists(output_directory+"/"+era+"/"+dataset) and filecounter > 0:
            os.makedirs(output_directory+"/"+era+"/"+dataset)
        job = htcondor.Submit({
            "executable": "run_skim.sh",
            "arguments": "$(arguments)",
            "output": "output/$(logpath)$(filename).$(ClusterId).$(ProcId).out",
            "error": "error/$(logpath)$(filename).$(ClusterId).$(ProcId).err",
            "log": "log/$(logpath)$(filename).$(ClusterId).$(ProcId).log",
            "universe": "vanilla",
            "Requirements": '(OpSysAndVer =?= "AlmaLinux9")',
            "+JobFlavour": flavour,
            "RequestCpus": cpus,
            "request_memory": memory,
            "request_disk": disk,
            "max_retries": "1",
            "batch_name": dataset
        })
        job['MY.SendCredential'] = "true"
        # print(condorinputs)
        if (len(condorinputs))>0:
            if skim_config['submit']:
                submit_result = schedd.submit(job,itemdata = iter(condorinputs))
    else:
        print("you don't have the filelist for:",dataset)
