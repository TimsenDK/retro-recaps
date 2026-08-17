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


# --------------------------------------------------------------------------
# What the PCB carries
# --------------------------------------------------------------------------


def declared(board_kind: str, **overrides) -> Board:
    document = {
        "id": "b",
        "machine": "commodore-1541",
        "board": board_kind,
        "revisions": ["1"],
        "verification": "unverified",
        "capacitors": [],
    }
    return Board.from_dict({**document, **overrides})


def test_an_explicit_mains_true_wins() -> None:
    """The 1541 longboard mainboard carries the machine's linear supply."""
    assert declared("mainboard", mains=True).carries_mains is True


def test_an_explicit_mains_false_wins() -> None:
    """The 1541-II analog board is low-voltage motor control."""
    assert declared("analog", mains=False).carries_mains is False


def test_an_explicit_mains_false_wins_even_on_a_psu() -> None:
    assert declared("psu", mains=False).carries_mains is False


def test_an_undeclared_psu_falls_back_to_mains() -> None:
    """The fallback keeps an undeclared supply warning rather than silent."""
    assert declared("psu").carries_mains is True


def test_an_undeclared_mainboard_is_not_mains() -> None:
    assert declared("mainboard").carries_mains is False


def test_an_undeclared_analog_board_is_not_mains() -> None:
    """The kind alone never promotes a board to mains; only 'psu' does."""
    assert declared("analog").carries_mains is False


def test_an_undeclared_logic_or_daughterboard_is_not_mains() -> None:
    assert declared("logic").carries_mains is False
    assert declared("daughterboard").carries_mains is False
