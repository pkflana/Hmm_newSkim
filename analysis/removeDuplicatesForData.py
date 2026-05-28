#!/usr/bin/env python3

import ROOT
import os
import re
import subprocess
import argparse
from collections import defaultdict

ROOT.gROOT.SetBatch(True)
ROOT.EnableThreadSafety()
ROOT.EnableImplicitMT()

ROOT.gInterpreter.Declare(r'''
struct EventDuplicateFilter {

    using LumiMap = std::map<unsigned int, std::set<unsigned long long>>;
    using RunMap  = std::map<unsigned int, LumiMap>;

    std::shared_ptr<RunMap> events;
    std::shared_ptr<std::mutex> mutex;

    EventDuplicateFilter() :
        events(std::make_shared<RunMap>()),
        mutex(std::make_shared<std::mutex>())
    {}

    bool operator()(unsigned int run,
                    unsigned int lumi,
                    unsigned long long event)
    {
        std::lock_guard<std::mutex> lock(*mutex);

        auto& lumiMap = (*events)[run];
        auto& evtSet  = lumiMap[lumi];

        if(evtSet.count(event))
            return false;

        evtSet.insert(event);
        return true;
    }
};
''')


def list_root_files(path):

    if path.endswith(".root"):
        return [path]

    match = re.match(r"root://([^/]+)/(.*)", path)

    if not match:
        raise RuntimeError(f"Invalid xrootd path: {path}")

    host = match.group(1)
    eos_path = "/" + match.group(2).lstrip("/")

    cmd = [
        "xrdfs",
        host,
        "ls",
        "-R",
        eos_path,
    ]

    print("Running:", " ".join(cmd))

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    files = []

    for line in result.stdout.splitlines():

        if not line.endswith(".root"):
            continue

        full_path = f"root://{host}//{line.lstrip('/')}"
        files.append(full_path)

    return sorted(files)

def extract_dataset_name(path):

    parent = os.path.basename(os.path.dirname(path))

    if re.match(r".*Run20[0-9]{2}[A-Z].*", parent):
        return parent

    fname = os.path.basename(path)

    match = re.match(r"(.*Run20[0-9]{2}[A-Z]).*", fname)

    if match:
        return match.group(1)

    return "UnknownDataset"

def merge_dataset(dataset, files, output_dir):

    output_file = output_dir.rstrip('/') + f"/{dataset}.root"

    df = ROOT.RDataFrame("Events", files)

    duplicate_filter = ROOT.EventDuplicateFilter()

    df_filtered = df.Filter(
        duplicate_filter,
        ["run", "luminosityBlock", "event"],
        "RemoveDuplicates"
    )

    columns = [str(c) for c in df.GetColumnNames()]

    opts = ROOT.RDF.RSnapshotOptions()
    opts.fMode = "RECREATE"

    df_filtered.Snapshot(
        "Events",
        output_file,
        columns,
        opts
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i",
        "--inputs",
        nargs="+",
        required=True,
        help="Input xrootd directory or root files"
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output xrootd directory"
    )

    args = parser.parse_args()

    all_files = []

    for inp in args.inputs:
        all_files.extend(list_root_files(inp))

    datasets = defaultdict(list)

    for f in all_files:

        dataset = extract_dataset_name(f)

        if dataset == "UnknownDataset":
            print(f"[WARNING] Could not determine dataset for: {f}")
            continue

        datasets[dataset].append(f)


    for ds, files in datasets.items():
        print(f"  - {ds}: {len(files)} files")

    for dataset, files in datasets.items():
        merge_dataset(dataset, files, args.output)
