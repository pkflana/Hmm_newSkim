import yaml
import os
samples_config = open("/afs/cern.ch/user/p/pflanaga/Hmm_newSkim/config/samples_2024.yaml",'r')
data = yaml.safe_load(samples_config)
nanoaod = 'nanoAOD'
for key in data.keys():
    print(key)
    print(data[key][nanoaod])
    filelist = os.popen(f'dasgoclient --query "file dataset={data[key][nanoaod]}"').read().split('\n')[:-1]
    for i in range(len(filelist)):
        if os.path.exists("/eos/cms/"+filelist[i]):
            filelist[i] = "/eos/cms/"+filelist[i]
        else:
            filelist[i] = "root://cms-xrd-global.cern.ch/"+filelist[i]
    data[key]['filelist'] = filelist
with open('2024withfiles.yaml', 'w') as file:
    yaml.dump(data, file)