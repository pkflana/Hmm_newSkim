from pathlib import Path

from common.histogram_completeness import (
    check_campaign,
    check_histograms,
    datasets_for_processes,
    datasets_for_histogram_groups,
    discover_eras,
    expected_datasets,
    inspect_dataset_work,
    processes_for_datasets,
)


def test_check_histograms_classifies_missing_empty_and_extra(tmp_path: Path):
    era_dir = tmp_path / "Run3_2024"
    era_dir.mkdir()
    (era_dir / "good.root").write_bytes(b"root")
    (era_dir / "empty.root").touch()
    (era_dir / "extra.root").write_bytes(b"root")

    result = check_histograms(
        tmp_path, "Run3_2024", ["good", "empty", "absent"]
    )

    assert result.complete == ("good",)
    assert result.empty == ("empty",)
    assert result.missing == ("absent",)
    assert result.unexpected == ("extra.root",)
    assert discover_eras(tmp_path) == ["Run3_2024"]


def test_suffix_is_part_of_expected_filename(tmp_path: Path):
    era_dir = tmp_path / "Run3_2025"
    era_dir.mkdir()
    (era_dir / "sample_shifted.root").write_bytes(b"root")

    result = check_histograms(
        era_dir, "Run3_2025", ["sample"], suffix="_shifted"
    )

    assert result.complete == ("sample",)


def test_data_process_expands_to_era_specific_datasets():
    repository = Path(__file__).resolve().parents[2]
    datasets = datasets_for_processes(
        repository, "Run3_2024", ["Data_Muon"]
    )

    assert "Muon0_Run2024C" in datasets
    assert "Muon1_Run2024I_v2" in datasets
    assert "Data_Muon" not in datasets


def test_histogram_mc_macrogroups_match_production_groups():
    repository = Path(__file__).resolve().parents[2]

    triboson = datasets_for_histogram_groups(
        repository, "Run3_2024", ["DiTriBoson"]
    )
    single_top = datasets_for_histogram_groups(
        repository, "Run3_2024", ["SingleTop"]
    )

    assert {"WWW_4F", "WWto2L2Nu_powheg", "WZZ", "ZZZ"} <= set(triboson)
    assert "TbarWplusto2L2Nu" in single_top
    assert "TbarBtoLminusNuB_s_channel_4FS" in single_top


def test_histogram_groups_are_era_dependent():
    repository = Path(__file__).resolve().parents[2]

    old = datasets_for_histogram_groups(
        repository, "Run3_2023", ["DY_amcatnlo", "W"]
    )
    modern = datasets_for_histogram_groups(
        repository, "Run3_2024", ["DY_amcatnlo", "W"]
    )

    assert "DYto2L_M_50_amcatnloFXFX" in old
    assert "WtoLNu_amcatnloFXFX" in old
    assert "DYto2Mu_M_50_amcatnloFXFX" in modern
    assert "WtoMuNu_amcatnloFXFX" in modern


def test_dataset_option_also_expands_a_configured_process():
    repository = Path(__file__).resolve().parents[2]

    expanded = expected_datasets(
        repository, "Run3_2024", ["Data_Muon"]
    )
    literal = expected_datasets(
        repository, "Run3_2024", ["Data_Muon"], exact=True
    )

    assert "Muon0_Run2024C" in expanded
    assert "Muon1_Run2024I_v2" in expanded
    assert "Data_Muon" not in expanded
    assert literal == ["Data_Muon"]


def test_processes_for_selected_datasets():
    repository = Path(__file__).resolve().parents[2]
    processes = processes_for_datasets(
        repository, "Run3_2024", ["TTto2L2Nu"]
    )

    assert "TT" in processes


def test_tmp_and_failed_chunks_are_reported(tmp_path: Path):
    era_dir = tmp_path / "Run3_2024"
    tmp_dir = era_dir / "sample_tmp"
    tmp_dir.mkdir(parents=True)
    (tmp_dir / "chunk_1.root").write_bytes(b"root")
    report = era_dir / "sample.root.failed_chunks.txt"
    report.write_text("Chunk 3 failed\nchunk_index=7\n")

    temporary, failures = inspect_dataset_work(era_dir, ["sample"])

    assert temporary[0].chunks == ("chunk_1.root",)
    assert not temporary[0].final_present
    assert failures[0].chunk_numbers == (3, 7)


def test_campaign_checks_all_three_pipeline_levels(tmp_path: Path):
    repository = Path(__file__).resolve().parents[2]
    era = "Run3_2024"
    dataset = "TTto2L2Nu"
    for directory in (
        tmp_path / "Hists_Central" / era,
        tmp_path / "Hists_Central_hadded" / era,
        tmp_path / "Hists_systMerged" / era,
    ):
        directory.mkdir(parents=True)
    (tmp_path / "Hists_Central" / era / f"{dataset}.root").write_bytes(b"root")
    (tmp_path / "Hists_Central_hadded" / era / "TT.root").write_bytes(b"root")
    (tmp_path / "Hists_systMerged" / era / "TT.root").write_bytes(b"root")

    result = check_campaign(
        repository, tmp_path, era, ["Central"], [dataset]
    )

    assert not result.systematics[0].datasets.missing
    assert "TT" in result.expected_processes
    assert "TT" not in result.systematics[0].processes.missing
    assert "TT" not in result.merged.missing
    assert not result.unmapped_datasets
