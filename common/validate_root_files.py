#!/usr/bin/env python3
"""Validate ROOT event files once and persist a reusable allow-list."""

import argparse
import multiprocessing
import os
import time
from pathlib import Path


def discover_root_files(path):
    if path.endswith(".root"):
        return [os.path.abspath(path)]
    files = []
    for root, _, names in os.walk(path):
        files.extend(
            os.path.abspath(os.path.join(root, name))
            for name in names
            if name.endswith(".root")
        )
    return sorted(files)


def validate_file(task):
    path, tree_name, *retry_options = task
    retries = int(retry_options[0]) if retry_options else 1
    retry_delay = float(retry_options[1]) if len(retry_options) > 1 else 0.0
    # Import ROOT in each spawned worker. Forking an initialized ROOT process is
    # unsafe and can deadlock while opening remote EOS files.
    import ROOT

    last_reason = "unknown validation error"
    for attempt in range(1, retries + 1):
        root_file = None
        try:
            root_file = ROOT.TFile.Open(path, "READ")
            if not root_file or root_file.IsZombie():
                last_reason = "cannot open file or zombie"
            else:
                tree = root_file.Get(tree_name)
                if not tree:
                    last_reason = f"missing tree '{tree_name}'"
                elif tree.GetListOfBranches().GetEntries() == 0:
                    last_reason = f"tree '{tree_name}' has no branches"
                else:
                    return path, True, ""
        except Exception as error:
            last_reason = repr(error)
        finally:
            if root_file:
                root_file.Close()
        if attempt < retries and retry_delay:
            time.sleep(retry_delay)
    return path, False, f"{last_reason} (failed after {retries} attempts)"


def atomic_write_lines(path, lines):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with temporary.open("w") as handle:
        for line in lines:
            handle.write(f"{line}\n")
    os.replace(temporary, output)


def main():
    parser = argparse.ArgumentParser(
        description="Check ROOT Events trees and write a reusable file list."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--tree", default="Events")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be >= 1")
    files = discover_root_files(args.input)
    if not files:
        raise RuntimeError(f"No ROOT files found under {args.input}")
    print(f"[VALIDATE] Found {len(files)} ROOT files", flush=True)

    valid = []
    invalid = []
    context = multiprocessing.get_context("spawn")
    tasks = ((path, args.tree) for path in files)
    with context.Pool(args.workers) as pool:
        for done, (path, ok, reason) in enumerate(
            pool.imap_unordered(validate_file, tasks, chunksize=1), start=1
        ):
            if ok:
                valid.append(path)
            else:
                invalid.append((path, reason))
                print(f"[INVALID] {path}: {reason}", flush=True)
            if done % args.progress_every == 0 or done == len(files):
                print(
                    f"[VALIDATE] {done}/{len(files)} checked; "
                    f"valid={len(valid)}, invalid={len(invalid)}",
                    flush=True,
                )

    atomic_write_lines(args.output, sorted(valid))
    rejected_path = f"{args.output}.invalid.tsv"
    atomic_write_lines(
        rejected_path,
        (f"{path}\t{reason}" for path, reason in sorted(invalid)),
    )
    print(f"[VALIDATE] Valid file list: {args.output}")
    print(f"[VALIDATE] Invalid report:  {rejected_path}")
    if not valid:
        raise RuntimeError("No valid ROOT files were found")


if __name__ == "__main__":
    main()
