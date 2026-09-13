#!/usr/bin/env python3
"""Generate front and rear end panels for a Sipeed Tang Mega 138K dock in the
Hermes-Lite 2 40 mm aluminium extrusion.

Base: hardware/enclosure/endcaps/kf7o/hl2_40f and hl2_40b (106 x 40 mm, 0.8 mm
PCB, four M3 holes 4 mm in from each edge). Header, setup, outline and mounting
holes are copied from kf7o hl2_40f; every opening is new.

Derivation: franz-claude-analysis/TANG_IN_40MM_CASE.md in the main repository.

Panel frame (kf7o): x 50..156, y 65..105, outer case bottom at y = 105, viewed
from OUTSIDE the case. Height above the case's outer bottom h -> y = 105 - h.
  Front:  panel_x = dock_y + 20.82   (dock_y = Sipeed Tang_Mega_NEO_Dock_31004 board-file y)
  Rear:   panel_x = 185.18 - dock_y
Assumed stack, heights above the outer case bottom:
  carrier plate top, lower card slot   8.20  (= HL2 board top in kf7o hl2_40f)
  M3 x 5.0 standoffs + 1.6 mm dock     dock top 14.80
  J14 mated header 7.0 + 1.6 adapter   SlimSAS seating plane 23.40
Run:  python gen_panels.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def header(title, comments):
    c = ''.join('    (comment %d "%s")\n' % (i + 1, t) for i, t in enumerate(comments))
    return """(kicad_pcb (version 20171130) (host pcbnew 5.1.5)

  (general
    (thickness 0.8)
    (drawings 0)
    (tracks 0)
    (zones 0)
    (modules 4)
    (nets 2)
  )

  (page USLetter)
  (title_block
    (title "%s")
    (date 2026-09-13)
    (rev "A")
%s  )

  (layers
    (0 F.Cu signal)
    (31 B.Cu signal)
    (32 B.Adhes user)
    (33 F.Adhes user)
    (34 B.Paste user)
    (35 F.Paste user)
    (36 B.SilkS user)
    (37 F.SilkS user)
    (38 B.Mask user)
    (39 F.Mask user)
    (40 Dwgs.User user)
    (41 Cmts.User user)
    (42 Eco1.User user)
    (43 Eco2.User user)
    (44 Edge.Cuts user)
    (45 Margin user)
    (46 B.CrtYd user hide)
    (47 F.CrtYd user)
    (48 B.Fab user)
    (49 F.Fab user hide)
  )

  (setup
    (last_trace_width 0.25)
    (trace_clearance 0.2)
    (zone_clearance 0.3)
    (zone_45_only no)
    (trace_min 0.2)
    (via_size 0.8)
    (via_drill 0.4)
    (via_min_size 0.4)
    (via_min_drill 0.3)
    (uvia_size 0.3)
    (uvia_drill 0.1)
    (uvias_allowed no)
    (uvia_min_size 0.2)
    (uvia_min_drill 0.1)
    (edge_width 0.15)
    (segment_width 0.2)
    (pcb_text_width 0.3)
    (pcb_text_size 1.5 1.5)
    (mod_edge_width 0.15)
    (mod_text_size 1 1)
    (mod_text_width 0.15)
    (pad_size 1.524 1.524)
    (pad_drill 0.762)
    (pad_to_mask_clearance 0.051)
    (solder_mask_min_width 0.25)
    (aux_axis_origin 50 65)
    (grid_origin 50 65)
    (visible_elements FFFFFF7F)
    (pcbplotparams
      (layerselection 0x015fc_ffffffff)
      (usegerberextensions false)
      (usegerberattributes false)
      (usegerberadvancedattributes false)
      (creategerberjobfile false)
      (excludeedgelayer true)
      (linewidth 0.100000)
      (plotframeref false)
      (viasonmask false)
      (mode 1)
      (useauxorigin true)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.000000)
      (psnegative false)
      (psa4output false)
      (plotreference true)
      (plotvalue true)
      (plotinvisibletext false)
      (padsonsilk false)
      (subtractmaskfromsilk false)
      (outputformat 1)
      (mirror false)
      (drillshape 0)
      (scaleselection 1)
      (outputdirectory "gerber/"))
  )

  (net 0 "")
  (net 1 GND)

  (net_class Default "This is the default net class."
    (clearance 0.2)
    (trace_width 0.25)
    (via_dia 0.8)
    (via_drill 0.4)
    (uvia_dia 0.3)
    (uvia_drill 0.1)
    (add_net GND)
  )
""" % (title, c)


def mh(ref, x, y):
    # kf7o endcaplib:mh3mmround as placed in hl2_40f / hl2_40b
    return """
  (module endcaplib:mh3mmround (layer F.Cu) (tedit 5D68A448)
    (at %s %s)
    (fp_text reference %s (at 0.1 3.7) (layer F.SilkS) hide
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (fp_text value 3mm (at 0.1 -3.6) (layer F.Fab)
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (pad 1 thru_hole circle (at 0 0) (size 4.9 4.9) (drill 3.4) (layers *.Cu *.Mask)
      (net 1 GND))
  )
""" % (x, y, ref)


OUTLINE = """
  (gr_arc (start 154 67) (end 156 67) (angle -90) (layer Edge.Cuts) (width 0.15))
  (gr_arc (start 154 103) (end 154 105) (angle -90) (layer Edge.Cuts) (width 0.15))
  (gr_arc (start 52 103) (end 50 103) (angle -90) (layer Edge.Cuts) (width 0.15))
  (gr_arc (start 52 67) (end 52 65) (angle -90) (layer Edge.Cuts) (width 0.15))
  (gr_line (start 50 103) (end 50 67) (layer Edge.Cuts) (width 0.15))
  (gr_line (start 154 105) (end 52 105) (layer Edge.Cuts) (width 0.15))
  (gr_line (start 156 67) (end 156 103) (layer Edge.Cuts) (width 0.15))
  (gr_line (start 52 65) (end 154 65) (layer Edge.Cuts) (width 0.15))
"""


def f(v):
    return ('%.3f' % v).rstrip('0').rstrip('.')


def rrect(x0, y0, x1, y1, r, layer='Edge.Cuts'):
    """Closed rounded-rectangle cut-out. KiCad 5 gr_arc: start = centre, end = arc start point."""
    L = lambda a, b, c, d: '  (gr_line (start %s %s) (end %s %s) (layer %s) (width 0.1))\n' % (f(a), f(b), f(c), f(d), layer)
    A = lambda cx, cy, ex, ey: '  (gr_arc (start %s %s) (end %s %s) (angle 90) (layer %s) (width 0.1))\n' % (f(cx), f(cy), f(ex), f(ey), layer)
    s = L(x0 + r, y0, x1 - r, y0) + L(x1, y0 + r, x1, y1 - r) + L(x1 - r, y1, x0 + r, y1) + L(x0, y1 - r, x0, y0 + r)
    s += A(x1 - r, y0 + r, x1 - r, y0)   # top-right
    s += A(x1 - r, y1 - r, x1, y1 - r)   # bottom-right
    s += A(x0 + r, y1 - r, x0 + r, y1)   # bottom-left
    s += A(x0 + r, y0 + r, x0, y0 + r)   # top-left
    return s


def circle_cut(x, y, d):
    return '  (gr_circle (center %s %s) (end %s %s) (layer Edge.Cuts) (width 0.1))\n' % (f(x), f(y), f(x + d / 2), f(y))


def text(t, x, y, layer='F.SilkS', size=1.2, thick=0.2):
    return ('  (gr_text "%s" (at %s %s) (layer %s)\n    (effects (font (size %s %s) (thickness %s)))\n  )\n'
            % (t, f(x), f(y), layer, f(size), f(size), f(thick)))


def centred(cx, cy, w, h):
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def py(h):
    return 105.0 - h


CARRIER_TOP = 8.20
DOCK_TOP = CARRIER_TOP + 5.0 + 1.6      # 14.80
SEAT = DOCK_TOP + 7.0 + 1.6             # 23.40


def front_x(dock_y):
    return dock_y + 20.82


def rear_x(dock_y):
    return 185.18 - dock_y


MH = [('MH1', 54, 69), ('MH2', 152, 69), ('MH3', 152, 101), ('MH4', 54, 101)]


def build_front():
    s = ''
    # SlimSAS SFF-8654 8i: plug overmould 25.95 x 9.90 -> window 26.5 x 10.5,
    # socket centreline dock y 53.73, plug spans SEAT .. SEAT + 9.90
    cx = front_x(53.73)
    s += rrect(cx - 13.25, py(SEAT + 9.90 + 0.30), cx + 13.25, py(SEAT - 0.30), 1.0)
    s += text('SlimSAS', cx, py(SEAT - 2.4))
    # dock P1 USB-C (USB3 via CH569): centre dock y 75.86, 1.63 above dock top; overmould 12.35 x 6.5
    cx, cy = front_x(75.86), py(DOCK_TOP + 1.63)
    s += rrect(*centred(cx, cy, 13.4, 7.5), 2.0)
    s += text('USB3', cx, cy + 5.6)
    # dock J12 RJ45 (board-sink type): centre dock y 98.43; body ESTIMATED -4.85 .. +8.65 about dock top
    cx = front_x(98.43)
    s += rrect(cx - 8.25, py(DOCK_TOP + 8.65 + 0.25), cx + 8.25, py(DOCK_TOP - 4.85 - 0.25), 0.5)
    s += text('ETH', cx, py(DOCK_TOP + 8.65 + 2.0))
    s += text('TANG 138K', 141.0, 72.5, size=1.3)
    return s


def build_rear():
    s = ''
    # panel-mount 5.5 x 2.1 DC jack (M8 thread type), short pigtail to dock J3 (dock y 78.83)
    cx, cy = rear_x(78.83), py(20.0)
    s += circle_cut(cx, cy, 8.3)
    s += text('12V DC', cx, cy + 6.0)
    # USB-C debug extension (dock J7 faces a side wall): window + 2 x M3 at 25 mm
    cx, cy = 130.0, py(28.0)
    s += rrect(*centred(cx, cy, 12.4, 6.6), 2.0)
    s += circle_cut(cx - 12.5, cy, 3.2)
    s += circle_cut(cx + 12.5, cy, 3.2)
    s += text('USB DEBUG', cx, cy + 5.6)
    # optional 7 mm momentary switch wired to the dock PWR_KEY (hold 2 s)
    cx, cy = 85.0, py(20.0)
    s += circle_cut(cx, cy, 7.0)
    s += text('PWR', cx, cy + 5.2)
    # 3 x 3 vent, 1.4 mm on a 2.5 mm grid (kf7o speakerventsmall pattern)
    for i in range(3):
        for j in range(3):
            s += circle_cut(67.5 + 2.5 * i, 77.5 + 2.5 * j, 1.4)
    return s


def write(name, title, comments, body):
    d = os.path.join(HERE, name)
    os.makedirs(d, exist_ok=True)
    out = header(title, comments) + ''.join(mh(*m) for m in MH) + OUTLINE + body + ')\n'
    with open(os.path.join(d, name + '.kicad_pcb'), 'w', newline='\n') as fh:
        fh.write(out)


if __name__ == '__main__':
    write('tang40_front', 'Tang Mega 138K in HL2 40mm case - FRONT panel',
          ['Base: kf7o hl2_40f outline and M3 holes. 0.8 mm PCB. Drawn as seen from outside.',
           'SlimSAS 26.5x10.5, dock USB3-C 13.4x7.5, dock RJ45 16.5x14.0 (RJ45 height ESTIMATED - check the board).',
           'Assumes carrier plate in lower slot, M3x5 standoffs, 7.0 mm J14 header stack, 1.6 mm adapter.',
           'Derivation: franz-claude-analysis/TANG_IN_40MM_CASE.md'], build_front())
    write('tang40_rear', 'Tang Mega 138K in HL2 40mm case - REAR panel',
          ['Base: kf7o hl2_40b outline and M3 holes. 0.8 mm PCB. Drawn as seen from outside.',
           'DC jack 8.3, USB-C debug extension 12.4x6.6 + 2x3.2 at 25 mm, PWR switch 7.0, 3x3 vent.',
           'Match the DC jack and USB-C extension holes to the parts actually bought.',
           'Derivation: franz-claude-analysis/TANG_IN_40MM_CASE.md'], build_rear())
    print('ok')
