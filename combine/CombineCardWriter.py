import os, sys
import ROOT
import math
import yaml


def build_uncertainties(yaml_path, processes):
    #Build the uncertainties list from the configuration file.
    with open(yaml_path, "r") as f:
        cfg = yaml.safe_load(f)

    uncertainties = []

    # Combine systematics and weights sections
    sections = {}
    sections.update(cfg["systematics"])
    sections.update(cfg["weights"])

    for key, block in sections.items():
        name = block.get("name", "")
        if name=="":
          continue
        name = name.replace("_{scale}","").replace("_{}","")
        # if not block.get("era_correlation"):
        #   name = name+"_"+year
        if name.find("{era}")!=-1:
          name = name.replace("{era}",year)
        if name.find("{process}")!=-1:
          if name.find("QCDscale")!=-1:
            for variation in cfg["qcd_scale"]["variations"]:
              for proc in processes:
                procname = variation["name"].replace("{process}", cfg["qcd_scale"]["process_labels"][proc])
                key = [uncertainty[0]==procname for uncertainty in uncertainties]
                if any(key):
                  uncertainties[key.index(True)][3].append(proc)
                else:
                  uncertainties.append([procname, "shape", "1", [proc]])
          # expand into one uncertainty per process
          else:
            for proc in processes:
              procname = name.replace("{process}", proc)
              # 4th element = the process this uncertainty applies to
              uncertainties.append([procname, "shape", "1", [proc]])
        elif name.find("{pdf_process}")!=-1:
          for proc in processes:
            procname = name.replace("{pdf_process}", cfg["pdf"]["process_labels"][proc])
            key = [uncertainty[0]==procname for uncertainty in uncertainties]
            if any(key):
              uncertainties[key.index(True)][3].append(proc)
            else:
              uncertainties.append([procname, "shape", "1", [proc]])
        else:
          uncertainties.append([name, "shape", "1", None])


    return uncertainties


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_PATH = os.environ.get(
    "ANALYSIS_PATH",
    os.path.abspath(os.path.join(BASE_PATH, "..")),
)

if "ANALYSIS_PATH" not in os.environ:
    print(
        f"Environment variable ANALYSIS_PATH is not set, "
        f"using {ANALYSIS_PATH} as default"
    )
else:
    print(f"Using ANALYSIS_PATH={ANALYSIS_PATH}")
CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")


#define the input names
signalprocesses = ["VBFHto2Mu_M125_amcatnlo","GluGluHto2Mu_amcatnlo"]
backgroundprocesses = ["DYto2Mu_MLL105To160","EWK_2Mu2J_MLL_105to160_herwig","ST","VV","TT","VVV","W_NJets","TTH_inclusive","TW","VH_inclusive","H"]
year = sys.argv[1]

outputpath = "/eos/user/p/pflanaga/combinetest2/"
histogramfilepath = "/eos/user/p/pflanaga/combinetest2/Run3_"+year+"/"

if os.path.isdir(outputpath):
  print("already exists")
else:
  os.system("mkdir "+outputpath) #make directory, if it doesn't exist

bands = ["Signal_Fit_VBF"]

lumidict = {"lumi_1": {"2022": "1.0138", "2023": "1.0017", "2024": "1.0020", "2025": "-"},
            "lumi_2": {"2022": "-", "2023": "1.0127", "2024": "1.0068", "2025": "-"},
            "lumi_3": {"2022": "-", "2023": "-", "2024": "1.0144", "2025": "-"},
            "lumi_2025": {"2022": "-", "2023": "-", "2024": "-", "2025": "1.05"}
}

xsecdict = {#"DYto2Mu_MLL105To160": ".7/1.1"
}#TODO: Fill this out, fix naming scheme

for band in bands:
  filename = band + "_" + year
  bandname = band# + "_" + year
  print(bandname," ",filename)

  uncertainties = build_uncertainties(CONFIG_PATH+"/Run3_"+year+"/systematics.yaml",signalprocesses+backgroundprocesses)
  for key in lumidict.keys():
    uncertainties.append([key, "lnN", lumidict[key][year], None])
  for key in xsecdict.keys():
    uncertainties.append([key, "lnN", xsecdict[key], None])


  #write the actual combine cards
  print("Creating Combine card file",outputpath + band+ ".txt")
  f = open(outputpath + "/" + band + ".txt","w")
  f.write("imax " + str(1) + "\n") #number of channels
  f.write("jmax " + str(len(backgroundprocesses)) + "\n") #number of backgrounds
  f.write("kmax " + str(len(uncertainties)) + "\n") #number of nuisance parameters
  # f.write("----------\n")
  # f.write("shapes * * $PROCESS.root $CHANNEL/DNN_NNOutput $CHANNEL/DNN_NNOutput_$SYSTEMATIC\n")
  # f.write("----------\n")
  # f.write("bin         " + band + "\n")
  f.write("----------\n")

  # Per-process shapes lines (no $PROCESS in filename).
  f.write(
      "shapes data_obs {ch}_{era} Run3_{era}/{file} {ch}/DNN_NNOutput\n".format(
          ch=band,
          file= "data_obs.root",
          era=year,
      )
  )
  for proc in signalprocesses + backgroundprocesses:
      f.write(
          "shapes {proc} {ch}_{era} Run3_{era}/{file} {ch}/DNN_NNOutput {ch}/DNN_NNOutput_$SYSTEMATIC\n".format(
              proc=proc,
              ch=band,
              file= proc + ".root",
              era=year,
          )
      )
  f.write("----------\n")
  f.write("bin         " + band + "_" + year + "\n")

  data = ROOT.TFile.Open(histogramfilepath+"data_obs.root")
  datahistogram = data.Get("Signal_Fit_VBF/DNN_NNOutput")
  print(histogramfilepath+"data_obs.root")
  f.write("observation " + "0" + "\n")#TODO:Fix this, data currently has value str(datahistogram.Integral()) + "\n")
  f.write("----------\n")

  ##assemble strings for lines
  print("Assembling lines for Combine card ",bandname)
  systLines = []
  maxLength = 0
  print("uncertainties",uncertainties)
  for i in range(0, len(uncertainties)): 
    systLines.append(uncertainties[i][0])
    maxLength = max(maxLength, len(systLines[i]))

  maxLength2 = 0
  for i in range(0, len(systLines)): #align uncertainty names, then assemble uncertainty types
    while len(systLines[i]) < (maxLength + 3):
      systLines[i] += " "
    systLines[i] += uncertainties[i][1]
    maxLength2 = max(maxLength2, len(systLines[i]))

  for i in range(0, len(systLines)): #align syst types
    while len(systLines[i]) < (maxLength2 + 5):
      systLines[i] += " "

  maxLength2 = len(systLines[0])

  #assemble bin and process block
  allNames = signalprocesses + backgroundprocesses
  allNumbers = []
  for i in range(-len(signalprocesses)+1, 1): #negative and zero numbers for signals
    allNumbers.append(i)
  for i in range (1, len(backgroundprocesses)+1): #positive nonzero numbers for backgrounds
    allNumbers.append(i)
  binLine      = "bin     "
  processLine1 = "process "
  processLine2 = "process "
  rateLine     = "rate    "

  #align bin, process, and rate lines with systematic line length
  while len(binLine) < maxLength2:
    binLine += " "
  while len(processLine1) < maxLength2:
    processLine1 += " "
  while len(processLine2) < maxLength2:
    processLine2 += " "
  while len(rateLine) < maxLength2:
    rateLine += " "

  for i in range(0, len(allNames)): #assemble bin, process, rate, and systematic line entries, then align HERE
    binLine += band + "_" + year
    processLine1 += allNames[i]
    processLine2 += str(allNumbers[i])
    rateLine += "-1"
    currentLength = max(len(binLine), len(processLine1), len(processLine2), len(rateLine))
    for j in range(0, len(systLines)): #assemble systematic values
      proc_tag = uncertainties[j][3]  # process this syst is tied to (or None)
      if proc_tag is not None:
        # {process}-expanded systematic: value only for matching process
        if allNames[i] in proc_tag:#proc_tag == allNames[i]:
          systLines[j] += uncertainties[j][2]
        else:
          systLines[j] += "-"+" "*(len(uncertainties[j][2])-1)
      elif (uncertainties[j][0] not in xsecdict.keys()) or (uncertainties[j][0]==allNames[i]):
        systLines[j] += uncertainties[j][2]
      else:
        systLines[j] += "-"+" "*(len(uncertainties[j][2])-1)
      currentLength = max(currentLength, len(systLines[j]))

    #align all lines with extra space
    currentLength += 5

    while len(binLine) < currentLength:
      binLine += " "

    while len(processLine1) < currentLength:
      processLine1 += " "

    while len(processLine2) < currentLength:
      processLine2 += " "

    while len(rateLine) < currentLength:
      rateLine += " "

    for j in range(0, len(systLines)):
      while len(systLines[j]) < currentLength:
        systLines[j] += " "

  print("Writing Combine Card values")
  f.write(binLine + "\n")
  f.write(processLine1 + "\n")
  f.write(processLine2 + "\n")
  f.write(rateLine + "\n")
  f.write("----------\n")

  for i in range(0, len(systLines)):
    f.write(systLines[i] + "\n")

  #add MC statistics evaluation
  f.write("\n")
  f.write("* autoMCStats 10")

  f.close()