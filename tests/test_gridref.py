from pathlib import Path

from PIL import Image

from tools.gridref import crop, grid_overlay


def make_source(path: Path, size: tuple[int, int] = (400, 200)) -> Path:
    Image.new("RGB", size, (255, 255, 255)).save(path, "PNG")
    return path


def test_the_overlay_keeps_the_picture_the_same_size(tmp_path: Path) -> None:
    source = make_source(tmp_path / "board.png")
    out = grid_overlay(source, tmp_path / "grid.png", columns=10, rows=5)
    assert Image.open(out).size == (400, 200)


def test_a_crop_is_one_cell_plus_its_margin(tmp_path: Path) -> None:
    make_source(tmp_path / "board.png")
    out = crop(tmp_path / "board.png", tmp_path / "cell.png", column=0, row=0,
               columns=10, rows=5, margin=0.0)
    assert Image.open(out).size == (40, 40)
