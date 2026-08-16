from __future__ import annotations

from pathlib import Path

from tools.loader import load_dataset

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_the_good_fixture_without_issues() -> None:
    dataset, issues = load_dataset(FIXTURES / "good")
    assert issues == []
    assert set(dataset.machines) == {"amiga-500"}
    assert set(dataset.boards) == {"amiga-500-mainboard-rev6a"}
    assert set(dataset.parts) == {"eeufr1e332", "eeufr1e470"}
    assert set(dataset.series) == {"panasonic-fr"}
    assert set(dataset.suppliers) == {"mouser", "digikey"}
    assert dataset.offers == {"mouser": {"eeufr1e332": "667-EEU-FR1E332"}}


def test_board_keeps_its_path_and_parses_capacitors() -> None:
    dataset, _ = load_dataset(FIXTURES / "good")
    board = dataset.boards["amiga-500-mainboard-rev6a"]
    assert board.total_capacitors == 3
    assert board.capacitors[0].designators == ("C401", "C402")
    assert board.path is not None
    assert board.path.name == "mainboard-rev6a.yaml"


def test_malformed_yaml_becomes_an_issue(tmp_path: Path) -> None:
    (tmp_path / "data" / "amiga-500").mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (tmp_path / "data" / "amiga-500" / "machine.yaml").write_text(
        "id: [unclosed\n", encoding="utf-8"
    )
    dataset, issues = load_dataset(tmp_path)
    assert dataset.machines == {}
    assert [issue.code for issue in issues] == ["yaml"]
    assert issues[0].location == "data/amiga-500/machine.yaml"


def test_schema_violation_becomes_an_issue_and_skips_the_document(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "amiga-500").mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (tmp_path / "data" / "amiga-500" / "machine.yaml").write_text(
        "id: amiga-500\nname: A500\n", encoding="utf-8"
    )
    dataset, issues = load_dataset(tmp_path)
    assert dataset.machines == {}
    assert issues
    assert all(issue.code == "schema" for issue in issues)


def test_duplicate_board_id_is_an_issue(tmp_path: Path) -> None:
    machine_dir = tmp_path / "data" / "amiga-500"
    machine_dir.mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (machine_dir / "machine.yaml").write_text(
        "id: amiga-500\nname: A500\nfamily: amiga\nboard_order: [mainboard]\n",
        encoding="utf-8",
    )
    body = (
        "id: amiga-500-mainboard-rev6a\n"
        "machine: amiga-500\n"
        "board: mainboard\n"
        "revisions: ['6A']\n"
        "verification: unverified\n"
        "capacitors:\n"
        "  - type: electrolytic-radial\n"
        "    capacitance_uf: 10\n"
        "    voltage_v: 25\n"
        "    quantity: 1\n"
    )
    (machine_dir / "mainboard-rev6a.yaml").write_text(body, encoding="utf-8")
    (machine_dir / "mainboard-rev6a-copy.yaml").write_text(body, encoding="utf-8")
    _, issues = load_dataset(tmp_path)
    assert any(issue.code == "duplicate-id" for issue in issues)


def test_non_utf8_file_becomes_an_issue(tmp_path: Path) -> None:
    (tmp_path / "data" / "amiga-500").mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (tmp_path / "data" / "amiga-500" / "machine.yaml").write_bytes(b"id: \xff\xfe\n")
    dataset, issues = load_dataset(tmp_path)
    assert dataset.machines == {}
    assert issues
    assert any(
        issue.location == "data/amiga-500/machine.yaml" for issue in issues
    )


def test_missing_directories_are_tolerated(tmp_path: Path) -> None:
    dataset, issues = load_dataset(tmp_path)
    assert dataset.machines == {}
    assert issues == []
