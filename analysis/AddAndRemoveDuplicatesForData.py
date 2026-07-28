#!/usr/bin/env python3

import ROOT
import os
import json
import argparse

ROOT.gROOT.SetBatch(True)

ROOT.EnableThreadSafety()
ROOT.EnableImplicitMT()

# =========================================================
# Duplicate filter
# =========================================================

ROOT.gInterpreter.Declare(
r'''
#include <map>
#include <set>
#include <mutex>
#include <memory>

struct EventDuplicateFilter {

    using LumiMap = std::map<unsigned int,
                    std::set<unsigned long long>>;

    using RunMap = std::map<unsigned int, LumiMap>;

    std::shared_ptr<RunMap> events;
    std::shared_ptr<std::mutex> mutex;

    EventDuplicateFilter():
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

        if (evtSet.count(event))
            return false;

        evtSet.insert(event);

        return true;
    }
};
'''
)

# =========================================================
# Utilities
# =========================================================

def list_root_files(path):

    if path.endswith(".root"):
        return [path]

    files = []

    for root, _, fnames in os.walk(path):

        for fname in fnames:

            if fname.endswith(".root"):

                files.append(
                    os.path.join(root, fname)
                )

    return sorted(files)


def extract_dataset_name(path):

    return os.path.basename(
        path.rstrip("/")
    )

# =========================================================
# JSON utilities
# =========================================================

def report_path_for_root(root_file):
    directory = os.path.dirname(root_file)
    stem = os.path.splitext(os.path.basename(root_file))[0]
    if stem.startswith("skim_") and stem[len("skim_"):].isdigit():
        return os.path.join(directory, f"report_{stem[len('skim_'):]}.json")
    return os.path.splitext(root_file)[0] + "_report.json"


def load_report_json(root_file):

    json_file = report_path_for_root(root_file)

    if not os.path.exists(json_file):

        print(f"[WARNING] Missing json: {json_file}")

        return {}

    with open(json_file) as f:

        return json.load(f)


def merge_reports(report_list):

    merged = {}

    total_initial = 0

    # =====================================================
    # First pass
    # =====================================================

    for report in report_list:

        if "Initial" in report:

            total_initial += report["Initial"]

        for key, value in report.items():

            if key == "Initial":
                continue

            if key not in merged:

                merged[key] = {
                    "pass": 0,
                    "eff": 0.0
                }

            if isinstance(value, dict):

                merged[key]["pass"] += value.get("pass", 0)

    # =====================================================
    # Recompute efficiencies
    # =====================================================

    merged["Initial"] = total_initial

    for key, value in merged.items():

        if key == "Initial":
            continue

        passed = value["pass"]

        if total_initial > 0:

            value["eff"] = passed / total_initial

        else:

            value["eff"] = 0.0

    return merged

# =========================================================
# Merge dataset
# =========================================================

def merge_dataset(
    dataset,
    files,
    is_data,
    output_dir,
    remove_inputs=False,
):

    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(
        output_dir,
        f"{dataset}.root"
    )

    output_json = os.path.join(
        output_dir,
        f"{dataset}_report.json"
    )

    print("\n================================================")
    print(f"Dataset : {dataset}")
    print(f"N files : {len(files)}")
    print(f"Output  : {output_file}")
    print("================================================\n")

    # =====================================================
    # Merge json reports
    # =====================================================

    report_list = []

    for f in files:

        report_list.append(
            load_report_json(f)
        )

    merged_report = merge_reports(report_list)

    # =====================================================
    # Create dataframe
    # =====================================================

    df = ROOT.RDataFrame(
        "Events",
        files
    )

    # =====================================================
    # Duplicate removal
    # =====================================================

    duplicate_filter = ROOT.EventDuplicateFilter()

    df_filtered = (
        df.Filter(
            duplicate_filter,
            ["run", "luminosityBlock", "event"],
            "RemoveDuplicates"
        ) if is_data else df
        #.Cache()
    )

    # =====================================================
    # Report
    # =====================================================

    report = df_filtered.Report()

    # =====================================================
    # Columns
    # =====================================================

    columns = ROOT.std.vector('string')()

    for c in df.GetColumnNames():
        columns.push_back(str(c))

    # =====================================================
    # Snapshot options
    # =====================================================

    opts = ROOT.RDF.RSnapshotOptions()

    opts.fMode = "RECREATE"

    # =====================================================
    # Snapshot
    # =====================================================

    print("Writing snapshot...")

    snapshot = df_filtered.Snapshot(
        "Events",
        output_file,
        columns,
        opts
    )

    # =====================================================
    # Trigger event loop ONCE
    # =====================================================

    snapshot.GetValue()

    # =====================================================
    # Save merged report json
    # =====================================================

    with open(output_json, "w") as fjson:

        json.dump(
            merged_report,
            fjson,
            indent=4
        )

    print(f"\nSaved merged report: {output_json}")

    # =====================================================
    # Print report
    # =====================================================

    print("\n================ REPORT ================\n")

    report.Print()

    # =====================================================
    # Check output
    # =====================================================

    f = ROOT.TFile.Open(output_file)

    t = f.Get("Events")

    if not t:

        print("[ERROR] Output tree not found")

    else:

        print(f"\nSaved tree with {t.GetEntries()} entries")

    f.Close()

    # =====================================================
    # Remove input files
    # =====================================================

    if remove_inputs:

        print("\nRemoving input files...\n")

        for f in files:

            try:

                print(f"Removing: {f}")

                os.remove(f)

                json_file = report_path_for_root(f)

                if os.path.exists(json_file):

                    print(f"Removing: {json_file}")

                    os.remove(json_file)

            except Exception as e:

                print(f"[WARNING] Could not remove {f}")

                print(e)

    print("\nDone.\n")

# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input ROOT files or directories"
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output directory"
    )

    parser.add_argument(
        "--remove-inputs",
        action="store_true",
        help="Remove original ROOT and JSON files"
    )
    parser.add_argument(
        "--is-data",
        action="store_true",
        help="Remove original ROOT and JSON files"
    )


    args = parser.parse_args()

    for inp in args.inputs:

        dataset = extract_dataset_name(inp)

        files = list_root_files(inp)

        if len(files) == 0:

            print(
                f"[WARNING] No ROOT files found in {inp}"
            )

            continue

        merge_dataset(
            dataset=dataset,
            files=files,
            is_data=args.is_data,
            output_dir=args.output,
            remove_inputs=args.remove_inputs,
        )
