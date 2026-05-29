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
```python id="9s5c58"
def merge_dataset(dataset, files, output_dir, remove_inputs=False):

    output_file = (
        output_dir.rstrip("/")
        + f"/{dataset}.root"
    )

    report_file = (
        output_dir.rstrip("/")
        + f"/{dataset}_Report.root"
    )

    print(f"\nProcessing dataset: {dataset}")
    print(f"Output file: {output_file}")

    # ========================================
    # RDF
    # ========================================

    df = ROOT.RDataFrame(
        "Events",
        files
    )

    duplicate_filter = ROOT.EventDuplicateFilter()

    df_filtered = df.Filter(
        duplicate_filter,
        ["run", "luminosityBlock", "event"],
        "RemoveDuplicates"
    )

    report = df_filtered.Report()

    columns = [
        str(c)
        for c in df.GetColumnNames()
    ]

    opts = ROOT.RDF.RSnapshotOptions()
    opts.fMode = "RECREATE"

    # ========================================
    # Snapshot
    # ========================================

    df_filtered.Snapshot(
        "Events",
        output_file,
        columns,
        opts
    )

    # ========================================
    # Save report
    # ========================================

    f_report = ROOT.TFile(
        report_file,
        "RECREATE"
    )

    report.Print()

    for cut in report:

        h = ROOT.TH1D(
            cut.GetName(),
            cut.GetName(),
            1,
            0,
            1
        )

        h.SetBinContent(
            1,
            cut.GetPass()
        )

        h.Write()

    f_report.Close()

    # ========================================
    # Remove original files
    # ========================================

    if remove_inputs:

        print("\nRemoving input files...")

        for f in files:

            print(f"Removing: {f}")

            if f.startswith("root://"):

                match = re.match(
                    r"root://([^/]+)/(.*)",
                    f
                )

                host = match.group(1)
                remote_path = "/" + match.group(2).lstrip("/")

                cmd = [
                    "xrdfs",
                    host,
                    "rm",
                    remote_path,
                ]

                subprocess.run(
                    cmd,
                    check=True
                )

            else:

                os.remove(f)
```


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
