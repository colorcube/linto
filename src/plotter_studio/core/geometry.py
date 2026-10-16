"""Core geometry types and transformations in millimeter coordinates."""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Sequence, Union
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

    def transform_xy(self, x: float, y: float) -> Tuple[float, float]:
        return (
            self.a * x + self.c * y + self.tx,
            self.b * x + self.d * y + self.ty,
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


@dataclass(frozen=True)
class LineSegment:
    """Straight line segment from start to end in millimeters."""
    start: Tuple[float, float]
    end: Tuple[float, float]

    def transformed(self, t: AffineTransform) -> LineSegment:
        return LineSegment(
            start=t.transform_xy(*self.start),
            end=t.transform_xy(*self.end),
        )


@dataclass(frozen=True)
class QuadraticBezierSegment:
    """Quadratic Bézier curve segment in millimeters."""
    start: Tuple[float, float]
    control: Tuple[float, float]
    end: Tuple[float, float]

    def transformed(self, t: AffineTransform) -> QuadraticBezierSegment:
        return QuadraticBezierSegment(
            start=t.transform_xy(*self.start),
            control=t.transform_xy(*self.control),
            end=t.transform_xy(*self.end),
        )


@dataclass(frozen=True)
class CubicBezierSegment:
    """Cubic Bézier curve segment in millimeters."""
    start: Tuple[float, float]
    control1: Tuple[float, float]
    control2: Tuple[float, float]
    end: Tuple[float, float]

    def transformed(self, t: AffineTransform) -> CubicBezierSegment:
        return CubicBezierSegment(
            start=t.transform_xy(*self.start),
            control1=t.transform_xy(*self.control1),
            control2=t.transform_xy(*self.control2),
            end=t.transform_xy(*self.end),
        )


@dataclass(frozen=True)
class ArcSegment:
    """Elliptical/circular arc segment in millimeters."""
    start: Tuple[float, float]
    end: Tuple[float, float]
    center: Tuple[float, float]
    rx: float
    ry: float
    rotation_rad: float = 0.0
    start_angle_rad: float = 0.0
    sweep_angle_rad: float = 0.0
    large_arc: bool = False
    sweep: bool = True
    cubics: Tuple[CubicBezierSegment, ...] = ()

    def transformed(self, t: AffineTransform) -> ArcSegment:
        sx = math.hypot(t.a, t.b)
        sy = math.hypot(t.c, t.d)
        det = t.a * t.d - t.b * t.c
        ortho = abs(t.a * t.c + t.b * t.d)
        new_cubics = tuple(c.transformed(t) for c in self.cubics)
        # Parametric arc (rx, ry, start_angle, sweep_angle) is preserved under
        # orientation-preserving similarity transforms (translation + rotation + uniform scale)
        is_similarity = det > 1e-12 and abs(sx - sy) <= 1e-6 * max(1.0, sx) and ortho <= 1e-6 * max(1.0, sx * sy)
        if is_similarity:
            rot_offset = math.atan2(t.b, t.a)
            return ArcSegment(
                start=t.transform_xy(*self.start),
                end=t.transform_xy(*self.end),
                center=t.transform_xy(*self.center),
                rx=self.rx * sx,
                ry=self.ry * sy,
                rotation_rad=self.rotation_rad + rot_offset,
                start_angle_rad=self.start_angle_rad,
                sweep_angle_rad=self.sweep_angle_rad,
                large_arc=self.large_arc,
                sweep=self.sweep,
                cubics=new_cubics,
            )
        # Under non-uniform scale, shear, or reflection, fall back to affine-invariant cubics
        return ArcSegment(
            start=t.transform_xy(*self.start),
            end=t.transform_xy(*self.end),
            center=t.transform_xy(*self.center),
            rx=0.0,
            ry=0.0,
            rotation_rad=0.0,
            start_angle_rad=0.0,
            sweep_angle_rad=0.0,
            large_arc=self.large_arc,
            sweep=self.sweep if det >= 0 else (not self.sweep),
            cubics=new_cubics,
        )


PathSegment = Union[LineSegment, QuadraticBezierSegment, CubicBezierSegment, ArcSegment]


def _quad_bezier_eval(p0: float, p1: float, p2: float, t: float) -> float:
    mt = 1.0 - t
    return mt * mt * p0 + 2.0 * mt * t * p1 + t * t * p2


def _cubic_bezier_eval(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    mt = 1.0 - t
    return (
        mt * mt * mt * p0
        + 3.0 * mt * mt * t * p1
        + 3.0 * mt * t * t * p2
        + t * t * t * p3
    )


def _cubic_extrema_1d(p0: float, p1: float, p2: float, p3: float) -> List[float]:
    vals = [p0, p3]
    a = -p0 + 3.0 * p1 - 3.0 * p2 + p3
    b = 2.0 * (p0 - 2.0 * p1 + p2)
    c = p1 - p0
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            t = -c / b
            if 0.0 < t < 1.0:
                vals.append(_cubic_bezier_eval(p0, p1, p2, p3, t))
    else:
        disc = b * b - 4.0 * a * c
        if disc >= 0.0:
            sqrt_d = math.sqrt(disc)
            for t in ((-b - sqrt_d) / (2.0 * a), (-b + sqrt_d) / (2.0 * a)):
                if 0.0 < t < 1.0:
                    vals.append(_cubic_bezier_eval(p0, p1, p2, p3, t))
    return vals


def compute_segments_bounds(segments: Sequence[PathSegment]) -> Optional[BoundingBox]:
    """Compute exact analytical axis-aligned bounding box for a sequence of PathSegments."""
    if not segments:
        return None

    xs: List[float] = []
    ys: List[float] = []

    for seg in segments:
        if isinstance(seg, LineSegment):
            xs.extend((seg.start[0], seg.end[0]))
            ys.extend((seg.start[1], seg.end[1]))
        elif isinstance(seg, QuadraticBezierSegment):
            x0, y0 = seg.start
            x1, y1 = seg.control
            x2, y2 = seg.end
            xs.extend((x0, x2))
            ys.extend((y0, y2))
            denom_x = x0 - 2.0 * x1 + x2
            if abs(denom_x) > 1e-12:
                tx = (x0 - x1) / denom_x
                if 0.0 < tx < 1.0:
                    xs.append(_quad_bezier_eval(x0, x1, x2, tx))
            denom_y = y0 - 2.0 * y1 + y2
            if abs(denom_y) > 1e-12:
                ty = (y0 - y1) / denom_y
                if 0.0 < ty < 1.0:
                    ys.append(_quad_bezier_eval(y0, y1, y2, ty))
        elif isinstance(seg, CubicBezierSegment):
            xs.extend(_cubic_extrema_1d(seg.start[0], seg.control1[0], seg.control2[0], seg.end[0]))
            ys.extend(_cubic_extrema_1d(seg.start[1], seg.control1[1], seg.control2[1], seg.end[1]))
        elif isinstance(seg, ArcSegment):
            if seg.cubics:
                for c in seg.cubics:
                    xs.extend(_cubic_extrema_1d(c.start[0], c.control1[0], c.control2[0], c.end[0]))
                    ys.extend(_cubic_extrema_1d(c.start[1], c.control1[1], c.control2[1], c.end[1]))
            else:
                xs.extend((seg.start[0], seg.end[0]))
                ys.extend((seg.start[1], seg.end[1]))

    if not xs or not ys:
        return None
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))

