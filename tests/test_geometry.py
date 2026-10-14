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
