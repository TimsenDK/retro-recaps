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


def test_an_empty_board_file_is_an_issue(tmp_path: Path) -> None:
    machine_dir = tmp_path / "data" / "amiga-2000"
    machine_dir.mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (machine_dir / "machine.yaml").write_text(
        "id: amiga-2000\nname: A2000\nfamily: amiga\nboard_order: [mainboard]\n",
        encoding="utf-8",
    )
    (machine_dir / "mainboard-rev6x.yaml").write_text(
        "# nothing here yet\n", encoding="utf-8"
    )
    dataset, issues = load_dataset(tmp_path)
    assert dataset.boards == {}
    assert [issue.code for issue in issues] == ["empty-document"]
    assert issues[0].location == "data/amiga-2000/mainboard-rev6x.yaml"
    assert issues[0].level == "error"


def test_a_yml_board_file_is_reported_rather_than_ignored(tmp_path: Path) -> None:
    machine_dir = tmp_path / "data" / "amiga-500"
    machine_dir.mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (machine_dir / "mainboard-rev6a.yml").write_text(
        "id: amiga-500-mainboard-rev6a\n", encoding="utf-8"
    )
    dataset, issues = load_dataset(tmp_path)
    assert dataset.boards == {}
    assert [issue.code for issue in issues] == ["unexpected-extension"]
    assert issues[0].location == "data/amiga-500/mainboard-rev6a.yml"
    assert "mainboard-rev6a.yaml" in issues[0].message


def test_an_uppercase_yml_board_file_is_reported_rather_than_loaded(
    tmp_path: Path,
) -> None:
    machine_dir = tmp_path / "data" / "amiga-500"
    machine_dir.mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (machine_dir / "mainboard-rev6a.YML").write_text(
        "id: amiga-500-mainboard-rev6a\n", encoding="utf-8"
    )
    dataset, issues = load_dataset(tmp_path)
    assert dataset.boards == {}
    assert [issue.code for issue in issues] == ["unexpected-extension"]
    assert issues[0].location == "data/amiga-500/mainboard-rev6a.YML"


def test_a_stray_non_yaml_file_is_reported_rather_than_ignored(
    tmp_path: Path,
) -> None:
    machine_dir = tmp_path / "data" / "amiga-500"
    machine_dir.mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (machine_dir / "notes.txt").write_text("todo\n", encoding="utf-8")
    dataset, issues = load_dataset(tmp_path)
    assert dataset.boards == {}
    assert [issue.code for issue in issues] == ["unexpected-extension"]
    assert issues[0].location == "data/amiga-500/notes.txt"


def test_a_machine_keeps_its_path() -> None:
    dataset, _ = load_dataset(FIXTURES / "good")
    machine = dataset.machines["amiga-500"]
    assert machine.path is not None
    assert machine.path.name == "machine.yaml"


def test_missing_directories_are_tolerated(tmp_path: Path) -> None:
    dataset, issues = load_dataset(tmp_path)
    assert dataset.machines == {}
    assert issues == []


def test_a_layout_file_is_loaded_as_a_layout_not_a_board(tmp_path: Path) -> None:
    machine_dir = tmp_path / "data" / "demo"
    machine_dir.mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (machine_dir / "machine.yaml").write_text(
        "id: demo\nname: Demo\nfamily: amiga\nboard_order:\n  - mainboard\n",
        encoding="utf-8",
    )
    (machine_dir / "mainboard.yaml").write_text(
        "id: demo-mainboard\nmachine: demo\nboard: mainboard\n"
        "revisions:\n  - '1'\nverification: derived\n"
        "capacitors:\n"
        "  - designators: [C1]\n    type: electrolytic-radial\n"
        "    capacitance_uf: 10\n    voltage_v: 25\n    quantity: 1\n",
        encoding="utf-8",
    )
    (machine_dir / "layout-mainboard.yaml").write_text(
        "id: demo-layout-mainboard\nboard: demo-mainboard\n"
        "precision: measured\nverification: derived\n"
        "orientation: Component side up.\n"
        "outline:\n  width: 1000\n  height: 620\n"
        "features:\n"
        "  - kind: capacitor\n    designator: C1\n    x: 0.5\n    y: 0.5\n",
        encoding="utf-8",
    )

    dataset, issues = load_dataset(tmp_path)

    assert [issue.code for issue in issues] == []
    assert set(dataset.boards) == {"demo-mainboard"}
    assert set(dataset.layouts) == {"demo-layout-mainboard"}
    assert dataset.layouts["demo-layout-mainboard"].board == "demo-mainboard"


def test_a_layout_coordinate_outside_the_board_is_a_schema_error(
    tmp_path: Path,
) -> None:
    # Coordinates are normalised fractions of the outline, 0 to 1; a feature
    # placed at x: 1.5 would draw off the edge of the board entirely, which
    # spec section 8 requires the schema itself to catch.
    machine_dir = tmp_path / "data" / "demo"
    machine_dir.mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    (machine_dir / "machine.yaml").write_text(
        "id: demo\nname: Demo\nfamily: amiga\nboard_order:\n  - mainboard\n",
        encoding="utf-8",
    )
    (machine_dir / "mainboard.yaml").write_text(
        "id: demo-mainboard\nmachine: demo\nboard: mainboard\n"
        "revisions:\n  - '1'\nverification: derived\n"
        "capacitors:\n"
        "  - designators: [C1]\n    type: electrolytic-radial\n"
        "    capacitance_uf: 10\n    voltage_v: 25\n    quantity: 1\n",
        encoding="utf-8",
    )
    (machine_dir / "layout-mainboard.yaml").write_text(
        "id: demo-layout-mainboard\nboard: demo-mainboard\n"
        "precision: measured\nverification: derived\n"
        "orientation: Component side up.\n"
        "outline:\n  width: 1000\n  height: 620\n"
        "features:\n"
        "  - kind: capacitor\n    designator: C1\n    x: 1.5\n    y: 0.5\n",
        encoding="utf-8",
    )

    dataset, issues = load_dataset(tmp_path)

    assert set(dataset.layouts) == set()
    assert [issue.code for issue in issues] == ["schema"]
    assert issues[0].location.startswith("data/demo/layout-mainboard.yaml")
