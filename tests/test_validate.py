from __future__ import annotations

from pathlib import Path

import pytest

from tools import cli
from tools.validate import run_validate

FIXTURES = Path(__file__).parent / "fixtures"


def test_good_fixture_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_validate(root=FIXTURES / "good") == 0
    assert "0 errors" in capsys.readouterr().out


def test_strict_turns_the_fixture_warning_into_a_failure() -> None:
    assert run_validate(root=FIXTURES / "good", strict=True) == 1


def test_errors_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine_dir = tmp_path / "data" / "amiga-500"
    machine_dir.mkdir(parents=True)
    (machine_dir / "machine.yaml").write_text(
        "id: amiga-500\nname: A500\nfamily: amiga\nboard_order: [mainboard]\n",
        encoding="utf-8",
    )
    (machine_dir / "mainboard-rev6a.yaml").write_text(
        "id: amiga-500-mainboard-rev6a\n"
        "machine: amiga-500\n"
        "board: mainboard\n"
        "revisions: ['6A']\n"
        "verification: verified\n"
        "capacitors:\n"
        "  - designators: [C1]\n"
        "    type: electrolytic-radial\n"
        "    capacitance_uf: 10\n"
        "    voltage_v: 16\n"
        "    original_voltage_v: 25\n"
        "    quantity: 1\n",
        encoding="utf-8",
    )
    assert run_validate(root=tmp_path) == 1
    output = capsys.readouterr().out
    assert "voltage-downgrade" in output
    assert "verified-without-source" in output


def test_loader_issues_reach_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A loader-level problem must fail the run, not just the domain rules."""
    machine_dir = tmp_path / "data" / "amiga-500"
    machine_dir.mkdir(parents=True)
    (machine_dir / "machine.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    assert run_validate(root=tmp_path) == 1
    assert "[yaml]" in capsys.readouterr().out


def test_cli_wires_the_command_through(tmp_path: Path) -> None:
    assert cli.main(["validate", "--root", str(FIXTURES / "good")]) == 0
