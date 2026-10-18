import math
import numpy as np
from plotter_studio.core.geometry import Point, BoundingBox, AffineTransform


def test_point_operations():
    p1 = Point(10.0, 20.0)
    p2 = Point(5.0, 10.0)
    assert p1 + p2 == Point(15.0, 30.0)
    assert p1 - p2 == Point(5.0, 10.0)
    assert p1 * 2.0 == Point(20.0, 40.0)
    assert math.isclose(p1.distance_to(p2), math.hypot(5.0, 10.0))


def test_bounding_box():
    pts = [Point(0, 5), Point(10, 2), Point(4, 20)]
    b = BoundingBox.from_points(pts)
    assert b is not None
    assert b.min_x == 0
    assert b.max_x == 10
    assert b.min_y == 2
    assert b.max_y == 20
    assert b.width == 10
    assert b.height == 18
    assert b.center == Point(5, 11)


def test_affine_transform():
    t = AffineTransform.translation(10, 20)
    s = AffineTransform.scale(2, 3)
    combined = t.multiply(s)  # Scale first, then translate

    pt = Point(5, 5)
    res = combined.transform_point(pt)
    assert res.x == 5 * 2 + 10  # 20
    assert res.y == 5 * 3 + 20  # 35

    coords = np.array([[0.0, 0.0], [5.0, 5.0]])
    t_coords = combined.transform_coords(coords)
    assert np.allclose(t_coords[0], [10.0, 20.0])
    assert np.allclose(t_coords[1], [20.0, 35.0])


def test_rotation_affine_transform():
    # Rotate around origin
    r90 = AffineTransform.rotation(90.0, 0.0, 0.0)
    assert r90.a == 0.0
    assert r90.b == 1.0
    assert r90.c == -1.0
    assert r90.d == 0.0

    p = Point(10.0, 0.0)
    p_rot = r90.transform_point(p)
    assert math.isclose(p_rot.x, 0.0, abs_tol=1e-9)
    assert math.isclose(p_rot.y, 10.0, abs_tol=1e-9)

    r_ccw = AffineTransform.rotation(-90.0, 0.0, 0.0)
    p_ccw = r_ccw.transform_point(p)
    assert math.isclose(p_ccw.x, 0.0, abs_tol=1e-9)
    assert math.isclose(p_ccw.y, -10.0, abs_tol=1e-9)

    # Rotate around custom center: center must remain fixed
    cx, cy = 50.0, 75.0
    r_center = AffineTransform.rotation(90.0, cx, cy)
    p_center = r_center.transform_point(Point(cx, cy))
    assert math.isclose(p_center.x, cx, abs_tol=1e-9)
    assert math.isclose(p_center.y, cy, abs_tol=1e-9)

    # 4 consecutive 90 degree rotations must return exactly to identity
    t = AffineTransform.identity()
    for _ in range(4):
        rot = AffineTransform.rotation(90.0, cx, cy)
        t = rot.multiply(t)

    assert math.isclose(t.a, 1.0, abs_tol=1e-9)
    assert math.isclose(t.b, 0.0, abs_tol=1e-9)
    assert math.isclose(t.c, 0.0, abs_tol=1e-9)
    assert math.isclose(t.d, 1.0, abs_tol=1e-9)
    assert math.isclose(t.tx, 0.0, abs_tol=1e-9)
    assert math.isclose(t.ty, 0.0, abs_tol=1e-9)


def test_analytical_curve_bounds():
    """Verify compute_segments_bounds matches dense numerical evaluation for S-curves."""
    from plotter_studio.core.geometry import (
        CubicBezierSegment,
        QuadraticBezierSegment,
        compute_segments_bounds,
    )
    from plotter_studio.pipeline.flatten import flatten_segment

    cubic = CubicBezierSegment(
        start=(10.0, 50.0),
        control1=( -30.0, 120.0),
        control2=(130.0, -40.0),
        end=(90.0, 50.0),
    )
    quad = QuadraticBezierSegment(
        start=(10.0, 10.0),
        control=(50.0, 90.0),
        end=(90.0, 10.0),
    )

    for seg in (cubic, quad):
        b = compute_segments_bounds([seg])
        assert b is not None
        dense_pts = np.array(flatten_segment(seg, tolerance=0.001))
        assert math.isclose(b.min_x, float(np.min(dense_pts[:, 0])), abs_tol=0.02)
        assert math.isclose(b.max_x, float(np.max(dense_pts[:, 0])), abs_tol=0.02)
        assert math.isclose(b.min_y, float(np.min(dense_pts[:, 1])), abs_tol=0.02)
        assert math.isclose(b.max_y, float(np.max(dense_pts[:, 1])), abs_tol=0.02)


def test_segment_transformations_including_non_uniform_arc():
    """Verify PathSegment.transformed under rotation, reflection, and non-uniform scaling."""
    from plotter_studio.core.svg_import import load_svg
    from plotter_studio.pipeline.flatten import flatten_path_segments

    svg_circle = """<svg width="100mm" height="100mm" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <circle cx="50" cy="50" r="30" stroke="#000000" fill="none"/>
    </svg>"""
    item = load_svg(svg_circle)
    segs = item.paths[0].segments

    # 1. Similarity transform (rotation + uniform scale + translation)
    t_sim = AffineTransform.translation(15.0, -25.0).multiply(
        AffineTransform.rotation(35.0, 50.0, 50.0)
    ).multiply(AffineTransform.scale(2.0))
    pts_sim = flatten_path_segments(segs, tolerance=0.01, transform=t_sim)
    pts_raw_transformed = t_sim.transform_coords(flatten_path_segments(segs, tolerance=0.01))
    assert math.isclose(float(np.min(pts_sim[:, 0])), float(np.min(pts_raw_transformed[:, 0])), abs_tol=0.1)
    assert math.isclose(float(np.max(pts_sim[:, 0])), float(np.max(pts_raw_transformed[:, 0])), abs_tol=0.1)
    assert math.isclose(float(np.min(pts_sim[:, 1])), float(np.min(pts_raw_transformed[:, 1])), abs_tol=0.1)
    assert math.isclose(float(np.max(pts_sim[:, 1])), float(np.max(pts_raw_transformed[:, 1])), abs_tol=0.1)

    # 2. Non-uniform scale + reflection (ellipse with flipped X)
    t_non_uni = AffineTransform.scale(-2.0, 0.5)
    pts_non_uni = flatten_path_segments(segs, tolerance=0.01, transform=t_non_uni)
    pts_expected = t_non_uni.transform_coords(flatten_path_segments(segs, tolerance=0.01))
    assert math.isclose(float(np.min(pts_non_uni[:, 0])), float(np.min(pts_expected[:, 0])), abs_tol=0.1)
    assert math.isclose(float(np.max(pts_non_uni[:, 0])), float(np.max(pts_expected[:, 0])), abs_tol=0.1)
    assert math.isclose(float(np.min(pts_non_uni[:, 1])), float(np.min(pts_expected[:, 1])), abs_tol=0.1)
    assert math.isclose(float(np.max(pts_non_uni[:, 1])), float(np.max(pts_expected[:, 1])), abs_tol=0.1)


def test_tight_rotated_current_bounds_and_margin_profile_preservation():
    """Verify tight current_bounds on rotated diamond and margin_profile preservation on Page.apply_preset."""
    from plotter_studio.core.document import ImportItem, VectorPath, Page

    # Diamond with vertices at (10,0), (20,10), (10,20), (0,10) -> original_bounds is 20x20
    # When rotated by 45 degrees around center (10,10), it becomes an axis-aligned square of side 10*sqrt(2) (~14.142)
    # Transforming the 4 corners of original_bounds would falsely give 20*sqrt(2) (~28.284)!
    diamond_pts = np.array([[10.0, 0.0], [20.0, 10.0], [10.0, 20.0], [0.0, 10.0], [10.0, 0.0]])
    item = ImportItem(name="Diamond", paths=[VectorPath(points=diamond_pts, pen_id=1, closed=True)])
    assert item.original_bounds is not None
    assert math.isclose(item.original_bounds.width, 20.0, abs_tol=1e-6)

    item.transform = AffineTransform.rotation(45.0, 10.0, 10.0)
    cb = item.current_bounds
    assert cb is not None
    expected_side = 10.0 * math.sqrt(2.0)
    assert math.isclose(cb.width, expected_side, abs_tol=1e-4)
    assert math.isclose(cb.height, expected_side, abs_tol=1e-4)

    # Verify Page.apply_preset preserves margin_profile ("norm" vs "exp")
    page = Page()
    page.apply_device_profile("mutoh_xp500", "top", "norm")
    assert page.margin_profile == "norm"
    norm_left = page.margin_left_mm
    page.apply_preset("A4", "portrait")
    assert page.margin_profile == "norm"
    assert math.isclose(page.margin_left_mm, norm_left, abs_tol=1e-6)


