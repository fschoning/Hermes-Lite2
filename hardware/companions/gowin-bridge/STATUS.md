# gowin-bridge status (branch `gowin-bridge-pcb`, rev D)

Last updated 2026-09-13. Worktree
`G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

**rev D is one design with two ends, on one panel.** The **radio end** plugs
onto the Hermes-Lite 2. The **Gowin end** plugs onto the Tang Mega 138K dock.
One schematic, one PCB, one BOM, one panel, snapped apart after manufacture.

| | |
|---|---|
| `bridge/` | **222 parts (192 fitted), 172 nets.** ERC **0**, DRC **0** violations, schematic/PCB parity **0** |
| `tools/check_netlist.py` | **OK** — radio-end header maps, the Gowin-end J14 map with both clocks on clock balls, all 74 contacts at each end, **the crossover walked radio→Gowin, Gowin→radio and radio→radio**, the radio-to-radio JTAG proof, the enables, every conductor clamped at both ends, and no net shared between the ends |
| `tools/check_geometry.py` | **OK** — every pad inside its own end, no courtyard overlaps, the radio-end sockets on the HL2 grids, the Gowin-end socket on dock J14 positions 5–40, both connector land patterns recomputed from SFF-8654 Table A-1, the connector at the case position, the scores clean |
| `tools/cost_model.py` | **$200.99** for five panels; the Gowin half **$68.56** |
| `gowin_end_j14.cst` | the Gowin constraint file, placed and routed by Gowin EDA 1.9.11.03 without error |

DRC reports 457 unconnected items: the routing, left for EasyEDA Pro.

---

## The Gowin end, in five facts

### 1. It is passive: no active chip at all

**J14 is FPGA Bank 4, and Bank 4 runs at 3.3 V**, fixed on the core module
(dock schematic sheet 2/21, the power tree). **Gowin supports true LVDS output
at 3.3 V**: DS1239 §2.3.1 Table 2-1 lists LVDS25 output at Bank VCCIO 2.5 or
3.3 V, and Table 3-10 gives its 3.135–3.465 V range. Input at 3.3 V is allowed
(Table 2-2), all 143 pairs are true-LVDS capable (UG1102 Table 2-3), and the
bottom banks terminate on-die (UG304 §3.3.2). **Gowin EDA placed and routed the
final pin map** — LVDS outputs at 3.5 mA, inputs with on-die termination, all
at 3.3 V — **with no error.**

So the Gowin end is the SlimSAS connector, 12 ESD arrays, 9 resistors and a
hand-fitted 2×18. **It adds no new part number to the order.** The alternatives
the brief listed — J13 on Bank 2, or changing Bank 4's voltage — were not
needed.

**The Gowin project must set `-use_sspi_as_gpio 1` and `-use_cpu_as_gpio 1`.**
Bank 4 doubles as the configuration bank and Gowin EDA refuses five of the
balls without them.

### 2. The clocks

| | J14 | Balls | Function |
|---|---|---|---|
| Forward clock from the radio | 20 / 19 | **U20 / V20** | global clock input SGCLK_5, also the reference input of PLLs BPLL2/BPLL3 |
| Duplicate forward clock | 32 / 31 | **Y18 / Y19** | global clock input MGCLK_4, also those PLLs' feedback input |
| Auxiliary clock | 24 / 23 | AB21 / AB22 | ordinary pins: J14 has only two clock pairs |

### 3. The position is the 40 mm case position, and it is also the bench position

Adopted from `franz-claude-analysis/TANG_IN_40MM_CASE.md`. In Sipeed's dock
coordinates: SlimSAS mating face at **x 89.73**, flush with the dock's RJ45
face; centreline **y 53.73**; M3 spacer hole at **(97.67, 62.66)** over dock
corner hole H7_LU1. The board is 64.50 × 25.12 mm, dock x 89.43–153.93,
y 41.17–66.29, with a notch so an HDMI cable still fits the dock.

**Nothing about the geometry changes between the two mounting schemes.** Only
the stacking parts and the spacer length do:

| | Scheme 1: dock on a carrier plate | Scheme 2: dock screwed to the case floor |
|---|---|---|
| Dock side, J14 positions 5–40 | 2×18 female 5.0 mm, C55160396 (**10 in stock**) | 2×18 male, C41376109 |
| Adapter side | 2×18 male C41376109, **upside down** | 2×18 female 8.5 mm, C42372542 |
| Stack | **7.5 mm**, or **7.0 mm** with the header insulator slid off | 11.0 mm |
| Spacer | M3 × 7 mm | M3 × 11 mm |
| SlimSAS top vs the 36.9 mm worst-case lid | 3.6 mm spare at 7.0, 3.1 mm at 7.5 | about 4 mm spare (case study, section 3) |

**If the insulator is left on (7.5 mm), the plug sits 0.5 mm higher than the
case study assumed**, and its front-panel window has only 0.3 mm of clearance:
move the window up 0.5 mm, or slide the insulator off. The panel files in
`panel-tang-40mm/` were not touched.

### 4. What the case position cost the link

J14 positions 1 and 2 sit under the connector's contacts and 3 and 4 under its
housing, so **neither side of the stack has anything at J14 positions 1–4.**
That leaves 34 pins: fourteen pairs plus six sideband lines, exactly. **Not
wired at the Gowin end: the spare lane and the four AUXIO lines.** The spare
lane reaches only test pads at the radio end, so nothing working today is lost;
AUXIO (remote keying, the radio's I2C bus) can be done by the radio's own
gateware on a command over the aux lane. All those conductors are still clamped
and on test pads.

### 5. JTAG is driven from the Gowin end, and stays safe

The Gowin drives TCK, TMS and TDI and reads TDO on the exact positions the
radio end listens on. **The radio end's gated buffer and pull-ups still decide
whether any of it reaches the radio's CN1**, so JTAG stays disabled at power-up.
At the Gowin end a 1 kΩ pull-down holds TCK low while the FPGA is unconfigured.
Radio to radio is unchanged: the radio end still leaves the TCK and TMS
positions undriven.

**Caution:** the Gowin end leaves the AUXIO drive conductors undriven, so a
radio linked to a Gowin end must **never enable AUXIO drive** — its pull-downs
would key CW/PTT.

---

## The panel and the cost

| | |
|---|---|
| Panel | **64.50 × 100.07 mm**: 5 mm rail, Gowin end, radio end, 5 mm rail; three straight V-scores; both connectors on the left edge |
| Outside 100 × 100 mm? | by 0.07 mm, and **it costs nothing**: the live quote is $50.52 at 99.67 mm and at 101 mm |
| **Order total, five panels** | **$200.99** |
| Paid once | **$108.41**: PCB $50.52 (of which $41.42 is the engineering and panel charges for two outlines on one panel), setup $8.18, stencil $1.53, assembly panel fee $8.21, six Extended fees $18.42, shipping $21.55 |
| Paid per panel | **$18.52**: radio-end parts $13.30, Gowin-end parts $4.04, joints $1.18 |
| **One complete link** | **$40.20** |
| **The Gowin half** | **$68.56** over the $132.43 radio-only order — $46.63 of it the fab's charges for two outlines on one panel, $21.91 the Gowin end's parts and joints |

`COST.md` has every line and source.

---

## Found and fixed while building it

**The committed rev D BOM had two R1s and two R2s.** The generator named the
forward-clock divider R1 and R2 by hand and also gave those names to two
AUXIO resistors automatically. A placement file cannot hold duplicate
designators. Fixed; every automatically numbered radio-end resistor moved up
by two; no net changed.

---

## Everything unverified that could stop the build

| Item | Why it matters | How to settle it |
|---|---|---|
| **The cable's pin wiring** | the whole two-ends argument rests on the A(n)↔B(n) crossover, and 10Gtek publish no wiring diagram | ohmmeter the first cable |
| **The M3 spacer under the Gowin-end connector** | the hole is under the connector housing, so the spacer can only be fixed from below, and it is 0.66 mm from the connector's locating-peg hole: a spacer that needs a hole over 3.2 mm will not fit | choose the spacer part before ordering |
| **C55160396 stock** | the only 5.0 mm 2×18 socket found; 10 in stock | buy them now if scheme 1 |
| **Dock J14 position on rev 31005** | all dock coordinates come from Sipeed's interactive BOM for rev 31004 | measure the board in hand, or print the 1:1 template and offer it up |
| **PMOD socket J9 height** | estimated 6.4 mm; scheme 1 leaves about 0.6 mm under the adapter | callipers |
| **V-scores across two 3.4 mm notches** | fab acceptance | ask JLCPCB at order time |
| **The connector's front-face setback** | derived, ±0.5 mm; sets where both mating faces sit | Amphenol's drawing for U10A474240T |
| **The radio end's open items** | M2/M3 heights under the radio end, HL2 R17 not fitted, the three-socket tolerance stack, Cyclone IV capture at 307.2 Mbit/s | `DESIGN_NOTES.md` §10 |

---

## The radio-end front panel

`panel-endcap/` (for the 55 mm case) still has its SlimSAS opening **31.65 mm
out of position**: it must move to panel x 120.30–144.30, same height and size.
That is layout work for a separate session and was not touched. No extra
ventilation holes are to be cut.

---

## Next steps, in order

1. Buy one cable and ohmmeter it.
2. Decide scheme 1 or scheme 2. If scheme 1, buy the C55160396 sockets now.
3. Choose the Gowin-end M3 spacer; confirm it fits a 3.2 mm hole.
4. Print `templates/bridge-1to1-TOP-fit-check.pdf` at 100 %. Offer the radio
   end to the radio and the Gowin end to the dock: J14 positions 5–40, the
   dock corner hole, and the connector face against the RJ45 face.
5. Route both ends in EasyEDA Pro. Gowin end: the fourteen pairs from the
   connector straight to J14, the ESD arrays within 5 mm of the contacts,
   pairs matched within each group.
6. Order: five panels, "Different Design 2", "Panel by Customer", Economic
   assembly. `COST.md`.
7. Gowin gateware: start from `gowin_end_j14.cst`, with the two
   configuration-pin options set.

**Anything that changes a net is changed in `tools/gen_gowin_bridge.py` and
regenerated, never hand-edited in the KiCad files, and `PINMAP.md` is updated
in the same commit.**

---

## Validation commands used

```
set KC=C:\Users\franz\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe

python tools/gen_gowin_bridge.py
python tools/check_geometry.py
python tools/check_netlist.py
python tools/cost_model.py

%KC% sch erc --severity-error -o bridge/bridge-erc.rpt bridge/bridge.kicad_sch
%KC% pcb drc --severity-error --schematic-parity --refill-zones ^
     -o bridge/bridge-drc.rpt bridge/bridge.kicad_pcb

%KC% pcb export drill --format excellon --drill-origin absolute ^
     --excellon-units mm --excellon-separate-th -o drl/ bridge/bridge.kicad_pcb

%KC% pcb export pdf --mode-single --scale 1 --black-and-white --drill-shape-opt 2 ^
     --exclude-value --layers "Edge.Cuts,Eco1.User,Dwgs.User,F.SilkS,F.Cu,F.Fab" ^
     -o templates/bridge-1to1-TOP-fit-check.pdf bridge/bridge.kicad_pcb
```

Results: **ERC 0, DRC 0, parity 0, all three checkers OK.** The Gowin-end
drill holes were read back from the Excellon export and land on dock J14
positions 5–40. KiCad 10.0.6; files written in KiCad 8 format.

The radio end's power budget, ESD choice, translator reasoning, JTAG buffer
and the corrections to the original brief are unchanged: `DESIGN_NOTES.md`
§1–§9 and `PINMAP.md` §1–§10.
