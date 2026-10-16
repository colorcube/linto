import math
from plotter_studio.core.svg_import import load_svg
from plotter_studio.core.color_cluster import cluster_colors_to_pens, hex_to_rgb, rgb_to_lab, delta_e


def test_color_cluster():
    palette = [(1, "#000000"), (2, "#ff0000"), (3, "#0000ff")]
    # Test matching similar red
    colors = ["#ff0000", "#fe0505", "#0000ff", "#111111"]
    mapping = cluster_colors_to_pens(colors, palette, max_pens=3)
    # The two reds should map to pen 2
    assert mapping["#ff0000"] == 2
    assert mapping["#fe0505"] == 2
    # Blue to pen 3
    assert mapping["#0000ff"] == 3
    # Dark gray to pen 1
    assert mapping["#111111"] == 1


def test_svg_load_shapes():
    svg_sample = """<svg width="200mm" height="150mm" viewBox="0 0 200 150" xmlns="http://www.w3.org/2000/svg">
      <rect x="20" y="30" width="100" height="50" stroke="#000000" fill="none"/>
      <line x1="0" y1="0" x2="200" y2="150" stroke="#ff0000"/>
    </svg>"""
    item = load_svg(svg_sample, name="TestShapes")
    assert len(item.paths) >= 2
    b = item.original_bounds
    assert b is not None
    assert math.isclose(b.min_x, 0.0, abs_tol=0.1)
    assert math.isclose(b.min_y, 0.0, abs_tol=0.1)
    assert math.isclose(b.max_x, 200.0, abs_tol=0.1)
    assert math.isclose(b.max_y, 150.0, abs_tol=0.1)


def test_svg_load_quadratic_bezier():
    from plotter_studio.core.geometry import QuadraticBezierSegment, CubicBezierSegment, ArcSegment

    svg_sample = """<svg width="100mm" height="100mm" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path d="M 10 10 Q 50 90 90 10" stroke="#000000" fill="none"/>
    </svg>"""
    item = load_svg(svg_sample, name="TestQuadratic")
    assert len(item.paths) == 1
    path = item.paths[0]
    # Geometry is stored unflattened as a single QuadraticBezierSegment
    assert path._points is None
    assert path.has_curves is True
    assert len(path.segments) == 1
    assert isinstance(path.segments[0], QuadraticBezierSegment)
    b = item.original_bounds
    assert b is not None
    assert math.isclose(b.min_x, 10.0, abs_tol=0.5)
    assert math.isclose(b.max_x, 90.0, abs_tol=0.5)
    # Exact analytical peak of Q(10,10 -> 50,90 -> 90,10) at t=0.5 is y = 50.0
    assert math.isclose(b.min_y, 10.0, abs_tol=0.1)
    assert math.isclose(b.max_y, 50.0, abs_tol=0.1)
    # Lazy polyline conversion still works on demand
    assert len(path.points) > 2


def test_svg_preserves_cubic_and_arc_segments():
    from plotter_studio.core.geometry import CubicBezierSegment, ArcSegment

    svg_sample = """<svg width="100mm" height="100mm" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path d="M 10 50 C 20 10, 80 10, 90 50" stroke="#000000" fill="none"/>
      <circle cx="50" cy="50" r="30" stroke="#ff0000" fill="none"/>
    </svg>"""
    item = load_svg(svg_sample, name="TestCurves")
    assert len(item.paths) == 2
    assert isinstance(item.paths[0].segments[0], CubicBezierSegment)
    assert any(isinstance(s, ArcSegment) for s in item.paths[1].segments)

