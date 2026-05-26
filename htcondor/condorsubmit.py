import htcondor
import yaml
base_path = "/afs/cern.ch/user/p/pflanaga/"
schedd = htcondor.Schedd()
col = htcondor.Collector()
credd = htcondor.Credd()
credd.add_user_cred(htcondor.CredTypes.Kerberos, None)
samples_config = open("2024withfiles.yaml",'r')
data = yaml.safe_load(samples_config)
time = 'tomorrow'
config_file_name = base_path+"Hmm_newSkim/config/maincfg_2024.yaml"
config_file = open(config_file_name,'r')
config_data = yaml.safe_load(config_file_name)
output_directory = config_data['outputdirectory']
if output_directory[-1]!='/':
    output_directory+='/'
for dataset in config_data['samplestoprocess']:
    if 'filelist' data[dataset].keys():
        condorinputs = []
        filecounter = 0
        for file in data[dataset]['filelist']:
            output_file = output_directory+dataset+"/"+file.replace(".root","out.root")
            condorinputs.append({"arguments":f'''{config_file_name} {file} {dataset} {output_file}''',"filename":file.replace(".root",""),"logpath":dataset+"/"})
            filecounter += 1
        if not os.path.exists(base_path+"Hmm_newSkim/htcondor/output/"+dataset) and filecounter>0:
            os.makedirs(base_path+"Hmm_newSkim/htcondor/output/"+dataset)
            os.makedirs(base_path+"Hmm_newSkim/htcondor/error/"+dataset)
            os.makedirs(base_path+"Hmm_newSkim/htcondor/log/"+dataset)
        if not os.path.exists(output_directory+dataset) and filecounter > 0:
            os.makedirs(output_directory+dataset)
        job = htcondor.Submit({
            "executable": "run_skim.sh",
            "arguments": "$(arguments)",
            "output": "output/$(logpath)$(filename).$(ClusterId).$(ProcId).out",
            "error": "error/$(logpath)$(filename).$(ClusterId).$(ProcId).err",
            "log": "log/$(logpath)$(filename).$(ClusterId).$(ProcId).log",
            "universe": "vanilla",
            "Requirements": '(OpSysAndVer =?= "AlmaLinux9")',
            "+JobFlavour": time,
            "RequestCpus": "10",
            "max_retries": "1",
            "batch_name": dataset
        })
        job['MY.SendCredential'] = "true"
        if (len(arguments))>0:
            submit_result = schedd.submit(job,itemdata = iter(condorinputs))
    else:
        print("you don't have the filelist for:",dataset)
