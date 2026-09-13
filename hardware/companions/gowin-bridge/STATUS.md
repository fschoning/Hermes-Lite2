# gowin-bridge status (branch `gowin-bridge-pcb`, rev D)

Last updated 2026-09-13 (prepared for Quilter). Worktree
`G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

**rev D is one design with two ends, on one board.** The **radio end** plugs
onto the Hermes-Lite 2. The **Gowin end** plugs onto the Tang Mega 138K dock.
One schematic, one PCB, one BOM, one outline, snapped apart along V-scores
after manufacture.

| | |
|---|---|
| `bridge/` | **161 parts (132 fitted), 168 nets, ten test points.** ERC **0**, DRC **0** violations, schematic/PCB parity **0**. **Prepared for Quilter, not placed:** 11 fixed parts locked, 142 parts waiting off the board |
| `quilter-upload/` | the three files to upload, KiCad 10 format. ERC 0, DRC 0, parity 0 on those copies too. Procedure: `QUILTER.md` |
| `tools/check_netlist.py` | **OK** — radio-end header maps, the Gowin-end J14 map with both clocks on clock balls, all 74 contacts at each end, **the crossover walked radio→Gowin, Gowin→radio and radio→radio**, the radio-to-radio JTAG proof, the enables, **the AUXIO fail-safe in all three pairings**, every conductor clamped at both ends, and no net shared between the ends |
| `tools/check_geometry.py` | **OK** — **one continuous outline, 64.50 × 90.00 mm, no rails**, the radio-end sockets on the HL2 grids, the Gowin-end socket on dock J14 positions 5–40, both connector land patterns recomputed from SFF-8654 Table A-1, **exactly the 11 fixed parts locked, each at its documented position**, every other part off the board, the score clean. Given the board Quilter returns, it also checks the placement and routing rules |
| `tools/cost_model.py` | **$154.84** for five boards; one link **$30.97**; the Gowin half **$22.41** |
| `gowin_end_j14.cst` | the Gowin constraint file, placed and routed by Gowin EDA 1.9.11.03 without error |

DRC reports 499 unconnected items: the placement and routing, left for Quilter.

---

## Prepared for Quilter (13 Sep 2026)

**What Quilter takes.** A schematic and a board file, plus the project file
for net classes; no zip, no folders. Its docs name no KiCad version; a user
report shows KiCad 10 format parsing where an older file did not, so the
upload copies are KiCad 10. Parts inside the outline stay put; parts outside
get placed. `DESIGN_NOTES.md` §12.1 has every answer with its source.

**What changed on the board.**

| | |
|---|---|
| Notes on the board | all removed; one name-and-revision line and the hot-plug warning per end remain. `DESIGN_NOTES.md` §12.2 |
| Test points | **73 → 10**, list below. Two spare outputs that ended on pads now carry no-connect flags |
| Locked | J1, J2, J3, J4, J5, J101, J102, FID1–FID3 and the MH6 hole. J5 is not set by the radio; it is locked so the placer cannot bury the USB Blaster header |
| Everything else | off the board, in five groups, one per placement region |
| Rules in the file | five top-side placement regions, ten keepouts, pair net class `differentialpair` at 0.25/0.20 mm, 0.15 mm clearance, JLC04161H-7628 stack, In1 named `GND`, In2 `PWR`. `DESIGN_NOTES.md` §12.5 |
| Rails | **removed**: JLCPCB lists rails as not necessary for Economic assembly, parts 0.3 mm from the edge. Board now **64.50 × 90.00 mm**, one score at y 25.12 |
| Pre-drawn +2V5 island | removed; it assumed the old placement. Quilter pours `+2V5` on In2 |
| Fixed on the way | bottom sockets had their silk, courtyard and fab graphics on the top layers; the middle score line was drawn 0.07 mm off the boundary; the old stack had core and prepreg swapped |
| Deleted | `drl/`, a stale drill export |

**What Quilter cannot be told, and is checked on return:** pairs on the top
layer only, and the length-matched groups within 2.5 mm. ESD arrays and
terminations within 5 mm are typed in as proximity constraints.

**Position disagreement found:** HL2 jumper header DB6 runs 0.50 mm past the
jumper window's far edge. It is about reaching the jumper, not a collision.
Not changed.

**Test points kept:**

| Ref | Net | Why |
|---|---|---|
| TP9 | GND | radio ground clip |
| TP1 | +3V3 | rail after the input bead |
| TP2 | +2V5 | the translators' 2.5 V rail |
| TP3 | SB_PRSNT_IN | is a powered far end present |
| TP4 | JTAG_EN_N | must read HIGH at power-up |
| TP5 | AUXIO_EN_N | must read HIGH at power-up |
| TP6 | AUXIO_OE_N | the drive enable after the presence interlock |
| TP7 | HL2_FWD_CLK | forward clock after the divider, 2.50 V high |
| TP8 | HL2_REV_CLK | reverse clock into FPGA pin 88 |
| TP101 | G_GND | Gowin ground clip |

No pull resistor, clamp or fail-safe element depended on a removed pad.
`check_netlist.py` passes all three pairings.

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
lane reaches nothing beyond its own spare channels at the radio end, so nothing
working today is lost;
AUXIO (remote keying, the radio's I2C bus) can be done by the radio's own
gateware on a command over the aux lane. All those conductors are still clamped. **Leaving them unwired is safe**: the radio end biases them
to the not-keyed level itself (next section but one). Tying them at the Gowin
end is not possible anyway: the safe level is 3.3 V and J14 has no 3.3 V pin,
only 5 V and ground.

### 5. JTAG is driven from the Gowin end, and stays safe

The Gowin drives TCK, TMS and TDI and reads TDO on the exact positions the
radio end listens on. **The radio end's gated buffer and pull-ups still decide
whether any of it reaches the radio's CN1**, so JTAG stays disabled at power-up.
At the Gowin end a 1 kΩ pull-down holds TCK low while the FPGA is unconfigured.
Radio to radio is unchanged: the radio end still leaves the TCK and TMS
positions undriven.

---

## An unwired far end can no longer key the transmitter

**Found:** rev D as first built pulled the four cable-side AUXIO inputs
**down** to ground. Two of those lines are the radio's CW key and PTT inputs,
which are keyed when low. So with the drive path enabled and a far end that
does not drive them — the Gowin end, an unplugged cable, an unpowered radio —
the radio would have transmitted. Fixed in the hardware.

**The four lines** (HL2 `hardware/hl`, sheet *Input Output*, and
`hermeslite.net`):

| DB1 | FPGA | Function | Active level | Safe level | On the radio |
|---|---|---|---|---|---|
| 10 | 90 | CW/PTT **ring** (PTT, or the dash paddle) | **LOW = keyed** | HIGH | R75 2.2 kΩ to +3V3, R77 100 Ω to the KEY jack CN4, C71 1 µF, D8 SM05. Sheet note: "Ground to key". Gateware debounces `~io_phone_ring` |
| 12 | 91 | CW/PTT **tip** (CW key, or the dot paddle) | **LOW = keyed** | HIGH | R76 2.2 kΩ, R78 100 Ω, C72 1 µF, D8. Gateware debounces `~io_phone_tip`. **Both low at boot also selects the factory image** |
| 16 | 103 | I2C1 **SCL** to U6, the 5P49V5923 clock generator | idle HIGH | HIGH | R43 4.7 kΩ to +3V3 |
| 18 | 104 | I2C1 **SDA**, same bus (U6 at address 0x6A) | idle HIGH | HIGH | R44 4.7 kΩ to +3V3 |

**How it is fail-safe now, on the radio end alone:**

1. **Every cable-side AUXIO input has a 10 kΩ pull-UP to +3V3.** A far end
   that is absent, unwired, unpowered or tri-stated leaves the line HIGH. The
   drive buffer can then only pass HIGH to the radio: not keyed, bus idle.
2. **The drive buffer (U9) can only be enabled while a powered far end is
   present.** Its enable is pulled up (off) and pulled down only through Q1,
   an AO3400A MOSFET: source on the gateware enable, gate on presence detect.
   Presence is held at 0 V by 10 kΩ with no far end or an unpowered one, so Q1
   is off and U9 is tri-stated **whatever the gateware does**. Q1 is a JLCPCB
   Basic part: no new fee.

**The clock-chip bus.** A write to U6 needs a START (SDA falling while SCL is
high), seven address bits, an acknowledge and register and data bytes: dozens
of coordinated edges on both lines. With no powered far end U9 is tri-stated,
so nothing reaches the bus at all. With one present and the drive enabled, an
undriven line sits at HIGH, which is the bus's idle state and can produce no
edge.

**The LVDS receiver agrees.** The four AUXIO lines are single-ended 3.3 V
sideband conductors and never pass through the DS90LV048A. Its own fail-safe
(TI SNLS045C §8.3.1 and Table 1: output HIGH for open, shorted or terminated
inputs) is HIGH too, so nothing here fights it.

**Checked:** `check_netlist.py` now walks each of the four lines with the far
end's connector pins unconnected — radio to Gowin, Gowin to radio and radio to
radio — and asserts the pull-up, the absence of any pull-down, the path
through U9 and 330 Ω to the right HL2 pin, and the presence interlock on U9's
enable. It passes in all three.

---

## The board and the cost

| | |
|---|---|
| Board | **64.50 × 90.00 mm, one continuous outline, no rails**: Gowin end, radio end, joined across one straight V-score at y 25.12; both connectors on the left edge |
| The 0.07 mm | the radio end's edge facing the Gowin end is 0.07 mm in (HL2 y 73.37), kept from when the rails had to fit 100 mm |
| **Order total, five boards** | **$154.84** |
| Paid once | **$61.78**: PCB $12.10 (board $7.00, lead-free HASL $5.10), setup $8.18, stencil $1.53, six Extended fees $18.42, shipping $21.55 |
| Paid per board | **$18.61**: radio-end parts $13.39, Gowin-end parts $4.04, joints $1.18 |
| **One complete link** | **$30.97** |
| **The Gowin half** | **$22.41** over the $132.43 radio-only order: $21.91 the Gowin end's parts and joints, $0.50 the AUXIO fail-safe parts and today's prices. The PCB costs the same $12.10 as the radio end alone |

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
| **A V-score on an Economic-assembly order** | JLCPCB's capability table lists V-cut panels for Standard assembly only; Standard would need the rails back | ask JLCPCB at order time |
| **What Quilter makes of the board** | its docs say nothing on scores; pairs cannot be held to the top layer; length matching is not available | `QUILTER.md` part E |
| **C5432262 stock** | 189 in stock on 13 Sep 2026; the order needs 10 | buy or order soon |
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
5. Upload to Quilter and check what comes back: `QUILTER.md`. Finish any
   routing by hand with `ROUTING_EASYEDA.md`.
6. Order: five boards, one design, 4 layer, 1.6 mm, lead-free HASL,
   Economic assembly. `COST.md`.
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

copy bridge\bridge.kicad_pro, .kicad_sch, .kicad_pcb to quilter-upload\
%KC% pcb upgrade --force quilter-upload/bridge.kicad_pcb
%KC% sch upgrade --force quilter-upload/bridge.kicad_sch
del quilter-upload\bridge.kicad_prl

%KC% pcb render --side top    -w 1600 -h 1600 --background opaque ^
     --preset follow_pcb_editor -o prep-top.png    bridge/bridge.kicad_pcb
%KC% pcb render --side bottom -w 1600 -h 1600 --background opaque ^
     --preset follow_pcb_editor -o prep-bottom.png bridge/bridge.kicad_pcb

%KC% pcb export pdf --mode-single --scale 1 --black-and-white --drill-shape-opt 2 ^
     --exclude-value --layers "Edge.Cuts,Eco1.User,Dwgs.User,F.SilkS,F.Cu,F.Fab" ^
     -o templates/bridge-1to1-TOP-fit-check.pdf bridge/bridge.kicad_pcb
```

Results: **ERC 0, DRC 0, parity 0, all three checkers OK**, on `bridge/`
and on the KiCad 10 copies in `quilter-upload/`. `prep-top.png` and
`prep-bottom.png` show the prepared board. KiCad 10.0.6; the generator writes
KiCad 8 format into `bridge/`.

The radio end's power budget, ESD choice, translator reasoning, JTAG buffer
and the corrections to the original brief are unchanged: `DESIGN_NOTES.md`
§1–§9 and `PINMAP.md` §1–§10.
