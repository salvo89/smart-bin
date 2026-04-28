#!/usr/bin/env python3
"""
Finger joint path generation for micro-raccolta panels (3 mm).
Base interna: (50-2t) x (44-2t) con t=3 mm -> 44 x 38 mm.
Fondo pannelli: un'unica tacca femmina centrata (niente dentini agli angoli); base con un solo dente maschio per lato.
Bordo superiore fronte/retro: linea dritta (coperchio appoggiato).

Uso: python tools/gen_finger_paths.py [ALTEZZA_MM]
  ALTEZZA_MM default 110. Pettini: PITCH/DEPTH/CORNER_TRIM fissi; il numero di denti segue l'altezza.
  In coda stampa FRONT_WINDOW_TRAP: vano fronte trapezoidale (parallelo al profilo esterno).
"""
from __future__ import annotations

import math

DEPTH = 3.0
PITCH = 10.0
CORNER_TRIM = 4.0

# Altezza pannelli verticali (mm). Originale 110; variante -30 mm lato -> 80.
HEIGHT = 110.0

MATERIAL = 3.0
# Fondo bidone: bordo esterno fronte 50 mm, lato 44 mm -> luce interna sotto spessore t
BASE_INNER_W = 50.0 - 2.0 * MATERIAL  # 44 (sotto fronte/retro)
BASE_INNER_D = 44.0 - 2.0 * MATERIAL  # 38 (sotto lati A/B)


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1])


def vscale(v, s):
    return (v[0] * s, v[1] * s)


def vlen(v):
    return math.hypot(v[0], v[1])


def vnorm(v):
    l = vlen(v)
    if l < 1e-12:
        return (0.0, 0.0)
    return (v[0] / l, v[1] / l)


def lerp(p0, p1, t):
    return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)


def finger_edge_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    inward: tuple[float, float],
    *,
    female: bool,
) -> list[tuple[float, float]]:
    tan = vnorm(vsub(p1, p0))
    L = vlen(vsub(p1, p0))
    nin = vnorm(inward)
    trim = min(CORNER_TRIM, max(0.0, (L - PITCH) / 2 - 0.5))
    p_start = vadd(p0, vscale(tan, trim))
    p_end = vsub(p1, vscale(tan, trim))
    Lm = vlen(vsub(p_end, p_start))
    if Lm < PITCH * 0.75:
        return [p0, p1]

    n_cells = max(1, int(round(Lm / PITCH)))
    cell = Lm / n_cells

    def off_for_cell(i: int) -> tuple[float, float]:
        odd = i % 2 == 1
        if not odd:
            return (0.0, 0.0)
        d = DEPTH if female else -DEPTH
        return vscale(nin, d)

    q = [lerp(p_start, p_end, k / n_cells) for k in range(n_cells + 1)]
    out: list[tuple[float, float]] = [p0, p_start]
    for i in range(n_cells):
        o = off_for_cell(i)
        start = vadd(q[i], o)
        end = vadd(q[i + 1], o)
        if abs(out[-1][0] - start[0]) > 1e-6 or abs(out[-1][1] - start[1]) > 1e-6:
            out.append(start)
        out.append(end)
    if abs(out[-1][0] - p_end[0]) > 1e-6 or abs(out[-1][1] - p_end[1]) > 1e-6:
        out.append(p_end)
    out.append(p1)
    return out


TAB_WIDTH = 12.0  # unico dente / tacca (mm)


def bottom_wall_single_center_notch(
    bottom_y: float,
    x0: float,
    x1: float,
) -> list[tuple[float, float]]:
    """Fondo pannello: linea retta con una sola tacca femmina centrata (rientro DEPTH)."""
    y_out = bottom_y
    y_in = bottom_y - DEPTH
    span = x1 - x0
    w = min(TAB_WIDTH, max(6.0, span - 6.0))
    cx = (x0 + x1) / 2.0
    na = cx - w / 2.0
    nb = cx + w / 2.0
    return [
        (x0, y_out),
        (na, y_out),
        (na, y_in),
        (nb, y_in),
        (nb, y_out),
        (x1, y_out),
    ]


def _single_tab_margins(span: float) -> tuple[float, float]:
    """Margine sinistro e larghezza tacca (tacca centrata, larghezza TAB_WIDTH)."""
    m = (span - TAB_WIDTH) / 2.0
    if m < 0:
        raise ValueError(f"span {span} troppo stretta per tacca {TAB_WIDTH}")
    return m, TAB_WIDTH


def edge_front_back(name: str):
    h = HEIGHT
    # Svasatura lineare come a 110 mm: +10 mm di luce in alto su fronte (50->60) in 110 mm di altezza.
    k = h / 110.0
    BL, BR = (0, h), (50, h)
    TR = (50.0 + 5.0 * k, 0.0)
    TL = (-5.0 * k, 0.0)
    c = (25.0, h / 2.0)
    if name == "bottom":
        p0, p1 = BL, BR
    elif name == "right":
        p0, p1 = BR, TR
    elif name == "top":
        p0, p1 = TR, TL
    elif name == "left":
        p0, p1 = TL, BL
    else:
        raise KeyError(name)
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    inward = vnorm(vsub(c, mid))
    return p0, p1, inward


def edge_side(name: str):
    h = HEIGHT
    k = h / 110.0
    BL, BR = (0, h), (44, h)
    TR = (44.0 + 5.0 * k, 0.0)
    TL = (-5.0 * k, 0.0)
    c = (22.0, h / 2.0)
    if name == "bottom":
        p0, p1 = BL, BR
    elif name == "right":
        p0, p1 = BR, TR
    elif name == "top":
        p0, p1 = TR, TL
    elif name == "left":
        p0, p1 = TL, BL
    else:
        raise KeyError(name)
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    inward = vnorm(vsub(c, mid))
    return p0, p1, inward


def stitch(edges: list[list[tuple[float, float]]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for seg in edges:
        if not seg:
            continue
        if out and seg[0] == out[-1]:
            out.extend(seg[1:])
        else:
            out.extend(seg)
    return out


def path_d(pts: list[tuple[float, float]]) -> str:
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    parts = [f"M{pts[0][0]:.4f},{pts[0][1]:.4f}"]
    for x, y in pts[1:]:
        parts.append(f"L{x:.4f},{y:.4f}")
    parts.append("Z")
    return " ".join(parts)


def panel_front_back_with_base_bottom() -> str:
    """Fondo: un'unica tacca centrata; top dritto."""
    bottom_y = HEIGHT
    bottom_pts = bottom_wall_single_center_notch(bottom_y, 0.0, 50.0)
    right = finger_edge_points(*edge_front_back("right"), female=True)
    p0, p1, _ = edge_front_back("top")
    top = [p0, p1]
    left = finger_edge_points(*edge_front_back("left"), female=True)
    segs = [bottom_pts, right, top, left]
    return path_d(stitch(segs))


def panel_side_with_base_bottom() -> str:
    bottom_y = HEIGHT
    bottom_pts = bottom_wall_single_center_notch(bottom_y, 0.0, 44.0)
    right = finger_edge_points(*edge_side("right"), female=False)
    top = [edge_side("top")[0], edge_side("top")[1]]
    left = finger_edge_points(*edge_side("left"), female=False)
    segs = [bottom_pts, right, top, left]
    return path_d(stitch(segs))


def front_window_trapezoid_path_d(
    height: float,
    y_top: float,
    win_h: float,
    inner_w_at_mid: float,
) -> str:
    """Vano fronte a trapezio: lati obliqui paralleli al profilo esterno; larghezza a quota media = inner_w_at_mid."""
    h = float(height)
    k = h / 110.0
    tlx = -5.0 * k
    trx = 50.0 + 5.0 * k

    def x_l(y: float) -> float:
        return tlx * (1.0 - y / h)

    def x_r(y: float) -> float:
        return trx + (50.0 - trx) * (y / h)

    y_bot = y_top + win_h
    y_mid = (y_top + y_bot) / 2.0
    w_mid = x_r(y_mid) - x_l(y_mid)
    delta = (w_mid - inner_w_at_mid) / 2.0

    x_tl = x_l(y_top) + delta
    x_tr = x_r(y_top) - delta
    x_br = x_r(y_bot) - delta
    x_bl = x_l(y_bot) + delta
    return (
        f"M{x_tl:.4f},{y_top:.4f} L{x_tr:.4f},{y_top:.4f} "
        f"L{x_br:.4f},{y_bot:.4f} L{x_bl:.4f},{y_bot:.4f} Z"
    )


def base_outer_path_d() -> str:
    """Piatto base 44x38 mm: un solo dente maschio centrato su ogni lato."""
    w, h = BASE_INNER_W, BASE_INNER_D
    mt, _ = _single_tab_margins(w)
    mr, _ = _single_tab_margins(h)
    t0, t1 = mt, mt + TAB_WIDTH
    r0, r1 = mr, mr + TAB_WIDTH
    d = MATERIAL
    return (
        f"M 0,0 L {t0},0 L {t0},-{d} L {t1},-{d} L {t1},0 L {w},0 "
        f"L {w},{r0} L {w + d},{r0} L {w + d},{r1} L {w},{r1} L {w},{h} "
        f"L {t1},{h} L {t1},{h + d} L {t0},{h + d} L {t0},{h} L 0,{h} "
        f"L 0,{r1} L -{d},{r1} L -{d},{r0} L 0,{r0} Z"
    )


def main():
    fb = panel_front_back_with_base_bottom()
    sd = panel_side_with_base_bottom()
    print("FRONT_BACK")
    print(fb)
    print("\nSIDE")
    print(sd)
    print("\nBASE")
    print(base_outer_path_d())
    h = HEIGHT
    y_top = 30.0 * (h / 110.0)
    win_h = 50.0 * (h / 110.0)
    iw = 40.0 * (h / 110.0)
    print("\nFRONT_WINDOW_TRAP")
    print(front_window_trapezoid_path_d(h, y_top, win_h, iw))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        HEIGHT = float(sys.argv[1])
    main()
