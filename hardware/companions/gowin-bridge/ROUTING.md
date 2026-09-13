# gowin-bridge routing guide, rev D

For whoever lays this board out. The schematic and the placement are
generated and validated; the routing is not done and is not done here.

**One design, one board, one connector.** rev C's three-socket fan-outs,
upright-fin transitions and panel V-scores do not exist any more.

| | |
|---|---|
| Board | radio end **64.50 × 64.88 mm** (outline from local y 0.07), local (0,0) = HL2 main board (70.00, 73.30); whole board with the Gowin end and rails 64.50 × 100.00 mm |
| Stack | **4 layer**, 1.6 mm. F.Cu signal / **In1.Cu solid GND** / In2.Cu power / B.Cu signal |
| Unrouted nets at handover | 328 items, DRC otherwise **0 violations** |
| Impedance | target **100 Ω differential**, **not** guaranteed — JLCPCB Economic gives no impedance control and `COST.md` §5.1 explains why buying it would waste $33.88 |

---

## 1. The four rules that are not negotiable

1. **In1.Cu is a solid ground plane and nothing crosses it.** Every
   differential pair references it. Do not route on In1.Cu, do not cut it, and
   do not let a via field starve it under the connector.
2. **Every single-ended net that touches an HL2 header pin stays under
   25 mm.** That is what the floor plan is built for: the translators and LVDS
   silicon sit in local x 9…53, y 12…34, right beside DB1 and DB12. The long
   runs are the terminated differential pairs up to the connector, and they do
   not care.
3. **Each received pair's 100 Ω termination goes within 5 mm of the receiver
   pins.** Eight of them. There is no termination at a driver output and none
   should be added.
4. **Each ESD array goes within 5 mm of the SlimSAS contacts**, on the
   connector side of the terminations, the series resistors and the buffers,
   with the shortest possible ground return. Twelve of them. An ESD clamp
   behind the thing it protects protects nothing.

## 2. The order to route in

| | What | Why first |
|---|---|---|
| 1 | **The four forward-group pairs** — `A_FWDCLK`, `A_ADCD0`, `A_ADCD1`, `A_ADCD2`, on connector positions 14/15, 17/18, 20/21, 23/24 | They are the only pairs whose **skew has to match each other**. Length-match them to within about 2.5 mm (which is 15 ps, under 0.5 % of a 3.2552 ns unit interval). They are four contiguous pairs each flanked by grounds, so they fan out cleanly |
| 2 | **The four reverse-group pairs** — `B_REVCLK`, `B_TXD0`, `B_TXD1`, `B_TXD2`, on the same position numbers in row B | Same rule, same tolerance |
| 3 | **The auxiliary pairs** — `A_AUXCLK`, `A_AUXDAT` on 2/3 and 5/6, and their row B counterparts | Clock and data must match each other; they need not match the forward group |
| 4 | **The duplicate clock pair** on 32/33, and the spare on 35/36 | No matching requirement at all |
| 5 | **The 12 ESD arrays**, then the 8 terminations | Rules 3 and 4 above. Do these before the single-ended routing takes the space |
| 6 | **The single-ended HL2 nets** | Rule 2. `HL2_FWD_CLK_RAW` → R1 → `HL2_FWD_CLK` → U1 is the shortest one worth caring about: 132 Ω of Thevenin into ~4 pF is 0.53 ns, and a long stub would add to it |
| 7 | **The 16 sideband conductors** | Slow. TCK at 24 MHz is the fastest; the AUXIO lines are DC to 400 kHz |
| 8 | **The JTAG run from CN1 to the connector** — about 59 mm | Deliberately allowed to be long. 41.7 ns of TCK period against 0.085 ns of added electrical length |
| 9 | **Power** | See §4 |

## 3. Differential-pair geometry

* **Route both legs of a pair on the same layer, side by side, over In1.Cu.**
  Do not split a pair between F.Cu and B.Cu.
* **Ground on both sides where there is room.** The connector gives you a
  ground contact between every pair for free — positions 1, 4, 7, 13, 16, 19,
  22, 25, 31, 34 and 37 in both rows — so stitch them.
* **Via transitions in pairs, with a ground via beside each.** Keep them to a
  minimum; ideally the forward group never changes layer.
* **P is always the lower-numbered contact** in both rows. `check_netlist.py`
  asserts it, because getting it wrong on one pair inverts one lane.
* **Do not add anything to a pair** — no series resistors, no AC coupling, no
  test points. rev C offered AC coupling as an option; rev D does not, because
  every lane has a fixed direction and a series capacitor on a driven pair is
  just an impedance discontinuity.

## 4. Power

* **`DB1_3V3` → FB1 → `+3V3`.** Put the 10 µF on the DB1 side and the 10 µF on
  the `+3V3` side, so the bead sees a capacitor on both sides. Wide copper:
  the board takes 350 mA and the radio's own feed to DB1 pins 19/20 has no
  filtering of its own.
* **In2.Cu is the power layer.** `+3V3` pours over most of it; the `+2V5`
  island spans local x 8…33, y 1…12 and has to reach U1's and U2's VCCA, U3's
  VCCB, U12's output and the `SL_VLVDS` link.
* **One 100 nF per supply pin, on the same side as the pin, via straight to
  the plane.** There are 22 of them and they are not decoration: the
  translators switch 15 pF of internal Cpd per channel at 153.6 MHz.
* **U12, the 2.5 V LDO, dissipates 40 mW.** No thermal work needed.

## 5. The mechanical constraints the router must respect

| | |
|---|---|
| **The three sockets are on the BOTTOM** (J2 on DB1, J3 on DB12, J4 on CN1) and their hole positions are fixed by the radio. Do not move them by so much as 0.01 mm — `check_geometry.py` recomputes all 36 holes from `hermeslite.kicad_pcb` and fails if they move |
| **The connector is at local (10.40, 46.00)** and its position is load-bearing: `DESIGN_NOTES.md` §6.2 shows it cannot go anywhere else. Do not "tidy" it toward the middle of the front edge |
| **The M3 anchor is a U-notch** at local x 1.30…4.70, from y 61.95 to the top edge. Keep copper 0.3 mm clear of it |
| **The window at local x 44.50…57.00, y 39.50…50.00** exists so the radio's DB6 and DB3 configuration jumpers stay reachable. Route around it, not through it |
| **J5, the JTAG pass-through, must stay reachable with the board fitted** — it is on the top at local (56.00, 24.50) and a USB Blaster's 10-way IDC socket needs about 20 × 12 mm of clear space above it and 15 mm of height |
| **The 1.1 mm unplated hole at local (4.04, 2.12)** is the optional locating peg into HL2 MH6 |

## 6. Fault-finding, in the order to try it

| Symptom | First suspect |
|---|---|
| **Nothing at all, both directions** | Read `TP_SB_PRSNT_IN`. If `R_DRVEN_PRSNT` was fitted instead of `R_DRVEN_ON` and the cable has no sidebands, the drivers are disabled and the board looks dead |
| **The forward link does not train** | Scope `TP_HL2_FWD_CLK_RAW`, then `TP_HL2_FWD_CLK` (after the divider — expect 2.50 V high), then `TP_DI_FWDCLK` (the translator output into the driver). If the divider level is low, pin 98 is not set to 8 mA drive |
| **Forward clock fine, data garbled** | Skew. The forward group must be length-matched. Check that all four went through U1 and U4 and that nothing was split across packages |
| **The forward link works but every bit is inverted** | The connector's A1 end is at the other physical end than the footprint assumes. Harmless and recoverable — invert the lane in gateware. `PINMAP.md` §1.1 |
| **The reverse clock is absent** | `R_CLKSEL_A` must be fitted and `R_CLKSEL_B` must not. If the primary clock lane is physically damaged, swap them |
| **The reverse data has a marginal eye** | This is the tightest path on the board: DB1 pins 11/15/17 are the LED pins, and a 3.3 V output into 15 pF gives a 1.65 ns rise against a 3.2552 ns unit interval. The series parts are 0 Ω on 0402 pads; do not raise them past 22 Ω |
| **The auxiliary link works one way only** | Clock and data must be in the same translator port. `TP_HL2_AUX_CLK_IN` and `TP_HL2_AUX_DAT_IN` are both brought out |
| **The radio's auxiliary clock input sees the reverse clock too** | HL2 **R17** is fitted. It must not be — it shorts the DB12 pin 5 and pin 6 nets through 100 Ω |
| **JTAG over the cable does nothing** | Read `TP_JTAG_EN_N`: HIGH means disabled, which is the power-up state and the correct state until the gateware asserts it. If the gateware cannot run, fit `R_JTAG_FORCE` |
| **A locally plugged USB Blaster misbehaves** | `TP_JTAG_EN_N` should read HIGH while a Blaster is plugged in. If it reads LOW, the remote path is driving CN1 at the same time |
| **The radio's CW/PTT or I2C behaves oddly** | Read `TP_AUXIO_OE_N`. HIGH is read-only and is the power-up state; it can only go LOW while `TP_AUXIO_EN_N` is LOW **and** a powered far end holds `TP_SB_PRSNT_IN` high. If it is LOW, the far end is driving four of the radio's pins |
| **The radio browns out or resets when the board is fitted** | Was the board plugged in with the radio powered? That is a 22 A microsecond event. Otherwise measure the radio's 3.3 V rail: the board should draw about 350 mA |

## 7. The bring-up sequence, and the safety check comes first

1. **With no gateware loaded and no cable plugged in**, power the radio with
   the board fitted and read `TP_JTAG_EN_N` and `TP_AUXIO_EN_N`. **Both must
   read HIGH.** That is the whole unprogrammed-board safety property and it is
   the first thing to confirm, before anything is driven.
2. Check `TP_+3V3` and `TP_+2V5`, and measure the radio's 3.3 V rail current
   with and without the board.
3. Read `TP_SB_PRSNT_IN` with the cable out (expect 0 V) and in, with the far
   end powered (expect 3.0 V).
4. Scope the forward clock chain: `TP_HL2_FWD_CLK_RAW`, `TP_HL2_FWD_CLK`,
   `TP_DI_FWDCLK`.
5. Bring up the forward link, then the reverse link, then the auxiliary link.
6. Only then enable JTAG over the cable, and only with no USB Blaster plugged
   into J5.
7. Leave the AUXIO drive path disabled unless you specifically want it. It can
   reach the radio's master-clock generator.
