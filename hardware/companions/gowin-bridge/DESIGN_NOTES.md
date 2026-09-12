# gowin-bridge design notes

Assumptions, calculations, and everything that is not verified. Read with
`PINMAP.md` (what connects to what) and `README.md` (how to build and order it).

---

## 1. Data rates and unit intervals

| Signal | Where | Rate | Unit interval |
|---|---|---|---|
| Forwarded ADC clock | cable 1 TMDS clock pair | 76.8 MHz | 13.02 ns period |
| DATA0..5 | cable 1 TMDS data 0..5 | 153.6 Mbit/s each (DDR against 76.8 MHz) | **6.51 ns** |
| Reverse clock | cable 2 TMDS clock pair | 153.6 MHz | 6.51 ns period |
| REV0..2, fast serial | cable 2 TMDS data 0..3 | 307.2 Mbit/s each | **3.26 ns** |
| Status UART, aux line, command UART | DDC SCL / SDA on both cables | <= 3 Mbaud | >= 333 ns |
| Cable detect | HPD on both cables | DC | — |

6 lanes x 153.6 Mbit/s = 921.6 Mbit/s = 12 bits x 76.8 MSPS. That is the whole
ADC stream with no compression and no framing overhead.

The parts are chosen with a wide margin: the DS90LV047A/048A pair is rated
**400 Mbit/s** per channel, so the worst case (307.2 Mbit/s) uses 77 % of the
rating and the forward lanes use 38 %. The Gowin `IDDR` gearbox limit is
400 Mbit/s and its `IDES4` limit 800 Mbit/s, both comfortable.

## 2. Termination and edge rates

* **Every LVDS receiver input pair gets a 100 ohm resistor on the board**, and
  the layout guide requires it **within 5 mm of the receiver pins**. Board A has
  seven (R26..R32, cable 2); board B has seven (R70..R76, cable 1). There is no
  termination at a driver output, which is correct for LVDS.
* **LVDS differential swing** is 250–450 mV (DS90LV047A `VOD1` into 100 ohm),
  common mode 1.125–1.375 V. Transition time is about 1 ns, so at 307.2 Mbit/s
  the edge occupies roughly 30 % of a unit interval — comfortable.
* **Cable length.** A dual-link DVI-D cable is 100 ohm differential, shielded
  per pair, and is qualified far above these rates (single-link DVI runs
  1.65 Gbit/s per pair). Cable length is not a limit here; anything up to a few
  metres is fine electrically. The practical limit is the LVDS driver's 400 Mbit/s
  rating, not the cable.
* **Short single-ended runs.** Every single-ended lane on both boards (HL2 pin
  to driver input, receiver output to HL2 pin or to J14) carries a 22 ohm series
  resistor for source damping and is required by the layout guide to be
  **under 25 mm**.

### 2.1 The one genuinely tight single-ended path

REV0..2 land on **HL2 DB1 pins 11, 15 and 17 at 307.2 Mbit/s**, and each of
those FPGA pins carries an LED with a 1 kohm resistor to +3V3 on the HL2 board.

The LED's junction capacitance (20–50 pF) is **in series with that 1 kohm**, so
at 150 MHz the branch looks like about 1 kohm resistive, not like a capacitor —
the LED does not load the edge. What does load it is the FPGA pin itself (7 pF
for a right-side Cyclone IV pin) plus the header and trace, roughly 12–15 pF
total. A 3.3 V CMOS output with about 50 ohm of effective source impedance into
15 pF gives a 10–90 % rise of about 1.65 ns, which is **51 % of the 3.26 ns
unit interval**. That works but it is the tightest margin on either board.

Consequences, all already in the design:
* keep those three traces under 25 mm (layout guide);
* the series parts R16/R17/R18 are **0 ohm by default** with 0402 pads, so a
  damping value can be substituted without a respin, but do not raise them
  much — at 22 ohm the rise grows to about 1.9 ns;
* the LEDs D3, D4 and D5 on the HL2 will glow or flicker with reverse-link
  data. That is unavoidable and harmless.

**Unverified:** whether the Cyclone IV C8 fabric can actually capture
307.2 Mbit/s DDR on ordinary bank-6 inputs. The device has only one input
register per IOE, so DDR input needs soft logic clocked at 153.6 MHz. That is
the gateware worker's problem, not the board's.

## 3. The 2.5 V / 3.3 V level cases

Four distinct cases, handled four different ways.

### 3.1 HL2 3.3 V output into an LVDS driver input (the forwarded clock)

DB1 pin 9 is bank 6 at 3.3 V; DS90LV047A `VIH` is 2.0 V min. Direct, 22 ohm
series. No issue.

### 3.2 HL2 2.5 V output into an LVDS driver input (DATA0..5)

This is the case worth being explicit about.

| | Value | Source |
|---|---|---|
| Cyclone IV 2.5 V LVCMOS output, `VOH` min | **2.0 V** at `IOH` = -1 mA | Cyclone IV Device Datasheet, Table 1-15 |
| DS90LV047A input `VIH` min | **2.0 V** | TI SNLS044D, Electrical Characteristics |
| Guaranteed margin | **0 mV** | |
| DS90LV047A input current | **-10 to +10 uA** max | TI SNLS044D, `IIH`/`IIL` |
| Actual level on the line | **>= 2.375 V** (VCCIO5 min) | 10 uA through a ~50 ohm source is 0.5 mV |
| Actual margin | **>= 375 mV** | |

The 0 mV figure is an artefact of comparing the driver's `VOH` at its 1 mA
datasheet test current against a load that actually draws 10 uA. **Decision:
connect directly**, with a 22 ohm series resistor and a 10 kohm pull-down (so
the lane is defined while the HL2 FPGA is unconfigured). A 2.5 V CMOS output
driving a 3.3 V LVDS serialiser input is ordinary practice.

If it ever proves marginal on the bench, an SN74AVC8T245 with `VCCA` = 2.5 V
(`VIH` = 0.65 x VCCA = 1.63 V, so 370 mV of *guaranteed* margin) can be
inserted, but that means a respin. It was left out deliberately: it would add
about 2.3 ns of delay and its own jitter to the forwarded clock lane.

### 3.3 3.3 V receiver output into the HL2's two input-only 2.5 V pins

HL2 **PIN_88** (DB12-5, reverse clock, 153.6 MHz) and **PIN_89** (DB12-6, fast
serial, 307.2 Mbit/s) are dedicated clock *inputs* in bank 5, VCCIO 2.5 V. The
Cyclone IV handbook permits up to 3.6 V on any pin but warns of higher leakage
above VCCIO, and **the PCI clamp diode is on by default for a 2.5 V bank** — a
3.3 V driver held high would inject DC into the HL2's 2.5 V rail, which comes
from a TPS730 LDO through a ferrite. Not acceptable.

Three candidate solutions were considered:

1. **A 2.5 V-supplied LVDS receiver.** Rejected: no quad LVDS receiver in the
   JLCPCB/LCSC catalogue operates below 3.0 V. DS90LV048A, SN65LVDS048A,
   SN65LVDS9637 and DS90LV028A are all specified 3.0–3.6 V; running one at
   2.5 V is out of spec.
2. **A resistor divider off the receiver output.** Rejected on numbers. The
   DS90LV048A output is specified only to `VOH` 2.7 V at **-0.4 mA** and `VOL`
   0.3 V at **2 mA**, so it cannot drive a low-impedance divider. A divider light
   enough for it (1 kohm / 3.3 kohm) has a Thevenin resistance of 767 ohm, which
   into the pin's ~10 pF gives tau = 7.7 ns — more than twice the 3.26 ns unit
   interval of the fast-serial lane. Dead.
3. **A dual-supply level translator.** Chosen: **SN74AVC4T245PWR** (LCSC
   C81461), `VCCA` = 3.3 V, `VCCB` = 2.5 V, rated **380 Mbit/s**, about 2.3 ns
   propagation delay. One package covers all three lines that need it: the
   reverse clock, the fast serial lane, and the optional slow command UART.
   `DIR` is tied high (A to B) and `OE` low.

307.2 Mbit/s against a 380 Mbit/s rating is 81 % — the least comfortable
margin in the design after section 2.1, and worth a bench check. The clock line
at 153.6 MHz (equivalent to 307.2 Mbit/s of toggling) is in the same position.

The translator's 2.5 V rail comes from **U6, an ME6211C25M5G LDO** fed from the
board's 3.3 V, not from the HL2. `R36` (`SL_VLVDS`, not fitted) can instead tie
`VCCB` to the HL2's own Vlvds rail on DB1 pins 7/8, which is electrically ideal
because the translator's B-side thresholds would then track the FPGA bank
supply exactly — at the cost of about 10 mA drawn from the HL2's TPS730, whose
remaining headroom is **unverified**. Hence the LDO as the default.

### 3.4 HL2 2.5 V output into a Gowin 3.3 V input (status UART, aux line)

Direct, with a 100 ohm series resistor on board A. The Gowin side has the same
0 mV-guaranteed problem as section 3.2 (GW5AST `LVCMOS33` `VIH` min is 2.0 V),
and here there *is* a free fix: **`IO_TYPE=LVTTL33`** has `VIH` min 1.7 V, giving
300 mV of guaranteed margin. `PINMAP.md` section 4.2 marks those two pins
`LVTTL33` and `HYSTERESIS=NONE` — the Gowin's 400 mV of hysteresis at
VCCIO 3.3 V is larger than the whole margin and must be switched off explicitly
rather than left to the tool default.

## 4. Power budget

### Board A

| Load | Current at 3.3 V |
|---|---|
| U1, U2 DS90LV047A, all channels loaded (`ICCL` max 30 mA each) | 60 mA |
| U3, U4 DS90LV048A (`ICC` max ~25 mA each) | 50 mA |
| U5 SN74AVC4T245 including switching into ~10 pF at 153.6 MHz | 10 mA |
| U6 LDO output (feeds U5's B side) plus its own quiescent | 12 mA |
| Pull-ups, pull-downs, terminations, LED loading on DB1 11/15/17 | 15 mA |
| **Total** | **~150 mA** |

Two sources, selected by header **J6**:

* **Default: DB1 pins 19/20, the HL2's +3V3 rail.** `hardware/hl/Power.sch`
  shows +3V3 generated by a switching stage (a 3.3 uH inductor network), not by
  the TPS730 — the TPS730 (U17) makes the **+2V5** rail, from which Vlvds and
  Veth are fed through ferrites FB28 and FB30. **The +3V3 regulator's part
  number and current rating were not identified in the time available, so the
  headroom for another 150 mA is UNVERIFIED.** This is the single most
  important electrical unknown; measure the HL2's 3.3 V rail with board A
  plugged in before trusting it.
* **Alternative: the DVI +5 V line.** Cable 1 pin 14 carries 5 V from board B
  (which takes it from J14 pin 11, `5V_Peripheral`) to board A's on-board
  AMS1117-3.3 (U7). Move the J6 shunt to 2-3 to use it. The cable then carries
  about 100 mA on one 28 AWG conductor, which is fine. This path makes board A
  independent of the HL2's 3.3 V margin entirely and is the fallback if the
  measurement above is disappointing.

Note that in the **two-radio** use case (README section 2b) there is no Gowin
and therefore no source of DVI +5 V, so both boards must run from their own
HL2's +3V3.

### Board B

~150 mA at 3.3 V (same mix: two quad drivers, two quad receivers), from an
AMS1117-3.3 (U5) fed by J14 pin 11. Dissipation is (5.0 - 3.3) x 0.15 =
**0.26 W** in a SOT-223, which needs the tab flooded to the layer-3 plane with
thermal vias — about a 40 degC rise on a modest pad, acceptable. **How much
current J14 pin 11 can actually supply is UNVERIFIED**; the dock is fed from a
12 V barrel jack so 200 mA should be unremarkable, but no figure was found.

## 5. Grounding

* **Board A** has four ground pins available and uses all of them: DB1 13, 14
  and DB12 3, 4. Plus two through-hole ground clip pads (TP101, TP102) and two
  grounded M3 mounting holes.
* **Board B** has exactly **one** ground pin on J14 (pin 12). That single pin
  is the return for seven 3.3 V CMOS outputs switching at up to 307.2 Mbit/s
  and seven inputs, which is not enough. Mitigations, all present:
  * the **`GND AUX` header J6** for a short wire to a PMOD socket ground pin
    (each PMOD socket has two);
  * two grounded M3 mounting holes — **whether the dock's mounting holes are
    actually grounded is UNVERIFIED**, the dock schematic was not obtained;
  * both DVI cable shields and DVI pins 15 tie board B's ground to board A's
    ground, so the cable itself carries a substantial return path.
  The user should fit the ground wire. It is not optional in practice.
* Both DVI shells go to board ground through a fitted 0 ohm 0805 link (R37/R38
  on board A, R82/R83 on board B) so the shield can be lifted if a ground loop
  appears between the radio and the dock.

## 6. Mechanical

### 6.1 Where DB1 and DB12 are, exactly

Extracted from `hardware/hl/hermeslite.kicad_pcb`, whose board outline is
x 70.00–169.95, y 40.00–140.00 mm (a 100 x 100 mm board).

`DB1` is footprint `HERMESLITE:10x2` at (75.31, 89.39) rotated **270 degrees**.
KiCad's rotation gives absolute = (module_x - pad_y, module_y + pad_x), so:

| DB1 pin | HL2 coordinate | Board A local coordinate |
|---|---|---|
| 1 | (74.04, 77.96) | (3.54, 3.96) |
| 2 | (76.58, 77.96) | (6.08, 3.96) |
| 19 | (74.04, 100.82) | (3.54, 26.82) |
| 20 | (76.58, 100.82) | (6.08, 26.82) |

So DB1 runs **parallel to the left board edge (x = 70)**, odd pins 4.04 mm from
that edge and even pins 6.58 mm, with **pin 1 at the y = 40 end**. This was
cross-checked two ways: the footprint's own pin-1 silkscreen circle sits at
(72.61, 76.49), i.e. diagonally outboard of pin 1 at the low-x, low-y corner;
and KiCad's `RotatePoint` (`x' = x cos + y sin`, `y' = y cos - x sin`) gives the
same answer for 270 degrees.

`DB12` is footprint `HERMESLITE:3x2` at (83.5, 90.0), **not rotated**:

| DB12 pin | HL2 coordinate | Board A local coordinate |
|---|---|---|
| 1 | (83.50, 87.46) | (13.00, 13.46) |
| 2 | (86.04, 87.46) | (15.54, 13.46) |
| 5 | (83.50, 92.54) | (13.00, 18.54) |
| 6 | (86.04, 92.54) | (15.54, 18.54) |

**The two headers are not on a common 0.1 inch grid.** DB12's first column is
6.92 mm inboard of DB1's inner row, and DB12's first row is 9.50 mm toward
y = 140 from DB1 pin 1. Neither is a multiple of 2.54 mm. That is fine for a
PCB — the two socket footprints are simply placed at these measured offsets —
but it does mean the board A outline and both sockets must be generated from
these numbers, not snapped to a grid. `board A local = HL2 - (70.50, 74.00)`.

### 6.2 The N2ADR filter board corridor

The N2ADR filter board (`hardware/companions/n2adr/n2adr.kicad_pcb`) is
**100 x 49.9 mm** (outline x 65–165, y 55–104.9 in its own coordinates). Its
1x20 header `CN2` sits at y 56.134, i.e. **1.1 mm from its y = 55 edge**, and
spans 48.26 mm along its x axis. On the HL2, `DB7` (22x1) is at (168.7, 100.26)
rotated 90 degrees and runs along the **right** board edge from y = 46.92 to
y = 100.26, i.e. 1.25 mm from the x = 169.95 edge.

Matching the connector to the edge in both boards shows the filter board's
x axis maps to the HL2's y axis: **the filter board occupies HL2 x 120.05 to
169.95, over the full y range.** `DB13` (5x2 at (167.1, 92.64) rot 90), which
the N2ADR/Pico IO board uses, is on the same right edge.

**So DB1 and DB12 leave a clear corridor of HL2 x 70.0 to 120.0, that is
50.0 mm wide.** Board A is laid out 48.0 mm wide (x 70.5 to 118.5), leaving
1.5 mm to the filter board's edge. There is **no electrical overlap** — the
filter board touches no DB1 or DB12 line.

### 6.3 Height

| | Height above the HL2 board top |
|---|---|
| HL2 DB1/DB12 male header insulator | 2.54 mm |
| 2.54 mm female socket body | 8.5 mm |
| **Board A underside** | **11.04 mm** |
| Board A (1.6 mm) top surface | 12.64 mm |
| Right-angle DVI receptacle shell top | ~26 mm |
| Stack-through tails above board A | ~3–6 mm |
| A stacked DB1 companion's own board | ~22.7 mm |

The HL2's own tall parts in the corridor are the **RJ45 magjack at (81.1, 62.8),
about 13.5 mm tall and occupying roughly HL2 x 73–89, y 52–73**, and the
**barrel jack CN2 at (80.8, 47.2)**, about 11 mm tall. Board A's underside at
11.04 mm is **below both**, so **board A must not extend past HL2 y = 74**.
That is exactly where its outline starts. Clearance to the magjack is
**1.0 mm in y**, not in z — board A stops short of it rather than passing over
it. Verify by measurement.

A stacked companion board on the stack-through header would sit at about
22.7 mm, leaving roughly 17 mm of headroom inside the enclosure for its own
parts, **but it would collide with board A's DVI receptacles** (top at ~26 mm)
if it extends over them. Stacking is therefore only practical for a companion
small enough to sit over board A's y = 20 to 47 window, or one raised further.

### 6.4 The enclosure problem, stated plainly

**Two right-angle dual-link DVI-D sockets cannot be brought out of a standard
HL2 enclosure with the N2ADR filter board fitted.** The numbers:

* The stock KiCad footprint for a DVI-D dual-link right-angle receptacle (Molex
  74320-4004) has a courtyard of **37.83 x 19.04 mm**. Two side by side need
  **75.7 mm** plus margins, about 80 mm.
* The corridor left by the filter board is **50 mm** (section 6.2).
* Placing one socket at each end of board A instead does not work either: the
  rear end is blocked by the RJ45 magjack (section 6.3), and moving a socket
  inboard means the plug shell would have to travel over 30 mm of board A's own
  top-side components at 0.4 mm clearance.
* Stacking the two sockets vertically needs about 32 mm of height plus the
  plug hood; the enclosure gives roughly 40 mm above the HL2 board and a
  vertical DVI plug needs about 45 mm of straight insertion.
* Vertical (up-facing) DVI receptacles would fit the 50 mm corridor in plan
  view but need about 60 mm of height for socket plus plug. No verified
  footprint for one was found either.

**What was built:** board A is **80 x 66 mm and L-shaped**. The 48 mm-wide arm
(local x 0–48, y 0–66) carries the sockets and all the electronics and sits
inside the corridor. A **32 x 19 mm tab** (local x 48–80, y 47–66) carries the
second DVI socket and **overhangs the filter board region** — in HL2
coordinates, **x 118.5 to 150.5, y 121 to 140**.

Three ways out, for the user to choose:

1. **Run without the N2ADR filter board** (or with the N2ADR/Pico IO board,
   which uses DB7/DB13 but is a different height — measure it). Then the tab
   has nothing under it.
2. **Measure the filter board in that 32 x 19 mm window.** It maps to n2adr
   board coordinates x ~146–165, y ~55–85. If nothing there is taller than
   about 9 mm, the tab clears it at 11.04 mm. This was not checked
   component-by-component and is **unverified**.
3. **Respin board A 48 mm wide with one DVI socket and a second bridge board**,
   or with vertical DVI sockets, accepting that the cables then exit upward and
   the extrusion cannot be closed.

The front-panel cutout needed for the FWD socket is about **40 x 17 mm**,
centred on HL2 x ~93, at 13 to 27 mm above the board. The HL2's own front-edge
RF connectors (`COMBORFGND` at x = 133.3 and 150.3, y = 140) are outside that
window, so a custom front panel — the panels are just 0.8 mm PCBs, see
`hardware/enclosure/endcaps/` — is straightforward. The rear panel is
104.7 x 54.3 mm, confirming a 55 x 105 mm case cross-section.

### 6.5 Board B on the Tang dock

**"User must verify by measurement."** No Tang Mega 138K dock board file,
mechanical drawing or 3D model was obtained, so board B's J14 socket is placed
at board-local (6.0, 8.0) for pin 1 with the header running along +x, odd pins
at y = 8.0 and even pins at y = 10.54, which is a plausible guess and nothing
more. Board B is 90 x 46 mm with both DVI sockets on the far long edge so they
overhang the dock's top edge and the cables route away from the board.

Before ordering, measure on the real dock: the distance from the J14 hole row
to the nearest board edge, and the clearance to the PMOD sockets (J8/J9, which
are right-angle parts and therefore low profile, so board A's 11 mm standoff
should clear them). Then edit `board_b()` in `tools/gen_gowin_bridge.py` and
regenerate. A 1:1 printable check template was **not** produced.

## 7. Layout guide (what remains to be routed)

Neither board has any tracks. Placement, nets, board outline, the 4-layer
stackup and the ground and power zones are done, and the PCB matches the
schematic exactly (`kicad-cli pcb drc --schematic-parity`: 0 issues on both).

Rules for whoever routes it:

1. **Layer 2 is an unbroken ground plane. Do not cut it.** Every differential
   pair must have continuous ground directly beneath it for its whole length.
   Layer 3 is the power plane (3.3 V, with a small 2.5 V island on board A
   under U5).
2. **Route all 28 DVI pairs on the outer layers**, 0.20 mm trace / 0.13 mm gap
   for 100 ohm differential over the JLCPCB standard 4-layer stackup. Confirm
   against the stackup you are actually quoted.
3. **Do not change layer inside a pair.** If a pair must change layer, via both
   legs together and put two ground stitching vias beside them.
4. **Intra-pair length match 0.2 mm.** Inter-pair match does not matter (each
   lane is delay-adjusted independently in the FPGA), so do not waste room on
   serpentines between pairs.
5. **Terminations within 5 mm of the receiver input pins**, on the same layer,
   with no via between the resistor and the pins.
6. **ESD arrays within 5 mm of the DVI connector pins**, on the connector side
   of everything else, so a strike is shunted before it reaches the driver or
   receiver. The TPD4E05U06's 0.5 pF per channel is why this is safe to put
   in-line on a 307 Mbit/s pair at all.
7. **Single-ended lanes under 25 mm** and away from the pairs. Keep the
   307.2 Mbit/s reverse lanes and the 153.6 MHz reverse clock away from the
   forwarded 76.8 MHz clock lane.
8. **Board B specifically:** the A (P) legs of each J14 pair carry a receive
   signal and the B (C) legs carry a transmit signal, because only 14 usable
   pins exist on that header (`PINMAP.md` section 4.1). Adjacent-pin crosstalk
   between a 153.6 Mbit/s input and a 307.2 Mbit/s output is therefore a real
   concern over the short run from the socket to the chips. Route them on
   opposite sides of the board where possible and put a ground trace or a via
   fence between them. If the user is willing to give up the PMOD0 socket,
   J14 pins 1–8 would provide four more pairs and allow full separation — that
   would be a pin-map change, so it is noted rather than done.
9. **U5 on board B (AMS1117, SOT-223):** flood the tab to the power plane with
   at least six 0.3 mm thermal vias; it dissipates 0.26 W.
10. **Stitch the ground planes** with vias every ~5 mm along the board edge and
    around both DVI connectors.

## 8. Deliberate departures from the original brief

| Brief said | What was done | Why |
|---|---|---|
| "DNP LVDS driver/receiver footprints" for the two spare cable-2 pairs | The spare pairs use the **spare channels of the quad packages that are already fitted** | A quad driver and a quad receiver each have one or three unused channels once the seven real lanes are assigned. Using them costs nothing and avoids two unpopulated ICs that a user could never hand-fit. Their outputs go to test points and to header J7. |
| "breakout pads for SCL1/SDA1 and the DB1 2.5 V rail pins" | Replaced by the **stack-through header**, per the later instruction, plus test points | Superseded. |
| Stack-through header as a separate part above the socket | **One 2.54 mm stack-through (long-tail) female header at the DB1 grid** | A separate male header cannot share the socket's holes, and a pass-through connection needs the same hole to carry both the DB1 contact and the companion contact. One long-tail socket does both. The 10 positions the link uses are silkscreened "CLIP TAILS 1-6,9,11,15,17 = USED BY LINK"; clipping them with side cutters is the only way to keep a stacked companion off those signals. |
| Resistor divider acceptable for the FS_RX / input-only case | **Level translator (SN74AVC4T245)** | Section 3.3 gives the numbers: no divider light enough for an LVDS receiver's output is fast enough for the 3.26 ns unit interval. |
| Two dual-link DVI sockets inside the standard enclosure with the filter board | **Not achievable.** Board A is 80 x 66 mm with a 32 x 19 mm tab overhanging the filter board region | Section 6.4 gives the proof. |

## 9. Everything unverified, in one list

1. **The HL2 +3V3 rail's spare current.** The regulator was not identified.
   Measure before relying on the default J6 setting. The DVI +5 V path exists
   as the fallback.
2. **How much current J14 pin 11 (`5V_Peripheral`) can supply** on the Tang dock.
3. **Whether the Tang dock's mounting holes are grounded** (dock schematic not
   obtained), which is why the `GND AUX` header exists.
4. **Board B's mechanical position on the dock** — a guess, section 6.5.
5. **DVI-D receptacle sourcing.** No LCSC part was found; the land pattern used
   is the stock KiCad Molex 74320-4004 footprint. Confirm the actual part's
   drawing before ordering.
6. **Whether the filter board is clear of board A's 32 x 19 mm tab**
   (HL2 x 118.5–150.5, y 121–140).
7. **Whether the Cyclone IV C8 can capture 307.2 Mbit/s DDR** on bank-6 inputs
   in soft logic. Gateware question, but it gates the reverse link.
8. **Whether DB12 ships fitted** on a factory-built HL2. Probably not; assume
   the user solders it.
9. **The SN74AVC4T245's 380 Mbit/s rating against the 307.2 Mbit/s fast-serial
   lane** (81 % of rating) — worth a scope check at bring-up.
10. **Whether a board A plugged into DB1 pins 11/15/17 while the HL2 still runs
    stock LED gateware causes contention.** The `RX MODE` jumper (J5) exists to
    hold the receivers off until the right gateware is loaded, and the
    cable-detect default means they are off whenever cable 2 is unplugged.
