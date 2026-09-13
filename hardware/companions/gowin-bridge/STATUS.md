# gowin-bridge status (branch `gowin-bridge-pcb`, rev D)

Last updated 2026-09-13, evening (the risk-review fixes: two backwards buffers,
stock-gateware contention, power sequencing, noise measures, DB3, front-panel
vents, Hardrock-50). Worktree `G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

**rev D is one design with two ends, on one board.** The **radio end** plugs
onto the Hermes-Lite 2. The **Gowin end** plugs onto the Tang Mega 138K dock.
One schematic, one PCB, one BOM, one outline, snapped apart at three
mouse-bite tabs after manufacture.

| | |
|---|---|
| `bridge/` | **184 parts (152 fitted), 176 nets, eleven test points, 48 ground stitching vias.** ERC **0**, DRC **0** violations, schematic/PCB parity **0**. **Prepared for Quilter, not placed:** 11 fixed parts and 48 mouse-bite holes locked, 165 parts waiting off the board. `bridge.kicad_dru` holds the 3 mm fast-net edge rule for KiCad DRC |
| `quilter-upload/` | the three files to upload, KiCad 10 format (plus the `.kicad_dru`, not uploaded). ERC 0, DRC 0, parity 0 on those copies too. Procedure: `QUILTER.md` |
| `tools/check_netlist.py` | **OK** — radio-end header maps, the Gowin-end J14 map with both clocks on clock balls, all 74 contacts at each end, **the crossover walked radio→Gowin, Gowin→radio and radio→radio**, the radio-to-radio JTAG proof, the enables, **the AUXIO fail-safe in all three pairings**, every conductor clamped at both ends, no net shared between the ends, and since 13 Sep 2026 **every translator's and LVDS part's direction and enable derived from the truth table**, **the safe state in all 16 combinations** of clock, far end and enable pins, and **the presence gating in all three pairings**. With U8's fault put back it fails with 10 problems |
| `tools/check_geometry.py` | **OK** — **one continuous outline, 64.50 × 92.00 mm, no rails**, the ends joined only by the three tabs, **nearest part 6.22 mm from a break line**, milling path 95 m per m² (fee from 120), **the three holes over the radio clear at their full size, read from the HL2 board file**, DB6 inside its window with 2.5 mm, the radio-end sockets on the HL2 grids, the Gowin-end socket on dock J14 positions 5–40, both connector land patterns recomputed from SFF-8654 Table A-1, exactly the fixed parts locked at their documented positions, every other part off the board. Given the board Quilter returns, it also checks the placement and routing rules, including nothing within 1 mm of a hole, pairs 2 mm from a hole, parts 5 mm from a break line and capacitors parallel to it |
| `tools/cost_model.py` | **$162.43** for five boards; one link **$32.49**; the Gowin half **$21.92** |
| `gowin_end_j14.cst` | the Gowin constraint file, placed and routed by Gowin EDA 1.9.11.03 without error |

DRC reports 499 unconnected items: the placement and routing, left for Quilter.

---

## The risk-review fixes (13 Sep 2026, owner-approved)

Full detail and numbers: `DESIGN_NOTES.md` §14. Pin contract: `PINMAP.md` §12.

**1. Two buffers were wired backwards, and are fixed.** U8, the AUXIO read
buffer, had its direction pins on ground, which on this part means cable →
radio: it drove the radio's CW key, PTT and clock-chip I2C pins from floating
cable wires, permanently. U10 port 1 did the same to the FPGA's TDO pin. Both
now run radio → cable, enabled only with a far end present. Every other
translator was checked against the truth table and was the right way round;
the checker now derives every channel's direction and fails on a backwards
one (proved by re-inserting U8's fault).

**2. The board no longer fights a radio running stock gateware.** Stock
gateware drives pins 87, 99, 100 and 101, which our receivers also drove
(20–49 mA per pin), and drives pins 72 and 80 LOW, which switched our JTAG
and AUXIO paths on. A small detector (U11's spare channel, 10 pF, two
RB751V-40 diodes, 10 nF, 100 kΩ) makes `LINK_ALIVE` HIGH only while the link
gateware's 153.6 MHz forward clock runs on pin 98 and a far end is present.
Every output that can drive a radio pin (U3, U6, U7), the JTAG buffers and the
AUXIO drive are off unless it is HIGH. Five AO3400A MOSFETs do the gating. The
checker proves it for stock gateware, no gateware, far end absent and cable
unplugged.

**3. A powered radio no longer pushes current into an unpowered Tang.** The
LVDS drivers now run only while the far end asserts presence (R_DRVEN_PRSNT
fitted), and so do the TDO and AUXIO read buffers (one more MOSFET). R103 at
the Gowin end is now 10 kΩ. **The Gowin gateware must keep its outputs off
until it reads presence** (`PINMAP.md` §11.4). **Buy the sideband cable:** a
no-sideband cable now leaves the link dead.

**4. Noise measures built in.** A 4.7 µH plus 100 µF filter on our 3.3 V
input; unfitted 10 nF footprints beside both shell-to-ground links; no track
on the bottom layer facing the radio; fast signals 3 mm from every edge and
none over the FPGA, AD9866 or T2; 48 ground vias round the cut-outs, at most
4.44 mm apart; every lane scrambled including idle (gateware rule). No
common-mode chokes. The bring-up noise test plan is `DESIGN_NOTES.md` §14.6.

**5. DB3 is clear.** DB3 is an optional radio header whose pins 3 and 4 go
straight into the AD9866's receive input. The main cut-out now clears it with
room for a mating socket (6.54 × 14.16 mm), no track may come within 3 mm of
those pins, and J5 (the USB Blaster header) moved to lie horizontal just below
J4, pin 1 at local (51.40, 30.80).

**6. Front panel vents restored.** Nine holes put back above the SlimSAS
opening in `panel-endcap/`: 27 holes, 73.7 mm², the stock figure. Strength
margin unchanged at 3.9×.

**7. Compatibility requirement: the DB9 adapter board cannot be fitted with
this bridge board.** Its wires land on DB1 pins our socket covers, and DB1
pin 3 is our ADC lane 1. The owner moves the Hardrock-50 serial and PTT to the
N2ADR HL2 IO board (own DB9, Hardrock-50 firmware example) and retires the DB9
adapter. No design change.

**Cost:** order $154.84 → **$162.43**; one link $30.97 → **$32.49**; the Gowin
half **$21.92**. One new $3.07 fee (the inductor); the detector diodes are
JLCPCB Preferred parts with no fee.

**Placement room after the changes:** header region 590 mm² for 338 mm² of
parts (was 538 for 298); main radio region 2166 for 593 (was 2368 for 483).
The 25 mm header-net rule still has at least 289 mm² of region within reach
of every header pin.

---

## Holes over the radio, tabs, jumper window (13 Sep 2026)

Three approved outline changes, then re-prepared for Quilter. No net, pin,
schematic symbol or locked part moved. Full reasoning and sources:
`DESIGN_NOTES.md` §13.

**1. Holes through the radio end over three radio parts.** Sized from each
package (read from the HL2 board file and checked against the datasheet),
plus 1.5 mm a side, corners R 1.0 mm, nothing within 1 mm of an edge.

| Over the radio's | Package | Hole |
|---|---|---|
| FPGA (HL2 U2) | 144-pin EQFP, 22 × 22 mm over the leads; footprint 23.20 | **26.20 × 26.20 mm**, a notch open to the radio end's top edge |
| AD9866 (HL2 U7) | 64-lead LFCSP, 9 × 9 mm; footprint 10.00 | **13.00 × 13.00 mm** |
| Transformer T2 | footprint 7.62 × 8.25 mm (the owner's T2 is 11.17 mm tall) | **10.62 × 11.25 mm** |

The AD9866 hole, the T2 hole and the jumper window are one cut-out: the webs
between them would have been under 2 mm. JLCPCB charges nothing per cut-out;
its only milling charge starts at 120 m of path per m², and this board is at
95. The header-chip placement region lost area to the FPGA notch and gained
the old score strip: 533 mm² for 298 mm² of parts (was 767). No other region
needed changing.

**2. Tabs instead of the V-score.** JLCPCB does not V-score Economic assembly
at all; it accepts mouse-bite panels. The ends are now joined by three 5 mm
tabs with 0.5 mm mouse bites across a 2 mm slot, radio end on top. Board
**64.50 × 92.00 mm**. **Nearest part to a break line 6.22 mm** (a fiducial);
anything Quilter places is held 5 mm off by keepouts and regions. No end had
to grow. Every SMD capacitor must be parallel to the break lines; Quilter
cannot be told, so the checker fails a returned board that breaks it.
**Rails stay off.** The question for JLCPCB is in `DESIGN_NOTES.md` §13.2.

**3. Jumper window widened** to local x 43.30–57.00, y 39.50–53.00. DB6 is
inside with 2.5 mm clear on every side. **Found:** DB3's position in the
notes and checker was wrong (footprint rotated the wrong way); about a third
of DB3 is under the board, beside locked J5, and always was.

**Measurements from the owner's radio** (build 9, 13 Sep 2026) recorded in
`DESIGN_NOTES.md` §13.4: underside 10.92 mm on his socket, Ethernet jack
11.18 mm, KEY jack 5.12 mm, clock SMAs 4.24 mm (both fitted, straight plugs),
T2 11.17 mm, FPGA heatsink 8.25 mm. They close the old M2 and M3 open items.

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
| Rules in the file | five top-side placement regions, ten keepouts (nineteen since the changes above), pair net class `differentialpair` at 0.25/0.20 mm, 0.15 mm clearance, JLC04161H-7628 stack, In1 named `GND`, In2 `PWR`. `DESIGN_NOTES.md` §12.5 |
| Rails | **removed**: JLCPCB lists rails as not necessary for Economic assembly, parts 0.3 mm from the edge. Board then 64.50 × 90.00 mm with one score; since replaced by the tabs above |
| Pre-drawn +2V5 island | removed; it assumed the old placement. Quilter pours `+2V5` on In2 |
| Fixed on the way | bottom sockets had their silk, courtyard and fab graphics on the top layers; the middle score line was drawn 0.07 mm off the boundary; the old stack had core and prepreg swapped |
| Deleted | `drl/`, a stale drill export |

**What Quilter cannot be told, and is checked on return:** pairs on the top
layer only, and the length-matched groups within 2.5 mm. ESD arrays and
terminations within 5 mm are typed in as proximity constraints.


**Test points kept:**

| Ref | Net | Why |
|---|---|---|
| TP9 | GND | radio ground clip |
| TP1 | +3V3 | rail after the input filter |
| TP2 | +2V5 | the translators' 2.5 V rail |
| TP3 | SB_PRSNT_IN | is a powered far end present |
| TP4 | JTAG_EN_N | must read HIGH at power-up and with stock gateware |
| TP5 | AUXIO_EN_N | the raw enable from FPGA pin 72: LOW under stock gateware |
| TP6 | AUXIO_OE_N | the drive enable after the link-alive and presence gates |
| TP7 | HL2_FWD_CLK | forward clock after the divider, 2.50 V high |
| TP8 | HL2_REV_CLK | reverse clock into FPGA pin 88 |
| TP10 | LINK_ALIVE | about 2.2 V only while the forward clock runs and a far end is present (added 13 Sep 2026) |
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
| Board | **64.50 × 92.00 mm, one continuous outline, no rails**: radio end on top, Gowin end below, joined by three mouse-bite tabs across a 2 mm slot; both connectors on the left edge |
| The 0.07 mm | the radio end's top edge is 0.07 mm in (HL2 y 73.37), kept from when the rails had to fit 100 mm |
| **Order total, five boards** | **$162.43** (was $154.84 before the risk-review fixes); 92.00 mm is in the same size band as the quote, but see the tabs question above |
| Paid once | **$64.85**: PCB $12.10 (board $7.00, lead-free HASL $5.10), setup $8.18, stencil $1.53, seven Extended fees $21.49, shipping $21.55 |
| Paid per board | **$19.52**: radio-end parts $14.23, Gowin-end parts $4.04, joints $1.25 |
| **One complete link** | **$32.49** |
| **The Gowin half** | **$21.92**: the Gowin end's parts and joints for five boards. The PCB costs the same $12.10 as the radio end alone |

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
| **The radio's Ethernet jack beside the radio end** | measured 11.18 mm tall, above the 10.92 mm underside; centred on its footprint it stops about 1.7 mm short of the board edge | look at the first fit |
| **Economic assembly of one outline with two circuits on tabs, and how it is charged** | JLCPCB lists mouse-bite panels for Economic, but may count the two ends as two designs and drop the promotional board price; `COST.md` assumes neither | ask JLCPCB the question in `DESIGN_NOTES.md` §13.2 before ordering |
| **What Quilter makes of the board** | its docs say nothing on panels or tabs; pairs cannot be held to the top layer; length matching is not available | `QUILTER.md` part E |
| **C5432262 stock** | 189 in stock on 13 Sep 2026; the order needs 10 | buy or order soon |
| **The connector's front-face setback** | derived, ±0.5 mm; sets where both mating faces sit | Amphenol's drawing for U10A474240T |
| **The radio end's open items** | HL2 R17 not fitted, the three-socket tolerance stack, Cyclone IV capture at 307.2 Mbit/s | `DESIGN_NOTES.md` §10 |
| **Whether the 10Gtek cable carries all 16 sidebands** | the LVDS drivers now need presence over a sideband; a no-sideband cable leaves the link dead | the ohmmeter test |
| **The link-alive detector on real parts** | its 2.2 V output is calculated, not measured | bench test with a 153.6 MHz signal before plugging into a radio (`ROUTING.md` §7 step 0) |
| **C193025 stock**, the 4.7 µH inductor | about 2,000 in stock | buy soon, or use SWPA4020S100MT (C82398) |
| **Whether Quilter keeps the 48 pre-placed ground vias, and routes with no track on the radio end's bottom layer** | its docs are silent on pre-placed vias; the bottom-layer ban leaves top and In2 for signals | `QUILTER.md` steps 5a and 50c |
| **Every noise ranking** | judgement until measured | `DESIGN_NOTES.md` §14.6 |

---

## The radio-end front panel

`panel-endcap/` (for the 55 mm case, rev C) has its SlimSAS opening at panel
x 120.30–144.30, centred on the connector. Moving it had cost nine of the 27
stock vent holes; on 13 Sep 2026 nine were put back, same Ø1.4 mm and 2.5 mm
pitch, as a 3 × 3 block above the opening at panel x 130.5–135.5, y 56.7–61.7.
Vent area is back to the stock **73.7 mm²**. The block is 12.5 mm from the
opening and 3.6 mm from the nearest stock hole. The 55 N strength margin is
unchanged at 3.9× (the new holes sit where the bending moment is lowest).
DRC: the same single, expected library-mismatch note. Full record:
`franz-claude-analysis/HL2_END_PANEL.md` in the master repo (kept out of git).

---

## Next steps, in order

1. Buy one cable and ohmmeter it, including all 16 sidebands.
1a. Retire the DB9 adapter board; move the Hardrock-50 serial and PTT to the N2ADR IO board.
2. Decide scheme 1 or scheme 2. If scheme 1, buy the C55160396 sockets now.
3. Choose the Gowin-end M3 spacer; confirm it fits a 3.2 mm hole.
4. Print `templates/bridge-1to1-TOP-fit-check.pdf` at 100 %. Offer the radio
   end to the radio: the three holes over the FPGA, AD9866 and T2, and DB6 in
   its window. Offer the Gowin end to the dock: J14 positions 5–40, the dock
   corner hole, and the connector face against the RJ45 face.
5. Upload to Quilter and check what comes back: `QUILTER.md`. Finish any
   routing by hand with `ROUTING_EASYEDA.md`.
6. Ask JLCPCB the tabs question (`DESIGN_NOTES.md` §13.2). Then order: five
   boards, 4 layer, 1.6 mm, lead-free HASL, Economic assembly, tabs left
   unbroken. `COST.md`.
7. Gowin gateware: start from `gowin_end_j14.cst`, with the two
   configuration-pin options set. Keep every LVDS and JTAG output off until
   presence (ball AA18) reads HIGH, and scramble every lane including idle.
8. HL2 link gateware: run the forward clock on pin 98 continuously; nothing
   reaches the radio's pins without it (`PINMAP.md` §9, §12).
9. At bring-up: bench-test `LINK_ALIVE`, then the safety check, then the noise
   test plan (`ROUTING.md` §7, `DESIGN_NOTES.md` §14.6).

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
%KC% pcb drc --refill-zones panel-endcap/panel-endcap.kicad_pcb

%KC% sch erc --severity-error -o bridge/bridge-erc.rpt bridge/bridge.kicad_sch
%KC% pcb drc --severity-error --schematic-parity --refill-zones ^
     -o bridge/bridge-drc.rpt bridge/bridge.kicad_pcb

copy bridge\bridge.kicad_pro, .kicad_sch, .kicad_pcb, .kicad_dru to quilter-upload\
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
%KC% pcb export pdf --mode-single --scale 1 --black-and-white --drill-shape-opt 2 ^
     --exclude-value --mirror --layers "Edge.Cuts,Dwgs.User,B.SilkS,B.Cu,B.Fab" ^
     -o templates/bridge-1to1-BOTTOM-mirrored.pdf bridge/bridge.kicad_pcb
```

`check_netlist.py` reads `bridge/` only; for the upload copies it was run on a
scratch copy of the folder with `quilter-upload/` in place of `bridge/`.

Results: **ERC 0, DRC 0, parity 0, all three checkers OK**, on `bridge/`
and on the KiCad 10 copies in `quilter-upload/`. `prep-top.png` and
`prep-bottom.png` show the prepared board. KiCad 10.0.6; the generator writes
KiCad 8 format into `bridge/`.

The radio end's power budget, ESD choice, translator reasoning, JTAG buffer
and the corrections to the original brief are unchanged: `DESIGN_NOTES.md`
§1–§9 and `PINMAP.md` §1–§10.
