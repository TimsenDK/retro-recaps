from __future__ import annotations

from tools.model import Board, Capacitor, Dataset, Machine


def capacitor(**overrides) -> Capacitor:
    base = {
        "designators": ["C1"],
        "type": "electrolytic-radial",
        "capacitance_uf": 10,
        "voltage_v": 25,
        "quantity": 1,
    }
    return Capacitor.from_dict({**base, **overrides})


def board(board_kind: str, board_id: str) -> Board:
    return Board.from_dict(
        {
            "id": board_id,
            "machine": "mac-se30",
            "board": board_kind,
            "revisions": ["1"],
            "verification": "verified",
            "capacitors": [
                {
                    "designators": ["C1"],
                    "type": "electrolytic-radial",
                    "capacitance_uf": 10,
                    "voltage_v": 25,
                    "quantity": 1,
                }
            ],
        }
    )


def test_capacitor_inherits_board_verification() -> None:
    assert capacitor().effective_verification("derived") == "derived"


def test_capacitor_verification_overrides_the_board() -> None:
    cap = capacitor(verification="unverified")
    assert cap.effective_verification("verified") == "unverified"


def test_capacitor_label_uses_designators_when_present() -> None:
    assert capacitor(designators=["C1", "C2"]).label == "C1, C2"


def test_capacitor_label_falls_back_to_quantity() -> None:
    assert capacitor(designators=[], quantity=3).label == "3 positions"


def test_collections_are_tuples() -> None:
    cap = capacitor(designators=["C1", "C2"])
    assert isinstance(cap.designators, tuple)


def test_boards_are_returned_in_recap_order() -> None:
    machine = Machine.from_dict(
        {
            "id": "mac-se30",
            "name": "Macintosh SE/30",
            "family": "macintosh",
            "board_order": ["logic", "analog", "psu"],
        }
    )
    boards = {
        "b-psu": board("psu", "b-psu"),
        "b-logic": board("logic", "b-logic"),
        "b-analog": board("analog", "b-analog"),
    }
    dataset = Dataset(
        machines={"mac-se30": machine},
        boards=boards,
        parts={},
        series={},
        suppliers={},
        offers={},
    )
    assert [b.board for b in dataset.boards_for("mac-se30")] == [
        "logic",
        "analog",
        "psu",
    ]
