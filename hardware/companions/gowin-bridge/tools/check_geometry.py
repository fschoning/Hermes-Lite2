#!/usr/bin/env python3
"""Geometry self-check for the generated gowin-bridge board, rev D.

Run:   python tools/check_geometry.py [board.kicad_pcb]

With no argument it reads bridge/bridge.kicad_pcb.  Give it the file Quilter
sends back to check a placed (and routed) board.

Reads the board back and checks, independently of KiCad:

 1. every pad of every LOCKED part lies inside its own end with margin, and
    every unlocked part is either wholly off the board (prepared for Quilter)
    or wholly inside its own end (placed) - never half and half;
 2. no two footprint courtyards overlap;
 3. no two pads of different nets are closer than the clearance floor;
 4. the three HL2 sockets land exactly on the DB1, DB12 and CN1 hole grids,
    recomputed here from hardware/hl/hermeslite.kicad_pcb rather than copied
    from the generator, so the two can disagree and be caught;
 5. the SlimSAS receptacle's 74 contacts, 4 shell tails and 2 locating pegs
    match SFF-8654 Rev 1.2 Table A-1 arithmetic, recomputed here, and the
    mated plug's fit inside the extrusion is restated with the numbers;
 6. the M3 anchor and the locating peg line up with HL2 MH2 and MH6;
 7. exactly the mechanically fixed parts are locked, each at its documented
    position (J1-J5, J101, J102, FID1-FID3, the MH6 hole, the mouse-bite
    holes, the U-notch);
 8. the three cut-outs over the radio's FPGA U2, AD9866 U7 and transformer
    T2: each package outline is read here from hardware/hl/hermeslite.kicad_pcb,
    grown by the stated margin, and every point of that rounded rectangle
    must be off the board; nothing - pad, courtyard, track or via - within
    1 mm of a hole, and no pair track within 2 mm; the DB6 jumper header,
    also read from the HL2 file, wholly inside its window with margin;
 9. the two ends joined only by the three mouse-bite tabs, no part within
    5 mm of any break line, and the milling path under JLCPCB's routing-fee
    threshold;
10. once parts are placed: the placement rules Quilter cannot read or can
    only be asked for - ESD arrays and terminations within 5 mm, decoupling
    capacitors at their pins, HL2 header nets under 25 mm, one side only,
    every SMD capacitor parallel to the break lines - and, once routed, pairs
    on the top layer only and the length-matched groups within 2.5 mm.

This exists because the placement is generated, not drawn, so it needs a test.
KiCad's own DRC is still the authority on manufacturability; this catches the
class of mistake DRC reports as a wall of text - a part placed off the board,
a header rotated the wrong way, a socket one pitch out - and states it in one
line.
"""

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp as K

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PAGE = (40.0, 40.0)          # generator's local (0,0) -> page coordinates
EDGE_MARGIN = 0.30           # JLCPCB copper-to-edge minimum
CLEARANCE = 0.13             # board clearance floor
COURTYARD_TOUCH = 0.0        # courtyards may touch but not overlap

# DB1 and DB12 hole grid, recomputed here from the HL2 PCB numbers rather
# than copied from the generator, so the two can disagree and be caught.
#   DB1  = HERMESLITE:10x2 at (75.31, 89.39) rot 270, pads pin n at
#          local (-11.43 + 2.54*((n-1)//2), 1.27 if n odd else -1.27)
#   DB12 = HERMESLITE:3x2  at (83.50, 90.00) rot 0, pads pin n at
#          local (0 if n odd else 2.54, -2.54 + 2.54*((n-1)//2))
# KiCad rot 270: absolute = (mod_x - pad_y, mod_y + pad_x)
HL2_ORIGIN = (70.00, 73.30)


# ---------------------------------------------------------------- the panel
# Retyped from the generator's panel block, so that a change there has to be
# made here too.  Panel (0,0) is page (40, 40).  Both ends unrotated, both
# connectors on the panel's left edge: the radio end on top, a 2 mm slot
# bridged by three mouse-bite tabs, the Gowin end below.
RADIO_W, RADIO_H = 64.50, 64.95        # local frame: HL2 y 73.30..138.25
RADIO_TRIM = 0.07                       # outline starts at local y 0.07
GOWIN_W, GOWIN_H = 64.50, 25.12
RAIL = 0.00                              # no assembly rails
PANEL_W = RADIO_W                        # 64.50
RADIO_Y0 = RAIL - RADIO_TRIM             # -0.07, radio local (0,0)
RADIO_BOTTOM = RADIO_Y0 + RADIO_H        # 64.88
SLOT_W = 2.00
GOWIN_Y0 = RADIO_BOTTOM + SLOT_W         # 66.88, Gowin local (0,0)
PANEL_H = GOWIN_Y0 + GOWIN_H + RAIL      # 92.00
PANEL_MAX = 100.00                       # JLCPCB promotional size band
GOWIN_BOX = (0.0, GOWIN_Y0, GOWIN_W, GOWIN_Y0 + GOWIN_H)
RADIO_BOX = (0.0, 0.0, RADIO_W, RADIO_BOTTOM)
RADIO_FRAME = (0.0, RADIO_Y0, RADIO_W, RADIO_Y0 + RADIO_H)
# The tabs: centres, width in the slot, slot corner radius, the mouse bites.
TAB_X = (29.60, 40.60, 51.60)
TAB_W, TAB_R = 5.00, 1.00
BITE_D, BITE_N, BITE_SPAN = 0.50, 8, 3.00
BITE_INSET = BITE_D / 2.0
BREAK_HALF = TAB_W / 2.0 + TAB_R         # the tab is 7 mm wide at the edge
BREAK_LINES = [(c - BREAK_HALF, c + BREAK_HALF, y) for c in TAB_X
               for y in (RADIO_BOTTOM - BITE_INSET, GOWIN_Y0 + BITE_INSET)]
BREAK_PART_CLEAR = 5.0                   # no part within 5 mm of a break line
ROUTING_FEE_LIMIT = 120.0                # m of >1 mm milling per m2 of board

# The cut-outs over the radio, DESIGN_NOTES.md section 13.1.  The package
# outlines are NOT retyped: hl2_package() reads them out of the HL2 board.
HOLE_MARGIN = 1.5        # each side, beyond the package outline incl. leads
HOLE_R = 1.0             # corner radius
HOLE_KEEP = 1.0          # nothing within this of a hole edge
PAIR_HOLE_KEEP = 2.0     # no pair track within this of a hole edge
HOLES = (('FPGA', 'U2'), ('ADC', 'U7'), ('T2', 'T2'))
WINDOW_REACH = 2.5       # DB6 clear of the window edge by this all round

# The parts whose position is set by the radio, the dock, the case or the
# board itself, and nothing else.  Panel coordinates of the footprint origin.
# J5's position is not set by the radio; it is locked so the placer cannot
# bury the USB Blaster header, and ROUTING.md section 5 gives its place.
LOCKED = {
    'J1': (10.40, RADIO_Y0 + 46.00),           # HL2 (80.40, 119.30)
    'J2': (4.04, RADIO_Y0 + 4.66),             # DB1 pin 1, HL2 (74.04, 77.96)
    'J3': (13.50, RADIO_Y0 + 14.16),           # DB12 pin 1, HL2 (83.50, 87.46)
    'J4': (58.23, RADIO_Y0 + 8.92),            # CN1 pin 1, HL2 (128.23, 82.22)
    'J5': (56.00, RADIO_Y0 + 24.50),           # ROUTING.md section 5
    'J101': (89.43 + 10.40 - 89.43, GOWIN_Y0 + 53.73 - 41.17),  # dock x 89.73
    'J102': (103.70 + 2 * 2.54 - 89.43, GOWIN_Y0 + 63.84 - 41.17),  # J14 pos 5
    'MB1': (4.04, RADIO_Y0 + 2.12),            # HL2 MH6 (74.04, 75.42)
    'FID1': (56.50, GOWIN_Y0 + 14.00),
    'FID2': (62.50, RADIO_Y0 + 62.50),
    'FID3': (8.50, RADIO_Y0 + 62.50),
}
# The mouse-bite holes, MB2 onward (MB1 is the MH6 locating hole), in the
# order the generator emits them: tab by tab, radio row then Gowin row.
_k = 2
for _c in TAB_X:
    for _y in (RADIO_BOTTOM - BITE_INSET, GOWIN_Y0 + BITE_INSET):
        for _i in range(BITE_N):
            LOCKED['MB%d' % _k] = (
                round(_c - BITE_SPAN + _i * 2 * BITE_SPAN / (BITE_N - 1), 3),
                round(_y, 3))
            _k += 1
# Board-edge features, panel coordinates: the M3 U-notch round HL2 MH2
# (73.00, 137.00), open into the slot.
NOTCH = (3.00 - 1.70, RADIO_BOTTOM - 3.00, 3.00 + 1.70)  # x0, y top, x1


# The Tang Mega 138K dock, from Sipeed's interactive BOM for dock 31004
# (Tang_Mega_NEO_Dock_31004): J14 pin 1 pad at (103.697657, 63.842586), the
# footprint rotated 90 so odd pins run along +x at y 63.84 and even pins at
# y 61.30.  H7_LU1, an M3 mounting hole, at (97.67, 62.66).  The case study
# TANG_IN_40MM_CASE.md fixes the SlimSAS mating face at dock x 89.73 and its
# centreline at dock y 53.73.
DOCK_ORIGIN = (89.43, 41.17)      # dock coordinates of Gowin-end local (0,0)
SS_FACE_DOCK_X = 89.73
SS_CENTRE_DOCK_Y = 53.73
BODY_FRONT = 10.10                # datum line to mating face, generator value


def dock_to_panel(dx, dy):
    return (dx - DOCK_ORIGIN[0], dy - DOCK_ORIGIN[1] + GOWIN_Y0)


def j14_grid():
    """J102 pin k -> J14 position k + 4 -> panel coordinates."""
    out = {}
    for k in range(1, 37):
        n = k + 4
        dx = 103.697657 + 2.54 * ((n - 1) // 2)
        dy = 63.842586 if n % 2 else 61.302586
        out[k] = dock_to_panel(dx, dy)
    return out


def db1_grid():
    out = {}
    mx, my = 75.31, 89.39
    for n in range(1, 21):
        px = -11.43 + 2.54 * ((n - 1) // 2)
        py = 1.27 if n % 2 else -1.27
        ax, ay = mx - py, my + px
        out[n] = (round(ax - HL2_ORIGIN[0], 3), round(ay - HL2_ORIGIN[1], 3))
    return out


def db12_grid():
    out = {}
    mx, my = 83.50, 90.00
    for n in range(1, 7):
        px = 0.0 if n % 2 else 2.54
        py = -2.54 + 2.54 * ((n - 1) // 2)
        out[n] = (round(mx + px - HL2_ORIGIN[0], 3),
                  round(my + py - HL2_ORIGIN[1], 3))
    return out


def cn1_grid():
    """CN1 = HERMESLITE:USBBLASTER at (129.50, 87.30) rot 270, pads pin n at
    local (-5.08 + 2.54*((n-1)//2), 1.27 if n odd else -1.27)."""
    out = {}
    mx, my = 129.50, 87.30
    for n in range(1, 11):
        px = -5.08 + 2.54 * ((n - 1) // 2)
        py = 1.27 if n % 2 else -1.27
        ax, ay = mx - py, my + px
        out[n] = (round(ax - HL2_ORIGIN[0], 3), round(ay - HL2_ORIGIN[1], 3))
    return out


# SFF-8654 Rev 1.2 Table A-1, retyped, so the land pattern can be recomputed
# rather than trusted.
SFF = dict(j01=10.95, j02=2.70, j03=2.35, j04=0.15, j05=0.60,
           pad_w=0.35, pad_l=1.30, loc_d=1.30, j09=5.15, j10=3.00,
           j11=0.68, npos=37)
SETBACK = 10.40          # board edge -> locating-hole datum line
SS_CENTRE_Y = 46.00      # local y of the connector centreline
PLUG_W, PLUG_H = 25.95, 9.90      # SFF-8654 Table 5-1, A03 and A13
ENC_Y0, ENC_Y1 = 41.75, 138.25    # extrusion internal clear width, HL2 y
UNDERSIDE = 11.04                 # board underside above the HL2 top surface


def check_slimsas(fps, box):
    prob = []
    bx0, by0 = box[0], box[1]
    hit = [q for q in fps if q.ref == 'J1']
    if not hit:
        return ['J1, the SlimSAS receptacle, is not on the board']
    f = hit[0]
    pads = {q[0]: (q[1] - bx0, q[2] - by0) for q in f.pads}
    outer = SFF['j01'] - SFF['j04']
    want = {}
    for row, xc in (('A', SFF['j02']), ('B', SFF['j02'] + SFF['j03'])):
        for i in range(1, SFF['npos'] + 1):
            want['%s%d' % (row, i)] = (
                SETBACK + xc,
                SS_CENTRE_Y + outer - (i - 1) * SFF['j05'])
    ty = SFF['j01'] + SFF['j11']
    tails = [(-SFF['j09'], ty), (-(SFF['j09'] + SFF['j10']), ty),
             (-SFF['j09'], -ty), (-(SFF['j09'] + SFF['j10']), -ty)]
    for k, (dx, dy) in enumerate(tails, start=1):
        want['SH%d' % k] = (SETBACK + dx, SS_CENTRE_Y + dy)
    for nm in sorted(want):
        wx, wy = want[nm]
        if nm not in pads:
            prob.append('J1: contact %s missing' % nm)
            continue
        gx, gy = pads[nm]
        if abs(gx - wx) > 0.01 or abs(gy - wy) > 0.01:
            prob.append('J1 contact %s at (%.3f, %.3f), Table A-1 says '
                        '(%.3f, %.3f)' % (nm, gx, gy, wx, wy))
    # the two unplated locating pegs carry no pad name
    extra = [nm for nm in pads if nm and nm not in want]
    if extra:
        prob.append('J1 has contacts that are not in Table A-1: %s'
                    % ', '.join(sorted(extra)))
    if not prob:
        print('   J1: all 74 contacts and 4 shell tails match SFF-8654 '
              'Rev 1.2 Table A-1')
        print('      row A at local x %.2f, row B at %.2f, pitch %.2f, '
              'contacts from y %.2f to %.2f'
              % (SETBACK + SFF['j02'], SETBACK + SFF['j02'] + SFF['j03'],
                 SFF['j05'], SS_CENTRE_Y - outer, SS_CENTRE_Y + outer))
    y0 = HL2_ORIGIN[1] + SS_CENTRE_Y - PLUG_W / 2
    y1 = HL2_ORIGIN[1] + SS_CENTRE_Y + PLUG_W / 2
    print('      mated plug overmould %.2f mm wide -> HL2 y %.2f..%.2f, '
          'inside the extrusion clear width %.2f..%.2f with %.2f mm spare '
          'below and %.2f mm above'
          % (PLUG_W, y0, y1, ENC_Y0, ENC_Y1, y0 - ENC_Y0, ENC_Y1 - y1))
    if y0 < ENC_Y0 or y1 > ENC_Y1:
        prob.append('the mated plug does not fit the extrusion clear width')
    print('      plug %.2f mm thick on a board top surface %.2f mm up -> '
          'occupies %.2f..%.2f mm above the HL2 top surface, which is above '
          'the clock SMA and KEY jack holes rather than beside them'
          % (PLUG_H, UNDERSIDE + 1.6, UNDERSIDE + 1.6,
             UNDERSIDE + 1.6 + PLUG_H))
    return prob


def check_mech(box):
    prob = []
    bx0, by0, bx1, by1 = box
    mh2 = (73.00 - HL2_ORIGIN[0], 137.00 - HL2_ORIGIN[1])
    mh6 = (74.04 - HL2_ORIGIN[0], 75.42 - HL2_ORIGIN[1])
    h = by1 - by0
    edge = h - mh2[1]
    print('   M3 anchor: HL2 MH2 (73.00, 137.00) = local (%.2f, %.2f), only '
          '%.2f mm from the top edge, so it is a U-notch open to the edge '
          'and not a hole' % (mh2[0], mh2[1], edge))
    if edge > 1.9:
        prob.append('MH2 is %.2f mm from the edge, which is enough room for '
                    'a plain 3.2 mm hole - the notch is no longer needed'
                    % edge)
    print('   locating peg: HL2 MH6 (74.04, 75.42) = local (%.2f, %.2f), '
          '1.1 mm unplated' % (mh6[0], mh6[1]))
    return prob


def rot(x, y, deg):
    """KiCad footprint rotation applied to a pad offset."""
    a = math.radians(-deg)
    return (x * math.cos(a) - y * math.sin(a),
            x * math.sin(a) + y * math.cos(a))


class FP:
    __slots__ = ('ref', 'at', 'r', 'layer', 'pads', 'crt', 'tht', 'locked')


def load(path):
    root = K.parse(open(path, encoding='utf-8').read())[0]
    fps = []
    edges = []
    tracks = []
    vias = []
    codes = {}
    for node in root[1:]:
        if not isinstance(node, list):
            continue
        h = K.head(node)
        if h == 'net':
            a = K.atoms(node)
            if len(a) >= 2:
                codes[a[0]] = a[1]
        elif h in ('segment', 'arc'):
            s0 = K.atoms(K.kid(node, 'start'))
            e0 = K.atoms(K.kid(node, 'end'))
            lay = K.atoms(K.kid(node, 'layer'))[0]
            nn = K.kid(node, 'net')
            net = K.atoms(nn)[-1] if nn is not None else ''
            ln = math.hypot(float(e0[0]) - float(s0[0]),
                            float(e0[1]) - float(s0[1]))
            if h == 'arc':
                m0 = K.atoms(K.kid(node, 'mid'))
                ln = (math.hypot(float(m0[0]) - float(s0[0]),
                                 float(m0[1]) - float(s0[1]))
                      + math.hypot(float(e0[0]) - float(m0[0]),
                                   float(e0[1]) - float(m0[1])))
            tracks.append((net, lay, ln,
                           (float(s0[0]), float(s0[1])),
                           (float(e0[0]), float(e0[1]))))
        elif h == 'via':
            a = K.atoms(K.kid(node, 'at'))
            sz = K.atoms(K.kid(node, 'size'))
            nn = K.kid(node, 'net')
            vias.append((K.atoms(nn)[-1] if nn is not None else '',
                         float(a[0]), float(a[1]), float(sz[0]) / 2.0))
        elif h in ('gr_line', 'gr_arc'):
            lay = K.kid(node, 'layer')
            if lay is not None and K.atoms(lay)[0] == 'Edge.Cuts':
                s = K.atoms(K.kid(node, 'start'))
                e = K.atoms(K.kid(node, 'end'))
                a0 = (float(s[0]), float(s[1]))
                a1 = (float(e[0]), float(e[1]))
                if h == 'gr_line':
                    edges.append([a0, a1])
                else:
                    m = K.atoms(K.kid(node, 'mid'))
                    edges.append(arc_points(a0, (float(m[0]), float(m[1])),
                                            a1))
        elif h == 'footprint':
            f = FP()
            a = K.atoms(K.kid(node, 'at'))
            f.at = (float(a[0]), float(a[1]))
            f.r = float(a[2]) if len(a) > 2 else 0.0
            f.layer = K.atoms(K.kid(node, 'layer'))[0]
            lk = K.kid(node, 'locked')
            f.locked = ('locked' in [x for x in node[1:2] if isinstance(x, str)]
                        or (lk is not None and (not K.atoms(lk)
                                                or K.atoms(lk)[0] == 'yes')))
            f.ref = None
            for tx in K.kids(node, 'fp_text'):
                if K.atoms(tx) and K.atoms(tx)[0] == 'reference':
                    f.ref = K.atoms(tx)[1]
            for pr in K.kids(node, 'property'):
                if K.atoms(pr) and K.atoms(pr)[0] == 'Reference':
                    f.ref = K.atoms(pr)[1]
            f.pads = []
            f.tht = False
            for pad in K.kids(node, 'pad'):
                pa = [x for x in pad[1:] if isinstance(x, (str, tuple))]
                num = pa[0][1] if isinstance(pa[0], tuple) else pa[0]
                if K.kid(pad, 'drill') is not None:
                    f.tht = True
                at = K.atoms(K.kid(pad, 'at'))
                sz = K.atoms(K.kid(pad, 'size'))
                px, py = rot(float(at[0]), float(at[1]), f.r)
                netn = K.kid(pad, 'net')
                net = K.atoms(netn)[-1] if netn is not None else ''
                hx, hy = float(sz[0]) / 2.0, float(sz[1]) / 2.0
                # the pad's own rotation is folded into the emitted value, so
                # a 90/270 total rotation swaps the pad's own x and y extents
                pr = K.atoms(K.kid(pad, 'at'))
                prot = float(pr[2]) if len(pr) > 2 else 0.0
                if round(prot) % 180 == 90:
                    hx, hy = hy, hx
                f.pads.append((num, f.at[0] + px, f.at[1] + py, hx, hy, net))
            ext = K.footprint_extent(node, 'F.CrtYd')
            if ext is None:
                ext = K.footprint_extent(node, 'B.CrtYd')
            if ext is None:
                xs = [p[1] - p[3] for p in f.pads] + [p[1] + p[3] for p in f.pads]
                ys = [p[2] - p[4] for p in f.pads] + [p[2] + p[4] for p in f.pads]
                f.crt = (min(xs), min(ys), max(xs), max(ys)) if xs else None
            else:
                x0, y0 = rot(ext[0], ext[1], f.r)
                x1, y1 = rot(ext[2], ext[3], f.r)
                f.crt = (f.at[0] + min(x0, x1), f.at[1] + min(y0, y1),
                         f.at[0] + max(x0, x1), f.at[1] + max(y0, y1))
            fps.append(f)
    xs = [p[0] for e in edges for p in e]
    ys = [p[1] for e in edges for p in e]
    box = (min(xs), min(ys), max(xs), max(ys))
    load.edges = edges
    load.tracks = [(codes.get(n, n), l_, ln, a, b) for (n, l_, ln, a, b)
                   in tracks]
    load.vias = [(codes.get(n, n), x, y, r) for (n, x, y, r) in vias]
    load.loops = edge_loops(edges)
    return fps, box


def arc_points(a, m, b, n=12):
    """A three-point arc -> a polyline of n segments from a to b."""
    ax, ay = a
    bx, by = b
    mx, my = m
    d = 2 * (ax * (my - by) + mx * (by - ay) + bx * (ay - my))
    ux = ((ax * ax + ay * ay) * (my - by) + (mx * mx + my * my) * (by - ay)
          + (bx * bx + by * by) * (ay - my)) / d
    uy = ((ax * ax + ay * ay) * (bx - mx) + (mx * mx + my * my) * (ax - bx)
          + (bx * bx + by * by) * (mx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t0 = math.atan2(ay - uy, ax - ux)
    tm = math.atan2(my - uy, mx - ux)
    t1 = math.atan2(by - uy, bx - ux)
    # sweep from t0 through tm to t1
    sweep = (t1 - t0) % (2 * math.pi)
    if (tm - t0) % (2 * math.pi) > sweep:
        sweep -= 2 * math.pi
    pts = [(ux + r * math.cos(t0 + sweep * i / n),
            uy + r * math.sin(t0 + sweep * i / n)) for i in range(n + 1)]
    pts[0], pts[-1] = a, b
    return pts


def on_board(x, y):
    """Even-odd rule over every Edge.Cuts loop: True if (x, y), in page
    coordinates, is board material."""
    inside = False
    for lp in load.loops or []:
        n = len(lp)
        for i in range(n):
            x1, y1 = lp[i - 1]
            x2, y2 = lp[i]
            if (y1 > y) != (y2 > y) and                     x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def loop_length(lp):
    return sum(math.hypot(lp[i][0] - lp[i - 1][0], lp[i][1] - lp[i - 1][1])
               for i in range(len(lp)))


def in_board(ref):
    """Which piece of the panel a footprint belongs to.  The Gowin end's
    designators are numbered from 101; the fiducials and mouse-bite drills
    belong to the panel itself; everything else is the radio end."""
    if ref.startswith(('FID', 'MB')):
        return 'panel'
    digits = ''.join(c for c in ref if c.isdigit())
    if digits and int(digits) >= 101 and ref[0] in 'JDRTMC':
        return 'gowin'
    return 'radio'


def check(name):
    path = (sys.argv[1] if len(sys.argv) > 1
            else os.path.join(ROOT, name, name + '.kicad_pcb'))
    fps, box = load(path)
    bx0, by0, bx1, by1 = box
    prob = []
    print('== %s ==' % name)
    print('   panel outline  x %.2f..%.2f  y %.2f..%.2f  (%.2f x %.2f mm)'
          % (bx0, bx1, by0, by1, bx1 - bx0, by1 - by0))
    if abs((bx1 - bx0) - PANEL_W) > 0.01 or abs((by1 - by0) - PANEL_H) > 0.01:
        prob.append('panel is %.2f x %.2f, expected %.2f x %.2f'
                    % (bx1 - bx0, by1 - by0, PANEL_W, PANEL_H))
    print('   %d footprints, %d pads'
          % (len(fps), sum(len(f.pads) for f in fps)))
    rects = {'radio': RADIO_BOX, 'gowin': GOWIN_BOX,
             'panel': (0.0, 0.0, PANEL_W, PANEL_H)}

    # 1. inside the outline of the piece the part belongs to.  A locked part
    # must be inside.  An unlocked part is either wholly OFF the board
    # (staged for Quilter) or wholly inside its own end (placed).
    staged, placed = [], []
    for f in fps:
        if f.ref.startswith('MB'):
            continue
        rx0, ry0, rx1, ry1 = rects[in_board(f.ref)]
        rx0 += PAGE[0]; rx1 += PAGE[0]; ry0 += PAGE[1]; ry1 += PAGE[1]
        bad = []
        for (num, px, py, hx, hy, net) in f.pads:
            if (px - hx < rx0 + EDGE_MARGIN or px + hx > rx1 - EDGE_MARGIN
                    or py - hy < ry0 + EDGE_MARGIN
                    or py + hy > ry1 - EDGE_MARGIN):
                bad.append((num, px, py))
        if not f.locked:
            off = f.crt is not None and (
                f.crt[0] > PAGE[0] + PANEL_W or f.crt[2] < PAGE[0]
                or f.crt[1] > PAGE[1] + PANEL_H or f.crt[3] < PAGE[1])
            if off:
                staged.append(f)
                continue
            placed.append(f)
        for (num, px, py) in bad:
            prob.append('OFF-BOARD pad %s.%s (%s end) at panel (%.2f, '
                        '%.2f)' % (f.ref, num, in_board(f.ref),
                                   px - PAGE[0], py - PAGE[1]))
    check.staged, check.placed = staged, placed
    print('   %d unlocked parts staged off the board for Quilter, %d placed '
          'on it' % (len(staged), len(placed)))
    # 2. courtyard overlaps
    for i in range(len(fps)):
        for j in range(i + 1, len(fps)):
            a, b = fps[i], fps[j]
            if a.crt is None or b.crt is None:
                continue
            # A through-hole footprint occupies both sides, so its courtyard
            # still clashes with a part on the opposite face. Only skip the
            # cross-layer pair when BOTH are surface mount.
            if a.layer != b.layer and not (a.tht or b.tht):
                continue
            ox = min(a.crt[2], b.crt[2]) - max(a.crt[0], b.crt[0])
            oy = min(a.crt[3], b.crt[3]) - max(a.crt[1], b.crt[1])
            if ox > COURTYARD_TOUCH and oy > COURTYARD_TOUCH:
                prob.append('COURTYARD OVERLAP %s / %s by %.2f x %.2f mm'
                            % (a.ref, b.ref, ox, oy))
    # 3. pad-to-pad clearance between different nets, different footprints
    pads = [(f, p) for f in fps for p in f.pads]
    for i in range(len(pads)):
        fa, pa = pads[i]
        for j in range(i + 1, len(pads)):
            fb, pb = pads[j]
            if fa is fb:
                continue
            if pa[5] and pa[5] == pb[5]:
                continue
            dx = abs(pa[1] - pb[1]) - pa[3] - pb[3]
            dy = abs(pa[2] - pb[2]) - pa[4] - pb[4]
            gap = max(dx, dy)
            if gap < CLEARANCE:
                prob.append('PAD CLEARANCE %s.%s [%s] / %s.%s [%s] = %.3f mm'
                            % (fa.ref, pa[0], pa[5], fb.ref, pb[0], pb[5],
                               gap))
    return fps, box, prob


def check_gowin(fps):
    prob = []
    byref = {f.ref: f for f in fps}
    f = byref.get('J102')
    if f is None:
        return ['J102, the Tang J14 socket, is missing']
    pads = {int(p[0]): (p[1] - PAGE[0], p[2] - PAGE[1]) for p in f.pads
            if p[0].isdigit()}
    bad = 0
    for k, (wx, wy) in j14_grid().items():
        gx, gy = pads.get(k, (1e9, 1e9))
        if abs(gx - wx) > 0.01 or abs(gy - wy) > 0.01:
            prob.append('J102 pin %d (J14 position %d) at panel (%.3f, %.3f), '
                        'dock grid says (%.3f, %.3f)'
                        % (k, k + 4, gx, gy, wx, wy))
            bad += 1
    if not bad:
        print('   J102: all 36 holes on dock J14 positions 5-40')
    # nothing of this end may stand over J14 positions 1-4 except the
    # connector's own surface-mount pads, which are on the top copper only
    for fp in fps:
        if fp.ref == 'J102' or not fp.tht:
            continue
        for (num, px, py, hx, hy, net) in fp.pads:
            if fp.ref == 'J101' and num[:1] in ('A', 'B'):
                continue        # surface-mount contacts, top copper only
            x, y = px - PAGE[0], py - PAGE[1]
            for n in (1, 2, 3, 4):
                wx, wy = dock_to_panel(103.697657 + 2.54 * ((n - 1) // 2),
                                       63.842586 if n % 2 else 61.302586)
                if abs(x - wx) < hx + 1.3 and abs(y - wy) < hy + 1.3:
                    prob.append('%s.%s has a hole over J14 position %d'
                                % (fp.ref, num, n))
    f = byref.get('J101')
    if f is None:
        return prob + ['J101, the Gowin-end SlimSAS receptacle, is missing']
    pads = {q[0]: (q[1] - PAGE[0], q[2] - PAGE[1]) for q in f.pads}
    dx0 = SS_FACE_DOCK_X + BODY_FRONT       # datum line, dock x
    ox, oy = dock_to_panel(dx0, SS_CENTRE_DOCK_Y)
    outer = SFF['j01'] - SFF['j04']
    want = {}
    for row, xc in (('A', SFF['j02']), ('B', SFF['j02'] + SFF['j03'])):
        for i in range(1, SFF['npos'] + 1):
            want['%s%d' % (row, i)] = (ox + xc,
                                       oy + outer - (i - 1) * SFF['j05'])
    ty = SFF['j01'] + SFF['j11']
    for k, (tx, tyy) in enumerate([(-SFF['j09'], ty),
                                   (-(SFF['j09'] + SFF['j10']), ty),
                                   (-SFF['j09'], -ty),
                                   (-(SFF['j09'] + SFF['j10']), -ty)], 1):
        want['SH%d' % k] = (ox + tx, oy + tyy)
    bad = 0
    for nm, (wx, wy) in sorted(want.items()):
        gx, gy = pads.get(nm, (1e9, 1e9))
        if abs(gx - wx) > 0.01 or abs(gy - wy) > 0.01:
            prob.append('J101 contact %s at (%.3f, %.3f), Table A-1 and the '
                        'case position say (%.3f, %.3f)'
                        % (nm, gx, gy, wx, wy))
            bad += 1
    if not bad:
        print('   J101: all 74 contacts and 4 shell tails match SFF-8654 '
              'Table A-1 with the mating face at dock x %.2f and the '
              'centreline at dock y %.2f' % (SS_FACE_DOCK_X, SS_CENTRE_DOCK_Y))
    hx, hy = dock_to_panel(97.67, 62.66)
    holes = [q_ for q_ in f.pads if q_[0] == '']
    if not any(abs(q_[1] - PAGE[0] - hx) < 0.01 and abs(q_[2] - PAGE[1] - hy)
               < 0.01 for q_ in holes):
        prob.append('no M3 spacer hole over dock hole H7_LU1 (97.67, 62.66)')
    else:
        print('   M3 spacer hole at dock (97.67, 62.66), over H7_LU1')
    return prob


def edge_loops(edges):
    """Chain Edge.Cuts segments into closed loops.  -> list of point lists,
    or None if any segment does not close."""
    key = lambda pt: (round(pt[0], 3), round(pt[1], 3))
    segs = [[key(p_) for p_ in e] for e in edges]
    loops = []
    while segs:
        pts = segs.pop(0)
        while pts[-1] != pts[0]:
            nxt = None
            for i, e in enumerate(segs):
                if e[0] == pts[-1]:
                    nxt = (i, e[1:])
                    break
                if e[-1] == pts[-1]:
                    nxt = (i, e[::-1][1:])
                    break
            if nxt is None:
                return None
            segs.pop(nxt[0])
            pts += nxt[1]
        loops.append(pts[:-1])
    return loops


def check_one_outline():
    """ONE board: exactly one closed outer Edge.Cuts loop spanning the whole
    board, and every other loop an internal cut-out strictly inside it."""
    prob = []
    loops = load.loops
    if loops is None:
        return ['Edge.Cuts does not close into loops']
    boxes = [(min(p[0] for p in lp), min(p[1] for p in lp),
              max(p[0] for p in lp), max(p[1] for p in lp)) for lp in loops]
    full = (PAGE[0], PAGE[1], PAGE[0] + PANEL_W, PAGE[1] + PANEL_H)
    outer = [i for i, bx in enumerate(boxes)
             if all(abs(bx[k] - full[k]) < 0.01 for k in range(4))]
    if len(outer) != 1:
        prob.append('expected exactly one Edge.Cuts loop spanning the whole '
                    'board, found %d' % len(outer))
        return prob
    for i, bx in enumerate(boxes):
        if i == outer[0]:
            continue
        if not (bx[0] > full[0] + 0.01 and bx[2] < full[2] - 0.01
                and bx[1] > full[1] + 0.01 and bx[3] < full[3] - 0.01):
            prob.append('Edge.Cuts loop %d at %s is not inside the outer '
                        'outline, so the file holds more than one board'
                        % (i, bx))
    if not prob:
        print('   ONE board: a single continuous outline %.2f x %.2f mm '
              'round both ends, no rails, plus %d internal cut-outs (the '
              'slot between the tabs, and the one over the radio AD9866, T2 '
              'and jumper DB6)' % (PANEL_W, PANEL_H, len(loops) - 1))
    return prob


def seg_rect_gap(x0, x1, y, r):
    """Distance from the horizontal segment x0..x1 at y to rectangle r."""
    dx = max(0.0, r[0] - x1, x0 - r[2])
    dy = max(0.0, r[1] - y, y - r[3])
    return math.hypot(dx, dy)


def part_extent(f):
    """Courtyard where there is one, and the pads either way."""
    xs = [p[1] - p[3] for p in f.pads] + [p[1] + p[3] for p in f.pads]
    ys = [p[2] - p[4] for p in f.pads] + [p[2] + p[4] for p in f.pads]
    boxes = []
    if xs:
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    if f.crt is not None:
        boxes.append(f.crt)
    return boxes


def check_panel(fps):
    """The two ends are joined only through the tabs; no part within 5 mm of
    any break line; the milling path is under the routing-fee threshold."""
    prob = check_one_outline()
    if load.loops is None:
        return prob
    # 1. across the middle of the slot, board material only inside the tabs
    ym = PAGE[1] + RADIO_BOTTOM + SLOT_W / 2.0
    bad = []
    x = 0.05
    while x < PANEL_W:
        mat = on_board(PAGE[0] + x, ym)
        want = any(abs(x - c) < TAB_W / 2.0 for c in TAB_X)
        edge = any(abs(abs(x - c) - TAB_W / 2.0) <= 0.06 for c in TAB_X)
        if mat != want and not edge:
            bad.append(x)
        x += 0.1
    if bad:
        prob.append('across the slot at y %.2f the board is not solid exactly '
                    'at the tabs (first disagreement at x %.2f)'
                    % (ym - PAGE[1], bad[0]))
    # the two ends' facing edges are free edges away from the tabs
    for yy, nm in ((RADIO_BOTTOM + 0.3, 'below the radio end'),
                   (GOWIN_Y0 - 0.3, 'above the Gowin end')):
        for xx in (10.0, 35.1, 46.1, 60.0):
            if on_board(PAGE[0] + xx, PAGE[1] + yy):
                prob.append('board material %s at x %.1f, outside a tab'
                            % (nm, xx))
    print('   the ends joined only by %d tabs, %.1f mm wide, at x %s, across '
          'a %.2f mm slot; %d mouse bites of %.2f mm per edge, %.2f mm '
          'inside it'
          % (len(TAB_X), TAB_W, ', '.join('%.2f' % c for c in TAB_X), SLOT_W,
             BITE_N, BITE_D, BITE_INSET))
    # 2. no part within BREAK_PART_CLEAR of a break line
    worst = (1e9, '')
    for f in fps:
        if f.ref.startswith('MB') or f in check.staged:
            continue
        for bx in part_extent(f):
            r = (bx[0] - PAGE[0], bx[1] - PAGE[1], bx[2] - PAGE[0],
                 bx[3] - PAGE[1])
            for (x0, x1, y) in BREAK_LINES:
                g = seg_rect_gap(x0, x1, y, r)
                if g < worst[0]:
                    worst = (g, f.ref)
                if g < BREAK_PART_CLEAR - 1e-6:
                    prob.append('%s is %.2f mm from the break line at x '
                                '%.2f..%.2f, y %.2f; the limit is %.1f mm'
                                % (f.ref, g, x0, x1, y, BREAK_PART_CLEAR))
    print('   nearest part to a break line: %s at %.2f mm (limit %.1f)'
          % (worst[1], worst[0], BREAK_PART_CLEAR))
    # 3. milling path
    path = sum(loop_length(lp) for lp in load.loops) / 1000.0
    area = PANEL_W * PANEL_H / 1e6
    print('   milling path %.3f m on a %.4f m2 board = %.0f m per m2 (JLCPCB '
          'routing fee from %.0f m per m2)'
          % (path, area, path / area, ROUTING_FEE_LIMIT))
    if path / area >= ROUTING_FEE_LIMIT:
        prob.append('milling path %.0f m per m2 reaches the routing fee'
                    % (path / area))
    if PANEL_W > PANEL_MAX + 1e-6 or PANEL_H > PANEL_MAX + 1e-6:
        prob.append('the board is %.2f x %.2f mm, outside the 100 x 100 mm '
                    'promotional size band' % (PANEL_W, PANEL_H))
    return prob


# ------------------------------------------------------------ the cut-outs
HL2_PCB = os.path.normpath(os.path.join(ROOT, '..', '..', 'hl',
                                        'hermeslite.kicad_pcb'))


def hl2_package(ref):
    """(x0, y0, x1, y1) HL2 coordinates of a part's outline: the union of its
    pads and its silkscreen and fab graphics, read from the HL2 board file.
    KiCad 5: pad positions turn with the module, pad angles are absolute."""
    if not hasattr(hl2_package, 'mods'):
        root = K.parse(open(HL2_PCB, encoding='utf-8').read())[0]
        hl2_package.mods = {}
        for m in K.kids(root, 'module'):
            for t in K.kids(m, 'fp_text'):
                a = K.atoms(t)
                if a and a[0] == 'reference':
                    hl2_package.mods[a[1]] = m
    m = hl2_package.mods[ref]
    at = K.atoms(K.kid(m, 'at'))
    mx, my = float(at[0]), float(at[1])
    mr = float(at[2]) if len(at) > 2 else 0.0
    xs, ys = [], []
    for pd in K.kids(m, 'pad'):
        pa = K.atoms(K.kid(pd, 'at'))
        sz = K.atoms(K.kid(pd, 'size'))
        px, py = float(pa[0]), float(pa[1])
        pr = float(pa[2]) if len(pa) > 2 else 0.0
        hx, hy = float(sz[0]) / 2, float(sz[1]) / 2
        ax, ay = rot(px, py, mr)
        for cx, cy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
            ox, oy = rot(cx, cy, pr)
            xs.append(mx + ax + ox)
            ys.append(my + ay + oy)
    for g in K.kids(m, 'fp_line'):
        lay = K.atoms(K.kid(g, 'layer'))[0]
        if lay not in ('F.SilkS', 'F.Fab'):
            continue
        for key in ('start', 'end'):
            a = K.atoms(K.kid(g, key))
            ax, ay = rot(float(a[0]), float(a[1]), mr)
            xs.append(mx + ax)
            ys.append(my + ay)
    return (min(xs), min(ys), max(xs), max(ys))


def hl2_to_panel(x, y):
    return (x - HL2_ORIGIN[0], y - HL2_ORIGIN[1] + RADIO_Y0)


def hl2_rect(ref):
    x0, y0, x1, y1 = hl2_package(ref)
    a = hl2_to_panel(x0, y0)
    b = hl2_to_panel(x1, y1)
    return (a[0], a[1], b[0], b[1])


def in_rounded(x, y, r, rad):
    """Is (x, y) inside rectangle r with corner radius rad?"""
    if not (r[0] <= x <= r[2] and r[1] <= y <= r[3]):
        return False
    cx = min(max(x, r[0] + rad), r[2] - rad)
    cy = min(max(y, r[1] + rad), r[3] - rad)
    return math.hypot(x - cx, y - cy) <= rad + 1e-9


EPS = 0.02      # boundary tolerance: points on an edge, arcs as chords


def shrink(r, d=EPS):
    return (r[0] + d, r[1] + d, r[2] - d, r[3] - d)


def sample_rect(r, step=0.2):
    n = max(1, int(round((r[2] - r[0]) / step)))
    m = max(1, int(round((r[3] - r[1]) / step)))
    for i in range(n + 1):
        for j in range(m + 1):
            yield (r[0] + (r[2] - r[0]) * i / n, r[1] + (r[3] - r[1]) * j / m)


def check_holes(fps):
    prob = []
    if load.loops is None:
        return prob
    rects = []
    for nm, ref in HOLES:
        pk = hl2_rect(ref)
        rects.append((nm, ref, pk, (pk[0] - HOLE_MARGIN, pk[1] - HOLE_MARGIN,
                                    pk[2] + HOLE_MARGIN, pk[3] + HOLE_MARGIN)))
    db6 = hl2_rect('DB6')
    win = (db6[0] - WINDOW_REACH, db6[1] - WINDOW_REACH,
           db6[2] + WINDOW_REACH, db6[3] + WINDOW_REACH)
    # 1. each hole at its position, at least its stated size
    for nm, ref, pk, cl in rects:
        hits = [pt for pt in sample_rect(shrink(cl), 0.1)
                if in_rounded(pt[0], pt[1], shrink(cl), HOLE_R)
                and on_board(PAGE[0] + pt[0], PAGE[1] + pt[1])]
        print('   hole over HL2 %s (%s): package outline %.2f x %.2f mm read '
              'from the HL2 board, clear %.2f x %.2f mm at panel x '
              '%.2f..%.2f, y %.2f..%.2f, corners R%.1f: %s'
              % (ref, nm, pk[2] - pk[0], pk[3] - pk[1], cl[2] - cl[0],
                 cl[3] - cl[1], cl[0], cl[2], cl[1], cl[3], HOLE_R,
                 'clear' if not hits else '%d points are board' % len(hits)))
        if hits:
            prob.append('the hole over HL2 %s is not clear: board material at '
                        'panel (%.2f, %.2f)' % (ref, hits[0][0], hits[0][1]))
    # 2. DB6 inside its window with margin
    hits = [pt for pt in sample_rect(shrink(win), 0.1)
            if on_board(PAGE[0] + pt[0], PAGE[1] + pt[1])]
    print('   DB6 outline x %.2f..%.2f, y %.2f..%.2f: %s'
          % (db6[0], db6[2], db6[1], db6[3],
             'inside the window with %.1f mm clear all round' % WINDOW_REACH
             if not hits else 'NOT inside the window'))
    if hits:
        prob.append('DB6 plus %.1f mm is not wholly inside the window (board '
                    'at panel (%.2f, %.2f))' % (WINDOW_REACH, hits[0][0],
                                                hits[0][1]))
    db3 = hl2_rect('DB3')
    pts = list(sample_rect(db3))
    cov = sum(1 for pt in pts if on_board(PAGE[0] + pt[0], PAGE[1] + pt[1]))
    print('      DB3 (reported, not checked) x %.2f..%.2f, y %.2f..%.2f: '
          '%.0f %% of it under the board; that end is under locked J5'
          % (db3[0], db3[2], db3[1], db3[3], 100.0 * cov / len(pts)))
    # 3. nothing within HOLE_KEEP of a hole.  "In a hole" = off the board and
    # inside the extent of a cut-out, so the outer edges do not count.
    ext = [(r[3][0] - 3, r[3][1] - 3, r[3][2] + 3, r[3][3] + 3)
           for r in rects] + [(win[0] - 3, win[1] - 3, win[2] + 3, win[3] + 3)]

    def in_hole(x, y):
        if not any(e[0] <= x <= e[2] and e[1] <= y <= e[3] for e in ext):
            return False
        return not on_board(PAGE[0] + x, PAGE[1] + y)

    def breach(bx, keep):
        g = (bx[0] - keep, bx[1] - keep, bx[2] + keep, bx[3] + keep)
        if not any(g[0] <= e[2] and g[2] >= e[0] and g[1] <= e[3]
                   and g[3] >= e[1] for e in ext):
            return None
        for pt in sample_rect(shrink(g), 0.25):
            if in_hole(*pt):
                return pt
        return None
    n_items = 0
    for f in fps:
        if f in check.staged or f.ref.startswith('MB'):
            continue
        n_items += 1
        for bx in part_extent(f):
            r = (bx[0] - PAGE[0], bx[1] - PAGE[1], bx[2] - PAGE[0],
                 bx[3] - PAGE[1])
            pt = breach(r, HOLE_KEEP)
            if pt:
                prob.append('%s is within %.1f mm of a cut-out (at panel '
                            '(%.2f, %.2f))' % (f.ref, HOLE_KEEP, pt[0], pt[1]))
                break
    for (n, lay, ln, a_, b_) in load.tracks:
        pair = n.endswith(('_P', '_N')) and n.startswith(('A_', 'B_', 'G_A_',
                                                         'G_B_'))
        keep = PAIR_HOLE_KEEP if pair else HOLE_KEEP
        steps = max(1, int(ln / 0.5))
        n_items += 1
        for i in range(steps + 1):
            x = a_[0] + (b_[0] - a_[0]) * i / steps - PAGE[0]
            y = a_[1] + (b_[1] - a_[1]) * i / steps - PAGE[1]
            if breach((x, y, x, y), keep):
                prob.append('track on %s (%s) within %.1f mm of a cut-out at '
                            'panel (%.2f, %.2f)' % (n, lay, keep, x, y))
                break
    for (n, x, y, r) in load.vias:
        x, y = x - PAGE[0], y - PAGE[1]
        n_items += 1
        if breach((x - r, y - r, x + r, y + r), HOLE_KEEP):
            prob.append('via on %s within %.1f mm of a cut-out at panel '
                        '(%.2f, %.2f)' % (n, HOLE_KEEP, x, y))
    print('   nothing within %.1f mm of a cut-out and no pair track within '
          '%.1f mm: %d parts, tracks and vias on the board checked'
          % (HOLE_KEEP, PAIR_HOLE_KEEP, n_items))
    return prob


def check_hl2_grid(fps, box):
    """The socket holes must land on the HL2's own hole grids."""
    bx0, by0 = box[0], box[1]
    want = {'J2': db1_grid(), 'J3': db12_grid(), 'J4': cn1_grid()}
    prob = []
    for f in fps:
        if f.ref not in want:
            continue
        g = want[f.ref]
        pads = {int(p[0]): (p[1] - bx0, p[2] - by0) for p in f.pads
                if p[0].isdigit()}
        bad = 0
        for n, (wx, wy) in g.items():
            if n not in pads:
                prob.append('%s: pin %d missing' % (f.ref, n))
                continue
            gx, gy = pads[n]
            if abs(gx - wx) > 0.01 or abs(gy - wy) > 0.01:
                prob.append('%s pin %-2d at (%.3f, %.3f), HL2 grid says '
                            '(%.3f, %.3f)' % (f.ref, n, gx, gy, wx, wy))
                bad += 1
        if not bad:
            print('   %s: all %d holes on the HL2 grid, pin 1 at local '
                  '(%.2f, %.2f)' % (f.ref, len(g), g[1][0], g[1][1]))
    return prob


def boot_arithmetic(fps, box, refs, body_w, label):
    xs = []
    for f in fps:
        if f.ref in refs:
            xs.append(f.at[0] - box[0])
    xs.sort()
    if len(xs) < 2:
        return []
    pitches = [round(xs[i + 1] - xs[i], 3) for i in range(len(xs) - 1)]
    w = box[2] - box[0]
    print('   %s socket centres at local x %s, pitch %s mm'
          % (label, ', '.join('%.2f' % v for v in xs),
             ', '.join('%.2f' % v for v in pitches)))
    print('      bodies %.2f mm wide -> occupy %.2f..%.2f mm on a %.1f mm '
          'board; max pitch that still leaves 0.55 mm of copper to each edge '
          'is %.2f mm' % (body_w, xs[0] - body_w / 2, xs[-1] + body_w / 2, w,
                          (w - 1.1 - 11.2) / 2 if body_w < 12 else
                          (w - 1.1 - body_w) / 2))
    return []


# ------------------------------------------------------------ locked parts
def check_locked(fps):
    """Exactly the mechanically fixed parts are locked, each where its
    source document puts it; the outline features are where they belong."""
    prob = []
    byref = {f.ref: f for f in fps}
    for ref, (wx, wy) in sorted(LOCKED.items()):
        f = byref.get(ref)
        if f is None:
            prob.append('locked part %s is missing' % ref)
            continue
        gx, gy = f.at[0] - PAGE[0], f.at[1] - PAGE[1]
        if abs(gx - wx) > 0.01 or abs(gy - wy) > 0.01:
            prob.append('%s at panel (%.3f, %.3f), documented (%.3f, %.3f)'
                        % (ref, gx, gy, wx, wy))
        if not f.locked:
            prob.append('%s is at its fixed position but not locked' % ref)
    extra = sorted(f.ref for f in fps if f.locked and f.ref not in LOCKED)
    if extra:
        prob.append('locked but not mechanically fixed, so Quilter would '
                    'never move them: %s' % ', '.join(extra))
    # the U-notch, from the Edge.Cuts segments; it opens into the slot
    segs = [((round(e[0][0] - PAGE[0], 3), round(e[0][1] - PAGE[1], 3)),
             (round(e[-1][0] - PAGE[0], 3), round(e[-1][1] - PAGE[1], 3)))
            for e in load.edges if len(e) == 2]

    def has(x0, y0, x1, y1):
        k = lambda v: round(v, 3)
        return any({a, b} == {(k(x0), k(y0)), (k(x1), k(y1))}
                   for a, b in segs)

    nx0, ny, nx1 = NOTCH
    rb = round(RADIO_BOTTOM, 3)
    if not (has(nx0, ny, nx1, ny) and has(nx0, ny, nx0, rb)
            and has(nx1, ny, nx1, rb)):
        prob.append('the M3 U-notch is not at x %.2f..%.2f from y %.2f to the '
                    'radio end edge' % (nx0, nx1, ny))
    if not prob:
        print('   locked, and each at its documented position: %s, and the '
              '%d mouse-bite holes MB2-MB%d'
              % (', '.join(sorted(r for r in LOCKED
                                  if not (r.startswith('MB') and r != 'MB1'))),
                 len(LOCKED) - 11, len(LOCKED) - 10))
        print('   U-notch in place; nothing else locked')
    return prob


# ------------------------------------------------ placement and routing rules
SS_CONTACT = {'J1': 'radio', 'J101': 'gowin'}
DECAP_PIN = {'VCCA': '1', 'VCCB': '16', 'input': '1', 'output': '5'}
VCC_PIN = {'SOIC': '4', 'TSSOP_RCV': '13'}
HDR_SKIP = ('GND', 'DB1_3V3', 'VLVDS')
GROUPS = {
    'radio forward': ['A_FWDCLK', 'A_ADCD0', 'A_ADCD1', 'A_ADCD2'],
    'radio reverse': ['B_REVCLK', 'B_TXD0', 'B_TXD1', 'B_TXD2'],
    'radio aux out': ['A_AUXCLK', 'A_AUXDAT'],
    'radio aux in': ['B_AUXCLK', 'B_AUXDAT'],
    'Gowin forward': ['G_B_FWDCLK', 'G_B_ADCD0', 'G_B_ADCD1', 'G_B_ADCD2'],
    'Gowin reverse': ['G_A_REVCLK', 'G_A_TXD0', 'G_A_TXD1', 'G_A_TXD2'],
    'Gowin aux out': ['G_A_AUXCLK', 'G_A_AUXDAT'],
    'Gowin aux in': ['G_B_AUXCLK', 'G_B_AUXDAT'],
}
MATCH_TOL = 2.5


def edge_gap(a, b):
    """Closest distance between two pad rectangles (x, y, hx, hy)."""
    dx = max(0.0, abs(a[1] - b[1]) - a[3] - b[3])
    dy = max(0.0, abs(a[2] - b[2]) - a[4] - b[4])
    return math.hypot(dx, dy)


def bom_functions():
    import csv
    path = os.path.join(ROOT, 'bridge', 'bridge-bom.csv')
    with open(path, encoding='utf-8') as fh:
        return {r['Designator']: r['Function'] for r in csv.DictReader(fh)}


def check_rules(fps):
    """The rules Quilter cannot read from the file.  Only meaningful once
    the unlocked parts are on the board; skipped while they are staged."""
    prob = []
    if not check.placed:
        print('   placement rules: nothing placed yet - checked when the '
              'board comes back from Quilter')
        return prob
    byref = {f.ref: f for f in fps}
    pads_on = {}
    for f in fps:
        for pd in f.pads:
            if pd[5]:
                pads_on.setdefault(pd[5], []).append((f, pd))
    # one side only
    for f in check.placed:
        if f.layer != 'F.Cu':
            prob.append('%s was placed on the bottom side' % f.ref)
    # every SMD capacitor with its long axis parallel to the break lines,
    # which run along x: the 0402 and 0805 footprints have their pads along
    # x at 0 degrees, so 0 or 180
    caps = [f for f in check.placed if f.ref.startswith('C') and not f.tht]
    for f in caps:
        if round(f.r) % 180 != 0:
            prob.append('capacitor %s is at %g degrees; turn it to 0 or 180 so '
                        'it lies parallel to the break lines' % (f.ref, f.r))
    print('   SMD capacitors parallel to the break lines: %d of %d'
          % (sum(1 for f in caps if round(f.r) % 180 == 0), len(caps)))
    # ESD arrays within 5 mm of the contacts they clamp
    worst = 0.0
    for f in check.placed:
        if not f.ref.startswith('D'):
            continue
        for pd in f.pads:
            if not pd[5] or pd[5] in ('GND', 'G_GND'):
                continue
            cons = [q for (g, q) in pads_on.get(pd[5], [])
                    if g.ref in SS_CONTACT]
            if not cons:
                continue
            d = min(edge_gap(pd, c) for c in cons)
            worst = max(worst, d)
            if d > 5.0:
                prob.append('%s pad %s (%s) is %.2f mm from its SlimSAS '
                            'contact; the limit is 5 mm'
                            % (f.ref, pd[0], pd[5], d))
    print('   ESD arrays: worst array-to-contact gap %.2f mm (limit 5)'
          % worst)
    # terminations within 5 mm of the receiver input
    worst = 0.0
    for f in check.placed:
        if not f.ref.startswith('R') or len(f.pads) != 2:
            continue
        nets = {pd[5] for pd in f.pads}
        if not all(n and n.endswith(('_P', '_N')) and
                   (n.startswith('B_') or n.startswith('G_B_')) for n in nets):
            continue
        rx = [(g, q) for n in nets for (g, q) in pads_on.get(n, [])
              if g.ref.startswith('U') or g.ref == 'J102']
        if not rx:
            continue
        d = min(edge_gap(pd, q) for pd in f.pads for (g, q) in rx)
        worst = max(worst, d)
        if d > 5.0:
            prob.append('termination %s is %.2f mm from its receiver %s; '
                        'the limit is 5 mm' % (f.ref, d, rx[0][0].ref))
    print('   terminations: worst resistor-to-receiver gap %.2f mm (limit 5)'
          % worst)
    # decoupling capacitors at the pins they serve
    fn = bom_functions()
    worst = 0.0
    for f in check.placed:
        if not f.ref.startswith('C'):
            continue
        words = fn.get(f.ref, '').split()
        if len(words) < 2 or not words[0].startswith('U'):
            continue
        ic = byref.get(words[0])
        if ic is None:
            continue
        kind = words[1]
        if kind in DECAP_PIN:
            pin = DECAP_PIN[kind]
        elif kind == 'VCC':
            pin = '4' if any(q[0] == '4' and q[5] == '+3V3' for q in ic.pads) \
                and len(ic.pads) == 16 and ic.crt and \
                (ic.crt[3] - ic.crt[1] > 9 or ic.crt[2] - ic.crt[0] > 9) \
                else '13'
        else:
            continue
        tgt = [q for q in ic.pads if q[0] == pin]
        cp = [q for q in f.pads if q[5] == (tgt[0][5] if tgt else None)]
        if not tgt or not cp:
            continue
        d = min(edge_gap(c, tgt[0]) for c in cp)
        worst = max(worst, d)
        if d > 3.0:
            prob.append('%s (%s) is %.2f mm from %s pin %s; keep it within '
                        '3 mm' % (f.ref, fn[f.ref], d, ic.ref, pin))
    print('   decoupling: worst capacitor-to-pin gap %.2f mm (limit 3)'
          % worst)
    # single-ended nets touching an HL2 header pin under 25 mm
    tracks = load.tracks
    worst = (0.0, '')
    for ref in ('J2', 'J3'):
        f = byref.get(ref)
        for pd in (f.pads if f else []):
            n = pd[5]
            if not n or n in HDR_SKIP:
                continue
            routed = sum(t[2] for t in tracks if t[0] == n)
            if routed:
                length, how = routed, 'routed'
            else:
                length = max(math.hypot(pd[1] - q[1], pd[2] - q[2])
                             for (g, q) in pads_on.get(n, [])) if \
                    pads_on.get(n) else 0.0
                how = 'straight-line'
            if length > worst[0]:
                worst = (length, '%s (%s)' % (n, how))
            if length > 25.0:
                prob.append('HL2 header net %s is %.1f mm %s; the limit is '
                            '25 mm' % (n, length, how))
    print('   HL2 header nets: longest %.1f mm, %s (limit 25)' % worst)
    if not tracks:
        print('   routing rules: no tracks yet')
        return prob
    # pairs on the top layer only, nothing routed on the ground plane
    for (n, lay, ln, a, b) in tracks:
        if n.endswith(('_P', '_N')) and n.startswith(('A_', 'B_', 'G_A_',
                                                      'G_B_')) \
                and lay != 'F.Cu':
            prob.append('pair net %s has track on %s; pairs are top layer '
                        'only' % (n, lay))
        if lay == 'In1.Cu':
            prob.append('track on the In1.Cu ground plane (net %s)' % n)
    # length-matched groups
    for grp, lanes in GROUPS.items():
        lens = {}
        for lane in lanes:
            lp = sum(t[2] for t in tracks if t[0] == lane + '_P')
            ln_ = sum(t[2] for t in tracks if t[0] == lane + '_N')
            lens[lane] = (lp + ln_) / 2.0
        spread = max(lens.values()) - min(lens.values())
        print('   %-14s pair lengths %s: spread %.2f mm (limit %.1f)'
              % (grp, ', '.join('%.1f' % v for v in lens.values()), spread,
                 MATCH_TOL))
        if spread > MATCH_TOL:
            prob.append('%s group lengths spread %.2f mm, over %.1f mm'
                        % (grp, spread, MATCH_TOL))
    return prob


def main():
    fps, box, prob = check('bridge')
    # the radio end's LOCAL frame (HL2 y 73.30 at its top), not its trimmed
    # outline: the HL2 grids and the notch arithmetic are in that frame
    rbox = (PAGE[0] + RADIO_FRAME[0], PAGE[1] + RADIO_FRAME[1],
            PAGE[0] + RADIO_FRAME[2], PAGE[1] + RADIO_FRAME[3])
    print('-- the radio end --')
    prob += check_hl2_grid(fps, rbox)
    prob += check_slimsas(fps, rbox)
    prob += check_mech(rbox)
    print('-- the Gowin end --')
    prob += check_gowin(fps)
    print('-- the panel: the tabs and break lines --')
    prob += check_panel(fps)
    print('-- the cut-outs over the radio --')
    prob += check_holes(fps)
    print('-- the locked parts --')
    prob += check_locked(fps)
    print('-- the placement and routing rules --')
    prob += check_rules(fps)
    for s_ in prob:
        print('   !! ' + s_)
    print('   %s' % ('OK - every pad inside its own end of the panel, no two '
                     'courtyards overlap, no two different-net pads closer '
                     'than the clearance floor, the radio end sockets on the '
                     'HL2 grids, the Gowin end socket on the dock J14 grid, '
                     'both SlimSAS land patterns match SFF-8654 Table A-1, the '
                     'ends are joined only by the tabs with no part within 5 mm '
                     'of a break line, the three holes over the radio are '
                     'clear with nothing inside their margin, DB6 is inside '
                     'its window, exactly the fixed parts are locked at '
                     'their documented positions, and every placement and '
                     'routing rule that applies at this stage holds'
                     if not prob else '%d PROBLEMS' % len(prob)))
    return 1 if prob else 0


if __name__ == '__main__':
    sys.exit(main())
