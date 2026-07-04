import os, sys
import ROOT
import math
import yaml


def build_uncertainties(yaml_path):
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
        if not block.get("era_correlation"):
          name = name+"_"+year
        uncertainties.append([name, "shape", "1"])


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
signalprocesses = ["VBF"]
backgroundprocesses = ["DY"]
year = sys.argv[1]

outputpath = "/eos/user/p/pflanaga/test/"
histogramfilepath = "/eos/user/p/pflanaga/test/"

if os.path.isdir(outputpath):
  print("already exists")
else:
  os.system("mkdir "+outputpath) #make directory, if it doesn't exist

bands = ["Z_sideband"]

lumidict = {"lumi_1": {"2022": "1.0138", "2023": "1.0017", "2024": "1.0020", "2025": "-"},
            "lumi_2": {"2022": "-", "2023": "1.0127", "2024": "1.0068", "2025": "-"},
            "lumi_3": {"2022": "-", "2023": "-", "2024": "1.0144", "2025": "-"},
            "lumi_2025": {"2022": "-", "2023": "-", "2024": "-", "2025": "1.05"}
}

xsecdict = {"DY": ".7/1.1"
}#TODO: Fill this out, fix naming scheme

for band in bands:
  filename = band + "_" + year
  bandname = "Hmm_" + band + "_" + year
  print(bandname," ",filename)

  B2Gn = "XXXXX"
  uncertainties = build_uncertainties(CONFIG_PATH+"/Run3_"+year+"/systematics.yaml")
  for key in lumidict.keys():
    uncertainties.append([key, "lnN", lumidict[key][year]])
  for key in xsecdict.keys():
    uncertainties.append([key, "lnN", xsecdict[key]])


  #write the actual combine cards
  print("Creating Combine card file",outputpath + band+ ".txt")
  f = open(outputpath + "/" + band + ".txt","w")
  f.write("imax " + str(1) + "\n") #number of channels
  f.write("jmax " + str(len(backgroundprocesses)) + "\n") #number of backgrounds
  f.write("kmax " + str(len(uncertainties)) + "\n") #number of nuisance parameters
  f.write("----------\n")
  f.write("shapes * * " + histogramfilepath + "$PROCESS_withSyst.root $CHANNEL/m_mumu $CHANNEL/m_mumu_$SYSTEMATIC\n")#HERE
  f.write("----------\n")
  f.write("bin         " + band + "_" + year + "\n")#HERE

  #TODO: load ROOT file, find observation number
  f.write("observation " + "0" + "\n")
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
  for i in range(0, len(systLines)): #align uncertainty names, then assemble uncertainty types HERE
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
    rateLine += "-1" #TODO: If there are any samples that don't appear in all bands, this needs to be set to 0 in the cards for the bands where they are absent.

    currentLength = max(len(binLine), len(processLine1), len(processLine2), len(rateLine))
    for j in range(0, len(systLines)): #assemble systematic values
      if (uncertainties[j][0] not in xsecdict.keys()) or (uncertainties[j][0]==allNames[i]):
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