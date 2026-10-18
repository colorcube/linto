"""Single-stroke Hershey Simplex vector font renderer for SVG <text> import."""

from __future__ import annotations

import unicodedata
from typing import List, Optional, Tuple

from .geometry import AffineTransform, LineSegment, PathSegment

# Standard Hershey Simplex (Roman Simplex) glyph definitions for ASCII 32..126.
# Format: (left_margin, right_margin, stroke_string) where coordinates are encoded
# as pairs of characters relative to 'R' (ord(c) - ord('R')), and " R" separates pen-up strokes.
# In Hershey coordinates: +X is right, +Y is down, cap-top is y=-12, baseline is y=+9 (cap-height = 21).
_HERSHEY_SIMPLEX_ASCII: dict[str, Tuple[int, int, str]] = {
    " ": (-8, 8, ""),
    "!": (-5, 5, "MWRFRT RRYQZR[SZRY"),
    '"': (-8, 8, "JZNFNM RVFVM"),
    "#": (-11, 10, "H]SBLb RYBRb RLOZO RKUYU"),
    "$": (-10, 10, "H\\PBP_ RTBT_ RYIWGTFPFMGKIKKLMMNOOUQWRXSYUYXWZT[P[MZKX"),
    "%": (-12, 12, "F^[FI[ RNFPHPJOLMMKMIKIIJGLFNFPGSHVHYG[F RWTUUTWTYV[X[ZZ[X[VYTWT"),
    "&": (-13, 13, "E_\\O\\N[MZMYNXPVUTXRZP[L[JZIYHWHUISJRQNRMSKSIRGPFNGMIMKNNPQUXWZY[[[\\Z\\Y"),
    "'": (-5, 5, "MWRHQGRFSGSIRKQL"),
    "(": (-7, 7, "KYVBTDRGPKOPOTPYR]T`Vb"),
    ")": (-7, 7, "KYNBPDRGTKUPUTTYR]P`Nb"),
    "*": (-8, 8, "JZRFRR RMIWO RWIMO"),
    "+": (-13, 13, "E_RIR[ RIR[R"),
    ",": (-5, 5, "MWSZR[QZRYSZS\\R^Q_"),
    "-": (-13, 13, "E_IR[R"),
    ".": (-5, 5, "MWRYQZR[SZRY"),
    "/": (-11, 11, "G][BIb"),
    "0": (-10, 10, "H\\QFNGLJKOKRLWNZQ[S[VZXWYRYOXJVGSFQF"),
    "1": (-10, 10, "H\\NJPISFS["),
    "2": (-10, 10, "H\\LKLJMHNGPFTFVGWHXJXLWNUQK[Y["),
    "3": (-10, 10, "H\\MFXFRNUNWOXPYSYUXXVZS[P[MZLYKW"),
    "4": (-10, 10, "H\\UFKTZT RUFU["),
    "5": (-10, 10, "H\\WFMFLOMNPMSMVNXPYSYUXXVZS[P[MZLYKW"),
    "6": (-10, 10, "H\\XIWGTFRFOGMJLOLTMXOZR[S[VZXXYUYTXQVOSNRNOOMQLT"),
    "7": (-10, 10, "H\\YFO[ RKFYF"),
    "8": (-10, 10, "H\\PFMGLILKMMONSOVPXRYTYWXYWZT[P[MZLYKWKTLRNPQOUNWMXKXIWGTFPF"),
    "9": (-10, 10, "H\\XMWPURRSQSNRLPKMKLLINGQFRFUGWIXMXRWWUZR[P[MZLX"),
    ":": (-5, 5, "MWRMQNROSNRM RRYQZR[SZRY"),
    ";": (-5, 5, "MWRMQNROSNRM RSZR[QZRYSZS\\R^Q_"),
    "<": (-12, 12, "F^ZIJRZ["),
    "=": (-13, 13, "E_IO[O RIU[U"),
    ">": (-12, 12, "F^JIZRJ["),
    "?": (-9, 9, "I[LKLJMHNGPFTFVGWHXJXLWNVORQRT RRYQZR[SZRY"),
    "@": (-14, 13, "DaWNVLTKQKOLNMMPMSNUPVSVUUVS RQKOMNPNSOUPV RWKVSVUXVZV\\T]Q]O\\L[JYHWGTFQFNGLHJJILHOHRIUJWLYNZQ[T[WZYYZX RXKWSWUXV"),
    "A": (-9, 9, "I[RFJ[ RRFZ[ RMTWT"),
    "B": (-10, 10, "G\\KFK[ RKFTFWGXHYJYLXNWOTP RKPTPWQXRYTYWXYWZT[K["),
    "C": (-10, 11, "H]ZKYIWGUFQFOGMILKKNKSLVMXOZQ[U[WZYXZV"),
    "D": (-10, 10, "G\\KFK[ RKFRFUGWIXKYNYSXVWXUZR[K["),
    "E": (-9, 10, "H[LFL[ RLFYF RLPTP RL[Y["),
    "F": (-9, 10, "HZLFL[ RLFYF RLPTP"),
    "G": (-10, 11, "H]ZKYIWGUFQFOGMILKKNKSLVMXOZQ[U[WZYXZVZS RUSZS"),
    "H": (-11, 11, "G]KFK[ RYFY[ RKPYP"),
    "I": (-4, 4, "NVRFR["),
    "J": (-8, 8, "JZVFVVUYTZR[P[NZMYLVLT"),
    "K": (-10, 11, "G\\KFK[ RYFKT RPOY["),
    "L": (-9, 8, "HYLFL[ RL[X["),
    "M": (-12, 12, "F^JFJ[ RJFR[ RZFR[ RZFZ["),
    "N": (-11, 11, "G]KFK[ RKFY[ RYFY["),
    "O": (-11, 11, "G]PFNGLIKKJNJSKVLXNZP[T[VZXXYVZSZNYKXIVGTFPF"),
    "P": (-10, 10, "G\\KFK[ RKFTFWGXHYJYMXOWPTQKQ"),
    "Q": (-11, 11, "G]PFNGLIKKJNJSKVLXNZP[T[VZXXYVZSZNYKXIVGTFPF RSWY]"),
    "R": (-10, 10, "G\\KFK[ RKFTFWGXHYJYLXNWOTPKP RRPY["),
    "S": (-10, 10, "H\\YIWGTFPFMGKIKKLMMNOOUQWRXSYUYXWZT[P[MZKX"),
    "T": (-8, 8, "JZRFR[ RKFYF"),
    "U": (-11, 11, "G]KFKULXNZQ[S[VZXXYUYF"),
    "V": (-9, 9, "I[JFR[ RZFR["),
    "W": (-12, 12, "F^HFM[ RRFM[ RRFW[ R\\FW["),
    "X": (-10, 10, "H\\KFY[ RYFK["),
    "Y": (-9, 9, "I[JFRPR[ RZFRP"),
    "Z": (-10, 10, "H\\YFK[ RKFYF RK[Y["),
    "[": (-7, 7, "KYOBOb RPBPb ROBVB RObVb"),
    "\\": (-7, 7, "KYKFY^"),
    "]": (-7, 7, "KYTBTb RUBUb RNBUB RNbUb"),
    "^": (-8, 8, "JZRDJR RRDZR"),
    "_": (-9, 9, "I[Ib[b"),
    "`": (-5, 5, "MWSFRGQIQKRLSKRJ"),
    "a": (-9, 10, "I\\XMX[ RXPVNTMQMONMPLSLUMXOZQ[T[VZXX"),
    "b": (-9, 10, "H[LFL[ RLPNNPMSMUNWPXSXUWXUZS[P[NZLX"),
    "c": (-9, 9, "I[XPVNTMQMONMPLSLUMXOZQ[T[VZXX"),
    "d": (-10, 9, "I\\XFX[ RXPVNTMQMONMPLSLUMXOZQ[T[VZXX"),
    "e": (-9, 9, "I[LSXSXQWOVNTMQMONMPLSLUMXOZQ[T[VZXX"),
    "f": (-5, 7, "MYWFUFSGRJR[ ROMVM"),
    "g": (-9, 10, "I\\XMX]W`VaTbQbOa RXPVNTMQMONMPLSLUMXOZQ[T[VZXX"),
    "h": (-9, 10, "I\\MFM[ RMQPNRMUMWNXQX["),
    "i": (-4, 4, "NVQFRGSFREQF RRMR["),
    "j": (-5, 5, "MWRFSGTFSERF RSMS^RaPbNb"),
    "k": (-9, 9, "IZMFM[ RWMMW RQSX["),
    "l": (-4, 4, "NVRFR["),
    "m": (-15, 15, "CaGMG[ RGQJNLMOMQNRQR[ RRQUNWMZM\\N]Q]["),
    "n": (-9, 10, "I\\MMM[ RMQPNRMUMWNXQX["),
    "o": (-9, 9, "I\\QMONMPLSLUMXOZQ[T[VZXXYUYSXPVNTMQM"),
    "p": (-9, 10, "H[LMLb RLPNNPMSMUNWPXSXUWXUZS[P[NZLX"),
    "q": (-10, 9, "I\\XMXb RXPVNTMQMONMPLSLUMXOZQ[T[VZXX"),
    "r": (-6, 7, "KXOMO[ ROSPPRNTMWM"),
    "s": (-8, 8, "J[XPWNTMQMNNMPNRPSUTWUXWXXWZT[Q[NZMX"),
    "t": (-5, 7, "MYRFRWSZU[W[ ROMVM"),
    "u": (-9, 10, "I\\MMMWNZP[S[UZXW RXMX["),
    "v": (-8, 8, "JZLMR[ RXMR["),
    "w": (-11, 11, "G]JMN[ RRMN[ RRMV[ RZMV["),
    "x": (-8, 8, "J[MMX[ RXMM["),
    "y": (-8, 8, "JZLMR[ RXMR[P_NaLbKb"),
    "z": (-8, 8, "J[XMM[ RMMXM RM[X["),
    "{": (-7, 7, "KYTBRCQDPFPHQJRKSMSOQQ RRCQEQGRISJTLTNSPORSTTVTXSZR[Q]Q_Ra RQSSUSWRYQZP\\P^Q`RaTb"),
    "|": (-4, 4, "NVRBRb"),
    "}": (-7, 7, "KYPBRCSDTFTHSJRKQMQOSQ RRCSESGRIQJPLPNQPURQTPVPXQZR[S]S_Ra RSSQUQWRYSZT\\T^S`RaPb"),
    "~": (-12, 12, "F^IUISJPLONOPPTSVTXTZS[Q ISJQLPNPPQTTVUXUZT[Q[O"),
}

# Cap height in Hershey units (from y=-12 to baseline y=+9)
_CAP_HEIGHT_UNITS = 21.0
_BASELINE_Y_UNITS = 9.0


def _decode_hershey_strokes(stroke_str: str) -> List[List[Tuple[float, float]]]:
    """Decode a Hershey stroke string (after the 2-char margin header) into polylines in Hershey units."""
    if len(stroke_str) <= 2:
        return []
    body = stroke_str[2:]
    polylines: List[List[Tuple[float, float]]] = []
    cur: List[Tuple[float, float]] = []
    i = 0
    while i + 1 < len(body):
        c1 = body[i]
        c2 = body[i + 1]
        i += 2
        if c1 == " " and c2 == "R":
            if len(cur) >= 2:
                polylines.append(cur)
            cur = []
            continue
        x = float(ord(c1) - ord("R"))
        y = float(ord(c2) - ord("R"))
        cur.append((x, y))
    if len(cur) >= 2:
        polylines.append(cur)
    return polylines


# Pre-decoded custom glyphs for German / common technical symbols in Hershey coordinates
_CUSTOM_GLYPHS: dict[str, Tuple[int, int, List[List[Tuple[float, float]]]]] = {
    "ß": (
        -9,
        10,
        [
            [(-5.0, 9.0), (-5.0, -7.0), (-4.0, -10.0), (-1.0, -12.0), (2.0, -12.0), (5.0, -10.0), (6.0, -7.0), (5.0, -4.0), (1.0, -2.0), (6.0, 0.0), (7.0, 3.0), (7.0, 6.0), (5.0, 8.0), (2.0, 9.0), (-1.0, 9.0)],
        ],
    ),
    "°": (
        -6,
        6,
        [
            [(0.0, -12.0), (2.5, -11.0), (3.5, -8.5), (2.5, -6.0), (0.0, -5.0), (-2.5, -6.0), (-3.5, -8.5), (-2.5, -11.0), (0.0, -12.0)],
        ],
    ),
    "±": (
        -11,
        11,
        [
            [(0.0, -11.0), (0.0, 3.0)],
            [(-7.0, -4.0), (7.0, -4.0)],
            [(-7.0, 8.0), (7.0, 8.0)],
        ],
    ),
    "×": (
        -10,
        10,
        [
            [(-6.0, -8.0), (6.0, 4.0)],
            [(6.0, -8.0), (-6.0, 4.0)],
        ],
    ),
    "–": (-10, 10, [[(-7.0, -1.0), (7.0, -1.0)]]),
    "—": (-13, 13, [[(-11.0, -1.0), (11.0, -1.0)]]),
    "„": (-6, 6, [[(-2.0, 7.0), (-3.0, 11.0)], [(2.0, 7.0), (1.0, 11.0)]]),
    "“": (-6, 6, [[(-2.0, -12.0), (-3.0, -8.0)], [(2.0, -12.0), (1.0, -8.0)]]),
    "”": (-6, 6, [[(-2.0, -12.0), (-3.0, -8.0)], [(2.0, -12.0), (1.0, -8.0)]]),
    "€": (
        -11,
        11,
        [
            [(7.0, -9.0), (4.0, -12.0), (-1.0, -12.0), (-5.0, -9.0), (-7.0, -4.0), (-7.0, 1.0), (-5.0, 6.0), (-1.0, 9.0), (4.0, 9.0), (7.0, 6.0)],
            [(-9.0, -3.0), (4.0, -3.0)],
            [(-9.0, 1.0), (3.0, 1.0)],
        ],
    ),
}


def _get_glyph_strokes(ch: str) -> Tuple[int, int, List[List[Tuple[float, float]]]]:
    """Return (left_margin, right_margin, polylines_in_hershey_units) for a single character."""
    if ch in _CUSTOM_GLYPHS:
        return _CUSTOM_GLYPHS[ch]

    if ch in _HERSHEY_SIMPLEX_ASCII:
        l_m, r_m, raw = _HERSHEY_SIMPLEX_ASCII[ch]
        return l_m, r_m, _decode_hershey_strokes(raw)

    # Decompose accented characters (e.g. Ä, Ö, Ü, ä, ö, ü, é, è, ê, ñ)
    decomp = unicodedata.normalize("NFKD", ch)
    base_ch = decomp[0] if decomp else "?"
    if base_ch not in _HERSHEY_SIMPLEX_ASCII:
        base_ch = "?"
    l_m, r_m, raw = _HERSHEY_SIMPLEX_ASCII[base_ch]
    strokes = _decode_hershey_strokes(raw)

    is_upper = base_ch.isupper()
    accent_y = -15.5 if is_upper else -8.5

    for comb in decomp[1:]:
        code = ord(comb)
        if code == 0x0308:  # Combining diaeresis (Umlaut ¨)
            strokes.append([(-3.0, accent_y - 1.0), (-3.0, accent_y + 0.5)])
            strokes.append([(3.0, accent_y - 1.0), (3.0, accent_y + 0.5)])
        elif code == 0x0301:  # Combining acute (´)
            strokes.append([(-1.5, accent_y + 1.0), (2.5, accent_y - 2.0)])
        elif code == 0x0300:  # Combining grave (`)
            strokes.append([(-2.5, accent_y - 2.0), (1.5, accent_y + 1.0)])
        elif code == 0x0302:  # Combining circumflex (^)
            strokes.append([(-3.0, accent_y + 1.0), (0.0, accent_y - 2.0), (3.0, accent_y + 1.0)])
        elif code == 0x0303:  # Combining tilde (~)
            strokes.append([(-3.5, accent_y), (-1.0, accent_y - 1.5), (1.0, accent_y + 1.0), (3.5, accent_y - 0.5)])
        elif code == 0x030A:  # Combining ring above (å)
            strokes.append([(0.0, accent_y - 2.0), (1.5, accent_y - 0.5), (0.0, accent_y + 1.0), (-1.5, accent_y - 0.5), (0.0, accent_y - 2.0)])

    return l_m, r_m, strokes


def render_text_to_subpaths(
    text: str,
    x: float,
    y: float,
    font_size: float = 12.0,
    anchor: str = "start",
    transform: Optional[AffineTransform] = None,
    scale_mm: float = 1.0,
) -> List[List[PathSegment]]:
    """
    Render a text string into a list of single-stroke vector subpaths (each a list of LineSegments)
    in millimeters.

    Parameters
    ----------
    text : str
        Text content to render.
    x, y : float
        Baseline start/anchor position in SVG user units.
    font_size : float
        SVG font-size in user units.
    anchor : str
        SVG text-anchor ('start', 'middle', or 'end').
    transform : Optional[AffineTransform]
        SVG element transformation matrix in user units.
    scale_mm : float
        Conversion factor from SVG user units to millimeters (default PX_TO_MM).
    """
    if not text or not text.strip():
        return []

    eff_font_size = max(1.0, float(font_size or 12.0))
    # Cap height is ~0.72 of nominal CSS/SVG font-size
    unit_scale = (eff_font_size * 0.72) / _CAP_HEIGHT_UNITS

    # First pass: collect glyph strokes and compute total advance width in Hershey units
    glyphs: List[Tuple[int, int, List[List[Tuple[float, float]]]]] = []
    total_units_w = 0.0
    for ch in text:
        if ch in ("\r", "\n"):
            continue
        if ch == "\t":
            ch = " "
        g = _get_glyph_strokes(ch)
        glyphs.append(g)
        total_units_w += float(g[1] - g[0])

    total_width_user = total_units_w * unit_scale
    anc = (anchor or "start").strip().lower()
    if anc == "middle":
        cursor_x = float(x) - total_width_user / 2.0
    elif anc == "end":
        cursor_x = float(x) - total_width_user
    else:
        cursor_x = float(x)

    baseline_y = float(y)
    subpaths: List[List[PathSegment]] = []

    for l_m, r_m, strokes in glyphs:
        advance_units = float(r_m - l_m)
        for poly in strokes:
            if len(poly) < 2:
                continue
            segs: List[PathSegment] = []
            for idx in range(len(poly) - 1):
                hx0, hy0 = poly[idx]
                hx1, hy1 = poly[idx + 1]

                ux0 = cursor_x + (hx0 - l_m) * unit_scale
                uy0 = baseline_y + (hy0 - _BASELINE_Y_UNITS) * unit_scale
                ux1 = cursor_x + (hx1 - l_m) * unit_scale
                uy1 = baseline_y + (hy1 - _BASELINE_Y_UNITS) * unit_scale

                if transform is not None:
                    tx0 = transform.a * ux0 + transform.c * uy0 + transform.tx
                    ty0 = transform.b * ux0 + transform.d * uy0 + transform.ty
                    tx1 = transform.a * ux1 + transform.c * uy1 + transform.tx
                    ty1 = transform.b * ux1 + transform.d * uy1 + transform.ty
                else:
                    tx0, ty0 = ux0, uy0
                    tx1, ty1 = ux1, uy1

                p0 = (tx0 * scale_mm, ty0 * scale_mm)
                p1 = (tx1 * scale_mm, ty1 * scale_mm)
                if (p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2 > 1e-12:
                    segs.append(LineSegment(start=p0, end=p1))
            if segs:
                subpaths.append(segs)

        cursor_x += advance_units * unit_scale

    return subpaths
