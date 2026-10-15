import pytest
import numpy as np
from plotter_studio.pipeline.clip import clip_segment, clip_polyline_to_box, clip_polylines_to_box


def test_clip_segment_inside():
    # Segment from (10, 10) to (50, 50) inside box [0, 0, 100, 100]
    res = clip_segment(10.0, 10.0, 50.0, 50.0, 0.0, 0.0, 100.0, 100.0)
    assert res is not None
    assert res == (10.0, 10.0, 50.0, 50.0)


def test_clip_segment_outside():
    # Segment from (-50, 10) to (-10, 10) outside box [0, 0, 100, 100]
    res = clip_segment(-50.0, 10.0, -10.0, 10.0, 0.0, 0.0, 100.0, 100.0)
    assert res is None


def test_clip_segment_crossing():
    # Segment from (-20, 50) to (50, 50) crossing x=0
    res = clip_segment(-20.0, 50.0, 50.0, 50.0, 0.0, 0.0, 100.0, 100.0)
    assert res is not None
    assert abs(res[0] - 0.0) < 1e-4
    assert abs(res[1] - 50.0) < 1e-4
    assert abs(res[2] - 50.0) < 1e-4
    assert abs(res[3] - 50.0) < 1e-4


def test_clip_polyline_through_box():
    # Polyline: (-10, 50) -> (50, 50) -> (150, 50)
    line = np.array([[-10.0, 50.0], [50.0, 50.0], [150.0, 50.0]])
    clipped = clip_polyline_to_box(line, 0.0, 0.0, 100.0, 100.0)
    assert len(clipped) == 1
    sub = clipped[0]
    assert len(sub) == 3
    assert abs(sub[0, 0] - 0.0) < 1e-4
    assert abs(sub[1, 0] - 50.0) < 1e-4
    assert abs(sub[2, 0] - 100.0) < 1e-4
