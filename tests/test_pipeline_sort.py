import math
import pytest
import numpy as np
from plotter_studio.pipeline.sort import (
    sort_and_optimize_lines,
    compute_polyline_length,
    compute_unsorted_travel_distance,
)


def test_polyline_length():
    line = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]])
    length = compute_polyline_length(line)
    assert abs(length - 20.0) < 1e-6


def test_sort_zigzag_lines_reversal():
    # 3 horizontal lines stacked vertically:
    # Line 0: (0, 0) -> (100, 0)
    # Line 1: (0, 10) -> (100, 10)  (if drawn 0->100, travel is from (100,0) to (0,10) = ~100)
    #                              (if reversed 100->0, travel is (100,0) to (100,10) = 10!)
    line0 = np.array([[0.0, 0.0], [100.0, 0.0]])
    line1 = np.array([[0.0, 10.0], [100.0, 10.0]])
    lines = [line0, line1]

    # Without reversal / unsorted:
    unsorted = compute_unsorted_travel_distance(lines, start_pos=(0.0, 0.0))
    # line 0 starts at (0,0) -> 0 travel
    # line 0 ends at (100,0), line 1 starts at (0,10) -> travel ~100.5
    assert unsorted > 100.0

    # With optimization:
    opt_lines, travels, travel_mm, _ = sort_and_optimize_lines(
        lines, start_pos=(0.0, 0.0), allow_reverse=True
    )
    # line 1 should have been reversed: (100, 10) -> (0, 10)
    # Travel from (100, 0) to (100, 10) is 10.0 mm
    assert abs(travel_mm - 10.0) < 1e-4
    assert len(opt_lines) == 2
    assert abs(opt_lines[1][0, 0] - 100.0) < 1e-4
    assert abs(opt_lines[1][0, 1] - 10.0) < 1e-4


def test_sort_random_order():
    # 5 vertical segments at x=10, 20, 30, 40, 50
    # Scrambled order
    lines = [
        np.array([[30.0, 0.0], [30.0, 50.0]]),
        np.array([[50.0, 0.0], [50.0, 50.0]]),
        np.array([[10.0, 0.0], [10.0, 50.0]]),
        np.array([[40.0, 0.0], [40.0, 50.0]]),
        np.array([[20.0, 0.0], [20.0, 50.0]]),
    ]
    opt_lines, travels, final_travel, unsorted = sort_and_optimize_lines(
        lines, start_pos=(0.0, 0.0), use_2opt=True
    )
    assert final_travel < unsorted
    assert len(opt_lines) == 5


def test_sort_no_reverse():
    """Verify allow_reverse=False preserves original line directions."""
    l0 = np.array([[0.0, 0.0], [100.0, 0.0]])
    l1 = np.array([[0.0, 10.0], [100.0, 10.0]])
    opt_lines, travels, travel_mm, _ = sort_and_optimize_lines(
        [l0, l1], start_pos=(0.0, 0.0), allow_reverse=False, use_2opt=False
    )
    assert np.allclose(opt_lines[0][0], [0.0, 0.0])
    assert np.allclose(opt_lines[1][0], [0.0, 10.0])
    assert travel_mm > 100.0


def test_2opt_uncrosses_paths_and_maintains_endpoints():
    """Verify optimize_paths_2opt resolves crossed travels and keeps travel list consistent."""
    from plotter_studio.pipeline.sort import optimize_paths_2opt

    # Construct a deliberately sub-optimal order with crossing travel moves:
    # 0: (0,0)->(10,0), 1: (30,0)->(20,0), 2: (20,0)->(10,0), 3: (30,0)->(40,0)
    # Reversing block [1..2] turns it into (10,0)->(20,0) and (20,0)->(30,0) with 0 travel!
    lines = [
        np.array([[0.0, 0.0], [10.0, 0.0]]),
        np.array([[30.0, 0.0], [20.0, 0.0]]),
        np.array([[20.0, 0.0], [10.0, 0.0]]),
        np.array([[30.0, 0.0], [40.0, 0.0]]),
    ]
    init_travel = compute_unsorted_travel_distance(lines, start_pos=(0.0, 0.0))
    assert math.isclose(init_travel, 40.0, abs_tol=1e-4)
    opt_lines, travels, new_travel = optimize_paths_2opt(
        lines, [], init_travel, start_pos=(0.0, 0.0)
    )
    assert new_travel < init_travel
    assert math.isclose(new_travel, 0.0, abs_tol=1e-4)
    # Verify travels match actual start/end points of opt_lines
    cur = (0.0, 0.0)
    for idx, line in enumerate(opt_lines):
        assert travels[idx][0] == cur
        assert np.allclose(travels[idx][1], line[0])
        cur = (float(line[-1, 0]), float(line[-1, 1]))

