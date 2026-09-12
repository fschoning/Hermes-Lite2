# gowin-bridge design notes — rev C

Assumptions, calculations, decisions and everything unverified. Read with
`PINMAP.md` (what connects to what), `ROUTING.md` (how to route it) and
`README.md` (how to build and order it).

Revision **C**, 2026-09-12. rev C replaces rev B's asymmetric link (6 lanes
forward at 153.6 Mbit/s, 3 lanes back at 307.2 Mbit/s, a single-ended
~10-25 Mbit/s command wire) with a **symmetric** one: every lane on every
cable now runs DDR at 153.6 MHz = 307.2 Mbit/s, 3 lanes each way, on two
fixed-direction cables, plus a third cable carrying a full-duplex, **307.2
Mbit/s (hardware)** auxiliary channel whose direction is set by a one-shunt
board strap. rev A (two dual-link DVI-D sockets) and rev B (three HDMI
sockets, the asymmetric link) are both in git history; nothing from either is
repeated here except where its reasoning still holds, and that is noted
section by section.

---

## 1. Data rates and unit intervals

Every lane, both directions, runs DDR at 153.6 MHz: two bits per clock, so
307.2 Mbit/s per lane, 3 lanes per cable, on two fixed-direction cables
(forward and reverse) plus one bidirectional auxiliary cable.

| Signal | Where | Rate | Unit interval |
|---|---|---|---|
| Forward clock | `OUT`/`IN` TMDS clock pair, cable 1 | 153.6 MHz | 6.5104 ns period |
| Forward lanes 0-2 | 3 pairs, cable 1 | 307.2 Mbit/s each (DDR against 153.6 MHz) | **3.2552 ns** |
| Reverse clock | `OUT`/`IN` TMDS clock pair, cable 2 | 153.6 MHz | 6.5104 ns period |
| Reverse lanes 0-2 | 3 pairs, cable 2 | 307.2 Mbit/s each | **3.2552 ns** |
| Auxiliary clock (group G1 or G2, whichever this board drives) | `AUX` TMDS clock pair, cable 3 | 153.6 MHz, own PLL each way | 6.5104 ns period |
| Auxiliary data (group G1 or G2) | `AUX` TMDS data pair, cable 3 | 307.2 Mbit/s hardware; **76.8 Mbit/s recommended, section 2.8** | 3.2552 ns (hw) / 13.02 ns (recommended) |
| Cable detect | HPD on `OUT`/`IN` sockets only | DC | - |

Unit interval at 307.2 Mbit/s: 1 / 307.2e6 = **3.2552 ns**. The 153.6 MHz
clock's own period is 1 / 153.6e6 = 6.5104 ns, and its half-period - the DDR
data unit interval - is the same 3.2552 ns. Both numbers come from one clock,
one PLL per direction.

3 lanes x 307.2 Mbit/s = **921.6 Mbit/s = 12 bits x 76.8 MSPS**: the whole
ADC stream, no compression, no framing overhead, **in each direction, on its
own cable**. rev B's reverse link already ran its three lanes at this rate
into DB1's LED pins (section 3.1); rev C makes the forward link identical to
it instead of running six slower lanes on a different clock domain, and adds
a third, symmetric cable purely for control.

The DS90LV047A driver / DS90LV048A receiver pair is rated **400 Mbit/s** per
channel, so every lane on the board now runs at 307.2 Mbit/s = **77 % of the
device rating** (307.2 / 400 = 0.768). rev B's forward lanes ran at 38 % of
this rating; rev C removes that headroom and runs every lane at the tighter
number the reverse link already had to meet.

Two single-ended-adjacent paths matter here because the rest of the document
leans on them:

* **The three reverse lanes land on HL2 DB1 pins 11, 15 and 17**, each
  carrying an LED wired as a 1 k pull-**up** to +3V3 through the LED (cathode
  at the FPGA pin; `hermeslite.net` D3/R72, D4/R73, D5/R74, all 1K). The
  receiver must **sink** (3.3 - 1.9) / 1000 = **1.4 mA**. DS90LV048A
  specifies `VOL` <= 0.3 V at 2 mA, so it is inside spec. Unchanged from
  rev B (section 3.1 has the full edge-rate derivation) - rev C changes
  nothing about this path except that it is no longer the only lane running
  at this rate.
* **HL2 PIN_80 (DB1 pin 4) is `VREFB5N0`**, and it now carries the auxiliary
  group G2 data pair - a **bidirectional** signal, not a fixed-direction
  forward lane as in rev B. At ~21 pF of pin capacitance plus about 6 pF of
  trace and header, a 2.5 V CMOS source of roughly 25 ohm gives a 10-90 %
  edge of **1.49 ns, which is 45.8 % of the 3.2552 ns unit interval**
  (1.49 / 3.2552 = 0.458). It works, with the narrowest eye anywhere in the
  design, and is **comfortable to about 135 Mbit/s**. This is a
  **calculation, not a datasheet guarantee**: the Cyclone IV handbook
  permits a VREF pin as a regular I/O when its bank carries no VREF-based
  standard (HL2 bank 5 carries only 2.5 V) and warns only qualitatively of
  "reduced performance of toggle rate and tCO", with **no numeric limit
  published anywhere**. Section 2.8 is why the gateware should not need this
  pin anywhere near 307.2 Mbit/s in practice.

**The OUT clock divider changed.** PIN_98 (the 3.3 V forward-clock pin)
still has to be brought down into the level translator's safe input range,
but the divider is now **100 ohm series + 660 ohm shunt (two 330 ohm
resistors in series)**, not rev B's 150 / 470 ohm:

| | Calculation | Result |
|---|---|---|
| High level at the translator A input | 3.3 x 660 / (660 + 100 + 25) *(25 ohm = PIN_98's own source impedance)* | **2.77 V** |
| Margin over the translator's `VIH` 1.63 V | | **1.14 V** |
| Headroom under the 3.0 V absolute maximum | | **230 mV** |
| Current drawn from PIN_98 when high | 3.3 / (660 + 100 + 25) | **4.2 mA**, inside its 8 mA drive setting |
| Thevenin source impedance at the A input | 100 \|\| 660 | **87 ohm** |
| Edge contribution into the translator's ~4 pF input | 2.2 x 87 x 4p | **0.77 ns**, i.e. 12 % of the 6.5104 ns clock period |
| Low level with the HL2 FPGA unconfigured *(the HL2's own LED pull-up: 1 k + LED forward drop, through the divider)* | (3.3 - 1.7) x 660 / (1000 + 100 + 660) | **0.60 V**, under the 0.875 V `VIL` max |

330 ohm (LCSC C25104) was used, in series pairs, rather than a single 470 ohm
resistor, because 330 ohm is the JLCPCB **Basic** part in that range and
470 ohm (LCSC C25117) is real but is not in JLCPCB's assembly library at
all. 100/330 alone (without the second 330 ohm) would have drawn
3.3 / (100 + 330 + 25) = **7.25 mA** from PIN_98 and forced it to its 16 mA
drive setting; the second 330 ohm exists to keep PIN_98 at its default 8 mA.

Section 4.2 has the full context for why this divider exists at all.

### 1.1 What rev C bought, and what rev B's asymmetry actually cost

rev B put six lanes forward at 153.6 Mbit/s and three back at 307.2 Mbit/s,
on the theory that halving the forward rate would buy margin. **It bought
nothing.** Both directions carried the same 921.6 Mbit/s of payload; the
reverse direction needed 307.2 Mbit/s per lane to move it in three lanes, so
that rate had to work regardless of what the forward link did. Deferring it
to one direction only hid the risk in the direction rev B analysed less,
rather than removing it.

rev C spends the pins that rev B's slower forward lanes freed up on a
**symmetric auxiliary cable**: a full-duplex, source-synchronous, 307.2
Mbit/s (hardware) control channel, in place of rev B's single-ended
~10-25 Mbit/s wire - a 12 to 30 times improvement even before the
recommended divided rate (section 2.8) is applied. It also moves the forward
link onto the same 3-lane, 307.2 Mbit/s geometry the reverse link already
used and that the gateware has **already simulated**
(`gateware/gowinlink/LINK_SPEC.md`, `GL_LANES = 3`), instead of running two
different lane geometries on two different clock domains at once.

---

## 2. The ROLE strap, and its failure analysis

### 2.1 The circuit

One 1x3 pin header (`ROLE`; board A `J9`, board B `J7`) with **one shunt**:

```
pin 1 = +3V3 --- pin 2 = ROLE --- pin 3 = GND
shunt on 1-2 => ROLE A          shunt on 2-3 => ROLE B
```

**One N-channel MOSFET** produces `ROLE_N` = NOT `ROLE`: gate on `ROLE`,
source to ground, drain on `ROLE_N`, loaded by the **10 k pull-up that is
fitted anyway**. A **10 k pull-up on `ROLE_N`** and a **100 k pull-down on
`ROLE`** give both nets a defined level even with no shunt fitted at all.

The part is **Alpha & Omega AO3400A, LCSC C20917**, SOT-23, **Basic** tier in
JLCPCB's assembly library, about 890,000 in stock, about $0.08, pin 1 gate /
pin 2 source / pin 3 drain. Its gate threshold is **1.45 V maximum**, so a
3.3 V strap drives it with **1.85 V of margin**. **Do not substitute the
cheaper 2N7002:** its threshold is specified up to 2.5 V, too close to a 3.3 V
drive.

**Why a MOSFET and not a logic gate.** A single-gate inverter was the first
choice. It was dropped on cost alone: **no 74x1G04, 1G00, 1G02, 1G14 or 1G07
of any brand, family or package is a Basic part in JLCPCB's library**, checked
across all ten manufacturers they list, so one gate would have cost the $3.07
per-unique-Extended-part fee on the Economic assembly tier this board is
ordered on. `COST.md` 5a has the money.

**What the MOSFET gives up, examined point by point:**

* **`ROLE_N`'s high state is now passive**, supplied by the 10 k pull-up
  rather than actively driven. **Acceptable**: `ROLE_N` drives only CMOS
  enable inputs - one LVDS driver `EN` and one translator `OE` per board -
  whose input leakage is nanoamps to a few microamps. At a worst case of
  20 uA the pull-up drops 0.2 V, giving 3.1 V against enable thresholds
  around 2.0 V.
* **The pull-up's rise time is slow.** **Irrelevant**: `ROLE_N` is a static
  level set once by a jumper and never switched in operation. Nothing on
  either board ever sees an edge on it.
* **The low state is better, not worse.** The MOSFET's on-resistance is tens
  of milliohms, so with the 0.33 mA that flows through the 10 k load the drain
  sits within microvolts of ground - cleaner than a logic gate's specified
  output low. The standing current is unchanged, because a logic inverter
  pulling the same node down through the same pull-up drew the same 0.33 mA.
* **No hysteresis regression.** The part it replaces, SN74LVC1G04, is a
  **plain** inverter with no Schmitt input either, so nothing is lost. And
  `ROLE` is never in transition: it is hard 3.3 V or hard 0 V through a shunt,
  or 0 V through the 100 k pull-down when no shunt is fitted, so the input
  never dwells in the threshold region where a soft transfer characteristic
  would matter.
* **The fail-safe direction is unchanged**, which is the point that matters
  most. A missing, dead or unpowered device leaves `ROLE_N` pulled **high** by
  the 10 k resistor, which **disables** the host-facing auxiliary port. That
  is the auxiliary-disabled state: the link fails to work and nothing is
  stressed. It can never enable a port.
* **Power-up is also safe, and this is new with the MOSFET.** It stays off
  until its gate passes about 1.45 V, so during the supply ramp `ROLE_N` is
  held high by the pull-up - again the auxiliary-disabled state.
* **What is genuinely weaker:** the input threshold is a device parameter with
  a manufacturing spread, rather than a specified fraction of the supply rail
  as a logic gate guarantees. For a jumper level that is either 0 V or 3.3 V,
  with 1.85 V of margin to the worst-case threshold, this does not matter.

**The 10 k pull-up is now doing two jobs**, and both are load-bearing: it is
the MOSFET's drain load - without it the drain has no high state at all - and
it is the fail-safe. `tools/check_netlist.py` asserts it is a pull-UP and that
there is no pull-down, and also that the source is grounded, because a MOSFET
inverter only inverts with its source at ground.

### 2.2 Why an inverter, and not a second link or a double-pole jumper

The scheme needs a complementary *pair* whose two halves can never disagree.
A 2x3 header with two shunts, wired as a double-pole changeover, looks like
the obvious way to get `ROLE` and `ROLE_N` from one header - and it is
wrong. A user can put one shunt in the A position and the other in the B
position, and one of the four resulting combinations - **both levels low** -
enables a host-facing translator port for group G2 **while the gateware
believes it is in ROLE B and is driving those same pins as outputs**. That
is CMOS against CMOS on PIN_72 and PIN_80, tens of milliamps.

One shunt plus one gate makes the complement a property of the circuit
rather than of the user's attention, for the cost of one SOT-23-5 part and
about nine cents.

### 2.3 The invariant, stated so it can be checked

For each auxiliary group, the LVDS driver's active-HIGH `EN` and the
host-facing buffer port's active-LOW `OE` are **the same net**. So a group
is either driven onto the cable (`EN` high, therefore `OE` high, therefore
the host-facing port off) or driven toward the host (`EN` low, therefore
`OE` low, therefore the driver tri-stated) - never both, for **any** level
on that net, including a stuck or floating one.

On board A: G1 driver `EN` = `ROLE`, and the translator port carrying G1
toward the HL2 has `OE` = `ROLE`; G2 driver `EN` = `ROLE_N`, and its port
has `OE` = `ROLE_N`. Board B is identical, with its own driver/buffer pair.
`tools/check_netlist.py` asserts exactly this on both boards and enumerates
both states of the strap net.

### 2.4 Why LVDS driver against LVDS driver is harmless

An LVDS driver is a **current source**, not a voltage source: the
DS90LV047A steers about 3.5 mA into a 100 ohm load to make its 350 mV swing,
and its short-circuit output current (`IOS`) is specified and internally
limited, of order 10 mA and bounded well below 25 mA. Two drivers fighting
on one pair present each other with a current source, not a low-impedance
rail, so the pair settles at some intermediate differential voltage and the
data is garbled. Dissipation per output stays in the milliwatts. **The
signal is lost; nothing is stressed.**

### 2.5 Why the CMOS case is prevented

The dangerous case is a host-facing buffer output fighting an HL2 (or
Gowin) output on a shared auxiliary pin - two CMOS push-pull stages, tens of
milliamps. The strap read - on PIN_89 for board A, on J14 pin 34 for board B
- is what prevents it. The gateware follows `ROLE`, so whenever a board's
buffer is driving an auxiliary pin the gateware has already made that pin an
input, and whenever the gateware drives the pin the buffer port for it is
disabled by the same `ROLE` level. **They always agree because they are the
same wire.**

### 2.6 The failure analysis, case by case

| Fault | Consequence |
|---|---|
| Shunt in the wrong position, both boards the same role | Both drive the same group, both receive the other. LVDS-against-LVDS (section 2.4) garbles both directions. No CMOS contention. The link just does not come up. |
| No shunt at all | The 100 k pull-down makes `ROLE` read low = ROLE B: a **defined state**, not a floating inverter input (a floating CMOS input would draw crowbar current). Board B ships ROLE B anyway, so on board B a lost shunt is not even a change. |
| Inverter missing, unpowered or dead | The 10 k pull-up makes `ROLE_N` read high, which **disables** the G2 host-facing port. The G2 driver is left enabled and drives whatever the translator presents from the (pulled-down) HL2 pins onto the cable, where the far end's G2 driver fights it - LVDS against LVDS, harmless (section 2.4). The auxiliary link does not work; nothing is stressed. **The pull direction is the whole point: a pull-down would have enabled the port instead.** |
| Both boards strapped correctly but the gateware ignores the strap | The one case the hardware cannot defend against. The gateware **must** set its four auxiliary pin directions from the strap it reads. |

### 2.7 Board B needed a part the first write-up of rev C did not give it

Board A tri-states its auxiliary receive path inside the level translator it
needs anyway for the HL2's 2.5 V bank pins (`U7`, `U8`). Board B has no
level shifting to do - everything on it is 3.3 V - so it had **nothing to
tri-state in**, and its always-on auxiliary receiver would then drive the
two J14 pins the gateware drives as outputs in that role: CMOS against CMOS,
exactly the failure this section exists to prevent. That is a defect found
while writing rev C, not a feature: the first draft of the pin map gave
board B an auxiliary receiver with no way to get off the bus.

Board B therefore carries **one SN74AVC4T245PWR (LCSC C81461, $0.3096 at
qty 10)**, `VCCA` = `VCCB` = 3.3 V, used purely as **two independently gated
2-channel buffers** - it adds no new unique part to the panel, because board
A already carries two of them for its own 2.5 V shift. The alternative
considered and not taken: a 74LVC125A quad buffer with four independent
enables would do the same job in one smaller, cheaper package, but it would
have added a **unique** part to the panel, where the AVC4T245 does not.

### 2.8 Running the auxiliary channel at a divided rate

**The gateware should clock the auxiliary lanes at a divided rate: 38.4 MHz
DDR = 76.8 Mbit/s per lane** is the suggested starting point, **not** 153.6
MHz DDR.

The reason is PIN_72, the G2 return clock. It arrives on an ordinary I/O,
not a dedicated clock input, because both of the HL2's dedicated clock
inputs are already spent - PIN_88 on the reverse link, PIN_89 on the strap
read. A regular I/O can drive the Cyclone IV global clock network but
**cannot feed a PLL input**, so the sampling phase cannot be adjusted. At
76.8 Mbit/s the unit interval is **13.02 ns**, so PIN_80's 1.49 ns edge
(section 1) and whatever static phase error the cable and the clock network
contribute are a small fraction of it and no phase adjustment is needed. At
307.2 Mbit/s the unit interval is 3.2552 ns and the sampling phase would
have to be right by luck.

**The hardware stays capable of 307.2 Mbit/s each way**, and nothing on the
board limits it to less - this is a gateware choice, revisitable once the
real phase is measured. A control channel needs kilobits; 76.8 Mbit/s is
already four orders of magnitude more than the job requires.

**One optimisation was deliberately not taken.** The two auxiliary clock
lanes could be reclaimed by timing the auxiliary data off cable 1's or
cable 2's clock instead, which would double the auxiliary payload. It was
not done because the inter-cable phase is unknown, and it would add risk for
bandwidth that is not needed. Recorded here as a possible future
**gateware-only** optimisation - it needs no board change - so whoever wants
it later knows it was considered and rejected on risk, not overlooked.

PIN_72's net reaches the FPGA only through the HL2's jumper **J25** (which
must be **closed**) and also lands on uFL pad **CL8**, an unterminated stub
on the HL2 that no bridge board can remove. In ROLE B the HL2 drives a
153.6 MHz clock out through that stub - the worst case of the four auxiliary
pins. If only the G2 direction misbehaves at speed, the stub is the first
suspect. Board A's cuttable link `SL_D0` isolates board A from the net but
does not remove the stub itself.

---

## 3. Termination, edge rates and the two tight paths

* **Every LVDS receiver input pair gets a 100 ohm resistor footprint on the
  board**, within 5 mm of the receiver pins. Both boards now have **eight**
  positions: four for the fixed-direction `IN` socket (always fitted) and
  four for the `AUX` socket (only the two this board *receives* in its
  shipped role are fitted - section 5.4). rev B's boards were asymmetric
  here (board A four, board B eight); rev C's are the same on both boards
  because both now carry an `AUX` receiver. There is no termination at a
  driver output, which is correct for LVDS.
* **LVDS differential swing** 250-450 mV (DS90LV047A `VOD1` into 100 ohm),
  common mode 1.125-1.375 V, transition about 1 ns. At 307.2 Mbit/s - now
  every lane, not just the reverse ones - the edge occupies about 31 % of a
  unit interval (1 / 3.2552 = 0.307).
* **Cable.** An HDMI cable is 100 ohm differential, individually shielded
  per pair, and qualified far above these rates - even HDMI 1.0 runs
  1.65 Gbit/s per pair. Cable length is not an electrical limit here; the
  400 Mbit/s driver rating is. Anything up to a few metres is fine.
* **Every single-ended run is under 25 mm** by layout rule, with a series
  resistor where one is useful.

### 3.1 Tight path one: the three reverse lanes into the HL2's LED pins

Unchanged from rev B, because the reverse link already ran at this rate.
Reverse lanes 0-2 land on **DB1 pins 11, 15 and 17 at 307.2 Mbit/s**, and
each of those FPGA pins carries an LED whose anode goes through 1 k to
**+3V3** (verified in `hermeslite.net`: D3/R72, D4/R73, D5/R74, all 1K).

* The LED's junction capacitance (20-50 pF) is **in series with the 1 k**,
  so at 150 MHz the branch looks like 1 k resistive, not capacitive - the
  LED does not load the edge. What loads it is the FPGA pin itself (7 pF for
  a right-side Cyclone IV pin) plus the header and trace, roughly 12-15 pF.
* A 3.3 V CMOS output with about 50 ohm of effective source impedance into
  15 pF gives a 10-90 % rise of about **1.65 ns, which is 51 % of the
  3.2552 ns unit interval.** That works, and remains the tightest margin on
  the board outside the auxiliary channel.
* The receiver must also **sink 1.4 mA** when low ((3.3 - 1.9) / 1000).
  DS90LV048A specifies `VOL` <= 0.3 V at 2 mA, so it is inside spec.
* The series parts are **0 ohm by default** on 0402 pads, so a damping value
  can be substituted without a respin - but do not raise them much: at
  22 ohm the rise grows to about 1.9 ns.

**Unverified:** whether the Cyclone IV C8 fabric can actually capture
307.2 Mbit/s DDR on ordinary bank-6 inputs. The device has one input
register per IOE, so DDR input needs soft logic clocked at 153.6 MHz. This
now gates **every** lane in the design, not just the reverse link, because
rev C runs the forward lanes at the same rate.

### 3.2 Tight path two: PIN_80, the 21 pF VREF pin, now bidirectional

rev B put a fixed-direction forward lane on PIN_80. rev C puts the
**auxiliary group G2 data pair** there instead - `AX_D2_P/N`, bidirectional,
an input in ROLE A (how board A ships) and an output only when this same
board design is strapped ROLE B (the two-radio case). Section 1 has the
edge-rate derivation: **1.49 ns, 45.8 % of the unit interval, comfortable to
about 135 Mbit/s**, a calculation and not a datasheet guarantee.

* **Consequence for the layout: keep the trace from DB1 pin 4 to the
  translator's A-side input as short as physically possible.** This remains
  the one single-ended net on board A where every millimetre counts.
* Per-lane delay is not a problem - the Gowin's `IODELAY` centres each
  lane's eye independently (`ROUTING.md` section 4.2). What the extra
  capacitance costs is **eye width**, not position.
* **Section 2.8's recommendation to run the auxiliary channel at
  76.8 Mbit/s, not 307.2 Mbit/s, is what makes this tight path comfortable
  in practice** rather than merely working: at a 13.02 ns unit interval, a
  1.49 ns edge is a small fraction of the eye instead of half of it.

---

## 4. The 2.5 V / 3.3 V level cases

### 4.1 The problem, stated with the numbers

| | Value | Source |
|---|---|---|
| Cyclone IV 2.5 V LVCMOS output, `VOH` min | **2.0 V** at `IOH` = -1 mA | Cyclone IV Device Datasheet, Table 1-15 |
| DS90LV047A input `VIH` min | **2.0 V** | TI SNLS044D, Electrical Characteristics |
| **Guaranteed margin** | **0 mV** | |

Board A's 2.5 V-bank signals into the LVDS drivers are no longer only
"outputs": four are fixed outputs (PIN_76, 77, 83, 86) and four more are the
**bidirectional** AUX pins (PIN_72, 80, 85, 87), which drive an LVDS driver
input whenever this board is the one driving that group. PIN_98's forward
clock is the one 3.3 V-bank exception, handled by its own divider
(section 1). So this is still not an edge case: it is the main signal path,
on every 2.5 V-bank pin that ever originates at the HL2, output or
bidirectional-when-driving alike.

Four candidate resolutions were considered in rev A/B; nothing here changed
in rev C.

**(a) An LVDS driver with LVTTL-specified inputs, `VIH` min 1.7 V.**
Rejected: no such part was found. `VIH` = 2.0 V is the TTL threshold and it
is what every discrete LVDS driver in the LCSC catalogue specifies -
DS90LV047A, SN65LVDS047, SN65LVDS31, DS90LV031A, ADN4667 are all 2.0 V. The
1.7 V figure is the *FPGA* `3.3-V LVTTL` I/O standard, not a logic-family
spec; it is available on the Gowin side (section 4.5) but not in a driver
chip.

**(b) An LVDS driver specified for a 2.5 V supply.** Rejected: no quad LVDS
driver in the catalogue operates below 3.0 V. DS90LV047A, SN65LVDS047,
SN65LVDS9637 and DS90LV031A are all specified 3.0-3.6 V.

**(c) A dual-supply translator in front of the drivers.** **CHOSEN.**
Section 4.2.

**(d) Argue that `VOH` approaches `VCCIO` at microamp load.** Kept as the
documented fallback, section 4.3, with bypass links fitted for it.

### 4.2 The chosen solution: one SN74AVC8T245, and what it costs

**U1 on board A is an SN74AVC8T245PWR (TSSOP-24, LCSC C465742 - rev B's
C53535 does not exist), `VCCA` = 2.5 V, `VCCB` = 3.3 V, `DIR` tied to
`VCCA` (A to B), `OE` low.**

| | Value |
|---|---|
| A-side `VIH` min | **0.65 x VCCA = 1.63 V** |
| Cyclone IV 2.5 V `VOH` min | 2.0 V |
| **Guaranteed margin** | **370 mV**, up from 0 mV |
| B-side output | 3.3 V CMOS, straight into the driver's 2.0 V threshold with 1.3 V of margin |
| Channels used | **All 8**: OUT clock (through the divider) + 3 OUT lanes + all 4 AUX pins |
| Rated data rate | 380 Mbit/s at these rails; the fastest signal through it is now 307.2 Mbit/s, i.e. **81 % of rating** (307.2 / 380 = 0.808) - up from rev B's 40 %, because every lane through this part now runs at the rate only the reverse link used to |
| Propagation delay | about 1.1 to 3.7 ns over process and temperature |
| Channel-to-channel skew within one package | about 0.5 ns |

**All eight forward-and-auxiliary signals go through this one package**, for
the same reason as rev B: propagation delay is a part-to-part property, so
putting them all in one package turns a 2.6 ns part-to-part uncertainty into
a 0.5 ns channel-to-channel one.

**Forward clock A is still the awkward one.** PIN_98 is a 3.3 V output, and
the SN74AVC8T245's A-side absolute maximum is `VCCA` + 0.5 V = **3.0 V**.
Feeding it 3.3 V directly is out of spec. The divider changed from rev B's
150 / 470 ohm to **100 ohm series + 660 ohm shunt (two 330 ohm in series)**,
because 470 ohm (LCSC C25117) turned out not to be in JLCPCB's assembly
library while 330 ohm (LCSC C25104) is a Basic part; the full table is in
section 1.

**Pull-downs.** Seven of the eight 2.5 V-bank signals through U1 get a 10 k
pull-down so they are defined while nothing drives them - the HL2 FPGA
unconfigured, or (for the four bidirectional AUX pins) the local translator
port disabled by the strap: the **3 OUT lanes** and the **4 AUX pins**.
**Clock A deliberately does not get one**, for the same reason as rev B: the
HL2's own LED pull-up on DB1 pin 9 plus the divider already define it at
0.60 V, and adding a 10 k pull-down to a net that already has a 1 k pull-up
through an LED would park it in the translator's forbidden band between
`VIL` 0.875 V and `VIH` 1.63 V.

### 4.3 The fallback, and why the bypass links exist

**Eight DNP 0 ohm links** short each A-side net to its B-side net - the same
count as rev B, now covering the OUT clock, 3 OUT lanes and 4 AUX pins
instead of two clocks and six lanes. Fit all eight, remove U1 and remove the
divider's second 330 ohm leg, and the HL2's 2.5 V-bank pins drive the LVDS
drivers directly - argument (d):

| | Value |
|---|---|
| DS90LV047A input current | **-10 to +10 uA** max (`IIH`/`IIL`, SNLS044D) |
| Voltage on the line at that current | **>= 2.375 V** (`VCCIO5` min); 10 uA through a ~50 ohm source is 0.5 mV |
| **Actual margin against `VIH` 2.0 V** | **>= 375 mV** |

Ship the translator; keep the links so that if the bench says the
translator is the problem, it can be removed in ten minutes.

### 4.4 3.3 V outputs into the HL2's two input-only 2.5 V pins

HL2 **PIN_88** (DB12 pin 6, reverse clock, 153.6 MHz) and **PIN_89** (DB12
pin 5) are dedicated inputs in bank 5 at `VCCIO` 2.5 V, with the PCI clamp
diode on by default - a 3.3 V driver held high would inject DC into the
HL2's 2.5 V rail. Not acceptable.

**What changed in rev C: PIN_89 no longer carries a command received from
the cable.** rev B's "slow in" line is gone; PIN_89 now carries the **ROLE
strap level, generated locally on this same board** (section 2) and
translated 3.3 V -> 2.5 V so the HL2 gateware can read its own role. The
translator that does this is now split across **two** packages instead of
rev B's one:

* **U7**, port 1 (always on) = the reverse-link clock into PIN_88; port 2 =
  AUX group G2 toward the HL2, `OE` = `ROLE_N` (section 2.3).
* **U8**, port 1 = AUX group G1 toward the HL2, `OE` = `ROLE`; port 2
  unused.
* The ROLE level itself travels on U7 port 1 alongside the reverse clock
  (`ROLE` -> `X_ROLE25` -> PIN_89), always enabled, because the HL2 must be
  able to read its role regardless of which AUX group this board is
  driving.

Both are **SN74AVC4T245PWR (LCSC C81461)** - the same part number as rev
B's single U5, unchanged because nothing about its rating needed to change.
The fastest signal through either is still the 153.6 MHz reverse clock
(equivalent to 307.2 Mbit/s of toggling) against its 380 Mbit/s rating, i.e.
**81 % of rating** - worth a scope check at bring-up, same as rev B.

A resistor divider was rejected on the same numbers as rev B: the
DS90LV048A output is specified only to `VOH` 2.7 V at -0.4 mA and `VOL`
0.3 V at 2 mA, so it cannot drive a low-impedance divider light enough to
resolve a 3.2552 ns unit interval.

`R_SL_VLVDS` (not fitted) can still tie the translators' 2.5 V side to the
HL2's own `Vlvds` rail instead of the on-board LDO, at the cost of about
10 mA from the HL2's TPS730 whose headroom is **unverified**.

### 4.5 HL2 2.5 V output into a Gowin 3.3 V input (the slow out)

Unchanged from rev B. PIN_86's status UART goes straight down cable 1 to
the Gowin with a 100 ohm series resistor and no buffer. **`IO_TYPE=LVTTL33`**
(`VIH` min 1.7 V) gives **300 mV of guaranteed margin**, where `LVCMOS33`'s
2.0 V would give zero. `PINMAP.md` 5.2 marks the destination pin `LVTTL33`
with `HYSTERESIS=NONE` explicitly - the Gowin's 400 mV of hysteresis at
3.3 V is larger than the whole margin.

### 4.6 Board B needs no voltage translation - but it does need one gating buffer

The Gowin's Bank 4 is at 3.3 V and so are board B's drivers and receivers,
so every interface on board B is still 3.3 V to 3.3 V: no level-shifting
translator is needed there, same as rev B. **What rev C adds is `U6`, a
gating buffer for the auxiliary pins** - not for voltage, but to stop board
B's always-on auxiliary receiver from driving a Gowin output pin. Section
2.7 has the full reasoning; it is the same invariant (driver `EN` and buffer
`OE` on the same net) as board A's U7/U8, just implemented with both of U6's
rails tied to 3.3 V instead of two different rails.

---

## 5. The AC-coupling option

Fitted as an **option, not fitted by default.** Every received `IN`-socket
pair carries, per leg: a **100 nF 0402 series capacitor (DNP)** in parallel
with a **0 ohm 0402 link (FITTED)**. Both boards now have four such pairs
(section 3).

To convert a pair to AC coupling: remove its two 0 ohm links, fit its two
100 nF capacitors, fit its two 4k7 bias resistors, and fit the shared
`VBIAS` divider (one per receiver chip).

### 5.1 Why it is an option and not the default

Unchanged from rev B. **For:** coupling capacitors block any DC path
between the two boards, which matters because the HL2 and the Tang dock have
separate power supplies and are joined only by cable shields. **Against, and
decisive:** AC coupling needs DC-balanced data, and the current gateware's
scrambler is explicit that it exists "to spread the spectrum of near-static
ADC data next to an HF receiver, not DC balance" (`LINK_SPEC.md` section 5).
A quiet antenna gives a near-constant ADC output, which is exactly the worst
case for baseline wander.

So: provide the footprints and the links, default to DC, and let the option
be taken later.

### 5.2 Component values and what was assumed

**Coupling capacitor: 100 nF 0402 (X7R, 16 V or better).** Unchanged from
rev B - the arithmetic (5 us RC time constant, 0.65 % droop over a 5-bit run
at 153.6 Mbit/s, negligible reactance at 15 MHz) does not depend on which
cable the pair is on, only on the 100 ohm termination it sees.

**Bias network: 10 k / 4k7 divider, 4k7 per leg.** This changed from rev
B's 1k8 / 1k0:

| | |
|---|---|
| Target receiver common mode | mid-range (DS90LV048A accepts 0.05 to 2.35 V) |
| Why it changed | rev B's two LCSC numbers turned out to be different values than the BOM claimed: **C25867 is 1.5 k, not 1k8; C21190 is 0603, not 0402.** Neither could be trusted, so the divider was reworked from confirmed values |
| Divider | 10 k from +3V3, 4k7 to GND -> 3.3 x 4.7 / 14.7 = **1.055 V** |
| Divider current | **none, steadily.** The per-leg 4k7 bias resistors sit in common mode, so the divider carries no DC load current; its higher 3.2 k Thevenin impedance (10 k \|\| 4k7) therefore costs nothing |
| Bias resistor per leg | **4k7**, unchanged |
| Effect on the differential impedance | 100 \|\| (2 x 4700) = **98.9 ohm**, a 1.1 % error, unchanged |

Still bypassed with 100 nF; still not fitted by default.

**The slow-line ringing damper changed from 33 pF to 22 pF.** LCSC C1555,
used on the status-UART lines, was assumed to be 33 pF in rev B's BOM and is
really **22 pF**. 22 pF into 100 ohm is 2.2 ns. Not fitted by default.

### 5.3 The AUX pairs deliberately do not get this option

**AC coupling is not offered on the four auxiliary pairs, for two
reasons:**

1. A series 0402 in the middle of a pair that is **driven half the time** is
   an impedance discontinuity on the outgoing signal.
2. A series capacitor would break the driver's DC path to the cable and
   leave the **far end's** receiver common mode undefined - on a
   bidirectional pair there is no always-DC-coupled end to set it, unlike a
   fixed-direction pair where the far end is always the driver.

So on an auxiliary pair the connector pin goes **straight** to the node
where the driver output and the receiver input meet, and the only fitted
part is the differential termination.

### 5.4 The strap-selected termination

Each of the four `AUX` pairs has a 100 ohm differential termination
position. Fit the two for the pairs this board **receives** in its shipped
role: board A ships ROLE A, so it fits the `D1` and `D2` pairs (group G2);
board B ships ROLE B, so it fits the `CLK` and `D0` pairs (group G1). It is
a **build-time choice, not an electrical one** - a switched 100 ohm would
need an analogue switch.

If both ends terminated a driven pair, the driver would see 50 ohm and the
differential swing would halve from about 350 mV to about 175 mV against the
receiver's 100 mV threshold - **75 mV of margin over a 2 m cable, which is
not enough.** Hence the links, and hence fitting only the receiving end's
two.

---

## 6. Power

### 6.1 Board A

**Board A now carries 10 ICs on 48 x 66 mm** - up from rev B - because the
auxiliary channel added a second AUX driver (U4), a second AUX receiver
(U6), a second 2.5 V translator (U8) and the ROLE inverter (U11). The table
below is **rev B's total, carried forward as a stale lower bound**; it does
not yet include the new parts, and the real rev C total needs recomputing
and then measuring (section 11).

| Load | Current at 3.3 V |
|---|---|
| U2, U3, U4 DS90LV047A drivers (rev B figure for 2 full-load packages; rev C has 3, 2 only partly loaded - **not yet recomputed**) | 60 mA (stale) |
| U5, U6 DS90LV048A receivers (rev B figure for 1 package; rev C has 2 - **not yet recomputed**) | 25 mA (stale) |
| U1 SN74AVC8T245, eight channels switching into 5 pF at up to 76.8 MHz (`C x V x f` = 5p x 3.3 x 76.8M = 1.27 mA each) plus quiescent | 12 mA |
| U9 ME6211C25 LDO, output ~6 mA plus quiescent (feeds U1's A side and U7/U8's B side) | 7 mA |
| U7, U8 SN74AVC4T245, A side (rev B figure for 1 package; rev C has 2 - **not yet recomputed**) | 1 mA (stale) |
| U11 AO3400A, the `ROLE_N` inverter | **0.33 mA when `ROLE_N` is low, 0 when it is high** - and that current is the 10 k pull-up's, not the MOSFET's, so it was already in the budget before the inverter existed. The device itself draws gate leakage only, in nanoamps. This is the one new part whose consumption needs no estimate. |
| Receiver outputs sinking the HL2's three LED pull-ups (1.4 mA each, average ~50 % duty) | 2 mA |
| Pull-ups, pull-downs, HPD dividers | 5 mA |
| **rev B total (stale, carried forward)** | **~112 mA** |

Two extra loads on the HL2 that are **not** on board A's 3.3 V rail:

* **4.2 mA out of PIN_98** through the clock-A divider (section 1,
  recalculated for the new 100/660 divider - was 5.1 mA in rev B). Inside
  the pin's 8 mA drive setting.
* **1.4 mA into each of DB1 pins 11, 15, 17** sunk by board A's receiver,
  current the HL2's own +3V3 rail sources through the LEDs. Unchanged from
  rev B.

**Supply: DB1 pins 19/20, the HL2's +3V3 rail, selected by header J6
(default shunt on 1-2).** Unchanged from rev B: the +3V3 regulator's part
number and current rating were not identified, and it is still the single
most important electrical unknown, now against a **higher and unrecomputed**
load. **Measure the HL2's 3.3 V rail with board A plugged in before trusting
it.**

**The alternative, and the decision not to make it the default.** Unchanged
from rev B: the `IN` socket's HDMI +5 V pin reaches an AMS1117-3.3 (U10)
through the DNP link `SL_5V`; move J6's shunt to 2-3 to use it. U10 and
`SL_5V` are both not fitted by default, because the two-radio configuration
has no Gowin and therefore no 5 V source at all, so board A has to be able
to run from its own HL2 anyway.

### 6.2 Board B

Board B gained one IC in rev C - **U6**, the strap-gated auxiliary buffer
(section 2.7) - which is likewise **not yet in the table below**.

| Load | Current at 3.3 V |
|---|---|
| U1, U2 DS90LV048A (`ICC` max ~25 mA each) | 50 mA |
| U3, U4, U5 DS90LV047A (rev B figure for 1 full-load package; rev C has 3, 2 only partly loaded - **not yet recomputed**) | 30 mA (stale) |
| U6 SN74AVC4T245, both channels used | **not in rev B's table - new load, not yet estimated** |
| Eight receiver outputs into a Gowin pin (~8 pF) at up to 76.8 MHz | 16 mA |
| Driver input pull-downs, HPD pull-ups, odds and ends | 10 mA |
| **rev B total (stale, carried forward)** | **~106 mA** |

From J14 pin 11 (`5V_Peripheral`) through **U7, an AMS1117-3.3 in
SOT-223**. **How much current J14 pin 11 can actually supply is still
UNVERIFIED**, unchanged from rev B.

---

## 7. Mechanical - and this is still why rev B, and now rev C, exist

### 7.1 Why rev A did not fit, in one line

Unchanged from rev B. Two right-angle dual-link DVI-D receptacles are
**37.83 mm wide each, so 76 mm side by side**, and the corridor left by the
N2ADR filter board is **50 mm**. rev A's answer was an L-shaped 80 x 66 mm
board with a tab overhanging the filter board; rev B's answer, kept in rev
C, is three mini HDMI sockets at **11.20 mm** each.

### 7.2 The corridor, and where board A sits in it

Unchanged from rev B - this is HL2 board geometry, not gowin-bridge
geometry, and rev C did not move board A.

From `hardware/hl/hermeslite.kicad_pcb`, whose outline is x 70.00-169.95,
y 40.00-140.00 (a 100 x 100 mm board):

* `DB1` is footprint `HERMESLITE:10x2` at **(75.31, 89.39) rotated 270**. For
  270 degrees KiCad gives absolute = (module_x - pad_y, module_y + pad_x), so
  pin 1 (local -11.43, +1.27) lands at **(74.04, 77.96)** and pin 20 (local
  +11.43, -1.27) at **(76.58, 100.82)**. Odd pins at x 74.04, even at 76.58,
  pin 1 at the y = 40 end.
* `DB12` is `HERMESLITE:3x2` at **(83.50, 90.00), not rotated**: pin 1 at
  (83.50, 87.46), pin 6 at (86.04, 92.54). Odd pins at x 83.50, even at
  86.04, rows at y 87.46 / 90.00 / 92.54.
* **The two headers are not on a common 0.1 inch grid.** DB12's first column
  is 6.92 mm inboard of DB1's inner row and its first row is 9.50 mm toward
  y = 140 from DB1 pin 1.
* The **N2ADR filter board** (`hardware/companions/n2adr/n2adr.kicad_pcb`) is
  100 x 49.9 mm; matching its 1x20 header `CN2` to the HL2's `DB7` maps the
  filter board's x axis to the HL2's y axis and puts the filter board over
  **HL2 x 120.05 to 169.95, full y range.**

**So the free corridor is HL2 x 70.00 to 120.05 = 50.05 mm.** Board A is
**48.00 x 66.00 mm** at HL2 x 70.50-118.50, y 74.00-140.00, leaving **1.55
mm** to the filter board's edge - a plain rectangle entirely inside the
corridor, with no mechanical overlap, so the filter board can stay fitted.

`HL2_ORIGIN` in `tools/gen_gowin_bridge.py` is the one constant that sets
this; the board can slide anywhere from HL2 x 70.00 to 72.05 with a one-line
change.

### 7.3 Do three mini HDMI sockets fit? Yes. Do three cables? Almost certainly.

Unchanged geometry from rev B (`MINI_PITCH = 17.40 mm` in the generator),
with the middle socket now called `AUX` instead of `OUT 2`, since it carries
the bidirectional auxiliary channel rather than a second fixed-direction
one.

**The sockets: yes, comfortably.** XKB A71-05H4-111N1, from its drawing:
body **11.20 mm wide x 7.50 mm deep x 3.10 mm high**, front face 0.50 mm
beyond the PCB edge so it occupies 7.00 mm of board.

| | |
|---|---|
| Socket centres, local x | **6.60, 24.00, 41.40** (pitch **17.40 mm**) |
| Bodies occupy | 1.00-12.20, 18.40-29.60, 35.80-47.00 mm |
| Gap between adjacent bodies | **6.20 mm** |
| Outermost copper (a shell-leg pad) | 0.55 mm from the board edge, against JLCPCB's 0.30 mm minimum |
| Largest pitch the 48 mm board allows | **17.65 mm** at the 0.30 mm limit; 17.40 was chosen to keep 0.55 mm |

**The cables: the binding constraint, and it is not fully verifiable.** The
moulded boot on the end of an HDMI cable is wider than the connector shell,
and **no manufacturer or distributor publishes a dimensioned drawing of a
mini HDMI cable's boot.**

| | Width | Source |
|---|---|---|
| Full-size Type A plug **boot** | **20.8 mm** (x 10.9 mm high) | PIC Wire assembly drawing 11012-4946 rev 7 sheet 2; corroborated by L-com's 20.8 mm recommended panel opening |
| Full-size Type A plug **shell** | 13.9 mm | same |
| Mini Type C plug **shell** | **10.42 mm** (+0.03/-0.04) x 2.42 mm | Multicomp 60S019P-301N-B2 datasheet |
| Mini Type C plug **boot** | **not published** | - |

| Estimate | Method | Mini boot width | Clearance at 17.40 mm pitch |
|---|---|---|---|
| Pessimistic | same absolute wall thickness: 10.42 + 6.9 | **17.32 mm** | **+0.08 mm** |
| Proportional | wall scales with the part: 20.8 x 10.42 / 13.9 | **15.59 mm** | **+1.81 mm** |

**Three cables therefore fit under both estimates, but only just under the
pessimistic one.** Measure the boots on the cables you intend to use with
calipers.

**Staggering the sockets in depth does not rescue this**: a Type A boot is
**44.2 mm long** and a mini one is comparable, so with any depth offset a
66 mm board still has the boots side by side over 90 % of their length.

**If the measured boots are too wide**, in order of preference:

1. **Buy narrower cables.** The boot is the whole problem and it varies a
   lot between brands; camera-type mini HDMI cables tend to be slim.
2. **Drop the AUX cable and fit only `OUT` and `IN`.** In rev C this is no
   longer "the 3-lane fallback" the way it was in rev B: 3 lanes at
   307.2 Mbit/s is now the only forward and reverse geometry there is. What
   dropping the middle socket actually costs is the fast auxiliary control
   channel (section 2), not the ADC link, since forward and reverse already
   run on their own dedicated cables and do not need the middle socket at
   all.
3. **Make a 100 mm mini-to-mini pigtail with a right-angle plug** on the
   board end for the middle socket.
4. **Reduce `MINI_PITCH` and shift `HL2_ORIGIN`** in the generator: moving
   the board to HL2 x 72.00 and dropping the pitch to 16.00 mm keeps all
   three bodies on the board and gives every boot 2 mm more room toward the
   extrusion wall, at the price of 1.5 mm of filter-board clearance.

**The two-radio configuration is immune.** It uses only `OUT` and `IN`,
whose centres are **34.80 mm apart** - more than twice the widest boot
estimate. That is why the socket order on the board edge is `OUT`, `AUX`,
`IN`: the two sockets used in the two-radio case are the outer pair, by
design.

**One clearance to check by measurement.** The leftmost boot, at the
pessimistic 17.32 mm, reaches HL2 x 6.60 - 8.66 + 70.50 = **68.44 mm**. The
HL2 board's left edge is x = 70.00 and the extrusion's internal cavity is
about 105 mm across a 100 mm board, putting its inner wall near HL2 x 67.6 -
**roughly 0.8 mm of clearance, and that figure is derived from the enclosure
cross-section, not measured.** Option 4 above is the fix if it fouls.

### 7.4 Height, and stacking still works

Unchanged from rev B.

| | Above the HL2 board top |
|---|---|
| HL2 DB1 / DB12 male header insulator | 2.54 mm |
| 2.54 mm female socket body | 8.50 mm |
| **Board A underside** | **11.04 mm** |
| Board A (1.6 mm) top surface | 12.64 mm |
| **Mini HDMI shell top** | **15.74 mm** (12.64 + 3.10) |
| Cable boot, 12 mm high, centred on the shell | about 8.2 to 20.2 mm |
| Stack-through tails above board A | ~3-6 mm |
| A stacked DB1 companion's own board | ~22.7 mm |

**Board A must not extend past HL2 y = 74.** The RJ45 magjack at (81.1,
62.8) is about 13.5 mm tall and occupies roughly HL2 x 73-89, y 52-73, and
the barrel jack CN2 at (80.8, 47.2) is about 11 mm tall. Board A's underside
sits at 11.04 mm, **below both**, so it must stop short of them rather than
pass over. Verify by measurement.

**A stacked companion board clears the sockets**: the mini HDMI shells
reach 15.74 mm, so a companion at ~22.7 mm passes over them. The cable
boots reach 20.2 mm, which still clears 22.7 mm by 2.5 mm.

The enclosure's rear panel is 104.7 x 54.3 mm, confirming a 55 x 105 mm
cross-section, so there is roughly 40 mm above the HL2 board. Board A's
tallest feature at 15.74 mm uses under half of it.

### 7.5 The endcap cutout

Unchanged from rev B. (This is the HL2 **enclosure endcap** cutout the
cables pass through - not the PCB fabrication panel of section 10, which
shares the word "panel" but is a different thing entirely.)

The three sockets are at **HL2 x 77.10, 94.50, 111.90** on the **y = 140
end** of the board - the end that carries the RF connectors, not the
Ethernet and power end, which the RJ45 magjack blocks. The endcaps are
0.8 mm PCBs (`hardware/enclosure/endcaps/`), so a custom one is
straightforward.

**One slot, not three holes**, because the boots are wider than the sockets
and the middle plug has to go in past its neighbours:

| | |
|---|---|
| Slot width | **HL2 x 68.4 to 120.6**, i.e. 52.2 mm, centred on x 94.5 |
| Slot height | **8.2 to 20.2 mm** above the HL2 board, i.e. 12.0 mm |
| Plug insertion depth needed past the panel | about 7.5 mm (the shell), plus the boot |

The HL2's own front-edge RF connectors (`COMBORFGND` at x 133.3 and 150.3,
y 140) are outside that window.

### 7.6 Board B on the Tang dock - still unverified

Unchanged from rev B. **"User must verify by measurement."** No Tang Mega
138K dock board file, mechanical drawing or 3D model was obtained, so board
B's J14 socket position is a plausible guess and nothing more:

| | |
|---|---|
| Board B | 90.00 x 46.00 mm |
| J14 socket pin 1 hole | local **(6.00, 8.00)** |
| Odd pins (J14 silkscreen "N") | the **y = 8.00** row |
| Even pins ("P") | the **y = 10.54** row |
| Pins ascend | in **+x**, to pins 39/40 at x 54.26 |
| Three Type A sockets | centres at local x **21.00, 45.00, 69.00** (pitch 24.00 mm) on the y = 46.00 edge |

All verified from the Excellon export. The Type A boot is **20.8 mm** wide
(section 7.3), so a 24.00 mm pitch gives **3.2 mm** between adjacent boots -
no problem, and board B has 11 mm of spare board either side if the pitch
needs to grow.

**What to measure on the real dock before ordering:** the distance from the
J14 hole row to the nearest board edge, the clearance to the PMOD sockets,
and which end of J14 is pin 1. Then change `board_b()`'s J14 position in
`tools/gen_gowin_bridge.py` and regenerate.

**Print `templates/tang-bridge-1to1-TOP-fit-check.pdf` at 100 %, measure its
50 mm calibration rule, and offer it up to the dock.**

### 7.7 The bottom-side mirroring trap, re-tested

Unchanged from rev B. KiCad does **not** mirror pad coordinates for a
footprint placed on `B.Cu`. Board A's two sockets must mate a male header
whose hole positions are fixed by the HL2, so the generator mirrors them in
x explicitly. This was proved from the drill export: DB1's odd column lands
at local x **3.54** and its even column at **6.08**, which is the HL2's
grid; there is **no hole at local x = 1.00**, which is where the even column
would be if the mirroring were missing. `tools/check_geometry.py` runs that
specific check every time.

Board B's J14 socket is **not** mirrored, and that is correct: its position
is not fixed by anything, and un-mirrored is what makes the header run in
+x from x = 6.00 instead of off the left edge.

---

## 8. Parts sourcing

Every LCSC number in the BOM has been checked against the live catalogue.
rev C changed several from rev B, each for a stated reason:

| Part | rev B number | rev C number | Why |
|---|---|---|---|
| Quad LVDS driver, DS90LV047ATMX/NOPB | C201946 | **C206491** | Same TI silicon, same pinout - the TMX tape-and-reel suffix. C201946 has zero stock at LCSC and is absent from JLCPCB's library. |
| SN74AVC8T245PWR, 2.5 V/3.3 V translator | C53535 | **C465742** | C53535 does not exist. |
| 2x20 female header (board B J14 socket) | C50982 | **C5124634** | C50982 has zero stock. |
| 2x10 female header (fallback, non-stacking) | C5361769 | **C42431860** | C5361769 does not exist. |
| Clock-A divider shunt resistor | 470 R, C25117 | **330 R, C25104** | C25117 is a real part but not in JLCPCB's assembly library; 330 R is Basic. Two are used in series for 660 R (section 1). |
| 10 uF bulk capacitor | C15525 | **C15850** | C15525 is Samsung CL05A106MQ5NUNC, 10 uF **6.3 V** X5R in **0402** - the wrong package for the 0805 pads it had been assigned, and 6.3 V would have lost most of its capacitance to DC bias on the two 5 V input bulk positions. C15850 is Samsung CL21A106KAYNNNE, 10 uF **25 V** X5R **0805**, JLCPCB Basic, 2,760,420 in stock, $0.085 at its minimum order quantity of 20. |

Four further rev B numbers pointed at parts that were real but not the
value or package claimed, so the design was reworked so none of those
values is needed any more: **C21190 is 0603, not 0402**; **C25746 is
113 k, not 150 R**; **C25867 is 1.5 k, not 1k8** (section 5.2); **C1555 is
22 pF, not 33 pF** (sections 3.1, 5.2).

The surviving passive set is **eleven values**, all confirmed JLCPCB Basic
parts: 0R, 22R, 100R, 330R, 4k7, 10k, 100k, 22pF, 100nF, 1uF and 10uF 25V
0805.

### 8.1 Silicon, connectors and the strap parts

| Part | LCSC | Note |
|---|---|---|
| DS90LV047ATMX/NOPB, quad LVDS driver, SOIC-16 | C206491 | |
| DS90LV048ATMTCX/NOPB, quad LVDS receiver, TSSOP-16 | C87137 | |
| SN74AVC8T245PWR, 8-bit translator | C465742 | Board A only, one per board |
| SN74AVC4T245PWR, 4-bit translator/buffer | C81461 | Board A: two, for the 2.5 V shift. Board B: one, as a gating buffer only (section 2.7) |
| AO3400A N-channel MOSFET, SOT-23, the `ROLE_N` inverter | C20917 | ~890,000 in stock, JLCPCB **Basic**, ~$0.08, Vgs(th) 1.45 V max. One per board. Replaced C7827 (SN74LVC1G04DBVR), which is Extended: no single-gate logic part of any family is Basic in JLCPCB's library, so a gate would have cost the $3.07 loading fee. Section 2.1 and `COST.md` 5a. **Do not substitute the 2N7002** - 2.5 V threshold. |
| ME6211C25M5G-N, 2.5 V LDO | C194395 | Board A only |
| AMS1117-3.3, 3.3 V LDO | C6186 | Both boards |
| 2.54 mm pin header strip (ROLE, option headers) | C2337 | |
| 2.54 mm jumper shunt | C5305 | One per ROLE header, plus the option headers |

### 8.2 The mini HDMI and full-size HDMI sockets, and the pin-1 check

Unchanged from rev B: XKB A71-05H4-111N1 mini HDMI, LCSC **C2682170**, 2,217
in stock, about $0.46 at qty 10; the full-size Amphenol ICC
10029449-111RLF, LCSC **C427307**, 10,000 mating cycles, 3,324 in stock,
$0.51 at qty 10 and qty 50, using the stock KiCad footprint unchanged.

**Which end of the mini HDMI land pattern is pin 1 is still the single
highest-risk item on the board** (section 11) - the footprint is generated
with pin 1 at the +x end, and the XKB drawing does not label its
land-pattern view.

### 8.3 The two parts the user solders himself

Neither exists at LCSC, so both are do-not-place footprints with a
hand-soldered part bought elsewhere:

**(i) A vertical, top-entry 2x3 2.54 mm female socket for HL2 DB12.**
LCSC's vertical female headers start at 2x4, and the one 2x3 they do list
(C99515) is side entry, not vertical. Buy **Samtec SSQ-103-02-S-D** (Mouser
200-SSQ10302SD, about EUR 1.49, only about 19 in stock so check before
relying on it) or cut a 2x4 down.

**(ii) A 2x10 2.54 mm female socket with about 10 mm tails for the HL2 DB1
stack-through.** **Correct here if a stale note is found elsewhere in the
project: Samtec SSQ-120-01-G-D and SSQ-120-01-T-D are the WRONG parts** -
they are **2x20**, not 2x10, with a **2.64 mm** tail, not 10 mm. The right
family is **SSQ-110**, the 2.54 mm 2x10 one with a 0.394 inch = 10.0 mm
tail: buy **Samtec SSQ-110-03-T-D** or **SSQ-110-23-L-D**, or **Phoenix
Enterprises HWS16492** at $0.99, 10.5 mm tails, sold explicitly for board
stacking. LCSC **C42431860** is the fallback ordinary short-pin 2x10 socket
for anyone not stacking a companion board on top.

On the DB1 stack-through, the tails must exist **only** on positions 7, 8,
10, 12, 13, 14, 16, 18, 19 and 20. **Clip the tails of 1, 2, 3, 4, 5, 6, 9,
11, 15 and 17 flush before fitting** - those ten carry the link and must
not reach a stacked board.

---

## 9. Deliberate departures from the brief

| Brief said | What was done | Why |
|---|---|---|
| PIN_88 = DB12 pin 5, PIN_89 = DB12 pin 6 | **Swapped**: PIN_88 = DB12 pin **6**, PIN_89 = DB12 pin **5** | The HL2 netlist says so. `PINMAP.md` 0.1 quotes it. rev A had it wrong and rev A's KiCad files were wired wrong accordingly. Unchanged in rev C - PIN_89 now carries the ROLE strap read instead of a received command, but it is still DB12 pin 5. |
| The LED pins have "1 k to ground" | They are 1 k **pull-ups to +3V3** through the LED | `hermeslite.net`: cathode at the FPGA pin, anode through 1 k to +3V3. Changes the sign of the load: the receiver must sink 1.4 mA, not source it. |
| Resolve the 2.5 V threshold with option (a) or (c) | **(c)**, dual-supply translators, with (d)'s argument documented and bypass links fitted for it | Option (a) does not exist: no discrete LVDS driver specifies `VIH` below 2.0 V. Section 4.1. rev C spreads the same solution across one 8-bit translator (U1) and two 4-bit translators (U7, U8) instead of rev B's one 8-bit and one 4-bit, because the auxiliary channel added four more bidirectional 2.5 V-bank signals. |
| Mini HDMI socket, hybrid SMT + THT shell | XKB A71-05H4-111N1: SMT contacts, **four THT shell legs in plated slots plus two THT locating pegs** | Better than asked for - six through-hole anchors, not just tabs. Unchanged. |
| Three sockets side by side, "state the arithmetic" | Done, and they fit - **but the cable boot, which sets the real pitch, is not published by anyone** | Section 7.3 gives both estimates and the clearance each implies. The pessimistic one leaves 0.08 mm. The middle socket carries the auxiliary channel in rev C rather than a second fixed-direction lane group, but the geometry argument is unchanged. |
| Grounded M3 mounting holes on both boards | Board B has two; **board A has none** | No mounting boss inside the HL2 enclosure was identified for a hole to line up with, and board A is carried by DB1, DB12 and the panel. Grounding is the J8 header plus two through-hole pads. Adding holes to a 48 mm-wide board that is already tight for the socket fan-outs costs layout room for no known benefit. Unchanged; board A is if anything tighter in rev C, carrying 10 ICs instead of 7. |
| 22 ohm series resistors on the driver inputs | **Not fitted on board A** (board B has them) | On board A the driver inputs are driven by the translators' B-side outputs over a trace under 10 mm long, already controlled. Board B's driver inputs come from a J14 header pin over a longer unterminated run, so they keep the 22 ohm. Unchanged in rev C. |

---

## 10. The production panel

**94.00 x 100.00 mm, two designs, 4 layer, 1.6 mm.** Both boards ship on one
panel so the whole set is one JLCPCB order. (Not to be confused with the
HL2 enclosure endcap cutout of section 7.5, which is also sometimes called a
"panel" opening but is a different piece of hardware entirely.)

Board A sits at panel (0, 29), unrotated, occupying panel x 0-48, y 29-95.
Board B sits **rotated 90 degrees**, with its local origin at panel (48,
95), occupying panel x 48-94, y 5-95 - board B's local x runs down the
panel and its local y runs across it, so its socket edge (local y = 46)
lands on the outer panel edge x = 94.

**Board B rotated is the only arrangement that fits inside 100 x 100 mm.**
Every other combination overflows: board B unrotated is 138 mm wide side by
side and 112 mm tall stacked; board A rotated gives 156 mm.

```
  y 100  +-------------------------+--------+   <- top rail, V-score at y = 95
   95    |  board A  48 x 66       | board  |
         |  socket edge at y = 95  |   B    |
         |  (V-scored: clean edge, |        |
         |   no nubs)              | 46 x 90|
   29    +==== mouse bites ========+ rotated|
         |  coupon 48 x 22         | socket |
         |  fiducials + label      | edge at|
    5    +-------------------------+ x = 94 |   <- bottom rail, V-score at y = 5
    0    +-------------------------+--------+
         x 0                     48       94
                                  ^
                       V-score at x = 48, full height
```

**Three V-scores: y = 5, y = 95, x = 48.** Each straight, each running edge
to edge, each with material on both sides for its whole length. The
assembly rails straddle x = 48, which is what supports that score over the
top and bottom 5 mm, and the last mouse-bite tab (x 43.5-48) is the only
thing holding material against that score over y 27-29.

**5 mm assembly rails on the y axis**, at y 0-5 and y 95-100, because the y
axis had 10 mm spare and the x axis had only 6 mm.

**One routed separation with mouse bites, at y = 29**, which is board A's
**back** edge and not a socket edge. A 2.00 mm routed channel with four tabs
at x 0-4, 12-17, 28-33 and 43.5-48, and 16 perforations of 0.50 mm on a
1.00 mm pitch centred on the y = 29 break line. No perforation comes within
1.75 mm of the x = 48 V-score or 1.50 mm of the panel's left edge. The two
outer tabs run right up to x = 0 and x = 48 so that every routed gap is a
closed slot - an outline that opens onto a board edge is not a closed shape,
and KiCad rejects it.

**The channel is taken entirely out of the coupon side**, so board A stays
exactly 66.00 mm and the nubs protrude **outward** from its back edge.

**The 0.3 mm the mouse-bite joint costs.** The perforations are centred on
the break line, so after snapping, nubs of roughly half a hole radius -
about **0.3 mm** - protrude past board A's nominal back edge. That edge
faces the HL2's magjack, whose clearance drops from **1.0 mm to 0.7 mm**.
**File the nubs flat after snapping** - this is a required assembly step,
not an optional tidy-up.

**Both socket edges land on an outer panel edge or on a V-score**, so there
are no nubs anywhere a plug goes. That is why the mouse bites were put on
board A's back edge specifically.

**The coupon is 48 x 22 mm, not the 48 x 24 mm in the first sketch**: the
2 mm routed channel has to come out of something, and board A's 66 mm and
the panel's 100 mm are both fixed. It carries two of the three fiducials
and the panel label.

**Three fiducials**, 1 mm bare copper with a 2 mm mask opening: two on the
coupon at (6, 10) and (42, 10), and one on the top rail at (89, 97.5) - a
long baseline, and deliberately not a symmetric set, so the placement
machine cannot fit the panel the wrong way round.

**Two body overhangs, both real and both worth recording.** Board A's mini
HDMI bodies reach 0.50 mm past the y = 95 V-score into the top rail, which
is scrap - **snap the top rail off before doing anything else.** Board B's
Type A bodies reach 0.10 mm past the outer panel edge at x = 94. Neither is
copper - the mini HDMI footprint's pads all sit inboard - so DRC is clean,
but the 0.10 mm at the panel edge is worth confirming with the fab. Also
note that V-scoring happens at fabrication, **before** assembly, so the
scoring blade never meets a component.

**Two placement changes the panel forced on board B**, both real: its
option headers (`RX MODE`, `ROLE`) moved from local y = 2 to y = 4, because
on the panel board B's local y is the distance from the x = 48 score and
they sat 0.55 mm from it against the fab's 1.00 mm minimum for a component
body; and its mounting holes moved from local x 4/86 to 6/84, because a
3.2 mm pad was 0.8 mm from a score.

**JLCPCB's Economic assembly service states a panelisation rule of
mouse-bite separations only; Standard allows mouse-bite or V-cut.** This
panel mixes both. **Flag it for the fab before ordering.** The fallback, if
the fab queries the panel: order the two boards as two separate jobs, at
about $9.70 more at two sets; `COST.md` prices both.

---

## 11. Everything unverified, in one list

1. **The mini HDMI land pattern's pin-1 end.** Section 8.2. Highest-risk
   item on the board: the footprint assumes pin 1 at the +x end and the XKB
   drawing does not label its land-pattern view. If the part in hand
   disagrees, set `MINI_HDMI['pin1_at_plus_x'] = False` in
   `tools/gen_gowin_bridge.py` and regenerate.
2. **The mini HDMI cable boot width** against the 17.40 mm socket pitch, and
   therefore whether three cables plug in at once. Section 7.3. Estimates
   15.6 to 17.3 mm against 17.4 mm of pitch. **Measure your cables.**
3. **Board B's position on the Tang dock**, including which end of J14 is
   pin 1. Section 7.6. Print the template.
4. **The HL2's spare +3V3 current.** Board A now needs more than rev B's
   ~112 mA, because it carries three more ICs than rev B did (the second
   AUX driver, the second AUX receiver, the second 2.5 V translator and the
   ROLE inverter). The figure needs recomputing and then measuring with
   board A plugged in. Section 6.1.
5. **PIN_80's 1.49 ns edge** as a calculation rather than a datasheet
   guarantee. Sections 1, 3.2.
6. **The auxiliary channel's real achievable rate.** 76.8 Mbit/s is the
   recommendation, not a measurement; the hardware is rated to 307.2
   Mbit/s. Section 2.8.
7. **The uFL stub on PIN_72.** Its effect on the auxiliary G2 clock at
   speed has not been measured. Section 2.8.
8. **Whether JLCPCB accepts a panel mixing V-score and mouse bites.** Their
   Economic service states mouse-bite-only; Standard allows either.
   Section 10.
9. **The 0.10 mm body overhang at the panel's x = 94 edge** (board B's Type
   A connector bodies). Section 10.
10. **The SMT solder-joint count and therefore the exact assembly fee** -
    JLCPCB will not compute it without a login and a CPL file.
11. **Shipping costs from Mouser and Phoenix Enterprises to Germany**, for
    the two hand-soldered sockets. Section 8.3.
12. **Whether the Cyclone IV C8 can capture 307.2 Mbit/s DDR** on bank-6
    inputs in soft logic. This now gates every lane in the design, not only
    the reverse link as in rev B. Section 3.1.
13. **The SN74AVC4T245's 380 Mbit/s rating against the 153.6 MHz reverse
    clock** (81 % of rating). Scope check at bring-up. Section 4.4.
14. **Whether DB12 ships fitted** on a factory-built HL2. The HL2 BOM says
    "do not install"; assume you solder it.
15. **Whether a board A plugged into DB1 pins 11/15/17 while the HL2 still
    runs stock LED gateware causes contention.** The `RX MODE` jumper exists
    to hold the receivers off until the right gateware is loaded, and the
    default setting keeps them off whenever the `IN` cable is unplugged.
16. **Whether the N2ADR filter board is clear of board A in z.** Reduces to
    the 1.55 mm edge-to-edge gap in plan view; rev B established this and
    rev C did not move board A.
17. **Whether the Tang dock's mounting holes are grounded** (dock schematic
    not obtained), which is why board B has the `GND AUX` header.
18. **How much current J14 pin 11 can supply.** Section 6.2.
19. **The clearance from the leftmost cable boot to the extrusion's inner
    wall** - about 0.8 mm, derived from the enclosure cross-section rather
    than measured. Section 7.3.
20. **Board A's and board B's full rev C current draw.** The strap-gated
    buffers and the inverter on each board are not yet in either power
    table. Sections 6.1, 6.2.
