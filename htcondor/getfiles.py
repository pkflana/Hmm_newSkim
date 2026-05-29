import yaml
import os
#voms-proxy-init --voms cms --valid 192:00
skimconfig = open("skim_cfg.yaml")
skim_config = yaml.safe_load(skimconfig)
base_path = os.popen("pwd").read().split('\n')[0]
samples_config = open(base_path.replace("htcondor","config")+"/"+skim_config['era']+"/samples.yaml",'r')
data = yaml.safe_load(samples_config)
process_names = open(base_path.replace("htcondor","config")+"/"+skim_config['era']+"/process_names.yaml",'r')
processes = yaml.safe_load(process_names)
datasetlist = []
for key in processes.keys():
    if 'datasets' in processes[key].keys():
        for dataset in processes[key]['datasets']:
            datasetlist.append(dataset)
    else:
        print(key,"has no datasets in process_names.yaml")
nanoaod = 'nanoAOD'
for key in data.keys():
    if key not in datasetlist:
        continue
    if nanoaod not in data[key].keys():
        print("Missing nanoAOD for",key,"in samples.yaml")
        continue
    filelist = os.popen(f'dasgoclient --query "file dataset={data[key][nanoaod]}"').read().split('\n')[:-1]
    for i in range(len(filelist)):
        if os.path.exists("/eos/cms/"+filelist[i]):
            filelist[i] = "/eos/cms/"+filelist[i]
        else:
            filelist[i] = "root://cms-xrd-global.cern.ch/"+filelist[i]
    data[key]['filelist'] = filelist
with open(skim_config['era']+'withfiles.yaml', 'w') as file:
    yaml.dump(data, file)