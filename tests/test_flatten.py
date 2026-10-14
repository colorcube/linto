import math
from plotter_studio.pipeline.flatten import (
    flatten_cubic_bezier, flatten_quadratic_bezier, flatten_arc, point_line_distance
)
from plotter_studio.pipeline.simplify import ramer_douglas_peucker
from plotter_studio.pipeline.merge import merge_polylines
import numpy as np


def test_point_line_distance():
    d = point_line_distance(0, 5, 0, 0, 10, 0)
    assert math.isclose(d, 5.0)

    # Beyond segment endpoint
    d2 = point_line_distance(15, 0, 0, 0, 10, 0)
    assert math.isclose(d2, 5.0)


def test_flatten_cubic_bezier():
    p0 = (0.0, 0.0)
    p1 = (10.0, 20.0)
    p2 = (30.0, 20.0)
    p3 = (40.0, 0.0)
    pts = flatten_cubic_bezier(p0, p1, p2, p3, tolerance=0.05)
    assert len(pts) > 5
    assert pts[0] == p0
    assert pts[-1] == p3


def test_simplify_douglas_peucker():
    line = np.array([
        [0.0, 0.0],
        [1.0, 0.01],
        [2.0, -0.01],
        [3.0, 0.0],
        [4.0, 5.0],
        [5.0, 10.0],
    ])
    simplified = ramer_douglas_peucker(line, epsilon=0.05)
    # The slight wobble between 0 and 3 should be eliminated
    assert len(simplified) < len(line)
    assert np.allclose(simplified[0], [0.0, 0.0])
    assert np.allclose(simplified[-1], [5.0, 10.0])


def test_merge_polylines():
    l1 = np.array([[0.0, 0.0], [10.0, 0.0]])
    l2 = np.array([[10.05, 0.0], [20.0, 0.0]])  # 0.05mm gap
    merged = merge_polylines([l1, l2], tolerance_mm=0.1)
    assert len(merged) == 1
    assert len(merged[0]) == 3
    assert np.allclose(merged[0][0], [0.0, 0.0])
    assert np.allclose(merged[0][-1], [20.0, 0.0])
