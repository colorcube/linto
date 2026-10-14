import pytest
from plotter_studio.core.document import Document, Page, DEVICE_PROFILES


def test_device_profile_mutoh_xp500_margins():
    page = Page(preset="A3", orientation="landscape", device_profile="mutoh_xp500", feed_edge="top")
    assert page.margin_top_mm == 25.0
    assert page.margin_bottom_mm == 5.0
    assert page.margin_left_mm == 5.0
    assert page.margin_right_mm == 5.0

    # Switch feed edge to left
    page.apply_device_profile("mutoh_xp500", feed_edge="left")
    assert page.margin_left_mm == 25.0
    assert page.margin_top_mm == 5.0
    assert page.margin_bottom_mm == 5.0
    assert page.margin_right_mm == 5.0

    # Switch feed edge to bottom
    page.apply_device_profile("mutoh_xp500", feed_edge="bottom")
    assert page.margin_bottom_mm == 25.0
    assert page.margin_top_mm == 5.0

    # Switch feed edge to right
    page.apply_device_profile("mutoh_xp500", feed_edge="right")
    assert page.margin_right_mm == 25.0
    assert page.margin_bottom_mm == 5.0


def test_device_profile_flatbed_margins():
    page = Page(preset="A3", orientation="landscape", device_profile="flatbed_sym")
    assert page.margin_top_mm == 5.0
    assert page.margin_bottom_mm == 5.0
    assert page.margin_left_mm == 5.0
    assert page.margin_right_mm == 5.0

    # Borderless flatbed
    page.apply_device_profile("flatbed_borderless")
    assert page.margin_top_mm == 0.0
    assert page.margin_bottom_mm == 0.0
    assert page.margin_left_mm == 0.0
    assert page.margin_right_mm == 0.0


def test_printable_area_respects_margins():
    page = Page(preset="A3", orientation="landscape", device_profile="mutoh_xp500", feed_edge="top")
    # A3 Landscape is 420 x 297 mm
    assert page.width_mm == 420.0
    assert page.height_mm == 297.0

    box = page.plottable_box
    # Width: 420 - (5 + 5) = 410 mm
    # Height: 297 - (25 + 5) = 267 mm
    assert box.width == 410.0
    assert box.height == 267.0
    assert box.min_x == 5.0
    assert box.max_x == 415.0
    assert box.min_y == 25.0
    assert box.max_y == 292.0
