import yaml
import os
base_path = "/afs/cern.ch/user/p/pflanaga/"
samples_config = open(base_path+"Hmm_newSkim/config/samples_2024.yaml",'r')
data = yaml.safe_load(samples_config)
process_names = open(base_path+"Hmm_newSkim/config/process_names.yaml",'r')
processes = yaml.safe_load(process_names)
datasetlist = []
for key in processes.keys():
    for dataset in processes[key]['datasets']:
        datasetlist.append(dataset)
nanoaod = 'nanoAOD'
for key in data.keys():
    if key not in datasetlist:
        continue
    filelist = os.popen(f'dasgoclient --query "file dataset={data[key][nanoaod]}"').read().split('\n')[:-1]
    for i in range(len(filelist)):
        if os.path.exists("/eos/cms/"+filelist[i]):
            filelist[i] = "/eos/cms/"+filelist[i]
        else:
            filelist[i] = "root://cms-xrd-global.cern.ch/"+filelist[i]
    data[key]['filelist'] = filelist
with open('2024withfiles.yaml', 'w') as file:
    yaml.dump(data, file)