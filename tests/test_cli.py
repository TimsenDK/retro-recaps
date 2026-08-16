from __future__ import annotations

import pytest

from tools import cli


def test_unknown_command_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["nonsense"])
    assert exc.value.code == 2


def test_no_command_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2


def test_validate_command_is_registered() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["validate", "--help"])
    assert exc.value.code == 0
