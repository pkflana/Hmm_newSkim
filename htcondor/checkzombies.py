import yaml
import os
import ROOT

def isFileBad(fileToOpen):
    print(fileToOpen)
    if not os.path.exists(fileToOpen):
        return 1
    try:
        file = ROOT.TFile.Open(fileToOpen,"READ")
    except:
        print("Error opening file",fileToOpen)
        return 2
    try:
        if file.IsZombie():
            print("File is zombie",fileToOpen)
            return 3
    except:
        print("Error accessing file",fileToOpen)
        return 4
    event_tree = file.Get("Events")
    if type(event_tree) != ROOT.TTree:
        print("Events tree is not in ",fileToOpen)
        report = file.Get("Report")
        if type(report) != ROOT.TH1D:
            print("file",fileToOpen,"is empty")
            return 5
        else:
            return 6
    return 7


base_path = os.popen("pwd").read().split('\n')[0]
skimconfig = open("skim_cfg.yaml")
skim_config = yaml.safe_load(skimconfig)
era = skim_config['era']
samples_config = open(era+"withfiles.yaml",'r')
data = yaml.safe_load(samples_config)
max_files = skim_config['max_files']
output_directory = skim_config['output_dir']
if output_directory[-1]!='/':
    output_directory+='/'
if os.path.exists("completed_files.txt"):
    with open("completed_files.txt") as file:
        lines = [line.rstrip() for line in file]
    text_file = open("completed_files.txt","a")
else:
    lines = []
    text_file = open("completed_files.txt","w")
for dataset in skim_config['processes']:
    if 'filelist' in data[dataset].keys():
        filecounter = 0
        for file in data[dataset]['filelist']:
            filecounter += 1
            if filecounter > max_files:
                break
            output_file = output_directory+"/"+era+"/"+dataset+"/"+file.replace(".root","skim.root").split("/")[-1]
            if output_file in lines:
                continue
            status = isFileBad(output_file)
            if status<6 and status !=1:
                os.remove(output_file)
            elif status==1:
                pass
            else:
                text_file.write(output_file+'\n')
            print(filecounter,max_files)
text_file.close()
