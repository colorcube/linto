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


def test_simplify_douglas_peucker_collinear_folded():
    """Verify that collinear paths with sharp reversals/folds are preserved."""
    # Path goes 100mm out along X and returns nearly to origin (0.1, 0)
    line = np.array([
        [0.0, 0.0],
        [100.0, 0.0],
        [0.1, 0.0],
    ])
    simplified = ramer_douglas_peucker(line, epsilon=0.5)
    # The peak at (100, 0) must be preserved because it is 99.9mm away from segment [(0,0), (0.1,0)]
    assert len(simplified) == 3
    assert np.allclose(simplified[1], [100.0, 0.0])


def test_merge_polylines():
    l1 = np.array([[0.0, 0.0], [10.0, 0.0]])
    l2 = np.array([[10.05, 0.0], [20.0, 0.0]])  # 0.05mm gap
    merged = merge_polylines([l1, l2], tolerance_mm=0.1)
    assert len(merged) == 1
    assert len(merged[0]) == 3
    assert np.allclose(merged[0][0], [0.0, 0.0])
    assert np.allclose(merged[0][-1], [20.0, 0.0])


def test_merge_polylines_all_four_orientations():
    """Verify append, append_rev, prepend, and prepend_rev modes in vectorized merge_polylines."""
    # Seed: (10, 0) -> (20, 0)
    seed = np.array([[10.0, 0.0], [20.0, 0.0]])
    # 1. append_rev: (30, 0) -> (20.02, 0) (cand_end near cur_end)
    c_append_rev = np.array([[30.0, 0.0], [20.02, 0.0]])
    # 2. prepend: (0, 0) -> (9.98, 0) (cand_end near cur_start)
    c_prepend = np.array([[0.0, 0.0], [9.98, 0.0]])
    # 3. prepend_rev: (0.02, 0) -> (-10, 0) (cand_start near new cur_start (0,0))
    c_prepend_rev = np.array([[0.02, 0.0], [-10.0, 0.0]])
    # 4. append: (30.03, 0) -> (40, 0) (cand_start near new cur_end (30,0))
    c_append = np.array([[30.03, 0.0], [40.0, 0.0]])
    # 5. Unrelated distant segment
    distant = np.array([[100.0, 100.0], [110.0, 100.0]])

    merged = merge_polylines(
        [seed, c_append_rev, c_prepend, c_prepend_rev, c_append, distant],
        tolerance_mm=0.1,
    )
    assert len(merged) == 2
    main_chain = merged[0]
    assert np.allclose(main_chain[0], [-10.0, 0.0])
    assert np.allclose(main_chain[-1], [40.0, 0.0])
    assert np.allclose(merged[1], distant)

