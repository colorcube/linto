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
