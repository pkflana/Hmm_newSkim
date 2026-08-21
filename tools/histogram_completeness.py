"""Read-only completeness checks for per-dataset histogram campaigns."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml

from common.dataset_utilities import resolve_dataset_selection

HISTOGRAM_MC_GROUPS = (
    "DiTriBoson",
    "DY_amcatnlo",
    "DY_amcatnlo_105_160",
    "EWK",
    "signals",
    "SingleH",
    "SingleTop",
    "TTX",
    "TT",
    "W",
)


@dataclass(frozen=True)
class HistogramCheck:
    era: str
    directory: Path
    expected: tuple[str, ...]
    complete: tuple[str, ...]
    missing: tuple[str, ...]
    empty: tuple[str, ...]
    unexpected: tuple[str, ...]


@dataclass(frozen=True)
class TemporaryOutput:
    dataset: str
    directory: Path
    chunks: tuple[str, ...]
    final_present: bool


@dataclass(frozen=True)
class FailedChunks:
    dataset: str
    report: Path
    chunk_numbers: tuple[int, ...]


@dataclass(frozen=True)
class SystematicCheck:
    systematic: str
    datasets: HistogramCheck
    processes: HistogramCheck
    temporary: tuple[TemporaryOutput, ...]
    failed_chunks: tuple[FailedChunks, ...]


@dataclass(frozen=True)
class CampaignCheck:
    era: str
    expected_datasets: tuple[str, ...]
    expected_processes: tuple[str, ...]
    unmapped_datasets: tuple[str, ...]
    systematics: tuple[SystematicCheck, ...]
    merged: HistogramCheck


def normalize_era(value: str) -> str:
    return value if value.startswith("Run3_") else f"Run3_{value}"


def discover_eras(folder: Path) -> list[str]:
    if folder.name.startswith("Run3_"):
        return [folder.name]
    return sorted(
        child.name
        for child in folder.iterdir()
        if child.is_dir() and child.name.startswith("Run3_")
    )


def era_directory(folder: Path, era: str) -> Path:
    return folder if folder.name == era else folder / era


def expected_datasets(
    repository: Path,
    era: str,
    explicit: list[str] | None = None,
    *,
    exact: bool = False,
) -> list[str]:
    if explicit:
        if exact:
            return list(dict.fromkeys(explicit))

        config_dir = repository / "config" / era
        with (config_dir / "process_names.yaml").open() as handle:
            processes = yaml.safe_load(handle) or {}
        with (config_dir / "samples.yaml").open() as handle:
            samples = yaml.safe_load(handle) or {}

        resolved = []
        for name in explicit:
            # Physical dataset names have precedence. Otherwise a configured
            # process name is expanded into the per-dataset histogram names.
            if name in samples or name not in processes:
                resolved.append(name)
            else:
                process = processes[name] or {}
                resolved.extend(process.get("datasets", []) or [])
                resolved.extend(process.get("sub_processes", []) or [])
        return list(dict.fromkeys(resolved))
    return resolve_dataset_selection(repository, era)["datasets"]


def datasets_for_processes(
    repository: Path, era: str, processes: list[str]
) -> list[str]:
    config_path = repository / "config" / era / "process_names.yaml"
    with config_path.open() as handle:
        config = yaml.safe_load(handle) or {}
    datasets = []
    for requested_process in processes:
        process = requested_process
        if process not in config:
            raise KeyError(
                f"group {requested_process!r} is not defined in "
                f"config/{era}/process_names.yaml"
            )
        process_config = config[process] or {}
        datasets.extend(process_config.get("datasets", []) or [])
        datasets.extend(process_config.get("sub_processes", []) or [])
    return list(dict.fromkeys(datasets))


def datasets_for_histogram_groups(
    repository: Path, era: str, groups: list[str]
) -> list[str]:
    """Resolve the MC macrogroups accepted by dataset_campaign.sh."""
    modern = era in {"Run3_2024", "Run3_2025", "Run3_2026"}
    static = {
        "DiTriBoson": [
            "WWW_4F", "WWZ_4F", "WWto2L2Nu_powheg", "WWto4Q_powheg",
            "WWtoLNu2Q_powheg", "WZZ", "WZto2L2Q_powheg",
            "WZtoLNu2Q_powheg", "ZZZ", "ZZto2L2Nu_powheg",
            "ZZto2L2Q_powheg", "ZZto2Nu2Q_powheg", "ZZto4L_powheg",
        ],
        "EWK": ["EWK_2L2J_madgraph_herwig"],
        "signals": [
            "GluGluHto2Mu", "GluGluHto2Mu_M120", "GluGluHto2Mu_M130",
            "GluGluHto2Mu_MiNNLO", "GluGluHto2Mu_amcatnlo",
            "GluGluHto2Mu_tuneDown", "GluGluHto2Mu_tuneUp",
            "VBFHto2Mu_M120", "VBFHto2Mu_M125_amcatnlo",
            "VBFHto2Mu_M125_powheg", "VBFHto2Mu_M130",
            "VBFHto2Mu_m125_Flashsim",
            "VBFHto2Mu_m125_tuneCP5Down_amcatnlo",
            "VBFHto2Mu_m125_tuneCP5Up_amcatnlo",
        ],
        "SingleH": [
            "GluGluHto2B_M125", "VBFHto2B_M125",
            "ggZH_Hto2B_Zto2L", "ggZH_Hto2B_Zto2Q",
            "ZH_Hto2B_Zto2L", "ZH_Hto2B_Zto2Q",
            "WminusH_Hto2B_WtoLNu", "WplusH_Hto2B_WtoLNu",
        ],
        "SingleTop": [
            "TWminusto2L2Nu", "TWminusto4Q", "TWminustoLNu2Q",
            "TbarWplusto2L2Nu", "TbarWplusto4Q", "TbarWplustoLNu2Q",
            "TBbarQto2Q_t_channel_4FS", "TBbarQtoLNu_t_channel_4FS",
            "TBbartoLplusNuBbar_s_channel_4FS",
            "TbarBQto2Q_t_channel_4FS", "TbarBQtoLNu_t_channel_4FS",
            "TbarBtoLminusNuB_s_channel_4FS",
        ],
        "TTX": [
            "TTHto2B_M125", "TTHtoNon2B_M125", "TTWH", "TTWW",
            "TTZH_ZHto4B", "TTZ_Zto2Q",
        ],
        "TT": ["TTto2L2Nu", "TTto4Q", "TTtoLNu2Q"],
    }
    dynamic = {
        "DY_amcatnlo": (
            [
                "DYto2Mu_M_50_amcatnloFXFX",
                "DYto2Tau_M_50_amcatnloFXFX",
                "DYto2E_M_50_amcatnloFXFX",
            ]
            if modern else ["DYto2L_M_50_amcatnloFXFX"]
        ),
        "DY_amcatnlo_105_160": [
            "DYto2Mu_MLL_105to160_amcatnloFXFX",
            *(
                ["DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF"]
                if modern else []
            ),
        ],
        "W": (
            ["WtoMuNu_amcatnloFXFX", "WtoTauNu_amcatnloFXFX"]
            if modern else [
                "WtoLNu_0J_amcatnloFXFX",
                "WtoLNu_1J_amcatnloFXFX",
                "WtoLNu_2J_amcatnloFXFX",
            ]
        ),
    }
    definitions = {**static, **dynamic}
    with (repository / "config" / era / "samples.yaml").open() as handle:
        configured_samples = set((yaml.safe_load(handle) or {}).keys())
    datasets = []
    for group in groups:
        if group not in definitions:
            raise KeyError(
                f"unknown histogram MC group {group!r}; choose from "
                + ", ".join(HISTOGRAM_MC_GROUPS)
            )
        excluded = set()
        if era == "Run3_2023BPix":
            excluded.update({
                "ggZH_Hto2B_Zto2L", "ggZH_Hto2B_Zto2Q",
                "ZH_Hto2B_Zto2L", "ZH_Hto2B_Zto2Q",
                "WminusH_Hto2B_WtoLNu", "WplusH_Hto2B_WtoLNu",
                "TTHto2B_M125", "TTHtoNon2B_M125",
            })
        datasets.extend(
            dataset
            for dataset in definitions[group]
            if dataset in configured_samples and dataset not in excluded
        )
    return list(dict.fromkeys(datasets))


def processes_for_datasets(
    repository: Path, era: str, datasets: list[str]
) -> list[str]:
    """Return every configured process fed by at least one selected dataset."""
    config_path = repository / "config" / era / "process_names.yaml"
    with config_path.open() as handle:
        config = yaml.safe_load(handle) or {}
    selected = set(datasets)
    processes = []
    for process, process_config in config.items():
        process_config = process_config or {}
        inputs = [
            *(process_config.get("datasets", []) or []),
            *(process_config.get("sub_processes", []) or []),
        ]
        if selected.intersection(inputs):
            processes.append(process)
    return processes


def inspect_dataset_work(
    directory: Path, datasets: list[str]
) -> tuple[tuple[TemporaryOutput, ...], tuple[FailedChunks, ...]]:
    temporary = []
    failures = []
    for dataset in datasets:
        tmp_dir = directory / f"{dataset}_tmp"
        final = directory / f"{dataset}.root"
        if tmp_dir.is_dir():
            temporary.append(
                TemporaryOutput(
                    dataset=dataset,
                    directory=tmp_dir,
                    chunks=tuple(path.name for path in sorted(tmp_dir.glob("chunk_*.root"))),
                    final_present=final.is_file() and final.stat().st_size > 0,
                )
            )

        report = directory / f"{dataset}.root.failed_chunks.txt"
        if report.is_file():
            text = report.read_text(errors="replace")
            # hist_maker currently writes "Chunk N", but accepting common
            # variants keeps old campaign reports useful.
            numbers = {
                int(value)
                for value in re.findall(
                    r"(?i)\bchunk(?:_index)?\s*[:=#]?\s*(\d+)", text
                )
            }
            failures.append(
                FailedChunks(
                    dataset=dataset,
                    report=report,
                    chunk_numbers=tuple(sorted(numbers)),
                )
            )
    return tuple(temporary), tuple(failures)


def check_campaign(
    repository: Path,
    campaign: Path,
    era: str,
    systematics: list[str],
    datasets: list[str],
) -> CampaignCheck:
    """Check per-dataset, hadded, and systematic-merged campaign products."""
    processes = processes_for_datasets(repository, era, datasets)
    mapped_datasets = set(
        datasets_for_processes(repository, era, processes)
    )
    systematic_checks = []
    for systematic in systematics:
        dataset_dir = campaign / f"Hists_{systematic}"
        process_dir = campaign / f"Hists_{systematic}_hadded"
        dataset_check = check_histograms(dataset_dir, era, datasets)
        process_check = check_histograms(process_dir, era, processes)
        temporary, failures = inspect_dataset_work(dataset_check.directory, datasets)
        systematic_checks.append(
            SystematicCheck(
                systematic=systematic,
                datasets=dataset_check,
                processes=process_check,
                temporary=temporary,
                failed_chunks=failures,
            )
        )
    return CampaignCheck(
        era=era,
        expected_datasets=tuple(datasets),
        expected_processes=tuple(processes),
        unmapped_datasets=tuple(
            dataset for dataset in datasets if dataset not in mapped_datasets
        ),
        systematics=tuple(systematic_checks),
        merged=check_histograms(
            campaign / "Hists_systMerged", era, processes
        ),
    )


def check_histograms(
    folder: Path,
    era: str,
    expected: list[str],
    suffix: str = "",
) -> HistogramCheck:
    directory = era_directory(folder, era)
    expected_paths = {
        dataset: directory / f"{dataset}{suffix}.root" for dataset in expected
    }
    missing = tuple(
        dataset for dataset, path in expected_paths.items() if not path.exists()
    )
    empty = tuple(
        dataset
        for dataset, path in expected_paths.items()
        if path.exists() and (not path.is_file() or path.stat().st_size == 0)
    )
    complete = tuple(
        dataset
        for dataset, path in expected_paths.items()
        if path.is_file() and path.stat().st_size > 0
    )
    expected_names = {path.name for path in expected_paths.values()}
    unexpected = tuple(
        path.name
        for path in sorted(directory.glob("*.root"))
        if path.name not in expected_names
    ) if directory.is_dir() else ()
    return HistogramCheck(
        era=era,
        directory=directory,
        expected=tuple(expected),
        complete=complete,
        missing=missing,
        empty=empty,
        unexpected=unexpected,
    )
