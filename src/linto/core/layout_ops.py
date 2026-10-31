"""Pure geometric layout and alignment operations for ImportItem collections."""

from __future__ import annotations

import copy
import math
from typing import Optional, Sequence

from .document import ImportItem
from .geometry import AffineTransform, BoundingBox


TransformChange = tuple[ImportItem, AffineTransform, AffineTransform]


def get_combined_bounds(items: Sequence[ImportItem]) -> Optional[BoundingBox]:
    """Compute the combined current bounding box of a sequence of ImportItems."""
    bounds: Optional[BoundingBox] = None
    for it in items:
        cb = it.current_bounds
        if cb is not None:
            bounds = cb if bounds is None else bounds.expanded_to(cb)
    return bounds


def center_item_in_box(item: ImportItem, target_box: BoundingBox) -> None:
    """Center a newly imported item within target_box using its original_bounds."""
    if item.original_bounds is not None:
        ob = item.original_bounds
        item.transform.tx = target_box.min_x + (target_box.width - ob.width) / 2.0 - ob.min_x
        item.transform.ty = target_box.min_y + (target_box.height - ob.height) / 2.0 - ob.min_y


def compute_rotation_transforms(
    items: Sequence[ImportItem],
    angle_degrees: float,
) -> list[TransformChange]:
    """Rotate items around their combined visual center."""
    if not items:
        return []
    cb = get_combined_bounds(items)
    if cb is None:
        return []

    cx, cy = cb.center.x, cb.center.y
    rot_t = AffineTransform.rotation(angle_degrees, cx, cy)
    changes: list[TransformChange] = []
    for it in items:
        old_t = copy.deepcopy(it.transform)
        new_t = rot_t.multiply(old_t)
        changes.append((it, old_t, new_t))
    return changes


def compute_scene_scale_transforms(
    items: Sequence[ImportItem],
    factor_x: float,
    factor_y: float,
) -> list[TransformChange]:
    """Scale items around their combined center in scene coordinates, preserving rotation."""
    if not items:
        return []
    cb = get_combined_bounds(items)
    if cb is None:
        return []

    cx, cy = cb.center.x, cb.center.y
    t1 = AffineTransform.translation(-cx, -cy)
    s = AffineTransform(factor_x, 0.0, 0.0, factor_y, 0.0, 0.0)
    t2 = AffineTransform.translation(cx, cy)
    s_scene = t2.multiply(s.multiply(t1))

    changes: list[TransformChange] = []
    for it in items:
        old_t = copy.deepcopy(it.transform)
        new_t = s_scene.multiply(old_t)
        changes.append((it, old_t, new_t))
    return changes


def compute_reset_scale_transforms(items: Sequence[ImportItem]) -> list[TransformChange]:
    """Reset each item's scale to 1.0 (1:1 original mm size), preserving rotation and center."""
    changes: list[TransformChange] = []
    for it in items:
        cur_scale = math.hypot(it.transform.a, it.transform.b)
        if cur_scale <= 1e-6:
            continue
        factor = 1.0 / cur_scale
        cb = it.current_bounds
        if cb is None:
            continue
        cx, cy = cb.center.x, cb.center.y
        t1 = AffineTransform.translation(-cx, -cy)
        s = AffineTransform(factor, 0.0, 0.0, factor, 0.0, 0.0)
        t2 = AffineTransform.translation(cx, cy)
        s_scene = t2.multiply(s.multiply(t1))
        old_t = copy.deepcopy(it.transform)
        new_t = s_scene.multiply(old_t)
        changes.append((it, old_t, new_t))
    return changes


def compute_fit_to_box_transforms(
    items: Sequence[ImportItem],
    target_box: BoundingBox,
    margin_mm: float = 0.0,
) -> list[TransformChange]:
    """Uniformly scale and center items to fit inside target_box with margin_mm."""
    if not items:
        return []
    cb = get_combined_bounds(items)
    if cb is None or cb.width <= 0 or cb.height <= 0:
        return []

    avail_w = max(10.0, target_box.width - 2 * margin_mm)
    avail_h = max(10.0, target_box.height - 2 * margin_mm)
    scale_factor = min(avail_w / cb.width, avail_h / cb.height)
    cx, cy = cb.center.x, cb.center.y

    t1 = AffineTransform.translation(-cx, -cy)
    s = AffineTransform(scale_factor, 0.0, 0.0, scale_factor, 0.0, 0.0)
    t2 = AffineTransform.translation(target_box.center.x, target_box.center.y)
    fit_t = t2.multiply(s.multiply(t1))

    changes: list[TransformChange] = []
    for it in items:
        old_t = copy.deepcopy(it.transform)
        new_t = fit_t.multiply(old_t)
        changes.append((it, old_t, new_t))
    return changes


def compute_translation_transforms(
    items: Sequence[ImportItem],
    dx: float,
    dy: float,
) -> list[TransformChange]:
    """Translate items by (dx, dy) in mm."""
    changes: list[TransformChange] = []
    for it in items:
        old_t = copy.deepcopy(it.transform)
        new_t = copy.deepcopy(old_t)
        new_t.tx += dx
        new_t.ty += dy
        changes.append((it, old_t, new_t))
    return changes


def compute_position_transforms(
    items: Sequence[ImportItem],
    target_box: BoundingBox,
    offset_x_mm: float,
    offset_y_mm: float,
) -> list[TransformChange]:
    """Move items so their combined top-left corner is at target_box.min + (offset_x_mm, offset_y_mm)."""
    if not items:
        return []
    cb = get_combined_bounds(items)
    if cb is None:
        return []
    dx = (target_box.min_x + offset_x_mm) - cb.min_x
    dy = (target_box.min_y + offset_y_mm) - cb.min_y
    return compute_translation_transforms(items, dx, dy)


def compute_align_center_transforms(
    items: Sequence[ImportItem],
    target_box: BoundingBox,
    horizontal: bool = True,
    vertical: bool = True,
) -> list[TransformChange]:
    """Align combined item center horizontally and/or vertically to target_box.center."""
    if not items:
        return []
    cb = get_combined_bounds(items)
    if cb is None:
        return []
    dx = (target_box.center.x - cb.center.x) if horizontal else 0.0
    dy = (target_box.center.y - cb.center.y) if vertical else 0.0
    return compute_translation_transforms(items, dx, dy)
