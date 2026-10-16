"""Core geometry types and transformations in millimeter coordinates."""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Sequence
import numpy as np


@dataclass(frozen=True)
class Point:
    """2D Point in millimeters."""
    x: float
    y: float

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Point:
        return Point(self.x * scalar, self.y * scalar)

    def distance_to(self, other: Point) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass
class BoundingBox:
    """Axis-aligned bounding box in millimeters."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return max(0.0, self.max_x - self.min_x)

    @property
    def height(self) -> float:
        return max(0.0, self.max_y - self.min_y)

    @property
    def center(self) -> Point:
        return Point((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    def contains_point(self, pt: Point) -> bool:
        return self.min_x <= pt.x <= self.max_x and self.min_y <= pt.y <= self.max_y

    def contains_box(self, other: BoundingBox) -> bool:
        return (
            self.min_x <= other.min_x
            and self.max_x >= other.max_x
            and self.min_y <= other.min_y
            and self.max_y >= other.max_y
        )

    def expanded_to(self, other: BoundingBox) -> BoundingBox:
        return BoundingBox(
            min_x=min(self.min_x, other.min_x),
            min_y=min(self.min_y, other.min_y),
            max_x=max(self.max_x, other.max_x),
            max_y=max(self.max_y, other.max_y),
        )

    @classmethod
    def from_points(cls, points: Sequence[Point]) -> Optional[BoundingBox]:
        if not points:
            return None
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return cls(min(xs), min(ys), max(xs), max(ys))


@dataclass
class AffineTransform:
    """2D Affine Transformation matrix [[a, c, tx], [b, d, ty]]."""
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    @classmethod
    def identity(cls) -> AffineTransform:
        return cls(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    @classmethod
    def translation(cls, tx: float, ty: float) -> AffineTransform:
        return cls(1.0, 0.0, 0.0, 1.0, tx, ty)

    @classmethod
    def scale(cls, sx: float, sy: Optional[float] = None) -> AffineTransform:
        if sy is None:
            sy = sx
        return cls(sx, 0.0, 0.0, sy, 0.0, 0.0)

    @classmethod
    def rotation(cls, angle_degrees: float, cx: float = 0.0, cy: float = 0.0) -> AffineTransform:
        rad = math.radians(angle_degrees)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        # Snap exact orthogonal angles
        if abs(cos_a) < 1e-12:
            cos_a = 0.0
        elif abs(cos_a - 1.0) < 1e-12:
            cos_a = 1.0
        elif abs(cos_a + 1.0) < 1e-12:
            cos_a = -1.0

        if abs(sin_a) < 1e-12:
            sin_a = 0.0
        elif abs(sin_a - 1.0) < 1e-12:
            sin_a = 1.0
        elif abs(sin_a + 1.0) < 1e-12:
            sin_a = -1.0

        # T(cx, cy) * R * T(-cx, -cy)
        t1 = cls.translation(-cx, -cy)
        r = cls(cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
        t2 = cls.translation(cx, cy)
        res = t2.multiply(r.multiply(t1))
        # Clean small float precision drifts
        res.a = round(res.a, 10)
        res.b = round(res.b, 10)
        res.c = round(res.c, 10)
        res.d = round(res.d, 10)
        res.tx = round(res.tx, 10)
        res.ty = round(res.ty, 10)
        return res

    def multiply(self, other: AffineTransform) -> AffineTransform:
        """Matrix product self * other (applies other first, then self)."""
        return AffineTransform(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            tx=self.a * other.tx + self.c * other.ty + self.tx,
            ty=self.b * other.tx + self.d * other.ty + self.ty,
        )

    def transform_point(self, pt: Point) -> Point:
        return Point(
            x=self.a * pt.x + self.c * pt.y + self.tx,
            y=self.b * pt.x + self.d * pt.y + self.ty,
        )

    def transform_points(self, points: Sequence[Point]) -> List[Point]:
        return [self.transform_point(p) for p in points]

    def transform_coords(self, coords: np.ndarray) -> np.ndarray:
        """Transform an (N, 2) numpy array of points."""
        if len(coords) == 0:
            return coords
        m = np.array([[self.a, self.c], [self.b, self.d]])
        t = np.array([self.tx, self.ty])
        return coords @ m.T + t

    def inverse(self) -> AffineTransform:
        """Calculate the inverse transformation matrix."""
        det = self.a * self.d - self.b * self.c
        if abs(det) < 1e-12:
            return AffineTransform.identity()
        inv_det = 1.0 / det
        return AffineTransform(
            a=self.d * inv_det,
            b=-self.b * inv_det,
            c=-self.c * inv_det,
            d=self.a * inv_det,
            tx=(-self.d * self.tx + self.c * self.ty) * inv_det,
            ty=(self.b * self.tx - self.a * self.ty) * inv_det,
        )
