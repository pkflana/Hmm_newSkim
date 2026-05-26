import htcondor
import yaml
schedd = htcondor.Schedd()
col = htcondor.Collector()
credd = htcondor.Credd()
credd.add_user_cred(htcondor.CredTypes.Kerberos, None)
samples_config = open("2024withfiles.yaml",'r')
data = yaml.safe_load(samples_config)
time = 'tomorrow'
config_file = "/afs/cern.ch/user/p/pflanaga/Hmm_newSkim/config/maincfg_2024.yaml"
for key in data.keys():
    if 'filelist' data[key].keys():
        condorinputs = []
        filecounter = 0
        for file in data[key]['filelist']:
            output_file = "/eos/user/p/pflanaga/skimtest/"+file.replace(".root","out.root")
            condorinputs.append({"arguments":f'''{config_file} {file} {key} {output_file}''',"filename":file.replace(".root",""),"logpath":key+"/"})
            filecounter += 1
        if not os.path.exists("/afs/cern.ch/user/p/pflanaga/Hmm_newSkim/htcondor/output/"+key) and filecounter>0:
            os.makedirs("/afs/cern.ch/user/p/pflanaga/Hmm_newSkim/htcondor/output/"+key)
            os.makedirs("/afs/cern.ch/user/p/pflanaga/Hmm_newSkim/htcondor/error/"+key)
            os.makedirs("/afs/cern.ch/user/p/pflanaga/Hmm_newSkim/htcondor/log/"+key)
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
        "batch_name": key
    })
    job['MY.SendCredential'] = "true"
    if (len(arguments))>0:
        submit_result = schedd.submit(job,itemdata = iter(condorinputs))
