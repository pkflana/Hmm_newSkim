import ROOT
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--inFile", required=True, type=str)
parser.add_argument("--inTree", required=False, type=str, default="Events")
args = parser.parse_args()


df = ROOT.RDataFrame(args.inTree, args.inFile)
print(df.Describe())
