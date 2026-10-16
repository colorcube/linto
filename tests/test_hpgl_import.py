"""Tests for HP-GL / PLT import (adapted from MutohPlot) and GUI integration."""

import math
from pathlib import Path
import pytest

from plotter_studio.core.hpgl_import import (
    HPGLTokenizer,
    HPGLParser,
    load_hpgl,
    is_hpgl_file,
    glyph_rows,
)
from plotter_studio.core.svg_export import load_document_from_svg


def test_is_hpgl_file():
    assert is_hpgl_file("drawing.hpgl") is True
    assert is_hpgl_file("drawing.PLT") is True
    assert is_hpgl_file("drawing.svg") is False


def test_tokenizer_handles_semicolons_and_compact_commands():
    tok = HPGLTokenizer()
    cmds = tok.tokenize("\x1b.YIN;SP1PU0,0PD400,0,400,400LBHELLO\x03SP0;")
    names = [c.name for c in cmds]
    assert names == ["IN", "SP", "PU", "PD", "LB", "SP"]
    assert cmds[1].numeric_args() == [1.0]
    assert cmds[3].numeric_args() == [400.0, 0.0, 400.0, 400.0]
    assert cmds[4].payload == "HELLO"


def test_load_hpgl_square_and_pen_assignment():
    # 4000 HP-GL units = 100.0 mm at 0.025 mm/unit
    hpgl = "IN;SP2;PU0,0;PD4000,0,4000,2000,0,2000,0,0;PU;SP0;"
    item = load_hpgl(hpgl, name="SquareTest")

    assert item.name == "SquareTest"
    assert len(item.paths) == 1
    path = item.paths[0]
    assert path.pen_id == 2
    assert path.closed is True
    assert item.original_bounds is not None
    assert math.isclose(item.original_bounds.width, 100.0, abs_tol=1e-4)
    assert math.isclose(item.original_bounds.height, 50.0, abs_tol=1e-4)
    assert math.isclose(item.original_bounds.min_x, 0.0, abs_tol=1e-4)
    assert math.isclose(item.original_bounds.min_y, 0.0, abs_tol=1e-4)


def test_load_hpgl_relative_moves_circles_arcs_and_rects():
    hpgl = (
        "IN;SP1;PA0,0;CI400,10;"
        "SP3;PU0,0;PD;PR400,0,0,400;PU;"
        "SP4;PA0,0;EA800,400;"
        "SP5;PA400,0;PD;AA0,0,90,15;PU;"
    )
    item = load_hpgl(hpgl)
    pens = [p.pen_id for p in item.paths]
    assert 1 in pens  # CI circle
    assert 3 in pens  # PR relative polyline
    assert 4 in pens  # EA rectangle
    assert 5 in pens  # AA arc
    # Circle and EA rectangle should be closed
    circle_path = next(p for p in item.paths if p.pen_id == 1)
    rect_path = next(p for p in item.paths if p.pen_id == 4)
    assert circle_path.closed is True
    assert rect_path.closed is True


def test_load_hpgl_labels_and_text_attributes():
    hpgl = "IN;SP6;PA1000,1000;SI0.3,0.4;DI1,0;SL0.1;CP1,0;LBMUTOH!\x03"
    item = load_hpgl(hpgl)
    assert len(item.paths) > 5
    assert all(p.pen_id == 6 for p in item.paths)
    assert glyph_rows("a") == glyph_rows("A")


def test_load_hpgl_file_and_gui_integration(tmp_path: Path, qapp):
    from plotter_studio.gui.main_window import MainWindow

    hpgl_path = tmp_path / "sample.plt"
    hpgl_path.write_text("IN;SP3;PU0,0;PD2000,0,2000,1000;PU;SP0;", encoding="ascii")

    # 1. Test load_document_from_svg with .plt
    doc = load_document_from_svg(str(hpgl_path))
    assert len(doc.items) == 1
    assert doc.items[0].name == "sample"
    assert doc.items[0].paths[0].pen_id == 3

    # 2. Test MainWindow.import_svg_file with .plt
    win = MainWindow()
    win.import_svg_file(str(hpgl_path))
    assert len(win.doc.items) == 1
    imported = win.doc.items[0]
    assert imported.name == "sample"
    assert imported.paths[0].pen_id == 3
    # Should be centered inside plottable_box
    pb = win.doc.page.plottable_box
    cb = imported.current_bounds
    assert cb is not None
    assert pb.contains_box(cb)
    win.close()


def test_load_classic_examples():
    """Verify that bundled classic HP-GL example files load properly."""
    examples_dir = Path(__file__).parent.parent / "examples"
    shuttle = examples_dir / "space-columbia.hpgl"
    if shuttle.is_file():
        item = load_hpgl(str(shuttle))
        assert len(item.paths) > 500
        pens = {p.pen_id for p in item.paths}
        assert len(pens) >= 5
        assert item.original_bounds is not None
        assert item.original_bounds.width > 20.0

    walker = examples_dir / "imperial-walker.hpgl"
    if walker.is_file():
        item_w = load_hpgl(str(walker))
        assert len(item_w.paths) > 400

